# core/managers/config_manager.py
#
# Parámetros globales del equipo (planeacion_opciones.md v4 §3.2; O2a, tanda 6).
#
# - `config/global_params.json` es la ÚNICA fuente de los valores de fábrica:
#   valor (= defecto), tipo, unidad, clase, mínimo, máximo, submenú (`grupo`)
#   y si es de solo lectura.
# - Con la base de datos vinculada (`vincular_bd`), el valor vigente sale de la
#   tabla `system_params`; un cambio (`fijar` / `restablecer`) se escribe
#   primero en la base y después en memoria, y todo lector que llame a get()
#   lo ve en el siguiente acceso, sin reiniciar (OPC-11).
# - Sin base (arranque degradado), valen los de fábrica y no se puede cambiar.
# - Erratas corregidas (`presion_admosferica`, `intervalo_imprecion_*`): la
#   clave canónica es la correcta; los nombres viejos se aceptan como alias en
#   get() y en el archivo, para no romper lectores ni instalaciones previas.

import json
import logging
import math
import os
import threading
from datetime import datetime

from autoclave.utils.resources import resource_path

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# nombre viejo (errata) -> clave canónica
ALIAS = {
    "presion_admosferica": "presion_atmosferica",
    "intervalo_imprecion_esterilizacion": "intervalo_impresion_esterilizacion",
}

# SAF-01 de O2a (DECISIÓN SIN CONFIRMAR): coherencia entre parámetros de
# empaque y la atmosférica calibrada, para que la puerta no se dé por sellada
# sin estarlo ni por retraída con el empaque inflado. kPa.
MARGEN_EMPAQUE_SOBRE_ATM = 20.0     # presion_empaque >= atm + 20
MARGEN_VACIO_BAJO_ATM = 10.0        # vacio_empaque <= atm - 10
FACTOR_CHEQUEO_CICLO = 0.6          # ciclo.py: falla si empaque < presion_empaque*0.6

# D9-3 (tanda 9): "camara_segura" (temp_max_apertura y rango_presion_atm, antes
# en "puerta") se muestra en todo equipo; "puerta" y "empaque" no aplican a
# un equipo de puertas simples.
# F1 (tanda 16): los límites de presión del equipo (DEU-01), el corte de
# chaqueta (D-CHQ) y los aislamientos (VCH) van en "chaqueta" (DECISIÓN SIN
# CONFIRMAR: un submenú nuevo cambiaría la pantalla fijada por O2a/P9).
GRUPOS = ("puerta", "camara_segura", "impresion", "drenaje", "empaque", "chaqueta", "sistema")
_GRUPOS_SIN_PUERTAS_SIMPLES = frozenset({"puerta", "empaque"})


# F1 (tanda 16): parámetros con regla cruzada de límites de presión
CLAVES_LIMITES_PRESION = _CLAVES_LIMITES_PRESION = ("presion_fondo_escala", "presion_suministro_vapor",
                           "presion_alivio_camara", "presion_alivio_chaqueta",
                           "presion_max_chaqueta_control")


def grupos_visibles(puertas_simples: bool) -> list[str]:
    """Submenús de Parámetros del equipo que se muestran, en su orden."""
    if not puertas_simples:
        return list(GRUPOS)
    return [g for g in GRUPOS if g not in _GRUPOS_SIN_PUERTAS_SIMPLES]


class ErrorParametro(Exception):
    """Cambio rechazado. `codigo`: no_existe, solo_lectura, tipo_invalido,
    fuera_de_rango, incoherente_empaque, incoherente_limites,
    sin_base_de_datos. `detalle`: dict con la regla incumplida y los valores
    (A7, tanda 27; solo en los dos de coherencia, si no {})."""

    def __init__(self, codigo: str, mensaje: str = "", detalle: dict | None = None):
        super().__init__(mensaje or codigo)
        self.codigo = codigo
        self.detalle = detalle or {}


# A7 (tanda 27): un código por familia de reglas de coherencia (antes los dos
# eran "incoherente" y la pantalla decía siempre el texto de empaque)
INCOHERENTE_EMPAQUE = "incoherente_empaque"
INCOHERENTE_LIMITES = "incoherente_limites"
CODIGOS_INCOHERENCIA = (INCOHERENTE_EMPAQUE, INCOHERENTE_LIMITES)
# reglas del detalle (`detalle["regla"]`)
REGLAS_EMPAQUE = ("sin_referencia", "empaque_sobre_atm", "empaque_chequeo_ciclo",
                  "vacio_bajo_atm", "vacio_bajo_empaque")
REGLAS_LIMITES = ("sin_referencia", "suministro_bajo_alivio", "alivio_bajo_fondo",
                  "corte_bajo_alivio_chaqueta")
CLAVES_EMPAQUE = ("presion_empaque", "vacio_empaque", "presion_atmosferica")


def canonica(clave: str) -> str:
    return ALIAS.get(clave, clave)


def _es_numero(v) -> bool:
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(float(v)))


class ConfigManager:
    def __init__(self):
        self.config = {}
        self._fabrica = {}          # clave -> valor de fábrica (defecto)
        self._meta = {}             # clave -> {"usuario", "fecha"} del último cambio
        self._db = None
        self._lock = threading.Lock()
        # serializa un cambio completo (escritura, aplicación o reversión):
        # dos PATCH simultáneos no se validan contra valores viejos (SAF-01 2ª)
        self.lock_cambios = threading.RLock()

    # ── carga ────────────────────────────────────────────────────────────
    def load_config(self):
        path = resource_path("autoclave/config/global_params.json")

        with open(path, "r", encoding="utf-8") as f:
            datos = json.load(f)
        config = {}
        for clave, entrada in datos.items():
            c = canonica(clave)
            if c in config and c != clave:
                continue                       # la canónica gana sobre el alias
            config[c] = entrada
        self.config = config
        self._fabrica = {c: e.get("value") for c, e in config.items() if isinstance(e, dict)}
        self._meta = {}

    def vincular_bd(self, db) -> None:
        """Toma de `system_params` los valores vigentes y siembra los que
        falten con el de fábrica. Una fila fuera del rango vigente o de otro
        tipo se ignora (vale el de fábrica) y queda en el log. Nunca lanza:
        sin base, siguen los de fábrica."""
        try:
            filas = db.listar_parametros_sistema()
        except Exception:
            logger.exception("system_params no disponible: rigen los valores de fábrica")
            return
        sembrar = []
        with self._lock:
            self._db = db
            for clave, entrada in self.config.items():
                if not isinstance(entrada, dict) or "value" not in entrada:
                    continue
                fila = filas.get(clave)
                if fila is None:
                    for viejo, nuevo in ALIAS.items():   # fila guardada con la errata
                        if nuevo == clave and viejo in filas:
                            fila = filas[viejo]
                if fila is None:
                    sembrar.append((clave, entrada))
                    continue
                valor = fila.get("valor")
                if self._validar(clave, entrada, valor, permitir_solo_lectura=True)[0] is None:
                    logger.warning("system_params.%s = %r fuera de rango o tipo: vale el de fábrica %r",
                                   clave, valor, self._fabrica.get(clave))
                    continue
                entrada["value"] = self._normalizar(entrada, valor)
                self._meta[clave] = {"usuario": fila.get("usuario") or "", "fecha": fila.get("fecha")}
        for clave, entrada in sembrar:
            self._sembrar(clave, entrada)

    def _sembrar(self, clave, entrada) -> None:
        try:
            self._db.guardar_parametro_sistema(clave, entrada.get("value"), self._fabrica.get(clave),
                                               entrada.get("min"), entrada.get("max"))
        except Exception:
            logger.exception("No se pudo sembrar system_params.%s", clave)

    # ── lectura ──────────────────────────────────────────────────────────
    def get(self, *keys, default=None):
        data = self.config

        for i, key in enumerate(keys):
            if i == 0 and isinstance(key, str):
                key = canonica(key)
            data = data.get(key, {})

        if isinstance(data, dict) and "value" in data:
            return data["value"]

        return data if data != {} else default

    def instantanea(self) -> dict:
        """Copia de todo el archivo con los valores vigentes (GET /global_params)."""
        with self._lock:
            return json.loads(json.dumps(self.config))

    def describir(self, clave: str | None = None):
        """Lista (o una entrada) con lo que necesita la ventana de ajuste."""
        def una(c):
            e = self.config[c]
            meta = self._meta.get(c, {})
            # A7 (tanda 27): rango que la validación acepta hoy con los demás
            # parámetros vigentes (igual a min/max si no hay acople)
            min_ef, max_ef = self._rango_efectivo(c, e)
            return {
                "min_efectivo": min_ef, "max_efectivo": max_ef,
                "clave": c, "grupo": e.get("grupo", ""), "valor": e.get("value"),
                "defecto": self._fabrica.get(c), "min": e.get("min"), "max": e.get("max"),
                "tipo": e.get("type", ""), "unidad": e.get("unit", ""), "clase": e.get("clase", ""),
                "solo_lectura": bool(e.get("solo_lectura")),
                "ultima_modificacion": ({"usuario": meta.get("usuario", ""), "fecha": meta.get("fecha")}
                                        if meta.get("fecha") else None),
            }
        with self._lock:
            if clave is not None:
                c = canonica(clave)
                if not isinstance(self.config.get(c), dict) or "value" not in self.config[c]:
                    raise ErrorParametro("no_existe", f"Parámetro desconocido: {clave}")
                return una(c)
            return [una(c) for c, e in self.config.items() if isinstance(e, dict) and "value" in e]

    # ── escritura ────────────────────────────────────────────────────────
    @staticmethod
    def _normalizar(entrada, valor):
        return int(round(float(valor))) if entrada.get("type") == "int" else float(valor)

    def _validar(self, clave, entrada, valor, permitir_solo_lectura=False):
        """(valor normalizado, "") o (None, código de error)."""
        if entrada.get("solo_lectura") and not permitir_solo_lectura:
            return None, "solo_lectura"
        if not _es_numero(valor):
            return None, "tipo_invalido"
        if entrada.get("type") == "int" and not float(valor).is_integer():
            return None, "tipo_invalido"
        v = self._normalizar(entrada, valor)
        minimo, maximo = entrada.get("min"), entrada.get("max")
        if (minimo is not None and v < minimo) or (maximo is not None and v > maximo):
            return None, "fuera_de_rango"
        return v, ""

    def _incoherencia(self, clave, nuevo) -> str:
        """'' o el código de la regla incumplida (SAF-01; A7, tanda 27:
        incoherente_empaque o incoherente_limites). Usa los valores vigentes
        de los demás. El detalle lo da `_incoherencia_detalle`."""
        return self._incoherencia_detalle(clave, nuevo)[0]

    def _incoherencia_detalle(self, clave, nuevo) -> tuple[str, dict]:
        """('', {}) o (código, detalle). Las reglas y márgenes son los de
        siempre; A7 solo separa el código y agrega el detalle."""
        if clave in _CLAVES_LIMITES_PRESION:
            return self._incoherencia_limites(clave, nuevo)
        if clave not in CLAVES_EMPAQUE:
            return "", {}
        vigentes = {k: (self.config.get(k) or {}).get("value") for k in CLAVES_EMPAQUE}
        v = dict(vigentes)
        v[clave] = nuevo
        pe, ve, atm = v["presion_empaque"], v["vacio_empaque"], v["presion_atmosferica"]
        if not all(_es_numero(x) for x in (pe, ve, atm)):
            regla = "sin_referencia"             # fail-closed sin referencia
        elif pe < atm + MARGEN_EMPAQUE_SOBRE_ATM:
            regla = "empaque_sobre_atm"
        elif pe * FACTOR_CHEQUEO_CICLO <= atm:
            regla = "empaque_chequeo_ciclo"
        elif ve > atm - MARGEN_VACIO_BAJO_ATM:
            regla = "vacio_bajo_atm"
        elif ve >= pe:
            regla = "vacio_bajo_empaque"
        else:
            return "", {}
        return INCOHERENTE_EMPAQUE, {
            "regla": regla, "clave": clave, "vigentes": vigentes, "propuestos": v,
            "presion_empaque": pe, "vacio_empaque": ve, "presion_atmosferica": atm,
            "margen_empaque_sobre_atm": MARGEN_EMPAQUE_SOBRE_ATM,
            "margen_vacio_bajo_atm": MARGEN_VACIO_BAJO_ATM,
            "factor_chequeo_ciclo": FACTOR_CHEQUEO_CICLO,
        }

    def _incoherencia_limites(self, clave, nuevo) -> tuple[str, dict]:
        """F1 (tanda 16). DEU-01 (D-DEU-1): suministro < alivio <= fondo de
        escala, para los dos alivios. D-CHQ: presion_max_chaqueta_control <=
        alivio de chaqueta - 10. Bajar el alivio por debajo del corte vigente
        + 10 también se rechaza. Fail-closed sin valor de referencia.
        La decisión sigue siendo `limites_coherentes` + el corte; la regla del
        detalle solo clasifica cuál falló (A7)."""
        from autoclave.core.managers import limites_equipo as le
        vigentes = {k: (self.config.get(k) or {}).get("value") for k in _CLAVES_LIMITES_PRESION}
        v = dict(vigentes)
        v[clave] = nuevo
        fondo, sumi = v["presion_fondo_escala"], v["presion_suministro_vapor"]
        a_cam, a_chq = v["presion_alivio_camara"], v["presion_alivio_chaqueta"]
        if not all(_es_numero(x) for x in v.values()):
            regla = "sin_referencia"
        elif not le.limites_coherentes(fondo, sumi, a_cam, a_chq):
            if sumi >= a_cam or sumi >= a_chq:
                regla = "suministro_bajo_alivio"
            elif a_cam > fondo or a_chq > fondo:
                regla = "alivio_bajo_fondo"
            else:
                regla = "sin_referencia"
        elif v["presion_max_chaqueta_control"] > a_chq - le.MARGEN_CORTE_BAJO_ALIVIO:
            regla = "corte_bajo_alivio_chaqueta"
        else:
            return "", {}
        return INCOHERENTE_LIMITES, {
            "regla": regla, "clave": clave, "vigentes": vigentes, "propuestos": v,
            "margen_corte_bajo_alivio": le.MARGEN_CORTE_BAJO_ALIVIO,
        }

    # ── rango efectivo (A7, tanda 27) ────────────────────────────────────
    def _valido_para_rango(self, clave, entrada, valor) -> bool:
        """La MISMA validación de `fijar` (rango propio + coherencia), sin
        solo_lectura ni base: el rango mostrado sale de ella, no de otra regla."""
        v, error = self._validar(clave, entrada, valor, permitir_solo_lectura=True)
        return not error and not self._incoherencia(clave, v)

    def _rango_efectivo(self, clave, entrada) -> tuple:
        """(min_efectivo, max_efectivo) de un parámetro acoplado: el intervalo
        de valores que `fijar` aceptaría con los demás vigentes. Se busca por
        bisección desde el valor vigente con la propia validación (las reglas
        dan un intervalo: cada una acota de un solo lado), en pasos de 1 (int)
        o de 0,01 (float, el redondeo de la ventana de ajuste). Sin acople,
        (min, max). Sin valor vigente válido o sin rango: (None, None)."""
        minimo, maximo = entrada.get("min"), entrada.get("max")
        if clave not in _CLAVES_LIMITES_PRESION and clave not in CLAVES_EMPAQUE:
            return minimo, maximo
        actual = entrada.get("value")
        if (not _es_numero(minimo) or not _es_numero(maximo) or not _es_numero(actual)
                or not self._valido_para_rango(clave, entrada, actual)):
            return None, None
        paso = 1 if entrada.get("type") == "int" else 100       # unidades por kPa
        def valor(n):
            return n if paso == 1 else n / 100.0
        def ok(n):
            return self._valido_para_rango(clave, entrada, valor(n))
        lo_n = math.ceil(minimo * paso)
        hi_n = math.floor(maximo * paso)
        cur_n = round(actual * paso)
        # menor válido en [lo_n, cur_n]
        a, b = lo_n, cur_n
        while a < b:
            m = (a + b) // 2
            if ok(m):
                b = m
            else:
                a = m + 1
        menor = a
        # mayor válido en [cur_n, hi_n]
        a, b = cur_n, hi_n
        while a < b:
            m = (a + b + 1) // 2
            if ok(m):
                a = m
            else:
                b = m - 1
        return valor(menor), valor(a)

    def fijar(self, clave: str, valor, usuario: str = "", permitir_solo_lectura: bool = False,
              aplicar: bool = True):
        """Valida y guarda en la base; con `aplicar`, también en memoria.
        Devuelve (anterior, nuevo). Con aplicar=False el llamador aplica luego
        con `aplicar_valor` (dentro del guard de estado, sin E/S: TMG-01) o
        deshace con `revertir_bd`. `permitir_solo_lectura` solo para la
        calibración atmosférica (O2f): la API nunca lo pasa."""
        c = canonica(clave)
        with self._lock:
            entrada = self.config.get(c)
            if not isinstance(entrada, dict) or "value" not in entrada:
                raise ErrorParametro("no_existe", f"Parámetro desconocido: {clave}")
            nuevo, error = self._validar(c, entrada, valor, permitir_solo_lectura)
            detalle = {}
            if not error:
                error, detalle = self._incoherencia_detalle(c, nuevo)
            if error:
                raise ErrorParametro(error, detalle=detalle)
            if self._db is None:
                raise ErrorParametro("sin_base_de_datos")
            anterior = entrada.get("value")
            minimo, maximo, db = entrada.get("min"), entrada.get("max"), self._db
        fecha = datetime.now().isoformat(timespec="seconds")
        try:                                   # E/S fuera del lock propio (TMG-04)
            db.guardar_parametro_sistema(c, nuevo, self._fabrica.get(c), minimo, maximo,
                                         usuario, fecha)
        except Exception as e:
            logger.exception("No se pudo guardar system_params.%s", c)
            raise ErrorParametro("sin_base_de_datos") from e
        if aplicar:
            self.aplicar_valor(c, nuevo, usuario, fecha)
        self._pendiente = {"clave": c, "fecha": fecha}
        return anterior, nuevo

    def aplicar_valor(self, clave: str, nuevo, usuario: str = "", fecha: str | None = None) -> None:
        """Solo memoria (sin E/S): seguro dentro del guard de estado."""
        c = canonica(clave)
        fecha = fecha or (getattr(self, "_pendiente", None) or {}).get("fecha")             or datetime.now().isoformat(timespec="seconds")
        with self._lock:
            anterior = self.config[c].get("value")
            self.config[c]["value"] = nuevo
            self._meta[c] = {"usuario": usuario or "", "fecha": fecha}
        logger.info("Parámetro del equipo %s: %r -> %r (%s)", c, anterior, nuevo, usuario)

    def revertir_bd(self, clave: str, anterior) -> None:
        """Deshace en la base un `fijar(aplicar=False)` que no se aplicó."""
        c = canonica(clave)
        meta = self._meta.get(c, {})
        e = self.config[c]
        try:
            self._db.guardar_parametro_sistema(c, anterior, self._fabrica.get(c), e.get("min"),
                                               e.get("max"), meta.get("usuario", ""), meta.get("fecha"))
        except Exception:
            logger.exception("No se pudo revertir system_params.%s", c)

    def restablecer(self, clave: str, usuario: str = "", aplicar: bool = True):
        c = canonica(clave)
        if c not in self._fabrica:
            raise ErrorParametro("no_existe", f"Parámetro desconocido: {clave}")
        return self.fijar(c, self._fabrica[c], usuario, aplicar=aplicar)

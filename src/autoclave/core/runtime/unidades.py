# core/runtime/unidades.py
#
# U1 (tanda 5; decisión 6 de Cristian, 20-oct): unidades de PRESENTACIÓN y de
# entrada de datos. Control, alarmas, umbrales, BD, calibración, JSON de ciclos
# y API siguen en °C y kPa ABSOLUTOS. Este módulo solo convierte lo que se
# muestra o se teclea; ningún módulo de control, puertas ni alarmas lo importa
# (prueba estática en tests/test_u1_unidades.py).
#
# - Temperatura: °C o °F. Kelvin no se ofrece.
# - Presión: kPa, bar o mbar, siempre absolutos; o psi, siempre manométrico
#   (psig) y, por debajo de la atmosférica, pulgadas de mercurio de vacío
#   (inHg). Nunca un psi negativo. La relativa/absoluta va ligada a la unidad.
# - Las DIFERENCIAS y tasas (histéresis, °C/min, kPa/min, bandas ±, márgenes)
#   se escalan sin desplazamiento: Δ°F = 1,8·Δ°C; Δpsi = ΔkPa / 6,894757.
# - P_atm es la presión atmosférica calibrada del equipo (presion_admosferica),
#   nunca 101,325 inventado: sin valor vigente, en psi se muestra "—".
# - Formato con punto decimal, como el formateador único de la interfaz
#   (ui_qml/domain/formato_numerico.py, TEC-D14).

import logging
import math

logger = logging.getLogger(__name__)

TEMPERATURAS = ("C", "F")
PRESIONES = ("kPa", "bar", "mbar", "psi")
POR_DEFECTO = {"temperatura": "C", "presion": "kPa"}

KPA_POR_PSI = 6.894757
KPA_POR_INHG = 3.386389

# Resolución de presentación (DECISIÓN SIN CONFIRMAR U1-1)
DECIMALES = {"C": 1, "F": 1, "kPa": 1, "bar": 2, "mbar": 0, "psig": 1, "inHg": 1}
SIMBOLOS = {"C": "°C", "F": "°F", "kPa": "kPa", "bar": "bar", "mbar": "mbar",
            "psig": "psig", "inHg": "inHg"}
SIN_DATO = "—"
# Diferencias pequeñas (brechas de décimas): un decimal más en °F y psi, para
# que valores distintos no se vean iguales (revisión U1, SAF-04)
DECIMALES_DIFERENCIA = {"C": 1, "F": 2, "kPa": 1, "bar": 3, "mbar": 0, "psi": 2}
# Parámetros que NO se convierten (revisión U1, SAF-03): rango_calentamiento
# era a la vez banda de temperatura y de presión en calentamiento.py. Desde
# R1-P3 (tanda 7) se separa en rango_calentamiento_temp/_pres (clase
# "diferencia"); el nombre viejo queda aquí solo para un archivo sin migrar.
SIN_CONVERSION = frozenset({"rango_calentamiento"})
# P_atm admisible (mismo rango que validacion_config.py)
P_ATM_MIN, P_ATM_MAX = 50.0, 110.0


def _finito(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validar(temperatura: str, presion: str) -> None:
    if temperatura not in TEMPERATURAS:
        raise ValueError(f"Unidad de temperatura inválida: {temperatura!r}")
    if presion not in PRESIONES:
        raise ValueError(f"Unidad de presión inválida: {presion!r}")


# ── temperatura ─────────────────────────────────────────────────────────────

def temp_a_mostrar(c: float, unidad: str) -> float:
    return c * 1.8 + 32.0 if unidad == "F" else float(c)


def temp_a_interna(v: float, unidad: str) -> float:
    return (v - 32.0) / 1.8 if unidad == "F" else float(v)


def dtemp_a_mostrar(dc: float, unidad: str) -> float:
    return dc * 1.8 if unidad == "F" else float(dc)


def dtemp_a_interna(dv: float, unidad: str) -> float:
    return dv / 1.8 if unidad == "F" else float(dv)


# ── presión ─────────────────────────────────────────────────────────────────

def pres_a_mostrar(kpa_abs: float, unidad: str, p_atm: float | None = None):
    """(valor, unidad_mostrada) o (None, unidad) si no se puede (psi sin P_atm).
    En psi: psig si P >= P_atm, inHg de vacío si P < P_atm."""
    if unidad == "kPa":
        return float(kpa_abs), "kPa"
    if unidad == "bar":
        return kpa_abs / 100.0, "bar"
    if unidad == "mbar":
        return kpa_abs * 10.0, "mbar"
    if unidad == "psi":
        if not _finito(p_atm):
            return None, "psig"
        if kpa_abs >= p_atm:
            return (kpa_abs - p_atm) / KPA_POR_PSI, "psig"
        return (p_atm - kpa_abs) / KPA_POR_INHG, "inHg"
    raise ValueError(f"Unidad de presión inválida: {unidad!r}")


def pres_a_interna(v: float, unidad: str, p_atm: float | None = None) -> float:
    """Valor tecleado en `unidad` ('kPa', 'bar', 'mbar', 'psig', 'inHg') a kPa
    absolutos. psig/inHg exigen P_atm; un psig o inHg negativo es inválido."""
    if unidad == "kPa":
        return float(v)
    if unidad == "bar":
        return v * 100.0
    if unidad == "mbar":
        return v / 10.0
    if unidad in ("psig", "inHg", "psi"):
        if not _finito(p_atm):
            raise ValueError("Sin presión atmosférica calibrada: no se puede convertir psi")
        if v < 0:
            raise ValueError("En psi no existen valores negativos: use inHg para vacío")
        if unidad == "inHg":
            return p_atm - v * KPA_POR_INHG
        return p_atm + v * KPA_POR_PSI
    raise ValueError(f"Unidad de presión inválida: {unidad!r}")


def dpres_a_mostrar(dkpa: float, unidad: str) -> tuple[float, str]:
    """Diferencia o tasa de presión: escala sin restar la atmósfera."""
    if unidad == "kPa":
        return float(dkpa), "kPa"
    if unidad == "bar":
        return dkpa / 100.0, "bar"
    if unidad == "mbar":
        return dkpa * 10.0, "mbar"
    if unidad == "psi":
        return dkpa / KPA_POR_PSI, "psi"
    raise ValueError(f"Unidad de presión inválida: {unidad!r}")


def dpres_a_interna(dv: float, unidad: str) -> float:
    if unidad == "kPa":
        return float(dv)
    if unidad == "bar":
        return dv * 100.0
    if unidad == "mbar":
        return dv / 10.0
    if unidad in ("psi", "psig"):
        return dv * KPA_POR_PSI
    raise ValueError(f"Unidad de presión inválida: {unidad!r}")


def p_atm_valida(v) -> float | None:
    """P_atm usable para psi, o None (sin valor o fuera de 50-110 kPa)."""
    return float(v) if _finito(v) and P_ATM_MIN <= v <= P_ATM_MAX else None


def unidades_de_ingreso_psi(minimo_kpa: float | None, maximo_kpa: float | None,
                            p_atm: float | None) -> list[str]:
    """En psi, si el rango del parámetro cruza la atmosférica se ofrece elegir
    psig o inHg (DECISIÓN SIN CONFIRMAR U1-2); si no, la unidad es fija."""
    if not _finito(p_atm):
        return []
    if minimo_kpa is not None and minimo_kpa >= p_atm:
        return ["psig"]
    if maximo_kpa is not None and maximo_kpa < p_atm:
        return ["inHg"]
    return ["psig", "inHg"]


# ── formato ─────────────────────────────────────────────────────────────────

def _texto(valor, unidad_mostrada: str, con_simbolo: bool) -> str:
    if not _finito(valor):
        return SIN_DATO
    d = DECIMALES.get(unidad_mostrada, 1)
    texto = f"{valor:.{d}f}"
    if texto.startswith("-") and float(texto) == 0:
        texto = texto[1:]
    return f"{texto} {SIMBOLOS.get(unidad_mostrada, unidad_mostrada)}" if con_simbolo else texto


def formatear_temp(c, unidad: str, con_simbolo: bool = True) -> str:
    if not _finito(c):
        return SIN_DATO
    return _texto(temp_a_mostrar(c, unidad), unidad, con_simbolo)


def formatear_dtemp(dc, unidad: str, con_simbolo: bool = True) -> str:
    if not _finito(dc):
        return SIN_DATO
    v = dtemp_a_mostrar(dc, unidad)
    texto = f"{v:.{DECIMALES_DIFERENCIA.get(unidad, 1)}f}"
    return f"{texto} {SIMBOLOS[unidad]}" if con_simbolo else texto


def formatear_pres(kpa_abs, unidad: str, p_atm: float | None = None,
                   con_simbolo: bool = True) -> str:
    if not _finito(kpa_abs):
        return SIN_DATO
    valor, mostrada = pres_a_mostrar(kpa_abs, unidad, p_atm)
    return _texto(valor, mostrada, con_simbolo)


def formatear_dpres(dkpa, unidad: str, con_simbolo: bool = True) -> str:
    if not _finito(dkpa):
        return SIN_DATO
    valor, mostrada = dpres_a_mostrar(dkpa, unidad)
    texto = f"{valor:.{DECIMALES_DIFERENCIA.get(mostrada, 1)}f}"
    return f"{texto} {mostrada}" if con_simbolo else texto


def simbolo_temp(unidad: str) -> str:
    return SIMBOLOS[unidad]


def simbolo_pres(unidad: str) -> str:
    return "psig" if unidad == "psi" else SIMBOLOS[unidad]


# ── unidad interna de un parámetro (por su "unit" y su nombre) ─────────────

# C1c (tanda 6): cada hoja de presión o temperatura de los JSON (ciclos de
# fábrica, defecto y usuario; global_params.json) declara su clase explícita:
#   "absoluto"       valor absoluto (°C; kPa abs): se convierte con desplazamiento;
#   "diferencia"     banda, margen, sumando o tasa: se escala sin desplazamiento;
#   "sin_conversion" se muestra en su unidad original (lo usaba
#                    rango_calentamiento, separado en R1-P3 de la tanda 7).
# El nombre del parámetro NO decide la clase. Los prefijos de abajo quedan solo
# como migración para un archivo viejo sin "clase", con una advertencia en el log.
CLASES = ("absoluto", "diferencia", "sin_conversion")

# Migración (U1-3 de la tanda 5): clasificación por prefijo del nombre.
_PREFIJOS_DIFERENCIA = ("rango_", "brecha_", "presion_add", "temperatura_add", "delta_",
                        "histeresis", "margen", "diferencia", "banda", "tolerancia",
                        "rango")
_UNIDADES_TEMP = ("°C", "C")
_UNIDADES_PRES = ("kPa",)
_TASAS_TEMP = ("°C/min",)
_TASAS_PRES = ("kPa/min", "kPa/s")
_avisados: set = set()


def _unidad_limpia(unidad_json: str) -> str:
    return (unidad_json or "").replace("�", "°").strip()


def requiere_clase(unidad_json: str) -> bool:
    """True si la hoja tiene unidad de temperatura o presión (debe llevar "clase")."""
    return _unidad_limpia(unidad_json) in (_UNIDADES_TEMP + _UNIDADES_PRES
                                           + _TASAS_TEMP + _TASAS_PRES)


def clase_por_prefijo(unidad_json: str, nombre: str = "") -> str | None:
    """Migración: la clase que deducía U1 por el nombre. None si no aplica."""
    if not requiere_clase(unidad_json):
        return None
    base = (nombre or "").split(".")[-1].lower()
    if base in SIN_CONVERSION:
        return "sin_conversion"
    u = _unidad_limpia(unidad_json)
    if u in _TASAS_TEMP + _TASAS_PRES or base.startswith(_PREFIJOS_DIFERENCIA):
        return "diferencia"
    return "absoluto"


def clase_de_unidad(unidad_json: str, nombre: str = "", clase: str | None = None) -> str | None:
    """'temp', 'dtemp', 'pres', 'dpres' o None (sin conversión), según la
    "clase" explícita de la hoja. Sin clase (archivo viejo) se usa la
    migración por prefijo y se registra una advertencia. Una clase desconocida
    no se convierte (se muestra en la unidad original: lo más seguro)."""
    u = _unidad_limpia(unidad_json)
    if not requiere_clase(u):
        return None
    if clase in (None, ""):
        clase = clase_por_prefijo(u, nombre)
        clave = (nombre or "", u)
        if clave not in _avisados:
            _avisados.add(clave)
            logger.warning("Parámetro %r (%s) sin \"clase\": se deduce %r por el "
                           "nombre (migración U1)", nombre, u, clase)
    if clase == "sin_conversion" or clase not in CLASES:
        if clase not in CLASES and (nombre or "", u, clase) not in _avisados:
            _avisados.add((nombre or "", u, clase))
            logger.warning("Parámetro %r: clase %r desconocida; se muestra sin conversión",
                           nombre, clase)
        return None
    temperatura = u in _UNIDADES_TEMP + _TASAS_TEMP
    tasa = u in _TASAS_TEMP + _TASAS_PRES
    if clase == "diferencia" or tasa:
        return "dtemp" if temperatura else "dpres"
    return "temp" if temperatura else "pres"


# ── configuración persistente (data/unidades.json) ──────────────────────────

class ConfigUnidades:
    """data/unidades.json = {"temperatura": "C"|"F", "presion": "kPa"|...}.
    Ausente, ilegible o inválido → °C y kPa (el comportamiento de siempre)."""

    def __init__(self, ruta):
        import threading
        from pathlib import Path
        self._ruta = Path(ruta)
        self._lock = threading.Lock()
        # R1 (I4 SAF-02/TMG-02): /status lo consulta en cada sondeo; solo se
        # relee el archivo si cambió su firma (mtime, tamaño)
        self._cache: tuple | None = None   # (firma, dict)

    def _firma(self):
        try:
            st = self._ruta.stat()
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def leer(self) -> dict:
        firma = self._firma()
        cache = self._cache
        if cache is not None and firma is not None and cache[0] == firma:
            return dict(cache[1])
        with self._lock:   # revisión R1: un guardar() concurrente no deja firma vieja
            firma = self._firma()      # antes de leer: un cambio posterior se detecta
            valor = self._leer_disco()
            self._cache = (firma, valor) if firma is not None else None
        return dict(valor)

    def _leer_disco(self) -> dict:
        import json
        try:
            datos = json.loads(self._ruta.read_text(encoding="utf-8"))
            t, p = datos.get("temperatura"), datos.get("presion")
            validar(t, p)
            return {"temperatura": t, "presion": p}
        except FileNotFoundError:
            return dict(POR_DEFECTO)
        except Exception:
            return dict(POR_DEFECTO)

    def guardar(self, temperatura: str, presion: str) -> dict:
        import json
        from autoclave.utils.archivos import escribir_texto_atomico
        validar(temperatura, presion)
        with self._lock:
            escribir_texto_atomico(self._ruta, json.dumps(
                {"temperatura": temperatura, "presion": presion}))
            self._cache = None
        return {"temperatura": temperatura, "presion": presion}

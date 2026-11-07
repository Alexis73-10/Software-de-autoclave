"""Sub-etapa de enfriamiento con contrapresión de líquidos (modos 4 y 5),
tanda 32 (LIQ-01 y LIQ-02).

Componente puro: no lee sensores ni escribe salidas; recibe las lecturas en
`tick()` y devuelve qué salidas deben quedar encendidas (`ResultadoTick`).
El reloj es inyectable (`ahora`, por defecto `time.monotonic`) para las
pruebas; nunca se usa el reloj de pared.

LIQ-01 (orden de arranque):
- `aire_comprimido_camara`: encendido mientras la presión de cámara (vigente)
  esté bajo el objetivo de reposición, reafirmado cada 3 s
  (`PERIODO_AIRE_COMPRIMIDO_S`); con la trama AI vencida o sin lectura,
  apagado (S9 / R2-A1 de la tanda 9). Revisión de la tanda 32 (M1): el
  objetivo de reposición es max(`presion_camara_enfriamiento`, P_min +
  `HISTERESIS_REPOSICION_AIRE_KPA`), con P_min de LIQ-02 (sin P_min
  calculable, solo `presion_camara_enfriamiento`), acotado por
  `presion_max_reposicion` (quien integra pasa el alivio de cámara menos
  10 kPa; sin ese dato, `presion_camara_enfriamiento` + 30). Así el aire no
  se detiene bajo el mínimo de contrapresión (falso CIC-24) cuando el
  Principal está sobre la temperatura de esterilización.
- Modo 5: `descompresion_lenta` abierta desde el primer tick.
- `descompresion_chaqueta` abierta fija desde el primer tick.
- Condiciones enclavadas: (a) presión de cámara >= presión de enfriamiento;
  (b) presión de chaqueta <= atmosférica + `presion_despresurizacion_chaqueta`.
  Solo con lectura vigente (falla cerrada); una vez cumplidas no se pierden.
- `agua_chaqueta` abre con (a) y (b) y queda abierta hasta el fin.
- Topes: (b) sin cumplir en `timeout_despresurizacion_chaqueta` min →
  `ENFR_TIMEOUT_DESPRESURIZACION_CHAQUETA`; (a) sin cumplir en
  `timeout_presurizacion_enfriamiento` min → `ENFR_TIMEOUT_PRESURIZACION`
  (DECISIÓN SIN CONFIRMAR). Los topes cuentan desde el primer tick.
  Sin `solo_aviso` el tope es un FALLO (todas las salidas apagadas). Con
  `solo_aviso=True` (protocolo de fallo; revisión de la tanda 32, hallazgo
  1) el tope NO es un fallo: queda enclavado en `tope` y la contrapresión se
  mantiene (aire según la regla de reposición, descompresión de chaqueta
  abierta), con el agua de chaqueta y la lenta cerradas desde ese tick;
  quien integra decide la salida (carga enfriada o sellado).
- (b) exige además la presión atmosférica de referencia: `None` (no
  configurada) = (b) no se cumple (falla cerrada).
- El vapor de chaqueta no se maneja aquí (queda apagado por quien integra).

LIQ-02 (vigilancia de contrapresión):
- P_min = Psat(T_Principal) + MARGEN_CONTRAPRESION_LIQUIDO, en cada tick.
  Se arma la primera vez que se cumple (a).
- Bajo el mínimo (o sin lectura del Principal o de la cámara, trama AI
  vencida, o Psat fuera de rango): 10 s seguidos → aviso no bloqueante (se
  despeja solo al recuperar); 60 s seguidos → `ENFR_CONTRAPRESION_BAJA`
  (DECISIÓN SIN CONFIRMAR hasta el banco). Volver sobre el mínimo reinicia
  el conteo. Con `solo_aviso=True` (protocolo de fallo) nunca hay fallo de
  contrapresión; en su lugar (segunda revisión, M-B) la lenta del modo 5 se
  cierra mientras el aviso esté activo y reabre al despejarse.
- M-A (segunda revisión): el objetivo de reposición nunca supera
  `presion_max_reposicion`, ni siquiera si `presion_camara_enfriamiento` es
  mayor (programa que la regla del catálogo rechaza).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Mapping

from autoclave.core.managers.catalogo_parametros import MARGEN_CONTRAPRESION_LIQUIDO
from autoclave.core.runtime.steam import p_saturacion_kpa

# Mismo periodo de reafirmación del aire comprimido que DESCOMPRESION y el
# protocolo de fallo (modos 4/5)
PERIODO_AIRE_COMPRIMIDO_S = 3.0

# LIQ-02 (DECISIÓN SIN CONFIRMAR hasta el banco)
TIEMPO_AVISO_CONTRAPRESION_S = 10.0
TIEMPO_FALLO_CONTRAPRESION_S = 60.0

# Revisión de la tanda 32 (M1): el aire repone como mínimo hasta P_min + esta
# histéresis (DECISIÓN SIN CONFIRMAR hasta el banco)
HISTERESIS_REPOSICION_AIRE_KPA = 2.0
# Sin `presion_max_reposicion`: tope de la reposición sobre el objetivo
MARGEN_REPOSICION_SIN_LIMITE_KPA = 30.0

# Códigos propios (el integrador los conecta al catálogo de alarmas)
ENFR_TIMEOUT_DESPRESURIZACION_CHAQUETA = "ENFR_TIMEOUT_DESPRESURIZACION_CHAQUETA"
ENFR_TIMEOUT_PRESURIZACION = "ENFR_TIMEOUT_PRESURIZACION"
ENFR_CONTRAPRESION_BAJA = "ENFR_CONTRAPRESION_BAJA"            # fallo
ENFR_AVISO_CONTRAPRESION = "ENFR_AVISO_CONTRAPRESION"          # aviso no bloqueante

PARAMETROS = (
    "presion_camara_enfriamiento",
    "presion_despresurizacion_chaqueta",
    "timeout_despresurizacion_chaqueta",
    "timeout_presurizacion_enfriamiento",
)


@dataclass(frozen=True)
class ResultadoTick:
    aire_comprimido_on: bool
    aire_comprimido_pulso: bool       # True en el tick en que se (re)ordena el ON
    descompresion_lenta_on: bool
    descompresion_chaqueta_on: bool
    agua_chaqueta_on: bool
    aviso_contrapresion: bool
    fallo: str | None
    cond_a: bool
    cond_b: bool
    armada: bool
    presion_minima: float | None      # P_min del tick (None sin dato o sin armar)
    segundos_bajo_minimo: float       # 0.0 si no está bajo el mínimo
    tope: str | None = None           # solo_aviso: tope de LIQ-01 alcanzado (enclavado)


def _numero(valor) -> float | None:
    """Número finito o None (bool no cuenta)."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    v = float(valor)
    return v if math.isfinite(v) else None


def _presion(valor) -> float | None:
    """Presión absoluta válida (finita y > 0) o None."""
    v = _numero(valor)
    return v if v is not None and v > 0 else None


class EnfriamientoContrapresion:
    """Una instancia por sub-etapa de enfriamiento (no se reutiliza)."""

    def __init__(self, params: Mapping, modo_5: bool, solo_aviso: bool = False,
                 ahora: Callable[[], float] = time.monotonic,
                 presion_max_reposicion: float | None = None):
        valores = {}
        for nombre in PARAMETROS:
            v = _numero(params.get(nombre)) if params is not None else None
            if v is None:
                raise ValueError(f"parámetro no válido: {nombre}={params and params.get(nombre)!r}")
            valores[nombre] = v
        if valores["presion_camara_enfriamiento"] <= 0:
            raise ValueError("presion_camara_enfriamiento debe ser > 0")
        if valores["presion_despresurizacion_chaqueta"] < 0:
            raise ValueError("presion_despresurizacion_chaqueta debe ser >= 0")
        for nombre in ("timeout_despresurizacion_chaqueta", "timeout_presurizacion_enfriamiento"):
            if valores[nombre] <= 0:
                raise ValueError(f"{nombre} debe ser > 0")

        self._presion_obj = valores["presion_camara_enfriamiento"]
        self._margen_chaqueta = valores["presion_despresurizacion_chaqueta"]
        self._tope_b_s = valores["timeout_despresurizacion_chaqueta"] * 60.0
        self._tope_a_s = valores["timeout_presurizacion_enfriamiento"] * 60.0
        self._modo_5 = bool(modo_5)
        self._solo_aviso = bool(solo_aviso)
        self._ahora = ahora
        # M1: tope de la reposición de aire. M-A (segunda revisión): el tope
        # rige también sobre el propio objetivo: con presion_camara_enfriamiento
        # mayor que el tope (alivio − 10), el aire nunca repone sobre el tope
        # (la regla del catálogo ya rechaza ese programa al guardar y al cargar)
        tope_rep = _presion(presion_max_reposicion)
        if tope_rep is None:
            tope_rep = self._presion_obj + MARGEN_REPOSICION_SIN_LIMITE_KPA
        self._presion_max_reposicion = tope_rep

        self._t_inicio: float | None = None
        self._t_aire: float | None = None
        self._cond_a = False
        self._cond_b = False
        self._t_bajo_desde: float | None = None
        self._fallo: str | None = None
        self._tope: str | None = None

    # -- propiedades de solo lectura ------------------------------------
    @property
    def cond_a(self) -> bool:
        return self._cond_a

    @property
    def cond_b(self) -> bool:
        return self._cond_b

    @property
    def armada(self) -> bool:
        return self._cond_a

    @property
    def fallo(self) -> str | None:
        return self._fallo

    @property
    def tope(self) -> str | None:
        return self._tope

    # -------------------------------------------------------------------
    def tick(self, pres_camara, pres_chaqueta, temp_principal,
             presion_atmosferica, datos_vigentes: bool) -> ResultadoTick:
        now = self._ahora()
        if self._t_inicio is None:
            self._t_inicio = now

        if self._fallo is not None:
            return self._resultado_fallo()

        vigente = datos_vigentes is True
        p_cam = _presion(pres_camara) if vigente else None
        p_chq = _presion(pres_chaqueta) if vigente else None
        p_atm = _presion(presion_atmosferica)

        # --- aire comprimido (M1: objetivo de reposición) ---
        pulso = False
        if p_cam is not None and p_cam < self._objetivo_reposicion(temp_principal):
            aire_on = True
            if self._t_aire is None or now >= self._t_aire:
                pulso = True
                self._t_aire = now + PERIODO_AIRE_COMPRIMIDO_S
        else:
            aire_on = False
            self._t_aire = None

        # --- condiciones enclavadas ---
        if not self._cond_a and p_cam is not None and p_cam >= self._presion_obj:
            self._cond_a = True
        if (not self._cond_b and p_chq is not None and p_atm is not None
                and p_chq <= p_atm + self._margen_chaqueta):
            self._cond_b = True

        # --- topes de LIQ-01 ---
        transcurrido = now - self._t_inicio
        codigo_tope = None
        if not self._cond_b and transcurrido >= self._tope_b_s:
            codigo_tope = ENFR_TIMEOUT_DESPRESURIZACION_CHAQUETA
        elif not self._cond_a and transcurrido >= self._tope_a_s:
            codigo_tope = ENFR_TIMEOUT_PRESURIZACION
        if codigo_tope is not None:
            if not self._solo_aviso:
                self._fallo = codigo_tope
                return self._resultado_fallo()
            if self._tope is None:
                # solo_aviso (hallazgo 1): sin fallo; se enclava el primero
                self._tope = codigo_tope

        # --- LIQ-02 ---
        p_min = None
        aviso = False
        bajo_s = 0.0
        if self._cond_a:
            p_min = self._presion_minima(temp_principal)
            bajo = p_min is None or p_cam is None or p_cam < p_min
            if bajo:
                if self._t_bajo_desde is None:
                    self._t_bajo_desde = now
                bajo_s = now - self._t_bajo_desde
                aviso = bajo_s >= TIEMPO_AVISO_CONTRAPRESION_S
                if not self._solo_aviso and bajo_s >= TIEMPO_FALLO_CONTRAPRESION_S:
                    self._fallo = ENFR_CONTRAPRESION_BAJA
                    return self._resultado_fallo(p_min, bajo_s)
            else:
                self._t_bajo_desde = None

        # Tras un tope (solo_aviso) la contrapresión se mantiene, pero ni la
        # lenta (carga posiblemente caliente) ni el agua de chaqueta
        en_tope = self._tope is not None
        # M-B (segunda revisión): en el protocolo de fallo (sin CIC-24) la
        # lenta se cierra mientras dure el aviso de contrapresión (10 s bajo
        # P_min o sin dato) y reabre al despejarse; el aire sigue reponiendo
        lenta_cerrada_por_aviso = self._solo_aviso and aviso
        return ResultadoTick(
            aire_comprimido_on=aire_on,
            aire_comprimido_pulso=pulso,
            descompresion_lenta_on=self._modo_5 and not en_tope and not lenta_cerrada_por_aviso,
            descompresion_chaqueta_on=True,
            agua_chaqueta_on=self._cond_a and self._cond_b and not en_tope,
            aviso_contrapresion=aviso,
            fallo=None,
            cond_a=self._cond_a,
            cond_b=self._cond_b,
            armada=self._cond_a,
            presion_minima=p_min,
            segundos_bajo_minimo=bajo_s,
            tope=self._tope,
        )

    # -------------------------------------------------------------------
    def _objetivo_reposicion(self, temp_principal) -> float:
        """M1: max(objetivo, P_min + histéresis); sin P_min calculable, el
        objetivo. M-A: el resultado siempre se acota a
        `presion_max_reposicion` (con tope >= objetivo es lo mismo que antes)."""
        p_min = self._presion_minima(temp_principal)
        objetivo = (self._presion_obj if p_min is None
                    else max(self._presion_obj, p_min + HISTERESIS_REPOSICION_AIRE_KPA))
        return min(objetivo, self._presion_max_reposicion)

    @staticmethod
    def _presion_minima(temp_principal) -> float | None:
        """Psat(T) + margen; None sin lectura o fuera de rango (= bajo el
        mínimo, falla cerrada)."""
        t = _numero(temp_principal)
        if t is None:
            return None
        try:
            return p_saturacion_kpa(t) + MARGEN_CONTRAPRESION_LIQUIDO
        except ValueError:
            return None

    def _resultado_fallo(self, p_min: float | None = None, bajo_s: float = 0.0) -> ResultadoTick:
        """En FALLO todas las salidas de la sub-etapa quedan apagadas."""
        return ResultadoTick(
            aire_comprimido_on=False,
            aire_comprimido_pulso=False,
            descompresion_lenta_on=False,
            descompresion_chaqueta_on=False,
            agua_chaqueta_on=False,
            aviso_contrapresion=False,
            fallo=self._fallo,
            cond_a=self._cond_a,
            cond_b=self._cond_b,
            armada=self._cond_a,
            presion_minima=p_min,
            segundos_bajo_minimo=bajo_s,
        )

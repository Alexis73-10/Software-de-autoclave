"""A14 (tanda 28): planta simulada de cámara y chaqueta y arnés que corre
CALENTAMIENTO → ESTERILIZACION con las fases reales, sin CicloState, backend
ni puerto.

Modelo (valores PROVISIONALES, no la dinámica real del equipo; sirven para
comparar el control antes y después de A14 con la misma planta):
  - cámara: presión parcial de vapor P_v y de aire P_aire; la carga (T) sigue a
    Tsat(P_v) y la sonda a la carga con retraso de primer orden (TAU_SONDA);
    pérdidas hacia el ambiente y escape lento enclavado (como en el
    programa de fábrica);
  - modo cámara: vapor_camara inyecta desde el suministro (P_SUMINISTRO);
  - modo chaqueta: vapor_chaqueta llena la chaqueta desde el suministro y
    vapor_camara (abierta) pasa vapor de la chaqueta a la cámara con un caudal
    proporcional a la diferencia de presión; la chaqueta pierde por sus
    paredes.
El arnés hace lo que CicloState hace alrededor de las fases y que ellas leen:
el corte D-CHQ (estado.inhibir_vapor_chaqueta con pres_chaqueta >=
presion_max_chaqueta_control o sin lectura en modo chaqueta) antes de update()
y el OFF forzado después; nada más."""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock

from autoclave.core.managers.config_manager import ConfigManager
from autoclave.core.managers.cycle_manager import Cycle
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.devices.io.set_io import SetOutput
from autoclave.installation.profile import MODO_CHAQUETA
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase

DT = 0.5
T_AMB = 25.0
RAIZ = Path(__file__).resolve().parents[2]
PROGRAMA_134 = RAIZ / "src" / "autoclave" / "cycles" / "factory" / "instrumental_134.json"


def psat(t: float) -> float:
    """kPa; por debajo de 99 °C empalma Antoine (la tabla del control no se
    usa fuera del rango de trabajo en la planta)."""
    if t >= 99:
        return p_saturacion_kpa(t)
    a, b, c = 8.07131, 1730.63, 233.426
    antoine = lambda x: 10 ** (a - b / (c + x)) * 0.133322
    return antoine(t) * p_saturacion_kpa(99) / antoine(99)


def tsat(p: float) -> float:
    bajo, alto = 0.0, 200.0
    for _ in range(50):
        medio = (bajo + alto) / 2
        if psat(medio) < p:
            bajo = medio
        else:
            alto = medio
    return (bajo + alto) / 2


class ModuloEsDoble:
    """Salidas digitales 1-indexadas (canal = índice de map_do + 1)."""

    def __init__(self, estado):
        self.estado = estado
        self.do = {}
        self._nombre = {i + 1: n for n, i in EstadoAutoclave.map_do.items()}

    def set_output(self, canal, valor):
        self.do[canal] = bool(valor)
        nombre = self._nombre.get(canal)
        if nombre:
            self.estado.salidas_do[nombre] = 1 if valor else 0

    def all_off(self):
        for canal in list(self.do):
            self.set_output(canal, False)
        return True

    def on(self, nombre):
        return self.do.get(EstadoAutoclave.map_do[nombre] + 1, False)


class PlantaVapor:
    P_SUMINISTRO = 350.0   # kPa abs (presion_suministro_vapor de fábrica)
    INYECCION = 3.0        # kPa/s, vapor_camara desde el suministro (modo cámara)
    LLENADO_CHAQUETA = 6.0  # kPa/s, vapor_chaqueta desde el suministro
    PASO_CAMARA = 0.06     # 1/s, caudal chaqueta → cámara por diferencia de presión
    RELACION_VOLUMEN = 1.5  # la chaqueta (menor) baja más de lo que sube la cámara
    PERDIDA_CHAQUETA = 0.15  # kPa/s, condensación en las paredes de la chaqueta
    CONDENSACION = 0.1     # 1/s, intercambio vapor-carga
    CALOR = 0.15           # 1/s, T de la carga hacia Tsat(P_v)
    PERDIDA_TERMICA = 0.0003  # 1/s hacia T_AMB
    TAU_SONDA = 15.0       # s

    def __init__(self, modulo_es, p_atm: float, chaqueta: bool,
                 t_inicial: float = 60.0, p_chaqueta_inicial: float = 328.0):
        self.modulo_es = modulo_es
        self.p_atm = p_atm
        self.chaqueta = chaqueta
        self.t = t_inicial
        self.t_sonda = t_inicial
        self.p_v = psat(t_inicial)
        self.p_aire = 0.1          # después del prevacío
        self.p_chaqueta = p_chaqueta_inicial if chaqueta else 300.0

    @property
    def p(self):
        return self.p_v + self.p_aire

    def _ventear(self, fraccion):
        fraccion = min(max(fraccion, 0.0), 0.9)
        self.p_aire *= (1 - fraccion)
        self.p_v *= (1 - fraccion)

    def paso(self):
        on = self.modulo_es.on
        if self.chaqueta:
            if on("vapor_chaqueta") and self.p_chaqueta < self.P_SUMINISTRO:
                self.p_chaqueta += (self.LLENADO_CHAQUETA * DT
                                    * min(1.0, (self.P_SUMINISTRO - self.p_chaqueta) / 30))
            if on("vapor_camara") and self.p_chaqueta > self.p:
                q = self.PASO_CAMARA * (self.p_chaqueta - self.p) * DT
                self.p_v += q
                self.p_chaqueta -= q * self.RELACION_VOLUMEN
            if self.p_chaqueta > self.p_atm:
                self.p_chaqueta = max(self.p_atm, self.p_chaqueta - self.PERDIDA_CHAQUETA * DT)
        elif on("vapor_camara") and self.p < self.P_SUMINISTRO:
            self.p_v += self.INYECCION * DT * min(1.0, (self.P_SUMINISTRO - self.p) / 50)
        if self.p > self.p_atm:
            sobre = (self.p - self.p_atm) / self.p
            if on("descompresion_rapida"):
                self._ventear(0.6 * DT * sobre)
            if on("descompresion_lenta"):
                self._ventear(0.001 * DT * sobre)
        self.p_v += (psat(self.t) - self.p_v) * self.CONDENSACION * DT
        self.p_v = max(self.p_v, 0.5)
        self.t += (tsat(self.p_v) - self.t) * self.CALOR * DT
        self.t += (T_AMB - self.t) * self.PERDIDA_TERMICA * DT
        self.t_sonda += (self.t - self.t_sonda) * DT / self.TAU_SONDA

    def publicar(self, estado):
        t = self.t_sonda
        estado.sensores_temp.update({"temp_camara": t, "temp_2_camara": t,
                                     "temp_ref": t - 0.2, "temp_drenaje": 40.0})
        estado.sensores_pres.update({"pres_camara": self.p, "pres_chaqueta": self.p_chaqueta,
                                     "pres_empaque_1": 350.0, "pres_empaque_2": 350.0})


def programa_134(**valores) -> Cycle:
    """Programa de fábrica 134 °C (sin migraciones de carga) con los valores
    dados como `seccion__parametro=valor`."""
    datos = json.loads(PROGRAMA_134.read_text(encoding="utf-8"))
    parametros = copy.deepcopy(datos["parameters"])
    for ruta, valor in valores.items():
        seccion, clave = ruta.split("__")
        parametros[seccion][clave]["value"] = valor
    return Cycle(datos["cycle_id"], datos.get("display_name", ""), parametros,
                 datos.get("cycle_number"))


@dataclass
class Resultado:
    modo: str
    resultado: str = "EN_CURSO"
    motivo: str | None = None
    alarma: tuple | None = None
    serie: list = field(default_factory=list)   # (s, fase, T, P, P_chq, vapor, tramo)
    aislamientos: int = 0
    inicio_ester_s: float | None = None
    t_est: float = 134.0
    p_control_max: float = 0.0

    def ester(self):
        return [m for m in self.serie if m[1] == "ESTERILIZACION"]

    @property
    def t_max_ester(self):
        return max((m[2] for m in self.ester()), default=None)

    @property
    def t_min_ester(self):
        return min((m[2] for m in self.ester()), default=None)

    @property
    def p_max_ester(self):
        return max((m[3] for m in self.ester()), default=None)

    @property
    def sobreimpulso_k(self):
        t = self.t_max_ester
        return None if t is None else t - self.t_est

    def fraccion_en_banda(self, ancho_k: float = 1.0) -> float | None:
        """Fracción del tiempo de ESTERILIZACION con T en [T_est, T_est + ancho]."""
        datos = self.ester()
        if not datos:
            return None
        dentro = sum(1 for m in datos if self.t_est <= m[2] <= self.t_est + ancho_k)
        return dentro / len(datos)


def simular(modo: str, programa: Cycle, limite_s: float = 3600.0,
            monkeypatch=None) -> Resultado:
    """Corre CALENTAMIENTO y ESTERILIZACION sobre la planta. `modo`:
    "camara" o "chaqueta". Con `monkeypatch` (pytest) parchea time.monotonic;
    sin él lo parchea y lo restaura aquí (script de diagnóstico)."""
    reloj = [1000.0]
    original = time.monotonic
    if monkeypatch is not None:
        monkeypatch.setattr(time, "monotonic", lambda: reloj[0])
    else:
        time.monotonic = lambda: reloj[0]
    try:
        return _simular(modo, programa, limite_s, reloj)
    finally:
        if monkeypatch is None:
            time.monotonic = original


def _simular(modo, programa, limite_s, reloj) -> Resultado:
    chaqueta = modo == "chaqueta"
    estado = EstadoAutoclave()
    estado.modo_vapor = MODO_CHAQUETA if chaqueta else "camara"
    estado.avisos_ciclo = []
    estado.f0_acumulado = 0.0
    config = ConfigManager()
    config.load_config()
    p_atm = float(config.get("presion_admosferica") or 101.3)
    corte_chq = float(config.get("presion_max_chaqueta_control") or 375)
    modulo_es = ModuloEsDoble(estado)
    planta = PlantaVapor(modulo_es, p_atm, chaqueta)
    set_do = SetOutput(modulo_es, estado, profile=None)
    alarmas = MagicMock()
    fases = [CalentamientoFase(estado, set_do, programa, config, alarmas, None),
             EsterilizacionFase(estado, set_do, programa, config, alarmas, None)]
    for f in fases:
        f.reset()
    t_est = programa.get_param("esterilizacion", "temperatura_esterilizacion")
    res = Resultado(modo=modo, t_est=t_est,
                    p_control_max=p_saturacion_kpa(t_est)
                    + programa.get_param("esterilizacion", "presion_add_esterilizacion"))
    idx = 0
    aislado_antes = False
    if chaqueta:
        set_do.vapor_camara_on()
    for n in range(int(limite_s / DT)):
        planta.publicar(estado)
        fase = fases[idx]
        estado.fase_ciclo = fase.name
        # D-CHQ como CicloState (_actualizar_corte_chaqueta), modo chaqueta
        pch = estado.sensores_pres.get("pres_chaqueta")
        corte = pch is None if chaqueta else False
        corte = corte or (pch is not None and pch >= corte_chq)
        estado.inhibir_vapor_chaqueta = corte
        r = fase.update()
        if corte:
            set_do.vapor_chaqueta_off()
        if not chaqueta:
            # modo cámara: la chaqueta la lleva CicloState; no afecta la planta
            set_do.vapor_chaqueta_off()
        ais = getattr(estado, "aislamiento_camara", None)
        aislado = bool(getattr(ais, "aislado", False))
        if aislado and not aislado_antes:
            res.aislamientos += 1
        aislado_antes = aislado
        actuador = "vapor_chaqueta" if chaqueta else "vapor_camara"
        tramo = ("ESTABLE" if getattr(fase, "_en_sostenimiento", False) else "RAMPA") \
            if idx == 0 else ("RECUPERACION" if getattr(fase, "_en_recuperacion", False)
                              else "PWM")
        res.serie.append((n * DT, fase.name, planta.t_sonda, planta.p, planta.p_chaqueta,
                          1 if modulo_es.on(actuador) else 0, tramo, 1 if aislado else 0))
        if r is FaseResult.FALLO:
            res.resultado = "FALLO"
            res.motivo = str(estado.motivo_fallo)
            res.alarma = getattr(fase, "alarma_fallo", None)
            break
        if r is FaseResult.COMPLETADO:
            if idx == 1:
                res.resultado = "COMPLETADO"
                break
            idx = 1
            res.inicio_ester_s = n * DT
        planta.paso()
        reloj[0] += DT
    return res

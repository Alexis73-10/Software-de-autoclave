"""T11 (tanda 2026-10-14): prueba de integración de un ciclo completo de cada
uno de los 4 programas de fábrica (1 Bowie & Dick, 2 Instrumental 134,
3 Instrumental 121, 4 Líquidos) contra una planta simulada.

El simulador del repositorio (autoclave.simulador) solo repite ciclos
grabados, así que aquí se usa un modelo físico simple de la cámara:
  - temperatura T del contenido, con vapor saturado: P_vapor = P_sat(T);
  - presión parcial de aire P_aire; P_cámara = P_vapor + P_aire;
  - vapor a la cámara calienta (fuente de ~139 °C); vacío extrae aire y vapor;
    los escapes ventean hacia la atmósfera; aire comprimido suma P_aire;
    pérdidas térmicas hacia 25 °C;
  - chaqueta: sube con su vapor y baja con su escape.
CicloState corre con SetOutput real sobre un módulo E/S simulado, con reloj
monotónico virtual (0,5 s por tick). Valores de la planta PROVISIONALES: la
prueba verifica la secuencia de fases y que el ciclo termine COMPLETADO sin
fallos, no la dinámica real del equipo."""

import json
import math
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.config_manager import ConfigManager
from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.devices.io.set_io import SetOutput
from autoclave.installation.equipment import EquipmentClass, get_capabilities
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState

DT = 0.5
P_ATM = 75.0      # se reemplaza por presion_admosferica de la configuración
T_AMB = 25.0
T_FUENTE = 139.0


def psat(t: float) -> float:
    """kPa. Por encima de 99 °C la misma fórmula que el control
    (core.runtime.steam); por debajo, Antoine, empalmada en 99 °C."""
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


class _ModuloEs:
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


class _Planta:
    """Vapor (presión parcial P_v), aire (P_aire) y temperatura del sensor T,
    que sigue a la saturación del vapor con retraso (por eso, mientras entra
    vapor, P supera a P_sat(T), como en el equipo real)."""

    P_FUENTE = 400.0      # kPa, generador
    INYECCION = 3.0       # kPa/s con la válvula de vapor abierta (~180 kPa/min)
    CONDENSACION = 0.1    # 1/s, intercambio vapor-carga
    CALOR = 0.15          # 1/s, T hacia T_sat(P_v)

    def __init__(self, modulo_es):
        self.t = T_AMB
        self.p_v = psat(T_AMB)
        self.p_aire = P_ATM - self.p_v
        self.p_chaqueta = P_ATM
        self.t_sonda = T_AMB
        self.modulo_es = modulo_es

    @property
    def p(self):
        return self.p_v + self.p_aire

    def _ventear(self, fraccion):
        fraccion = min(max(fraccion, 0.0), 0.9)
        self.p_aire *= (1 - fraccion)
        self.p_v *= (1 - fraccion)

    def paso(self):
        on = self.modulo_es.on
        if on("vapor_camara") and self.p < self.P_FUENTE:
            self.p_v += self.INYECCION * DT * min(1.0, (self.P_FUENTE - self.p) / 50)
        if on("vacio_camara") and on("bomba_vacio"):
            self._ventear(0.25 * DT)
        if self.p > P_ATM:
            sobre = (self.p - P_ATM) / self.p
            if on("descompresion_rapida"):
                self._ventear(0.6 * DT * sobre)
            if on("descompresion_lenta"):
                self._ventear(0.001 * DT * sobre)
                # el aire (más denso) sale primero por el escape de abajo,
                # desplazado por el vapor que entra (purga por gravedad)
                if on("vapor_camara"):
                    self.p_aire *= (1 - 0.02 * DT)
        elif on("aire_admosferico_camara") or on("descompresion_rapida"):
            self.p_aire += (P_ATM - self.p) * min(1.0, 0.8 * DT)
        if on("aire_comprimido_camara") and self.p < 320:
            self.p_aire += 15 * DT
        # intercambio vapor-carga: condensación (o evaporación) y calentamiento
        self.p_v += (psat(self.t) - self.p_v) * self.CONDENSACION * DT
        self.p_v = max(self.p_v, 0.5)
        self.t += (tsat(self.p_v) - self.t) * self.CALOR * DT
        self.t = max(self.t, 15.0)        # la carga no se enfría más por evaporación
        perdida = 0.0003 + (0.02 if on("agua_chaqueta") else 0.0)
        self.t += (T_AMB - self.t) * perdida * DT
        self.t_sonda += (self.t - self.t_sonda) * DT / self.TAU_SONDA
        # chaqueta
        if on("vapor_chaqueta"):
            self.p_chaqueta = min(400.0, self.p_chaqueta + 15 * DT)
        if on("descompresion_chaqueta") or on("agua_chaqueta"):
            self.p_chaqueta = max(P_ATM, self.p_chaqueta - 30 * DT)
        elif not on("vapor_chaqueta"):
            self.p_chaqueta = max(P_ATM, self.p_chaqueta - 0.5 * DT)

    # La sonda (PT100 con su vaina) sigue a la temperatura del vapor con un
    # retraso de primer orden: mientras el vapor sube, P > P_sat(T_sonda),
    # como en el equipo. Sin este retraso el corte por calidad de vapor del
    # calentamiento (P >= P_sat(T) + 11 kPa) no se cumpliría con vapor puro.
    TAU_SONDA = 15.0      # s

    def publicar(self, estado):
        t = self.t_sonda
        estado.sensores_temp.update({"temp_camara": t, "temp_2_camara": t,
                                     "temp_ref": t - 0.2, "temp_drenaje": 40.0})
        estado.sensores_pres.update({"pres_camara": self.p, "pres_chaqueta": self.p_chaqueta,
                                     "pres_empaque_1": 350.0, "pres_empaque_2": 350.0})


@pytest.fixture(scope="module")
def programas():
    """Programas de FÁBRICA (cycles/factory): los de usuario homónimos los
    reemplazan al cargar todo, así que se cargan aparte (SAF-07 de T11)."""
    cm = CycleManager()
    cm._load_from_folder("cycles/factory", source="factory")
    return {c.number: c for c in cm.cycles.values() if c.number is not None}


def test_numeracion_con_todos_los_programas():
    cm = CycleManager()
    cm.load_all_cycles()
    assert sorted(c.number for c in cm.cycles.values()) == [1, 2, 3, 4]


def _correr(programa, monkeypatch, limite_s=4 * 3600, sonda_cero_en=None):
    reloj = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: reloj[0])
    estado = EstadoAutoclave()
    for di in estado.sensores_di:
        estado.sensores_di[di] = 1
    estado.sensores_di["paro_emergencia"] = 1           # NC: 1 = sin paro
    modulo_es = _ModuloEs(estado)
    config = ConfigManager()
    config.load_config()
    global P_ATM
    P_ATM = float(config.get("presion_admosferica") or 101.3)
    planta = _Planta(modulo_es)
    alarmas = AlarmManager()
    profile = MagicMock(door_count=2, door_type=None, vapor_source="generator",
                        equipment_class=EquipmentClass.PISO_LAB,
                        supply_inputs={}, temperature_probes={})
    set_do = SetOutput(modulo_es, estado, profile=None)
    ciclo = CicloState(estado, set_do, programa, config, alarmas,
                       cap=get_capabilities(EquipmentClass.PISO_LAB))
    planta.publicar(estado)
    ciclo.reset()
    fases, resultado = [], None
    t_max_rapida_caliente = None
    usadas = set()
    simultaneo = False          # vapor y agua de chaqueta a la vez (TMG-01)
    t_fase = {}
    for _ in range(int(limite_s / DT)):
        planta.publicar(estado)
        if sonda_cero_en is not None and estado.fase_ciclo == sonda_cero_en:
            estado.sensores_temp["temp_camara"] = 0          # sensor sin señal
        if not fases or fases[-1] != estado.fase_ciclo:
            fases.append(estado.fase_ciclo)
        r = ciclo.run()
        usadas.update(k for k, v in estado.salidas_do.items() if v)
        simultaneo |= bool(estado.salidas_do.get("vapor_chaqueta")
                           and estado.salidas_do.get("agua_chaqueta"))
        t_fase[estado.fase_ciclo] = t_fase.get(estado.fase_ciclo, 0) + DT
        # temperatura REAL de la planta, no la de la sonda (SAF-07 de T11)
        if modulo_es.on("descompresion_rapida") and planta.t > 80.5:
            t_max_rapida_caliente = max(t_max_rapida_caliente or 0, planta.t)
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            resultado = estado.fase_ciclo
            break
        planta.paso()
        reloj[0] += DT
    return {"fases": fases, "resultado": resultado, "motivo": estado.motivo_fallo,
            "rapida_caliente": t_max_rapida_caliente, "t_final": planta.t_sonda,
            "salidas": usadas, "simultaneo": simultaneo, "t_fase": t_fase,
            "minutos": (reloj[0] - 1000.0) / 60}


def test_numeracion_de_los_programas(programas):
    assert {n: c.id for n, c in programas.items()} == {
        1: "bowe_dick", 2: "134_instrumental", 3: "instrumental_121", 4: "liquidos"}


@pytest.mark.parametrize("numero, fases_esperadas", [
    (1, ["PRECALENTAMIENTO", "PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION", "DESCOMPRESION", "SECADO"]),
    (2, ["PRECALENTAMIENTO", "PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION", "DESCOMPRESION", "SECADO"]),
    (3, ["PRECALENTAMIENTO", "PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION", "DESCOMPRESION", "SECADO"]),
    (4, ["PRECALENTAMIENTO", "PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION", "DESCOMPRESION", "SECADO"]),
])
def test_ciclo_completo_de_cada_programa(programas, monkeypatch, numero, fases_esperadas):
    r = _correr(programas[numero], monkeypatch)
    assert r["resultado"] == "COMPLETADO", (r["resultado"], r["motivo"], r["fases"][-3:])
    vistas = [f for f in r["fases"] if f in fases_esperadas]
    assert vistas == fases_esperadas, r["fases"]
    assert not r["simultaneo"], "vapor_chaqueta y agua_chaqueta a la vez"
    # cada fase termina dentro de su timeout (con margen)
    prog = programas[numero]
    assert r["t_fase"].get("CALENTAMIENTO", 0) < prog.get_param("calentamiento", "timeout_calentamiento") * 60 * 0.8


def test_liquidos_no_usa_la_rapida_con_la_carga_caliente(programas, monkeypatch):
    """Decisión 1.2: modo 4 enfría con contrapresión hasta 80 °C antes de la
    despresurización final con la rápida."""
    r = _correr(programas[4], monkeypatch)
    assert r["resultado"] == "COMPLETADO", r["motivo"]
    assert r["rapida_caliente"] is None or r["rapida_caliente"] <= 82.0   # retraso de la sonda
    assert "vacio_camara" not in r["salidas"]          # sin prevacío ni secado
    assert "aire_comprimido_camara" in r["salidas"]    # contrapresión del modo 4
    assert r["t_final"] <= 80.5                        # enfrió hasta 80 °C
    assert not r["simultaneo"]
    assert r["t_fase"]["DESCOMPRESION"] < programas[4].get_param(
        "descompresion", "modo_4", "timeout") * 60 * 0.8
    # fases saltadas: un solo tick
    assert r["t_fase"]["PRE_VACIO"] <= DT and r["t_fase"]["SECADO"] <= DT


def test_liquidos_con_la_sonda_en_cero_no_abre_la_rapida(programas, monkeypatch):
    """SAF-01 de T11: si el Principal cae a 0 (sin señal) durante la
    descompresión, nunca se abre la rápida con la carga caliente."""
    r = _correr(programas[4], monkeypatch, limite_s=3600, sonda_cero_en="DESCOMPRESION")
    assert r["rapida_caliente"] is None

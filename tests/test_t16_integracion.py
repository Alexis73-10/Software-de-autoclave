# tests/test_t16_integracion.py
#
# Integración de la tanda 16 (etapa I): pruebas mínimas de VCH §8, puntos 1 a
# 9, de punta a punta con CicloState, CALENTAMIENTO y ESTERILIZACION reales,
# el programa de fábrica Instrumental 134 °C, EstadoAutoclave real, el
# AlarmManager real y el ProtocoloFallo real. Las fases que no intervienen
# (PRECALENTAMIENTO, PRE_VACIO, DESCOMPRESION, SECADO) son dobles. Las salidas
# se registran en un SetOutput de prueba que guarda su último estado; el reloj
# monotónico es simulado (ticks de 0,5 s).

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.cycle_manager import Cycle
from autoclave.core.runtime import presion_sin_lectura
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.installation.profile import MODO_CAMARA, MODO_CHAQUETA
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.states import ciclo as modulo_ciclo
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState

pytestmark = pytest.mark.req("T16-VCH-8")

_PROGRAMA = (Path(__file__).resolve().parents[1] / "src" / "autoclave" / "cycles" / "factory"
             / "instrumental_134.json")
T_EST = 134.0
P_SAT = p_saturacion_kpa(T_EST)
TECHO_EST = P_SAT + 15.0           # P_control_max con presion_add_esterilizacion = 15
TICK = 0.5


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Salidas:
    """SetOutput de prueba: estado de cada salida y registro de órdenes."""

    def __init__(self):
        self.estado: dict[str, bool] = {}
        self.ordenes: list[tuple[str, bool]] = []

    def __getattr__(self, nombre):
        for sufijo, valor in (("_on", True), ("_off", False)):
            if nombre.endswith(sufijo):
                salida = nombre[: -len(sufijo)]

                def orden(*_a, _s=salida, _v=valor, **_k):
                    self.estado[_s] = _v
                    self.ordenes.append((_s, _v))
                    return True
                return orden
        raise AttributeError(nombre)

    def reset_all_outputs(self, *_a, **_k):
        for s in list(self.estado):
            self.estado[s] = False
        self.ordenes.append(("ALL_OFF", False))
        return True

    def apagar_por_paro(self, *_a, **_k):
        return self.reset_all_outputs()

    def set_output(self, *_a, **_k):
        return True

    def on(self, s):
        return self.estado.get(s, False)


class FaseDoble:
    def __init__(self, name, resultado=FaseResult.COMPLETADO):
        self.name = name
        self.resultado = resultado

    def reset(self):
        pass

    def update(self):
        return self.resultado


def _armar(monkeypatch, modo=MODO_CHAQUETA, pres_chaqueta=330.0):
    reloj = Reloj()
    monkeypatch.setattr(time, "monotonic", reloj)
    monkeypatch.setattr(modulo_ciclo, "modo_vapor", lambda _perfil: modo)
    datos = json.loads(_PROGRAMA.read_text(encoding="utf-8"))
    programa = Cycle(datos["cycle_id"], datos["display_name"], datos["parameters"])
    estado = EstadoAutoclave()
    estado.sensores_temp.update({"temp_camara": 100.0})
    estado.sensores_pres.update({"pres_camara": 120.0, "pres_chaqueta": pres_chaqueta,
                                 "pres_empaque_1": 300.0, "pres_empaque_2": 300.0})
    estado.sensores_di.update({"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                               "vapor_suministro": 1})
    config = MagicMock()
    config.get.return_value = None
    salidas = Salidas()
    am = AlarmManager()
    ciclo = CicloState(estado, salidas, programa, config, am)
    ciclo.reset()
    ciclo._pres_vigilados = [presion_sin_lectura.CAMARA, presion_sin_lectura.CHAQUETA]
    f = ciclo._fases
    f[0] = FaseDoble("PRECALENTAMIENTO")
    f[1] = FaseDoble("PRE_VACIO")
    f[4] = FaseDoble("DESCOMPRESION", FaseResult.EN_CURSO)
    f[5] = FaseDoble("SECADO", FaseResult.EN_CURSO)
    return ciclo, estado, salidas, am, reloj


def _tick(ciclo, reloj, estado=None, temp=None, pres=None, **otras):
    if estado is not None:
        if temp is not None:
            estado.sensores_temp["temp_camara"] = temp
        if pres is not None:
            estado.sensores_pres["pres_camara"] = pres
        estado.sensores_pres.update(otras)
    r = ciclo.run()
    reloj.t += TICK
    return r


def _hasta_fase(ciclo, reloj, nombre, maximo=50):
    for _ in range(maximo):
        if ciclo._fases[min(ciclo._fase_idx, 5)].name == nombre:
            return
        _tick(ciclo, reloj)
    raise AssertionError(f"no se llegó a {nombre}")


def _calentar(ciclo, estado, salidas, reloj, registro=None, max_ticks=400):
    """Sube a 134 °C en vapor saturado y sostiene hasta pasar a ESTERILIZACION."""
    temp = 100.0
    for _ in range(max_ticks):
        if ciclo._fases[ciclo._fase_idx].name == "ESTERILIZACION":
            return
        temp = min(134.3, temp + 0.5)
        _tick(ciclo, reloj, estado, temp=temp, pres=p_saturacion_kpa(temp))
        if registro is not None:
            registro.append(salidas.on("vapor_camara"))
    raise AssertionError("CALENTAMIENTO no terminó")


def _esterilizar(ciclo, estado, salidas, reloj, registro=None, max_ticks=2000):
    for _ in range(max_ticks):
        if ciclo._fase_idx >= 4:
            return
        _tick(ciclo, reloj, estado, temp=134.3, pres=p_saturacion_kpa(134.3))
        if registro is not None and ciclo._fase_idx == 3:
            registro.append(salidas.on("vapor_camara"))
    raise AssertionError("ESTERILIZACION no terminó")


# ── 1 y 8. Modo chaqueta: vapor_camara abierta de CALENTAMIENTO al fin ───────

def test_1_8_modo_chaqueta_camara_abierta_y_control_por_chaqueta(monkeypatch):
    ciclo, estado, salidas, _am, reloj = _armar(monkeypatch)
    _hasta_fase(ciclo, reloj, "CALENTAMIENTO")
    registro = []
    _calentar(ciclo, estado, salidas, reloj, registro)
    # 8: la transición CALENTAMIENTO -> ESTERILIZACION no cierra vapor_camara
    assert registro and all(registro[1:]), "vapor_camara se cerró durante CALENTAMIENTO"
    assert salidas.on("vapor_camara")
    salidas.ordenes.clear()
    registro_est = []
    _esterilizar(ciclo, estado, salidas, reloj, registro_est)
    assert registro_est and all(registro_est)
    # el control conmutó solo vapor_chaqueta (vapor_camara nunca a OFF hasta el fin)
    camara = [v for s, v in salidas.ordenes if s == "vapor_camara"]
    chaqueta = [v for s, v in salidas.ordenes if s == "vapor_chaqueta"]
    assert False in chaqueta and True in chaqueta
    assert camara[-1] is False and camara[:-1] and all(camara[:-1])
    # 6 (D6): al COMPLETAR ESTERILIZACION se cierran las dos
    assert not salidas.on("vapor_camara") and not salidas.on("vapor_chaqueta")


# ── 2. Modo cámara: el control sigue sobre vapor_camara ───────────────────

def test_2_modo_camara_controla_vapor_camara(monkeypatch):
    ciclo, estado, salidas, _am, reloj = _armar(monkeypatch, modo=MODO_CAMARA, pres_chaqueta=300.0)
    _hasta_fase(ciclo, reloj, "CALENTAMIENTO")
    assert getattr(ciclo._fases[2], "controla_vapor_chaqueta", False) is False
    salidas.ordenes.clear()
    _calentar(ciclo, estado, salidas, reloj)
    camara = [v for s, v in salidas.ordenes if s == "vapor_camara"]
    assert True in camara and False in camara          # el duty de CALENTAMIENTO va a la cámara
    salidas.ordenes.clear()
    _esterilizar(ciclo, estado, salidas, reloj)
    camara = [v for s, v in salidas.ordenes if s == "vapor_camara"]
    chaqueta = [v for s, v in salidas.ordenes if s == "vapor_chaqueta"]
    assert camara[:-1] and all(camara[:-1]) and camara[-1] is False   # RECUPERACION, fin
    # la chaqueta la lleva _mantener_chaqueta con su consigna (300 < consigna - 10)
    assert chaqueta and all(chaqueta)


# ── 3 y 5. Aislamiento: techo, histéresis y 3 s; exposición sigue ──────────

def test_3_5_aislamiento_en_esterilizacion(monkeypatch):
    ciclo, estado, salidas, _am, reloj = _armar(monkeypatch)
    _hasta_fase(ciclo, reloj, "CALENTAMIENTO")
    _calentar(ciclo, estado, salidas, reloj)
    _tick(ciclo, reloj, estado, temp=134.3, pres=p_saturacion_kpa(134.3))
    est = ciclo._fases[3]
    fin = est._timer_fin
    restante_antes = estado.exposicion_restante_s
    # entrada inmediata al llegar al techo
    _tick(ciclo, reloj, estado, temp=134.5, pres=TECHO_EST + 0.1)
    assert estado.aislamiento_camara.aislado
    assert not salidas.on("vapor_camara") and not salidas.on("vapor_chaqueta")
    # bajo el techo pero no bajo techo - histéresis (3 kPa): sigue aislada
    for _ in range(10):
        _tick(ciclo, reloj, estado, temp=134.5, pres=TECHO_EST - 1.0)
        assert not salidas.on("vapor_camara") and not salidas.on("vapor_chaqueta")
    # bajo techo - 3 kPa sostenido 3 s: reabre
    for _ in range(6):
        _tick(ciclo, reloj, estado, temp=134.5, pres=TECHO_EST - 4.0)
        assert not salidas.on("vapor_camara")
    _tick(ciclo, reloj, estado, temp=134.5, pres=TECHO_EST - 4.0)
    _tick(ciclo, reloj, estado, temp=134.5, pres=TECHO_EST - 4.0)
    assert not estado.aislamiento_camara.aislado and salidas.on("vapor_camara")
    # 5: la exposición siguió corriendo (el fin no se movió) y F0 sigue en ESTERILIZACION
    assert est._timer_fin == fin
    assert estado.exposicion_restante_s < restante_antes
    assert estado.fase_ciclo == "ESTERILIZACION"


# ── 4. Fallas del aislamiento ─────────────────────────────────────────────

def test_4a_aislamiento_sostenido_falla_cic15(monkeypatch):
    ciclo, estado, salidas, _am, reloj = _armar(monkeypatch)
    _hasta_fase(ciclo, reloj, "CALENTAMIENTO")
    _calentar(ciclo, estado, salidas, reloj)
    r = None
    for _ in range(int(181 / TICK) + 4):
        r = _tick(ciclo, reloj, estado, temp=134.5, pres=TECHO_EST + 0.5)
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            break
    assert r == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.codigo_fallo == "CIC-15"
    assert not salidas.on("vapor_camara") and not salidas.on("vapor_chaqueta")


def test_4b_aislamiento_recurrente_falla_cic16(monkeypatch):
    ciclo, estado, salidas, _am, reloj = _armar(monkeypatch)
    _hasta_fase(ciclo, reloj, "CALENTAMIENTO")
    _calentar(ciclo, estado, salidas, reloj)
    r = None
    for _ in range(6):
        r = _tick(ciclo, reloj, estado, temp=134.5, pres=TECHO_EST + 0.5)
        if r == CicloResultado.ESPERANDO_CONFIRMACION:
            break
        for _ in range(8):
            _tick(ciclo, reloj, estado, temp=134.5, pres=TECHO_EST - 4.0)
    assert r == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.codigo_fallo == "CIC-16"


# ── 6. Protección de chaqueta: corte y sin lectura ────────────────────────

def test_6a_corte_de_chaqueta_gana_a_la_fase(monkeypatch):
    ciclo, estado, salidas, am, reloj = _armar(monkeypatch)
    _hasta_fase(ciclo, reloj, "CALENTAMIENTO")
    # lejos del objetivo la fase pide vapor_chaqueta ON; con el corte, OFF
    _tick(ciclo, reloj, estado, temp=110.0, pres=p_saturacion_kpa(110.0), pres_chaqueta=376.0)
    assert not salidas.on("vapor_chaqueta")
    assert salidas.on("vapor_camara")
    assert any(i.codigo == "CIC-18" for i in am.activas())
    _tick(ciclo, reloj, estado, temp=110.5, pres=p_saturacion_kpa(110.5), pres_chaqueta=330.0)
    assert salidas.on("vapor_chaqueta")
    assert not any(i.codigo == "CIC-18" for i in am.activas())


def test_6b_chaqueta_sin_lectura_corta_el_vapor(monkeypatch):
    ciclo, estado, salidas, _am, reloj = _armar(monkeypatch)
    _hasta_fase(ciclo, reloj, "CALENTAMIENTO")
    _tick(ciclo, reloj, estado, temp=110.0, pres=p_saturacion_kpa(110.0))
    assert salidas.on("vapor_chaqueta")
    _tick(ciclo, reloj, estado, temp=110.5, pres=p_saturacion_kpa(110.5), pres_chaqueta=None)
    assert not salidas.on("vapor_chaqueta") and not salidas.on("vapor_camara")


# ── 7. _mantener_chaqueta: no actúa en CAL/EST, retoma después ─────────────

def test_7_mantener_chaqueta_no_actua_y_retoma(monkeypatch):
    ciclo, estado, salidas, _am, reloj = _armar(monkeypatch, pres_chaqueta=200.0)
    _hasta_fase(ciclo, reloj, "CALENTAMIENTO")
    _calentar(ciclo, estado, salidas, reloj)
    # en ESTERILIZACION, con la presión de cámara en el techo, la fase deja la
    # chaqueta en OFF aunque la chaqueta esté muy por debajo de su consigna
    _tick(ciclo, reloj, estado, temp=134.5, pres=TECHO_EST + 0.5)
    assert not salidas.on("vapor_chaqueta")
    for _ in range(8):
        _tick(ciclo, reloj, estado, temp=134.5, pres=TECHO_EST - 4.0)
    _esterilizar(ciclo, estado, salidas, reloj)
    assert ciclo._fases[ciclo._fase_idx].name == "DESCOMPRESION"
    _tick(ciclo, reloj, estado, temp=134.0, pres=P_SAT)
    assert salidas.on("vapor_chaqueta")            # consigna de chaqueta retomada


# ── 9. FALLO, cancelación y paro cierran las dos válvulas ─────────────────

def _en_esterilizacion(monkeypatch):
    ciclo, estado, salidas, am, reloj = _armar(monkeypatch)
    _hasta_fase(ciclo, reloj, "CALENTAMIENTO")
    _calentar(ciclo, estado, salidas, reloj)
    _tick(ciclo, reloj, estado, temp=134.3, pres=p_saturacion_kpa(134.3))
    assert salidas.on("vapor_camara")
    return ciclo, estado, salidas, reloj


def test_9a_fallo_cierra_las_dos(monkeypatch):
    ciclo, estado, salidas, reloj = _en_esterilizacion(monkeypatch)
    for _ in range(14):                                   # temperatura alta 5 s
        r = _tick(ciclo, reloj, estado, temp=138.0, pres=p_saturacion_kpa(134.3))
    assert r == CicloResultado.ESPERANDO_CONFIRMACION
    assert not salidas.on("vapor_camara") and not salidas.on("vapor_chaqueta")


def test_9b_cancelacion_cierra_las_dos(monkeypatch):
    ciclo, estado, salidas, reloj = _en_esterilizacion(monkeypatch)
    estado.set_flag("CICLO_CANCELADO", True)
    assert _tick(ciclo, reloj) == CicloResultado.ESPERANDO_CONFIRMACION
    assert not salidas.on("vapor_camara") and not salidas.on("vapor_chaqueta")


def test_9c_paro_cierra_las_dos(monkeypatch):
    ciclo, estado, salidas, reloj = _en_esterilizacion(monkeypatch)
    estado.set_flag("PARO_EMERGENCIA", True)
    estado.set_flag("PARO_REAL", True)
    assert _tick(ciclo, reloj) == CicloResultado.ESPERANDO_CONFIRMACION
    assert not salidas.on("vapor_camara") and not salidas.on("vapor_chaqueta")

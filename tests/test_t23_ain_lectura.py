# tests/test_t23_ain_lectura.py
#
# Tanda 23 (AIN-03, AIN-04): el enlace lee las 16 AI del principal (fc04
# 0x0000 ×16). Lista cruda "ai" de 24: ai[0..5] = RTD 1-6, ai[6..7] = None,
# ai[8..23] = AI 1-16. Contra el simulador M31 (127.0.0.1, puerto libre).

import logging

import pytest

from autoclave.config import load_config
from autoclave.core.runtime import asignacion_io as aio
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.hal.measures import converters
from autoclave.protocols import modbus_link
from autoclave.protocols.modbus_link import ModbusLink
from autoclave.utils.resources import resource_path
from tests.helpers.m31_simulado import M31Simulado, config_para, esperar

logging.getLogger("pymodbus").setLevel(logging.CRITICAL)

CALIBRACION = resource_path("autoclave/config/calibration_modbus.yaml")


@pytest.fixture(autouse=True)
def _limpio():
    aio.restablecer_memoria_fabrica_codigo()
    converters.reiniciar_presiones()
    yield
    aio.restablecer_memoria_fabrica_codigo()
    converters.reiniciar_presiones()


@pytest.fixture
def sim():
    s = M31Simulado()
    s.iniciar()
    yield s
    s.detener()


def test_constantes_del_mapa():
    assert modbus_link.DIR_PRES == 0x0000
    assert modbus_link.N_PRES == 16
    assert modbus_link.N_AI == 24


@pytest.mark.req("AIN-03")
def test_lee_las_16_ai_con_corrientes_distintas(sim):
    # corrientes distintas por canal (todas >= 4 mA: el módulo no las pone a 0)
    sim.corrientes = [4000 + 1000 * i for i in range(16)]
    sim.temperaturas = [100, 200, 300, 400, 500, 600]
    enlace = ModbusLink(config=config_para(sim))
    assert len(enlace.get_state()["ai"]) == 24        # estado inicial: 24, todo None
    enlace.MARGEN_TICK_CONTROL = 0.3
    enlace.start()
    try:
        esperar(lambda: enlace.is_connected() and enlace.get_state()["ai_seq"] > 1, 5.0)
        ai = enlace.get_state()["ai"]
    finally:
        enlace.stop()
    assert len(ai) == 24
    assert ai[0:6] == [100, 200, 300, 400, 500, 600]   # RTD 1-6
    assert ai[6] is None and ai[7] is None
    for i in range(16):
        assert ai[8 + i] == 4000 + 1000 * i, f"AI {i + 1:02d}"    # ai[8+i] = AI i+1


@pytest.mark.req("AIN-04")
def test_ai_16_con_calibracion_nominal_lee_un_valor():
    """AI 16 (canal crudo 23) con la calibración nominal de fábrica: 12 mA ->
    200 kPa. Asignada a pres_camara, EstadoAutoclave la lee de su posición."""
    cfg = load_config(CALIBRACION)
    assert len(cfg.calibration.factory.pressure) == 16
    ai = [None] * 24
    ai[23] = 12000
    for _ in range(converters.DEBOUNCE_LECTURAS_PRESION + 1):
        presiones = converters.convert_pressures(ai, cfg)
    assert len(presiones) == 16
    assert presiones[15] == pytest.approx(200.0)
    assert all(v is None for v in presiones[:15])

    asignacion = aio.combinar(aio.fabrica_codigo(), {"pres_camara": 16})
    assert aio.validar(asignacion) == []
    assert aio.canal_crudo("pres_camara", 16) == 23
    aio.aplicar_en_memoria(asignacion)
    assert EstadoAutoclave.map_pres["pres_camara"] == 15
    e = EstadoAutoclave()
    e.update({"pressure": presiones})
    assert e.sensores_pres["pres_camara"] == pytest.approx(200.0)

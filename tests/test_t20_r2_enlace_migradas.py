# Tanda 20, revisión R (V20-s2-01, V20-s2-04): propiedades que probaban
# pruebas borradas con el enlace serial y que no son del serial, migradas a
# ModbusLink contra el simulador M31 (127.0.0.1, puerto libre).
#
# - SAF-01 / A-3 (antes test_u4::test_conectar_notifica_la_di_en_cero_a_units
#   y test_adenda_enlace_paro::test_connect_pone_di_en_cero_y_borra_el_sello):
#   al (re)abrir la conexión, la DI de la conexión anterior no vale: se pone a
#   0 (equivale a paro) y se avisa a Units antes del primer sondeo.
# - B9 hipótesis 2 (antes test_b9_buzzer_paro con SerialLink real): tras el
#   apagado total con el paro, el enlace real no vuelve a escribir en ON
#   ninguna bobina por su cuenta (ni por la lógica de discrepancia).

import time

import pytest

from autoclave.protocols.modbus_link import ModbusLink
from tests.helpers.m31_simulado import M31Simulado, TickLazo, config_para, esperar


@pytest.fixture
def sim():
    s = M31Simulado()
    s.precargar_configuracion()
    s.iniciar()
    yield s
    s.detener()


def _enlace(sim, recibidos):
    e = ModbusLink(on_update=lambda d: recibidos.append(dict(d, di=list(d["di"]))),
                   config=config_para(sim))
    e.start()
    return e


@pytest.mark.req("SAF-01")
@pytest.mark.req("T20-03")
def test_al_reconectar_la_di_anterior_se_pone_en_cero_antes_del_primer_sondeo(sim):
    sim.di[:] = [True] * 16
    recibidos = []
    e = _enlace(sim, recibidos)
    try:
        assert esperar(e.is_connected, timeout=10)
        assert esperar(lambda: recibidos and recibidos[-1]["di"][:16] == [1] * 16, timeout=5)
        sim.silencio = True
        assert esperar(lambda: not e.is_connected(), timeout=10)
        corte = len(recibidos)
        sim.silencio = False
        assert esperar(e.is_connected, timeout=15)
        tras = recibidos[corte:]
        # La primera notificación con el puerto abierto tras la pérdida trae la
        # DI a cero (paro) y es anterior a cualquier DI leída de nuevo en 1.
        i_cero = next(i for i, d in enumerate(tras) if d["port_open"] and d["di"] == [0] * 56)
        primeras_en_uno = [i for i, d in enumerate(tras) if d["di"][:16] == [1] * 16]
        assert not primeras_en_uno or i_cero < primeras_en_uno[0]
    finally:
        e.stop()


@pytest.mark.req("D9-9")
@pytest.mark.req("T20-03")
def test_tras_all_off_el_enlace_no_reescribe_bobinas_en_on(sim):
    recibidos = []
    e = _enlace(sim, recibidos)
    try:
        with TickLazo(e):
            assert esperar(e.is_connected, timeout=10)
            for canal in (3, 4, 9):
                assert e.set_output(canal, True) is True
            assert esperar(lambda: all(sim.bobinas[c - 1] for c in (3, 4, 9)), timeout=3)
            assert e.all_off(timeout=2.0) is True
            n = len(sim.escrituras_bobinas())
            time.sleep(2.5)    # > tolerancia de discrepancia (1 s) + varios sondeos
            nuevas = sim.escrituras_bobinas()[n:]
            assert not any(any(v) for _fc, _dir, v in nuevas), nuevas
            assert not any(sim.bobinas)
    finally:
        e.stop()

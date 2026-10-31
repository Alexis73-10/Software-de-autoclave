"""Tanda 8 / S2a / D8-2.9 (TMG-04 de la revisión Q1): DESPEJAR de COM-02/03
(`ControlLoop.enlace_confirmado_ok`) y la salida de la tolerancia por DI
vencida (`CicloState`) exigen 3 tramas DI DISTINTAS y nuevas (por número de
secuencia de la trama), no 3 ticks. Una misma trama DI vigente leída en varios
ticks cuenta una sola vez."""

import time
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.states import ciclo as modulo_ciclo
from autoclave.state_machine.states.ciclo import CicloResultado
from tests.test_t2_p3_di_vencida import _ciclo

DI = "DI:" + "1" * 56


# Las pruebas del número de secuencia DI en SerialLink se retiraron con el
# enlace serial (tanda 20, T20-03).

# ── ControlLoop: enlace_confirmado_ok cuenta tramas, no ticks ───────────────

def _loop():
    from tests.test_control_loop_test_mode import _make_control_loop
    loop, _, estado = _make_control_loop()
    loop.link.puerto_presente.return_value = True
    loop.link.is_connected.return_value = True
    loop.link.edad_ultima_di.return_value = 0.1
    return loop, estado


def _tick_enlace(loop):
    loop._actualizar_estado_modulo_es(True, 0.0)
    loop._contar_enlace_ok()


def test_la_misma_trama_en_varios_ticks_no_confirma_el_enlace():
    loop, _ = _loop()
    loop.link.secuencia_ultima_di.return_value = 7
    for _ in range(10):
        _tick_enlace(loop)
    assert loop.enlace_confirmado_ok is False


def test_tres_tramas_distintas_confirman_el_enlace():
    loop, _ = _loop()
    for i, seq in enumerate([1, 1, 2, 2, 2, 3]):
        loop.link.secuencia_ultima_di.return_value = seq
        _tick_enlace(loop)
        assert loop.enlace_confirmado_ok is (i == 5)


def test_dato_vencido_reinicia_la_cuenta_aunque_la_secuencia_cambie():
    loop, _ = _loop()
    for seq in (1, 2):
        loop.link.secuencia_ultima_di.return_value = seq
        _tick_enlace(loop)
    loop.link.edad_ultima_di.return_value = 99.0         # DI vencida
    _tick_enlace(loop)
    loop.link.edad_ultima_di.return_value = 0.1
    loop.link.secuencia_ultima_di.return_value = 3
    _tick_enlace(loop)
    assert loop.enlace_confirmado_ok is False
    for seq in (4, 5):
        loop.link.secuencia_ultima_di.return_value = seq
        _tick_enlace(loop)
    assert loop.enlace_confirmado_ok is True


def test_la_trama_previa_a_la_caida_no_cuenta_como_nueva():
    # misma secuencia antes y después de un tick vencido: no es trama nueva
    loop, _ = _loop()
    loop.link.secuencia_ultima_di.return_value = 1
    _tick_enlace(loop)
    loop.link.edad_ultima_di.return_value = 99.0
    _tick_enlace(loop)
    loop.link.edad_ultima_di.return_value = 0.1
    for seq in (1, 2, 3):
        loop.link.secuencia_ultima_di.return_value = seq
        _tick_enlace(loop)
    assert loop.enlace_confirmado_ok is False
    loop.link.secuencia_ultima_di.return_value = 4
    _tick_enlace(loop)
    assert loop.enlace_confirmado_ok is True


def test_publica_trama_di_nueva_en_el_estado():
    loop, estado = _loop()
    loop.link.secuencia_ultima_di.return_value = 1
    _tick_enlace(loop)
    assert estado.trama_di_nueva is True
    _tick_enlace(loop)
    assert estado.trama_di_nueva is False
    loop.link.edad_ultima_di.return_value = 99.0
    loop.link.secuencia_ultima_di.return_value = 2
    _tick_enlace(loop)
    assert estado.trama_di_nueva is False


def test_tick_fallido_reinicia_la_cuenta():
    loop, _ = _loop()
    for seq in (1, 2):
        loop.link.secuencia_ultima_di.return_value = seq
        _tick_enlace(loop)
    loop._tick_fallido()
    loop.link.secuencia_ultima_di.return_value = 3
    _tick_enlace(loop)
    assert loop.enlace_confirmado_ok is False


def test_tras_un_tick_fallido_la_misma_trama_no_cuenta_como_nueva():
    # TMG-05 (revisión S2a)
    loop, estado = _loop()
    loop.link.secuencia_ultima_di.return_value = 1
    _tick_enlace(loop)
    loop._tick_fallido()
    assert estado.trama_di_nueva is False
    _tick_enlace(loop)                                   # misma trama (1)
    assert estado.trama_di_nueva is False
    for seq in (2, 3):
        loop.link.secuencia_ultima_di.return_value = seq
        _tick_enlace(loop)
    assert loop.enlace_confirmado_ok is False             # solo 2 tramas nuevas
    loop.link.secuencia_ultima_di.return_value = 4
    _tick_enlace(loop)
    assert loop.enlace_confirmado_ok is True


# ── CicloState: salida de la tolerancia por DI vencida ─────────────────────

@pytest.fixture
def reloj(monkeypatch):
    t = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    return t


def test_ticks_sin_trama_nueva_no_reinician_la_tolerancia(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, _ = _ciclo(flags)
    ciclo.run()
    reloj[0] += modulo_ciclo._TOLERANCIA_DI_VENCIDA_SEG - 0.5
    flags["PARO_EMERGENCIA"] = False
    estado.trama_di_nueva = True
    ciclo.run()                                         # 1 trama nueva
    estado.trama_di_nueva = False
    for _ in range(5):                                  # 5 ticks con la misma trama
        assert ciclo.run() == CicloResultado.EN_CURSO
    flags["PARO_EMERGENCIA"] = True
    reloj[0] += 1.0
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "FALLO_CONEXION"


def test_tres_tramas_nuevas_reinician_la_tolerancia(reloj):
    flags = {"PARO_EMERGENCIA": True}
    ciclo, estado, _ = _ciclo(flags)
    ciclo.run()
    reloj[0] += modulo_ciclo._TOLERANCIA_DI_VENCIDA_SEG - 0.5
    flags["PARO_EMERGENCIA"] = False
    for nueva in (True, False, True, False, True):
        estado.trama_di_nueva = nueva
        assert ciclo.run() == CicloResultado.EN_CURSO
    flags["PARO_EMERGENCIA"] = True
    reloj[0] += 1.0
    assert ciclo.run() == CicloResultado.EN_CURSO       # la tolerancia cuenta desde cero
    ciclo._protocolo.ejecutar.assert_not_called()

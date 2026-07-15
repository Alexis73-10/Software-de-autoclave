from unittest.mock import MagicMock, patch

import serial

from tests.test_control_loop_connectivity_ticket import _make_loop


def _run_two_ticks(loop):
    """Deja correr run() hasta completar 2 pasadas por time.sleep()."""
    loop.link.is_connected.return_value = True
    loop._running.set()

    calls = {"n": 0}

    def _stop(*_a, **_k):
        calls["n"] += 1
        if calls["n"] >= 2:
            loop._running.clear()

    with patch("time.sleep", side_effect=_stop):
        loop.run()

    return calls["n"]


def test_excepcion_en_door_update_no_mata_el_hilo_control_loop():
    """Reproduce el bug: la tarjeta se desconecta/reconecta y una escritura
    serial en curso (p.ej. door.update() -> cerrar_on()) lanza
    SerialTimeoutException. El hilo ControlLoop no debe morir por eso: debe
    registrar el error y seguir iterando en el siguiente tick."""
    loop = _make_loop()

    door_falla = MagicMock()
    door_falla.update.side_effect = serial.serialutil.SerialTimeoutException(
        "Write timeout"
    )
    loop.doors = [door_falla]

    ticks = _run_two_ticks(loop)

    assert ticks == 2  # el loop sobrevivió a la excepción y completó otra vuelta
    assert door_falla.update.call_count == 2  # se siguió llamando en cada tick

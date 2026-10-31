# tests/test_q1rev_enlace_ok_tick_fallido.py
"""Revisión Q1 (SAF-03): un tick que no se completa (lanza) reinicia el
conteo de ticks con el enlace "ok", para que enlace_confirmado_ok no quede en
True con el lazo fallando o el enlace caído."""
from unittest.mock import patch

from tests.test_control_loop_test_mode import _make_control_loop


def test_tick_fallido_reinicia_el_conteo_del_enlace():
    loop, _, _ = _make_control_loop()
    loop._ticks_modulo_es_ok = 5
    assert loop.enlace_confirmado_ok is True
    loop._tick_fallido()
    assert loop._ticks_modulo_es_ok == 0
    assert loop.enlace_confirmado_ok is False


def test_tick_que_lanza_tras_contar_no_deja_el_enlace_confirmado():
    loop, _, _ = _make_control_loop()
    loop._ticks_modulo_es_ok = 5
    loop.estado_modulo_es = "ok"            # el conteo sube en este tick

    def tick_roto():
        loop._contar_enlace_ok()          # cuenta y después falla
        raise RuntimeError("x")

    loop._tick = tick_roto
    loop._running.set()

    def _stop(*_a, **_k):
        loop._running.clear()

    with patch("time.sleep", side_effect=_stop):
        loop.run()
    assert loop.enlace_confirmado_ok is False

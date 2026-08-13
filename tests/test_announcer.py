import time
from unittest.mock import MagicMock, patch

import numpy as np

from autoclave.devices.audio.announcer import Announcer


def _evento(event_id, prioridad, cooldown_s=5.0):
    ev = MagicMock()
    ev.event_id = event_id
    ev.prioridad = prioridad
    ev.cooldown_s = cooldown_s
    ev.samples = np.array([0.0, 0.0], dtype=np.float32)
    ev.sample_rate = 22050
    return ev


def _make_announcer(eventos, enabled=True, volume=80):
    return Announcer(
        eventos={e.event_id: e for e in eventos},
        get_volume=lambda: volume,
        get_enabled=lambda: enabled,
    )


@patch("autoclave.devices.audio.announcer.sd")
def test_say_retorna_de_inmediato_sin_bloquear(mock_sd):
    ev = _evento("a", prioridad=4)
    announcer = _make_announcer([ev])
    inicio = time.monotonic()
    announcer.say("a")
    assert time.monotonic() - inicio < 0.05


@patch("autoclave.devices.audio.announcer.sd")
def test_reproduce_evento_encolado(mock_sd):
    ev = _evento("a", prioridad=4)
    announcer = _make_announcer([ev])
    announcer.start()
    try:
        announcer.say("a")
        time.sleep(0.2)
        assert mock_sd.play.called
    finally:
        announcer.stop()


@patch("autoclave.devices.audio.announcer.sd")
def test_evento_desconocido_se_ignora(mock_sd):
    announcer = _make_announcer([])
    announcer.say("no_existe")  # no debe lanzar


@patch("autoclave.devices.audio.announcer.sd")
def test_deshabilitado_no_encola(mock_sd):
    ev = _evento("a", prioridad=4)
    announcer = _make_announcer([ev], enabled=False)
    announcer.start()
    try:
        announcer.say("a")
        time.sleep(0.2)
        assert not mock_sd.play.called
    finally:
        announcer.stop()


@patch("autoclave.devices.audio.announcer.sd")
def test_cooldown_descarta_repeticion_inmediata(mock_sd):
    ev = _evento("a", prioridad=4, cooldown_s=60.0)
    announcer = _make_announcer([ev])
    announcer.start()
    try:
        announcer.say("a")
        time.sleep(0.15)
        mock_sd.play.reset_mock()
        announcer.say("a")
        time.sleep(0.15)
        assert not mock_sd.play.called
    finally:
        announcer.stop()


@patch("autoclave.devices.audio.announcer.sd")
def test_evento_mas_urgente_interrumpe_al_que_suena(mock_sd):
    lento = _evento("lento", prioridad=3)
    urgente = _evento("urgente", prioridad=0)
    announcer = _make_announcer([lento, urgente])

    # Simula reproducción en curso: sd.wait() no retorna hasta que el test lo libere
    liberar = __import__("threading").Event()
    mock_sd.wait.side_effect = lambda: liberar.wait(2)

    announcer.start()
    try:
        announcer.say("lento")
        time.sleep(0.15)  # da tiempo a que el worker entre a sd.play/sd.wait
        announcer.say("urgente")
        time.sleep(0.05)
        assert mock_sd.stop.called
    finally:
        liberar.set()
        announcer.stop()


@patch("autoclave.devices.audio.announcer.sd")
def test_ganancia_cuadratica_se_aplica_al_volumen(mock_sd):
    import numpy as np
    ev = _evento("a", prioridad=4)
    ev.samples = np.array([1.0, 1.0], dtype=np.float32)
    announcer = _make_announcer([ev], volume=50)
    announcer.start()
    try:
        announcer.say("a")
        time.sleep(0.2)
        muestras_enviadas = mock_sd.play.call_args[0][0]
        assert abs(muestras_enviadas[0] - (0.5 ** 2.0)) < 1e-6
    finally:
        announcer.stop()

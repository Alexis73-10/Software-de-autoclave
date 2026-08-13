import threading
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


@patch("autoclave.devices.audio.announcer.sd")
def test_interrupcion_no_pierde_el_stop_por_condicion_de_carrera(mock_sd):
    # Regresión: si el worker soltara el lock entre popear el item de la cola y
    # llamar a sd.play(), un say() concurrente podría alcanzar a invocar
    # sd.stop() ANTES de que sd.play() se llamara siquiera — "deteniendo" una
    # reproducción que en realidad nunca arrancó.
    #
    # Para exponer esa ventana con precisión (sin depender de sleeps a ciegas),
    # inyectamos la demora justo en el hueco entre popear el item y llamar a
    # sd.play() usando get_volume (una dependencia real de _run(), ubicada
    # exactamente ahí en el código): entrado_get_volume se dispara apenas el
    # worker entra a esa sección, y solo entonces el test dispara el say()
    # interruptor. Si el worker soltara el lock antes de sd.play() (el bug),
    # ese say() alcanzaría a ejecutar sd.stop() durante la demora, antes de que
    # sd.play() se invoque siquiera. Con el fix (lock sostenido hasta incluir
    # sd.play()), el say() interruptor debe bloquearse en el lock hasta que
    # sd.play() ya haya sido llamado.
    lento = _evento("lento", prioridad=3)
    urgente = _evento("urgente", prioridad=0)
    entrado_get_volume = threading.Event()

    def _get_volume_lento():
        entrado_get_volume.set()
        time.sleep(0.15)
        return 80

    announcer = Announcer(
        eventos={lento.event_id: lento, urgente.event_id: urgente},
        get_volume=_get_volume_lento,
        get_enabled=lambda: True,
    )

    announcer.start()
    try:
        announcer.say("lento")
        assert entrado_get_volume.wait(1), "el worker no llego a get_volume()"
        announcer.say("urgente")  # con el fix, debe esperar el lock hasta que play() ya se haya llamado

        nombres_llamadas = [c[0] for c in mock_sd.mock_calls]
        idx_play = nombres_llamadas.index("play")
        idx_stop = nombres_llamadas.index("stop")
        assert idx_play < idx_stop
    finally:
        announcer.stop()


@patch("autoclave.devices.audio.announcer.sd")
def test_disable_now_vacia_cola_y_detiene_reproduccion(mock_sd):
    en_curso = _evento("en_curso", prioridad=4)
    pendiente = _evento("pendiente", prioridad=4)
    announcer = _make_announcer([en_curso, pendiente])

    # Simula reproducción en curso: sd.wait() no retorna hasta que el test lo libere
    liberar = threading.Event()
    mock_sd.wait.side_effect = lambda: liberar.wait(2)

    announcer.start()
    try:
        announcer.say("en_curso")
        time.sleep(0.15)  # da tiempo a que el worker entre a sd.play/sd.wait
        announcer.say("pendiente")
        time.sleep(0.05)  # "pendiente" queda encolado, no reproduciendo aun

        announcer.disable_now()

        assert mock_sd.stop.called
        assert len(announcer._cola) == 0
        assert "pendiente" not in announcer._encolados
    finally:
        liberar.set()
        announcer.stop()


@patch("autoclave.devices.audio.announcer.sd")
def test_evento_duplicado_mientras_esta_encolado_no_se_repite(mock_sd):
    bloqueante = _evento("bloqueante", prioridad=4)
    dup = _evento("dup", prioridad=4)
    announcer = _make_announcer([bloqueante, dup])

    # Simula reproducción en curso: sd.wait() no retorna hasta que el test lo libere
    liberar = threading.Event()
    mock_sd.wait.side_effect = lambda: liberar.wait(2)

    announcer.start()
    try:
        announcer.say("bloqueante")
        time.sleep(0.15)  # ocupa al worker, deja el lock libre para solo encolar

        announcer.say("dup")
        announcer.say("dup")  # segunda llamada mientras "dup" sigue en cola

        assert len(announcer._cola) == 1
        assert announcer._encolados == {"dup"}
    finally:
        liberar.set()
        announcer.stop()


@patch("autoclave.devices.audio.announcer.sd")
def test_cola_llena_descarta_el_menos_urgente_pero_nunca_a_p0(mock_sd):
    bloqueante = _evento("bloqueante", prioridad=4)
    # 10 eventos con urgencia decreciente (numero mayor = menos urgente)
    eventos_cola = [_evento(f"ev{i}", prioridad=5 + i) for i in range(10)]
    peor_nuevo = _evento("peor_nuevo", prioridad=99)
    p0 = _evento("p0", prioridad=0)
    announcer = _make_announcer([bloqueante, *eventos_cola, peor_nuevo, p0])

    # Simula reproducción en curso: sd.wait() no retorna hasta que el test lo libere
    liberar = threading.Event()
    mock_sd.wait.side_effect = lambda: liberar.wait(2)

    announcer.start()
    try:
        announcer.say("bloqueante")
        time.sleep(0.15)  # ocupa al worker para que la cola no se vacie sola

        for ev in eventos_cola:
            announcer.say(ev.event_id)  # llena la cola hasta el limite (_MAX_COLA=10)

        assert len(announcer._cola) == 10

        # un evento nuevo menos urgente que todos los presentes debe descartarse
        announcer.say("peor_nuevo")
        assert "peor_nuevo" not in announcer._encolados
        assert len(announcer._cola) == 10

        # ev9 (prioridad=14) es el menos urgente presente en la cola
        assert any(item[2] == "ev9" for item in announcer._cola)

        # un P0 nunca debe ser el descartado: al llegar con la cola llena,
        # debe desplazar al menos urgente presente (ev9), no perderse el mismo
        announcer.say("p0")
        assert "p0" in announcer._encolados
        assert not any(item[2] == "ev9" for item in announcer._cola)
        assert len(announcer._cola) == 10
    finally:
        liberar.set()
        announcer.stop()

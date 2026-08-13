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
        inicio = time.monotonic()
        announcer.say("urgente")
        transcurrido = time.monotonic() - inicio
        assert transcurrido < 0.05, "say() no debe bloquear aunque el worker este en sd.wait()"
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
def test_interrupcion_no_bloquea_al_control_loop_ni_pierde_el_stop(mock_sd):
    # Regresión del hallazgo crítico de la revisión final: el fix anterior
    # (lock sostenido durante sd.play()) cerraba la condición de carrera de
    # abajo, pero a costa de bloquear a say() -- llamado desde el hilo del
    # ControlLoop -- durante lo que tardara sd.play() en abrir el dispositivo
    # de audio (potencialmente indefinido con hardware colgado). El nuevo
    # contrato exige que say() SIEMPRE retorne casi de inmediato, sin importar
    # en qué punto esté el worker -- incluso en el hueco entre popear el item
    # de la cola y llamar a sd.play() -- a costa de reabrir una ventana de
    # carrera muy angosta y sin contención de lock donde, en el peor caso, el
    # sd.stop() de una interrupción podría no alcanzar a detener ese sonido
    # específico. Riesgo residual aceptado: el audio no tiene rol de
    # seguridad en este sistema (ver spec).
    #
    # Para forzar el peor caso (say() interruptor llega mientras el worker
    # sigue en el hueco, antes de sd.play()) inyectamos la demora en
    # get_volume() -- dependencia real de _run(), ubicada justo ahí en el
    # código -- y solo disparamos el say() interruptor una vez que el worker
    # ya entró a esa sección.
    lento = _evento("lento", prioridad=3)
    urgente = _evento("urgente", prioridad=0)
    entrado_get_volume = threading.Event()
    seguir = threading.Event()

    def _get_volume_lento():
        entrado_get_volume.set()
        seguir.wait(2)
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

        # El worker ya soltó el lock (popeó "lento", está dentro de
        # get_volume(), antes de llamar sd.play()). say() debe retornar casi
        # de inmediato de todos modos -- ya NO debe esperar a que el worker
        # llegue a llamar sd.play().
        inicio = time.monotonic()
        announcer.say("urgente")
        transcurrido = time.monotonic() - inicio
        assert transcurrido < 0.05, "say() no debe bloquear esperando al worker/dispositivo de audio"

        # El sd.stop() de la interrupción se ejecuta dentro de say() mismo,
        # fuera del lock -- debe quedar hecho ya, sin esperar a que el worker
        # termine get_volume()/play()/wait().
        assert mock_sd.stop.called

        seguir.set()  # libera al worker para que termine get_volume() y play()/wait()
    finally:
        seguir.set()
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

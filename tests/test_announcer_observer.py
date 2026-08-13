# tests/test_announcer_observer.py
from unittest.mock import MagicMock

from autoclave.devices.puertas.advanced_door import DoorState
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.services.domain.audio.announcer_observer import AnnouncerObserver


class _Alarma:
    def __init__(self, alarm_id):
        self.id = alarm_id


def _estado(machine_state=GlobalState.PREPARADO, fase_ciclo="", alarmas=None,
            puertas=None, camara_segura=False):
    e = MagicMock()
    e.get_machine_state.return_value = machine_state
    e.fase_ciclo = fase_ciclo
    e.Alarmas_activas = alarmas or []
    e.estado_puertas = puertas or {"Puerta 1": DoorState.CERRADO, "Puerta 2": DoorState.CERRADO}
    e.camara_segura_confirmada = camara_segura
    return e


def test_primer_tick_no_anuncia_nada():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado())
    announcer.say.assert_not_called()


def test_alarma_nueva_dispara_evento_mapeado():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado())  # siembra
    obs.update(_estado(alarmas=[_Alarma("SUMINISTRO_AGUA_BOMBA")]))
    announcer.say.assert_called_once_with("alr_sum_agua_bomba")


def test_alarma_sin_mapeo_no_dispara_nada():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado())
    obs.update(_estado(alarmas=[_Alarma("NO_HAY_CONEXION")]))
    announcer.say.assert_not_called()


def test_alarma_que_sigue_activa_no_repite():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado())
    obs.update(_estado(alarmas=[_Alarma("SENSOR_AUSENTE")]))
    announcer.say.reset_mock()
    obs.update(_estado(alarmas=[_Alarma("SENSOR_AUSENTE")]))
    announcer.say.assert_not_called()


def test_puerta_abriendo_a_abierto_anuncia_una_vez():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(puertas={"Puerta 1": DoorState.CERRADO, "Puerta 2": DoorState.CERRADO}))
    obs.update(_estado(puertas={"Puerta 1": DoorState.ABRIENDO, "Puerta 2": DoorState.CERRADO}))
    announcer.say.assert_not_called()  # transitorio, D-07
    obs.update(_estado(puertas={"Puerta 1": DoorState.ABIERTO, "Puerta 2": DoorState.CERRADO}))
    announcer.say.assert_called_once_with("pta_1_abierta")


def test_puerta_atrapada_dispara_emergencia():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado())
    obs.update(_estado(puertas={"Puerta 1": DoorState.CERRADO, "Puerta 2": DoorState.ATRAPADA}))
    announcer.say.assert_called_once_with("emg_puerta_2_atrapada")


def test_transicion_a_ciclo_anuncia_ciclo_iniciado():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(machine_state=GlobalState.PREPARADO))
    obs.update(_estado(machine_state=GlobalState.CICLO))
    announcer.say.assert_called_once_with("cic_iniciado")


def test_ciclo_completado_anuncia_equipo_preparado_y_cic_completado():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(machine_state=GlobalState.CICLO, fase_ciclo="COMPLETADO"))
    obs.update(_estado(machine_state=GlobalState.PREPARADO, fase_ciclo="COMPLETADO"))
    llamados = {c.args[0] for c in announcer.say.call_args_list}
    assert llamados == {"equipo_preparado", "cic_completado"}


def test_ciclo_cancelado_no_anuncia_cic_completado():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(machine_state=GlobalState.CICLO, fase_ciclo="CANCELADO"))
    obs.update(_estado(machine_state=GlobalState.PREPARADO, fase_ciclo="CANCELADO"))
    llamados = {c.args[0] for c in announcer.say.call_args_list}
    assert llamados == {"equipo_preparado"}


def test_transicion_ciclo_a_falla_anuncia_fallo_de_ciclo():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(machine_state=GlobalState.CICLO))
    obs.update(_estado(machine_state=GlobalState.FALLA))
    announcer.say.assert_called_once_with("fal_ciclo_abortado")


def test_camara_segura_confirmada_dispara_una_vez():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(camara_segura=False))
    obs.update(_estado(camara_segura=True))
    announcer.say.assert_called_once_with("fal_camara_segura")
    announcer.say.reset_mock()
    obs.update(_estado(camara_segura=True))
    announcer.say.assert_not_called()


def test_equipo_de_una_puerta_no_dispara_eventos_de_puerta_2():
    announcer = MagicMock()
    obs = AnnouncerObserver(announcer)
    obs.update(_estado(puertas={"Puerta 1": DoorState.CERRADO}))
    obs.update(_estado(puertas={"Puerta 1": DoorState.ABIERTO}))
    llamados = [c.args[0] for c in announcer.say.call_args_list]
    assert all("puerta_2" not in nombre for nombre in llamados)

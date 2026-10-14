"""E6 — reacción del ControlLoop a los eventos de la tarjeta (plan de protocolo
§7) y abortar_por_falla_io() en CicloState (§11.5)."""

from unittest.mock import MagicMock, patch

import pytest

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.protocols.serial_link import EventoTarjeta
from autoclave.state_machine.alarms.alarm_types import AlarmType
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState


# ---------------------------------------------------------------------------
# CicloState.abortar_por_falla_io
# ---------------------------------------------------------------------------

def _make_ciclo():
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 100.0}
    estado.sensores_pres = {"pres_camara": 200.0}
    estado.get_flag.return_value = False
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    ciclo = CicloState(estado, MagicMock(), cycle, config, MagicMock())
    ciclo.reset()
    return ciclo, estado


def test_abortar_por_falla_io_reporta_emergencia_con_el_id_recibido():
    ciclo, estado = _make_ciclo()
    ciclo.abortar_por_falla_io("TARJETA_WATCHDOG", "watchdog disparado")
    alarma = ciclo.alarm_manager.report.call_args[0][0]
    assert alarma.id == "TARJETA_WATCHDOG"
    assert alarma.type == AlarmType.EMERGENCIA
    assert estado.motivo_fallo == "watchdog disparado"
    assert estado.fase_ciclo == "FALLO_IO"


def test_abortar_por_falla_io_ejecuta_protocolo_y_deja_fallo_pendiente():
    ciclo, estado = _make_ciclo()
    ciclo._protocolo = MagicMock()
    ciclo.abortar_por_falla_io("TARJETA_REINICIO", "reinicio")
    ciclo._protocolo.ejecutar.assert_called_once()

    estado.get_flag.side_effect = lambda f: f == "CICLO_CONFIRMADO"
    assert ciclo.run() == CicloResultado.FALLO


def test_abortar_por_falla_io_no_duplica():
    ciclo, _ = _make_ciclo()
    ciclo.abortar_por_falla_io("TARJETA_REINICIO", "x")
    ciclo.abortar_por_falla_io("DISCREPANCIA_SALIDAS", "y")
    ciclo.abortar_por_desconexion()
    ciclo.alarm_manager.report.assert_called_once()


# ---------------------------------------------------------------------------
# ControlLoop
# ---------------------------------------------------------------------------

def _loop(estado_maquina=GlobalState.PREPARADO, conectado=True):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = EstadoAutoclave()
    cm = MagicMock()
    cm.get_selected_cycle.return_value = MagicMock()
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=estado, link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=MagicMock(), cycle_manager=cm,
                           config_manager=MagicMock())
    loop.units.get_all.return_value = {}
    estado.sensores_di["paro_emergencia"] = 1
    estado.sensores_di["suministro_electrico"] = 1
    loop.link.is_connected.return_value = conectado
    loop.link.edad_ultima_di.return_value = 0.1
    loop.link.tomar_eventos.return_value = []
    estado.get_machine_state = MagicMock(return_value=estado_maquina)
    return loop, estado


def _reportadas(loop):
    return [c[0][0] for c in loop.alarm_manager.report.call_args_list]


def _correr_un_tick(loop, tick):
    """run() con un solo tick: `tick` reemplaza a _tick y detiene el bucle."""
    loop.interval = 0

    def unico():
        loop._running.clear()
        tick()

    loop._tick = unico
    loop._running.set()
    loop.run()


def test_run_marca_el_tick_de_control_al_completarse():
    # TMG-01: solo un tick completado renueva el latido (FW-D6)
    loop, _ = _loop()
    _correr_un_tick(loop, lambda: None)
    loop.link.marcar_tick_control.assert_called_once()


def test_run_no_marca_el_tick_si_el_tick_falla():
    # TMG-01: un lazo vivo que falla en cada tick no alimenta el HB, así el
    # watchdog del firmware apaga las salidas.
    loop, _ = _loop()

    def falla():
        raise RuntimeError("falla en el tick")

    _correr_un_tick(loop, falla)
    loop.link.marcar_tick_control.assert_not_called()


def test_tick_no_marca_por_si_mismo():
    loop, _ = _loop(conectado=False)
    loop._tick()
    loop.link.marcar_tick_control.assert_not_called()


def test_fallo_de_handshake_reporta_alarma_bloqueante():
    loop, _ = _loop(conectado=False)
    loop.link.tomar_eventos.return_value = [
        EventoTarjeta("handshake", "TARJETA_SIN_ACK", "sin ack")]
    loop._tick()
    alarma = next(a for a in _reportadas(loop) if a.id == "TARJETA_SIN_ACK")
    assert alarma.type == AlarmType.FALLA
    assert alarma.blocks_operation is True
    assert alarma.description == "sin ack"


@pytest.mark.parametrize("alarm_id", ["TARJETA_WATCHDOG", "TARJETA_REINICIO",
                                      "DISCREPANCIA_SALIDAS",
                                      "TARJETA_EXPANSOR_FUERA_DE_LINEA"])
def test_evento_de_operacion_en_ciclo_aborta_por_falla_io(alarm_id):
    loop, _ = _loop(GlobalState.CICLO)
    loop.link.tomar_eventos.return_value = [EventoTarjeta("operacion", alarm_id, "motivo")]
    loop._tick()
    loop.state_machine.ciclo.abortar_por_falla_io.assert_called_once_with(alarm_id, "motivo")


def test_evento_de_operacion_en_ciclo_aborta_aunque_el_enlace_este_caido():
    loop, _ = _loop(GlobalState.CICLO, conectado=False)
    loop.link.tomar_eventos.return_value = [
        EventoTarjeta("operacion", "TARJETA_WATCHDOG", "wd")]
    loop._tick()
    loop.state_machine.ciclo.abortar_por_falla_io.assert_called_once()


@pytest.mark.parametrize("alarm_id", ["TARJETA_WATCHDOG", "TARJETA_REINICIO"])
def test_wd_o_reinicio_fuera_de_ciclo_es_alarma_bloqueante(alarm_id):
    loop, _ = _loop(GlobalState.PREPARADO)
    loop.link.tomar_eventos.return_value = [EventoTarjeta("operacion", alarm_id, "m")]
    loop._tick()
    loop.state_machine.ciclo.abortar_por_falla_io.assert_not_called()
    alarma = next(a for a in _reportadas(loop) if a.id == alarm_id)
    assert alarma.type == AlarmType.FALLA and alarma.blocks_operation is True
    # el propio enlace ya repite el handshake tras WD/BOOT
    loop.link.solicitar_handshake.assert_not_called()


@pytest.mark.parametrize("alarm_id", ["DISCREPANCIA_SALIDAS", "TARJETA_EXPANSOR_FUERA_DE_LINEA"])
def test_expansor_o_discrepancia_fuera_de_ciclo_pide_nuevo_handshake(alarm_id):
    loop, _ = _loop(GlobalState.PREPARADO)
    loop.link.tomar_eventos.return_value = [EventoTarjeta("operacion", alarm_id, "m")]
    loop._tick()
    assert any(a.id == alarm_id for a in _reportadas(loop))
    loop.link.solicitar_handshake.assert_called_once()


def test_handshake_ok_despeja_las_alarmas_de_tarjeta_de_fuera_de_ciclo():
    loop, _ = _loop(GlobalState.PREPARADO)
    loop.link.tomar_eventos.return_value = [
        EventoTarjeta("handshake", "TARJETA_SIN_ACK", "m"),
        EventoTarjeta("operacion", "TARJETA_WATCHDOG", "m")]
    loop._tick()
    loop.link.tomar_eventos.return_value = [EventoTarjeta("conectada", None, "ok")]
    loop._tick()
    despejadas = {c[0][0] for c in loop.alarm_manager.clear.call_args_list}
    assert {"TARJETA_SIN_ACK", "TARJETA_WATCHDOG"} <= despejadas


def test_handshake_ok_no_despeja_la_alarma_del_fallo_del_ciclo():
    loop, _ = _loop(GlobalState.CICLO)
    loop.link.tomar_eventos.return_value = [
        EventoTarjeta("operacion", "TARJETA_WATCHDOG", "m")]
    loop._tick()
    loop.link.tomar_eventos.return_value = [EventoTarjeta("conectada", None, "ok")]
    loop._tick()
    despejadas = {c[0][0] for c in loop.alarm_manager.clear.call_args_list}
    assert "TARJETA_WATCHDOG" not in despejadas


def test_enlace_sin_tomar_eventos_no_rompe_el_tick():
    loop, _ = _loop()
    loop.link.tomar_eventos.return_value = "no es lista"
    loop._tick()
    loop.state_machine.update.assert_called()


# ---------------------------------------------------------------------------
# TMG-06 / TMG-07 (revisión de temporización de la tanda 2026-10-14)
# ---------------------------------------------------------------------------

def test_evento_que_falla_no_pierde_los_siguientes():
    loop, _ = _loop()
    loop.link.tomar_eventos.return_value = [
        EventoTarjeta("handshake", "TARJETA_SIN_ACK", "a"),
        EventoTarjeta("handshake", "TARJETA_SIN_TRAMA_VALIDA", "b"),
    ]
    reportes = []

    def report(alarma):
        reportes.append(alarma.id)
        if len(reportes) == 1:
            raise RuntimeError("falla al reportar")

    loop.alarm_manager.report.side_effect = report
    loop._tick()
    assert reportes == ["TARJETA_SIN_ACK", "TARJETA_SIN_TRAMA_VALIDA"]


def test_falla_en_operacion_con_ciclo_terminando_se_reporta_fuera_de_ciclo():
    # TMG-07: abortar_por_falla_io no actúa si el ciclo ya terminaba; la
    # alarma no debe perderse; en CICLO no se repite el handshake (decisión 8).
    loop, _ = _loop(estado_maquina=GlobalState.CICLO)
    loop.state_machine.ciclo.abortar_por_falla_io.return_value = False
    loop.link.tomar_eventos.return_value = [
        EventoTarjeta("operacion", "DISCREPANCIA_SALIDAS", "motivo")]
    loop._tick()
    assert "DISCREPANCIA_SALIDAS" in _reportadas_ids(loop)
    loop.link.solicitar_handshake.assert_not_called()


def test_abortar_por_falla_io_devuelve_si_actuo():
    ciclo, _ = _make_ciclo()
    assert ciclo.abortar_por_falla_io("TARJETA_REINICIO", "x") is True
    assert ciclo.abortar_por_falla_io("TARJETA_REINICIO", "x") is False


def _reportadas_ids(loop):
    return [c[0][0].id for c in loop.alarm_manager.report.call_args_list]


def test_expansor_caido_fuera_de_ciclo_repite_el_handshake():
    # SAF-01: tras un ciclo abortado por expansor, no seguir con DI congeladas
    loop, _ = _loop(estado_maquina=GlobalState.FALLA)
    loop.link.expansor_fuera_de_linea.return_value = True
    loop._tick()
    loop.link.solicitar_handshake.assert_called_once()


def test_expansor_caido_en_ciclo_no_repite_el_handshake():
    loop, _ = _loop(estado_maquina=GlobalState.CICLO)
    loop.link.expansor_fuera_de_linea.return_value = True
    loop._tick()
    loop.link.solicitar_handshake.assert_not_called()

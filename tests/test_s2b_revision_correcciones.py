"""S2b (tanda 8): correcciones de la revisión de seguridad y temporización
(safety-reviewer SAF-01/02/04/05, timing-auditor TMG-02/03/04/10)."""

from unittest.mock import MagicMock

import requests

from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import COM_04
from autoclave.state_machine.alarms.instancia import EstadoInstancia
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_backend_autenticacion import db, entorno  # noqa: F401  (fixtures)
from tests.test_control_loop_test_mode import _make_control_loop, _run_one_tick


# ── SAF-01: COM-04 solo se resuelve con una confirmación ─────────────────────

def test_reconocer_la_falla_no_resuelve_com04():
    am = AlarmManager()
    am.activar(COM_04)
    am.resolver_todas_por_reinicio()
    assert am.obtener(COM_04).estado is EstadoInstancia.ACTIVA
    am.resolver(COM_04)
    assert am.obtener(COM_04).estado is EstadoInstancia.RESUELTA_SIN_RECONOCER


def test_confirmacion_resuelve_com04_aunque_la_marca_local_este_desfasada():
    loop, _, _ = _make_control_loop()
    loop.alarm_manager = AlarmManager()
    loop.alarm_manager.activar(COM_04)
    loop._com04_activa = False
    loop._salidas_confirmadas("handshake", registrar=False)
    assert loop.alarm_manager.obtener(COM_04).estado is EstadoInstancia.RESUELTA_SIN_RECONOCER


def test_fault_reset_rechazado_durante_los_reintentos(entorno):  # noqa: F811
    client, ctx, _ = entorno
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    ctx.estado.get_flag.side_effect = lambda f: False
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.salidas_sin_confirmar_pendiente = True
    r = client.post("/fault/reset")
    assert r.status_code == 409 and r.json()["codigo"] == "salidas_sin_confirmar"
    assert ("RESET_FALLA", True) not in [c.args for c in ctx.estado.set_flag.call_args_list]


# ── TMG-04 / SAF-02: /cycle/start con modo prueba o reintentos pendientes ────

def _start_rechazado(client, ctx, codigo):
    r = client.post("/cycle/start")
    assert r.status_code == 409, r.text
    assert r.json()["codigo"] == codigo
    assert ("START_CICLO", True) not in [c.args for c in ctx.estado.set_flag.call_args_list]


def test_start_rechazado_con_reintentos_pendientes(entorno):  # noqa: F811
    client, ctx, _ = entorno
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.salidas_sin_confirmar_pendiente = True
    _start_rechazado(client, ctx, "salidas_sin_confirmar")


def test_start_rechazado_con_modo_prueba(entorno):  # noqa: F811
    client, ctx, _ = entorno
    ctx.control_loop.test_mode_active = True
    ctx.control_loop.salidas_sin_confirmar_pendiente = False
    _start_rechazado(client, ctx, "modo_prueba_activo")


def test_entrar_al_modo_prueba_borra_la_orden_de_inicio():
    loop, _, estado = _make_control_loop()
    estado.set_flag("START_CICLO", True)
    assert loop.enter_test_mode()[0] is True
    assert estado.get_flag("START_CICLO") is False


# ── TMG-03: el reintento espera el ACK con un plazo corto ───────────────────

def test_reintento_usa_un_plazo_corto_del_ack():
    from autoclave.services.domain.loop import control_loop as cl
    loop, _, _ = _make_control_loop()
    loop.link.puerto_presente.return_value = True
    loop.link.tomar_eventos.return_value = []
    loop.link.expansor_fuera_de_linea.return_value = False
    loop.enter_test_mode()
    loop.set_do.reset_all_outputs.reset_mock()
    loop.set_do.reset_all_outputs.return_value = False
    loop.exit_test_mode()
    assert loop.salidas_sin_confirmar_pendiente is True
    _run_one_tick(loop)
    assert loop.set_do.reset_all_outputs.call_args.kwargs == {
        "timeout": cl._TIMEOUT_ACK_REINTENTO_ALL_OFF_S}
    assert cl._TIMEOUT_ACK_REINTENTO_ALL_OFF_S < 0.8      # menor que el del cliente HTTP


def test_set_output_pasa_el_plazo_al_enlace():
    from autoclave.devices.io.set_io import SetOutput
    s = SetOutput.__new__(SetOutput)
    s.io = MagicMock()
    s.io.all_off.return_value = True
    assert s.reset_all_outputs(timeout=0.3) is True
    s.io.all_off.assert_called_once_with(timeout=0.3)
    s.io.all_off.reset_mock()
    s.reset_all_outputs()
    s.io.all_off.assert_called_once_with()


# ── TMG-02: motivo del timeout de calentamiento en el sostenimiento ─────────

def _calentamiento_vencido(pausada):
    f = CalentamientoFase(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
    f.reset()
    f.cycle.get_param.side_effect = lambda s, n: None
    f._inicializado = True
    f._timer_timeout_fin = -1.0
    f._timer_sostenido_desde = 0.0
    if pausada:
        f.pausar_ventanas_estabilidad(3.0)
    return f


def test_timeout_en_sostenimiento_alargado_tiene_su_motivo():
    f = _calentamiento_vencido(pausada=True)
    assert f.update() == FaseResult.FALLO
    assert "durante el sostenimiento" in f.estado.motivo_fallo
    assert "no se alcanzó" not in f.estado.motivo_fallo


def test_timeout_sin_pausas_conserva_el_motivo():
    f = _calentamiento_vencido(pausada=False)
    assert f.update() == FaseResult.FALLO
    assert "no se alcanzó el objetivo" in f.estado.motivo_fallo


def test_reset_pone_en_cero_lo_pausado():
    f = _calentamiento_vencido(pausada=True)
    assert f.ventana_pausada_s() == 3.0
    f.reset()
    assert f.ventana_pausada_s() == 0.0


# ── TMG-10 / SAF-05: timeout del DESPEJAR ────────────────────────────────────

def test_despejar_sin_confirmacion_a_tiempo():
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend
    ui = UIServiceBackend.__new__(UIServiceBackend)
    ui.backend = MagicMock()
    ui.backend.post.side_effect = requests.Timeout("lento")
    assert ui.reconocer_alarma("COM-02|X", "operador") == (
        False, "notificaciones.despejar_sin_confirmacion")

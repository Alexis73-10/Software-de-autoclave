"""T5 (E3, tanda 2026-10-14): protocolo de estado seguro común (fin de ciclo
§15), paro con el resultado pendiente (TMG-04), excepciones repetidas en el
tick (TMG-03) y endpoints."""

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.state_machine.machine.enum_global import GlobalState

_CFG = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0}


class _Config(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def _estado(pres=200.0, temp=120.0, paro=False):
    flags = {"PARO_EMERGENCIA": paro}
    return SimpleNamespace(
        sensores_pres={"pres_camara": pres}, sensores_temp={"temp_camara": temp},
        get_flag=lambda f: flags.get(f, False), flags=flags)


def _protocolo():
    p = MagicMock()
    p.ejecutado = True
    p.cycle = None
    return p


def _es(estado, eventos=None):
    return ProtocoloEstadoSeguro(estado, _Config(_CFG), programas_seguridad=lambda: [],
                                 al_evento=(lambda e, d: eventos.append((e, d)))
                                 if eventos is not None else None)


def test_sigue_el_protocolo_hasta_tres_ticks_seguros_y_cierra_valvulas():
    estado, eventos = _estado(), []
    es, prot = _es(estado, eventos), _protocolo()
    es.iniciar(prot)
    es.update()
    prot.update.assert_called_once()
    assert es.activo
    estado.sensores_pres["pres_camara"] = 101.3
    estado.sensores_temp["temp_camara"] = 60.0
    es.update(); es.update()
    assert es.activo
    es.update()
    assert not es.activo
    prot.finalizar.assert_called_once()
    assert [e for e, _ in eventos][-1] == "estado_seguro_alcanzado"
    assert "duracion_s" in eventos[-1][1]


def test_paro_detiene_y_exige_confirmacion():
    estado, eventos = _estado(), []
    es, prot = _es(estado, eventos), _protocolo()
    es.iniciar(prot)
    estado.flags["PARO_EMERGENCIA"] = True
    es.update()
    prot.update.assert_not_called()
    assert es.confirmar() is False                    # con el paro activo, no
    estado.flags["PARO_EMERGENCIA"] = False
    es.update(); es.update()
    prot.update.assert_not_called()                   # liberado: sin avance automático
    assert es.requiere_confirmacion
    assert es.confirmar() is True
    es.update()
    prot.update.assert_called_once()
    nombres = [e for e, _ in eventos]
    assert nombres == ["estado_seguro_iniciado", "paro_activado", "paro_liberado",
                       "estado_seguro_confirmado"]


def test_sin_datos_vigentes_no_avanza():
    estado = _estado()
    es, prot = _es(estado), _protocolo()
    es.iniciar(prot)
    es.update(datos_vigentes=False)
    prot.update.assert_not_called()


def test_no_inicia_con_un_protocolo_no_ejecutado():
    es = _es(_estado())
    prot = _protocolo()
    prot.ejecutado = False
    es.iniciar(prot)
    assert not es.activo


# ── CicloState: paro con el resultado pendiente (TMG-04) ───────────────────

from autoclave.state_machine.alarms.alarm_manager import AlarmManager     # noqa: E402
from autoclave.state_machine.states.ciclo import CicloResultado, CicloState  # noqa: E402


def _ciclo(flags):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 100.0}
    estado.sensores_pres = {"pres_camara": 200.0}
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1}
    estado.get_flag.side_effect = lambda f: flags.get(f, False)
    cycle = MagicMock()
    cycle.get_param.return_value = None
    cycle.copia.return_value = cycle
    cycle.sensores = None
    config = MagicMock(); config.get.return_value = None
    set_do = MagicMock()
    ciclo = CicloState(estado, set_do, cycle, config, AlarmManager())
    ciclo.reset()
    ciclo._protocolo = MagicMock()
    return ciclo, set_do


def test_paro_en_ciclo_apaga_sin_abrir_valvulas():
    flags = {"PARO_EMERGENCIA": True}
    ciclo, set_do = _ciclo(flags)
    assert ciclo.run() == CicloResultado.ESPERANDO_CONFIRMACION
    ciclo._protocolo.ejecutar.assert_called_once_with(abrir_valvulas=False)


def test_resultado_pendiente_con_paro_no_acciona_reposo_ni_protocolo():
    flags = {}
    ciclo, set_do = _ciclo(flags)
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    ciclo._mantener_valvula_reposo = MagicMock()
    flags["PARO_EMERGENCIA"] = True
    ciclo.run()
    set_do.apagar_por_paro.assert_called()
    ciclo._mantener_valvula_reposo.assert_not_called()
    flags["PARO_EMERGENCIA"] = False                   # liberado sin confirmar
    ciclo.run()
    ciclo._mantener_valvula_reposo.assert_not_called()
    ciclo._protocolo.update.assert_not_called()
    flags["CICLO_CONFIRMADO"] = True                   # confirmación fusionada
    assert ciclo.run() == CicloResultado.COMPLETADO


# ── ControlLoop: TMG-03 ─────────────────────────────────────────────────────

def _loop():
    from autoclave.services.domain.loop.control_loop import ControlLoop
    from autoclave.core.runtime.status import EstadoAutoclave
    cm = MagicMock()
    cm.get_selected_cycle.return_value = MagicMock()
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=EstadoAutoclave(), link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=MagicMock(), cycle_manager=cm,
                           config_manager=MagicMock())
    return loop


def test_tres_ticks_fallidos_apagan_todas_las_salidas():
    loop = _loop()
    loop._tick_fallido()
    loop._tick_fallido()
    loop.set_do.reset_all_outputs.assert_not_called()
    loop._tick_fallido()
    loop.set_do.reset_all_outputs.assert_called_once()
    loop._tick_fallido()
    loop.set_do.reset_all_outputs.assert_called_once()     # una vez por racha


def test_estado_seguro_sobrevive_a_set_active_cycle():
    loop = _loop()
    es = loop.estado_seguro
    loop.estado.set_flag("PARO_EMERGENCIA", False)     # S2: con paro se rechaza
    with patch("autoclave.services.domain.loop.control_loop.StateMachine") as sm:
        loop.set_active_cycle(MagicMock())
    assert sm.call_args.kwargs["estado_seguro"] is es


# ── Endpoints ───────────────────────────────────────────────────────────────

from tests.backend_doble import cargar_servidor                     # noqa: E402


def _cliente(paro=False, confirmado=True):
    ctx = MagicMock()
    ctx.estado.get_flag.side_effect = lambda f: paro if f == "PARO_EMERGENCIA" else False
    ctx.estado.get_machine_state.return_value = GlobalState.FALLA
    ctx.control_loop.confirmar_estado_seguro.return_value = confirmado
    ctx.control_loop.bloqueo_maquina.return_value = threading.Lock()
    ctx.control_loop.test_mode_active = False
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), ctx


def test_confirmar_estado_seguro():
    client, ctx = _cliente()
    assert client.post("/safe-state/confirm").status_code == 200


def test_confirmar_con_paro_409():
    client, ctx = _cliente(paro=True)
    r = client.post("/safe-state/confirm")
    assert r.status_code == 409 and r.json()["codigo"] == "paro_emergencia"
    ctx.control_loop.confirmar_estado_seguro.assert_not_called()


def test_confirmar_sin_pendiente_409():
    client, _ = _cliente(confirmado=False)
    assert client.post("/safe-state/confirm").json()["codigo"] == "sin_confirmacion_pendiente"


def test_reconocer_falla_confirma_tambien_el_estado_seguro():
    client, ctx = _cliente()
    assert client.post("/fault/reset").status_code == 200
    ctx.control_loop.confirmar_estado_seguro.assert_called_once()


# ── StateMachine ────────────────────────────────────────────────────────────

from autoclave.state_machine.state_machine import StateMachine          # noqa: E402
from autoclave.core.runtime.status import EstadoAutoclave               # noqa: E402


def _sm():
    estado = EstadoAutoclave()
    es = MagicMock()
    cycle = MagicMock(); cycle.copia.return_value = cycle; cycle.get_param.return_value = None
    sm = StateMachine(io=MagicMock(), estado=estado, set_do=MagicMock(), cycle=cycle,
                      config=MagicMock(), estado_seguro=es)
    return sm, estado, es


def test_falla_espera_el_estado_seguro_antes_de_preparacion():
    sm, estado, es = _sm()
    estado.set_machine_state(GlobalState.FALLA)
    estado.set_flag("RESET_FALLA", True)
    es.activo = True
    sm.update()
    assert estado.get_machine_state() == GlobalState.FALLA
    assert estado.get_flag("RESET_FALLA") is True          # el reconocimiento queda
    es.update.assert_called()
    es.activo = False
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARACION


@pytest.mark.parametrize("resultado,destino", [("FALLO", GlobalState.FALLA),
                                               ("CANCELADO", GlobalState.PREPARADO)])
def test_fallo_y_cancelacion_inician_el_estado_seguro(resultado, destino):
    sm, estado, es = _sm()
    estado.set_machine_state(GlobalState.CICLO)
    sm.prev_state = GlobalState.CICLO
    sm.ciclo.run = MagicMock(return_value=resultado)
    sm.update()
    assert estado.get_machine_state() == destino
    es.iniciar.assert_called_once_with(sm.ciclo._protocolo)


def test_preparado_no_ventea_ni_habilita_con_estado_seguro_activo():
    sm, estado, es = _sm()
    es.activo = True
    sm.preparado.supervisor = MagicMock(return_value=True)
    sm.preparado.ejecutor = MagicMock()
    assert sm.preparado.run() is False
    sm.preparado.ejecutor.assert_not_called()


# ── Correcciones de la auditoría de temporización de T5 ────────────────────

def test_preparado_con_supervisor_fallido_y_estado_seguro_no_ventea():
    # TMG-01: las salidas seguras del supervisor ventean con la rápida
    sm, estado, es = _sm()
    es.activo = True
    sm.preparado.supervisor = MagicMock(return_value=False)
    sm.preparado._salidas_seguras_supervisor = MagicMock()
    assert sm.preparado.run() is False
    sm.preparado._salidas_seguras_supervisor.assert_not_called()
    sm.preparado.set_do.vapor_chaqueta_off.assert_called()


def test_confirmacion_durante_paro_se_descarta():
    # TMG-06
    flags = {"PARO_EMERGENCIA": True, "CICLO_CONFIRMADO": True, "RESET_FALLA": True}
    ciclo, _ = _ciclo(flags)
    ciclo._resultado_pendiente = CicloResultado.FALLO
    ciclo.estado.set_flag.side_effect = lambda f, v: flags.__setitem__(f, v)
    ciclo.run()
    assert flags["CICLO_CONFIRMADO"] is False and flags["RESET_FALLA"] is False


def test_al_reanudar_tras_una_pausa_se_reinician_pulsos_y_plazo():
    # TMG-02 / TMG-07
    estado = _estado()
    es, prot = _es(estado), _protocolo()
    es.iniciar(prot)
    es.update()
    prot.reanudar.assert_called_once()
    es.update()
    prot.reanudar.assert_called_once()             # solo al pasar de pausado a activo
    estado.flags["PARO_EMERGENCIA"] = True
    es.update()
    estado.flags["PARO_EMERGENCIA"] = False
    es.confirmar()
    es.update()
    assert prot.reanudar.call_count == 2


def test_error_del_estado_seguro_no_corta_el_estado():
    # TMG-04
    sm, estado, es = _sm()
    estado.set_machine_state(GlobalState.FALLA)
    es.update.side_effect = RuntimeError("falla")
    es.activo = False
    estado.set_flag("RESET_FALLA", True)
    sm.update()
    assert estado.get_machine_state() == GlobalState.PREPARACION


def test_estado_seguro_bloqueado_activa_cic10_y_lo_resuelve():
    # SAF-04
    estado = _estado()
    am = MagicMock()
    es = ProtocoloEstadoSeguro(estado, _Config(_CFG), programas_seguridad=lambda: [],
                               alarm_manager=am)
    prot = _protocolo()
    prot.bloqueado_motivo = "Sensor Principal sin lectura"
    es.iniciar(prot)
    es.update()
    am.activar.assert_called_once_with("CIC-10", motivo="Sensor Principal sin lectura")
    prot.bloqueado_motivo = None
    es.update()
    am.resolver.assert_called_with("CIC-10")


def test_estado_seguro_mantiene_el_drenaje():
    # SAF-07
    es, prot = _es(_estado()), _protocolo()
    es.mantener_drenaje = MagicMock()
    es.iniciar(prot)
    es.update()
    es.mantener_drenaje.assert_called_once()


def test_puerta_no_abre_con_estado_seguro_activo():
    # SAF-03
    from autoclave.services.domain.puertas.ser_puertas import ServicioPuertas
    puerta = MagicMock(); puerta.name = "Puerta 1"
    servicio = ServicioPuertas([puerta], _estado(pres=101.3, temp=30.0), None, _Config(_CFG),
                               estado_seguro_activo=lambda: True)
    ok, motivo = servicio._can_open_physical("Puerta 1")
    assert ok is False and "estado seguro" in motivo


def test_paro_domina_sobre_la_cancelacion():
    # SAF-05
    flags = {"PARO_EMERGENCIA": True, "CICLO_CANCELADO": True}
    ciclo, _ = _ciclo(flags)
    ciclo.run()
    assert ciclo.estado.fase_ciclo == "EMERGENCIA"
    ciclo._protocolo.ejecutar.assert_called_once_with(abrir_valvulas=False)

# S2b / D8-2.11 (tanda 8, Q1-P1): si el módulo E/S no confirma el ALL_OFF al
# salir del modo prueba, se reintenta 3 veces (una por tick, con la máquina de
# estados todavía pausada). Si sigue sin confirmar, sale la alarma COM-04
# "Salidas sin confirmar" (bloquea el inicio) hasta que llegue una
# confirmación. Todo queda en la bitácora.

import pytest

from autoclave.state_machine.alarms.catalogo import CATALOGO, COM_04, Nivel
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_control_loop_test_mode import _make_control_loop, _run_one_tick


def _loop_con_bitacora():
    loop, sm, estado = _make_control_loop()
    eventos = []
    loop.al_evento_seguridad = lambda ev, det: eventos.append((ev, det))
    loop.link.puerto_presente.return_value = True
    loop.link.tomar_eventos.return_value = []
    loop.link.expansor_fuera_de_linea.return_value = False
    return loop, sm, estado, eventos


def _salir_sin_ack(loop):
    loop.enter_test_mode()
    loop.set_do.reset_all_outputs.reset_mock()
    loop.set_do.reset_all_outputs.return_value = False
    return loop.exit_test_mode()


def _activadas(loop):
    return [c.args[0] for c in loop.alarm_manager.activar.call_args_list]


def test_catalogo_com04_bloquea_el_inicio_y_se_despeja_solo():
    d = CATALOGO[COM_04]
    assert d.titulo == "Salidas sin confirmar"
    assert d.bloquea_inicio is True
    assert d.nivel is Nivel.ALARMA
    assert d.campos() == set()


def test_con_ack_al_primer_intento_no_hay_reintentos_ni_pausa():
    loop, sm, _, eventos = _loop_con_bitacora()
    loop.enter_test_mode()
    loop.set_do.reset_all_outputs.reset_mock()
    loop.set_do.reset_all_outputs.return_value = True

    assert loop.exit_test_mode() is True
    assert loop.salidas_sin_confirmar_pendiente is False
    _run_one_tick(loop)

    loop.set_do.reset_all_outputs.assert_called_once()
    sm.update.assert_called_once()
    assert COM_04 not in _activadas(loop)
    assert eventos == []


def test_sin_ack_reintenta_en_los_ticks_siguientes_con_la_maquina_pausada():
    loop, sm, _, eventos = _loop_con_bitacora()
    assert _salir_sin_ack(loop) is False
    assert loop.test_mode_active is False
    assert loop.salidas_sin_confirmar_pendiente is True

    _run_one_tick(loop)   # reintento 1 (falla)
    _run_one_tick(loop)   # reintento 2 (falla)

    assert loop.set_do.reset_all_outputs.call_count == 3
    sm.update.assert_not_called()          # la máquina sigue pausada
    assert COM_04 not in _activadas(loop)


def test_confirma_en_un_reintento_reanuda_y_lo_anota():
    loop, sm, _, eventos = _loop_con_bitacora()
    _salir_sin_ack(loop)
    loop.set_do.reset_all_outputs.side_effect = [False, True]

    _run_one_tick(loop)   # reintento 1: falla
    sm.update.assert_not_called()
    _run_one_tick(loop)   # reintento 2: confirma, y en el mismo tick reanuda

    assert loop.salidas_sin_confirmar_pendiente is False
    sm.update.assert_called_once()
    assert COM_04 not in _activadas(loop)
    assert eventos == [("salidas_confirmadas_tras_reintento", {"reintento": 2})]
    _run_one_tick(loop)
    assert loop.set_do.reset_all_outputs.call_count == 3   # no reintenta más


def test_tres_reintentos_fallidos_dan_la_alarma_reanudan_y_piden_handshake():
    loop, sm, _, eventos = _loop_con_bitacora()
    _salir_sin_ack(loop)

    for _ in range(3):
        _run_one_tick(loop)

    assert loop.set_do.reset_all_outputs.call_count == 4   # 1 + 3 reintentos
    assert _activadas(loop).count(COM_04) == 1
    assert loop.salidas_sin_confirmar_pendiente is False
    sm.update.assert_called_once()        # reanuda en el tick del último intento
    loop.link.solicitar_handshake.assert_called_once()
    assert eventos == [("salidas_sin_confirmar", {"reintentos": 3})]

    _run_one_tick(loop)
    assert loop.set_do.reset_all_outputs.call_count == 4
    assert _activadas(loop).count(COM_04) == 1


def _con_alarma(loop):
    _salir_sin_ack(loop)
    for _ in range(3):
        _run_one_tick(loop)
    assert COM_04 in _activadas(loop)


def test_alarma_se_despeja_con_el_handshake_siguiente():
    loop, _, _, eventos = _loop_con_bitacora()
    _con_alarma(loop)

    class _Ev:
        origen, alarm_id, motivo = "conectada", None, ""
    loop.link.tomar_eventos.return_value = [_Ev()]
    _run_one_tick(loop)

    loop.alarm_manager.resolver.assert_any_call(COM_04)
    assert eventos[-1] == ("salidas_confirmadas", {"origen": "handshake"})


def test_alarma_se_despeja_con_un_all_off_confirmado_al_entrar_al_modo_prueba():
    loop, _, _, eventos = _loop_con_bitacora()
    _con_alarma(loop)
    loop.set_do.reset_all_outputs.return_value = True

    ok, _ = loop.enter_test_mode()

    assert ok
    loop.alarm_manager.resolver.assert_any_call(COM_04)
    assert eventos[-1] == ("salidas_confirmadas", {"origen": "modo_prueba"})


def test_alarma_no_se_despeja_si_el_nuevo_all_off_tampoco_confirma():
    loop, _, _, _ = _loop_con_bitacora()
    _con_alarma(loop)
    loop.set_do.reset_all_outputs.return_value = False

    loop.enter_test_mode()

    assert all(c.args[0] != COM_04 for c in loop.alarm_manager.resolver.call_args_list)


def test_entrar_al_modo_prueba_con_reintentos_pendientes_los_cancela():
    loop, sm, _, _ = _loop_con_bitacora()
    _salir_sin_ack(loop)
    loop.set_do.reset_all_outputs.return_value = True

    loop.enter_test_mode()

    assert loop.salidas_sin_confirmar_pendiente is False
    assert loop.test_mode_active is True


def test_paro_durante_los_reintentos_no_deja_la_maquina_pausada():
    loop, sm, estado, _ = _loop_con_bitacora()
    _salir_sin_ack(loop)
    estado.sensores_di["paro_emergencia"] = 0
    estado.set_flag("PARO_EMERGENCIA", True)
    loop.paro_emergencia.update = lambda *_a, **_k: None   # mantener el flag

    _run_one_tick(loop)

    sm.update.assert_called_once()   # la máquina aplica su protocolo de paro


def test_sin_handshake_si_el_equipo_esta_en_ciclo():
    loop, _, estado, _ = _loop_con_bitacora()
    _salir_sin_ack(loop)
    estado.set_machine_state(GlobalState.CICLO)   # no debería pasar; falla segura
    for _ in range(3):
        _run_one_tick(loop)
    loop.link.solicitar_handshake.assert_not_called()

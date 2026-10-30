# tests/test_e1_paro_emergencia_nc.py
#
# E1-5 (D-16, PF-21, HAZ-FC-04): paro de emergencia con lógica de seguridad
# intrínseca. Entrada en 0 = paro; sin datos = paro; entrada en 1 = sin paro.

from unittest.mock import MagicMock, patch

import pytest

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.devices.paro_emergencia.paro_emergencia import AVISO_CABLEADO_NC, EmergencyStop
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states.preparacion import preparacion_state


# ---------------------------------------------------------------------------
# EmergencyStop
# ---------------------------------------------------------------------------

def test_sin_datos_al_construir_hay_paro():
    estado = EstadoAutoclave()
    paro = EmergencyStop(estado)
    assert paro.active is True
    assert estado.get_flag("PARO_EMERGENCIA") is True


@pytest.mark.parametrize("valor,esperado", [(0, True), (1, False), (None, True),
                                            (False, True), (True, False)])
def test_interpretacion_invertida(valor, esperado):
    estado = EstadoAutoclave()
    paro = EmergencyStop(estado)
    paro.update(valor)
    assert paro.active is esperado
    assert estado.get_flag("PARO_EMERGENCIA") is esperado


def test_liberar_y_volver_a_pulsar():
    estado = EstadoAutoclave()
    paro = EmergencyStop(estado)
    paro.update(1)
    assert paro.falling_edge()
    paro.update(0)
    assert paro.rising_edge()
    assert estado.get_flag("PARO_EMERGENCIA") is True


# ---------------------------------------------------------------------------
# ControlLoop
# ---------------------------------------------------------------------------

def _loop(estado):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cm = MagicMock()
    cm.get_selected_cycle.return_value = MagicMock()
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        return ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=estado, link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=MagicMock(), cycle_manager=cm,
                           config_manager=MagicMock())


@pytest.mark.parametrize("di,esperado", [(0, True), (1, False)])
def test_control_loop_lee_el_di_invertido(di, esperado):
    estado = EstadoAutoclave()
    loop = _loop(estado)
    loop.units.get_all.return_value = {}
    estado.sensores_di["paro_emergencia"] = di
    estado.sensores_di["suministro_electrico"] = 1
    loop.link.is_connected.return_value = True
    loop.link.edad_ultima_di.return_value = 0.0     # trama DI vigente (A-3)
    loop._tick()
    assert estado.get_flag("PARO_EMERGENCIA") is esperado


def test_control_loop_sin_entrada_en_la_trama_es_paro():
    estado = EstadoAutoclave()
    del estado.sensores_di["paro_emergencia"]
    loop = _loop(estado)
    loop.units.get_all.return_value = {}
    loop.link.is_connected.return_value = True
    loop._tick()
    assert estado.get_flag("PARO_EMERGENCIA") is True


def test_control_loop_antes_de_la_primera_trama_es_paro():
    estado = EstadoAutoclave()
    loop = _loop(estado)
    loop.link.is_connected.return_value = False
    loop._tick()
    assert estado.get_flag("PARO_EMERGENCIA") is True


def test_control_loop_entra_a_modo_prueba_solo_sin_paro():
    estado = EstadoAutoclave()
    loop = _loop(estado)
    assert loop.enter_test_mode()[0] is False      # sin datos = paro
    loop.units.get_all.return_value = {}
    estado.sensores_di["paro_emergencia"] = 1
    estado.sensores_di["suministro_electrico"] = 1
    loop.link.is_connected.return_value = True
    loop.link.edad_ultima_di.return_value = 0.0     # trama DI vigente (A-3)
    loop._tick()
    assert loop.enter_test_mode()[0] is True


# ---------------------------------------------------------------------------
# PREPARACION usa el flag, no el DI crudo
# ---------------------------------------------------------------------------

def _preparacion(flag_paro, di_paro):
    estado = MagicMock()
    estado.sensores_di = {"paro_emergencia": di_paro}
    estado.get_flag.side_effect = lambda f: flag_paro if f in ("PARO_EMERGENCIA", "PARO_REAL") else False  # U4
    p = preparacion_state(AlarmManager(), estado, MagicMock(), MagicMock(), MagicMock())
    p.supervisor = MagicMock(return_value=False)
    # supervisor en False lleva a salidas seguras (decisión P4); aquí solo
    # importa el flag del paro
    p._salidas_seguras_supervisor = MagicMock()
    return p


def test_preparacion_paro_por_flag_aunque_el_di_valga_1():
    p = _preparacion(flag_paro=True, di_paro=1)
    assert p.run() is False
    p.set_do.apagar_por_paro.assert_called_once()      # ALL_OFF limitado (A-7)
    [alarma] = p.alarm_manager.activas()
    assert alarma.codigo == "SIS-01"
    assert AVISO_CABLEADO_NC in alarma.descripcion
    p.supervisor.assert_not_called()


def test_preparacion_sin_paro_por_flag_aunque_el_di_valga_0():
    p = _preparacion(flag_paro=False, di_paro=0)
    p.run()
    p.set_do.apagar_por_paro.assert_not_called()
    assert p.alarm_manager.activas() == []
    p.supervisor.assert_called_once()


# ---------------------------------------------------------------------------
# Mensaje de la alarma en los demás estados
# ---------------------------------------------------------------------------

def test_mensaje_de_alarma_menciona_cableado_nc_en_todos_los_estados():
    from autoclave.state_machine.states.preparado import preparado_state
    from autoclave.state_machine.states.falla import FallaState
    from autoclave.state_machine.states.ciclo import CicloState

    def _estado():
        e = MagicMock()
        e.get_flag.side_effect = lambda f: f in ("PARO_EMERGENCIA", "PARO_REAL")  # U4: paro real
        return e

    descripciones = []
    for construir in (
        lambda am: preparado_state(am, _estado(), MagicMock(), MagicMock(), MagicMock()).run(),
        lambda am: FallaState(_estado(), MagicMock(), am).run(),
    ):
        am = AlarmManager()
        construir(am)
        descripciones.append(am.activas()[0].descripcion)

    cycle = MagicMock()
    cycle.copia.return_value = cycle
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    estado = _estado()
    estado.sensores_pres = {}
    estado.sensores_temp = {}
    am = AlarmManager()
    ciclo = CicloState(estado, MagicMock(), cycle, config, am)
    ciclo.reset()
    ciclo.run()
    descripciones.append(am.activas()[0].descripcion)

    for d in descripciones:
        assert AVISO_CABLEADO_NC in d

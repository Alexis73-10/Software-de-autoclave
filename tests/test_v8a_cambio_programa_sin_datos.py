"""V8a (tanda 8), D8-5.1, decisión de Cristian de las 12:08: el programa se
puede cambiar AUNQUE la tarjeta no esté conectada ni haya datos vigentes.
Seleccionar un programa no acciona nada; el inicio del ciclo sigue exigiendo
datos, sensores y todas las condiciones actuales. Se conservan los bloqueos
con ciclo en curso, paro (REAL), estado seguro y modo prueba; en FALLA se
permite (decisión del 19-oct)."""

from unittest.mock import MagicMock, patch

import pytest

from autoclave.state_machine.machine.enum_global import GlobalState
from tests.test_control_loop_set_active_cycle import _FakeEstado, _make_control_loop


def _loop(estado_maquina=GlobalState.PREPARACION):
    estado = _FakeEstado()
    estado.set_machine_state(estado_maquina)
    loop, _, inicial, _ = _make_control_loop(estado)
    return loop, inicial, estado


@pytest.mark.parametrize("estado_maquina", [GlobalState.PREPARACION, GlobalState.PREPARADO,
                                            GlobalState.FALLA])
@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_sin_datos_de_la_tarjeta_se_permite(_sm, estado_maquina):
    """Tarjeta conectada sin tramas válidas: PARO_EMERGENCIA sin PARO_REAL (U4)."""
    loop, _, estado = _loop(estado_maquina)
    estado.set_flag("PARO_EMERGENCIA", True)
    estado.set_flag("PARO_REAL", False)
    nuevo = MagicMock()
    assert loop.set_active_cycle(nuevo) == (True, "")
    assert loop.cycle is nuevo


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_sin_tarjeta_conectada_se_permite(_sm):
    """Enlace caído (desconectado): tampoco hay PARO_REAL."""
    loop, _, estado = _loop()
    loop._desconectado_desde = 1.0
    estado.set_flag("PARO_EMERGENCIA", True)
    estado.set_flag("PARO_REAL", False)
    assert loop.desconectado is True
    assert loop.set_active_cycle(MagicMock())[0] is True


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_paro_real_sigue_bloqueando(_sm):
    loop, inicial, estado = _loop()
    estado.set_flag("PARO_EMERGENCIA", True)
    estado.set_flag("PARO_REAL", True)
    ok, motivo = loop.set_active_cycle(MagicMock())
    assert ok is False and "paro" in motivo.lower() and loop.cycle is inicial


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_ciclo_en_curso_sigue_bloqueando_aun_sin_datos(_sm):
    loop, inicial, estado = _loop(GlobalState.CICLO)
    estado.set_flag("PARO_EMERGENCIA", True)
    assert loop.set_active_cycle(MagicMock())[0] is False and loop.cycle is inicial


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_modo_prueba_y_estado_seguro_siguen_bloqueando_sin_datos(_sm):
    loop, inicial, estado = _loop()
    estado.set_flag("PARO_EMERGENCIA", True)
    loop._test_mode.set()
    assert loop.set_active_cycle(MagicMock())[0] is False
    loop._test_mode.clear()
    loop.estado_seguro._protocolo = MagicMock()
    assert loop.set_active_cycle(MagicMock())[0] is False and loop.cycle is inicial


# ── Reproducción con el ControlLoop real (D8-5.1: "con tarjeta simulada y sin
# tarjeta"): el enlace es un doble que informa conexión y edad de la trama DI;
# el tick real publica PARO_EMERGENCIA / PARO_REAL (U4) como en el equipo. ──

def _loop_real():
    from autoclave.core.runtime.status import EstadoAutoclave
    from autoclave.services.domain.loop.control_loop import ControlLoop
    estado = EstadoAutoclave()
    cm = MagicMock()
    cm.get_selected_cycle.return_value = MagicMock()
    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=estado, link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=MagicMock(), cycle_manager=cm,
                           config_manager=MagicMock(), profile=None)
    loop.units.get_all.return_value = {}
    estado.sensores_di["paro_emergencia"] = 1
    estado.sensores_di["suministro_electrico"] = 1
    estado.set_machine_state(GlobalState.PREPARADO)
    return loop, estado


@pytest.mark.parametrize("caso", ["tarjeta_simulada_con_datos", "tarjeta_simulada_sin_tramas_validas",
                                  "sin_tarjeta"])
@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_reproduccion_cambio_con_y_sin_tarjeta(_sm, caso):
    loop, estado = _loop_real()
    loop.link.is_connected.return_value = caso != "sin_tarjeta"
    loop.link.edad_ultima_di.return_value = 0.1 if caso == "tarjeta_simulada_con_datos" else None
    loop._tick()
    assert estado.get_flag("PARO_REAL") is False
    assert estado.get_flag("PARO_EMERGENCIA") is (caso != "tarjeta_simulada_con_datos")
    nuevo = MagicMock()
    assert loop.set_active_cycle(nuevo) == (True, ""), caso
    assert loop.cycle is nuevo


@patch("autoclave.services.domain.loop.control_loop.StateMachine")
def test_reproduccion_paro_real_leido_bloquea(_sm):
    loop, estado = _loop_real()
    loop.link.is_connected.return_value = True
    loop.link.edad_ultima_di.return_value = 0.1
    estado.sensores_di["paro_emergencia"] = 0          # NC abierto: paro pulsado
    loop._tick()                                       # TMG-04 de U4: el primer 0 no cuenta
    loop._tick()
    assert estado.get_flag("PARO_REAL") is True
    ok, motivo = loop.set_active_cycle(MagicMock())
    assert ok is False and "paro" in motivo.lower()

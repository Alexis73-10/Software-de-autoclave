from unittest.mock import MagicMock
from tests.alarmas_helpers import codigos_activados, codigos_resueltos, ultima_activacion
from autoclave.state_machine.alarms.catalogo import CATALOGO, SUM_06
from autoclave.state_machine.states.ciclo import CicloState


def _make_ciclo(vapor=1, pres_chaqueta=300.0):
    estado = MagicMock()
    estado.sensores_pres = {"pres_chaqueta": pres_chaqueta}
    estado.sensores_di = {"vapor_suministro": vapor}
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    alarm_manager = MagicMock()
    ciclo = CicloState(estado, set_do, cycle, config, alarm_manager)
    return ciclo, set_do, alarm_manager


def test_sin_vapor_apaga_valvula_y_reporta_alarma_no_bloqueante():
    ciclo, set_do, alarm_manager = _make_ciclo(vapor=0)
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()
    assert ultima_activacion(alarm_manager)[0] == SUM_06
    assert CATALOGO[SUM_06].bloquea_inicio is False


def test_con_vapor_limpia_alarma():
    ciclo, set_do, alarm_manager = _make_ciclo(vapor=1, pres_chaqueta=300.0)
    ciclo._mantener_chaqueta()
    assert SUM_06 in codigos_resueltos(alarm_manager)

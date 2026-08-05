from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _make_ciclo_en_espera(resultado_pendiente, temp_drenaje=45.0, temp_segura=40.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_drenaje": temp_drenaje}
    estado.sensores_pres = {}
    estado.get_flag.return_value = False
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = temp_segura
    alarm_manager = MagicMock()
    ciclo = CicloState(estado, set_do, cycle, config, alarm_manager)
    ciclo._resultado_pendiente = resultado_pendiente
    return ciclo, set_do, alarm_manager


def test_drenaje_corre_durante_espera_completado():
    ciclo, set_do, alarm_manager = _make_ciclo_en_espera(CicloResultado.COMPLETADO)
    ciclo.run()
    ciclo.run()
    ciclo.run()
    set_do.agua_intercambiador_on.assert_called_once()


def test_drenaje_corre_durante_espera_fallo():
    ciclo, set_do, alarm_manager = _make_ciclo_en_espera(CicloResultado.FALLO)
    ciclo.run()
    ciclo.run()
    ciclo.run()
    set_do.agua_intercambiador_on.assert_called_once()


def test_drenaje_corre_durante_espera_cancelado():
    ciclo, set_do, alarm_manager = _make_ciclo_en_espera(CicloResultado.CANCELADO)
    ciclo.run()
    ciclo.run()
    ciclo.run()
    set_do.agua_intercambiador_on.assert_called_once()

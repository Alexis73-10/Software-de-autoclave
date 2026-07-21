from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _make_ciclo():
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 100.0}
    estado.sensores_pres = {"pres_camara": 200.0}
    estado.get_flag.return_value = False

    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    alarms = MagicMock()

    ciclo = CicloState(estado, set_do, cycle, config, alarms)
    ciclo.reset()
    return ciclo, estado


def test_abortar_por_desconexion_reporta_alarma():
    ciclo, estado = _make_ciclo()
    ciclo.abortar_por_desconexion()

    ciclo.alarm_manager.report.assert_called_once()
    alarma = ciclo.alarm_manager.report.call_args[0][0]
    assert alarma.id == "FALLO_CONEXION"


def test_abortar_por_desconexion_ejecuta_protocolo():
    ciclo, estado = _make_ciclo()
    ciclo._protocolo = MagicMock()

    ciclo.abortar_por_desconexion()

    ciclo._protocolo.ejecutar.assert_called_once()


def test_abortar_por_desconexion_deja_fallo_pendiente():
    ciclo, estado = _make_ciclo()
    ciclo.abortar_por_desconexion()

    estado.get_flag.side_effect = lambda f: f == "CICLO_CONFIRMADO"
    resultado = ciclo.run()

    assert resultado == CicloResultado.FALLO


def test_abortar_por_desconexion_no_duplica_si_ya_hay_resultado_pendiente():
    ciclo, estado = _make_ciclo()
    ciclo.abortar_por_desconexion()
    ciclo.abortar_por_desconexion()

    ciclo.alarm_manager.report.assert_called_once()

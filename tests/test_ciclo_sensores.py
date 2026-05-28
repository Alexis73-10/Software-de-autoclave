# tests/test_ciclo_sensores.py
from unittest.mock import MagicMock, patch
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _make_ciclo():
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 100.0}
    estado.sensores_pres = {"pres_camara": 200.0, "pres_chaqueta": 300.0}
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                          "vapor_suministro": 1}
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


def test_fallo_si_temp_camara_ausente():
    ciclo, estado = _make_ciclo()
    estado.sensores_temp["temp_camara"] = None

    result = ciclo.run()

    assert result == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "SENSOR_AUSENTE"
    ciclo.alarm_manager.report.assert_called_once()


def test_fallo_si_pres_camara_ausente():
    ciclo, estado = _make_ciclo()
    estado.sensores_pres["pres_camara"] = None

    result = ciclo.run()

    assert result == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "SENSOR_AUSENTE"


def test_no_fallo_si_sensores_presentes():
    ciclo, estado = _make_ciclo()
    # Sensores OK, puertas OK → debe llegar a ejecutar la primera fase
    result = ciclo.run()
    # No debe ser SENSOR_AUSENTE
    assert estado.fase_ciclo != "SENSOR_AUSENTE"

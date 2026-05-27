from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _make_ciclo(fallo_suministro=False):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 100.0}
    estado.sensores_pres = {
        "pres_camara": 200.0, "pres_chaqueta": 300.0,
        "pres_empaque_1": 300.0, "pres_empaque_2": 300.0,
    }
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                          "vapor_suministro": 1}

    def flag_side(flag):
        if flag == "FALLO_SUMINISTRO_ELECTRICO":
            return fallo_suministro
        return False

    estado.get_flag.side_effect = flag_side

    set_do = MagicMock()
    cycle  = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    alarms = MagicMock()

    ciclo = CicloState(estado, set_do, cycle, config, alarms)
    ciclo.reset()
    return ciclo, estado


def test_fallo_suministro_aborta_ciclo():
    ciclo, estado = _make_ciclo(fallo_suministro=True)
    result = ciclo.run()
    assert result == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "FALLO_SUMINISTRO"


def test_fallo_suministro_reporta_alarma_emergencia():
    ciclo, estado = _make_ciclo(fallo_suministro=True)
    ciclo.run()
    ciclo.alarm_manager.report.assert_called_once()
    alarma = ciclo.alarm_manager.report.call_args[0][0]
    assert alarma.id == "FALLO_SUMINISTRO_ELECTRICO"


def test_fallo_suministro_ejecuta_protocolo():
    ciclo, estado = _make_ciclo(fallo_suministro=True)
    ciclo._protocolo = MagicMock()
    ciclo.run()
    ciclo._protocolo.ejecutar.assert_called_once()


def test_sin_fallo_suministro_ciclo_continua():
    ciclo, estado = _make_ciclo(fallo_suministro=False)
    result = ciclo.run()
    assert estado.fase_ciclo != "FALLO_SUMINISTRO"

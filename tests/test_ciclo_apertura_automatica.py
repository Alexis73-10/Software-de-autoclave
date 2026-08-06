from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _make_ciclo(door_service=None, apertura_automatica=False,
                 tiempo_espera=60, temp_max=80.0, timeout_min=30,
                 temp_camara=25.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": temp_camara}
    estado.sensores_pres = {"pres_camara": 101.3}
    estado.get_flag.return_value = False

    set_do = MagicMock()
    cycle = MagicMock()

    def _get_param(seccion, nombre, default=None):
        valores = {
            ("finalizacion", "apertura_automatica"): apertura_automatica,
            ("finalizacion", "tiempo_espera_apertura"): tiempo_espera,
            ("finalizacion", "temp_max_apertura"): temp_max,
            ("finalizacion", "timeout_temperatura"): timeout_min,
        }
        return valores.get((seccion, nombre), default)

    cycle.get_param.side_effect = _get_param
    config = MagicMock()
    config.get.return_value = None
    alarm_manager = MagicMock()

    ciclo = CicloState(estado, set_do, cycle, config, alarm_manager,
                        cap=None, door_service=door_service)
    ciclo.reset()
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    return ciclo, estado, set_do, alarm_manager


def test_door_service_none_por_defecto():
    ciclo, *_ = _make_ciclo()
    assert ciclo.door_service is None


def test_door_service_se_guarda_si_se_pasa():
    door_service = MagicMock()
    ciclo, *_ = _make_ciclo(door_service=door_service)
    assert ciclo.door_service is door_service


def test_door_service_none_no_rompe_run(monkeypatch):
    ciclo, *_ = _make_ciclo(door_service=None, apertura_automatica=True)
    resultado = ciclo.run()
    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION

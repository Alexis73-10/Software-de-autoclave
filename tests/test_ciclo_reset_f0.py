# tests/test_ciclo_reset_f0.py
from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState


def test_reset_pone_f0_acumulado_en_cero():
    estado = MagicMock()
    estado.f0_acumulado = 7.5  # letalidad acumulada de un ciclo anterior
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    alarms = MagicMock()

    ciclo = CicloState(estado, set_do, cycle, config, alarms)
    ciclo.reset()

    assert estado.f0_acumulado == 0.0

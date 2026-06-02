from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.prevacio import PrevacioFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(has_vacuum: bool):
    estado = MagicMock()
    set_do = MagicMock()
    cycle  = MagicMock()
    cycle.get_param.return_value = 0  # todos los conteos en 0
    config = MagicMock()
    alarms = MagicMock()
    cap    = MagicMock()
    cap.has_vacuum = has_vacuum

    fase = PrevacioFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, set_do


def test_prevacio_skip_sin_vacuum():
    fase, set_do = _make_fase(has_vacuum=False)
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.bomba_vacio_on.assert_not_called()
    set_do.vacio_camara_on.assert_not_called()


def test_prevacio_skip_sin_vacuum_retorna_en_primer_tick():
    fase, _ = _make_fase(has_vacuum=False)
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_prevacio_con_vacuum_y_pulsos_cero_igual_salta():
    fase, set_do = _make_fase(has_vacuum=True)
    result = fase.update()
    # Todos los conteos en 0 → COMPLETADO aunque tenga vacuum
    assert result == FaseResult.COMPLETADO

# tests/test_precalentamiento_fase.py
from unittest.mock import MagicMock, patch

from autoclave.state_machine.cycle_phases.precalentamiento import PrecalentamientoFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(tiempo_min=5, presion_obj=200.0, timeout_min=10):
    """Construye una PrecalentamientoFase con mocks configurados."""
    estado = MagicMock()
    estado.sensores_pres = {"pres_chaqueta": 0.0}
    estado.fase_en_sostenimiento = False

    set_do = MagicMock()

    cycle = MagicMock()
    def get_param(seccion, param, default=None):
        valores = {
            "tiempo_precalentamiento": tiempo_min,
            "presion_precalentamiento": presion_obj,
            "timeout_precalentamiento": timeout_min,
        }
        return valores.get(param, default)
    cycle.get_param.side_effect = get_param

    config  = MagicMock()
    alarms  = MagicMock()

    fase = PrecalentamientoFase(estado, set_do, cycle, config, alarms)
    fase.reset()
    return fase, estado, set_do


def test_skip_cuando_tiempo_es_cero():
    fase, estado, set_do = _make_fase(tiempo_min=0)
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_not_called()


def test_aproximacion_valvula_on_y_en_curso():
    fase, estado, set_do = _make_fase(tiempo_min=1, presion_obj=200.0)
    estado.sensores_pres["pres_chaqueta"] = 100.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_chaqueta_off.assert_not_called()


def test_sostenimiento_arranca_al_alcanzar_presion():
    fase, estado, set_do = _make_fase(tiempo_min=1, presion_obj=200.0)
    estado.sensores_pres["pres_chaqueta"] = 200.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._timer_sostenimiento is not None
    assert estado.fase_en_sostenimiento is True


def test_completado_tras_sostenimiento():
    fase, estado, set_do = _make_fase(tiempo_min=1, presion_obj=200.0)
    estado.sensores_pres["pres_chaqueta"] = 250.0

    fase.update()
    fase._timer_sostenimiento -= 70

    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_chaqueta_off.assert_called()
    assert estado.fase_en_sostenimiento is False


def test_fallo_por_timeout():
    fase, estado, set_do = _make_fase(tiempo_min=1, presion_obj=200.0, timeout_min=1)
    estado.sensores_pres["pres_chaqueta"] = 50.0

    fase.update()
    fase._timer_timeout_fin -= 100

    result = fase.update()
    assert result == FaseResult.FALLO
    set_do.vapor_chaqueta_off.assert_called()


def test_bang_bang_durante_sostenimiento():
    fase, estado, set_do = _make_fase(tiempo_min=5, presion_obj=200.0)

    estado.sensores_pres["pres_chaqueta"] = 210.0
    fase.update()
    assert estado.fase_en_sostenimiento is True
    timer_original = fase._timer_sostenimiento

    set_do.reset_mock()
    estado.sensores_pres["pres_chaqueta"] = 150.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_chaqueta_on.assert_called()
    assert fase._timer_sostenimiento == timer_original


def test_valvula_cierra_cuando_presion_ok_en_sostenimiento():
    fase, estado, set_do = _make_fase(tiempo_min=5, presion_obj=200.0)

    estado.sensores_pres["pres_chaqueta"] = 210.0
    fase.update()

    set_do.reset_mock()
    estado.sensores_pres["pres_chaqueta"] = 205.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()

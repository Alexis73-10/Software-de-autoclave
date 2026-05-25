# tests/test_purga_fase.py
from unittest.mock import MagicMock
import pytest

from autoclave.state_machine.cycle_phases.purga import PurgaFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(tiempo_min=5):
    """Construye una PurgaFase con mocks configurados."""
    estado = MagicMock()
    set_do = MagicMock()

    cycle = MagicMock()
    def get_param(seccion, param, default=None):
        return {"tiempo_purga": tiempo_min}.get(param, default)
    cycle.get_param.side_effect = get_param

    config = MagicMock()
    alarms = MagicMock()

    fase = PurgaFase(estado, set_do, cycle, config, alarms)
    fase.reset()
    return fase, estado, set_do


# ──────────────────────────────────────────────────────────────────────────────
# 1. Skip cuando tiempo == 0
# ──────────────────────────────────────────────────────────────────────────────

def test_skip_cuando_tiempo_es_cero():
    fase, _, set_do = _make_fase(tiempo_min=0)
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_on.assert_not_called()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.vapor_camara_off.assert_not_called()
    set_do.descompresion_rapida_off.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Primer update: abre ambas válvulas y retorna EN_CURSO
# ──────────────────────────────────────────────────────────────────────────────

def test_abre_ambas_valvulas_en_primer_update():
    fase, _, set_do = _make_fase(tiempo_min=5)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Updates sucesivos: no reabre válvulas mientras el tiempo no se cumple
# ──────────────────────────────────────────────────────────────────────────────

def test_en_curso_y_no_reabre_valvulas():
    fase, _, set_do = _make_fase(tiempo_min=5)
    fase.update()         # inicializa, abre válvulas
    set_do.reset_mock()   # limpia contadores
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_not_called()
    set_do.descompresion_rapida_on.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 4. Tiempo cumplido → COMPLETADO y ambas válvulas cerradas
# ──────────────────────────────────────────────────────────────────────────────

def test_completado_tras_tiempo_cumplido():
    fase, _, set_do = _make_fase(tiempo_min=1)   # 60 s
    fase.update()                                 # inicializa timer
    fase._timer_fin -= 70                         # 70 s > 60 s → expirado
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called_once()
    set_do.descompresion_rapida_off.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# 5. reset() limpia el estado interno
# ──────────────────────────────────────────────────────────────────────────────

def test_reset_limpia_estado():
    fase, _, set_do = _make_fase(tiempo_min=1)
    fase.update()                        # inicializa: _inicializado=True, _timer_fin=<valor>
    fase.reset()
    assert fase._inicializado == False
    assert fase._timer_fin is None

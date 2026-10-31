# S2b / D8-2.12 (tanda 8, Q1-P2): durante la tolerancia por DI vencida se
# pausan las ventanas de estabilidad (sostenimiento / hold) de todas las fases;
# los timeouts de fase siguen corriendo (son límites de seguridad).

import math
from unittest.mock import MagicMock

import pytest

from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase
from autoclave.state_machine.cycle_phases.descompresion import DescompresionFase
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from autoclave.state_machine.cycle_phases.precalentamiento import PrecalentamientoFase
from autoclave.state_machine.cycle_phases.prevacio import PrevacioFase
from autoclave.state_machine.cycle_phases.secado import SecadoFase


def _fase(cls):
    return cls(MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())


@pytest.mark.parametrize("cls, ventana, timeouts", [
    (PrecalentamientoFase, "_timer_sostenimiento", ["_timer_timeout_fin"]),
    (PrevacioFase, "_hold_inicio", ["_timeout_bajo_fin", "_timeout_alto_fin"]),
    (CalentamientoFase, "_timer_sostenido_desde", ["_timer_timeout_fin"]),
    (SecadoFase, "_timer_fin", ["_limite_vacio", "_timeout_pulso_fin"]),
])
def test_corre_la_ventana_y_no_los_timeouts(cls, ventana, timeouts):
    f = _fase(cls)
    setattr(f, ventana, 1000.0)
    for t in timeouts:
        setattr(f, t, 2000.0)

    f.pausar_ventanas_estabilidad(3.5)

    assert getattr(f, ventana) == 1003.5
    for t in timeouts:
        assert getattr(f, t) == 2000.0


@pytest.mark.parametrize("cls", [PrecalentamientoFase, PrevacioFase, CalentamientoFase,
                                 SecadoFase, DescompresionFase, EsterilizacionFase])
def test_sin_ventana_abierta_no_hace_nada(cls):
    f = _fase(cls)
    f.reset()
    antes = dict(vars(f))
    f.pausar_ventanas_estabilidad(3.0)
    assert vars(f) == antes


@pytest.mark.parametrize("segundos", [0, -1.0, math.nan, math.inf, None, True, "3"])
def test_segundos_invalidos_no_corren_nada(segundos):
    f = _fase(CalentamientoFase)
    f._timer_sostenido_desde = 1000.0
    f.pausar_ventanas_estabilidad(segundos)
    assert f._timer_sostenido_desde == 1000.0


def test_descompresion_y_esterilizacion_no_tocan_sus_timeouts():
    d = _fase(DescompresionFase)
    d._t_timeout, d._t_inicio = 5000.0, 100.0
    d.pausar_ventanas_estabilidad(4.0)
    assert (d._t_timeout, d._t_inicio) == (5000.0, 100.0)

    e = _fase(EsterilizacionFase)
    e._timer_timeout_max = 7000.0
    e.pausar_ventanas_estabilidad(4.0)
    assert e._timer_timeout_max == 7000.0


def test_ciclo_aplica_la_pausa_a_la_fase_en_curso(monkeypatch):
    from autoclave.state_machine.states import ciclo as mod
    c = mod.CicloState.__new__(mod.CicloState)
    c.estado = MagicMock()
    c.estado.sin_datos_modulo_es_s = 0.0
    fase = MagicMock()
    c._fases = [fase]
    c._fase_idx = 0
    c._pausa_sin_datos_desde = 100.0
    c.cycle = MagicMock()
    monkeypatch.setattr(mod.time, "monotonic", lambda: 103.0)
    monkeypatch.setattr(c, "_fase_actual_legible", lambda: "Calentamiento", raising=False)

    c._cerrar_pausa_sin_datos()

    fase.pausar_ventanas_estabilidad.assert_called_once_with(3.0)
    fase.pausar_exposicion.assert_called_once_with(3.0)


def test_calentamiento_ventana_no_vence_por_los_segundos_sin_datos(monkeypatch):
    """La ventana de estabilidad de CALENTAMIENTO exige su tiempo con datos."""
    from autoclave.state_machine.cycle_phases import calentamiento as mod
    f = _fase(CalentamientoFase)
    reloj = [1000.0]
    monkeypatch.setattr(mod.time, "monotonic", lambda: reloj[0])
    f._timer_sostenido_desde = 1000.0
    reloj[0] = 1004.0           # 4 s sin datos (la fase no corrió)
    f.pausar_ventanas_estabilidad(4.0)
    assert reloj[0] - f._timer_sostenido_desde == 0.0

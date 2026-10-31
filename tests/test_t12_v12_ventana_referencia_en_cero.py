"""Tanda 12, V12 (SAF-08): en la ventana de CALENTAMIENTO una Referencia que
lee 0 (o no finita) es "sin lectura", como en ESTERILIZACION y en CicloState:
no bloquea la ventana (el ciclo queda NO CONFORME por CicloState)."""
import math

import pytest

from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests.test_t12_c13_7b_ventana_referencia_sin_lectura import _UNA_REF, _ventana


@pytest.mark.parametrize("valor", [0, 0.0, math.nan])
def test_referencia_sin_senal_no_bloquea_la_ventana(valor):
    fase = _ventana(_UNA_REF, {"temp_ref": valor})
    assert fase._timer_sostenido_desde is not None
    fase._timer_sostenido_desde -= 6
    assert fase.update() == FaseResult.COMPLETADO


def test_referencia_fria_que_lee_si_bloquea():
    fase = _ventana(_UNA_REF, {"temp_ref": 120.0})
    assert fase._timer_sostenido_desde is None

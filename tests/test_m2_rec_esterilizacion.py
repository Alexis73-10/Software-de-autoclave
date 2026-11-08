"""M2-REC-01 (7-nov, decisión de Cristian, opción 1) quedó SUPERADO en la
tanda 33 por CAS-02: en ESTERILIZACION, modo chaqueta, vapor_chaqueta la decide
la cascada (cascada_chaqueta.py) y el corte A14-M2 y su exención bajo la banda
ya no rigen en esta fase (docs/mis_plans/planeacion_control_cascada_chaqueta.md
§2.3). Las pruebas de la exención y de la planta se retiraron; la cascada con
la fase real y la planta simulada se prueban en
tests/test_t33_cas02_esterilizacion.py. Aquí queda la garantía de que la
exención no vuelve y de que el modo cámara no cambia."""

import pytest

from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import corte_chaqueta_consigna as ccc
from autoclave.state_machine.cycle_phases import esterilizacion as est
from tests.helpers import t12_e12_apoyo as ap

pytestmark = pytest.mark.req("M2-REC-01")

T_EST = 134.0
P_SP = p_saturacion_kpa(134.6)          # brecha 0,3 + histéresis 0,3
BAJO = P_SP - est._BANDA_PWM_BAJA - 0.5  # cámara bajo la banda PWM


def test_exencion_retirada():
    assert not hasattr(ccc, "motivo_exencion")
    assert not hasattr(ccc, "MOTIVO_BAJO_BANDA")
    assert not hasattr(est.EsterilizacionFase, "_actualizar_exencion_m2")
    assert not hasattr(est.EsterilizacionFase, "_corte_consigna_chaqueta")


@pytest.mark.parametrize("temp,pres", [(134.0, P_SP), (134.0, BAJO), (134.7, BAJO)])
def test_modo_camara_sin_cambio(monkeypatch, temp, pres):
    f, estado, set_do, _ = ap.fase(monkeypatch, t_est=T_EST, presion_add=15.0,
                                   brecha_seg=0.3, tiempo_min=30, temp=temp, pres=pres)
    estado.modo_vapor = "camara"
    estado.sensores_pres["pres_chaqueta"] = P_SP + 23.0
    f.update()
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_not_called()

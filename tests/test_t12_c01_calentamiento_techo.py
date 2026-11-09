"""Tanda 12, C-01 (decisiones_tanda_12.md): en CALENTAMIENTO
`presion_add_calentamiento` es solo techo.

- p_obj = Psat(T_obj), sin sumar presion_add (duty_proximidad, sobrepaso, logs).
- Entrada a ESTABLE_PREESTERILIZACION: T >= T_obj y P >= p_obj - 2 kPa.
- Techo independiente: P >= Psat(T_obj) + presion_add -> duty 0 (antes 2x).
- duty_calidad_vapor exige P >= Psat(T) - 2 kPa (sin presion_add).
"""
import logging

from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import calentamiento as cal
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests import test_calentamiento_fase as tcal

PSAT_134 = p_saturacion_kpa(134.0)



# PAM (9-nov): el enclave de t_obj (5 s sostenidos) rige ahora para toda carga
# y la entrada a ESTABLE_PREESTERILIZACION lo exige. Estas pruebas son
# anteriores y no ejercitan esa espera: el enclave se hace en el primer tick
# con T >= t_obj (el enclave de 5 s lo cubren test_ajuste_7nov_liquidos.py y
# test_pam_*.py).
import pytest as _pytest_pam


@_pytest_pam.fixture(autouse=True)
def _enclave_inmediato_pam(monkeypatch):
    from autoclave.state_machine.cycle_phases import calentamiento as _cal
    monkeypatch.setattr(_cal, "_ENCLAVE_T_OBJ_SOSTENIDO_S", 0.0)

def test_constante_de_tolerancia_psat():
    assert cal._TOLERANCIA_PSAT_KPA == 2.0


def test_entra_a_sostener_con_presion_1_9_kpa_bajo_psat():
    fase, estado, _ = tcal._make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.update()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = PSAT_134 - 1.9
    assert fase.update() == FaseResult.EN_CURSO
    assert fase._en_sostenimiento is True
    assert fase._timer_sostenido_desde is not None


def test_no_entra_con_presion_2_1_kpa_bajo_psat():
    fase, estado, _ = tcal._make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=5)
    fase.update()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = PSAT_134 - 2.1
    assert fase.update() == FaseResult.EN_CURSO
    assert fase._en_sostenimiento is False


def test_completa_en_psat_sin_sumar_presion_add():
    fase, estado, _ = tcal._make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = PSAT_134
    assert fase.update() == FaseResult.COMPLETADO


def _fase_techo(pres):
    # rango grande y factor 0: duty_proximidad = sobrepaso > 0 cerca del techo,
    # para aislar el corte por techo.
    fase, estado, set_do = tcal._make_fase(t_obj=134.0, presion_add=11.0, rango=50.0,
                                           factor=0.0, tiempo_estable=999)
    fase.update()
    # PAM (9-nov): T bajo t_obj para medir el techo de la rampa antes del
    # enclave (con T >= t_obj se fijaría P_trabajo y regiría la bajada)
    estado.sensores_temp["temp_camara"] = 133.0
    estado.sensores_pres["pres_camara"] = pres
    fase.update()
    return fase


def test_techo_en_psat_mas_presion_add_no_el_doble():
    assert _fase_techo(PSAT_134 + 11.0 - 0.1)._duty_actual > 0.0
    assert _fase_techo(PSAT_134 + 11.0)._duty_actual == 0.0
    # entre 1x y 2x presion_add (el techo viejo) el vapor ya está cortado
    assert _fase_techo(PSAT_134 + 16.0)._duty_actual == 0.0


def test_con_aire_duty_cero_por_techo_y_no_sostiene(caplog):
    caplog.set_level(logging.WARNING)
    fase, estado, set_do = tcal._make_fase(t_obj=134.0, presion_add=11.0, tiempo_estable=0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = PSAT_134 + 30.0
    for _ in range(3):
        assert fase.update() == FaseResult.EN_CURSO
        assert fase._duty_actual == 0.0
        assert fase._timer_sostenido_desde is None
        assert estado.fase_en_sostenimiento is False
    assert "techo" in caplog.text


def test_log_de_inicio_usa_p_obj_sin_presion_add(caplog):
    caplog.set_level(logging.INFO)
    fase, _, _ = tcal._make_fase(t_obj=134.0, presion_add=11.0)
    fase.update()
    assert f"{PSAT_134:.1f} kPa" in caplog.text


def test_duty_calidad_vapor_usa_psat_menos_2_sin_presion_add():
    t = 132.0
    assert cal._duty_por_calidad_vapor(temp=t, pres=p_saturacion_kpa(t) - 1.9, t_obj=134.0) == 1.0
    assert cal._duty_por_calidad_vapor(temp=t, pres=p_saturacion_kpa(t) - 2.1, t_obj=134.0) == 0.0

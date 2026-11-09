"""Tanda 12, C-02: coherencia T-P para entrar a esterilizar (solo sólidos).
La banda de sostenimiento además exige |Tsat(P) - T_principal| <= 1.0 K;
fuera de coherencia = fuera de banda (reinicia la ventana y arma el timeout
de recuperación). Con globals.tipo_carga = "liquido" no se exige."""
import logging

from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import calentamiento as cal
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests import test_calentamiento_fase as tcal



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

def _fase(tipo_carga=None, tiempo_estable=5):
    # presion_add=20: deja Psat(135.2) bajo el techo y aísla la coherencia
    fase, estado, _ = tcal._make_fase(t_obj=134.0, presion_add=20.0,
                                      tiempo_estable=tiempo_estable)
    if tipo_carga is not None:
        original = fase.cycle.get_param.side_effect

        def get_param(seccion, param, default=None):
            if (seccion, param) == ("globals", "tipo_carga"):
                return tipo_carga
            return original(seccion, param, default)
        fase.cycle.get_param.side_effect = get_param
    fase.update()
    return fase, estado


# PAM-05: presión 19,5 kPa sobre Psat(134) (Tsat ≈ 136,1 °C): sobre el margen de
# aire min(20, Psat(136) - Psat(134) ≈ 18,2) y bajo el techo Psat(134) + 20
_P_AIRE = p_saturacion_kpa(134.0) + 19.5


def _entrar_coherente(fase, estado):
    """PAM-03: la entrada exige P <= P_trabajo + 1; se entra coherente."""
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.4)
    fase.update()
    assert fase._timer_sostenido_desde is not None


def test_constante_coherencia():
    assert cal._COHERENCIA_TP_K == 1.0


def test_incoherencia_1_2_k_reinicia_ventana_y_arma_recuperacion(caplog):
    caplog.set_level(logging.WARNING)
    fase, estado = _fase()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.4)  # coherente
    fase.update()
    assert fase._timer_sostenido_desde is not None

    # PAM-05: el lado de aire se mide en kPa, min(presion_add 20, 2 K ≈ 18,2
    # kPa); 19,5 kPa sobre Psat(134) es incoherente y sigue en banda
    estado.sensores_pres["pres_camara"] = _P_AIRE
    assert fase.update() == FaseResult.EN_CURSO
    assert fase._timer_sostenido_desde is None
    assert fase._timer_recuperacion_fin is not None
    assert estado.fase_en_sostenimiento is False
    assert "Tsat" in caplog.text


def test_incoherencia_sostenida_no_completa_y_termina_en_fallo_por_recuperacion():
    fase, estado = _fase(tiempo_estable=5)
    _entrar_coherente(fase, estado)
    estado.sensores_pres["pres_camara"] = _P_AIRE
    assert fase.update() == FaseResult.EN_CURSO
    fase._timer_recuperacion_fin -= 10_000
    assert fase.update() == FaseResult.FALLO


def test_coherencia_0_8_k_completa():
    fase, estado = _fase()
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.8)
    fase.update()
    assert fase._timer_sostenido_desde is not None
    fase._timer_sostenido_desde -= 6
    assert fase.update() == FaseResult.COMPLETADO


def test_liquido_no_exige_coherencia():
    fase, estado = _fase(tipo_carga="liquido")
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(135.2)
    fase.update()
    assert fase._timer_sostenido_desde is not None
    fase._timer_sostenido_desde -= 6
    assert fase.update() == FaseResult.COMPLETADO


def test_solido_explicito_exige_coherencia():
    fase, estado = _fase(tipo_carga="solido")
    _entrar_coherente(fase, estado)
    estado.sensores_pres["pres_camara"] = _P_AIRE
    fase.update()
    assert fase._timer_sostenido_desde is None


def test_tipo_carga_nulo_se_trata_como_solido():
    # falla segura (DECISIÓN SIN CONFIRMAR del informe P12)
    fase, estado = _fase(tipo_carga="")
    _entrar_coherente(fase, estado)
    estado.sensores_pres["pres_camara"] = _P_AIRE
    fase.update()
    assert fase._timer_sostenido_desde is None

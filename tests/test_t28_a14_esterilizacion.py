"""Tanda 28, A14: sobreimpulso en ESTERILIZACION y fallo por aislamiento CIC-16.

- M1: la banda PWM se ancla a P_sp = Psat(T_est + brecha_segura_temperatura +
  0,3), fija al entrar a la fase; advertencia de programa si P_sp + 1 >
  P_control_max - 5.
Reloj monotonic simulado (tests/helpers/t12_e12_apoyo.py)."""

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import esterilizacion as est
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests.helpers import t12_e12_apoyo as ap

pytestmark = pytest.mark.req("T28-A14")

T_EST = 134.0
P_SP = p_saturacion_kpa(134.6)          # brecha 0,3 + histéresis 0,3


def _pwm(monkeypatch, **kw):
    """Fase en PWM_ACTIVO: entra con T sobre la salida de RECUPERACION y la
    presión en la consigna."""
    kw.setdefault("tiempo_min", 30)
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, presion_add=15.0,
                                       brecha_seg=0.3, temp=134.7, pres=P_SP, **kw)
    assert f.update() == FaseResult.EN_CURSO
    assert f._en_recuperacion is False
    return f, estado, set_do, reloj


# ── M1: banda fija ──────────────────────────────────────────────────────────

def test_m1_consigna_fija_al_entrar(monkeypatch):
    f, estado, _, reloj = _pwm(monkeypatch)
    assert f.p_sp == pytest.approx(309.57, abs=0.01)
    # no cambia con la temperatura medida
    for temp in (134.8, 135.2, 135.9):
        ap.poner(estado, temp, P_SP)
        reloj.avanzar(0.5)
        f.update()
        assert f.p_sp == pytest.approx(309.57, abs=0.01)


def test_m1_consigna_igual_a_la_del_catalogo():
    for t_est, brecha in ((134.0, 0.3), (121.0, 0.3), (134.0, 1.0)):
        assert est.EsterilizacionFase.consigna_pwm(t_est, brecha) == pytest.approx(
            cp.consigna_pwm_esterilizacion(t_est, brecha))
    assert cp.BANDA_PWM_ALTA_KPA == est._BANDA_PWM_ALTA


@pytest.mark.parametrize("temp", [134.7, 135.0, 135.5, 136.0])
def test_m1_temperatura_que_sube_no_arrastra_la_presion(monkeypatch, temp):
    """Con P sobre P_sp + 1 el vapor queda OFF aunque la temperatura suba; con
    la banda anterior [Psat(T) - 2, Psat(T) + 1], a 135,5 °C (Psat 318,1)
    311 kPa pedía vapor ON forzado y la presión seguía a la temperatura."""
    f, estado, set_do, reloj = _pwm(monkeypatch)
    ap.poner(estado, temp, P_SP + 1.5)
    set_do.reset_mock()
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.EN_CURSO
    assert f._en_recuperacion is False
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_m1_bajo_la_banda_on_forzado_sin_importar_la_temperatura(monkeypatch):
    f, estado, set_do, reloj = _pwm(monkeypatch)
    ap.poner(estado, 135.5, P_SP - 2.5)
    set_do.reset_mock()
    reloj.avanzar(0.5)
    f.update()
    assert f._en_recuperacion is False
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_m1_el_techo_sigue_rigiendo(monkeypatch):
    f, estado, set_do, reloj = _pwm(monkeypatch)
    techo = p_saturacion_kpa(T_EST) + 15.0
    ap.poner(estado, 134.7, techo)
    set_do.reset_mock()
    reloj.avanzar(0.5)
    f.update()
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


# ── M1: advertencia de programa ─────────────────────────────────────────────

def _params(brecha, add=15.0, t_est=134.0):
    return {"esterilizacion": {
        "temperatura_esterilizacion": {"value": t_est},
        "brecha_segura_temperatura": {"value": brecha},
        "presion_add_esterilizacion": {"value": add}}}


def test_m1_advertencia_con_brecha_1_y_techo_cerca():
    # P_sp = Psat(135,3) = 315,9; +1 = 316,9 > 319,2 - 5
    claves = [c for c, _ in cp.advertencias_programa(_params(1.0))]
    assert claves == [cp.ADVERTENCIA_BANDA_PWM_TECHO]


def test_m1_sin_advertencia_con_brecha_0_3():
    # P_sp + 1 = 310,6 <= 314,2
    assert cp.advertencias_programa(_params(0.3)) == []


def test_m1_advertencia_en_el_limite():
    p_sp = cp.consigna_pwm_esterilizacion(134.0, 0.3)
    add_limite = p_sp + 1 + 5 - p_saturacion_kpa(134.0)       # ≈ 11,4 kPa
    assert cp.advertencias_programa(_params(0.3, add=add_limite + 0.01)) == []
    assert [c for c, _ in cp.advertencias_programa(_params(0.3, add=add_limite - 0.01))] \
        == [cp.ADVERTENCIA_BANDA_PWM_TECHO]


def test_m1_advertencia_filtrada_por_parametro_y_no_bloquea():
    p = _params(1.0)
    for clave in ("brecha_segura_temperatura", "presion_add_esterilizacion",
                  "temperatura_esterilizacion"):
        assert cp.advertencias_programa(p, "esterilizacion", [clave])
    assert cp.advertencias_programa(p, "esterilizacion", ["tiempo_esterilizacion"]) == []
    assert not any("banda" in e for e in cp.errores_coherencia(p))


def test_m1_texto_i18n_de_la_advertencia():
    from autoclave import i18n
    from autoclave.ui_qml.controllers import parametros_ciclo_controller as pc
    assert pc._ADVERTENCIAS[cp.ADVERTENCIA_BANDA_PWM_TECHO] == "opciones.aviso_banda_pwm_techo"
    for idioma in ("es", "en"):
        assert i18n.existe("opciones.aviso_banda_pwm_techo", idioma)

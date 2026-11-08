"""M2-REC-01 (7-nov, decisión de Cristian, opción 1): en ESTERILIZACION, modo
chaqueta, el corte A14-M2 de vapor_chaqueta (pres_chaqueta > P_sp + margen) no
aplica en el tick en que pres_camara < P_sp - 2 (RECUPERACION sola no exime).
Sin lectura de pres_chaqueta sigue cortando; el aislamiento VCH-AIS y D-CHQ
prevalecen. Reproducción con la planta simulada (valores PROVISIONALES) de los
ciclos 21 y 23 de SN260001 (Líquidos 121 °C, CIC-04)."""

import logging

import pytest

from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import corte_chaqueta_consigna as ccc
from autoclave.state_machine.cycle_phases import esterilizacion as est
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests.helpers import t12_e12_apoyo as ap
from tests.helpers.planta_vapor import programa_liquidos, simular

pytestmark = pytest.mark.req("M2-REC-01")

T_EST = 134.0
P_SP = p_saturacion_kpa(134.6)          # brecha 0,3 + histéresis 0,3
UMBRAL = P_SP + 8.0                     # umbral M2 con el margen por defecto
P_LOW = P_SP - est._BANDA_PWM_BAJA
BAJO = P_LOW - 0.5                      # cámara bajo la banda PWM


# ── Componente puro ─────────────────────────────────────────────────────────

def test_debe_cortar_con_exencion():
    assert ccc.debe_cortar(UMBRAL + 20, P_SP, 8.0, camara_necesita_vapor=True) is False
    assert ccc.debe_cortar(UMBRAL + 20, P_SP, 8.0) is True           # sin exención, igual
    assert ccc.debe_cortar(UMBRAL + 20, P_SP, 8.0, camara_necesita_vapor=False) is True


@pytest.mark.parametrize("lectura", [None, float("nan"), float("inf"), "300", True])
def test_debe_cortar_sin_lectura_sigue_cortando_con_exencion(lectura):
    assert ccc.debe_cortar(lectura, P_SP, 8.0, camara_necesita_vapor=True) is True


def test_debe_cortar_sin_umbral_sigue_cortando_con_exencion():
    assert ccc.debe_cortar(250.0, None, 8.0, camara_necesita_vapor=True) is True
    assert ccc.debe_cortar(250.0, P_SP, float("nan"), camara_necesita_vapor=True) is True


def test_debe_cortar_exencion_solo_con_true_estricto():
    assert ccc.debe_cortar(UMBRAL + 20, P_SP, 8.0, camara_necesita_vapor=1) is True
    assert ccc.debe_cortar(UMBRAL + 20, P_SP, 8.0, camara_necesita_vapor="si") is True


def test_motivo_exencion():
    assert ccc.motivo_exencion(P_LOW - 0.1, P_SP, 2.0) == ccc.MOTIVO_BAJO_BANDA
    assert ccc.motivo_exencion(P_LOW, P_SP, 2.0) is None                 # en el borde
    assert ccc.motivo_exencion(P_SP, P_SP, 2.0) is None
    assert ccc.motivo_exencion(P_SP + 5, P_SP, 2.0) is None
    assert ccc.motivo_exencion(None, P_SP, 2.0) is None
    assert ccc.motivo_exencion(float("nan"), P_SP, 2.0) is None
    assert ccc.motivo_exencion(True, P_SP, 2.0) is None                  # bool no es lectura
    assert ccc.motivo_exencion(200.0, None, 2.0) is None
    assert ccc.motivo_exencion(200.0, P_SP, None) is None


# ── Fase ────────────────────────────────────────────────────────────────────

def _fase(monkeypatch, pres_chaqueta, temp, pres, modo="chaqueta", **kw):
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, presion_add=15.0,
                                       brecha_seg=0.3, tiempo_min=30, temp=temp, pres=pres,
                                       **kw)
    estado.modo_vapor = modo
    estado.inhibir_vapor_chaqueta = False
    estado.sensores_pres["pres_chaqueta"] = pres_chaqueta
    return f, estado, set_do, reloj


def test_recuperacion_dentro_de_la_banda_corta_como_antes(monkeypatch):
    """Opción 1: RECUPERACION sola no exime (con carga líquida la sonda lenta
    la sostiene aunque la cámara esté en la banda)."""
    f, _, set_do, _ = _fase(monkeypatch, UMBRAL + 15.0, temp=134.0, pres=P_SP)
    assert f.update() == FaseResult.EN_CURSO
    assert f._en_recuperacion is True
    assert f._exencion_m2 is None
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_on.assert_called()


def test_recuperacion_bajo_la_banda_enciende(monkeypatch):
    f, _, set_do, _ = _fase(monkeypatch, UMBRAL + 15.0, temp=134.0, pres=BAJO)
    assert f.update() == FaseResult.EN_CURSO
    assert f._en_recuperacion is True
    assert f._exencion_m2 == ccc.MOTIVO_BAJO_BANDA
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_chaqueta_off.assert_not_called()
    set_do.vapor_camara_on.assert_called()


def test_pwm_bajo_la_banda_enciende(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, UMBRAL + 15.0, temp=134.7, pres=P_SP)
    f.update()
    assert f._en_recuperacion is False
    ap.poner(estado, 134.7, BAJO)
    set_do.reset_mock()
    reloj.avanzar(0.5)
    f.update()
    assert f._en_recuperacion is False
    assert f._exencion_m2 == ccc.MOTIVO_BAJO_BANDA
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_chaqueta_off.assert_not_called()


def test_dentro_de_la_banda_corta_como_antes(monkeypatch):
    """PWM en el tramo ON (intervalo 30 s, factor 1 %) dentro de la banda."""
    f, _, set_do, _ = _fase(monkeypatch, UMBRAL + 0.5, temp=134.7, pres=P_SP,
                            intervalo=30, factor=1.0)
    f.update()
    assert f._en_recuperacion is False and f._pwm_abierto is True
    assert f._exencion_m2 is None
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()


def test_sobre_la_banda_queda_off(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, UMBRAL + 15.0, temp=134.7, pres=P_SP)
    f.update()
    ap.poner(estado, 134.7, P_SP + 1.5)
    set_do.reset_mock()
    reloj.avanzar(0.5)
    f.update()
    assert f._exencion_m2 is None
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("lectura", [None, float("nan"), float("inf"), "300", True])
@pytest.mark.parametrize("temp", [134.0, 134.7])
def test_sin_lectura_de_chaqueta_off_con_exencion(monkeypatch, lectura, temp):
    f, _, set_do, _ = _fase(monkeypatch, lectura, temp=temp, pres=BAJO)
    f.update()
    assert f._exencion_m2 == ccc.MOTIVO_BAJO_BANDA
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()


def test_aislamiento_prevalece(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, UMBRAL + 15.0, temp=134.0, pres=BAJO)
    f.update()
    assert f._exencion_m2 == ccc.MOTIVO_BAJO_BANDA
    ap.poner(estado, 134.0, p_saturacion_kpa(T_EST) + 15.0)       # techo P_control_max
    set_do.reset_mock()
    reloj.avanzar(0.5)
    assert f.update() == FaseResult.EN_CURSO
    assert f._aislamiento().aislado is True
    assert f._exencion_m2 is None
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_camara_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_off.assert_called()


@pytest.mark.parametrize("temp", [134.0, 134.7])
def test_inhibicion_d_chq_prevalece(monkeypatch, temp):
    f, estado, set_do, _ = _fase(monkeypatch, UMBRAL + 15.0, temp=temp, pres=BAJO)
    estado.inhibir_vapor_chaqueta = True
    f.update()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()


def test_sin_lectura_de_la_camara_sin_exencion(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, UMBRAL + 15.0, temp=134.0, pres=BAJO)
    f.update()
    assert f._exencion_m2 == ccc.MOTIVO_BAJO_BANDA
    estado.sensores_pres["pres_camara"] = None
    set_do.reset_mock()
    reloj.avanzar(0.5)
    f.update()
    assert f._exencion_m2 is None
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("temp,pres", [(134.0, P_SP), (134.0, BAJO), (134.7, BAJO)])
def test_modo_camara_sin_cambio(monkeypatch, temp, pres):
    f, _, set_do, _ = _fase(monkeypatch, UMBRAL + 15.0, temp=temp, pres=pres, modo="camara")
    f.update()
    assert f._exencion_m2 is None
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_not_called()


def _lineas(caplog, texto):
    return [r for r in caplog.records
            if r.name == est.logger.name and texto in r.getMessage()]


def test_log_de_la_exencion_al_empezar_y_al_terminar(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger=est.logger.name)
    # RECUPERACION dentro de la banda: sin exención ni línea
    f, estado, _, reloj = _fase(monkeypatch, UMBRAL + 15.0, temp=134.0, pres=P_SP)
    for _ in range(3):
        f.update()
        reloj.avanzar(0.5)
    assert _lineas(caplog, "M2-REC-01") == []
    # bajo la banda: una sola línea de inicio
    ap.poner(estado, 134.0, BAJO)
    for _ in range(4):
        f.update()
        reloj.avanzar(0.5)
    inicio = _lineas(caplog, "exención del corte A14-M2 (M2-REC-01, motivo bajo_banda)")
    assert len(inicio) == 1
    msg = inicio[0].getMessage()
    assert f"pres_camara {BAJO:.1f}" in msg and f"pres_chaqueta {UMBRAL + 15.0:.1f}" in msg
    assert f"umbral M2 {UMBRAL:.1f}" in msg
    # vuelve a la banda: una sola línea de fin
    ap.poner(estado, 134.0, P_SP)
    for _ in range(4):
        f.update()
        reloj.avanzar(0.5)
    assert len(_lineas(caplog, "fin de la exención del corte A14-M2 (motivo bajo_banda)")) == 1
    assert len(_lineas(caplog, "M2-REC-01, motivo bajo_banda")) == 1


def test_reset_limpia_la_exencion(monkeypatch):
    f, _, _, _ = _fase(monkeypatch, UMBRAL + 15.0, temp=134.0, pres=BAJO)
    f.update()
    assert f._exencion_m2 is not None
    f.reset()
    assert f._exencion_m2 is None


# ── Planta simulada: Líquidos 121 °C, modo chaqueta (valores PROVISIONALES) ──
# Entrada a ESTERILIZACION con la chaqueta cargada a 240 kPa y la cámara a
# 213 kPa; pérdida de cámara 0,35 kPa/s sin vapor (escape lento enclavado y
# carga líquida); paso chaqueta → cámara restrictivo (0,015/s); 1 s de
# vapor_chaqueta sube la chaqueta 12 kPa; sonda en la carga (121,0 °C, sube
# despacio). Ver docs/informes/m2_recuperacion/R_informe.md.

ESCENARIO_LIQUIDOS = dict(
    t_inicial=121.1, t_sonda_inicial=121.0, p_camara_inicial=213.0,
    p_chaqueta_inicial=240.0,
    ajustes=dict(PASO_CAMARA=0.015, LLENADO_CHAQUETA=12.0, PERDIDA_CAMARA=0.35,
                 CONDENSACION=0.005, CALOR=0.003, PERDIDA_TERMICA=0.0))

VARIANTES = {
    "base": {},
    "paso_0_025": {"PASO_CAMARA": 0.025},
    "carga_calor_0_01": {"CALOR": 0.01},
}


def _simular_liquidos(monkeypatch, **ajustes):
    kw = dict(ESCENARIO_LIQUIDOS, ajustes={**ESCENARIO_LIQUIDOS["ajustes"], **ajustes})
    return simular("chaqueta", programa_liquidos(), limite_s=1200, monkeypatch=monkeypatch,
                   planta_kw=kw, desde_esterilizacion=True)


@pytest.mark.parametrize("variante", list(VARIANTES))
def test_planta_antes_del_cambio_reproduce_cic04(monkeypatch, variante):
    """Sin la exención (comportamiento anterior): la chaqueta cortada por M2 no
    repone la cámara y la fase falla por presión baja (CIC-04), como en los
    ciclos 21 y 23 del equipo (56 y 83 s)."""
    monkeypatch.setattr(ccc, "motivo_exencion", lambda *a, **k: None)
    r = _simular_liquidos(monkeypatch, **VARIANTES[variante])
    assert r.resultado == "FALLO"
    assert r.alarma is None and "203.0" in r.motivo                 # CIC-04 (pres baja)
    assert 30 <= r.ester()[-1][0] <= 120
    assert r.p_chaqueta_max_ester <= 240.5


@pytest.mark.parametrize("variante", list(VARIANTES))
def test_planta_despues_del_cambio_completa(monkeypatch, variante):
    """Con la exención solo bajo la banda la cámara se repone y el ciclo
    COMPLETA sin aislamientos; la chaqueta queda lejos de D-CHQ (375)."""
    r = _simular_liquidos(monkeypatch, **VARIANTES[variante])
    assert r.resultado == "COMPLETADO", (r.resultado, r.motivo, r.alarma)
    assert r.aislamientos == 0
    assert r.p_min_ester > p_saturacion_kpa(121.0) - 2.0            # sobre el umbral CIC-04
    assert r.p_max_ester < p_saturacion_kpa(121.0) + 11.0           # bajo el techo
    assert r.p_chaqueta_max_ester < 300.0
    assert r.t_min_ester >= 121.0 - 0.1
    assert r.exencion_s > 0

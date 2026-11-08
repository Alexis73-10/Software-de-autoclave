"""Tanda 33, CAS-02: control en cascada de vapor_chaqueta en ESTERILIZACION,
solo modo chaqueta (docs/mis_plans/planeacion_control_cascada_chaqueta.md §3).

La cascada (cascada_chaqueta.py) decide vapor_chaqueta con p_ref = P_sp
(A14-M1) y p_techo = P_control_max, en lugar del PWM, el corte A14-M2 y la
exención M2-REC-01. Prevalecen VCH-AIS, inhibir_vapor_chaqueta (D-CHQ, sin
suministro, sin lectura) y la falta de lectura del Principal o de la cámara.
RECUPERACION se sigue calculando pero no decide la válvula. Modo cámara sin
cambio. Reloj monotonic simulado (tests/helpers/t12_e12_apoyo.py)."""

import logging

import pytest

from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import cascada_chaqueta as cc
from autoclave.state_machine.cycle_phases import corte_chaqueta_consigna as ccc
from autoclave.state_machine.cycle_phases import esterilizacion as est
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests.helpers import t12_e12_apoyo as ap
from tests.helpers.planta_vapor import programa_liquidos, simular

pytestmark = pytest.mark.req("CAS-02")

T_EST = 134.0
PRESION_ADD = 15.0
P_SP = p_saturacion_kpa(134.6)                 # brecha 0,3 + histéresis 0,3 ≈ 309,57
TECHO = p_saturacion_kpa(T_EST) + PRESION_ADD  # P_control_max ≈ 319,2
TOPE = TECHO - cc.MARGEN_TECHO_KPA             # < 375 - 10 y < suministro 350
MARGEN = 4.0                                   # margen_chaqueta_est de las pruebas
CONSIGNA_BANDA = P_SP + MARGEN                 # < TOPE
BAJO = P_SP - cc.UMBRAL_BAJO_KPA - 0.5         # nivel baja
ALTO = P_SP + cc.UMBRAL_ALTO_KPA + 0.5         # nivel alta
H = cc.HISTERESIS_KPA


def _fase(monkeypatch, pres_chaqueta, temp=134.7, pres=P_SP, modo="chaqueta",
          margen=MARGEN, **kw):
    kw.setdefault("tiempo_min", 30)
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, presion_add=PRESION_ADD,
                                       brecha_seg=0.3, temp=temp, pres=pres, **kw)
    estado.modo_vapor = modo
    estado.inhibir_vapor_chaqueta = False
    estado.sensores_pres["pres_chaqueta"] = pres_chaqueta
    if margen is not None:
        base = f.cycle.get_param.side_effect
        f.cycle.get_param.side_effect = (
            lambda s, p, default=None: margen if p == "margen_chaqueta_est" else base(s, p, default))
    f.reset()
    return f, estado, set_do, reloj


def _tick(f, set_do, reloj, paso=0.5):
    set_do.reset_mock()
    reloj.avanzar(paso)
    return f.update()


def _chaqueta(set_do):
    """Última orden de vapor_chaqueta del tick (None si no hubo)."""
    ordenes = [c[0] for c in set_do.mock_calls
               if c[0] in ("vapor_chaqueta_on", "vapor_chaqueta_off")]
    return ordenes[-1] if ordenes else None


def test_consignas_de_las_pruebas():
    assert TOPE == pytest.approx(cc.CascadaChaqueta.tope(TECHO, 375.0, 350.0))
    assert P_SP + 1 < CONSIGNA_BANDA < TOPE


# ── Niveles con la fase real ────────────────────────────────────────────────

def test_nivel_baja_lleva_la_chaqueta_al_tope(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, TOPE - H - 0.1, pres=BAJO)
    assert f.update() == FaseResult.EN_CURSO
    assert _chaqueta(set_do) == "vapor_chaqueta_on"
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()
    pub = estado.cascada_chaqueta
    assert pub["nivel"] == cc.NIVEL_BAJA and pub["valvula"] is True
    assert pub["consigna"] == pytest.approx(TOPE)
    # llega al tope: OFF
    estado.sensores_pres["pres_chaqueta"] = TOPE
    _tick(f, set_do, reloj)
    assert _chaqueta(set_do) == "vapor_chaqueta_off"
    assert estado.cascada_chaqueta["valvula"] is False


def test_nivel_banda_con_histeresis(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, CONSIGNA_BANDA - H)
    f.update()
    assert estado.cascada_chaqueta["nivel"] == cc.NIVEL_BANDA
    assert estado.cascada_chaqueta["consigna"] == pytest.approx(CONSIGNA_BANDA)
    assert _chaqueta(set_do) == "vapor_chaqueta_on"
    # dentro de la histéresis conserva ON
    estado.sensores_pres["pres_chaqueta"] = CONSIGNA_BANDA - 1.0
    _tick(f, set_do, reloj)
    assert _chaqueta(set_do) == "vapor_chaqueta_on"
    # en la consigna: OFF
    estado.sensores_pres["pres_chaqueta"] = CONSIGNA_BANDA
    _tick(f, set_do, reloj)
    assert _chaqueta(set_do) == "vapor_chaqueta_off"
    # baja dentro de la histéresis: conserva OFF
    estado.sensores_pres["pres_chaqueta"] = CONSIGNA_BANDA - 1.0
    _tick(f, set_do, reloj)
    assert _chaqueta(set_do) == "vapor_chaqueta_off"
    # bajo consigna - 3: ON otra vez
    estado.sensores_pres["pres_chaqueta"] = CONSIGNA_BANDA - H - 0.1
    _tick(f, set_do, reloj)
    assert _chaqueta(set_do) == "vapor_chaqueta_on"


def test_nivel_banda_usa_el_margen_del_programa(monkeypatch):
    f, estado, _, _ = _fase(monkeypatch, 250.0, margen=6.0)
    f.update()
    assert estado.cascada_chaqueta["consigna"] == pytest.approx(P_SP + 6.0)
    # margen por defecto (8): la consigna queda limitada por el tope
    f2, estado2, _, _ = _fase(monkeypatch, 250.0, margen=None)
    f2.update()
    assert estado2.cascada_chaqueta["consigna"] == pytest.approx(
        min(P_SP + ccc.MARGEN_DEFECTO_KPA, TOPE))


def test_nivel_alta_off_aunque_la_chaqueta_este_baja(monkeypatch):
    f, estado, set_do, _ = _fase(monkeypatch, 200.0, pres=ALTO)
    f.update()
    assert _chaqueta(set_do) == "vapor_chaqueta_off"
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_camara_on.assert_called()
    assert estado.cascada_chaqueta == {"nivel": cc.NIVEL_ALTA, "consigna": None,
                                       "valvula": False}


def test_cambio_de_nivel_reevalua_en_el_mismo_tick(monkeypatch):
    # chaqueta entre la consigna de banda y el tope: OFF en banda, ON en baja
    pj = CONSIGNA_BANDA + 0.5
    assert pj <= TOPE - H
    f, estado, set_do, reloj = _fase(monkeypatch, pj)
    f.update()
    assert _chaqueta(set_do) == "vapor_chaqueta_off"
    ap.poner(estado, 134.7, BAJO)
    _tick(f, set_do, reloj)
    assert _chaqueta(set_do) == "vapor_chaqueta_on"
    ap.poner(estado, 134.7, P_SP)
    _tick(f, set_do, reloj)
    assert _chaqueta(set_do) == "vapor_chaqueta_off"


# ── RECUPERACION y PWM no deciden en modo chaqueta ──────────────────────────

def test_recuperacion_no_decide_la_valvula(monkeypatch):
    # T = T_est: RECUPERACION; con la cámara alta la cascada cierra igual
    f, estado, set_do, _ = _fase(monkeypatch, 250.0, temp=134.0, pres=ALTO)
    f.update()
    assert f._en_recuperacion is True
    assert _chaqueta(set_do) == "vapor_chaqueta_off"
    # PWM_ACTIVO (T sobre la salida de RECUPERACION) bajo la banda: ON
    f2, _, set_do2, _ = _fase(monkeypatch, 250.0, temp=134.7, pres=BAJO)
    f2.update()
    assert f2._en_recuperacion is False
    assert _chaqueta(set_do2) == "vapor_chaqueta_on"


@pytest.mark.parametrize("factor, intervalo", [(1.0, 30), (99.0, 3), (70.0, 0)])
def test_factor_e_intervalo_no_se_usan(monkeypatch, factor, intervalo):
    """Dentro de la banda, con la chaqueta lejos de la consigna, la válvula
    queda ON en todos los ticks (sin PWM), sea cual sea el factor."""
    f, _, set_do, reloj = _fase(monkeypatch, 250.0, factor=factor, intervalo=intervalo)
    f.update()
    assert f._en_recuperacion is False
    for _ in range(20):
        _tick(f, set_do, reloj)
        assert _chaqueta(set_do) == "vapor_chaqueta_on"
        set_do.vapor_chaqueta_off.assert_not_called()
    assert f._t_pulso_pwm is None


# ── Prevalencias ────────────────────────────────────────────────────────────

def test_aislamiento_prevalece(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, 250.0, pres=BAJO)
    f.update()
    assert _chaqueta(set_do) == "vapor_chaqueta_on"
    ap.poner(estado, 134.7, TECHO)
    assert _tick(f, set_do, reloj) == FaseResult.EN_CURSO
    assert f._aislamiento().aislado is True
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    assert estado.cascada_chaqueta["valvula"] is False
    # la cámara cae a nivel baja, pero el aislamiento sigue 3 s: OFF
    ap.poner(estado, 134.7, BAJO)
    for _ in range(6):                                  # 0 a 2,5 s bajo el umbral
        _tick(f, set_do, reloj)
        assert f._aislamiento().aislado is True
        set_do.vapor_chaqueta_on.assert_not_called()
        set_do.vapor_camara_on.assert_not_called()
        assert estado.cascada_chaqueta["nivel"] == cc.NIVEL_BAJA
        assert estado.cascada_chaqueta["valvula"] is False
    _tick(f, set_do, reloj)                             # 3,0 s: sale
    assert f._aislamiento().aislado is False
    set_do.vapor_camara_on.assert_called()
    assert _chaqueta(set_do) == "vapor_chaqueta_on"


def test_inhibicion_prevalece_y_sincroniza_la_histeresis(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, CONSIGNA_BANDA - H - 1.0)
    f.update()
    assert _chaqueta(set_do) == "vapor_chaqueta_on"
    estado.inhibir_vapor_chaqueta = True
    _tick(f, set_do, reloj)
    set_do.vapor_chaqueta_on.assert_not_called()
    assert _chaqueta(set_do) == "vapor_chaqueta_off"
    assert estado.cascada_chaqueta["valvula"] is False
    set_do.vapor_camara_on.assert_called()
    # sin inhibición, con la chaqueta dentro de la histéresis: sigue OFF
    # (la cascada recuerda la orden dada, no la que pidió)
    estado.inhibir_vapor_chaqueta = False
    estado.sensores_pres["pres_chaqueta"] = CONSIGNA_BANDA - 1.0
    _tick(f, set_do, reloj)
    assert _chaqueta(set_do) == "vapor_chaqueta_off"
    estado.sensores_pres["pres_chaqueta"] = CONSIGNA_BANDA - H - 0.1
    _tick(f, set_do, reloj)
    assert _chaqueta(set_do) == "vapor_chaqueta_on"


def test_inhibicion_solo_con_true_estricto(monkeypatch):
    from unittest.mock import MagicMock
    f, estado, set_do, _ = _fase(monkeypatch, 250.0)
    estado.inhibir_vapor_chaqueta = MagicMock()
    f.update()
    assert _chaqueta(set_do) == "vapor_chaqueta_on"


@pytest.mark.parametrize("lectura", [None, float("nan"), float("inf"), 0.0, -5.0, "300", True])
def test_sin_lectura_de_chaqueta_off(monkeypatch, lectura):
    f, estado, set_do, _ = _fase(monkeypatch, lectura, pres=BAJO)
    f.update()
    set_do.vapor_chaqueta_on.assert_not_called()
    assert _chaqueta(set_do) == "vapor_chaqueta_off"
    set_do.vapor_camara_on.assert_called()
    assert estado.cascada_chaqueta == {"nivel": cc.NIVEL_SIN_DATOS, "consigna": None,
                                       "valvula": False}


def test_sin_lectura_del_principal_off(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, 250.0, pres=BAJO)
    f.update()
    assert _chaqueta(set_do) == "vapor_chaqueta_on"
    estado.sensores_temp["temp_camara"] = None
    assert _tick(f, set_do, reloj) == FaseResult.EN_CURSO
    set_do.vapor_chaqueta_on.assert_not_called()
    assert _chaqueta(set_do) == "vapor_chaqueta_off"
    set_do.vapor_camara_on.assert_called()
    assert estado.cascada_chaqueta["valvula"] is False


def test_sin_lectura_de_la_camara_off(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, 250.0, pres=BAJO)
    f.update()
    estado.sensores_pres["pres_camara"] = None
    _tick(f, set_do, reloj)
    set_do.vapor_chaqueta_on.assert_not_called()
    assert _chaqueta(set_do) == "vapor_chaqueta_off"
    assert estado.cascada_chaqueta["nivel"] == cc.NIVEL_SIN_DATOS


# ── Publicación y ciclo de vida ─────────────────────────────────────────────

def test_reset_limpia_la_publicacion_y_la_cascada(monkeypatch):
    f, estado, _, _ = _fase(monkeypatch, 250.0)
    f.update()
    assert estado.cascada_chaqueta is not None
    anterior = f._cascada
    f.reset()
    assert estado.cascada_chaqueta is None
    assert f._cascada is not anterior and f._cascada.valvula is False


def test_completado_limpia_la_publicacion(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, 250.0, tiempo_min=1)
    f.update()
    r = FaseResult.EN_CURSO
    for _ in range(130):
        r = _tick(f, set_do, reloj)
        if r != FaseResult.EN_CURSO:
            break
    assert r == FaseResult.COMPLETADO
    set_do.vapor_chaqueta_off.assert_called()
    assert estado.cascada_chaqueta is None


def test_fallo_limpia_la_publicacion(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, 250.0)
    f.update()
    ap.poner(estado, 134.7, p_saturacion_kpa(T_EST) - 10.0)   # presión baja
    r = FaseResult.EN_CURSO
    for _ in range(20):
        r = _tick(f, set_do, reloj)
        if r != FaseResult.EN_CURSO:
            break
    assert r == FaseResult.FALLO
    set_do.vapor_chaqueta_off.assert_called()
    assert estado.cascada_chaqueta is None


# ── Modo cámara sin cambio ──────────────────────────────────────────────────

@pytest.mark.parametrize("temp, pres", [(134.0, P_SP), (134.0, BAJO), (134.7, BAJO),
                                        (134.7, P_SP), (134.7, ALTO)])
def test_modo_camara_no_usa_la_cascada(monkeypatch, temp, pres):
    f, estado, set_do, reloj = _fase(monkeypatch, 250.0, temp=temp, pres=pres, modo="camara")
    for _ in range(4):
        _tick(f, set_do, reloj)
        set_do.vapor_chaqueta_on.assert_not_called()
        set_do.vapor_chaqueta_off.assert_not_called()
    assert estado.cascada_chaqueta is None


def test_modo_camara_techo_y_pwm_como_antes(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, None, pres=P_SP, modo="camara",
                                     intervalo=30, factor=1.0)
    f.update()
    assert f._en_recuperacion is False and f._pwm_abierto is True
    ap.poner(estado, 134.7, TECHO)
    _tick(f, set_do, reloj)
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


# ── Log ─────────────────────────────────────────────────────────────────────

def _lineas_cascada(caplog):
    return [r for r in caplog.records
            if r.name == cc.logger.name and "Cascada chaqueta" in r.getMessage()]


def test_log_de_la_cascada_sin_repeticion_por_tick(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger=cc.logger.name)
    f, estado, set_do, reloj = _fase(monkeypatch, 250.0)
    f.update()
    for _ in range(10):
        _tick(f, set_do, reloj)
    assert len(_lineas_cascada(caplog)) == 1
    # la válvula conmuta sin cambiar nivel ni consigna: sin líneas nuevas
    estado.sensores_pres["pres_chaqueta"] = CONSIGNA_BANDA
    for _ in range(5):
        _tick(f, set_do, reloj)
    assert len(_lineas_cascada(caplog)) == 1
    # cambio de nivel: una línea más, una sola vez
    ap.poner(estado, 134.7, BAJO)
    for _ in range(5):
        _tick(f, set_do, reloj)
    lineas = _lineas_cascada(caplog)
    assert len(lineas) == 2 and "nivel=baja" in lineas[-1].getMessage()


def test_log_de_inicio_en_modo_chaqueta(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger=est.logger.name)
    f, _, _, _ = _fase(monkeypatch, 250.0)
    f.update()
    assert any("CAS-02" in r.getMessage() for r in caplog.records if r.name == est.logger.name)


# ── Integración con CicloState real (orden real del tick) ──────────────────

def test_integracion_cicloestate(monkeypatch):
    """CicloState real con la EsterilizacionFase real: la cascada decide en el
    tick y D-CHQ (presion_max_chaqueta_control, 375) prevalece después."""
    from autoclave.installation.profile import MODO_CHAQUETA
    from tests import test_t16_s3_ciclo_chaqueta as s3
    from autoclave.state_machine.states.ciclo import CicloResultado

    f, _, _, reloj = ap.fase(monkeypatch, t_est=T_EST, presion_add=PRESION_ADD,
                             brecha_seg=0.3, tiempo_min=30)
    ciclo, estado, set_do, _ = s3._ciclo(pres_chaqueta=250.0, modo=MODO_CHAQUETA)
    estado.sensores_temp["temp_camara"] = 134.7
    estado.sensores_pres["pres_camara"] = P_SP
    estado.avisos_ciclo = []
    f.estado, f.set_do = estado, set_do
    f.reset()
    s3._con_fases(ciclo, f)
    consigna = min(P_SP + ccc.MARGEN_DEFECTO_KPA, TOPE)

    assert ciclo.run() == CicloResultado.EN_CURSO
    assert estado.inhibir_vapor_chaqueta is False
    assert s3._ordenes_chaqueta(set_do)[-1] == "vapor_chaqueta_on"

    set_do.reset_mock()
    reloj.avanzar(1.0)
    estado.sensores_pres["pres_chaqueta"] = consigna + 0.5       # < 375
    assert ciclo.run() == CicloResultado.EN_CURSO
    assert estado.inhibir_vapor_chaqueta is False
    assert set(s3._ordenes_chaqueta(set_do)) == {"vapor_chaqueta_off"}

    set_do.reset_mock()
    reloj.avanzar(1.0)
    estado.sensores_pres["pres_chaqueta"] = consigna - H - 0.5
    ciclo.run()
    assert s3._ordenes_chaqueta(set_do)[-1] == "vapor_chaqueta_on"

    # D-CHQ: sobre presion_max_chaqueta_control, OFF aunque la cámara esté baja
    set_do.reset_mock()
    reloj.avanzar(1.0)
    estado.sensores_pres["pres_camara"] = BAJO
    estado.sensores_pres["pres_chaqueta"] = 376.0
    ciclo.run()
    assert estado.inhibir_vapor_chaqueta is True
    assert "vapor_chaqueta_on" not in s3._ordenes_chaqueta(set_do)


# ── Planta simulada (valores PROVISIONALES, tests/helpers/planta_vapor.py) ──
# Escenario de M2-REC-01 (Líquidos 121 °C, entrada con la cámara a 213 kPa).

_ESCENARIO = dict(
    t_inicial=121.1, t_sonda_inicial=121.0, p_camara_inicial=213.0,
    ajustes=dict(LLENADO_CHAQUETA=12.0, PERDIDA_CAMARA=0.35,
                 CONDENSACION=0.005, CALOR=0.003, PERDIDA_TERMICA=0.0))


def _simular(monkeypatch, p_chaqueta, paso):
    kw = dict(_ESCENARIO, p_chaqueta_inicial=p_chaqueta,
              ajustes={**_ESCENARIO["ajustes"], "PASO_CAMARA": paso})
    return simular("chaqueta", programa_liquidos(), limite_s=1200, monkeypatch=monkeypatch,
                   planta_kw=kw, desde_esterilizacion=True)


def test_planta_paso_abierto_completa(monkeypatch):
    """Cámara y chaqueta casi un solo volumen (válvula de asiento sin
    restricción, dato de Cristian): COMPLETA sin aislamientos ni CIC-04."""
    r = _simular(monkeypatch, 213.0, 0.1)
    assert r.resultado == "COMPLETADO", (r.resultado, r.motivo, r.alarma)
    assert r.aislamientos == 0
    assert r.p_min_ester > p_saturacion_kpa(121.0) - 2.0
    assert r.p_chaqueta_max_ester < 300.0


def test_planta_paso_restrictivo_falla_segura(monkeypatch):
    """Caracterización (DECISIÓN SIN CONFIRMAR, HAZ-CAS-02): con el paso
    restrictivo del escenario M2-REC (0,015/s) y la chaqueta cargada a
    240 kPa, sobre el tope de la cascada, vapor_chaqueta no se abre y la cámara
    cae a CIC-04 sin aislamientos (falla segura, como los ciclos 21 y 23)."""
    r = _simular(monkeypatch, 240.0, 0.015)
    assert r.resultado == "FALLO"
    assert r.alarma is None and "203.0" in r.motivo
    assert r.aislamientos == 0
    assert r.p_chaqueta_max_ester <= 240.5

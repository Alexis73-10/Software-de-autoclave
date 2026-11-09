"""CRI-01 (tanda 35, docs/mis_plans/planeacion_cascada_integral.md §3, §6.2):
consigna de banda de la cascada de chaqueta con acción integral.

dp += KI_CRI * (p_ref - P_cam) * dt, dt recortado a 0..DT_MAX_S, acotada a
[DP_MIN_KPA, tope_baja - p_ref]; valor inicial margen_chaqueta_est o el dp
heredado de CALENTAMIENTO; consigna de banda min(p_ref + dp, tope_baja), sin
techo - 2; integral congelada con aislamiento, inhibir_vapor_chaqueta, sin
lectura o con orden OFF por prevalencia; dp publicado y log por cambio > 2 kPa.
"""

import logging
import math
import types

import pytest

from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import calentamiento as cal_mod
from autoclave.state_machine.cycle_phases import cascada_chaqueta as cc
from autoclave.state_machine.cycle_phases.cascada_chaqueta import CascadaChaqueta
from tests.helpers import t12_e12_apoyo as ap

pytestmark = pytest.mark.req("CRI-01")

LOGGER = cc.logger.name
P_REF = 200.0
MARGEN = 8.0
PMAX = 375.0
SUMINISTRO = 350.0
TOPE_BAJA = 350.0          # min(375 - 10, 350)


def _ev(c, pc, pj, ahora, **kw):
    args = dict(p_ref=P_REF, margen_est=MARGEN, presion_max_chaqueta_control=PMAX,
                presion_suministro_vapor=SUMINISTRO, ahora=ahora)
    args.update(kw)
    return c.evaluar(pc, pj, **args)


# ── Constantes ──────────────────────────────────────────────────────────────

def test_constantes():
    assert cc.KI_CRI == 0.15
    assert cc.DP_MIN_KPA == 3.0
    assert cc.DT_MAX_S == 2.0
    assert cc.UMBRAL_LOG_DP_KPA == 2.0
    assert cc.MARGEN_P_BAJA_KPA == 1.0
    assert not hasattr(cc, "MARGEN_TECHO_KPA")
    assert not hasattr(CascadaChaqueta, "tope")


# ── Valor inicial ───────────────────────────────────────────────────────────

def test_valor_inicial_es_el_margen():
    c = CascadaChaqueta()
    assert c.dp is None
    r = _ev(c, 199.0, 150.0, 0.0)
    assert c.dp == pytest.approx(MARGEN)
    assert r.consigna == pytest.approx(P_REF + MARGEN)


def test_primer_tick_no_integra():
    c = CascadaChaqueta()
    _ev(c, 190.0 + 9.0, 150.0, 1000.0)       # error 1, sin tick previo
    assert c.dp == pytest.approx(MARGEN)


def test_valor_inicial_heredado_prevalece_sobre_el_margen():
    c = CascadaChaqueta(dp_inicial=17.0)
    r = _ev(c, 199.0, 150.0, 0.0)
    assert c.dp == pytest.approx(17.0)
    assert r.consigna == pytest.approx(P_REF + 17.0)


@pytest.mark.parametrize("heredado", [None, math.nan, math.inf, "15", True])
def test_heredado_invalido_usa_el_margen(heredado):
    c = CascadaChaqueta(dp_inicial=heredado)
    _ev(c, 199.0, 150.0, 0.0)
    assert c.dp == pytest.approx(MARGEN)


@pytest.mark.parametrize("inicial, esperado", [(1.0, 3.0), (-5.0, 3.0), (500.0, 150.0)])
def test_valor_inicial_acotado(inicial, esperado):
    c = CascadaChaqueta(dp_inicial=inicial)
    _ev(c, 199.0, 150.0, 0.0)
    assert c.dp == pytest.approx(esperado)
    c2 = CascadaChaqueta()
    _ev(c2, 199.0, 150.0, 0.0, margen_est=inicial)
    assert c2.dp == pytest.approx(esperado)


def test_reset_con_dp_inicial():
    c = CascadaChaqueta()
    _ev(c, 199.0, 150.0, 0.0)
    _ev(c, 199.0, 150.0, 1.0)
    c.reset(dp_inicial=12.0)
    assert c.dp is None
    _ev(c, 199.0, 150.0, 5.0)
    assert c.dp == pytest.approx(12.0)


# ── Integración ─────────────────────────────────────────────────────────────

def test_integra_con_error_positivo():
    c = CascadaChaqueta()
    _ev(c, 199.0, 150.0, 0.0)
    _ev(c, 199.0, 150.0, 1.0)                 # error 1 kPa, 1 s
    assert c.dp == pytest.approx(MARGEN + 0.15)
    _ev(c, 199.0, 150.0, 1.5)                 # 0,5 s
    assert c.dp == pytest.approx(MARGEN + 0.15 + 0.075)


def test_error_cero_no_cambia():
    c = CascadaChaqueta()
    for t in range(20):
        _ev(c, P_REF, 150.0, float(t))
    assert c.dp == pytest.approx(MARGEN)


def test_en_alta_la_integral_baja_dp():
    c = CascadaChaqueta()
    _ev(c, 199.0, 150.0, 0.0)
    r = _ev(c, 202.0, 150.0, 1.0)              # alta, error -2
    assert r.nivel == cc.NIVEL_ALTA and r.decision is False
    assert c.dp == pytest.approx(MARGEN - 0.3)


def test_en_baja_la_integral_sigue():
    c = CascadaChaqueta()
    _ev(c, 199.0, 150.0, 0.0)
    r = _ev(c, 195.0, 150.0, 1.0)              # baja, error 5
    assert r.nivel == cc.NIVEL_BAJA
    assert r.consigna == pytest.approx(TOPE_BAJA)
    assert c.dp == pytest.approx(MARGEN + 0.75)


@pytest.mark.parametrize("salto, dt_efectivo", [(100.0, 2.0), (2.0, 2.0), (-50.0, 0.0)])
def test_dt_recortado(salto, dt_efectivo):
    c = CascadaChaqueta()
    _ev(c, 199.0, 150.0, 1000.0)
    _ev(c, 199.0, 150.0, 1000.0 + salto)
    assert c.dp == pytest.approx(MARGEN + 0.15 * dt_efectivo)


def test_cota_superior_tope_baja_menos_p_ref():
    c = CascadaChaqueta()
    for t in range(0, 20000):
        _ev(c, 199.5, 150.0, float(t))
    assert c.dp == pytest.approx(TOPE_BAJA - P_REF)
    r = _ev(c, 199.5, 150.0, 20001.0)
    assert r.consigna == pytest.approx(TOPE_BAJA)


def test_cota_inferior_dp_min():
    c = CascadaChaqueta()
    for t in range(0, 200):
        _ev(c, 201.0, 150.0, float(t))          # error -1 (banda)
    assert c.dp == pytest.approx(cc.DP_MIN_KPA)
    assert _ev(c, 201.0, 150.0, 201.0).consigna == pytest.approx(P_REF + cc.DP_MIN_KPA)


def test_cotas_con_tope_bajo_p_ref():
    assert CascadaChaqueta.cotas_dp(349.0, 350.0) == (3.0, 3.0)
    assert CascadaChaqueta.cotas_dp(200.0, 350.0) == (3.0, 150.0)


# ── Consigna de banda sin techo ─────────────────────────────────────────────

def test_banda_sin_limite_de_techo():
    """CRI-01: el caso del equipo (Líquidos 121 °C, presion_add 11): techo
    216,0, P_sp 212; con dp 20 la consigna es 232, sobre el techo - 2 = 214."""
    p_sp = 212.0
    c = CascadaChaqueta(dp_inicial=20.0)
    r = _ev(c, 212.0, 220.0, 0.0, p_ref=p_sp)
    assert r.nivel == cc.NIVEL_BANDA
    assert r.consigna == pytest.approx(232.0)
    assert r.decision is True                   # 220 <= 232 - 3


def test_banda_limitada_por_tope_baja():
    c = CascadaChaqueta(dp_inicial=140.0)
    r = _ev(c, 199.0, 150.0, 0.0, presion_suministro_vapor=300.0)
    assert r.consigna == pytest.approx(300.0)


def test_consigna_sigue_a_dp():
    c = CascadaChaqueta()
    _ev(c, 199.0, 150.0, 0.0)
    for t in range(1, 11):
        r = _ev(c, 199.0, 150.0, float(t))
    assert r.consigna == pytest.approx(P_REF + MARGEN + 1.5)


# ── Congelamiento ───────────────────────────────────────────────────────────

def test_congelar_no_cambia_dp():
    c = CascadaChaqueta()
    _ev(c, 199.0, 150.0, 0.0)
    for t in range(1, 30):
        r = _ev(c, 190.0, 150.0, float(t), congelar=True)
    assert c.dp == pytest.approx(MARGEN)
    assert r.decision is True                   # la decisión no cambia (la prevalencia la aplica el llamador)


def test_tras_congelar_no_integra_de_golpe():
    c = CascadaChaqueta()
    _ev(c, 199.0, 150.0, 0.0)
    _ev(c, 199.0, 150.0, 1.0, congelar=True)
    _ev(c, 199.0, 150.0, 60.0, congelar=True)
    _ev(c, 199.0, 150.0, 61.0)
    assert c.dp == pytest.approx(MARGEN + 0.15)


@pytest.mark.parametrize("campo, valor", [("camara", None), ("camara", math.nan), ("camara", 0.0),
                                          ("chaqueta", None), ("chaqueta", -1.0),
                                          ("chaqueta", math.inf)])
def test_sin_lectura_no_integra(campo, valor):
    c = CascadaChaqueta()
    _ev(c, 199.0, 150.0, 0.0)
    for t in range(1, 10):
        pc, pj = (valor, 150.0) if campo == "camara" else (190.0, valor)
        r = _ev(c, pc, pj, float(t))
        assert r.decision is False
    assert c.dp == pytest.approx(MARGEN)
    _ev(c, 199.0, 150.0, 10.0)                   # vuelve la lectura: un tick normal
    assert c.dp == pytest.approx(MARGEN + 0.15)


@pytest.mark.parametrize("ahora", [None, math.nan, math.inf, "1", True])
def test_ahora_no_finito_falla_cerrada(ahora):
    c = CascadaChaqueta()
    _ev(c, 199.0, 150.0, 0.0)
    r = _ev(c, 190.0, 150.0, ahora)
    assert r.decision is False
    assert r.motivo == cc.MOTIVO_PARAMETROS_INVALIDOS
    assert c.dp == pytest.approx(MARGEN)


@pytest.mark.parametrize("p_baja", [math.nan, math.inf, "205", True])
def test_p_baja_no_finito_falla_cerrada(p_baja):
    c = CascadaChaqueta()
    r = _ev(c, 190.0, 150.0, 0.0, p_baja=p_baja)
    assert r.decision is False
    assert r.motivo == cc.MOTIVO_PARAMETROS_INVALIDOS
    assert c.dp is None


def test_parametros_invalidos_no_integran():
    c = CascadaChaqueta()
    _ev(c, 199.0, 150.0, 0.0)
    _ev(c, 190.0, 150.0, 1.0, p_ref=math.nan)
    assert c.dp == pytest.approx(MARGEN)


# ── Umbral del nivel baja ───────────────────────────────────────────────────

def test_p_baja_propio():
    c = CascadaChaqueta()
    assert _ev(c, 196.9, 150.0, 0.0, p_baja=197.0).nivel == cc.NIVEL_BAJA
    assert _ev(c, 197.0, 150.0, 0.0, p_baja=197.0).nivel == cc.NIVEL_BANDA
    # sin p_baja: p_ref - 2
    assert _ev(c, 197.5, 150.0, 0.0).nivel == cc.NIVEL_BAJA


def test_p_baja_nunca_sobre_p_ref_menos_1():
    c = CascadaChaqueta()
    # p_baja 205 > p_ref + 1: sin el recorte la cámara a 202 daría baja (350)
    r = _ev(c, 202.0, 150.0, 0.0, p_baja=205.0)
    assert r.nivel == cc.NIVEL_ALTA and r.decision is False
    assert _ev(c, 199.0, 150.0, 0.0, p_baja=205.0).nivel == cc.NIVEL_BANDA
    assert _ev(c, 198.9, 150.0, 0.0, p_baja=205.0).nivel == cc.NIVEL_BAJA


# ── Publicación y log ───────────────────────────────────────────────────────

def test_publica_dp():
    c = CascadaChaqueta()
    assert c.publicar()["dp"] is None
    _ev(c, 199.0, 150.0, 0.0)
    _ev(c, 199.0, 150.0, 1.0)
    assert c.publicar()["dp"] == pytest.approx(MARGEN + 0.15)


def _lineas(caplog):
    return [r.getMessage() for r in caplog.records
            if r.name == LOGGER and r.levelno == logging.INFO]


def test_log_por_cambio_de_dp_mayor_de_2(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    c = CascadaChaqueta()
    _ev(c, 199.0, 150.0, 0.0)                   # línea inicial
    assert len(_lineas(caplog)) == 1
    assert "dp=8.0" in _lineas(caplog)[0]
    # error 1 kPa: 0,15 kPa/s; a los 13 s dp sube 1,95 (sin línea)
    for t in range(1, 14):
        _ev(c, 199.0, 150.0, float(t))
    assert len(_lineas(caplog)) == 1
    _ev(c, 199.0, 150.0, 14.0)                   # 2,1 > 2: una línea
    assert len(_lineas(caplog)) == 2
    assert "dp=10.1" in _lineas(caplog)[-1]
    for t in range(15, 27):                      # 1,8 más: sin línea
        _ev(c, 199.0, 150.0, float(t))
    assert len(_lineas(caplog)) == 2


# ── ESTERILIZACION: herencia, integración y congelamiento ───────────────────

T_EST = 134.0
P_SP = p_saturacion_kpa(134.6)
TECHO = p_saturacion_kpa(T_EST) + 15.0


def _ester(monkeypatch, pres_chaqueta=250.0, pres=P_SP, temp=134.7, heredado="sin"):
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, presion_add=15.0,
                                       brecha_seg=0.3, temp=temp, pres=pres, tiempo_min=30)
    estado.modo_vapor = "chaqueta"
    estado.inhibir_vapor_chaqueta = False
    estado.sensores_pres["pres_chaqueta"] = pres_chaqueta
    base = f.cycle.get_param.side_effect
    f.cycle.get_param.side_effect = (
        lambda s, p, default=None: MARGEN if p == "margen_chaqueta_est" else base(s, p, default))
    estado.cascada_chaqueta = None if heredado == "sin" else heredado
    f.reset()
    return f, estado, set_do, reloj


def test_ester_hereda_dp_de_calentamiento(monkeypatch):
    f, estado, _, _ = _ester(monkeypatch, heredado={"nivel": None, "consigna": None,
                                                     "valvula": False, "dp": 21.0})
    assert estado.cascada_chaqueta is None       # reset limpia la publicación
    f.update()
    assert estado.cascada_chaqueta["dp"] == pytest.approx(21.0)
    assert estado.cascada_chaqueta["consigna"] == pytest.approx(P_SP + 21.0)


@pytest.mark.parametrize("heredado", ["sin", {"dp": None}, {"dp": math.nan}, {"nivel": "banda"},
                                      "texto", 5.0])
def test_ester_sin_herencia_valida_usa_el_margen(monkeypatch, heredado):
    f, estado, _, _ = _ester(monkeypatch, heredado=heredado)
    f.update()
    assert estado.cascada_chaqueta["dp"] == pytest.approx(MARGEN)


def test_ester_integra_en_la_banda(monkeypatch):
    f, estado, set_do, reloj = _ester(monkeypatch, pres=P_SP - 1.0)
    f.update()
    for _ in range(10):
        reloj.avanzar(0.5)
        f.update()
    assert estado.cascada_chaqueta["nivel"] == cc.NIVEL_BANDA
    assert estado.cascada_chaqueta["dp"] == pytest.approx(MARGEN + 0.15 * 5.0)


def test_ester_congela_con_aislamiento(monkeypatch):
    f, estado, set_do, reloj = _ester(monkeypatch)
    f.update()
    ap.poner(estado, 134.7, TECHO)               # aislamiento (error negativo)
    set_do.reset_mock()
    for _ in range(4):
        reloj.avanzar(0.5)
        f.update()
    assert f._aislamiento().aislado is True
    assert estado.cascada_chaqueta["dp"] == pytest.approx(MARGEN)
    set_do.vapor_chaqueta_on.assert_not_called()
    # la cámara cae a la banda con el aislamiento aún vigente (3 s): sigue congelada
    ap.poner(estado, 134.7, P_SP - 1.0)
    reloj.avanzar(0.5)
    f.update()
    assert f._aislamiento().aislado is True
    assert estado.cascada_chaqueta["dp"] == pytest.approx(MARGEN)


def test_ester_congela_con_inhibicion(monkeypatch):
    f, estado, set_do, reloj = _ester(monkeypatch, pres=P_SP - 1.0)
    f.update()
    estado.inhibir_vapor_chaqueta = True
    set_do.reset_mock()
    for _ in range(10):
        reloj.avanzar(0.5)
        f.update()
    set_do.vapor_chaqueta_on.assert_not_called()
    assert estado.cascada_chaqueta["dp"] == pytest.approx(MARGEN)
    assert estado.cascada_chaqueta["valvula"] is False


def test_ester_congela_sin_lectura_del_principal(monkeypatch):
    f, estado, set_do, reloj = _ester(monkeypatch, pres=P_SP - 1.0)
    f.update()
    estado.sensores_temp["temp_camara"] = None
    for _ in range(10):
        reloj.avanzar(0.5)
        f.update()
    assert estado.cascada_chaqueta["dp"] == pytest.approx(MARGEN)


def test_ester_congela_sin_lectura_de_chaqueta(monkeypatch):
    f, estado, set_do, reloj = _ester(monkeypatch, pres=P_SP - 1.0)
    f.update()
    estado.sensores_pres["pres_chaqueta"] = None
    for _ in range(10):
        reloj.avanzar(0.5)
        f.update()
    assert estado.cascada_chaqueta["nivel"] == cc.NIVEL_SIN_DATOS
    estado.sensores_pres["pres_chaqueta"] = 250.0
    reloj.avanzar(0.5)
    f.update()
    assert estado.cascada_chaqueta["dp"] == pytest.approx(MARGEN + 0.15 * 0.5)


def test_ester_banda_sobre_techo_menos_2(monkeypatch):
    """Caso del equipo: la consigna de banda puede quedar sobre techo - 2."""
    f, estado, set_do, _ = _ester(monkeypatch, heredado={"dp": 20.0})
    set_do.reset_mock()
    estado.sensores_pres["pres_chaqueta"] = TECHO
    f.update()
    assert estado.cascada_chaqueta["consigna"] == pytest.approx(P_SP + 20.0)
    assert estado.cascada_chaqueta["consigna"] > TECHO - 2.0
    set_do.vapor_chaqueta_on.assert_called()


# ── CALENTAMIENTO: integración, congelamiento y entrega de dp ───────────────

from tests import test_calentamiento_fase as tcal   # noqa: E402

T_OBJ = 134.0
P_OBJ = p_saturacion_kpa(T_OBJ)


@pytest.fixture
def reloj_cal(monkeypatch):
    ahora = [1000.0]
    monkeypatch.setattr(cal_mod, "time", types.SimpleNamespace(monotonic=lambda: ahora[0]))
    monkeypatch.setattr(cal_mod, "_ENCLAVE_T_OBJ_SOSTENIDO_S", 0.0)
    return ahora


def _cal(chaqueta=True, inhibir=False):
    fase, estado, set_do = tcal._make_fase(t_obj=T_OBJ, presion_add=11.0, tiempo_estable=600)
    original = fase.cycle.get_param.side_effect
    valores = {"tipo_carga": "solido", "presion_add_liquido_calentamiento": 0.0}
    fase.cycle.get_param.side_effect = (
        lambda s, p, default=None: valores[p] if p in valores else original(s, p, default))
    if chaqueta:
        estado.modo_vapor = "chaqueta"
        estado.inhibir_vapor_chaqueta = inhibir
    estado.sensores_pres["pres_chaqueta"] = 200.0
    fase.update()
    return fase, estado, set_do


def _a_sostenimiento(fase, estado):
    """Entra a ESTABLE_PREESTERILIZACION y da un tick más para que la cascada
    (que decide desde el tick siguiente a la entrada) quede inicializada."""
    _tick_cal(fase, estado, P_OBJ)
    assert fase._en_sostenimiento is True
    _tick_cal(fase, estado, P_OBJ)
    assert estado.cascada_chaqueta is not None


def _tick_cal(fase, estado, pres):
    estado.sensores_temp["temp_camara"] = T_OBJ
    estado.sensores_pres["pres_camara"] = pres
    return fase.update()


def test_cal_integra_en_sostenimiento(reloj_cal):
    fase, estado, _ = _cal()
    _a_sostenimiento(fase, estado)
    dp0 = estado.cascada_chaqueta["dp"]
    reloj_cal[0] += 1.0
    _tick_cal(fase, estado, P_OBJ - 1.0)
    assert estado.cascada_chaqueta["dp"] == pytest.approx(dp0 + 0.15)


def test_cal_congela_con_inhibicion(reloj_cal):
    fase, estado, set_do = _cal()
    _a_sostenimiento(fase, estado)
    dp0 = estado.cascada_chaqueta["dp"]
    estado.inhibir_vapor_chaqueta = True
    for _ in range(5):
        reloj_cal[0] += 1.0
        _tick_cal(fase, estado, P_OBJ - 1.0)
    assert estado.cascada_chaqueta["dp"] == pytest.approx(dp0)
    assert estado.cascada_chaqueta["valvula"] is False


def test_cal_completado_entrega_dp(reloj_cal):
    fase, estado, _ = _cal()
    _a_sostenimiento(fase, estado)
    reloj_cal[0] += 1.0
    _tick_cal(fase, estado, P_OBJ - 1.0)
    dp = fase._cascada.dp
    fase._apagar_salidas(completado=True)
    assert estado.cascada_chaqueta == {"nivel": None, "consigna": None, "valvula": False,
                                       "dp": pytest.approx(dp)}


def test_cal_fallo_no_entrega_dp(reloj_cal):
    fase, estado, _ = _cal()
    _a_sostenimiento(fase, estado)
    fase._apagar_salidas(completado=False)
    assert estado.cascada_chaqueta is None


def test_cal_completado_sin_cascada_no_entrega(reloj_cal):
    fase, estado, _ = _cal()
    assert fase._cascada.dp is None
    fase._apagar_salidas(completado=True)
    assert estado.cascada_chaqueta is None


def test_cal_completado_modo_camara_no_entrega(reloj_cal):
    fase, estado, _ = _cal(chaqueta=False)
    fase._cascada.dp = 12.0
    fase._apagar_salidas(completado=True)
    assert estado.cascada_chaqueta is None


def test_herencia_de_calentamiento_a_esterilizacion(monkeypatch, reloj_cal):
    """La dp que CALENTAMIENTO aprende llega a ESTERILIZACION por
    estado.cascada_chaqueta (CicloState: COMPLETADO -> siguiente.reset())."""
    fase, estado_cal, _ = _cal()
    _a_sostenimiento(fase, estado_cal)
    for _ in range(20):
        reloj_cal[0] += 1.0
        _tick_cal(fase, estado_cal, P_OBJ - 1.0)
    dp = fase._cascada.dp
    assert dp == pytest.approx(MARGEN + 0.15 * 20)
    fase._apagar_salidas(completado=True)
    f, estado, _, _ = _ester(monkeypatch, heredado=estado_cal.cascada_chaqueta)
    f.update()
    assert estado.cascada_chaqueta["dp"] == pytest.approx(dp)

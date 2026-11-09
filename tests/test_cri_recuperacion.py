"""CRI-02 (tanda 35, docs/mis_plans/planeacion_cascada_integral.md §3, §6.2):
brecha_segura_presion medida sobre Psat(T_est).

RECUPERACION entra con T < T_est + brecha_segura_temperatura o
P < Psat(T_est) + brecha_segura_presion y sale con T >= T_est + brecha + 0,3
y P >= Psat(T_est) + brecha_segura_presion + 1,0, en los dos modos. En modo
chaqueta, ESTERILIZACION: umbral «baja» de la cascada
p_baja = min(Psat(T_est) + brecha_segura_presion, P_sp - 1) (log una vez por
fase si recorta). ESTABLE_PREESTERILIZACION sigue en p_ref - 2.

Segunda revisión de seguridad, MEDIA-B: p_baja nunca bajo Psat(T_est) +
PISO_P_BAJA_KPA (salvo que el piso alcance P_sp - 1: rige P_sp - 1) y
brecha_segura_presion ausente o ilegible usa el valor de fábrica con aviso."""

import logging
import types

import pytest

from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import calentamiento as cal_mod
from autoclave.state_machine.cycle_phases import cascada_chaqueta as cc
from autoclave.state_machine.cycle_phases import esterilizacion as est
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests.helpers import t12_e12_apoyo as ap

pytestmark = pytest.mark.req("CRI-02")

T_EST = 134.0
PSAT = p_saturacion_kpa(T_EST)               # 304,20
BRECHA_P = 1.5
P_SP = p_saturacion_kpa(134.6)               # brecha_seg 0,3 + 0,3 ≈ 309,57
T_OK = 134.7                                 # sobre T_est + 0,3 + 0,3


def _fase(monkeypatch, modo=None, brecha_p=BRECHA_P, temp=T_OK, pres=PSAT + 5.0,
          pres_chaqueta=250.0):
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, presion_add=15.0,
                                       brecha_seg=0.3, brecha_seg_p=brecha_p,
                                       temp=temp, pres=pres, tiempo_min=30)
    if modo is not None:
        estado.modo_vapor = modo
        estado.inhibir_vapor_chaqueta = False
        estado.sensores_pres["pres_chaqueta"] = pres_chaqueta
        estado.cascada_chaqueta = None
        f.reset()
    return f, estado, set_do, reloj


def _tick(f, estado, reloj, pres, temp=T_OK):
    ap.poner(estado, temp, pres)
    reloj.avanzar(0.5)
    return f.update()


# ── Umbrales de RECUPERACION (los dos modos) ────────────────────────────────

@pytest.mark.parametrize("modo", [None, "chaqueta"])
def test_entra_bajo_psat_mas_brecha(monkeypatch, modo):
    f, estado, _, reloj = _fase(monkeypatch, modo)
    f.update()
    assert f._en_recuperacion is False           # PSAT + 5 sale en el primer tick
    _tick(f, estado, reloj, PSAT + BRECHA_P)       # en el umbral: no entra
    assert f._en_recuperacion is False
    _tick(f, estado, reloj, PSAT + BRECHA_P - 0.1)
    assert f._en_recuperacion is True


@pytest.mark.parametrize("modo", [None, "chaqueta"])
def test_entra_sobre_psat(monkeypatch, modo):
    """Antes (bajo Psat) PSAT + 1,0 no disparaba RECUPERACION; ahora sí."""
    f, estado, _, reloj = _fase(monkeypatch, modo)
    f.update()
    _tick(f, estado, reloj, PSAT + 1.0)
    assert f._en_recuperacion is True


@pytest.mark.parametrize("modo", [None, "chaqueta"])
def test_sale_con_psat_mas_brecha_mas_1(monkeypatch, modo):
    f, estado, _, reloj = _fase(monkeypatch, modo, pres=PSAT)
    f.update()
    assert f._en_recuperacion is True
    _tick(f, estado, reloj, PSAT + BRECHA_P + 0.9)
    assert f._en_recuperacion is True            # falta 0,1 kPa de histéresis
    _tick(f, estado, reloj, PSAT + BRECHA_P + 1.0)
    assert f._en_recuperacion is False


@pytest.mark.parametrize("modo", [None, "chaqueta"])
def test_salida_sigue_exigiendo_la_temperatura(monkeypatch, modo):
    f, estado, _, reloj = _fase(monkeypatch, modo, pres=PSAT, temp=T_EST)
    f.update()
    _tick(f, estado, reloj, PSAT + BRECHA_P + 2.0, temp=T_EST + 0.59)
    assert f._en_recuperacion is True
    _tick(f, estado, reloj, PSAT + BRECHA_P + 2.0, temp=T_EST + 0.61)
    assert f._en_recuperacion is False


def test_modo_camara_recuperacion_abre_vapor_camara(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch)
    f.update()
    set_do.reset_mock()
    _tick(f, estado, reloj, PSAT + 1.0)
    assert f._en_recuperacion is True
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_modo_camara_falla_sin_cambio(monkeypatch):
    """CIC-04 (Psat - brecha_error_presion) no cambia: RECUPERACION entra
    mucho antes, pero la falla sigue en el mismo umbral."""
    f, estado, _, reloj = _fase(monkeypatch)
    f.update()
    r = FaseResult.EN_CURSO
    for _ in range(12):
        r = _tick(f, estado, reloj, PSAT - 1.9)   # sobre Psat - 2: no falla
        assert r == FaseResult.EN_CURSO
    assert f._en_recuperacion is True


# ── Umbral «baja» de la cascada en ESTERILIZACION (modo chaqueta) ───────────

def test_p_baja_es_psat_mas_brecha(monkeypatch):
    f, _, _, _ = _fase(monkeypatch, "chaqueta")
    f.update()
    assert f._p_baja_cascada(PSAT, BRECHA_P) == pytest.approx(PSAT + BRECHA_P)
    assert PSAT + BRECHA_P < P_SP - 1.0


def test_nivel_baja_bajo_psat_mas_brecha(monkeypatch):
    f, estado, set_do, reloj = _fase(monkeypatch, "chaqueta")
    f.update()
    _tick(f, estado, reloj, PSAT + BRECHA_P - 0.1)
    assert estado.cascada_chaqueta["nivel"] == cc.NIVEL_BAJA
    assert estado.cascada_chaqueta["consigna"] == pytest.approx(350.0)
    # entre Psat + brecha y P_sp - 2 (antes «baja»): ahora banda
    _tick(f, estado, reloj, P_SP - 2.5)
    assert P_SP - 2.5 > PSAT + BRECHA_P
    assert estado.cascada_chaqueta["nivel"] == cc.NIVEL_BANDA


def test_p_baja_recortado_a_p_sp_menos_1_con_log_una_vez(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger=est.logger.name)
    brecha = 8.0                                  # Psat + 8 = 312,2 > P_sp - 1
    f, estado, _, reloj = _fase(monkeypatch, "chaqueta", brecha_p=brecha, pres=P_SP + 0.5)
    f.update()
    assert f._p_baja_cascada(PSAT, brecha) == pytest.approx(P_SP - 1.0)
    _tick(f, estado, reloj, P_SP - 1.1)
    assert estado.cascada_chaqueta["nivel"] == cc.NIVEL_BAJA
    _tick(f, estado, reloj, P_SP - 1.0)
    assert estado.cascada_chaqueta["nivel"] == cc.NIVEL_BANDA
    for _ in range(10):
        _tick(f, estado, reloj, P_SP)
    avisos = [r for r in caplog.records if r.name == est.logger.name
              and "CRI-02" in r.getMessage()]
    assert len(avisos) == 1
    # una vez por fase: el reset rearma el aviso
    f.reset()
    f.update()
    avisos = [r for r in caplog.records if r.name == est.logger.name
              and "CRI-02" in r.getMessage()]
    assert len(avisos) == 2


def test_sin_recorte_no_hay_aviso(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger=est.logger.name)
    f, estado, _, reloj = _fase(monkeypatch, "chaqueta")
    for _ in range(5):
        _tick(f, estado, reloj, P_SP)
    assert not [r for r in caplog.records if "CRI-02" in r.getMessage()]


# ── MEDIA-B (segunda revisión): piso de p_baja y brecha ilegible ────────────

def _avisos(caplog, marca="MEDIA-B"):
    return [r for r in caplog.records if r.name == est.logger.name and marca in r.getMessage()]


def test_piso_constante():
    assert est.PISO_P_BAJA_KPA == 1.5


@pytest.mark.req("CRI-02")
@pytest.mark.parametrize("brecha", [0.0, 0.5, 1.4])
def test_brecha_bajo_el_piso_usa_el_piso_con_log_una_vez(monkeypatch, caplog, brecha):
    """Antes, con brecha 0, p_baja = Psat(T_est): a 0,1 K de la falla de
    temperatura baja. Ahora p_baja = Psat(T_est) + 1,5."""
    caplog.set_level(logging.WARNING, logger=est.logger.name)
    f, estado, _, reloj = _fase(monkeypatch, "chaqueta", brecha_p=brecha)
    f.update()
    assert f._p_baja_cascada(PSAT, brecha) == pytest.approx(PSAT + est.PISO_P_BAJA_KPA)
    _tick(f, estado, reloj, PSAT + est.PISO_P_BAJA_KPA - 0.1)
    assert estado.cascada_chaqueta["nivel"] == cc.NIVEL_BAJA
    _tick(f, estado, reloj, PSAT + est.PISO_P_BAJA_KPA)
    assert estado.cascada_chaqueta["nivel"] == cc.NIVEL_BANDA
    for _ in range(5):
        _tick(f, estado, reloj, P_SP)
    assert len(_avisos(caplog)) == 1
    f.reset()
    f.update()
    assert len(_avisos(caplog)) == 2              # una vez por fase


def test_brecha_en_el_piso_sin_aviso(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger=est.logger.name)
    f, estado, _, reloj = _fase(monkeypatch, "chaqueta")    # brecha 1,5 = piso
    for _ in range(5):
        _tick(f, estado, reloj, P_SP)
    assert f._p_baja_cascada(PSAT, BRECHA_P) == pytest.approx(PSAT + BRECHA_P)
    assert not _avisos(caplog)


def test_piso_sobre_p_sp_menos_1_conserva_p_sp_menos_1(monkeypatch, caplog):
    """P_sp muy cerca de Psat(T_est) (p. ej. P_sp = Psat + 2): P_sp - 1 queda
    bajo el piso: rige P_sp - 1 (nunca se solapa con «alta») y se avisa una
    vez."""
    caplog.set_level(logging.WARNING, logger=est.logger.name)
    f, estado, _, reloj = _fase(monkeypatch, "chaqueta", brecha_p=0.0)
    f.p_sp = PSAT + 2.0
    tope = f.p_sp - 1.0
    assert PSAT + est.PISO_P_BAJA_KPA >= tope
    assert f._p_baja_cascada(PSAT, 0.0) == pytest.approx(tope)
    assert f._p_baja_cascada(PSAT, 0.0) == pytest.approx(tope)
    avisos = _avisos(caplog)
    assert len(avisos) == 1 and "se conserva" in avisos[0].getMessage()


@pytest.mark.parametrize("valor", [None, "1.5", float("nan"), float("inf"), -1.0, 25.0, True])
def test_brecha_ilegible_usa_el_defecto_con_aviso(monkeypatch, caplog, valor):
    """Sin `or 0.0`: ausente o ilegible usa el valor de fábrica (1,5 kPa) con
    aviso una vez por fase; afecta a RECUPERACION y a la cascada."""
    caplog.set_level(logging.WARNING, logger=est.logger.name)
    f, estado, _, reloj = _fase(monkeypatch, "chaqueta", brecha_p=valor)
    f.update()
    assert f._brecha_segura_presion() == pytest.approx(1.5)
    _tick(f, estado, reloj, PSAT + 1.4)
    assert f._en_recuperacion is True             # con 0 no habría entrado
    avisos = [r for r in _avisos(caplog) if "brecha_segura_presion" in r.getMessage()]
    assert len(avisos) == 1


def test_brecha_cero_valida_sin_aviso_de_defecto(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger=est.logger.name)
    f, _, _, _ = _fase(monkeypatch, "chaqueta", brecha_p=0.0)
    assert f._brecha_segura_presion() == 0.0
    assert not [r for r in _avisos(caplog) if "ausente o ilegible" in r.getMessage()]


@pytest.mark.parametrize("p_sat, brecha", [(float("nan"), 1.5), (PSAT, float("inf")),
                                           (None, 1.5), (PSAT, "1.5")])
def test_p_baja_sin_dato_valido_cae_al_umbral_anterior(monkeypatch, p_sat, brecha):
    f, _, _, _ = _fase(monkeypatch, "chaqueta")
    f.update()
    assert f._p_baja_cascada(p_sat, brecha) is None


def test_la_fase_pasa_p_baja_a_la_cascada(monkeypatch):
    f, estado, _, reloj = _fase(monkeypatch, "chaqueta")
    f.update()
    vistos = []
    original = f._cascada.evaluar

    def espia(*a, **kw):
        vistos.append(kw.get("p_baja"))
        return original(*a, **kw)
    f._cascada.evaluar = espia
    _tick(f, estado, reloj, P_SP)
    assert vistos == [pytest.approx(PSAT + BRECHA_P)]


# ── ESTABLE_PREESTERILIZACION sigue en p_ref - 2 ────────────────────────────

from tests import test_calentamiento_fase as tcal   # noqa: E402

P_OBJ = p_saturacion_kpa(T_EST)


@pytest.fixture
def reloj_cal(monkeypatch):
    ahora = [1000.0]
    monkeypatch.setattr(cal_mod, "time", types.SimpleNamespace(monotonic=lambda: ahora[0]))
    monkeypatch.setattr(cal_mod, "_ENCLAVE_T_OBJ_SOSTENIDO_S", 0.0)
    return ahora


def test_estable_preesterilizacion_no_pasa_p_baja(reloj_cal):
    fase, estado, _ = tcal._make_fase(t_obj=T_EST, presion_add=11.0, tiempo_estable=600)
    original = fase.cycle.get_param.side_effect
    valores = {"tipo_carga": "solido", "presion_add_liquido_calentamiento": 0.0,
               "brecha_segura_presion": 8.0}
    fase.cycle.get_param.side_effect = (
        lambda s, p, default=None: valores[p] if p in valores else original(s, p, default))
    estado.modo_vapor = "chaqueta"
    estado.inhibir_vapor_chaqueta = False
    estado.sensores_pres["pres_chaqueta"] = 200.0
    fase.update()
    vistos = []
    original_eval = fase._cascada.evaluar

    def espia(*a, **kw):
        vistos.append(kw.get("p_baja"))
        return original_eval(*a, **kw)
    fase._cascada.evaluar = espia
    for pres in (P_OBJ, P_OBJ, P_OBJ - 1.5):
        estado.sensores_temp["temp_camara"] = T_EST
        estado.sensores_pres["pres_camara"] = pres
        reloj_cal[0] += 0.5
        fase.update()
    assert fase._en_sostenimiento is True
    assert vistos and all(v is None for v in vistos)
    # P_OBJ - 1,5 está sobre p_ref - 2: banda (con brecha 8 sobre Psat sería baja)
    assert estado.cascada_chaqueta["nivel"] == cc.NIVEL_BANDA

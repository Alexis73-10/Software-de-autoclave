"""Tanda 28, A14: sobreimpulso en ESTERILIZACION y fallo por aislamiento CIC-16.

- M1: la banda PWM se ancla a P_sp = Psat(T_est + brecha_segura_temperatura +
  0,3), fija al entrar a la fase; advertencia de programa si P_sp + 1 >
  P_control_max - 5.
- M2: en modo chaqueta, vapor_chaqueta OFF con pres_chaqueta > consigna +
  margen_chaqueta_est (o sin lectura), en CALENTAMIENTO y ESTERILIZACION.
Reloj monotonic simulado (tests/helpers/t12_e12_apoyo.py)."""

import glob
import json
import logging
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import migrar_parametros
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import calentamiento as cal_mod
from autoclave.state_machine.cycle_phases import corte_chaqueta_consigna as ccc
from autoclave.state_machine.cycle_phases import esterilizacion as est
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.states.ciclo import CicloResultado
from tests import test_t16_s2_calentamiento_chaqueta as s2
from tests.helpers import t12_e12_apoyo as ap

CICLOS = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "cycles"

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


# ── M2: corte de vapor_chaqueta sobre la consigna + margen ─────────────────

def _ester_chaqueta(monkeypatch, pres_chaqueta, temp=134.0, pres=None, margen=None, **kw):
    """ESTERILIZACION en modo chaqueta; con T = T_est entra en RECUPERACION
    (la fase pide vapor_chaqueta ON)."""
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, presion_add=15.0,
                                       brecha_seg=0.3, tiempo_min=30, temp=temp,
                                       pres=p_saturacion_kpa(T_EST) if pres is None else pres,
                                       **kw)
    estado.modo_vapor = "chaqueta"
    estado.inhibir_vapor_chaqueta = False
    estado.sensores_pres["pres_chaqueta"] = pres_chaqueta
    if margen is not None:
        base = f.cycle.get_param.side_effect
        f.cycle.get_param.side_effect = (
            lambda s, p, default=None: margen if p == "margen_chaqueta_est" else base(s, p, default))
    return f, estado, set_do, reloj


def _ester_chaqueta_pwm_on(monkeypatch, pres_chaqueta, margen=None):
    """M2-REC-01: el corte M2 ya no rige en RECUPERACION ni bajo la banda; se
    prueba en PWM_ACTIVO dentro de la banda, en el tramo ON (t_on ≈ 29,7 s)."""
    return _ester_chaqueta(monkeypatch, pres_chaqueta, temp=134.7, pres=P_SP,
                           margen=margen, intervalo=30, factor=1.0)


def test_m2_ester_corta_sobre_p_sp_mas_margen_y_reabre_debajo(monkeypatch):
    umbral = P_SP + 8.0                                   # ≈ 317,6 kPa
    f, estado, set_do, reloj = _ester_chaqueta_pwm_on(monkeypatch, umbral + 0.1)
    f.update()
    assert f._en_recuperacion is False and f._pwm_abierto is True   # la fase pide ON
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_on.assert_called()               # la cámara no se toca
    # en el umbral (sin superarlo) reabre
    estado.sensores_pres["pres_chaqueta"] = umbral
    set_do.reset_mock()
    reloj.avanzar(0.5)
    f.update()
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_chaqueta_off.assert_not_called()
    # lo vuelve a superar: OFF otra vez
    estado.sensores_pres["pres_chaqueta"] = umbral + 1.0
    set_do.reset_mock()
    reloj.avanzar(0.5)
    f.update()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_m2_ester_usa_el_margen_del_programa(monkeypatch):
    f, _, set_do, _ = _ester_chaqueta_pwm_on(monkeypatch, P_SP + 4.0, margen=3.0)
    f.update()
    set_do.vapor_chaqueta_on.assert_not_called()
    f2, _, set_do2, _ = _ester_chaqueta_pwm_on(monkeypatch, P_SP + 4.0, margen=5.0)
    f2.update()
    set_do2.vapor_chaqueta_on.assert_called()


@pytest.mark.parametrize("lectura", [None, float("nan"), float("inf"), "300", True])
def test_m2_ester_sin_lectura_de_chaqueta_off(monkeypatch, lectura):
    f, _, set_do, _ = _ester_chaqueta(monkeypatch, lectura)
    f.update()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_on.assert_called()


def test_m2_ester_no_enciende_lo_que_la_fase_apaga(monkeypatch):
    """AND con la decisión de la fase: en PWM sobre la banda (OFF) una
    chaqueta baja no enciende nada."""
    f, estado, set_do, reloj = _ester_chaqueta(monkeypatch, 250.0, temp=134.7, pres=P_SP)
    f.update()
    assert f._en_recuperacion is False
    ap.poner(estado, 134.7, P_SP + 1.5)
    set_do.reset_mock()
    reloj.avanzar(0.5)
    f.update()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_m2_ester_no_reemplaza_d_chq(monkeypatch):
    f, estado, set_do, _ = _ester_chaqueta(monkeypatch, 250.0)
    estado.inhibir_vapor_chaqueta = True
    f.update()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_m2_ester_modo_camara_no_depende_de_la_chaqueta(monkeypatch):
    f, estado, set_do, _ = ap.fase(monkeypatch, t_est=T_EST, presion_add=15.0, brecha_seg=0.3)
    estado.sensores_pres.pop("pres_chaqueta", None)
    f.update()
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_not_called()


# ── M2 / H1: el corte se reevalúa en cada tick del tramo ON del PWM ────────
# intervalo 30 s y factor 1 % → t_on ≈ 29,7 s: antes de H1 el corte solo se
# evaluaba en la transición a ON y vapor_chaqueta seguía ON todo el tramo.

def _pwm_chaqueta_t_on_largo(monkeypatch, pres_chaqueta=250.0):
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, presion_add=15.0,
                                       brecha_seg=0.3, tiempo_min=30, temp=134.7, pres=P_SP,
                                       intervalo=30, factor=1.0)
    estado.modo_vapor = "chaqueta"
    estado.inhibir_vapor_chaqueta = False
    estado.sensores_pres["pres_chaqueta"] = pres_chaqueta
    assert f.update() == FaseResult.EN_CURSO
    assert f._en_recuperacion is False
    assert f._pwm_abierto is True                         # inicio del tramo ON
    set_do.vapor_chaqueta_on.assert_called()
    set_do.reset_mock()
    return f, estado, set_do, reloj


def test_h1_corte_por_consigna_durante_el_tramo_on(monkeypatch):
    f, estado, set_do, reloj = _pwm_chaqueta_t_on_largo(monkeypatch)
    reloj.avanzar(1.0)                                    # dentro de t_on
    estado.sensores_pres["pres_chaqueta"] = P_SP + 8.0 + 0.5
    f.update()
    assert f._pwm_abierto is True                         # el PWM no cambia de tramo
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_camara_on.assert_called()
    # sigue cortada en los ticks siguientes del mismo tramo
    set_do.reset_mock()
    reloj.avanzar(1.0)
    f.update()
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("lectura", [None, float("nan")])
def test_h1_perdida_de_lectura_de_chaqueta_durante_el_tramo_on(monkeypatch, lectura):
    f, estado, set_do, reloj = _pwm_chaqueta_t_on_largo(monkeypatch)
    reloj.avanzar(1.0)
    estado.sensores_pres["pres_chaqueta"] = lectura
    f.update()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_h1_inhibicion_d_chq_durante_el_tramo_on(monkeypatch):
    f, estado, set_do, reloj = _pwm_chaqueta_t_on_largo(monkeypatch)
    reloj.avanzar(1.0)
    estado.inhibir_vapor_chaqueta = True
    f.update()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_h1_tramo_off_no_enciende_la_chaqueta(monkeypatch):
    f, estado, set_do, reloj = _pwm_chaqueta_t_on_largo(monkeypatch)
    reloj.avanzar(29.8)                                   # pasa a OFF
    f.update()
    assert f._pwm_abierto is False
    set_do.vapor_chaqueta_off.assert_called()
    set_do.reset_mock()
    reloj.avanzar(0.1)                                    # sigue en t_off (0,3 s)
    f.update()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_h1_modo_camara_sin_cambio_en_el_tramo_on(monkeypatch):
    """Modo cámara: dentro de t_on no se reenvía nada y la chaqueta no se toca."""
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, presion_add=15.0,
                                       brecha_seg=0.3, tiempo_min=30, temp=134.7, pres=P_SP,
                                       intervalo=30, factor=1.0)
    estado.sensores_pres["pres_chaqueta"] = None
    f.update()
    assert f._en_recuperacion is False and f._pwm_abierto is True
    set_do.vapor_camara_on.assert_called()
    set_do.reset_mock()
    reloj.avanzar(1.0)
    f.update()
    assert f._pwm_abierto is True
    set_do.vapor_camara_on.assert_not_called()
    set_do.vapor_camara_off.assert_not_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_not_called()


# ── H1: pruebas pedidas por la revisión del commit 5a94e685 ───────────────
UMBRAL_EST = P_SP + 8.0                                   # P_sp + margen defecto


def _cortes_m2(caplog):
    inicio = [r for r in caplog.records
              if r.name == est.logger.name and "cortada por consigna" in r.getMessage()]
    fin = [r for r in caplog.records
           if r.name == est.logger.name and "fin del corte de vapor_chaqueta" in r.getMessage()]
    return len(inicio), len(fin)


def test_h1_corte_se_despeja_dentro_de_t_on_y_vuelve_a_on(monkeypatch):
    """(a) Comportamiento fijado: sin histéresis, si el corte se despeja dentro
    del tramo ON, vapor_chaqueta vuelve a ON en ese mismo tick y el tramo
    conserva su temporización (pasa a OFF al cumplirse t_on desde su inicio)."""
    f, estado, set_do, reloj = _pwm_chaqueta_t_on_largo(monkeypatch)
    inicio_tramo = f._t_pulso_pwm
    reloj.avanzar(1.0)
    estado.sensores_pres["pres_chaqueta"] = UMBRAL_EST + 0.5
    f.update()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.reset_mock()
    reloj.avanzar(1.0)
    estado.sensores_pres["pres_chaqueta"] = UMBRAL_EST - 0.5
    f.update()
    assert f._pwm_abierto is True and f._t_pulso_pwm == inicio_tramo
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_chaqueta_off.assert_not_called()
    # el tramo ON termina a los 29,7 s de su inicio, no se reinicia
    set_do.reset_mock()
    reloj.avanzar(27.8)                                   # 29,8 s desde el inicio
    f.update()
    assert f._pwm_abierto is False
    set_do.vapor_chaqueta_off.assert_called()


def test_h1_log_del_corte_una_vez_con_doble_llamada_en_la_transicion(monkeypatch, caplog):
    """(b) En el tick de transición a ON, _tick_dos_estados y el bloque H1
    llaman dos veces a _vapor_on: el inicio y el fin del corte M2 se registran
    una sola vez."""
    caplog.set_level(logging.INFO, logger=est.logger.name)
    # primer tick (temporizador sin armar): doble llamada con el corte ya activo
    f, estado, set_do, reloj = ap.fase(monkeypatch, t_est=T_EST, presion_add=15.0,
                                       brecha_seg=0.3, tiempo_min=30, temp=134.7, pres=P_SP,
                                       intervalo=30, factor=1.0)
    estado.modo_vapor = "chaqueta"
    estado.inhibir_vapor_chaqueta = False
    estado.sensores_pres["pres_chaqueta"] = UMBRAL_EST + 0.5
    llamadas = MagicMock(wraps=f._vapor_on)
    monkeypatch.setattr(f, "_vapor_on", llamadas)
    f.update()
    assert llamadas.call_count == 2                       # la doble llamada existe
    assert _cortes_m2(caplog) == (1, 0)
    set_do.vapor_chaqueta_on.assert_not_called()
    # se despeja: un solo registro de fin
    reloj.avanzar(1.0)
    estado.sensores_pres["pres_chaqueta"] = UMBRAL_EST - 0.5
    f.update()
    assert _cortes_m2(caplog) == (1, 1)
    # pasa a OFF (sin evaluar el corte) y vuelve a ON con el corte activo:
    # transición OFF -> ON con doble llamada, un solo registro de inicio
    reloj.avanzar(28.8)
    f.update()
    assert f._pwm_abierto is False
    estado.sensores_pres["pres_chaqueta"] = UMBRAL_EST + 0.5
    llamadas.reset_mock()
    set_do.reset_mock()
    reloj.avanzar(0.4)                                    # t_off = 0,3 s cumplido
    f.update()
    assert f._pwm_abierto is True and llamadas.call_count == 2
    assert _cortes_m2(caplog) == (2, 1)
    set_do.vapor_chaqueta_on.assert_not_called()
    # siguen ticks con el corte: sin registros nuevos
    reloj.avanzar(1.0)
    f.update()
    assert _cortes_m2(caplog) == (2, 1)


def test_h1_aislamiento_a_mitad_del_tramo_on_con_el_corte_activo(monkeypatch):
    """(c) Corte por consigna activo y, en un tick posterior del mismo tramo
    ON, la cámara llega al techo: VCH-AIS fuerza las dos válvulas OFF y el
    bloque H1 no corre (ni _vapor_on)."""
    f, estado, set_do, reloj = _pwm_chaqueta_t_on_largo(monkeypatch)
    reloj.avanzar(1.0)
    estado.sensores_pres["pres_chaqueta"] = UMBRAL_EST + 0.5
    f.update()
    assert f._corte_m2_previo is True and f._pwm_abierto is True
    llamadas = MagicMock(wraps=f._vapor_on)
    monkeypatch.setattr(f, "_vapor_on", llamadas)
    set_do.reset_mock()
    reloj.avanzar(1.0)
    ap.poner(estado, 134.7, p_saturacion_kpa(T_EST) + 15.0)   # techo P_control_max
    assert f.update() == FaseResult.EN_CURSO
    assert f._aislamiento().aislado is True
    assert f._pwm_abierto is False and f._t_pulso_pwm is None
    llamadas.assert_not_called()
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_h1_bajo_p_low_con_el_corte_activo(monkeypatch):
    """(e) Rama P < p_low (ON forzado) con pres_chaqueta sobre el umbral M2.
    Ajustada por M2-REC-01 (7-nov): bajo la banda la cámara necesita vapor y el
    corte M2 no aplica, así que vapor_chaqueta queda ON (antes OFF); al volver
    dentro de la banda con el tramo ON el corte rige otra vez."""
    f, estado, set_do, reloj = _pwm_chaqueta_t_on_largo(monkeypatch)
    reloj.avanzar(1.0)
    ap.poner(estado, 134.7, P_SP - est._BANDA_PWM_BAJA - 0.5)
    estado.sensores_pres["pres_chaqueta"] = UMBRAL_EST + 0.5
    f.update()
    assert f._en_recuperacion is False
    assert f._pwm_abierto is True and f._t_pulso_pwm is None   # rama ON forzado
    assert f._exencion_m2 == ccc.MOTIVO_BAJO_BANDA
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_chaqueta_off.assert_not_called()
    set_do.vapor_camara_on.assert_called()
    set_do.reset_mock()
    reloj.avanzar(1.0)
    ap.poner(estado, 134.7, P_SP)
    f.update()
    assert f._exencion_m2 is None
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


def _ordenes_chaqueta(set_do):
    return [c[0] for c in set_do.mock_calls
            if c[0] in ("vapor_chaqueta_on", "vapor_chaqueta_off")]


def test_h1_integracion_cicloestate_corte_por_consigna_en_el_tick(monkeypatch):
    """(d) CicloState real con la EsterilizacionFase real, orden real del tick
    (fase.update() y luego el corte D-CHQ de ciclo.py, paso 7): con
    pres_chaqueta sobre P_sp + margen pero bajo presion_max_chaqueta_control
    (D-CHQ inactivo), vapor_chaqueta queda OFF en el mismo tick en que aparece
    el corte por consigna a mitad del tramo ON; lo apaga la fase, no CICLO."""
    from autoclave.installation.profile import MODO_CHAQUETA
    from tests import test_t16_s3_ciclo_chaqueta as s3

    f, _, _, reloj = ap.fase(monkeypatch, t_est=T_EST, presion_add=15.0, brecha_seg=0.3,
                             tiempo_min=30, intervalo=30, factor=1.0)
    ciclo, estado, set_do, _ = s3._ciclo(pres_chaqueta=250.0, modo=MODO_CHAQUETA)
    estado.sensores_temp["temp_camara"] = 134.7
    estado.sensores_pres["pres_camara"] = P_SP
    estado.avisos_ciclo = []
    f.estado, f.set_do = estado, set_do
    f.reset()
    s3._con_fases(ciclo, f)
    assert f.controla_vapor_chaqueta is True

    assert ciclo.run() == CicloResultado.EN_CURSO        # inicio del tramo ON
    assert f._pwm_abierto is True and estado.inhibir_vapor_chaqueta is False
    assert _ordenes_chaqueta(set_do)[-1] == "vapor_chaqueta_on"

    set_do.reset_mock()
    reloj.avanzar(1.0)
    estado.sensores_pres["pres_chaqueta"] = UMBRAL_EST + 0.5   # < 375 kPa
    assert ciclo.run() == CicloResultado.EN_CURSO
    assert estado.inhibir_vapor_chaqueta is False         # D-CHQ no actúa
    assert f._pwm_abierto is True
    assert _ordenes_chaqueta(set_do) and set(_ordenes_chaqueta(set_do)) == {"vapor_chaqueta_off"}

    set_do.reset_mock()
    reloj.avanzar(1.0)
    estado.sensores_pres["pres_chaqueta"] = UMBRAL_EST - 0.5
    ciclo.run()
    assert _ordenes_chaqueta(set_do)[-1] == "vapor_chaqueta_on"


@pytest.fixture
def reloj_cal(monkeypatch):
    ahora = [1000.0]
    monkeypatch.setattr(cal_mod, "time", types.SimpleNamespace(monotonic=lambda: ahora[0]))
    return ahora


def _cal_chaqueta(pres_chaqueta, margen=None):
    extra = {"margen_chaqueta_est": margen} if margen is not None else None
    fase, estado, set_do = s2._fase(extra=extra)
    estado.sensores_pres["pres_chaqueta"] = pres_chaqueta
    return fase, estado, set_do


def test_m2_calentamiento_usa_el_techo_de_la_fase(reloj_cal):
    """En CALENTAMIENTO P_sp aún no existe: consigna Psat(T_obj) +
    presion_add_calentamiento."""
    umbral = p_saturacion_kpa(s2.T_OBJ) + s2.P_ADD + 8.0
    fase, estado, set_do = _cal_chaqueta(umbral + 0.1)
    assert fase.update() == FaseResult.EN_CURSO          # lejos del objetivo: duty 1
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_on.assert_called()
    estado.sensores_pres["pres_chaqueta"] = umbral
    set_do.reset_mock()
    reloj_cal[0] += 0.5
    fase.update()
    set_do.vapor_chaqueta_on.assert_called()


def test_m2_calentamiento_usa_el_margen_del_programa(reloj_cal):
    umbral = p_saturacion_kpa(s2.T_OBJ) + s2.P_ADD
    fase, _, set_do = _cal_chaqueta(umbral + 4.0, margen=3.0)
    fase.update()
    set_do.vapor_chaqueta_on.assert_not_called()


@pytest.mark.parametrize("lectura", [None, float("nan")])
def test_m2_calentamiento_sin_lectura_off(reloj_cal, lectura):
    fase, _, set_do = _cal_chaqueta(lectura)
    fase.update()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_camara_on.assert_called()


def test_m2_calentamiento_no_reemplaza_d_chq(reloj_cal):
    fase, estado, set_do = _cal_chaqueta(250.0)
    estado.inhibir_vapor_chaqueta = True
    fase.update()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_m2_calentamiento_modo_camara_sin_cambio(reloj_cal):
    fase, estado, set_do = s2._fase(chaqueta=False)
    estado.sensores_pres.pop("pres_chaqueta", None)
    fase.update()
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_m2_debe_cortar_puro():
    assert ccc.debe_cortar(318.0, 309.6, 8.0) is True
    assert ccc.debe_cortar(317.6, 309.6, 8.0) is False
    assert ccc.debe_cortar(None, 309.6, 8.0) is True
    assert ccc.debe_cortar(300.0, None, 8.0) is True
    assert ccc.debe_cortar(300.0, 309.6, float("nan")) is True


@pytest.mark.parametrize("valor,esperado", [(8.0, 8.0), (1.0, 2.0), (31.0, 30.0), (None, 8.0),
                                            ("8", 8.0), (True, 8.0), (float("nan"), 8.0)])
def test_m2_margen_recortado(valor, esperado):
    cycle = MagicMock()
    cycle.get_param.return_value = valor
    assert ccc.margen_kpa(cycle) == esperado


# ── M2: parámetro margen_chaqueta_est ───────────────────────────────────────

def test_m2_catalogo_margen():
    hoja = {"type": "float"}
    assert cp.MARGEN_CHAQUETA_EST_DEFECTO == ccc.MARGEN_DEFECTO_KPA == 8.0
    assert cp.coercionar(hoja, "esterilizacion", ["margen_chaqueta_est"], 2) == 2
    assert cp.coercionar(hoja, "esterilizacion", ["margen_chaqueta_est"], 30) == 30
    for malo in (1.9, 30.1, "8", True, float("nan")):
        with pytest.raises(ValueError):
            cp.coercionar(hoja, "esterilizacion", ["margen_chaqueta_est"], malo)


@pytest.mark.parametrize("ruta", sorted(glob.glob(str(CICLOS / "*" / "*.json"))))
def test_m2_programas_del_repo_con_margen(ruta):
    p = json.loads(Path(ruta).read_text(encoding="utf-8"))["parameters"]
    hoja = p["esterilizacion"]["margen_chaqueta_est"]
    assert (hoja["value"], hoja["type"], hoja["unit"], hoja["clase"], hoja["min"], hoja["max"]) \
        == (8.0, "float", "kPa", "diferencia", 2, 30)
    claves = list(p["esterilizacion"])
    assert claves[claves.index("histeresis_cierre_camara") + 1] == "margen_chaqueta_est"


def _params_134():
    return json.loads((CICLOS / "factory" / "instrumental_134.json")
                      .read_text(encoding="utf-8"))["parameters"]


def test_m2_migracion_agrega_el_defecto_sin_aviso():
    p = _params_134()
    del p["esterilizacion"]["margen_chaqueta_est"]
    corr = []
    assert migrar_parametros(p, corr) is True
    assert corr == []
    claves = list(p["esterilizacion"])
    assert claves[claves.index("histeresis_cierre_camara") + 1] == "margen_chaqueta_est"
    assert p["esterilizacion"]["margen_chaqueta_est"]["value"] == 8.0
    assert cp.errores_programa(p) == []
    assert migrar_parametros(p, corr) is False


def test_m2_programa_fuera_de_rango_no_valida():
    p = _params_134()
    p["esterilizacion"]["margen_chaqueta_est"]["value"] = 40.0
    assert any("margen_chaqueta_est" in e for e in cp.errores_programa(p))


def test_m2_textos_i18n():
    from autoclave import i18n
    for idioma in ("es", "en"):
        for clave in ("parametros.esterilizacion.margen_chaqueta_est",
                      "parametros_desc.esterilizacion.margen_chaqueta_est"):
            assert i18n.existe(clave, idioma), (clave, idioma)

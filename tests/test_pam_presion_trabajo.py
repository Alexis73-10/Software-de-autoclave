"""PAM (9-nov, docs/mis_plans/planeacion_presion_add_margen.md): la presión
añadida como margen de trabajo sobre la saturación.

PAM-01 empuje sólido a p_techo - (histeresis_cierre + 1) hasta el enclave de
t_obj (5 s, toda carga); PAM-02 P_trabajo y su adaptación; PAM-03 entrada y
sostenimiento con P_trabajo; PAM-04 herencia de d en ESTERILIZACION (P_sp, log
y ticket); PAM-05 margen de aire en kPa (C-03 y C-02), nunca más de 2 K;
PAM-06 regla brecha_segura_presion < brecha_error_presion (rechazo al guardar,
SIS-06 sin migrar al cargar). Reloj monotonic simulado."""
import logging
import types

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.services.domain.logging import ticket_formatter as tf
from autoclave.state_machine.cycle_phases import calentamiento as cal
from autoclave.state_machine.cycle_phases import esterilizacion as est_mod
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from tests import test_calentamiento_fase as tcal
from tests.helpers import planta_vapor as pv
from tests.helpers import t12_e12_apoyo as ap

pytestmark = pytest.mark.req("PAM")

T_OBJ = 121.0
P_ADD = 11.0
P_OBJ = p_saturacion_kpa(T_OBJ)          # 205,04
P_TECHO = P_OBJ + P_ADD                  # 216,04
TOPE = P_TECHO - 4.0                     # histeresis 3 + 1 -> 212,04


@pytest.fixture
def reloj(monkeypatch):
    ahora = [1000.0]
    monkeypatch.setattr(cal, "time", types.SimpleNamespace(monotonic=lambda: ahora[0]))
    return ahora


def _fase(carga="solido", extra=15.0, chaqueta=False, tiempo_estable=30, p_add=P_ADD):
    fase, estado, set_do = tcal._make_fase(t_obj=T_OBJ, presion_add=p_add,
                                           tiempo_estable=tiempo_estable)
    original = fase.cycle.get_param.side_effect
    valores = {"tipo_carga": carga, "presion_add_liquido_calentamiento": extra}

    def get_param(seccion, param, default=None):
        if param in valores:
            return valores[param]
        return original(seccion, param, default)
    fase.cycle.get_param.side_effect = get_param
    if chaqueta:
        estado.modo_vapor = "chaqueta"
        estado.inhibir_vapor_chaqueta = False
        estado.sensores_pres["pres_chaqueta"] = 225.0
    fase.update()   # inicializa
    return fase, estado, set_do


def _tick(fase, estado, temp, pres):
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = pres
    return fase.update()


def _enclavar(fase, estado, reloj, temp, pres):
    _tick(fase, estado, temp, pres)
    reloj[0] += 6.0
    return _tick(fase, estado, temp, pres)


# ── 6.1: constantes y funciones puras ─────────────────────────────────────

def test_constantes():
    assert cal.PASO_TRABAJO_KPA == 1.0
    assert cal.margen_empuje_kpa(3.0) == 4.0
    assert cal.TOLERANCIA_ENTRADA_TRABAJO_KPA == 1.0


def test_tope_y_clamp_de_la_presion_de_trabajo():
    assert cal.tope_trabajo_kpa(P_OBJ, P_TECHO, 4.0) == pytest.approx(TOPE)
    # presion_add menor que el margen: el tope no baja de Psat(t_obj)
    assert cal.tope_trabajo_kpa(P_OBJ, P_OBJ + 2.0, 4.0) == pytest.approx(P_OBJ)
    assert cal.presion_trabajo_kpa(227.0, P_OBJ, TOPE) == pytest.approx(TOPE)
    assert cal.presion_trabajo_kpa(200.0, P_OBJ, TOPE) == pytest.approx(P_OBJ)
    assert cal.presion_trabajo_kpa(209.0, P_OBJ, TOPE) == pytest.approx(209.0)


@pytest.mark.parametrize("t", [100.0, 121.0, 134.0, 140.0])
@pytest.mark.parametrize("add", [0.0, 5.0, 11.0, 15.0, 30.0, None, "x", -3.0])
def test_tolerancia_de_aire_nunca_supera_2_k(t, add):
    dos_k = p_saturacion_kpa(t + 2.0) - p_saturacion_kpa(t)
    tol = cal.tolerancia_aire_kpa(t, add)
    assert 0.0 <= tol <= dos_k + 1e-9
    if isinstance(add, float) and add >= 0:
        assert tol == pytest.approx(min(add, dos_k))
    if add is None or add == "x":
        assert tol == pytest.approx(dos_k)


def test_tolerancia_de_aire_sin_temperatura_valida_es_none():
    assert cal.tolerancia_aire_kpa(None, 11.0) is None
    assert cal.tolerancia_aire_kpa(float("nan"), 11.0) is None


# ── PAM-01: empuje sólido ─────────────────────────────────────────────────

def test_solido_empuja_hasta_el_tope_antes_del_enclave():
    fase, estado, _ = _fase("solido")
    # 3 kPa bajo el tope (con rango_calentamiento 2 kPa): proximidad 1
    _tick(fase, estado, 110.0, TOPE - 3.0)
    assert fase._duty_actual == 1.0
    # sobre el tope + rango de presión: sin vapor
    _tick(fase, estado, 110.0, TOPE + 2.5)
    assert fase._duty_actual == 0.0
    assert fase._t_obj_alcanzada is False


def test_liquido_con_extra_conserva_el_empuje_del_ajuste_7nov():
    fase, estado, _ = _fase("liquido", extra=20.0)
    _tick(fase, estado, 110.0, P_OBJ + 17.0)       # bajo Psat + 20 (no el tope sólido)
    assert fase._duty_actual == 1.0
    _tick(fase, estado, 110.0, P_TECHO + 20.0 + 0.5)   # techo ampliado
    assert fase._duty_actual == 0.0


def test_presion_add_menor_que_el_margen_es_el_comportamiento_anterior():
    fase, estado, _ = _fase("solido", p_add=3.0)
    _tick(fase, estado, 110.0, P_OBJ + 0.5)        # sobre Psat(t_obj): sin vapor
    assert fase._duty_actual < 1.0


# ── PAM-02: P_trabajo ─────────────────────────────────────────────────────

def test_sin_enclave_no_hay_presion_de_trabajo_ni_entrada(reloj):
    fase, estado, _ = _fase("solido")
    assert estado.presion_trabajo is None and estado.desfase_trabajo is None
    _tick(fase, estado, T_OBJ, P_OBJ + 3.0)        # un solo tick con T >= t_obj
    reloj[0] += 4.0
    _tick(fase, estado, T_OBJ, P_OBJ + 3.0)
    assert fase._t_obj_alcanzada is False
    assert fase._en_sostenimiento is False
    assert estado.presion_trabajo is None


@pytest.mark.parametrize("temp,pres", [(T_OBJ, float("nan")), (T_OBJ, float("inf"))])
def test_lectura_no_finita_no_enclava(reloj, temp, pres):
    # revisión M2 (9-nov): una presión NaN/inf no cuenta para el enclave ni fija
    # P_trabajo. (Una temperatura NaN no llega a la fase: EstadoAutoclave.update
    # la publica como None, P7 de la tanda 16; la rampa con NaN lanza en
    # p_saturacion_kpa, comportamiento anterior a PAM.)
    fase, estado, _ = _fase("solido")
    _tick(fase, estado, temp, pres)
    reloj[0] += 6.0
    _tick(fase, estado, temp, pres)
    assert fase._t_obj_alcanzada is False
    assert fase._p_trabajo is None and estado.presion_trabajo is None


def test_fijar_presion_trabajo_no_finita_no_fija(caplog):
    caplog.set_level(logging.ERROR)
    fase, estado, _ = _fase("solido")
    fase._fijar_presion_trabajo(float("nan"), P_OBJ, TOPE)
    assert fase._p_trabajo is None and estado.desfase_trabajo is None
    assert "no finitos" in caplog.text


def test_enclave_fija_p_trabajo_y_publica_el_desfase(reloj, caplog):
    caplog.set_level(logging.INFO)
    fase, estado, _ = _fase("solido")
    _enclavar(fase, estado, reloj, T_OBJ, P_OBJ + 6.0)
    assert fase._t_obj_alcanzada is True
    assert estado.presion_trabajo == pytest.approx(P_OBJ + 6.0)
    assert estado.desfase_trabajo == pytest.approx(6.0)
    assert "presión de trabajo fijada" in caplog.text


@pytest.mark.parametrize("pres,esperada", [(P_OBJ + 22.0, TOPE), (P_OBJ - 1.0, P_OBJ)])
def test_p_trabajo_queda_entre_psat_y_el_tope(reloj, pres, esperada):
    fase, estado, _ = _fase("liquido", extra=20.0)
    _enclavar(fase, estado, reloj, T_OBJ, pres)
    assert estado.presion_trabajo == pytest.approx(esperada)
    assert estado.desfase_trabajo == pytest.approx(esperada - P_OBJ)


def test_reinicio_con_principal_bajo_t_obj_sube_1_kpa_una_vez_por_reinicio(reloj, caplog):
    caplog.set_level(logging.INFO)
    fase, estado, _ = _fase("solido")
    _enclavar(fase, estado, reloj, T_OBJ, P_OBJ + 4.0)
    assert fase._en_sostenimiento is True
    for _ in range(4):                              # 4 ticks fuera: una sola subida
        _tick(fase, estado, T_OBJ - 0.3, P_OBJ + 4.0)
    assert estado.presion_trabajo == pytest.approx(P_OBJ + 5.0)
    assert "sube de" in caplog.text
    _tick(fase, estado, T_OBJ + 0.2, P_OBJ + 5.0)   # dentro: rearma
    _tick(fase, estado, T_OBJ - 0.3, P_OBJ + 5.0)   # segundo reinicio
    assert estado.presion_trabajo == pytest.approx(P_OBJ + 6.0)


def test_p_trabajo_nunca_supera_el_tope(reloj):
    fase, estado, _ = _fase("solido")
    _enclavar(fase, estado, reloj, T_OBJ, TOPE - 0.5)
    for _ in range(10):
        _tick(fase, estado, T_OBJ + 0.2, TOPE)
        _tick(fase, estado, T_OBJ - 0.3, TOPE)
        assert estado.presion_trabajo <= TOPE + 1e-9
    assert estado.presion_trabajo == pytest.approx(TOPE)


def test_reinicio_por_presion_no_sube(reloj):
    fase, estado, _ = _fase("solido")
    _enclavar(fase, estado, reloj, T_OBJ, P_OBJ + 6.0)
    _tick(fase, estado, T_OBJ + 0.2, P_OBJ - 3.0)    # fuera por presión, T en banda
    assert estado.presion_trabajo == pytest.approx(P_OBJ + 6.0)


def test_reset_limpia_la_presion_de_trabajo(reloj):
    fase, estado, _ = _fase("solido")
    _enclavar(fase, estado, reloj, T_OBJ, P_OBJ + 6.0)
    fase.reset()
    assert fase._p_trabajo is None
    assert estado.presion_trabajo is None and estado.desfase_trabajo is None


def test_estado_autoclave_sin_presion_de_trabajo():
    estado = EstadoAutoclave()
    assert estado.presion_trabajo is None
    assert estado.desfase_trabajo is None


# ── PAM-03: entrada y sostenimiento ───────────────────────────────────────

def test_liquido_tras_el_empuje_sin_vapor_hasta_p_trabajo_mas_1(reloj):
    fase, estado, set_do = _fase("liquido", extra=20.0)
    _enclavar(fase, estado, reloj, T_OBJ, P_OBJ + 22.0)   # P_trabajo = TOPE (212,0)
    _tick(fase, estado, T_OBJ, TOPE + 1.5)
    assert fase._duty_actual == 0.0
    assert fase._en_sostenimiento is False
    _tick(fase, estado, T_OBJ, TOPE + 0.8)          # ejemplo 3.7: entra con P <= 213,0
    assert fase._en_sostenimiento is True


def test_entrada_exige_psat_menos_2(reloj):
    fase, estado, _ = _fase("solido")
    _enclavar(fase, estado, reloj, T_OBJ, P_OBJ - 2.5)
    assert fase._en_sostenimiento is False


def test_sostenimiento_modo_camara_apunta_a_p_trabajo(reloj):
    fase, estado, _ = _fase("solido")
    _enclavar(fase, estado, reloj, T_OBJ, P_OBJ + 6.0)
    assert fase._en_sostenimiento is True
    # 3 kPa bajo P_trabajo: hay aporte de vapor (lo limita solo la
    # temperatura); con la referencia anterior (Psat) el sobrepaso de presión
    # (3 kPa > rango 2) lo dejaría en 0
    _tick(fase, estado, T_OBJ + 0.2, P_OBJ + 3.0)
    assert fase._duty_actual > 0.0


def test_sostenimiento_modo_chaqueta_cascada_con_p_ref_p_trabajo(reloj):
    fase, estado, _ = _fase("solido", chaqueta=True)
    _enclavar(fase, estado, reloj, T_OBJ, P_OBJ + 6.0)
    assert fase._en_sostenimiento is True
    # P = P_trabajo: nivel banda (con p_ref = Psat sería «alta»)
    _tick(fase, estado, T_OBJ + 0.2, P_OBJ + 6.0)
    assert estado.cascada_chaqueta["nivel"] == "banda"


def test_banda_de_sostenimiento_sin_cambio(reloj):
    fase, estado, _ = _fase("solido")
    _enclavar(fase, estado, reloj, T_OBJ, P_OBJ + 6.0)
    _tick(fase, estado, T_OBJ + 0.2, P_TECHO + 0.5)   # sobre el techo: fuera
    assert fase._timer_sostenido_desde is None
    _tick(fase, estado, T_OBJ + 0.2, P_OBJ - 1.5)     # Psat - 2 <= P: dentro
    assert fase._timer_sostenido_desde is not None


def test_sin_lectura_no_enclava_ni_inyecta(reloj):
    fase, estado, set_do = _fase("solido")
    _tick(fase, estado, T_OBJ, P_OBJ + 6.0)
    reloj[0] += 6.0
    set_do.reset_mock()
    _tick(fase, estado, T_OBJ, None)
    assert fase._t_obj_alcanzada is False
    set_do.vapor_camara_on.assert_not_called()


# ── PAM-05: C-02 (CALENTAMIENTO) ──────────────────────────────────────────

def test_c02_lado_de_aire_en_kpa_nunca_mas_de_2_k(reloj):
    # presion_add 30 > 2 K (≈13,2 kPa a 121 °C): el margen queda en 2 K
    fase, estado, _ = _fase("solido", p_add=30.0)
    dos_k = p_saturacion_kpa(T_OBJ + 2.0) - P_OBJ
    _enclavar(fase, estado, reloj, T_OBJ, P_OBJ + 6.0)
    _tick(fase, estado, T_OBJ, P_OBJ + dos_k - 0.3)
    assert fase._coherente_previo is True
    _tick(fase, estado, T_OBJ, P_OBJ + dos_k + 0.3)
    assert fase._coherente_previo is False
    assert fase._timer_sostenido_desde is None


def test_c02_lado_de_vapor_sin_cambio(reloj, caplog):
    caplog.set_level(logging.WARNING)
    fase, estado, _ = _fase("solido")
    _enclavar(fase, estado, reloj, T_OBJ, P_OBJ + 1.0)
    # T 1,15 K sobre Tsat(P), dentro de la banda de T y de P
    _tick(fase, estado, T_OBJ + 1.0, p_saturacion_kpa(T_OBJ - 0.15))
    assert fase._coherente_previo is False
    assert "kPa" in caplog.text


# ── PAM-04: herencia en ESTERILIZACION ────────────────────────────────────

def test_consigna_heredada_ejemplo_3_7():
    p_calc = EsterilizacionFase.consigna_pwm(T_OBJ, 0.3)
    p, origen = EsterilizacionFase.consigna_heredada(p_calc, P_OBJ, 7.0, P_TECHO)
    assert p == pytest.approx(P_OBJ + 7.0)                 # 212,0
    assert origen == "heredada"


@pytest.mark.parametrize("d", [None, 0.0, -1.0, float("nan"), "x"])
def test_d_sin_dato_es_el_comportamiento_anterior(d):
    p_calc = EsterilizacionFase.consigna_pwm(T_OBJ, 0.3)
    assert EsterilizacionFase.consigna_heredada(p_calc, P_OBJ, d, P_TECHO) == (p_calc, "calculada")


def test_consigna_heredada_con_tope_bajo_el_techo():
    p_calc = EsterilizacionFase.consigna_pwm(T_OBJ, 0.3)
    p, origen = EsterilizacionFase.consigna_heredada(p_calc, P_OBJ, 20.0, P_TECHO)
    assert p == pytest.approx(P_TECHO - 3.0)
    assert origen == "heredada"


def test_d_pequeno_conserva_la_calculada():
    p_calc = EsterilizacionFase.consigna_pwm(T_OBJ, 0.3)    # ≈ Psat(121,6)
    p, origen = EsterilizacionFase.consigna_heredada(p_calc, P_OBJ, 0.5, P_TECHO)
    assert (p, origen) == (p_calc, "calculada")


def _fase_est(monkeypatch, d, chaqueta=False, pres=None):
    f, estado, set_do, rel = ap.fase(monkeypatch, t_est=T_OBJ, presion_add=P_ADD,
                                     temp=T_OBJ + 0.3, pres=pres)
    estado.desfase_trabajo = d
    if chaqueta:
        estado.modo_vapor = "chaqueta"
        estado.inhibir_vapor_chaqueta = False
        estado.sensores_pres["pres_chaqueta"] = 225.0
    return f, estado, set_do, rel


def test_esterilizacion_hereda_d_registra_log_y_ticket(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    f, estado, _, _ = _fase_est(monkeypatch, 7.0)
    f.update()
    assert f.p_sp == pytest.approx(P_OBJ + 7.0)
    assert "heredada" in caplog.text
    assert {"clave": tf.CLAVE_PRESION_TRABAJO, "d": "7.0"} in estado.avisos_ciclo


def test_esterilizacion_sin_d_igual_que_antes(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    f, estado, _, _ = _fase_est(monkeypatch, None)
    f.update()
    assert f.p_sp == pytest.approx(EsterilizacionFase.consigna_pwm(T_OBJ, 0.3))
    assert "calculada" in caplog.text
    assert estado.avisos_ciclo == []


def test_entrada_a_esterilizacion_sin_nivel_baja_de_la_cascada(monkeypatch):
    # la cámara llega en P_trabajo (212,0): con la consigna heredada la
    # cascada arranca en «banda»; con la calculada (≈208,4) estaría «alta»
    f, estado, _, _ = _fase_est(monkeypatch, 7.0, chaqueta=True, pres=P_OBJ + 6.5)
    f.update()
    assert estado.cascada_chaqueta["nivel"] == "banda"


def test_fallas_siguen_contra_t_est_fija(monkeypatch):
    # CIC-04 en Psat(T_est) - brecha_error_presion, aunque P_sp sea heredada
    f, estado, _, rel = _fase_est(monkeypatch, 7.0, pres=P_OBJ - 2.5)
    f.update()
    rel.avanzar(5.0)
    assert f.update() == FaseResult.FALLO
    assert getattr(estado.motivo_fallo, "codigo", None) == "est_pres_baja"


def test_constante_de_ticket_coincide():
    assert est_mod.CLAVE_TICKET_PRESION_TRABAJO == tf.CLAVE_PRESION_TRABAJO


@pytest.mark.parametrize("idioma,texto", [("es", "Presión de trabajo: Psat + 7.0 kPa"),
                                          ("en", "Working pressure: Psat + 7.0 kPa")])
def test_linea_de_ticket(idioma, texto):
    p = tf.Presentacion(idioma=idioma)
    assert tf._linea_aviso({"clave": tf.CLAVE_PRESION_TRABAJO, "d": "7.0"}, p) == texto


# ── PAM-05: C-03 (ESTERILIZACION) ─────────────────────────────────────────

@pytest.mark.parametrize("add,exceso,falla", [(11.0, 10.5, False), (11.0, 11.5, True),
                                              (30.0, None, None)])
def test_c03_aire_en_kpa(monkeypatch, add, exceso, falla):
    t = T_OBJ + 0.3
    dos_k = p_saturacion_kpa(t + 2.0) - p_saturacion_kpa(t)
    if exceso is None:                 # add > 2 K: rige 2 K
        casos = [(dos_k - 0.3, False), (dos_k + 0.3, True)]
    else:
        casos = [(exceso, falla)]
    for exc, debe_fallar in casos:
        f, estado, _, rel = ap.fase(monkeypatch, t_est=T_OBJ, presion_add=add, rango_pres=30.0,
                                    temp=t, pres=p_saturacion_kpa(t) + exc)
        estado.desfase_trabajo = None
        f.update()
        rel.avanzar(5.0)
        r = f.update()
        if debe_fallar:
            assert r == FaseResult.FALLO
            codigo, valores = f.alarma_fallo
            assert codigo == "CIC-12"
            assert valores["limite_kpa"] == pytest.approx(min(add, dos_k))
            assert getattr(estado.motivo_fallo, "codigo", None) == "est_aire_kpa"
            assert "kPa" in str(estado.motivo_fallo)
        else:
            assert r == FaseResult.EN_CURSO


def test_c03_vapor_sobrecalentado_sin_cambio(monkeypatch):
    f, estado, _, rel = ap.fase(monkeypatch, t_est=134.0, temp=136.5, pres=p_saturacion_kpa(134.0))
    f.update()
    rel.avanzar(5.0)
    assert f.update() == FaseResult.FALLO
    assert f.alarma_fallo[0] == "CIC-13"


# PAM-06 retirada en la tanda 35 (CRI-03): sus pruebas pasaron a tests/test_cri_coherencia.py

def test_textos_pam():
    from autoclave import i18n
    for idioma in ("es", "en"):
        assert i18n.existe("ticket_ciclo.presion_trabajo", idioma)
        assert i18n.existe("motivos_fase.est_aire_kpa", idioma)

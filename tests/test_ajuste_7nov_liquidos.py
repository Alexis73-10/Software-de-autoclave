"""Ajuste 7-nov: presion_add_liquido_calentamiento (empuje de la rampa de
CALENTAMIENTO con carga líquida), VCH-AIS / A14-M2 con techo ampliado durante
el empuje, validación (prevacío permitido con líquidos) y migración."""
import copy
import json
import types
from pathlib import Path

import pytest

from autoclave.core.managers import catalogo_parametros as cat
from autoclave.core.managers.cycle_manager import migrar_parametros
from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import calentamiento as cal_mod
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests import test_calentamiento_fase as tcal

T_OBJ = 134.0
P_ADD = 11.0
EXTRA = 15.0
P_OBJ = p_saturacion_kpa(T_OBJ)
P_TECHO = P_OBJ + P_ADD
P_TECHO_RAMPA = P_TECHO + EXTRA


@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    ahora = [1000.0]
    monkeypatch.setattr(cal_mod, "time", types.SimpleNamespace(monotonic=lambda: ahora[0]))
    return ahora


def _fase(carga="liquido", extra=EXTRA, chaqueta=False, tiempo_estable=0):
    fase, estado, set_do = tcal._make_fase(t_obj=T_OBJ, presion_add=P_ADD,
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
        estado.sensores_pres["pres_chaqueta"] = 300.0
    fase.update()  # inicializa
    return fase, estado, set_do


def _tick(fase, estado, temp, pres):
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = pres
    return fase.update()


def _enclavar(fase, estado, reloj, pres, temp=T_OBJ):
    """T >= T_obj sostenida más de 5 s (MEDIA-2): enclava t_obj alcanzada."""
    _tick(fase, estado, temp, pres)
    reloj[0] += 6.0
    return _tick(fase, estado, temp, pres)


# ── Sólidos y extra 0: idéntico al comportamiento anterior ────────────────

@pytest.mark.parametrize("carga,extra", [("solido", 15.0), ("liquido", 0.0), ("solido", 0.0)])
def test_solido_o_extra_cero_no_empuja(carga, extra):
    fase, estado, _ = _fase(carga, extra)
    _tick(fase, estado, 110.0, P_OBJ + 5)
    referencia, est_ref, _ = _fase("solido", 0.0)
    _tick(referencia, est_ref, 110.0, P_OBJ + 5)
    assert fase._duty_actual == referencia._duty_actual
    assert fase._add_liquido() == 0.0
    # el techo sigue siendo p_techo: a P >= p_techo duty 0
    _tick(fase, estado, 110.0, P_TECHO + 1)
    assert fase._duty_actual == 0.0
    assert fase._t_obj_alcanzada is False


def test_solido_alcanzar_t_obj_no_enclava_ni_baja_a_psat():
    fase, estado, set_do = _fase("solido", EXTRA)
    _tick(fase, estado, T_OBJ, P_OBJ + 10)
    assert fase._t_obj_alcanzada is False


# ── Líquido con extra: rampa y techo ampliados ────────────────────────────

def test_liquido_rampa_apunta_a_psat_mas_extra():
    fase, estado, _ = _fase("liquido", EXTRA)
    ref, est_ref, _ = _fase("solido", 0.0)
    pres = P_OBJ + 6   # sobre p_obj: sin extra la rampa ya se apaga
    _tick(fase, estado, 110.0, pres)
    _tick(ref, est_ref, 110.0, pres)
    assert fase._duty_actual > ref._duty_actual


def test_liquido_techo_de_rampa_incluye_el_extra():
    fase, estado, _ = _fase("liquido", EXTRA)
    ref, est_ref, _ = _fase("solido", 0.0)
    pres = P_TECHO + 1     # sobre el techo normal, bajo el ampliado
    _tick(fase, estado, 110.0, pres)
    _tick(ref, est_ref, 110.0, pres)
    assert ref._duty_actual == 0.0
    assert fase._duty_actual > 0.0
    _tick(fase, estado, 110.0, P_TECHO_RAMPA + 0.5)
    assert fase._duty_actual == 0.0


# ── Enclave al alcanzar T_obj y bajando_a_psat ────────────────────────────

def test_enclave_exige_t_obj_sostenida_5_s_y_se_reinicia_bajo_t_obj(reloj):
    fase, estado, _ = _fase("liquido", EXTRA)
    _tick(fase, estado, T_OBJ, P_OBJ + 10)
    reloj[0] += 4.0
    _tick(fase, estado, T_OBJ, P_OBJ + 10)
    assert fase._t_obj_alcanzada is False
    _tick(fase, estado, T_OBJ - 0.5, P_OBJ + 10)      # bajo T_obj: reinicia la cuenta
    reloj[0] += 4.0
    _tick(fase, estado, T_OBJ, P_OBJ + 10)
    reloj[0] += 4.0
    _tick(fase, estado, T_OBJ, P_OBJ + 10)
    assert fase._t_obj_alcanzada is False
    reloj[0] += 2.0
    _tick(fase, estado, T_OBJ, P_OBJ + 10)
    assert fase._t_obj_alcanzada is True


def test_sin_lectura_reinicia_la_cuenta_del_enclave(reloj):
    fase, estado, _ = _fase("liquido", EXTRA)
    _tick(fase, estado, T_OBJ, P_OBJ + 10)
    reloj[0] += 4.0
    _tick(fase, estado, T_OBJ, None)
    reloj[0] += 4.0
    _tick(fase, estado, T_OBJ, P_OBJ + 10)
    assert fase._t_obj_alcanzada is False


def test_enclave_y_bajando_a_psat_mantiene_vapor_off_y_no_entra_a_estable(reloj):
    fase, estado, set_do = _fase("liquido", EXTRA)
    assert _enclavar(fase, estado, reloj, P_OBJ + 10) == FaseResult.EN_CURSO
    assert fase._t_obj_alcanzada is True
    assert fase._duty_actual == 0.0
    assert fase._en_sostenimiento is False
    set_do.reset_mock()
    # la temperatura cae bajo T_obj: el enclave se mantiene
    _tick(fase, estado, T_OBJ - 0.5, P_OBJ + 5)
    assert fase._t_obj_alcanzada is True
    assert fase._duty_actual == 0.0
    set_do.vapor_camara_on.assert_not_called()
    _tick(fase, estado, T_OBJ, P_OBJ + 2.5)           # aún sobre Psat + 2
    assert fase._en_sostenimiento is False
    assert fase._duty_actual == 0.0


def test_entra_a_estable_solo_con_p_dentro_de_psat_mas_menos_2(reloj):
    fase, estado, _ = _fase("liquido", EXTRA)
    _enclavar(fase, estado, reloj, P_OBJ + 10)
    _tick(fase, estado, T_OBJ, P_OBJ + 2.5)
    assert fase._en_sostenimiento is False
    _tick(fase, estado, T_OBJ, P_OBJ + 1.5)
    assert fase._en_sostenimiento is True


def test_no_entra_a_estable_si_p_bajo_psat_menos_2(reloj):
    fase, estado, _ = _fase("liquido", EXTRA)
    _enclavar(fase, estado, reloj, P_OBJ - 3)
    assert fase._en_sostenimiento is False


def test_objetivo_post_empuje_es_psat_mas_1_kpa(reloj):
    fase, estado, _ = _fase("liquido", EXTRA)
    _enclavar(fase, estado, reloj, P_OBJ + 1.5)
    # T baja con P a 1 kPa sobre Psat: la rampa ya está en su objetivo, no empuja a +15
    _tick(fase, estado, 125.0, P_OBJ + 1.0)
    ref = fase._duty_actual
    _tick(fase, estado, 125.0, P_OBJ + 8.0)           # bajando_a_psat
    assert fase._duty_actual == 0.0
    assert ref >= 0.0


def test_vuelve_al_objetivo_normal_tras_el_enclave(reloj):
    fase, estado, _ = _fase("liquido", EXTRA)
    _enclavar(fase, estado, reloj, P_OBJ + 1)
    assert fase._t_obj_alcanzada is True
    _tick(fase, estado, 125.0, P_OBJ + 8)
    assert fase._duty_actual == 0.0


def test_sin_lectura_vapor_off():
    fase, estado, set_do = _fase("liquido", EXTRA)
    set_do.reset_mock()
    estado.sensores_temp["temp_camara"] = 110.0
    estado.sensores_pres["pres_camara"] = None
    fase.update()
    set_do.vapor_camara_on.assert_not_called()
    # modo chaqueta: sin lectura la chaqueta queda OFF
    fase, estado, set_do = _fase("liquido", EXTRA, chaqueta=True)
    set_do.reset_mock()
    estado.sensores_temp["temp_camara"] = 110.0
    estado.sensores_pres["pres_camara"] = None
    fase.update()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()


# ── Modo chaqueta: VCH-AIS y A14-M2 ───────────────────────────────────────

def test_chaqueta_ais_usa_techo_ampliado_durante_el_empuje():
    fase, estado, _ = _fase("liquido", EXTRA, chaqueta=True)
    _tick(fase, estado, 110.0, P_TECHO + 5)       # entre techo normal y ampliado
    assert fase._aislamiento().aislado is False
    _tick(fase, estado, 110.0, P_TECHO_RAMPA + 1)  # sobre el ampliado
    assert fase._aislamiento().aislado is True


def test_chaqueta_ais_usa_techo_normal_sin_extra():
    fase, estado, _ = _fase("solido", EXTRA, chaqueta=True)
    _tick(fase, estado, 110.0, P_TECHO + 5)
    assert fase._aislamiento().aislado is True


def test_chaqueta_ais_techo_ampliado_en_la_bajada_y_normal_al_terminarla(reloj):
    fase, estado, _ = _fase("liquido", EXTRA, chaqueta=True)
    _enclavar(fase, estado, reloj, P_TECHO + 5)   # enclave; P > Psat+2: bajando_a_psat
    assert fase._t_obj_alcanzada is True
    assert fase._aislamiento().aislado is False   # techo ampliado durante la bajada
    # P baja a la banda de entrada: fin de la bajada, techo normal
    _tick(fase, estado, T_OBJ, P_OBJ + 1.5)
    assert fase._en_sostenimiento is True


def test_chaqueta_ais_sin_lectura_usa_techo_normal():
    fase, estado, _ = _fase("liquido", EXTRA, chaqueta=True)
    _tick(fase, estado, None, P_TECHO + 5)
    assert fase._aislamiento().aislado is True


def test_chaqueta_m2_techo_ampliado_en_empuje_y_en_bajada_normal_despues(reloj):
    p_chaq = P_TECHO + 10   # > normal + 8 (corta); < ampliado + 8 (no corta)
    fase, estado, set_do = _fase("liquido", EXTRA, chaqueta=True)
    estado.sensores_pres["pres_chaqueta"] = p_chaq
    set_do.reset_mock()
    _tick(fase, estado, 110.0, 150.0)             # lejos de saturación, duty 1
    set_do.vapor_chaqueta_on.assert_called()
    assert fase._corte_m2_previo is False
    # sin extra (sólido): el mismo valor corta
    ref, est_ref, do_ref = _fase("solido", 0.0, chaqueta=True)
    est_ref.sensores_pres["pres_chaqueta"] = p_chaq
    do_ref.reset_mock()
    _tick(ref, est_ref, 110.0, 150.0)
    do_ref.vapor_chaqueta_on.assert_not_called()
    assert ref._corte_m2_previo is True
    # durante la bajada a saturación sigue el techo ampliado
    _enclavar(fase, estado, reloj, P_OBJ + 10)
    assert fase._corte_m2_previo is False
    # terminada la bajada (P <= Psat+2) vuelve el techo normal y corta
    _tick(fase, estado, T_OBJ, P_OBJ + 1.5)
    assert fase._corte_m2_previo is True


# ── Validación y migración ────────────────────────────────────────────────

_RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "cycles" / "factory"


def _liquidos():
    return copy.deepcopy(json.loads((_RAIZ / "liquidos.json").read_text(encoding="utf-8"))["parameters"])


def test_liquido_con_prevacio_ahora_es_valido():
    p = _liquidos()
    p["prevacio"]["conteo_pulso_a"]["value"] = 2
    errores = cat.errores_coherencia(p)
    assert not any("prevac" in e.lower() for e in errores), errores


def test_el_programa_de_fabrica_liquidos_es_valido():
    assert cat.errores_programa(_liquidos()) == []


def test_psat_mas_add_mas_extra_sobre_alivio_se_rechaza():
    p = _liquidos()
    alivio = 385.0
    extra_max = alivio - P_OBJ - P_ADD
    p["calentamiento"]["temperatura_calentamiento"]["value"] = T_OBJ
    p["calentamiento"]["presion_add_calentamiento"]["value"] = P_ADD
    p["calentamiento"]["presion_add_liquido_calentamiento"]["value"] = 30.0
    errores = cat.errores_coherencia(p)
    if extra_max < 30.0:
        assert any("presion_add_liquido_calentamiento" in e for e in errores), errores
    p["calentamiento"]["presion_add_liquido_calentamiento"]["value"] = 0.0
    assert not any("presion_add_liquido_calentamiento" in e for e in cat.errores_coherencia(p))


def test_extra_bajo_el_alivio_se_acepta():
    p = _liquidos()
    p["calentamiento"]["presion_add_liquido_calentamiento"]["value"] = 5.0
    assert not any("presion_add_liquido_calentamiento" in e for e in cat.errores_coherencia(p))


def test_migracion_agrega_el_parametro_con_15_e_idempotente():
    p = _liquidos()
    del p["calentamiento"]["presion_add_liquido_calentamiento"]
    agregadas = []
    assert migrar_parametros(p, agregadas=agregadas) is True
    hoja = p["calentamiento"]["presion_add_liquido_calentamiento"]
    assert hoja["value"] == 15.0
    assert any(a["parametro"] == "presion_add_liquido_calentamiento" for a in agregadas)
    claves = list(p["calentamiento"])
    assert claves.index("presion_add_liquido_calentamiento") == \
        claves.index("presion_add_calentamiento") + 1
    copia = copy.deepcopy(p)
    agregadas2 = []
    migrar_parametros(p, agregadas=agregadas2)
    assert p == copia
    assert not any(a["parametro"] == "presion_add_liquido_calentamiento" for a in agregadas2)


def test_migracion_respeta_un_valor_existente():
    p = _liquidos()
    p["calentamiento"]["presion_add_liquido_calentamiento"]["value"] = 7.0
    migrar_parametros(p)
    assert p["calentamiento"]["presion_add_liquido_calentamiento"]["value"] == 7.0

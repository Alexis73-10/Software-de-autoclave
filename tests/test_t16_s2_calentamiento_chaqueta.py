"""Tanda 16, s2: CALENTAMIENTO en modo chaqueta (VCH C), aislamiento de cámara
(VCH-AIS, CIC-15/16), corte inhibir_vapor_chaqueta y P3 (D-14.3)."""
import types

import pytest

from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import calentamiento as cal_mod
from autoclave.state_machine.cycle_phases.aislamiento_camara import AislamientoCamara
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from tests import test_calentamiento_fase as tcal

pytestmark = pytest.mark.req("T16-S2")

T_OBJ = 134.0
P_ADD = 11.0
P_TECHO = p_saturacion_kpa(T_OBJ) + P_ADD
_UNA_REF = {"temp_camara": "principal", "temp_2_camara": "no_en_uso", "temp_ref": "referencia"}


@pytest.fixture
def reloj(monkeypatch):
    """Reloj monotónico controlado solo dentro de calentamiento.py."""
    ahora = [1000.0]
    monkeypatch.setattr(cal_mod, "time", types.SimpleNamespace(monotonic=lambda: ahora[0]))
    return ahora


def _fase(chaqueta=True, inhibir=False, extra=None, **kw):
    fase, estado, set_do = tcal._make_fase(t_obj=T_OBJ, presion_add=P_ADD, **kw)
    if chaqueta:
        estado.modo_vapor = "chaqueta"
        estado.inhibir_vapor_chaqueta = inhibir
    if extra:
        original = fase.cycle.get_param.side_effect

        def get_param(seccion, param, default=None):
            if param in extra:
                return extra[param]
            return original(seccion, param, default)
        fase.cycle.get_param.side_effect = get_param
    return fase, estado, set_do


# ── Modo y actuador ───────────────────────────────────────────────────────

def test_controla_vapor_chaqueta_solo_en_modo_chaqueta():
    fase, _, _ = _fase(chaqueta=True)
    assert fase.controla_vapor_chaqueta is True
    fase.update()
    assert fase.controla_vapor_chaqueta is True
    fase_cam, _, _ = _fase(chaqueta=False)
    assert fase_cam.controla_vapor_chaqueta is False
    fase_cam.update()
    assert fase_cam.controla_vapor_chaqueta is False


def test_modo_chaqueta_conmuta_solo_vapor_chaqueta_y_camara_queda_abierta():
    fase, estado, set_do = _fase()
    assert fase.update() == FaseResult.EN_CURSO   # lejos del objetivo: duty 1
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()
    # muy por encima del objetivo (duty 0): la chaqueta cierra, la cámara no
    set_do.reset_mock()
    estado.sensores_temp["temp_camara"] = 140.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(T_OBJ) + 5
    fase.update()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_camara_off.assert_not_called()
    set_do.vapor_camara_on.assert_called()


def test_modo_camara_no_toca_vapor_chaqueta():
    fase, estado, set_do = _fase(chaqueta=False)
    fase.update()
    set_do.vapor_camara_on.assert_called()
    estado.sensores_temp["temp_camara"] = 140.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(T_OBJ) + 5
    fase.update()
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_not_called()


def _completar(fase, estado):
    fase.update()
    estado.sensores_temp["temp_camara"] = T_OBJ
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(T_OBJ)
    return fase.update()


def test_completado_en_modo_chaqueta_no_cierra_vapor_camara():
    fase, estado, set_do = _fase(tiempo_estable=0)
    assert _completar(fase, estado) == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()


def test_completado_en_modo_camara_cierra_vapor_camara():
    fase, estado, set_do = _fase(chaqueta=False, tiempo_estable=0)
    assert _completar(fase, estado) == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_not_called()


def test_fallo_en_modo_chaqueta_cierra_ambas():
    fase, _, set_do = _fase()
    fase.update()
    set_do.reset_mock()
    fase._timer_timeout_fin = 0.0
    assert fase.update() == FaseResult.FALLO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()


def test_inhibir_vapor_chaqueta_nunca_enciende_la_chaqueta():
    fase, _, set_do = _fase(inhibir=True)
    for _ in range(3):
        fase.update()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_on.assert_called()


def test_inhibir_magicmock_no_cuenta_como_corte():
    # solo `is True` inhibe (un MagicMock es truthy)
    fase, estado, set_do = _fase()
    del estado.inhibir_vapor_chaqueta
    fase.update()
    set_do.vapor_chaqueta_on.assert_called()


def test_sin_lectura_de_presion_apaga_chaqueta_y_camara_sigue_abierta():
    fase, estado, set_do = _fase()
    fase.update()
    set_do.reset_mock()
    estado.sensores_pres["pres_camara"] = None
    assert fase.update() == FaseResult.EN_CURSO
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_camara_off.assert_not_called()


def test_sin_lectura_del_principal_apaga_chaqueta():
    fase, estado, set_do = _fase()
    fase.update()
    set_do.reset_mock()
    estado.sensores_temp["temp_camara"] = None
    fase.update()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_sin_principal_antes_de_inicializar_apaga_chaqueta():
    fase, estado, set_do = _fase()
    estado.sensores_temp["temp_camara"] = None
    assert fase.update() == FaseResult.EN_CURSO
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_sin_lectura_en_modo_camara_queda_como_antes():
    fase, estado, set_do = _fase(chaqueta=False)
    fase.update()
    set_do.reset_mock()
    estado.sensores_pres["pres_camara"] = None
    assert fase.update() == FaseResult.EN_CURSO
    assert set_do.method_calls == []


def test_modo_queda_registrado_en_el_log(caplog):
    caplog.set_level("INFO", logger=cal_mod.__name__)
    fase, _, _ = _fase()
    fase.update()
    assert any("modo de vapor chaqueta" in r.getMessage() for r in caplog.records)
    caplog.clear()
    fase_cam, _, _ = _fase(chaqueta=False)
    fase_cam.update()
    assert any("modo de vapor cámara" in r.getMessage() for r in caplog.records)


# ── Aislamiento VCH-AIS ───────────────────────────────────────────────────

def test_aislamiento_crea_instancia_si_el_estado_no_la_tiene():
    fase, estado, _ = _fase()
    fase.update()
    assert isinstance(estado.aislamiento_camara, AislamientoCamara)


def test_aislamiento_usa_la_instancia_compartida_del_estado():
    fase, estado, _ = _fase()
    compartida = AislamientoCamara()
    estado.aislamiento_camara = compartida
    fase.update()
    assert estado.aislamiento_camara is compartida


def test_aislamiento_entrada_y_salida_por_histeresis_y_3_s(reloj, caplog):
    caplog.set_level("INFO", logger=cal_mod.__name__)
    fase, estado, set_do = _fase()
    fase.update()
    set_do.reset_mock()
    estado.sensores_temp["temp_camara"] = 120.0
    estado.sensores_pres["pres_camara"] = P_TECHO
    fase.update()
    assert estado.aislamiento_camara.aislado
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()
    set_do.vapor_chaqueta_on.assert_not_called()
    assert any("AISLAMIENTO" in r.getMessage() for r in caplog.records)

    # bajo el techo pero sin llegar a la histéresis (3 kPa): sigue aislada
    estado.sensores_pres["pres_camara"] = P_TECHO - 2.0
    for _ in range(5):
        reloj[0] += 2.0
        fase.update()
    assert estado.aislamiento_camara.aislado

    # en la histéresis: hace falta 3 s sostenidos
    set_do.reset_mock()
    estado.sensores_pres["pres_camara"] = P_TECHO - 3.0
    fase.update()
    reloj[0] += 2.9
    fase.update()
    assert estado.aislamiento_camara.aislado
    set_do.vapor_camara_on.assert_not_called()
    reloj[0] += 0.2
    fase.update()
    assert not estado.aislamiento_camara.aislado
    set_do.vapor_camara_on.assert_called()
    assert any("fin del aislamiento" in r.getMessage() for r in caplog.records)


def test_aislamiento_respeta_histeresis_configurada_y_recorta(reloj):
    fase, estado, _ = _fase(extra={"histeresis_cierre_camara": 50})  # recorta a 10
    fase.update()
    estado.sensores_pres["pres_camara"] = P_TECHO
    fase.update()
    estado.sensores_pres["pres_camara"] = P_TECHO - 9.0
    for _ in range(3):
        reloj[0] += 2.0
        fase.update()
    assert estado.aislamiento_camara.aislado
    estado.sensores_pres["pres_camara"] = P_TECHO - 10.0
    fase.update()
    reloj[0] += 3.1
    fase.update()
    assert not estado.aislamiento_camara.aislado


@pytest.mark.parametrize("valor", [None, "x", True, float("nan")])
def test_histeresis_invalida_vale_3(valor):
    fase, _, _ = _fase(extra={"histeresis_cierre_camara": valor})
    assert fase._histeresis_cierre() == 3.0


def test_aislamiento_no_existe_en_modo_camara():
    fase, estado, set_do = _fase(chaqueta=False)
    estado.aislamiento_camara = AislamientoCamara()
    fase.update()
    estado.sensores_pres["pres_camara"] = P_TECHO + 5
    fase.update()
    assert not estado.aislamiento_camara.aislado
    set_do.vapor_chaqueta_off.assert_not_called()


def test_cic_15_aislamiento_sostenido(reloj):
    fase, estado, set_do = _fase()
    fase.update()
    estado.sensores_pres["pres_camara"] = P_TECHO + 1
    fase.update()
    reloj[0] += 180.0          # defecto 3 min: aún no
    assert fase.update() == FaseResult.EN_CURSO
    set_do.reset_mock()
    reloj[0] += 1.0
    assert fase.update() == FaseResult.FALLO
    codigo, valores = fase.alarma_fallo
    assert codigo == "CIC-15"
    assert valores["minutos"] == "3"
    assert valores["fase"] == "Calentamiento"
    assert valores["maximo"] == pytest.approx(P_TECHO)
    assert estado.motivo_fallo
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()


def test_cic_16_aislamiento_recurrente(reloj):
    fase, estado, set_do = _fase()
    fase.update()
    for i in range(6):
        estado.sensores_pres["pres_camara"] = P_TECHO
        resultado = fase.update()
        if i == 5:
            break
        assert resultado == FaseResult.EN_CURSO
        estado.sensores_pres["pres_camara"] = P_TECHO - 5
        fase.update()
        reloj[0] += 3.5
        fase.update()
        assert not estado.aislamiento_camara.aislado
        reloj[0] += 10.0
    assert resultado == FaseResult.FALLO
    codigo, valores = fase.alarma_fallo
    assert codigo == "CIC-16"
    assert valores["cantidad"] == 6
    assert valores["minutos"] == "15"
    assert valores["fase"] == "Calentamiento"
    set_do.vapor_camara_off.assert_called()


def test_reset_limpia_alarma_fallo(reloj):
    fase, estado, _ = _fase()
    fase.update()
    estado.sensores_pres["pres_camara"] = P_TECHO + 1
    fase.update()
    reloj[0] += 200.0
    assert fase.update() == FaseResult.FALLO
    fase.reset()
    assert fase.alarma_fallo is None


# ── P3 / D-14.3 ───────────────────────────────────────────────────────────

def _ventana_ref(t_ref, brecha_extra):
    fase, estado, _ = _fase(chaqueta=False, tiempo_estable=5, extra=brecha_extra)
    fase.cycle.sensores = _UNA_REF
    fase.update()
    estado.sensores_temp["temp_camara"] = T_OBJ
    estado.sensores_temp["temp_ref"] = t_ref
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(T_OBJ)
    fase.update()
    return fase


def test_p3_referencia_dentro_de_la_brecha_abre_la_ventana():
    fase = _ventana_ref(T_OBJ - 0.4, {"brecha_error_temperatura": 0.5})
    assert fase._timer_sostenido_desde is not None


def test_p3_referencia_bajo_la_brecha_bloquea():
    fase = _ventana_ref(T_OBJ - 0.6, {"brecha_error_temperatura": 0.5})
    assert fase._timer_sostenido_desde is None


def test_p3_brecha_por_defecto_de_los_programas():
    fase = _ventana_ref(T_OBJ - 0.1, {"brecha_error_temperatura": 0.1})
    assert fase._timer_sostenido_desde is not None


@pytest.mark.parametrize("valor", [None, "0.5", -1.0, float("inf"), True])
def test_p3_brecha_invalida_conserva_el_criterio_anterior(valor):
    fase = _ventana_ref(T_OBJ - 0.1, {"brecha_error_temperatura": valor})
    assert fase._timer_sostenido_desde is None
    fase_ok = _ventana_ref(T_OBJ, {"brecha_error_temperatura": valor})
    assert fase_ok._timer_sostenido_desde is not None


def test_p3_se_lee_de_la_seccion_esterilizacion():
    fase = _ventana_ref(T_OBJ, {})
    secciones = [c.args[0] for c in fase.cycle.get_param.call_args_list
                 if c.args[1] == "brecha_error_temperatura"]
    assert secciones and set(secciones) == {"esterilizacion"}

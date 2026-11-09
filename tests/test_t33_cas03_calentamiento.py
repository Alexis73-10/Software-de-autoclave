"""Tanda 33, CAS-03: en CALENTAMIENTO modo chaqueta la cascada (CAS-01) decide
vapor_chaqueta en ESTABLE_PREESTERILIZACION y, con carga líquida y empuje,
desde el enclave de t_obj alcanzada (incluida la bajada a saturación). La
rampa previa, VCH-AIS, D-CHQ y el modo cámara no cambian."""
import logging
import types

import pytest

from autoclave.core.runtime.steam import p_saturacion_kpa
from autoclave.state_machine.cycle_phases import calentamiento as cal_mod
from autoclave.state_machine.cycle_phases.cascada_chaqueta import CascadaChaqueta
from tests import test_calentamiento_fase as tcal

T_OBJ = 134.0
P_ADD = 11.0
EXTRA = 15.0
P_OBJ = p_saturacion_kpa(T_OBJ)          # p_ref
P_TECHO = P_OBJ + P_ADD                  # techo normal
MARGEN = 8.0                             # margen_chaqueta_est por defecto
TOPE = P_TECHO - 2.0                     # tope de banda anterior a CRI-01 (solo referencia)
TOPE_BAJA = 350.0                        # min(375 - 10, 350): nivel baja (ajuste 8-nov)
CONSIGNA_BANDA = P_OBJ + MARGEN          # CRI-01: min(p_ref + dp, 350), dp inicial = margen



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

@pytest.fixture(autouse=True)
def reloj(monkeypatch):
    ahora = [1000.0]
    monkeypatch.setattr(cal_mod, "time", types.SimpleNamespace(monotonic=lambda: ahora[0]))
    return ahora


def _fase(carga="solido", extra=0.0, chaqueta=True, inhibir=False, pres_chaqueta=300.0):
    fase, estado, set_do = tcal._make_fase(t_obj=T_OBJ, presion_add=P_ADD, tiempo_estable=600)
    original = fase.cycle.get_param.side_effect
    valores = {"tipo_carga": carga, "presion_add_liquido_calentamiento": extra}

    def get_param(seccion, param, default=None):
        if param in valores:
            return valores[param]
        return original(seccion, param, default)
    fase.cycle.get_param.side_effect = get_param
    if chaqueta:
        estado.modo_vapor = "chaqueta"
        estado.inhibir_vapor_chaqueta = inhibir
    estado.sensores_pres["pres_chaqueta"] = pres_chaqueta
    fase.update()  # inicializa
    return fase, estado, set_do


def _tick(fase, estado, temp, pres, pres_chaqueta=None):
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = pres
    if pres_chaqueta is not None:
        estado.sensores_pres["pres_chaqueta"] = pres_chaqueta
    return fase.update()


def _a_sostenimiento(fase, estado):
    _tick(fase, estado, T_OBJ, P_OBJ)
    assert fase._en_sostenimiento is True


def _ultima_chaqueta(set_do):
    """'on'/'off' según la última orden de vapor_chaqueta del tick."""
    for nombre, _, _ in reversed(set_do.mock_calls):
        if nombre == "vapor_chaqueta_on":
            return "on"
        if nombre == "vapor_chaqueta_off":
            return "off"
    return None


# ── Sostenimiento ──────────────────────────────────────────────────────────

def test_sostenimiento_banda_con_histeresis_bajo_la_consigna():
    fase, estado, set_do = _fase()
    _a_sostenimiento(fase, estado)
    set_do.reset_mock()
    _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=CONSIGNA_BANDA - 3.5)
    assert _ultima_chaqueta(set_do) == "on"
    assert estado.cascada_chaqueta == {"nivel": "banda", "consigna": pytest.approx(CONSIGNA_BANDA),
                                       "valvula": True, "dp": pytest.approx(MARGEN)}
    set_do.reset_mock()
    _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=CONSIGNA_BANDA + 0.2)
    assert _ultima_chaqueta(set_do) == "off"
    set_do.reset_mock()
    _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=CONSIGNA_BANDA - 1.5)   # histéresis
    assert _ultima_chaqueta(set_do) == "off"


def test_sostenimiento_baja_usa_el_tope_de_baja():
    """Ajuste 8-nov: en baja la consigna es min(375 − 10, 350) = 350, aun
    con la chaqueta sobre techo − 2."""
    fase, estado, set_do = _fase()
    _a_sostenimiento(fase, estado)
    set_do.reset_mock()
    _tick(fase, estado, T_OBJ, P_OBJ - 3.0, pres_chaqueta=TOPE + 5.0)
    assert estado.cascada_chaqueta["nivel"] == "baja"
    assert estado.cascada_chaqueta["consigna"] == pytest.approx(TOPE_BAJA)
    assert _ultima_chaqueta(set_do) == "on"


def test_sostenimiento_alta_apaga_aunque_el_pwm_encenderia():
    fase, estado, set_do = _fase()
    _a_sostenimiento(fase, estado)
    set_do.reset_mock()
    _tick(fase, estado, T_OBJ, P_OBJ + 1.5, pres_chaqueta=200.0)
    assert estado.cascada_chaqueta["nivel"] == "alta"
    assert estado.cascada_chaqueta["consigna"] is None
    assert _ultima_chaqueta(set_do) == "off"
    set_do.vapor_chaqueta_on.assert_not_called()


def test_la_cascada_reemplaza_a_a14_m2_en_sostenimiento():
    fase, estado, set_do = _fase()
    _a_sostenimiento(fase, estado)
    _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=250.0)
    assert fase._corte_m2_previo is False
    assert _ultima_chaqueta(set_do) == "on"


# ── Líquidos con empuje ────────────────────────────────────────────────────

def _enclavar(fase, estado, reloj, pres, pres_chaqueta=250.0):
    _tick(fase, estado, T_OBJ, pres, pres_chaqueta)
    reloj[0] += 6.0
    _tick(fase, estado, T_OBJ, pres, pres_chaqueta)
    assert fase._t_obj_alcanzada is True


def test_empuje_antes_del_enclave_sigue_con_la_rampa():
    fase, estado, set_do = _fase("liquido", EXTRA)
    set_do.reset_mock()
    _tick(fase, estado, 110.0, 150.0, pres_chaqueta=250.0)
    assert estado.cascada_chaqueta is None
    assert _ultima_chaqueta(set_do) == "on"


def test_bajando_a_psat_nivel_alta_off(reloj):
    fase, estado, set_do = _fase("liquido", EXTRA)
    _tick(fase, estado, T_OBJ, P_OBJ + 10, 250.0)     # empuje: aún la rampa
    reloj[0] += 6.0
    set_do.reset_mock()
    _tick(fase, estado, T_OBJ, P_OBJ + 10, 250.0)     # tick del enclave
    assert fase._t_obj_alcanzada is True
    assert fase._en_sostenimiento is False
    assert estado.cascada_chaqueta["nivel"] == "alta"
    set_do.vapor_chaqueta_on.assert_not_called()


def test_tras_el_enclave_decide_la_cascada_antes_del_sostenimiento(reloj):
    fase, estado, set_do = _fase("liquido", EXTRA)
    _enclavar(fase, estado, reloj, P_OBJ + 10)
    set_do.reset_mock()
    # P bajo Psat - 2: no entra a ESTABLE, pero la cascada (baja) decide
    _tick(fase, estado, T_OBJ, P_OBJ - 3.0, pres_chaqueta=TOPE + 5.0)
    assert fase._en_sostenimiento is False
    assert estado.cascada_chaqueta["nivel"] == "baja"
    # ajuste 8-nov: en baja el tope no depende del techo (normal ni ampliado)
    assert estado.cascada_chaqueta["consigna"] == pytest.approx(TOPE_BAJA)
    assert _ultima_chaqueta(set_do) == "on"


def test_solido_con_extra_no_activa_la_cascada_antes_del_sostenimiento():
    fase, estado, _ = _fase("solido", EXTRA)
    _tick(fase, estado, T_OBJ, P_OBJ - 3.0)
    assert estado.cascada_chaqueta is None


# ── Rampa previa ───────────────────────────────────────────────────────────

def test_rampa_previa_sin_cambio_y_con_a14_m2():
    fase, estado, set_do = _fase()
    set_do.reset_mock()
    _tick(fase, estado, 110.0, 150.0, pres_chaqueta=250.0)
    assert estado.cascada_chaqueta is None
    assert _ultima_chaqueta(set_do) == "on"
    set_do.reset_mock()
    _tick(fase, estado, 110.0, 150.0, pres_chaqueta=P_TECHO + MARGEN + 1)
    assert fase._corte_m2_previo is True
    assert _ultima_chaqueta(set_do) == "off"


# ── Prevalencias ───────────────────────────────────────────────────────────

def test_vch_ais_prevalece_sobre_la_cascada(monkeypatch):
    fase, estado, set_do = _fase()
    _a_sostenimiento(fase, estado)
    monkeypatch.setattr(fase, "_vigilar_aislamiento", lambda *a: (True, None))
    set_do.reset_mock()
    _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=250.0)
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_camara_off.assert_called()
    assert estado.cascada_chaqueta["valvula"] is False


def test_inhibir_prevalece_y_no_reabre_por_histeresis():
    fase, estado, set_do = _fase(inhibir=True)
    _a_sostenimiento(fase, estado)
    set_do.reset_mock()
    _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=250.0)
    set_do.vapor_chaqueta_on.assert_not_called()
    assert estado.cascada_chaqueta["valvula"] is False
    estado.inhibir_vapor_chaqueta = False
    _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=CONSIGNA_BANDA - 1.5)   # histéresis
    set_do.vapor_chaqueta_on.assert_not_called()
    _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=CONSIGNA_BANDA - 3.5)
    set_do.vapor_chaqueta_on.assert_called()


def test_sin_lectura_de_chaqueta_off():
    fase, estado, set_do = _fase()
    _a_sostenimiento(fase, estado)
    estado.sensores_pres["pres_chaqueta"] = None
    set_do.reset_mock()
    _tick(fase, estado, T_OBJ, P_OBJ)
    assert _ultima_chaqueta(set_do) == "off"
    assert estado.cascada_chaqueta["nivel"] == "sin_datos"


@pytest.mark.parametrize("temp,pres", [(T_OBJ, None), (None, P_OBJ)])
def test_sin_lectura_de_camara_o_principal_off_y_no_reabre_por_histeresis(temp, pres):
    fase, estado, set_do = _fase()
    _a_sostenimiento(fase, estado)
    _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=250.0)
    assert fase._cascada.valvula is True
    set_do.reset_mock()
    _tick(fase, estado, temp, pres)
    assert _ultima_chaqueta(set_do) == "off"
    set_do.vapor_chaqueta_on.assert_not_called()
    assert fase._cascada.valvula is False
    # vuelve la lectura con la chaqueta en la histéresis: sigue OFF
    _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=CONSIGNA_BANDA - 1.5)
    set_do.vapor_chaqueta_on.assert_not_called()


# ── Modo cámara, reset, fallo y log ───────────────────────────────────────

def test_modo_camara_sin_cambio():
    fase, estado, set_do = _fase(chaqueta=False)
    _a_sostenimiento(fase, estado)
    _tick(fase, estado, T_OBJ, P_OBJ)
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_not_called()
    assert estado.cascada_chaqueta is None


def test_reset_crea_cascada_nueva_y_limpia_la_publicacion():
    fase, estado, _ = _fase()
    _a_sostenimiento(fase, estado)
    _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=250.0)
    anterior = fase._cascada
    fase.reset()
    assert isinstance(fase._cascada, CascadaChaqueta) and fase._cascada is not anterior
    assert fase._cascada.valvula is False
    assert estado.cascada_chaqueta is None


def test_fallo_limpia_la_publicacion():
    fase, estado, _ = _fase()
    _a_sostenimiento(fase, estado)
    _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=250.0)
    fase._fallo("prueba")
    assert estado.cascada_chaqueta is None
    assert fase._cascada.valvula is False


def test_cas04_valvula_publicada_es_la_orden_aplicada(monkeypatch):
    """CAS-04: como ESTERILIZACION, `valvula` publicada = orden aplicada a
    vapor_chaqueta, también cuando la cascada pide ON y prevalece otra regla."""
    fase, estado, set_do = _fase()
    _a_sostenimiento(fase, estado)
    casos = [(250.0, False, False), (CONSIGNA_BANDA + 0.5, False, False),
             (250.0, True, False), (250.0, False, True), (250.0, False, False)]
    for pch, inhibir, aislado in casos:
        estado.inhibir_vapor_chaqueta = inhibir
        monkeypatch.setattr(fase, "_vigilar_aislamiento",
                            (lambda *a: (True, None)) if aislado
                            else cal_mod.CalentamientoFase._vigilar_aislamiento.__get__(fase))
        set_do.reset_mock()
        _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=pch)
        assert estado.cascada_chaqueta["valvula"] is (_ultima_chaqueta(set_do) == "on")
        assert estado.cascada_chaqueta["valvula"] is fase._cascada.valvula


def test_log_sin_repeticion(caplog):
    fase, estado, _ = _fase()
    _a_sostenimiento(fase, estado)
    with caplog.at_level(logging.INFO):
        for _ in range(5):
            _tick(fase, estado, T_OBJ, P_OBJ, pres_chaqueta=250.0)
    mensajes = [r.getMessage() for r in caplog.records]
    assert sum("control en cascada" in m for m in mensajes) == 1
    assert sum(m.startswith("Cascada chaqueta:") for m in mensajes) == 1

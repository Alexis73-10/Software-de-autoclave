"""CAS-01 (tanda 33): componente puro de control en cascada de vapor_chaqueta.

CRI-01 (tanda 35): `evaluar` pide `ahora`; con el mismo instante en cada tick
(dt = 0) la integral no se mueve y dp = margen_est, así que estas pruebas
siguen fijando niveles, histéresis y falla cerrada. CRI-01 retiró el tope
techo - 2 de la banda y el parámetro p_techo (lo integral se prueba en
tests/test_cri_cascada.py)."""

import logging
import math

import pytest

from autoclave.state_machine.cycle_phases import cascada_chaqueta as cc
from autoclave.state_machine.cycle_phases.cascada_chaqueta import CascadaChaqueta

LOGGER = "autoclave.state_machine.cycle_phases.cascada_chaqueta"

# p_ref 200: baja < 198, alta > 201. banda: min(200 + 8, 350) = 208.
# baja (ajuste 8-nov): min(375-10, 350) = 350.
P_REF = 200.0
MARGEN = 8.0
PMAX = 375.0
SUMINISTRO = 350.0


def _ev(c, pc, pj, **kw):
    args = dict(p_ref=P_REF, margen_est=MARGEN,
                presion_max_chaqueta_control=PMAX, presion_suministro_vapor=SUMINISTRO,
                ahora=0.0)
    args.update(kw)
    return c.evaluar(pc, pj, **args)


# --- Niveles -------------------------------------------------------------

def test_nivel_baja_consigna_tope():
    r = _ev(CascadaChaqueta(), 197.9, 200.0)
    assert r.nivel == cc.NIVEL_BAJA
    assert r.consigna == pytest.approx(350.0)
    assert r.decision is True
    assert r.motivo == cc.MOTIVO_BAJO_CONSIGNA


def test_nivel_banda_consigna_margen():
    r = _ev(CascadaChaqueta(), 199.0, 200.0)
    assert r.nivel == cc.NIVEL_BANDA
    assert r.consigna == pytest.approx(208.0)
    assert r.decision is True


def test_bordes_de_banda_son_banda():
    assert _ev(CascadaChaqueta(), 198.0, 200.0).nivel == cc.NIVEL_BANDA
    assert _ev(CascadaChaqueta(), 201.0, 200.0).nivel == cc.NIVEL_BANDA


def test_nivel_alta_off_sin_consigna():
    c = CascadaChaqueta()
    assert _ev(c, 199.0, 190.0).decision is True
    r = _ev(c, 201.1, 150.0)
    assert r.nivel == cc.NIVEL_ALTA
    assert r.consigna is None
    assert r.decision is False
    assert r.motivo == cc.MOTIVO_CAMARA_ALTA
    assert c.valvula is False


def test_banda_consigna_sin_tope_de_techo():
    # CRI-01: margen 40 -> 240 (antes se recortaba a techo - 2 = 228)
    r = _ev(CascadaChaqueta(), 199.0, 200.0, margen_est=40.0)
    assert r.consigna == pytest.approx(240.0)


# --- Histéresis ----------------------------------------------------------

def test_histeresis_subiendo_no_conmuta_hasta_consigna():
    c = CascadaChaqueta()
    assert _ev(c, 199.0, 205.0).decision is True        # <= 208 - 3
    for pj in (205.5, 206.0, 207.0, 207.9):
        r = _ev(c, 199.0, pj)
        assert r.decision is True
        assert r.motivo == cc.MOTIVO_HISTERESIS
    r = _ev(c, 199.0, 208.0)
    assert r.decision is False
    assert r.motivo == cc.MOTIVO_CONSIGNA_ALCANZADA


def test_histeresis_bajando_no_conmuta_hasta_consigna_menos_3():
    c = CascadaChaqueta()
    assert _ev(c, 199.0, 209.0).decision is False
    for pj in (207.9, 207.0, 206.0, 205.1):
        r = _ev(c, 199.0, pj)
        assert r.decision is False
        assert r.motivo == cc.MOTIVO_HISTERESIS
    assert _ev(c, 199.0, 205.0).decision is True


def test_arranque_en_zona_de_histeresis_queda_off():
    r = _ev(CascadaChaqueta(), 199.0, 206.0)
    assert r.decision is False
    assert r.motivo == cc.MOTIVO_HISTERESIS


# --- Cambio de nivel en el mismo tick ------------------------------------

def test_cambio_banda_a_baja_reevalua_mismo_tick():
    c = CascadaChaqueta()
    assert _ev(c, 199.0, 210.0).decision is False       # banda, sobre 208
    r = _ev(c, 197.0, 210.0)                            # baja: consigna 350
    assert r.nivel == cc.NIVEL_BAJA
    assert r.decision is True


def test_cambio_baja_a_banda_reevalua_mismo_tick():
    c = CascadaChaqueta()
    assert _ev(c, 197.0, 215.0).decision is True        # baja, 215 <= 225
    r = _ev(c, 199.0, 215.0)                            # banda: 215 >= 208
    assert r.nivel == cc.NIVEL_BANDA
    assert r.decision is False


def test_cambio_de_nivel_conserva_valvula_en_histeresis():
    c = CascadaChaqueta()
    assert _ev(c, 197.0, 200.0).decision is True        # baja, ON
    r = _ev(c, 199.0, 206.0)                            # banda: 205 < 206 < 208
    assert r.decision is True
    assert r.motivo == cc.MOTIVO_HISTERESIS


def test_alta_a_banda_vuelve_a_encender_bajo_consigna_menos_3():
    c = CascadaChaqueta()
    _ev(c, 202.0, 150.0)
    assert _ev(c, 200.0, 206.0).decision is False       # histéresis, venía OFF
    assert _ev(c, 200.0, 204.0).decision is True


# --- Tope ----------------------------------------------------------------

def test_banda_limitada_por_tope_baja():
    # CRI-01: la banda solo la limita tope_baja (D-CHQ - 10 / suministro)
    r = _ev(CascadaChaqueta(), 199.0, 200.0, margen_est=30.0,
            presion_suministro_vapor=220.0)
    assert r.consigna == pytest.approx(220.0)


def test_tope_por_dchq_menos_10():
    assert CascadaChaqueta.tope_baja(300.0, 350.0) == pytest.approx(290.0)
    r = _ev(CascadaChaqueta(), 190.0, 200.0, presion_max_chaqueta_control=300.0)
    assert r.consigna == pytest.approx(290.0)


def test_tope_por_suministro():
    assert CascadaChaqueta.tope_baja(375.0, 250.0) == pytest.approx(250.0)
    r = _ev(CascadaChaqueta(), 190.0, 200.0, presion_suministro_vapor=250.0)
    assert r.consigna == pytest.approx(250.0)


# --- Ajuste 8-nov: tope del nivel baja ----------------------------------

def test_tope_baja_no_depende_del_techo():
    """Baja: min(presion_max_chaqueta_control - 10, suministro); con los
    defectos del equipo (375, 350) vale 350 (CRI-01: el techo ya no entra)."""
    r = _ev(CascadaChaqueta(), 190.0, 150.0)
    assert r.nivel == cc.NIVEL_BAJA
    assert r.consigna == pytest.approx(350.0)
    assert CascadaChaqueta.tope_baja(375.0, 350.0) == pytest.approx(350.0)
    assert CascadaChaqueta.tope_baja(355.0, 350.0) == pytest.approx(345.0)


def test_tope_baja_nunca_alcanza_dchq():
    for pmax in (300.0, 340.0, 375.0, 400.0):
        for sumi in (250.0, 350.0, 500.0):
            assert CascadaChaqueta.tope_baja(pmax, sumi) <= pmax - cc.MARGEN_DCHQ_KPA


def test_baja_histeresis_bajo_350():
    c = CascadaChaqueta()
    assert _ev(c, 190.0, 346.9).decision is True        # <= 350 - 3
    assert _ev(c, 190.0, 349.0).decision is True        # histéresis, venía ON
    assert _ev(c, 190.0, 350.0).decision is False       # consigna alcanzada
    assert _ev(c, 190.0, 348.0).decision is False       # histéresis, venía OFF


def test_paso_baja_a_banda_reevalua_en_el_mismo_tick():
    c = CascadaChaqueta()
    assert _ev(c, 190.0, 300.0).decision is True        # baja, consigna 350
    r = _ev(c, 199.0, 300.0)                            # banda, consigna 208
    assert r.consigna == pytest.approx(208.0)
    assert r.decision is False


def test_baja_parametros_invalidos_falla_cerrada():
    for kw in ({"presion_max_chaqueta_control": float("nan")},
               {"presion_suministro_vapor": None},
               {"presion_suministro_vapor": float("inf")}):
        r = _ev(CascadaChaqueta(), 190.0, 150.0, **kw)
        assert r.decision is False
        assert r.motivo == cc.MOTIVO_PARAMETROS_INVALIDOS


def test_tope_bajo_p_ref_advierte_una_vez_y_no_lo_supera(caplog):
    c = CascadaChaqueta()
    caplog.set_level(logging.WARNING, logger=LOGGER)
    # suministro 200 -> tope_baja 200 < p_ref + 1 = 201.
    for pc in (199.0, 199.5, 198.5, 190.0):
        r = _ev(c, pc, 150.0, presion_suministro_vapor=200.0)
        assert r.consigna == pytest.approx(200.0)
    avisos = [x for x in caplog.records if x.levelno == logging.WARNING]
    assert len(avisos) == 1
    assert "Cascada chaqueta" in avisos[0].getMessage()


def test_reset_rearma_la_advertencia(caplog):
    c = CascadaChaqueta()
    caplog.set_level(logging.WARNING, logger=LOGGER)
    _ev(c, 190.0, 150.0, presion_suministro_vapor=200.0)
    c.reset()
    _ev(c, 190.0, 150.0, presion_suministro_vapor=200.0)
    assert len([x for x in caplog.records if x.levelno == logging.WARNING]) == 2


def test_sin_advertencia_con_tope_holgado(caplog):
    caplog.set_level(logging.WARNING, logger=LOGGER)
    _ev(CascadaChaqueta(), 190.0, 150.0)
    assert not [x for x in caplog.records if x.levelno == logging.WARNING]


# --- Sin lectura y no finitos --------------------------------------------

INVALIDAS = [None, math.nan, math.inf, -math.inf, 0, 0.0, -5.0, True, "200"]


@pytest.mark.parametrize("valor", INVALIDAS)
def test_sin_lectura_camara_falla_cerrada(valor):
    c = CascadaChaqueta()
    assert _ev(c, 199.0, 190.0).decision is True
    r = _ev(c, valor, 190.0)
    assert r.decision is False
    assert r.consigna is None
    assert r.nivel == cc.NIVEL_SIN_DATOS
    assert r.motivo == cc.MOTIVO_SIN_LECTURA_CAMARA
    assert c.valvula is False


@pytest.mark.parametrize("valor", INVALIDAS)
def test_sin_lectura_chaqueta_falla_cerrada(valor):
    c = CascadaChaqueta()
    assert _ev(c, 199.0, 190.0).decision is True
    r = _ev(c, 199.0, valor)
    assert r.decision is False
    assert r.consigna is None
    assert r.motivo == cc.MOTIVO_SIN_LECTURA_CHAQUETA
    assert c.valvula is False


@pytest.mark.parametrize("campo", ["p_ref", "margen_est",
                                   "presion_max_chaqueta_control",
                                   "presion_suministro_vapor", "ahora"])
@pytest.mark.parametrize("valor", [None, math.nan, math.inf, -math.inf, "x", True])
def test_parametros_no_finitos_falla_cerrada(campo, valor):
    c = CascadaChaqueta()
    assert _ev(c, 199.0, 190.0).decision is True
    r = _ev(c, 199.0, 190.0, **{campo: valor})
    assert r.decision is False
    assert r.consigna is None
    assert r.motivo == cc.MOTIVO_PARAMETROS_INVALIDOS


def test_tras_falla_cerrada_reabre_solo_bajo_consigna_menos_3():
    c = CascadaChaqueta()
    _ev(c, 199.0, 190.0)
    _ev(c, None, 190.0)
    assert _ev(c, 199.0, 206.0).decision is False       # histéresis, venía OFF
    assert _ev(c, 199.0, 205.0).decision is True


# --- Log -----------------------------------------------------------------

def _lineas_info(caplog):
    return [x.getMessage() for x in caplog.records
            if x.levelno == logging.INFO and x.name == LOGGER]


def test_log_sin_repeticion_por_tick(caplog):
    c = CascadaChaqueta()
    caplog.set_level(logging.INFO, logger=LOGGER)
    for pj in (200.0, 203.0, 206.0, 208.5, 207.0, 204.0):   # banda, consigna fija
        _ev(c, 199.0, pj)
    lineas = _lineas_info(caplog)
    assert len(lineas) == 1
    assert lineas[0].startswith("Cascada chaqueta")
    assert "pres_camara=199.0" in lineas[0]
    assert "pres_chaqueta=200.0" in lineas[0]
    assert "nivel=banda" in lineas[0]
    assert "consigna=208.0" in lineas[0]


def test_log_una_linea_por_cambio_de_nivel_o_consigna(caplog):
    c = CascadaChaqueta()
    caplog.set_level(logging.INFO, logger=LOGGER)
    _ev(c, 199.0, 200.0)                    # banda (1)
    _ev(c, 199.5, 200.0)                    # sin cambio
    _ev(c, 197.0, 200.0)                    # baja (2)
    _ev(c, 196.0, 201.0)                    # sin cambio
    _ev(c, 196.0, 201.0, presion_suministro_vapor=340.0)   # consigna 340 (3)
    _ev(c, 202.0, 201.0, presion_suministro_vapor=340.0)   # alta (4)
    _ev(c, 203.0, 150.0, presion_suministro_vapor=340.0)   # sin cambio
    _ev(c, None, 150.0)                     # sin datos (5)
    _ev(c, None, None)                      # sin cambio
    lineas = _lineas_info(caplog)
    assert len(lineas) == 5
    assert all(x.startswith("Cascada chaqueta") for x in lineas)
    assert "nivel=alta" in lineas[3] and "consigna=—" in lineas[3]
    assert "sin_datos" in lineas[4]


# --- Publicación y reset -------------------------------------------------

def test_publicar():
    c = CascadaChaqueta()
    assert c.publicar() == {"nivel": None, "consigna": None, "valvula": False, "dp": None}
    _ev(c, 199.0, 200.0)
    assert c.publicar() == {"nivel": "banda", "consigna": pytest.approx(208.0),
                            "valvula": True, "dp": pytest.approx(8.0)}
    _ev(c, 202.0, 200.0)
    assert c.publicar() == {"nivel": "alta", "consigna": None, "valvula": False,
                            "dp": pytest.approx(8.0)}


def test_reset():
    c = CascadaChaqueta()
    _ev(c, 199.0, 200.0)
    c.reset()
    assert c.valvula is False
    assert c.publicar() == {"nivel": None, "consigna": None, "valvula": False, "dp": None}
    assert _ev(c, 199.0, 206.0).decision is False       # sin memoria de ON


def test_constantes():
    assert cc.HISTERESIS_KPA == 3.0
    assert not hasattr(cc, "MARGEN_TECHO_KPA")         # CRI-01: retirado
    assert cc.UMBRAL_BAJO_KPA == 2.0
    assert cc.UMBRAL_ALTO_KPA == 1.0

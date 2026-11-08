"""Tanda 33, CAS-04: criterio de liberación de la cascada de chaqueta con la
planta simulada (valores PROVISIONALES, tests/helpers/planta_vapor.py; tabla y
comparación con la alpha.24 en docs/informes/tanda33/CAS04_tabla.md).

Criterio: COMPLETADO; presión mínima de cámara en ESTERILIZACION >=
Psat(T_est) − brecha_error_presion + 1,5 (204,5 kPa a 121 °C, 303,7 a 134 °C);
aislamientos VCH-AIS <= 1; chaqueta real máxima < presion_max_chaqueta_control
(375); a 134 °C sobreimpulso <= 0,59 + 0,2 K.

Lo que cumple se exige; lo que no cumple queda marcado xfail(strict=True) con
el motivo, para que un cambio de comportamiento (en cualquier sentido) se vea:
  - caudal «abierto» (válvula de asiento sin restricción, la configuración
    REAL confirmada por Cristian) con k = 1,00 y 0,95: cumple;
  - caudal «abierto» con k = 1,07 (transmisor de chaqueta que lee alto): NO
    cumple en Líquidos (CIC-04 o temperatura baja, sin aislamientos: falla
    segura, dependencia de calibración HAZ-CAS-02) ni a 134 °C (tiempo límite
    de CALENTAMIENTO en la rampa A14-M2, igual en la alpha.24);
  - caudal «restrictivo» (0,015/s): NO cumple con ningún k. Líquidos: CIC-04
    sin aislamientos (con el paso restrictivo sostener la cámara exige la
    chaqueta ~23 kPa sobre ella, por encima del tope techo − 2 de la cascada;
    ningún ajuste de HISTERESIS_KPA 2–5 ni MARGEN_TECHO_KPA 1–4 lo corrige);
    134 °C: tiempo límite de CALENTAMIENTO en la rampa, igual en la alpha.24.
"""
import logging

import pytest

from autoclave.core.runtime.status import EstadoAutoclave
from tests.banco import t33_planta_tabla as tb
from tests.helpers import planta_vapor as pv

pytestmark = pytest.mark.req("CAS-04")


@pytest.fixture(autouse=True)
def _sin_log():
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


# ── Extensiones de la planta ──────────────────────────────────────────────

def test_planta_por_defecto_sin_cambio():
    assert pv.PlantaVapor.GANANCIA_CHAQUETA == 1.0
    assert pv.PlantaVapor.PASO_CAMARA == 0.06
    assert pv.VARIANTES_CAUDAL == {"restrictivo": {"PASO_CAMARA": 0.015},
                                   "abierto": {"PASO_CAMARA": 0.1}}
    estado = EstadoAutoclave()
    planta = pv.PlantaVapor(pv.ModuloEsDoble(estado), 75.0, True)
    planta.publicar(estado)
    assert estado.sensores_pres["pres_chaqueta"] == planta.p_chaqueta


@pytest.mark.parametrize("k", [1.07, 0.95])
def test_error_de_ganancia_de_la_lectura_de_chaqueta(k):
    estado = EstadoAutoclave()
    planta = pv.PlantaVapor(pv.ModuloEsDoble(estado), 75.0, True,
                            ajustes={"GANANCIA_CHAQUETA": k}, p_chaqueta_inicial=208.0)
    planta.publicar(estado)
    assert estado.sensores_pres["pres_chaqueta"] == pytest.approx(75.0 + (208.0 - 75.0) * k)
    assert planta.p_chaqueta == 208.0          # la planta conserva la real
    assert planta.lectura_chaqueta(75.0) == pytest.approx(75.0)


# ── Criterio de liberación ────────────────────────────────────────────────

def _esperado(esc):
    nombre, carga, caudal, k, _ = esc
    if caudal is None or (caudal == "abierto" and k in (1.00, 0.95)):
        return None
    if caudal == "abierto":
        return ("HAZ-CAS-02: transmisor que lee alto (k=1,07)"
                + ("; 134 °C: rampa A14-M2, igual en alpha.24" if carga == "134" else ""))
    return ("caudal restrictivo: tope de la cascada bajo la chaqueta necesaria"
            if carga == "liquidos" else "caudal restrictivo: rampa A14-M2, igual en alpha.24")


_ESCENARIOS = list(tb.escenarios())


@pytest.mark.parametrize(
    "esc",
    [pytest.param(e, marks=pytest.mark.xfail(strict=True, reason=_esperado(e)))
     if _esperado(e) else e for e in _ESCENARIOS],
    ids=[f"{e[0]}|{e[2]}|k={e[3]:.2f}" for e in _ESCENARIOS])
def test_criterio_cas04(esc):
    f = tb.correr(pv, *esc)
    assert f["completado"], f["resultado"]
    assert f["p_min_ester"] >= f["p_min_req"], f
    assert f["aislamientos"] <= 1, f
    assert f["p_chq_max"] < 375.0, f
    if f["carga"] == "134":
        assert f["sobreimpulso_k"] <= 0.59 + 0.2, f


@pytest.mark.parametrize("k", [1.00, 1.07])
def test_liquidos_que_no_cumplen_fallan_seguro(k):
    """Restrictivo k=1,00 y abierto k=1,07 (add_est 11): falla por presión o
    temperatura baja, sin aislamientos y con la chaqueta lejos de D-CHQ."""
    caudal = "restrictivo" if k == 1.00 else "abierto"
    f = tb.correr(pv, "LIQ", "liquidos", caudal, k,
                  {"esterilizacion__presion_add_esterilizacion": 11.0})
    assert not f["completado"]
    assert "baja" in f["resultado"]
    assert f["aislamientos"] == 0
    assert f["p_chq_max"] < 300.0

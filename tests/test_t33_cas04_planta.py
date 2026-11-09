"""Tanda 33, CAS-04: criterio de liberación de la cascada de chaqueta con la
planta simulada (valores PROVISIONALES, tests/helpers/planta_vapor.py; tabla y
comparación con la alpha.24 en docs/informes/tanda33/CAS04_tabla.md).

Umbrales: COMPLETADO; presión mínima de cámara en ESTERILIZACION >=
Psat(T_est) − brecha_error_presion + 1,5 (204,5 kPa a 121 °C, 303,7 a 134 °C);
aislamientos VCH-AIS <= 1; chaqueta real máxima < presion_max_chaqueta_control
(375); a 134 °C sobreimpulso <= 0,59 + 0,2 K.

Criterio de liberación (Cristian, 8-nov, con el ajuste del tope de la baja):
k = 1,00 con caudal abierto Y con caudal restrictivo. Regla: si el abierto
k = 1,00 deja de cumplir se revierte el ajuste; si solo falla el restrictivo se
libera con el ajuste y el restrictivo queda como caracterización. Lo que no
cumple queda xfail(strict=True) con su motivo, para que un cambio de
comportamiento (en cualquier sentido) se vea:
  - excluido: 134 °C con timeout de CALENTAMIENTO (rampa con A14-M2, que CAS no
    toca; igual en la alpha.24);
  - caracterización: caudal restrictivo k = 1,00 en Líquidos con
    add_liq 20 (presión mínima 204,2–204,3 kPa, bajo 204,5 por 0,2–0,3 kPa;
    sobre el umbral de falla 203,0; COMPLETADO);
  - informativos: k = 1,07 y k = 0,95 (dependencia de calibración,
    HAZ-CAS-02).
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
    """None si el escenario cumple; si no, el motivo del xfail."""
    nombre, carga, caudal, k, valores = esc
    if caudal is None:
        return None
    if carga == "134" and (caudal == "restrictivo" or k == 1.07):
        return "excluido: timeout de CALENTAMIENTO en la rampa A14-M2, igual en alpha.24"
    if k == 1.07:
        return "informativo, HAZ-CAS-02: transmisor que lee alto (k=1,07)"
    if caudal == "restrictivo" and k == 0.95:
        return "informativo, HAZ-CAS-02: transmisor que lee bajo (k=0,95) con caudal restrictivo"
    if (caudal == "restrictivo" and k == 1.00
            and valores.get("calentamiento__presion_add_liquido_calentamiento") == 20.0):
        return ("caracterización: caudal restrictivo, presión mínima 204,2–204,3 kPa "
                "bajo 204,5 (COMPLETADO)")
    return None


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


@pytest.mark.parametrize("caudal,k,add_liq", [("restrictivo", 1.00, 20.0),
                                               ("restrictivo", 0.95, 15.0),
                                               ("abierto", 1.07, 15.0)])
def test_liquidos_que_no_cumplen_quedan_lejos_de_la_falla(caudal, k, add_liq):
    """Con el ajuste del 8-nov los Líquidos que no cumplen el criterio
    completan igual: presión mínima sobre el umbral de falla (Psat − 2),
    aislamientos <= 1 y la chaqueta bajo D-CHQ − 10."""
    f = tb.correr(pv, "LIQ", "liquidos", caudal, k,
                  {"esterilizacion__presion_add_esterilizacion": 11.0,
                   "calentamiento__presion_add_liquido_calentamiento": add_liq})
    assert f["completado"], f["resultado"]
    assert f["p_min_ester"] >= f["p_min_req"] - 1.5, f
    assert f["aislamientos"] <= 1, f
    assert f["p_chq_max"] < 375.0 - 10.0, f

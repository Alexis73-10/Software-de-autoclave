"""Tanda 13 (S13, VAP-01): saturación con IAPWS-IF97, región 4.

Decisión 4 de docs/mis_plans/decisiones_tanda_13.md: valores de verificación
de la norma (tablas 35 y 36), puntos de trabajo y ida y vuelta.
"""
import math

import pytest

from autoclave.core.runtime.steam import p_saturacion_kpa, t_saturacion_c


# ── Tabla 35 de IAPWS-IF97: ps(T), T en K → p en MPa ─────────────────────────
@pytest.mark.parametrize("t_k, p_mpa", [
    (300.0, 0.353658941e-2),
    (500.0, 0.263889776e1),
    (600.0, 0.123443146e2),
])
def test_tabla_35_presion_saturacion(t_k, p_mpa):
    p_kpa = p_saturacion_kpa(t_k - 273.15)
    assert p_kpa / 1000.0 == pytest.approx(p_mpa, rel=1e-8)


# ── Tabla 36 de IAPWS-IF97: Ts(p), p en MPa → T en K ─────────────────────────
@pytest.mark.parametrize("p_mpa, t_k", [
    (0.1, 372.755919),
    (1.0, 453.035632),
    (10.0, 584.149488),
])
def test_tabla_36_temperatura_saturacion(p_mpa, t_k):
    t_c = t_saturacion_c(p_mpa * 1000.0)
    assert abs((t_c + 273.15) - t_k) < 1e-6


# ── Puntos de trabajo (±0.02 kPa) ────────────────────────────────────────────
@pytest.mark.parametrize("t_c, p_kpa", [
    (121.0, 205.04),
    (134.0, 304.20),
    (134.5, 308.67),
])
def test_puntos_de_trabajo(t_c, p_kpa):
    assert abs(p_saturacion_kpa(t_c) - p_kpa) <= 0.02


# ── Ida y vuelta T → p → T en 100–145 °C ─────────────────────────────────────
@pytest.mark.parametrize("t", [100.0 + 0.25 * i for i in range(181)])
def test_ida_y_vuelta_100_a_145(t):
    assert abs(t_saturacion_c(p_saturacion_kpa(t)) - t) < 1e-6


def test_monotonica_en_zona_de_trabajo():
    temps = [100.0 + i for i in range(46)]
    presiones = [p_saturacion_kpa(t) for t in temps]
    assert all(a < b for a, b in zip(presiones, presiones[1:]))


# ── Validez (decisión 3): 0.01–373.946 °C; fuera → ValueError ─────────────────
def test_extremos_del_rango_validos():
    assert p_saturacion_kpa(0.01) == pytest.approx(0.611657, abs=1e-5)
    assert p_saturacion_kpa(373.946) == pytest.approx(22064.0, rel=1e-4)


@pytest.mark.parametrize("t", [0.0, -1.0, -40.0, 373.95, 400.0, 1000.0,
                               math.nan, math.inf, -math.inf])
def test_temperatura_fuera_de_rango_lanza_valueerror(t):
    with pytest.raises(ValueError):
        p_saturacion_kpa(t)


@pytest.mark.parametrize("p", [0.0, -1.0, -300.0, 0.5, 22100.0, 1e9,
                               math.nan, math.inf, -math.inf])
def test_presion_fuera_de_rango_lanza_valueerror(p):
    with pytest.raises(ValueError):
        t_saturacion_c(p)


def test_extremos_de_presion_validos():
    assert t_saturacion_c(p_saturacion_kpa(0.01)) == pytest.approx(0.01, abs=1e-6)
    assert t_saturacion_c(22064.0) == pytest.approx(373.946, abs=1e-3)


# ── Valores de referencia derivados (decisión 5) ──────────────────────────────
def test_referencias_derivadas():
    from autoclave.core.managers.catalogo_parametros import consigna_chaqueta
    assert round(p_saturacion_kpa(134.0) + 9, 1) == 313.2          # techo 134 °C / 9
    assert round(consigna_chaqueta(134.0, 9.0, 1.5, 15.0), 1) == 328.2
    assert round(consigna_chaqueta(121.0, 11.0, 1.5, 15.0), 2) == 231.04  # chaqueta 121 °C / 11


# ── Llamadores de validación: temperatura fuera de la tabla (DECISIÓN SIN CONFIRMAR)
@pytest.mark.parametrize("t", [0, -5, 0.0, 400, 999])
@pytest.mark.parametrize("fase, clave", [("esterilizacion", "temperatura_esterilizacion"),
                                         ("calentamiento", "temperatura_calentamiento")])
def test_programa_con_temperatura_fuera_de_tabla_da_errores_sin_lanzar(fase, clave, t):
    """Antes de la tanda 13 la fórmula vieja no lanzaba: un programa con una
    temperatura fuera del catálogo quedaba DAÑADO. Debe seguir igual (lista
    de errores), no romper la carga con ValueError."""
    import copy, glob, json
    from autoclave.core.managers import catalogo_parametros as cp
    ruta = sorted(glob.glob("src/autoclave/cycles/factory/*.json"))[0]
    with open(ruta, encoding="utf-8") as f:
        parametros = copy.deepcopy(json.load(f)["parameters"])
    parametros[fase][clave]["value"] = t
    errores = cp.errores_programa(parametros)
    assert any(clave in e for e in errores)


@pytest.mark.parametrize("t", [0, -5, 400, 999])
def test_consigna_chaqueta_fuera_de_tabla_es_none(t):
    from autoclave.core.managers.catalogo_parametros import consigna_chaqueta
    assert consigna_chaqueta(t, 9.0, 1.5, 15.0) is None

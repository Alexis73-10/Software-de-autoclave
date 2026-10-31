# tests/test_llf_fraccion_fases.py
#
# Llenado de la barra de fases (LLF A-2, docs/mis_plans/planeacion_llenado_fases_decisiones.md):
# fraccion_fase y los campos `fraccion`/`referencia_s` por fase de armar_progreso.
# Una fase que no está "completada" nunca pasa de TOPE_FRACCION_ACTIVA (HAZ-LLF-01).

import math

import pytest

from autoclave.core.runtime import progreso_ciclo as pc

pytestmark = pytest.mark.req("REQ-36")

MIN = 60.0
TOPE = pc.TOPE_FRACCION_ACTIVA
_APLICA = ["vacio", "calentamiento", "esterilizacion", "descompresion", "secado"]
_REF = {"vacio": 12 * MIN, "calentamiento": 3 * MIN, "esterilizacion": 15 * MIN,
        "descompresion": 2 * MIN, "secado": 13 * MIN}


def test_tope_es_090():
    assert TOPE == 0.90


# ── fraccion_fase ───────────────────────────────────────────────────────

def test_pendiente_es_cero():
    assert pc.fraccion_fase("pendiente", None, 180.0) == 0.0
    assert pc.fraccion_fase("pendiente", None, None) == 0.0


def test_completada_es_uno():
    assert pc.fraccion_fase("completada", 30.0, 180.0) == 1.0
    assert pc.fraccion_fase("completada", None, None) == 1.0


@pytest.mark.parametrize("estado", ["fallida", "interrumpida", "rara", None])
def test_fallida_interrumpida_o_desconocido_es_none(estado):
    assert pc.fraccion_fase(estado, 30.0, 180.0) is None


def test_dentro_de_la_referencia_es_lineal():
    assert pc.fraccion_fase("activa", 0.0, 180.0) == 0.0
    assert pc.fraccion_fase("activa", 45.0, 180.0) == 0.25
    assert pc.fraccion_fase("activa", 90.0, 180.0) == 0.5
    assert pc.fraccion_fase("activa", None, 180.0) == 0.0


def test_en_e_igual_a_ref_empieza_la_extension():
    # e = ref: r = 5 min de extensión → 180/(180+300) = 0.375
    assert pc.fraccion_fase("activa", 180.0, 180.0) == round(180.0 / 480.0, 4)
    # justo antes de la referencia la fracción ingenua pasa del tope
    assert pc.fraccion_fase("activa", 179.9, 180.0) == TOPE


def test_diente_de_sierra_en_las_extensiones_baja_en_la_renovacion():
    ref = 180.0
    antes = pc.fraccion_fase("activa", ref + 299.0, ref)       # casi al final del bloque
    renov = pc.fraccion_fase("activa", ref + 300.0, ref)       # bloque renovado
    despues = pc.fraccion_fase("activa", ref + 450.0, ref)
    assert antes == TOPE
    assert renov < antes
    assert renov == round((ref + 300.0) / (ref + 600.0), 4)
    assert renov < despues <= TOPE


@pytest.mark.parametrize("e", [0.0, 10.0, 179.0, 179.999, 180.0, 400.0, 479.9,
                               480.0, 1e6, 1e9])
def test_tope_en_todo_no_completado(e):
    v = pc.fraccion_fase("activa", e, 180.0)
    assert 0.0 <= v <= TOPE
    assert pc.fraccion_fase("activa", None, None, 0.0, 420.0, conteo_propio=True) == TOPE
    assert pc.fraccion_fase("activa", None, None, -5.0, 420.0, conteo_propio=True) == 0.0


@pytest.mark.parametrize("ref", [None, 0.0, -1.0, "180", math.nan, math.inf, True])
def test_sin_referencia_es_none(ref):
    assert pc.fraccion_fase("activa", 60.0, ref) is None


def test_esterilizacion_con_restante():
    assert pc.fraccion_fase("activa", 100.0, 900.0, 320.0, 420.0, conteo_propio=True) == 0.2381
    assert pc.fraccion_fase("activa", 0.0, None, 210.0, 420.0, conteo_propio=True) == 0.5


def test_esterilizacion_detenida_es_cero():
    # excursión confirmada: la fase publica restante = total
    assert pc.fraccion_fase("activa", 300.0, 900.0, 420.0, 420.0, conteo_propio=True) == 0.0


def test_esterilizacion_restante_cero_con_f0_pendiente_queda_en_el_tope():
    assert pc.fraccion_fase("activa", 500.0, 900.0, 0.0, 420.0, conteo_propio=True) == TOPE


@pytest.mark.parametrize("restante,total", [(None, 420.0), (320.0, None), (320.0, 0.0),
                                            (math.nan, 420.0), (320.0, True)])
def test_esterilizacion_sin_conteo_valido_es_cero(restante, total):
    # sin el conteo de la fase no se usa el historial: 0.0
    assert pc.fraccion_fase("activa", 100.0, 900.0, restante, total, conteo_propio=True) == 0.0


def test_resultado_redondeado_a_4_decimales():
    v = pc.fraccion_fase("activa", 60.0, 180.0)
    assert v == 0.3333


# ── armar_progreso ──────────────────────────────────────────────────────

def _filas(*fases):
    filas, t = [], 0.0
    for f, d in fases:
        filas.append({"fase": f, "inicio_s": t, "fin_s": None if d is None else t + d,
                      "duracion_s": d})
        if d is not None:
            t += d
    return filas


def test_en_curso_anteriores_uno_activa_segun_regla_siguientes_cero():
    filas = _filas(("PRE_VACIO", 700.0), ("CALENTAMIENTO", None))
    p = pc.armar_progreso(_APLICA, filas, "CALENTAMIENTO", 790.0, _REF)
    assert [f["fraccion"] for f in p["fases"]] == [1.0, 0.5, 0.0, 0.0, 0.0]
    assert [f["referencia_s"] for f in p["fases"]] == [_REF[f] for f in _APLICA]


def test_sin_referencia_activa_none_y_referencia_none():
    filas = _filas(("PRE_VACIO", None))
    p = pc.armar_progreso(_APLICA, filas, "PRE_VACIO", 30.0, {})
    assert p["fases"][0]["fraccion"] is None
    assert all(f["referencia_s"] is None for f in p["fases"])
    assert [f["fraccion"] for f in p["fases"][1:]] == [0.0] * 4


def test_esterilizacion_activa_usa_el_total_como_referencia():
    filas = _filas(("PRE_VACIO", 700.0), ("CALENTAMIENTO", 180.0), ("ESTERILIZACION", None))
    p = pc.armar_progreso(_APLICA, filas, "ESTERILIZACION", 980.0, _REF,
                          restante_exposicion_s=320.0, total_exposicion_s=420.0)
    ester = p["fases"][2]
    assert ester["fraccion"] == 0.2381
    assert ester["referencia_s"] == 420.0
    # restante_s sin cambio: usa el restante propio
    assert p["restante_s"] == 320.0 + 2 * MIN + 13 * MIN


def test_esterilizacion_activa_sin_total_cero_y_referencia_del_historial():
    filas = _filas(("PRE_VACIO", 700.0), ("CALENTAMIENTO", 180.0), ("ESTERILIZACION", None))
    p = pc.armar_progreso(_APLICA, filas, "ESTERILIZACION", 980.0, _REF,
                          restante_exposicion_s=None)
    ester = p["fases"][2]
    assert ester["fraccion"] == 0.0
    assert ester["referencia_s"] == 15 * MIN


def test_total_fuera_de_esterilizacion_se_ignora():
    filas = _filas(("PRE_VACIO", None))
    p = pc.armar_progreso(_APLICA, filas, "PRE_VACIO", 60.0, _REF,
                          restante_exposicion_s=10.0, total_exposicion_s=420.0)
    assert p["fases"][0]["fraccion"] == round(60.0 / 720.0, 4)
    assert p["fases"][2]["referencia_s"] == 15 * MIN


def test_completado_todas_uno():
    filas = _filas(*[(f, 10.0) for f in ("PRE_VACIO", "CALENTAMIENTO", "ESTERILIZACION",
                                         "DESCOMPRESION", "SECADO")])
    p = pc.armar_progreso(_APLICA, filas, "COMPLETADO", 50.0, _REF)
    assert [f["fraccion"] for f in p["fases"]] == [1.0] * 5
    assert p["restante_s"] == 0.0


@pytest.mark.parametrize("fase_ciclo,estado_term", [("FALLO_ESTERILIZACION", "fallida"),
                                                    ("EMERGENCIA", "fallida"),
                                                    ("CANCELADO", "interrumpida")])
def test_fallo_o_cancelado_terminacion_none_anteriores_uno_siguientes_cero(fase_ciclo, estado_term):
    filas = _filas(("PRE_VACIO", 700.0), ("CALENTAMIENTO", 180.0), ("ESTERILIZACION", 30.0))
    p = pc.armar_progreso(_APLICA, filas, fase_ciclo, 910.0, _REF,
                          restante_exposicion_s=100.0, total_exposicion_s=420.0)
    assert [f["estado"] for f in p["fases"]] == ["completada", "completada", estado_term,
                                                 "pendiente", "pendiente"]
    assert [f["fraccion"] for f in p["fases"]] == [1.0, 1.0, None, 0.0, 0.0]
    assert p["fases"][2]["referencia_s"] == 15 * MIN
    assert p["fase_terminacion"] == "esterilizacion"
    assert p["restante_s"] is None


def test_ningun_no_completado_supera_el_tope():
    filas = _filas(("PRE_VACIO", 700.0), ("CALENTAMIENTO", None))
    for t in range(700, 700 + 3000, 7):
        p = pc.armar_progreso(_APLICA, filas, "CALENTAMIENTO", float(t), _REF)
        for f in p["fases"]:
            if f["estado"] != "completada" and f["fraccion"] is not None:
                assert f["fraccion"] <= TOPE


def test_campos_previos_no_cambian():
    filas = _filas(("PRE_VACIO", 700.0), ("CALENTAMIENTO", None))
    p = pc.armar_progreso(_APLICA, filas, "CALENTAMIENTO", 760.0, _REF)
    assert set(p) == {"fase_activa", "resultado", "fase_terminacion", "fases",
                      "transcurrido_s", "restante_s"}
    assert all(set(f) == {"fase", "estado", "duracion_s", "fraccion", "referencia_s"}
               for f in p["fases"])
    assert p["restante_s"] == (3 * MIN - 60.0) + 15 * MIN + 2 * MIN + 13 * MIN


def test_llamada_posicional_de_6_argumentos_sigue_funcionando():
    # simulador/servidor.py llama armar_progreso de forma posicional
    filas = _filas(("PRE_VACIO", 700.0), ("CALENTAMIENTO", 180.0), ("ESTERILIZACION", None))
    p = pc.armar_progreso(_APLICA, filas, "ESTERILIZACION", 980.0, _REF, 320.0)
    assert p["restante_s"] == 320.0 + 2 * MIN + 13 * MIN
    assert p["fases"][2]["fraccion"] == 0.0          # sin total: 0.0
    assert p["fases"][2]["referencia_s"] == 15 * MIN
    # el simulador (servidor.py:186) pasa 5
    p5 = pc.armar_progreso(_APLICA, filas, "ESTERILIZACION", 980.0, _REF)
    assert p5["fases"][2]["fraccion"] == 0.0
    # el total solo entra por palabra clave
    with pytest.raises(TypeError):
        pc.armar_progreso(_APLICA, filas, "ESTERILIZACION", 980.0, _REF, 320.0, 420.0)


# ── Revisión: entradas hostiles y barrido de estados (HAZ-LLF-01) ───────────

@pytest.mark.parametrize("restante,total,esperado", [
    (500.0, 420.0, 0.0),                      # restante mayor que el total
    (float("inf"), 420.0, 0.0),
    (float("nan"), 420.0, 0.0),
    (100.0, float("inf"), 0.0),
    (100.0, float("nan"), 0.0),
    (0.0, 1e-300, TOPE),                      # total diminuto: acotado
    (1e-300, 1e-300, 0.0),
])
def test_conteo_propio_entradas_extremas(restante, total, esperado):
    r = pc.fraccion_fase("activa", 10.0, None, restante, total, conteo_propio=True)
    assert r == esperado


def test_conteo_propio_int_gigante_no_lanza():
    gigante = 10 ** 400
    for restante, total in [(gigante, 420.0), (0, gigante), (gigante, gigante)]:
        r = pc.fraccion_fase("activa", 10.0, None, restante, total, conteo_propio=True)
        assert r is None or 0.0 <= r <= TOPE


def test_referencia_int_gigante_no_lanza():
    r = pc.fraccion_fase("activa", 10 ** 400, 10 ** 400)
    assert r is None or 0.0 <= r <= TOPE
    r = pc.fraccion_fase("activa", 10.0, 10 ** 400)
    assert r is None or 0.0 <= r <= TOPE


def test_armar_progreso_con_int_gigante_no_lanza():
    filas = [{"fase": "ESTERILIZACION", "inicio_s": 0.0, "fin_s": None, "duracion_s": None}]
    gigante = 10 ** 400
    # (restante_s usa otra ruta, fuera del LLF: aquí el restante es normal)
    p = pc.armar_progreso(["esterilizacion"], filas, "ESTERILIZACION", 10.0,
                          {"esterilizacion": 420.0}, 100.0, total_exposicion_s=gigante)
    f = p["fases"][0]
    assert f["fraccion"] is None or 0.0 <= f["fraccion"] <= TOPE
    p = pc.armar_progreso(["esterilizacion"], filas, "ESTERILIZACION", 10.0,
                          {"esterilizacion": gigante}, 100.0, total_exposicion_s=420.0)
    assert p["fases"][0]["referencia_s"] == 420.0


_CIERRES = ["COMPLETADO", "CANCELADO", "EMERGENCIA", "SENSOR_AUSENTE", "FALLO_ESTERILIZACION",
            "FALLO_CALENTAMIENTO", "FALLO_RARO", "", None, "CALENTAMIENTO", "ESTERILIZACION",
            "PRE_VACIO", "DESCOMPRESION", "SECADO"]
_VALORES = [None, 0, 0.0, 5.0, 420.0, 1e9, 1e-300, -1.0, float("nan"), float("inf"), True,
            "x", 10 ** 400]
_RESTANTES = [v for v in _VALORES if v != 10 ** 400]     # restante_s no es del LLF
_REFS = [v for v in _VALORES if isinstance(v, float) or v == 0]   # el endpoint arma floats


@pytest.mark.parametrize("fase_ciclo", _CIERRES)
def test_barrido_nunca_supera_el_tope_si_no_esta_completada(fase_ciclo):
    filas = [{"fase": "PRE_VACIO", "inicio_s": 0.0, "fin_s": 100.0, "duracion_s": 100.0},
             {"fase": "CALENTAMIENTO", "inicio_s": 100.0, "fin_s": 200.0, "duracion_s": 100.0},
             {"fase": "ESTERILIZACION", "inicio_s": 200.0, "fin_s": None, "duracion_s": None}]
    for rest in _RESTANTES:
        for tot in _VALORES:
            for ref in _REFS:
                p = pc.armar_progreso(_APLICA, filas, fase_ciclo, 500.0,
                                      {f: ref for f in _APLICA}, rest, total_exposicion_s=tot)
                for item in p["fases"]:
                    if item["estado"] != "completada":
                        assert item["fraccion"] is None or item["fraccion"] <= TOPE


def test_esterilizacion_activa_restante_cero_total_420_es_tope():
    filas = [{"fase": "ESTERILIZACION", "inicio_s": 0.0, "fin_s": None, "duracion_s": None}]
    p = pc.armar_progreso(["esterilizacion", "descompresion"], filas, "ESTERILIZACION", 420.0,
                          {"esterilizacion": 420.0, "descompresion": 120.0}, 0.0,
                          total_exposicion_s=420.0)
    ester = p["fases"][0]
    assert ester["estado"] == "activa"
    assert ester["fraccion"] == TOPE
    assert ester["referencia_s"] == 420.0

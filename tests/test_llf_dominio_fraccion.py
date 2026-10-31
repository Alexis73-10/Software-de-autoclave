# tests/test_llf_dominio_fraccion.py
#
# LLF (llenado de fases): fraccion y referencia_s por fase en la frontera de
# confianza de la UI (ui_qml/domain/ciclo_en_curso.normalizar_progreso).

import pytest

from autoclave.core.runtime.progreso_ciclo import TOPE_FRACCION_ACTIVA
from autoclave.ui_qml.domain.ciclo_en_curso import NIVEL_INDETERMINADO, normalizar_progreso

pytestmark = pytest.mark.req("REQ-36")


def _fase(estado, **extra):
    r = normalizar_progreso({"activo": True, "fases": [
        {"fase": "calentamiento", "estado": estado, "duracion_s": 1.0, **extra}]})
    return r["fases"][0]


def test_constantes():
    assert TOPE_FRACCION_ACTIVA == 0.90
    assert NIVEL_INDETERMINADO == 0.25


@pytest.mark.parametrize("valor", ["0.5", True, float("nan"), float("inf"), -0.1, 1.5, None])
def test_activa_valor_invalido_es_none(valor):
    assert _fase("activa", fraccion=valor)["fraccion"] is None


def test_activa_sin_campo_es_none():
    assert _fase("activa")["fraccion"] is None


def test_activa_se_limita_al_tope():
    assert _fase("activa", fraccion=0.97)["fraccion"] == TOPE_FRACCION_ACTIVA
    assert _fase("activa", fraccion=1.0)["fraccion"] == TOPE_FRACCION_ACTIVA


def test_activa_valida_pasa():
    assert _fase("activa", fraccion=0.4)["fraccion"] == 0.4
    assert _fase("activa", fraccion=0)["fraccion"] == 0.0


@pytest.mark.parametrize("valor", [0.3, None, "x", -5, float("nan")])
def test_completada_siempre_uno(valor):
    assert _fase("completada", fraccion=valor)["fraccion"] == 1.0


@pytest.mark.parametrize("valor", [0.3, None, "x"])
def test_pendiente_y_desconocido_cero(valor):
    assert _fase("pendiente", fraccion=valor)["fraccion"] == 0.0
    assert _fase("rara", fraccion=valor)["fraccion"] == 0.0


@pytest.mark.parametrize("estado", ["fallida", "interrumpida"])
def test_terminadas_sin_fraccion(estado):
    assert _fase(estado, fraccion=0.5)["fraccion"] is None


@pytest.mark.parametrize("valor,esperado", [
    (420.0, 420.0), (0, 0.0), (-1, None), ("x", None), (True, None),
    (float("nan"), None), (float("inf"), None), (None, None)])
def test_referencia_s(valor, esperado):
    assert _fase("activa", referencia_s=valor)["referencia_s"] == esperado


def test_sin_ciclo_sigue_vacio():
    assert normalizar_progreso({"activo": False})["fases"] == []


# ── Revisión: fases terminadas con fracción 1.0 ─────────────────────────────

@pytest.mark.parametrize("estado", ["fallida", "interrumpida"])
def test_terminadas_con_fraccion_uno_son_none(estado):
    assert _fase(estado, fraccion=1.0)["fraccion"] is None


def test_activa_con_uno_es_tope():
    assert _fase("activa", fraccion=1.0)["fraccion"] == TOPE_FRACCION_ACTIVA == 0.90

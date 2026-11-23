# tests/test_fab_e3_solo_lectura.py
#
# Modo fábrica, Etapa 3, FAB-06: en ENTREGADO la base de fábrica del equipo
# (parámetros, calibración y defectos de programas) es de solo lectura. Solo
# el cierre (Etapa 5) la escribe, a través de las funciones de
# core/runtime/fabrica_equipo.py. Vigilancia por AST sobre src/autoclave:
#   1. solo fabrica_equipo.py nombra los dos archivos (literal);
#   2. las tres funciones de escritura solo se nombran en fabrica_equipo.py y
#      en el módulo del cierre (CIERRE: la Etapa 5 lo agrega aquí);
#   3. ningún módulo de rutas del backend nombra esas funciones ni los
#      archivos, y la carpeta cycles/defecto solo la nombran los gestores de
#      programas que ya la usaban.

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "autoclave"
MODULO = "core/runtime/fabrica_equipo.py"
# Etapa 5: módulo(s) del cierre que pueden llamar a las funciones de escritura
CIERRE: set[str] = {"core/runtime/cierre_fabrica.py"}
ARCHIVOS = ("parametros_fabrica_equipo", "calibracion_fabrica_equipo")
ESCRITURAS = ("escribir_parametros_fabrica_equipo", "escribir_calibracion_fabrica_equipo",
              "consolidar_defectos_programas")
# cycles/defecto: lectura (cycle_manager) y defecto propio de un programa
# nuevo o su borrado (gestion_programas, O1 de la tanda 5 y E2); el cierre
# reescribe la carpeta entera solo con consolidar_defectos_programas
USAN_CARPETA_DEFECTO = {"core/managers/cycle_manager.py", "core/managers/gestion_programas.py",
                        MODULO}


def _modulos():
    for ruta in sorted(SRC.rglob("*.py")):
        rel = ruta.relative_to(SRC).as_posix()
        yield rel, ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))


def _cadenas(arbol):
    for n in ast.walk(arbol):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            yield n.value


def _nombres(arbol):
    for n in ast.walk(arbol):
        if isinstance(n, ast.Name):
            yield n.id
        elif isinstance(n, ast.Attribute):
            yield n.attr
        elif isinstance(n, ast.alias):
            yield n.name.split(".")[-1]
        elif isinstance(n, ast.FunctionDef):
            yield n.name


MODULOS = list(_modulos())


def test_el_modulo_existe_y_define_las_funciones():
    nombres = set(_nombres(dict(MODULOS)[MODULO]))
    assert set(ESCRITURAS) <= nombres


@pytest.mark.parametrize("archivo", ARCHIVOS)
def test_solo_fabrica_equipo_nombra_los_archivos(archivo):
    culpables = [rel for rel, arbol in MODULOS
                 if rel != MODULO and any(archivo in c for c in _cadenas(arbol))]
    assert culpables == [], f"{archivo} nombrado fuera de {MODULO}: {culpables}"


@pytest.mark.parametrize("funcion", ESCRITURAS)
def test_solo_el_cierre_llama_a_las_escrituras(funcion):
    culpables = [rel for rel, arbol in MODULOS
                 if rel != MODULO and rel not in CIERRE and funcion in set(_nombres(arbol))]
    assert culpables == [], f"{funcion} usado fuera del cierre: {culpables}"


def test_ninguna_ruta_escribe_la_base_de_fabrica():
    for rel, arbol in MODULOS:
        if not rel.startswith("backend/rutas/"):
            continue
        assert not (set(ESCRITURAS) & set(_nombres(arbol))), rel


def test_carpeta_de_defectos_solo_en_sus_gestores():
    culpables = [rel for rel, arbol in MODULOS
                 if rel not in USAN_CARPETA_DEFECTO
                 and any("cycles/defecto" in c for c in _cadenas(arbol))]
    assert culpables == [], culpables

"""Lista las claves de src/autoclave/i18n/es.json que el código no usa (D-19).

Solo lista: no borra ni modifica nada. Ninguna clave se elimina sin
autorización de Cristian (planeacion_i18n.md D-19).

Una clave cuenta como usada si:
  1. aparece completa como literal ("seccion.clave") en un .qml o en el Python
     dentro del alcance de D-02;
  2. empieza por el prefijo de una familia dinámica ("estados." + x,
     "instalacion.puerta_" + x, f"validacion.{codigo}") que aparece en ese
     código — criterio conservador: toda la familia cuenta como usada;
  3. la lee por su nombre corto un generador de PDF que recibe el catálogo
     entero (ui_qml/exportacion: textos.get("eje_tiempo"), "col_" + c, ...).

Uso:  python tools/claves_sin_uso_i18n.py [--md docs/mis_plans/claves_sin_uso_i18n.md]
"""

import argparse
import ast
import json
import re
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "autoclave"
ES_JSON = SRC / "i18n" / "es.json"

PY_ALCANCE = sorted(
    list((SRC / "ui_qml").rglob("*.py"))
    + [SRC / "ui_pyside" / "views" / "nuevo_usuario" / "puente.py",
       SRC / "ui_pyside" / "views" / "nuevo_usuario" / "vista.py",
       SRC / "auth" / "roles.py",
       SRC / "auth" / "validacion_usuario.py"])
QML_ARCHIVOS = sorted((SRC / "ui_qml" / "qml").rglob("*.qml"))
PDF = sorted((SRC / "ui_qml" / "exportacion").glob("*.py"))


def hojas(nodo, ruta=""):
    """Claves de texto ("seccion.clave"); las listas cuentan como una clave."""
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            yield from hojas(v, f"{ruta}.{k}" if ruta else k)
    else:
        yield ruta


def constantes_py(ruta: Path):
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            yield nodo.value
        elif isinstance(nodo, ast.JoinedStr) and nodo.values and isinstance(nodo.values[0], ast.Constant):
            yield nodo.values[0].value + "\0"     # f"prefijo{...}" -> prefijo dinámico


def analizar():
    es = json.loads(ES_JSON.read_text(encoding="utf-8"))
    secciones = "|".join(sorted(es))
    claves = list(hojas(es))
    literales, prefijos, motivos = set(), set(), {}

    patron_lit = re.compile(r'"((?:%s)(?:\.[A-Za-z0-9_]+)*\.?_?)"' % secciones)
    patron_pre = re.compile(r'"((?:%s)\.[A-Za-z0-9_.]*)"\s*\+' % secciones)
    for ruta in QML_ARCHIVOS:
        texto = ruta.read_text(encoding="utf-8")
        literales.update(patron_lit.findall(texto))
        prefijos.update(patron_pre.findall(texto))
    for ruta in PY_ALCANCE:
        texto = ruta.read_text(encoding="utf-8")
        prefijos.update(patron_pre.findall(texto))
        for c in constantes_py(ruta):
            if c.endswith("\0"):
                if re.match(r"(?:%s)\." % secciones, c):
                    prefijos.add(c[:-1])
            elif re.fullmatch(r"(?:%s)(?:\.[A-Za-z0-9_]+)+" % secciones, c):
                literales.add(c)

    cortas, prefijos_cortos = set(), set()
    for ruta in PDF:
        for c in constantes_py(ruta):
            if c.endswith("\0"):
                continue
            (prefijos_cortos if c.endswith("_") else cortas).add(c)

    sin_uso = []
    for clave in claves:
        hoja = clave.rsplit(".", 1)[-1]
        if clave in literales:
            continue
        if any(clave.startswith(p) for p in prefijos):
            continue
        if hoja in cortas or any(hoja.startswith(p) for p in prefijos_cortos):
            continue
        sin_uso.append(clave)
    return claves, sin_uso, sorted(prefijos)


def informe_md(claves, sin_uso, prefijos) -> str:
    lineas = [
        "# Claves de es.json sin uso (D-19)",
        "",
        f"Generado por `tools/claves_sin_uso_i18n.py` el {date.today():%d/%m/%Y}. "
        "**Solo lista: no se borra ninguna clave sin autorización de Cristian.**",
        "",
        f"- Claves de texto en `src/autoclave/i18n/es.json`: {len(claves)}",
        f"- Sin uso detectado: {len(sin_uso)}",
        "",
        "Criterio (conservador): una clave cuenta como usada si aparece completa en un .qml o en el "
        "Python de alcance D-02, si empieza por el prefijo de una familia dinámica que aparece en "
        "ese código, o si la lee por su nombre corto un generador de PDF de `ui_qml/exportacion`. "
        "Puede haber claves que el script da por usadas sin que lo estén (p. ej. toda una familia "
        "dinámica), pero no al revés salvo usos fuera de ese código (vistas PySide).",
        "",
        "## Claves sin uso",
        "",
        "| Clave | Texto en español |",
        "|---|---|",
    ]
    es = json.loads(ES_JSON.read_text(encoding="utf-8"))
    for clave in sin_uso:
        nodo = es
        for parte in clave.split("."):
            nodo = nodo[parte]
        texto = nodo if isinstance(nodo, str) else f"({type(nodo).__name__} de {len(nodo)} elementos)"
        lineas.append(f"| `{clave}` | {str(texto).replace('|', '/').replace(chr(10), ' ')} |")
    lineas += ["", "## Prefijos de familias dinámicas encontrados", ""]
    lineas += [f"- `{p}`" for p in prefijos]
    return "\n".join(lineas) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--md", help="escribe el informe en Markdown en esta ruta")
    args = parser.parse_args()
    claves, sin_uso, prefijos = analizar()
    for clave in sin_uso:
        print(clave)
    print(f"-- {len(sin_uso)} de {len(claves)} claves sin uso detectado")
    if args.md:
        Path(args.md).write_text(informe_md(claves, sin_uso, prefijos), encoding="utf-8")


if __name__ == "__main__":
    main()

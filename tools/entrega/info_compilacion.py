# tools/entrega/info_compilacion.py
"""VER-04 (etapa VER): identificación de la compilación.

`generar_build_info(raiz)` escribe `src/autoclave/_build_info.py` (en .gitignore)
con el commit corto, la etiqueta de entrega (o None), la fecha UTC y si el árbol
estaba sucio. Lo llaman los `.spec` del autoclave al empezar, así que toda
compilación lo lleva; `autoclave._version` decide con esos datos qué se muestra.

La etiqueta es la variable de entorno `AUTOCLAVE_ETIQUETA_ENTREGA` si existe
(la pone solo `compilar_entrega.py`: la etiqueta se crea después de compilar) o
la etiqueta `v1.0.0-...` que ya apunte al commit; si no hay, None (verificación).

Sin dependencias fuera de la biblioteca estándar: lo importa PyInstaller."""

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

VARIABLE_ETIQUETA = "AUTOCLAVE_ETIQUETA_ENTREGA"
ARCHIVO = Path("src") / "autoclave" / "_build_info.py"
# Lo que va dentro del ejecutable: un archivo sin versionar aquí lo cambia
CARPETAS_PRODUCTO = ("src/", "packaging/", "tools/instalador/", "Hardware/")
_ETIQUETA_ENTREGA = re.compile(r"^v\d+\.\d+\.\d+(-(alpha|beta|rc)\.\d+)?$")


def git(raiz, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(raiz), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def estado_arbol(porcelana: str) -> tuple[list[str], list[str], list[str]]:
    """Salida de `git status --porcelain` -> (versionados con cambios,
    sin versionar en carpetas del producto, sin versionar en otras carpetas)."""
    cambiados, sin_versionar_producto, sin_versionar_otros = [], [], []
    for linea in porcelana.splitlines():
        if not linea.strip():
            continue
        codigo, ruta = linea[:2], linea[3:].strip().strip('"')
        if codigo == "??":
            destino = (sin_versionar_producto if ruta.startswith(CARPETAS_PRODUCTO)
                       else sin_versionar_otros)
            destino.append(ruta)
        else:
            cambiados.append(ruta)
    return cambiados, sin_versionar_producto, sin_versionar_otros


def etiqueta_del_commit(raiz) -> str | None:
    etiquetas = [e.strip() for e in git(raiz, "tag", "--points-at", "HEAD").splitlines()]
    entregas = sorted(e for e in etiquetas if _ETIQUETA_ENTREGA.match(e))
    return entregas[-1] if entregas else None


def datos_compilacion(raiz, entorno=os.environ, ahora=None) -> dict:
    raiz = Path(raiz)
    commit = git(raiz, "rev-parse", "--short=7", "HEAD").strip()
    cambiados, sin_versionar, _ = estado_arbol(
        git(raiz, "status", "--porcelain", "--untracked-files=all"))
    etiqueta = entorno.get(VARIABLE_ETIQUETA) or etiqueta_del_commit(raiz)
    fecha = (ahora or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"commit": commit, "etiqueta": etiqueta, "fecha_utc": fecha,
            "sucio": bool(cambiados or sin_versionar)}


def texto_build_info(d: dict) -> str:
    return ("# src/autoclave/_build_info.py — GENERADO al compilar por\n"
            "# tools/entrega/info_compilacion.py (VER-04). No versionar ni editar.\n"
            f"COMMIT = {d['commit']!r}\n"
            f"ETIQUETA = {d['etiqueta']!r}\n"
            f"FECHA_UTC = {d['fecha_utc']!r}\n"
            f"SUCIO = {bool(d['sucio'])!r}\n")


def generar_build_info(raiz, entorno=os.environ, ahora=None) -> dict:
    d = datos_compilacion(raiz, entorno, ahora)
    (Path(raiz) / ARCHIVO).write_text(texto_build_info(d), encoding="utf-8")
    print(f"VER-04: _build_info.py -> commit {d['commit']}, etiqueta {d['etiqueta']}, "
          f"sucio {d['sucio']}")
    return d

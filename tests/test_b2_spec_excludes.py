"""B2 (tanda 4): `Autoclave.spec` no puede excluir módulos que el programa
importa (directa o transitivamente). Con `scipy` excluido, qfluentwidgets no
cargaba y el menú de ajustes (engrane) no abría en el ejecutable."""

import ast
import os
import pathlib
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SPEC = RAIZ / "Autoclave.spec"

# Módulos que el ejecutable necesita en tiempo de ejecución (medidos importando
# autoclave.ui_pyside.main_window, backend.server, ui_qml.app y exe_unico).
IMPRESCINDIBLES = (
    "scipy", "numpy", "PIL", "colorthief", "darkdetect", "qframelesswindow",
    "qfluentwidgets", "win32api", "win32con", "win32gui", "win32print", "serial",
    "uvicorn", "fastapi", "starlette", "pydantic", "pydantic_core", "yaml", "ruamel",
    "requests", "sqlite3", "defusedxml", "unittest", "escpos",
    "PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    "PySide6.QtSvg", "PySide6.QtSvgWidgets", "PySide6.QtXml", "PySide6.QtQml",
    "PySide6.QtQuick", "PySide6.QtQuickControls2", "PySide6.QtNetwork",
    "autoclave", "autoclave.backend", "autoclave.ui_qml", "autoclave.ui_pyside",
)


def _excludes_del_spec() -> list[str]:
    arbol = ast.parse(SPEC.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.keyword) and nodo.arg == "excludes":
            return [e.value for e in nodo.value.elts]
    raise AssertionError("el .spec no define excludes")


def test_el_spec_no_excluye_modulos_imprescindibles():
    excluidos = _excludes_del_spec()
    assert excluidos, "excludes vacío: ¿cambió el formato del .spec?"
    # excluir un paquete entero o un submódulo suyo es un error; PySide6 y
    # autoclave se miden módulo a módulo (p. ej. QtWebEngine* y simulador sí)
    paquetes = [i for i in IMPRESCINDIBLES if i not in ("PySide6", "autoclave")]
    malos = [e for e in excluidos
             if e in IMPRESCINDIBLES or any(e.startswith(i + ".") for i in paquetes)]
    assert not malos, f"el .spec excluye módulos imprescindibles: {malos}"


def test_scipy_no_esta_excluido_porque_qfluentwidgets_lo_importa():
    assert "scipy" not in _excludes_del_spec()


def test_lo_excluido_no_se_importa_al_cargar_la_aplicacion():
    """Importa las 5 entradas del ejecutable en un intérprete limpio y verifica
    que ninguno de los módulos excluidos (salvo autoclave.simulador, que solo
    corre por `python -m`) quedó cargado."""
    excluidos = [e for e in _excludes_del_spec() if e != "autoclave.simulador"]
    codigo = (
        "import sys; sys.path.insert(0, 'src');"
        "import autoclave.backend.server, autoclave.backend.main,"
        " autoclave.ui_pyside.main_window, autoclave.ui_pyside.app,"
        " autoclave.ui_qml.app, autoclave.exe_unico;"
        f"ex = {excluidos!r};"
        "print([m for m in ex if any(k == m or k.startswith(m + '.') for k in sys.modules)])"
    )
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    r = subprocess.run([sys.executable, "-I", "-c", codigo], cwd=RAIZ, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
    assert r.stdout.strip().splitlines()[-1] == "[]", r.stdout[-400:]


def test_main_window_se_importa_en_entorno_offscreen():
    """El menú de ajustes (engrane) abre solo si esta cadena de imports carga."""
    codigo = ("import sys; sys.path.insert(0, 'src');"
              "from autoclave.ui_pyside import main_window; print('ok')")
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    r = subprocess.run([sys.executable, "-I", "-c", codigo], cwd=RAIZ, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
    assert r.stdout.strip().endswith("ok")

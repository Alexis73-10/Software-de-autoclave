"""Tanda 15 (ORG-11): las capas que no son de interfaz no importan la interfaz.

Lee el código con ``ast`` (no importa ningún módulo):

- ningún archivo de ``backend/``, ``auth/``, ``cliente/``, ``simulador/``,
  ``core/``, ``services/``, ``state_machine/``, ``protocols/``, ``devices/`` ni
  ``hal/`` importa ``autoclave.ui``, ``autoclave.ui_pyside`` ni
  ``autoclave.ui_qml``;
- ``auth/`` no importa PySide6.

Cuenta también los imports diferidos (dentro de funciones) y los relativos.

Excepción conocida (DECISIÓN SIN CONFIRMAR, tanda 15): el backend importa de
forma diferida ``autoclave.ui_qml.exportacion.config_correo`` y ``.correo``
(configuración y envío de correo, sin PySide6). Moverlos queda fuera del
alcance de la tanda 15 (D2); la excepción se limita a esos dos módulos y a la
capa ``backend``, así que cualquier otra dependencia nueva hace fallar el test.
"""
import ast
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src" / "autoclave"

_CAPAS = ("backend", "auth", "cliente", "simulador", "core", "services",
          "state_machine", "protocols", "devices", "hal")
_UI = ("autoclave.ui", "autoclave.ui_pyside", "autoclave.ui_qml")

_EXCEPCIONES = {
    "backend": frozenset({
        "autoclave.ui_qml.exportacion",
        "autoclave.ui_qml.exportacion.config_correo",
        "autoclave.ui_qml.exportacion.config_correo.config_correo",
        "autoclave.ui_qml.exportacion.config_correo.correo_valido",
        "autoclave.ui_qml.exportacion.correo",
    }),
}


def _paquete(archivo: Path) -> list[str]:
    partes = ["autoclave", *archivo.relative_to(_SRC).with_suffix("").parts]
    return partes if archivo.name == "__init__.py" else partes[:-1]


def _modulos_importados(archivo: Path, paquete: list[str] | None = None) -> list[tuple[int, str]]:
    """Módulos importados, con los imports relativos resueltos (V15-U-01)."""
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    mods = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            mods.extend((nodo.lineno, a.name) for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                base = paquete if paquete is not None else _paquete(archivo)
                base = base[:len(base) - (nodo.level - 1)]
                modulo = ".".join(base + ([nodo.module] if nodo.module else []))
            else:
                modulo = nodo.module
            if not modulo:
                continue
            mods.append((nodo.lineno, modulo))
            mods.extend((nodo.lineno, f"{modulo}.{a.name}") for a in nodo.names)
    return mods


def _es_de(modulo: str, paquete: str) -> bool:
    return modulo == paquete or modulo.startswith(paquete + ".")


def _archivos(capa: str) -> list[Path]:
    return sorted((_SRC / capa).rglob("*.py"))


@pytest.mark.parametrize("capa", _CAPAS)
def test_capa_no_importa_la_ui(capa):
    violaciones = []
    for archivo in _archivos(capa):
        for linea, mod in _modulos_importados(archivo):
            if mod in _EXCEPCIONES.get(capa, ()):
                continue
            if any(_es_de(mod, ui) for ui in _UI):
                violaciones.append(f"{archivo.relative_to(_SRC)}:{linea} importa {mod}")
    assert not violaciones, "\n".join(sorted(set(violaciones)))


def test_auth_existe_y_no_importa_pyside6():
    archivos = _archivos("auth")
    assert archivos, "falta el paquete autoclave.auth"
    violaciones = [f"{a.relative_to(_SRC)}:{linea} importa {mod}"
                   for a in archivos for linea, mod in _modulos_importados(a)
                   if _es_de(mod, "PySide6")]
    assert not violaciones, "\n".join(violaciones)


def test_resuelve_imports_relativos(tmp_path):
    """El detector ve también los imports relativos (V15-U-01)."""
    archivo = _SRC / "backend" / "rutas" / "io.py"
    assert any(m == "autoclave.backend.dependencias" for _, m in _modulos_importados(archivo))
    falso = tmp_path / "falso.py"
    falso.write_text("from ...ui_qml import app\nfrom . import _comun\n", encoding="utf-8")
    mods = [m for _, m in _modulos_importados(falso, ["autoclave", "backend", "rutas"])]
    assert "autoclave.ui_qml.app" in mods and "autoclave.backend.rutas._comun" in mods

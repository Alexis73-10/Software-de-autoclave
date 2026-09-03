# tests/test_icon_qml.py
#
# Verifica el componente Icon (§7.3 del plan de interfaz dual-pantalla):
# aplica el tinte de color en tiempo de ejecución sobre un SVG monocromo,
# ya que el renderizador SVG de Qt (SVG Tiny 1.2) no resuelve currentColor
# ni variables CSS (hallazgo UI-06) — el SVG de origen trae un color
# cualquiera fijo y el componente lo recolorea vía MultiEffect.colorization.

import sys
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

_ICON_QML = "src/autoclave/ui_qml/components/Icon.qml"

# SVG mínimo que respeta el contrato de entrega del §7.3: viewBox 0 0 24 24,
# sin width/height, sin <style>, color fijo (no currentColor, no resuelto
# por el renderizador de Qt).
_SVG_SINTETICO = (
    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M4 4h16v16H4z" stroke="#000000" stroke-width="2" fill="none"/>'
    "</svg>"
)


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def icons_dir(tmp_path):
    d = tmp_path / "icons"
    d.mkdir()
    (d / "icon-purga-24.svg").write_text(_SVG_SINTETICO, encoding="utf-8")
    return d


def _crear_icono(icons_dir, **props):
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(_ICON_QML))
    obj = component.create()
    assert obj is not None, [e.toString() for e in component.errors()]
    obj.setProperty("iconsDir", QUrl.fromLocalFile(str(icons_dir) + "/").toString())
    for nombre, valor in props.items():
        obj.setProperty(nombre, valor)
    # Mantiene vivos engine/component: ver test_tokens_qml_runtime.py.
    obj._keepalive = (engine, component)
    return obj


def test_icon_instancia_sin_error(icons_dir):
    obj = _crear_icono(icons_dir, name="purga")
    assert obj is not None


def test_icon_tamano_por_defecto_es_24(icons_dir):
    obj = _crear_icono(icons_dir, name="purga")
    assert obj.property("width") == 24
    assert obj.property("height") == 24


def test_icon_respeta_tamano_explicito(icons_dir):
    obj = _crear_icono(icons_dir, name="purga", size=48)
    assert obj.property("width") == 48
    assert obj.property("height") == 48


def test_icon_resuelve_fuente_desde_name(icons_dir):
    obj = _crear_icono(icons_dir, name="purga")
    fuente = obj.property("source").toString()
    assert "icon-purga-24.svg" in fuente


def test_icon_color_por_defecto_es_negro(icons_dir):
    obj = _crear_icono(icons_dir, name="purga")
    from PySide6.QtGui import QColor
    assert obj.property("color") == QColor("black")


def test_icon_acepta_color_explicito(icons_dir):
    from PySide6.QtGui import QColor
    obj = _crear_icono(icons_dir, name="purga", color=QColor("#FF0000"))
    assert obj.property("color") == QColor("#FF0000")

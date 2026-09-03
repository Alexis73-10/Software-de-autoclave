# tests/test_tokens_qml_runtime.py
#
# Verifica que Tokens.qml (generado por generate_tokens.py) sea QML válido
# y que el toggle claro/oscuro (D-21) funcione en un motor QML real, no
# solo que el texto generado tenga la forma esperada (ver
# test_generate_tokens_qml.py para eso).

import json
import sys
import pytest

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

from autoclave.ui_qml.design.generate_tokens import generar_tokens_qml, _TOKENS_JSON


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def tokens_object(tmp_path):
    tokens = json.loads(_TOKENS_JSON.read_text(encoding="utf-8"))
    qml_path = tmp_path / "Tokens.qml"
    qml_path.write_text(generar_tokens_qml(tokens), encoding="utf-8")

    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_path)))
    obj = component.create()
    assert obj is not None, [e.toString() for e in component.errors()]
    # Mantiene vivos engine/component: sin esta referencia, Python los
    # recolecta al salir del fixture y el objeto QML creado queda con su
    # C++ subyacente destruido (RuntimeError al acceder a properties).
    obj._engine_keepalive = (engine, component)
    return obj


def test_tokens_qml_es_valido_e_instancia(tokens_object):
    assert tokens_object.property("dark") is False


def test_dark_false_usa_valores_claros(tokens_object):
    color = tokens_object.property("color").toVariant()
    assert color["surface"]["card"] == "#FFFFFF"
    assert color["primary"]["500"] == "#1168F6"


def test_dark_true_usa_valores_oscuros(tokens_object):
    tokens_object.setProperty("dark", True)
    color = tokens_object.property("color").toVariant()
    assert color["surface"]["card"] == "#16202B"
    assert color["primary"]["500"] == "#4C8FFB"


def test_valores_no_sobrescritos_en_dark_no_cambian(tokens_object):
    tokens_object.setProperty("dark", True)
    color = tokens_object.property("color").toVariant()
    assert color["module"]["cycle"] == "#009933"


def test_grupos_sin_tema_expuestos_correctamente(tokens_object):
    space = tokens_object.property("space").toVariant()
    assert space["4"] == 16

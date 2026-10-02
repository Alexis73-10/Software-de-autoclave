# tests/test_url_backend_ui_qml.py
#
# La UI QML se puede apuntar a otro backend (p. ej. el simulador,
# python -m autoclave.simulador) con AUTOCLAVE_BACKEND_URL; sin la variable
# sigue en localhost:8000.

from autoclave.ui_qml import app


def test_sin_variable_usa_el_backend_local():
    assert app.url_backend({}) == "http://localhost:8000"


def test_variable_apunta_a_otro_backend():
    assert app.url_backend({"AUTOCLAVE_BACKEND_URL": "http://localhost:8001"}) == "http://localhost:8001"


def test_variable_vacia_se_ignora():
    assert app.url_backend({"AUTOCLAVE_BACKEND_URL": "  "}) == "http://localhost:8000"

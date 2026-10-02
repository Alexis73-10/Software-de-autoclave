# tests/test_url_backend_ui_qml.py
#
# URL del backend en las interfaces. Se usa 127.0.0.1 y no "localhost": en
# Windows, "localhost" se prueba primero como IPv6 (::1), donde el backend no
# escucha (solo IPv4, host 0.0.0.0); Windows reintenta la conexión rechazada y
# cada petición tardaba 0.8–2 s (medido el 2026-10-01). La UI QML además se
# puede apuntar a otro backend (p. ej. el simulador) con AUTOCLAVE_BACKEND_URL.

from pathlib import Path

from autoclave.ui_qml import app

SRC = Path(__file__).resolve().parents[1] / "src" / "autoclave"


def test_sin_variable_usa_el_backend_local_por_ipv4():
    assert app.url_backend({}) == "http://127.0.0.1:8000"


def test_variable_apunta_a_otro_backend():
    assert app.url_backend({"AUTOCLAVE_BACKEND_URL": "http://127.0.0.1:8001"}) == "http://127.0.0.1:8001"


def test_variable_vacia_se_ignora():
    assert app.url_backend({"AUTOCLAVE_BACKEND_URL": "  "}) == "http://127.0.0.1:8000"


def test_ningun_cliente_del_backend_usa_localhost():
    usos = [f"{p.relative_to(SRC)}:{n}"
            for p in SRC.rglob("*.py")
            for n, linea in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if "localhost:8000" in linea]
    assert usos == []

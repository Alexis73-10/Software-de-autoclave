"""B1 (tanda 4): la vista PySide de secado guarda por PATCH /cycle/parameter
(un parámetro por petición, con token), y muestra el motivo de un rechazo del
backend sin confundirlo con un fallo de conexión ni con un éxito."""

import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

from autoclave.cliente.session_manager import SessionManager


@pytest.fixture(autouse=True)
def sesion():
    SessionManager.login({"nombre": "T", "usuario": "t", "rol": "tecnico"}, "TOK")
    yield
    SessionManager.logout()


def _resp(estado, datos=None):
    r = MagicMock()
    r.status_code = estado
    r.json.return_value = datos if datos is not None else {}
    r.raise_for_status.side_effect = (
        requests.HTTPError(response=r) if estado >= 400 else None)
    return r


_SECADO = {"modo": {"value": 1}, "tiempo_secado": {"value": 2.0},
           "presion_chaqueta_secado": {"value": 200},
           "presion_baja_secado": {"value": 20}, "presion_alta_secado": {"value": 80}}


def _vista():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication(sys.argv)
    from autoclave.ui_pyside.views.secado import SecadoView
    v = SecadoView(lambda _: None)
    with patch("requests.get", return_value=_resp(
            200, {"id": "instrumental_134", "parameters": {"secado": _SECADO}})):
        v._load_current()
    avisos = []
    v._aviso = lambda nivel, titulo, contenido, ms=0: avisos.append((nivel, titulo, contenido))
    return v, avisos


def test_la_vista_ya_no_usa_la_ruta_inexistente():
    import pathlib
    import autoclave.ui_pyside.views.secado as m
    assert "/cycle/parameters" not in pathlib.Path(m.__file__).read_text(encoding="utf-8")


def test_guarda_solo_lo_que_cambio_con_token():
    v, avisos = _vista()
    v._spin_tiempo.setValue(3.5)
    with patch("requests.patch", return_value=_resp(200, {"ok": True})) as p:
        v._save()
    assert p.call_count == 1
    llamada = p.call_args
    assert llamada.args[0].endswith("/cycle/parameter")
    assert llamada.kwargs["json"] == {"cycle_id": "instrumental_134", "fase": "secado",
                                      "path": ["tiempo_secado"], "value": 3.5}
    assert llamada.kwargs["headers"] == {"Authorization": "Bearer TOK"}
    assert avisos[-1][0] == "success"


def test_sin_cambios_no_llama_al_backend():
    v, avisos = _vista()
    with patch("requests.patch") as p:
        v._save()
    p.assert_not_called()
    assert avisos[-1][0] == "info"


def test_fuera_de_rango_muestra_el_motivo_y_no_exito():
    v, avisos = _vista()
    v._spin_tiempo.setValue(50.0)
    rechazo = _resp(422, {"detail": "tiempo_secado fuera de rango", "codigo": "VALOR_INVALIDO"})
    with patch("requests.patch", return_value=rechazo):
        v._save()
    assert avisos[-1][0] == "error" and "fuera de rango" in avisos[-1][2]
    assert all(a[0] != "success" for a in avisos)


def test_conflicto_409_muestra_el_motivo():
    v, avisos = _vista()
    v._spin_modo.setValue(2)
    with patch("requests.patch", return_value=_resp(409, {"detail": "Estado no permite editar"})):
        v._save()
    assert avisos[-1][0] == "error" and "Estado no permite editar" in avisos[-1][2]


def test_401_pide_login_y_cancelado_no_guarda():
    """P3 (tanda 5): sesión vencida -> diálogo de login; cancelado, no se guarda."""
    v, avisos = _vista()
    v._spin_chaqueta.setValue(150)
    with patch("requests.patch", return_value=_resp(401, {"detail": "x"})):
        v._save()
    assert avisos[-1][0] == "warning" and "no se guardó" in avisos[-1][2].lower()


@pytest.mark.parametrize("estado", [403])
def test_sin_permiso_lo_dice_y_no_es_fallo_de_conexion(estado):
    v, avisos = _vista()
    v._spin_chaqueta.setValue(150)
    with patch("requests.patch", return_value=_resp(estado, {"detail": "x"})):
        v._save()
    assert avisos[-1][0] == "error" and "permiso" in avisos[-1][2].lower()


def test_backend_caido_es_sin_conexion():
    v, avisos = _vista()
    v._spin_tiempo.setValue(4.0)
    with patch("requests.patch", side_effect=requests.ConnectionError()):
        v._save()
    assert avisos[-1][0] == "warning" and avisos[-1][1] == "Sin conexión"


def test_sin_programa_cargado_no_guarda():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication(sys.argv)
    from autoclave.ui_pyside.views.secado import SecadoView
    v = SecadoView(lambda _: None)
    avisos = []
    v._aviso = lambda nivel, titulo, contenido, ms=0: avisos.append((nivel, titulo))
    with patch("requests.patch") as p:
        v._save()
    p.assert_not_called()
    assert avisos[-1][0] == "warning"


def test_barrido_toda_ruta_http_de_ui_pyside_existe_en_el_backend():
    """B1: cada ruta literal que la UI PySide (y el cliente compartido) llama
    existe en el backend con ese método."""
    import pathlib
    import re
    from autoclave.backend.server import app
    raiz = pathlib.Path(__file__).resolve().parents[1] / "src" / "autoclave"
    rutas = [(re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", r.path) + "$"), m)
             for r in app.routes if hasattr(r, "methods") for m in r.methods]
    patron = re.compile(r"\.(get|post|patch|put|delete)\(\s*f?[\"'](/[^\"']*)[\"']")
    faltan = []
    for carpeta in (raiz / "ui_pyside", raiz / "cliente"):
        for py in carpeta.rglob("*.py"):
            for metodo, ruta in patron.findall(py.read_text(encoding="utf-8")):
                ruta = re.sub(r"\{[^}]+\}", "x", ruta)
                if not any(rx.match(ruta) and m == metodo.upper() for rx, m in rutas):
                    faltan.append(f"{py.name}: {metodo.upper()} {ruta}")
    assert not faltan, faltan

"""B7 (tanda 4): los tokens de sesión caducan por inactividad también en el
backend, con el mismo plazo que la UI (SESION_INACTIVIDAD_S), renovados por cada
petición autenticada. La caducidad no toca el control del ciclo."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.backend.autenticacion import AlmacenTokens
from autoclave.core.runtime.sesion_inactividad import (
    PLAZO_TOKEN_BACKEND_S, SESION_INACTIVIDAD_S, SESION_KEEPALIVE_S)
from tests.backend_doble import cargar_servidor


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _almacen():
    reloj = Reloj()
    return AlmacenTokens(reloj=reloj), reloj


def test_el_plazo_del_backend_es_el_de_la_ui_mas_dos_avisos():
    """SAF-02/TMG-04: la UI cierra primero (con su logout y su mensaje)."""
    import autoclave.ui_qml.sesion_backend as ui
    assert ui.SESION_INACTIVIDAD_S == SESION_INACTIVIDAD_S == 300
    assert ui.KEEPALIVE_S == SESION_KEEPALIVE_S == 30
    assert AlmacenTokens()._inactividad_s == PLAZO_TOKEN_BACKEND_S == 360


def test_un_aviso_29_s_antes_del_ultimo_toque_no_deja_caducar_el_token_antes_que_la_ui():
    a, reloj = _almacen()
    s = a.emitir("tec", "Tec", "tecnico", False)
    # aviso en t=0, último toque en t=29 (sin aviso); la UI cierra en t=329
    reloj.t += 328
    assert a.obtener(s.token, renovar=False) is s


def test_token_vigente_y_caducado_por_inactividad():
    a, reloj = _almacen()
    s = a.emitir("tec", "Tec", "tecnico", False)
    reloj.t += PLAZO_TOKEN_BACKEND_S - 1
    assert a.obtener(s.token) is s
    reloj.t += PLAZO_TOKEN_BACKEND_S
    assert a.obtener(s.token) is None
    assert a.obtener(s.token) is None                 # ya borrado


def test_cada_peticion_renueva_el_plazo():
    a, reloj = _almacen()
    s = a.emitir("tec", "Tec", "tecnico", False)
    for _ in range(10):                               # 10 x 5 min = 50 min con uso constante
        reloj.t += 300
        assert a.obtener(s.token) is s


def test_exactamente_en_el_plazo_caduca():
    a, reloj = _almacen()
    s = a.emitir("tec", "Tec", "tecnico", False)
    reloj.t += PLAZO_TOKEN_BACKEND_S
    assert a.obtener(s.token) is None


def test_la_consulta_interna_no_renueva():
    a, reloj = _almacen()
    s = a.emitir("tec", "Tec", "tecnico", False)
    reloj.t += 200
    assert a.obtener(s.token, renovar=False) is s and a.existe(s.token)
    reloj.t += 170                                    # 370 s desde la emisión
    assert a.obtener(s.token) is None


def test_se_purgan_las_caducadas_al_emitir_y_no_afectan_a_las_vigentes():
    a, reloj = _almacen()
    vieja = a.emitir("a", "A", "tecnico", False)
    reloj.t += 200
    viva = a.emitir("b", "B", "ingeniero", False)
    reloj.t += 170                                    # vieja: 370 s; viva: 170 s
    nueva = a.emitir("c", "C", "tecnico", False)
    assert vieja.token not in a._sesiones
    assert a.obtener(viva.token) is viva and a.obtener(nueva.token) is nueva


def test_invalidar_un_token_caducado_es_inocuo():
    a, reloj = _almacen()
    s = a.emitir("tec", "Tec", "tecnico", False)
    reloj.t += 1000
    a.obtener(s.token)
    assert a.invalidar(s.token) is None


def test_el_reloj_por_defecto_es_monotonico():
    import time
    assert AlmacenTokens()._reloj is time.monotonic


# ── endpoints ───────────────────────────────────────────────────────────────

@pytest.fixture
def api():
    ctx = MagicMock()
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    reloj = Reloj()
    srv.tokens = AlmacenTokens(reloj=reloj)
    return TestClient(srv.app), srv, ctx, reloj


def _h(srv, rol="tecnico"):
    s = srv.tokens.emitir(f"u_{rol}", rol, rol, False)
    return {"Authorization": f"Bearer {s.token}"}, s


def test_un_token_vencido_recibe_401_en_una_ruta_con_sesion(api):
    client, srv, ctx, reloj = api
    h, _ = _h(srv)
    assert client.get("/auth/sesion", headers=h).status_code == 200
    reloj.t += PLAZO_TOKEN_BACKEND_S + 1
    r = client.get("/auth/sesion", headers=h)
    assert r.status_code == 401 and r.json()["codigo"] == "sesion_invalida"


def test_las_peticiones_autenticadas_mantienen_viva_la_sesion(api):
    client, srv, ctx, reloj = api
    h, _ = _h(srv)
    for _ in range(5):
        reloj.t += 200
        assert client.get("/auth/sesion", headers=h).status_code == 200


def test_el_401_por_caducidad_queda_como_rechazo_de_sesion_en_el_log(api, caplog):
    # D9-6 (tanda 9): el rechazo ya no va a la bitácora, solo al log de desarrollo
    import logging
    client, srv, ctx, reloj = api
    h, _ = _h(srv)
    reloj.t += PLAZO_TOKEN_BACKEND_S + 1
    with caplog.at_level(logging.INFO):
        assert client.get("/auth/sesion", headers=h).status_code == 401
    assert not ctx.db.registrar_auditoria.called
    assert "rechazo_401" in caplog.text


def test_la_caducidad_no_toca_el_control_del_ciclo_ni_las_rutas_sin_sesion(api):
    client, srv, ctx, reloj = api
    h, _ = _h(srv)
    ctx.control_loop.reset_mock()
    reloj.t += 10 * PLAZO_TOKEN_BACKEND_S
    # rutas sin sesión siguen respondiendo (el operador de la puerta, el apagado...)
    assert client.get("/db/estado").status_code == 200
    # ninguna llamada al ControlLoop por haber vencido el token
    assert ctx.control_loop.mock_calls == []
    # la ruta de apagado no mira el token: un token vencido no la impide (A1)
    r = client.post("/system/shutdown", headers=h, json={"ventana": "otra"})
    assert r.status_code == 403 and r.json()["codigo"] == "solo_ventana_principal"


def test_login_nuevo_tras_caducar_funciona(api):
    client, srv, ctx, reloj = api
    h, s = _h(srv)
    reloj.t += PLAZO_TOKEN_BACKEND_S + 1
    assert client.get("/auth/sesion", headers=h).status_code == 401
    h2, _ = _h(srv)
    assert client.get("/auth/sesion", headers=h2).status_code == 200


def test_el_modo_prueba_se_entera_de_que_el_dueno_ya_no_tiene_sesion(api):
    client, srv, ctx, reloj = api
    _, s = _h(srv, "tecnico")
    reloj.t += PLAZO_TOKEN_BACKEND_S + 1
    assert srv.tokens.existe(s.token) is False


# ── UI: la ventana mantiene viva la sesión del backend mientras se usa ──────

def _ui(respuestas=None):
    import sys
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui.service_ui.session_manager import SessionManager
    from autoclave.ui_qml import sesion_backend as sb
    llamadas = []

    def transporte(metodo, ruta, cuerpo, token, plazo):
        llamadas.append((metodo, ruta, token))
        return (respuestas or {}).get((metodo, ruta), (200, {"usuario": "t", "rol": "tecnico"}))

    r = Reloj()
    s = sb.SesionVentana(transporte=transporte, ejecutar=lambda t: t(), reloj=r)
    SessionManager.login({"nombre": "T", "usuario": "t", "rol": "tecnico"}, "TOK")
    return s, r, llamadas, SessionManager


def test_la_ventana_en_uso_avisa_al_backend_cada_30_s_como_maximo():
    s, reloj, llamadas, sm = _ui()
    try:
        s.registrarActividad()
        s.registrarActividad()
        assert [(m, r) for m, r, _ in llamadas] == [("GET", "/auth/sesion")]
        reloj.t += 29
        s.registrarActividad()
        assert len(llamadas) == 1
        reloj.t += 2
        s.registrarActividad()
        assert len(llamadas) == 2 and llamadas[-1][2] == "TOK"
    finally:
        sm.logout()


def test_sin_sesion_o_fuera_de_una_pantalla_con_token_no_hay_avisos():
    s, reloj, llamadas, sm = _ui()
    try:
        s.vigilar(True, False)                           # sin pantalla con token a la vista
        s.registrarActividad()
        assert llamadas == []
        sm.logout()
        s.vigilar(True, True)
        s.registrarActividad()
        assert llamadas == []
    finally:
        sm.logout()


def test_un_401_del_aviso_cierra_la_sesion_de_la_ventana():
    s, reloj, llamadas, sm = _ui({("GET", "/auth/sesion"): (401, {"codigo": "sesion_invalida"})})
    try:
        s.registrarActividad()
        assert sm.is_authenticated() is False
    finally:
        sm.logout()

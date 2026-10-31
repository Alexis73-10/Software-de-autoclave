# tests/test_c2_correo_bitacora_api.py
#
# C2 (tanda 7): POST /email/sent deja en audit_log cada envío de correo del
# Historial/Reportes (direcciones y resultado por destinatario, sin la
# contraseña). El Menú Principal envía sin sesión: el registro se acepta sin
# token (el backend solo escucha en 127.0.0.1) y, si hay sesión, la anota.
# Además, el correo de prueba no cuenta como enviado un rechazo total.

from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime.config_correo_equipo import ConfigCorreoEquipo
from tests.helpers.backend_doble import modulo_backend


@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.sin_base_de_datos = False
    ctx.config_correo_equipo = ConfigCorreoEquipo(tmp_path / "ce.json", semilla=lambda: [])
    srv, _ = cargar_servidor(ctx)
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    yield TestClient(srv.app), srv, ctx, cabecera
    ctx.db.close()


_CUERPO = {"tipo": "ciclos", "destinatarios": ["juan@gmail.com", "malo@x.com"],
           "manuales": ["juan@gmail.com"], "ciclos": [12],
           "aceptados": ["juan@gmail.com"], "rechazados": {"malo@x.com": 550},
           "resultado": "parcial"}


def test_registra_el_envio_sin_sesion(api):
    client, srv, ctx, cab = api
    r = client.post("/email/sent", json=_CUERPO)
    assert r.status_code == 200 and r.json() == {"ok": True}
    fila = ctx.db.get_auditoria(evento="correo_enviado")[0]
    assert fila["usuario"] == "" and fila["entidad"] == "/email/sent"
    d = fila["detalle"]
    assert d["destinatarios"] == ["juan@gmail.com", "malo@x.com"]
    assert d["manuales"] == ["juan@gmail.com"] and d["resultado"] == "parcial"
    assert d["aceptados"] == ["juan@gmail.com"] and d["rechazados"] == {"malo@x.com": 550}
    assert d["tipo"] == "ciclos" and d["ciclos"] == [12]
    # lo que muestra la pantalla de Bitácora ({nuevo}): resultado y direcciones
    from autoclave.core.runtime import bitacora
    nuevo = bitacora.presentar(fila, {}, {})["nuevo"]
    assert "parcial" in nuevo and "juan@gmail.com" in nuevo and "malo@x.com" in nuevo


def test_con_sesion_anota_el_usuario(api):
    client, srv, ctx, cab = api
    r = client.post("/email/sent", json=_CUERPO, headers=cab(srv, "operador", "ana"))
    assert r.status_code == 200
    fila = ctx.db.get_auditoria(evento="correo_enviado")[0]
    assert fila["usuario"] == "ana" and fila["rol"] == "operador"


@pytest.mark.parametrize("cambio", [
    {"resultado": "inventado"},
    {"tipo": "otro"},
    {"contrasena": "SECRETA-123"},                       # campos extra: rechazados
    {"destinatarios": [f"u{i}@x.com" for i in range(30)]},
    {"destinatarios": ["x" * 400]},
])
def test_cuerpo_invalido_no_registra(api, cambio):
    client, srv, ctx, cab = api
    r = client.post("/email/sent", json={**_CUERPO, **cambio})
    assert r.status_code == 422
    assert ctx.db.get_auditoria(evento="correo_enviado") == []
    assert "SECRETA" not in r.text


def test_evento_con_texto_en_la_bitacora():
    from autoclave import i18n
    from autoclave.core.runtime import bitacora
    assert "correo_enviado" in bitacora.EVENTOS
    for idioma in ("es", "en"):
        assert i18n.t("bitacora.ev.correo_enviado", idioma) != "bitacora.ev.correo_enviado"


def test_correo_de_prueba_no_cuenta_un_rechazo_total(api, monkeypatch):
    """_enviar_correo del backend: si el relay no aceptó a nadie, es un fallo."""
    client, srv, ctx, cab = api
    from autoclave.ui_qml.exportacion import correo
    monkeypatch.setattr(correo, "enviar", lambda config, m: correo.ResultadoEnvio(
        (), {"a@x.co": 550}))
    with pytest.raises(Exception):
        modulo_backend("rutas.reportes")._enviar_correo(MagicMock(), MagicMock())
    monkeypatch.setattr(correo, "enviar", lambda config, m: correo.ResultadoEnvio(("a@x.co",), {}))
    modulo_backend("rutas.reportes")._enviar_correo(MagicMock(), MagicMock())

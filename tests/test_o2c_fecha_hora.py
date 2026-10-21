# tests/test_o2c_fecha_hora.py
#
# O2c (tanda 6; decisión 1.10): Fecha y hora SOLO LECTURA. GET /system/time
# con hora, zona, instalación y aviso M1-01; sin endpoint de ajuste; visible
# para todos los roles con sesión; pantalla sin campos de edición.

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def srv_ctx():
    from tests.backend_doble import cargar_servidor
    ctx = MagicMock()
    srv, _ = cargar_servidor(ctx)
    return srv, ctx


def test_info_reloj_y_aviso_m1_01(srv_ctx):
    srv, ctx = srv_ctx
    tz = timezone(timedelta(hours=-5))
    ctx.profile.created_at = datetime(2026, 10, 26, 9, 0)
    r = srv._info_reloj(datetime(2026, 10, 21, 8, 0, tzinfo=tz))
    assert r["zona"].startswith("UTC-05:00") and r["utc_offset_min"] == -300
    assert r["instalacion"].startswith("2026-10-26") and r["reloj_anterior_instalacion"] is True
    assert r["ajuste_habilitado"] is False
    r = srv._info_reloj(datetime(2026, 10, 27, 8, 0, tzinfo=tz))
    assert r["reloj_anterior_instalacion"] is False


def test_sin_perfil_no_avisa(srv_ctx):
    srv, ctx = srv_ctx
    ctx.profile = None
    r = srv._info_reloj()
    assert r["instalacion"] is None and r["reloj_anterior_instalacion"] is False


def test_endpoint_y_sin_ajuste(srv_ctx):
    from fastapi.testclient import TestClient
    srv, ctx = srv_ctx
    ctx.profile = None
    c = TestClient(srv.app)
    assert c.get("/system/time").status_code == 200
    for metodo in ("put", "post", "patch"):
        assert getattr(c, metodo)("/system/time", json={}).status_code == 405
    rutas = {getattr(r, "path", "") for r in srv.app.routes}
    assert not any("time" in p and p != "/system/time" for p in rutas)


@pytest.mark.parametrize("rol", ["admin", "tecnico", "ingeniero"])
def test_visible_para_todos(rol):
    from autoclave.ui_qml.domain import permisos_opciones as p
    assert p.puede_ver("fecha_hora", rol) and p.edicion_permitida("CICLO", rol, "fecha_hora")
    assert not p.puede_ver("fecha_hora", "operador")


def test_controlador_aviso_local():
    import sys
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    from autoclave.ui_qml.controllers.fecha_hora_controller import FechaHoraController
    from autoclave.ui_qml.sesion_backend import Resultado

    class S:
        def enviar(self, m, r, c=None):
            return Resultado("ok", {"zona": "UTC-05:00", "instalacion": "2026-10-26T09:00:00",
                                    "reloj_anterior_instalacion": False}, 200)
    tz = timezone(timedelta(hours=-5))
    c = FechaHoraController(sesion=S(), reloj=lambda: datetime(2026, 10, 21, 7, 5, 9, tzinfo=tz))
    c.cargar()
    assert (c.hora, c.fechaIso, c.zona) == ("07:05:09", "2026-10-21", "UTC-05:00")
    assert c.relojAnterior is True          # calculado localmente con la instalación


@pytest.mark.parametrize("rol,anterior", [("admin", False), ("tecnico", True)])
def test_pantalla(rol, anterior):
    pytest.importorskip("PySide6")
    from tests.opciones_qml_doble import correr
    datos = {"zona": "UTC-05:00 (Hora est. Pacífico SA)", "reloj_anterior_instalacion": anterior,
             "instalacion": "2026-10-26T09:00:00" if anterior else "2026-10-01T09:00:00"}
    r = correr("fecha_hora", rol, {"/system/time": datos},
               pasos=[{"leer": [("avisoRelojAnterior", "visible"), ("avisoEdicionBloqueada", "visible"),
                                ("horaGrande", "text")],
                       "captura": f"O2c_{'2_aviso' if anterior else '1_fecha_hora'}_{rol}.png"}])
    assert r["avisos"] == []
    p = r["pasos"][0]["props"]
    assert p["avisoRelojAnterior.visible"] is anterior and p["avisoEdicionBloqueada.visible"] is False
    assert len(p["horaGrande.text"]) == 8
    assert any("Solo lectura" in t for t in r["pasos"][0]["textos"])

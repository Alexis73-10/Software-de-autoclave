# tests/test_o2d_info_sistema.py
#
# O2d (tanda 6; mockup 8): Información del sistema, solo lectura, para todos.
# GET /system/info agrupa equipo, software/módulo E/S, uso/mantenimiento y
# configuración vigente; un dato que falla queda en None sin romper el resto.

from datetime import datetime
from unittest.mock import MagicMock

import pytest

INFO = {
    "equipo": {"modelo": "ACV-150", "serie": "ACV-2026-001", "instalacion": "2026-10-26T09:00:00",
               "fuente_vapor": "generator"},
    "software": {"version": "1.0.0", "firmware": "1.0.0", "id_tarjeta": "ESP32-A1B2C3"},
    "uso": {"ciclos": 128, "mantenimiento": None},
    "configuracion": {"idioma": "es", "unidades": {"temperatura": "C", "presion": "kPa"},
                      "impresora": "sin_papel", "red": "conectada"},
}


@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cargar_servidor
    ctx = MagicMock()
    ctx.profile.model_id, ctx.profile.serial_number = "ACV-150", "ACV-2026-001"
    ctx.profile.created_at = datetime(2026, 10, 26, 9, 0)
    ctx.profile.vapor_source = "boiler"
    ctx.serial.tarjeta.return_value = {"version": "1.0.0", "id": "ESP32-X"}
    ctx.db.max_numero_ciclo.return_value = 42
    ctx.mantenimiento.resumen.return_value = {"estado": "ok"}
    ctx.config_idioma.leer.return_value = "en"
    ctx.config_unidades.leer.return_value = {"temperatura": "F", "presion": "psi"}
    ctx.config_impresora.habilitada.return_value = True
    ctx.realtime_printer.estado.return_value = "lista"
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), ctx


def test_info_completa(cliente):
    c, ctx = cliente
    d = c.get("/system/info").json()
    assert d["equipo"] == {"modelo": "ACV-150", "serie": "ACV-2026-001",
                           "instalacion": "2026-10-26T09:00:00", "fuente_vapor": "boiler",
                           "capacidad_litros": None, "tipo_carga": None,     # M1: MagicMock = sin dato
                           "clase": None}                                    # E2 (tanda 8)
    assert d["software"]["firmware"] == "1.0.0" and d["software"]["id_tarjeta"] == "ESP32-X"
    assert d["uso"]["ciclos"] == 42 and d["uso"]["mantenimiento"] == {"estado": "ok"}
    assert d["configuracion"]["idioma"] == "en" and d["configuracion"]["impresora"] == "lista"
    assert d["configuracion"]["unidades"] == {"temperatura": "F", "presion": "psi"}
    assert d["configuracion"]["red"] in ("conectada", "sin_red")


def test_un_dato_que_falla_no_rompe(cliente):
    c, ctx = cliente
    ctx.db.max_numero_ciclo.side_effect = RuntimeError("bd")
    ctx.config_impresora.habilitada.return_value = False
    d = c.get("/system/info").json()
    assert d["uso"]["ciclos"] is None and d["configuracion"]["impresora"] == "deshabilitada"
    assert d["equipo"]["modelo"] == "ACV-150"


def test_grupos_presentables():
    from autoclave.ui_qml.controllers.info_sistema_controller import grupos_de
    g = {x["grupo"]: {f["clave"]: f for f in x["filas"]} for x in grupos_de(INFO)}
    assert list(g) == ["equipo", "software", "uso", "configuracion"]
    assert g["equipo"]["fuente_vapor"]["valorClave"] == "info_sistema.vapor_generator"
    assert g["uso"]["ciclos_realizados"]["valor"] == "128"
    assert g["configuracion"]["unidades"]["valor"] == "°C / kPa"
    assert g["configuracion"]["impresora"]["chip"] == "aviso"
    assert g["configuracion"]["red"]["chip"] == "ok"
    vacio = grupos_de({})
    assert all(f["valor"] == "" and f["chip"] == "" for x in vacio for f in x["filas"])


@pytest.mark.parametrize("rol", ["admin", "tecnico", "ingeniero"])
def test_visible_para_todos(rol):
    from autoclave.ui_qml.domain import permisos_opciones as p
    assert p.puede_ver("info_sistema", rol) and p.edicion_permitida("CICLO", rol, "info_sistema")


def test_pantalla():
    pytest.importorskip("PySide6")
    from tests.helpers.opciones_qml_doble import correr
    r = correr("info_sistema", "admin", {"/system/info": INFO},
               pasos=[{"leer": [("avisoEdicionBloqueada", "visible")], "captura": "O2d_1_info_sistema.png"}])
    assert r["avisos"] == []
    t = r["pasos"][0]["textos"]
    for texto in ("ACV-2026-001", "ESP32-A1B2C3", "128", "Generador", "Sin papel", "Conectada", "Español"):
        assert texto in t, texto
    assert "No disponible" not in t
    assert r["pasos"][0]["props"]["avisoEdicionBloqueada.visible"] is False

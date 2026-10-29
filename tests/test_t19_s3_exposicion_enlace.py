"""Tanda 19 (P-s3): exposición del enlace Modbus.

- MOD-10: /status["comunicacion"] pasa tal cual el diagnóstico del enlace,
  incluida la clave `modulos` del ModbusLink.
- MOD-06/MOD-12: /status["modulo_es"] funciona con `modulo_es()` del ModbusLink
  ({"version": "1.5 / 1.3", "protocolo": "modbus-tcp", "id": <MAC>}).
- MOD-01: el enlace activo en Información del equipo (panel) y en OPCIONES ›
  Información del sistema (/system/info, grupo software).

Tanda 20 (T20-03): el enlace serial se retiró; /status publica la constante
"modbus" y la interfaz ya no tiene texto para "serial" (se muestra como un
valor desconocido). Los casos serial se borraron o pasaron a ese caso."""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

_MAC = "A1B2C3D4E5F6"
_TARJETA_MODBUS = {"version": "1.5 / 1.3", "protocolo": "modbus-tcp", "id": _MAC}
_MODULOS = {
    "modelos": ["XAXX0A00G", "GAXXXA000", "GXXAX00A0", "GXXAX00A0", "GXDXX0600"],
    "firmware": {"principal": "1.5", "expansiones": ["1.3", "1.3", "1.3", "1.3"]},
    "mac": _MAC,
    "codigo_error": 0,
    "mascara_expansores": 0,
    "falla_salidas": 0,
    "enlace": "modbus-tcp",
}
_I18N = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "i18n"


@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cargar_servidor
    ctx = MagicMock()
    ctx.estado.estado_puertas = {}
    ctx.estado.sensores_temp = {}
    ctx.estado.sensores_pres = {}
    ctx.estado.sensores_di = {}
    ctx.estado.salidas_do = {}
    ctx.estado.flags = {}
    ctx.estado.Alarmas_activas = []
    ctx.profile.model_id, ctx.profile.serial_number = "ACV-150", "ACV-2026-001"
    ctx.profile.created_at = datetime(2026, 10, 26, 9, 0)
    ctx.profile.vapor_source = "boiler"
    ctx.profile.board_id = _MAC
    ctx.serial.modulo_es.return_value = dict(_TARJETA_MODBUS)
    ctx.serial.get_diagnostico.return_value = {
        "lineas_invalidas_total": 3, "lineas_invalidas_consecutivas": 0,
        "handshake_completo": True, "modulo_es_st": None, "modulos": _MODULOS}
    ctx.db.max_numero_ciclo.return_value = 1
    ctx.mantenimiento.resumen.return_value = {"estado": "ok"}
    ctx.config_idioma.leer.return_value = "es"
    ctx.config_unidades.leer.return_value = {"temperatura": "C", "presion": "kPa"}
    ctx.config_impresora.habilitada.return_value = False
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), ctx


# ---------------------------------------------------------------------------
# /status (MOD-10, MOD-06)
# ---------------------------------------------------------------------------

@pytest.mark.req("MOD-10")
def test_status_comunicacion_pasa_los_modulos_tal_cual(cliente):
    c, _ = cliente
    com = c.get("/status").json()["comunicacion"]
    assert com["modulos"] == _MODULOS
    assert com["handshake_completo"] is True and com["modulo_es_st"] is None
    assert com["lineas_invalidas_total"] == 3


@pytest.mark.req("MOD-10")
def test_status_comunicacion_sin_diagnostico_es_none(cliente):
    c, ctx = cliente
    ctx.serial.get_diagnostico.side_effect = RuntimeError("enlace caído")
    assert c.get("/status").json()["comunicacion"] is None


@pytest.mark.req("MOD-12")
def test_status_tarjeta_con_el_enlace_modbus(cliente):
    c, _ = cliente
    assert c.get("/status").json()["modulo_es"] == {
        "version": "1.5 / 1.3", "id": _MAC, "emparejada": True}


@pytest.mark.req("MOD-12")
def test_status_tarjeta_modbus_no_emparejada(cliente):
    c, ctx = cliente
    ctx.profile.board_id = "FFFFFFFFFFFF"
    assert c.get("/status").json()["modulo_es"]["emparejada"] is False


@pytest.mark.req("MOD-01")
def test_status_y_system_info_publican_el_enlace(cliente):
    # T20-03: valor constante "modbus" (se borró el caso "serial")
    c, _ = cliente
    enlace = "modbus"
    assert c.get("/status").json()["enlace_io"] == enlace
    sw = c.get("/system/info").json()["software"]
    assert sw["enlace_io"] == enlace
    assert sw["firmware"] == "1.5 / 1.3" and sw["id_modulo_es"] == _MAC


# ---------------------------------------------------------------------------
# Información del sistema (OPCIONES)
# ---------------------------------------------------------------------------

def _software(sw):
    from autoclave.ui_qml.controllers.info_sistema_controller import grupos_de
    g = {x["grupo"]: {f["clave"]: f for f in x["filas"]} for x in grupos_de({"software": sw})}
    return g["software"]


@pytest.mark.req("MOD-01")
@pytest.mark.parametrize("enlace", ["modbus"])     # T20-03: sin "serial"
def test_info_sistema_fila_del_enlace(enlace):
    fila = _software({"version": "1.0", "enlace_io": enlace})["enlace_io"]
    assert fila["valorClave"] == f"equipo.enlace_io_{enlace}"


@pytest.mark.req("MOD-01")
# T20-03: "serial" (enlace retirado) se muestra como valor desconocido
@pytest.mark.parametrize("valor", [None, "", "rtu", 3, "serial"])
def test_info_sistema_enlace_sin_dato_muestra_guion(valor):
    fila = _software({"enlace_io": valor})["enlace_io"]
    assert fila == {"clave": "enlace_io", "valor": "", "valorClave": "", "chip": ""}


@pytest.mark.req("MOD-01")
def test_info_sistema_rotulo_en_es_y_en():
    from autoclave.ui_qml.controllers.info_sistema_controller import CLAVES_FILA
    assert "enlace_io" in CLAVES_FILA
    for idioma in ("es", "en"):
        datos = json.loads((_I18N / f"{idioma}.json").read_text(encoding="utf-8"))
        assert datos["info_sistema"]["rotulo_enlace_io"]
        # T20-03: la clave enlace_io_serial se retiró con el enlace serial
        for clave in ("enlace_io", "enlace_io_modbus"):
            assert datos["equipo"][clave]
        assert "enlace_io_serial" not in datos["equipo"]


# ---------------------------------------------------------------------------
# Información del equipo (panel)
# ---------------------------------------------------------------------------

def _filas(**kw):
    from autoclave.ui_qml.bridge.info_equipo import filas_equipo
    return {f["clave"]: f for f in filas_equipo(None, 1, "1.0", [], **kw)}


@pytest.mark.req("MOD-01")
@pytest.mark.parametrize("enlace", ["modbus"])     # T20-03: sin "serial"
def test_panel_equipo_fila_del_enlace(enlace):
    fila = _filas(enlace=enlace)["enlace_io"]
    assert fila == {"clave": "enlace_io", "valor": enlace, "disponible": True,
                    "valorClave": f"enlace_io_{enlace}"}


@pytest.mark.req("MOD-01")
def test_panel_equipo_enlace_sin_consultar_es_guion():
    fila = _filas()["enlace_io"]
    assert fila == {"clave": "enlace_io", "valor": None, "disponible": True}


@pytest.mark.req("MOD-01")
# T20-03: "serial" (enlace retirado) es un valor no disponible
@pytest.mark.parametrize("valor", ["", "rtu", 7, "serial"])
def test_panel_equipo_enlace_invalido_es_no_disponible(valor):
    fila = _filas(enlace=valor)["enlace_io"]
    assert fila["disponible"] is False and "valorClave" not in fila


@pytest.mark.req("MOD-01")
def test_panel_equipo_con_tarjeta_modbus():
    filas = _filas(modulo_es={"version": "1.5 / 1.3", "id": _MAC, "emparejada": True},
                   enlace="modbus")
    assert filas["version_modulo_es"]["valor"] == "1.5 / 1.3"
    assert filas["id_modulo_es"]["valor"] == _MAC
    assert filas["emparejamiento_modulo_es"]["valorClave"] == "modulo_es_emparejada"


def _info_equipo(status):
    pytest.importorskip("PySide6")
    from autoclave.ui_qml.bridge.info_equipo import InfoEquipo
    backend = MagicMock()

    def get(ruta, **kw):
        if ruta == "/cycle/history":
            return []
        if ruta == "/status":
            if isinstance(status, Exception):
                raise status
            return status
        return None

    backend.get.side_effect = get
    info = InfoEquipo(None, 1, backend, "1.0", ejecutar=lambda tarea: tarea())
    return info


@pytest.mark.req("MOD-01")
def test_info_equipo_consulta_el_enlace_en_status():
    info = _info_equipo({"modulo_es": dict(_TARJETA_MODBUS), "enlace_io": "modbus"})
    info.actualizar()
    filas = {f["clave"]: f for f in info.filas}
    assert filas["enlace_io"]["valorClave"] == "enlace_io_modbus"


@pytest.mark.req("MOD-01")
def test_info_equipo_status_sin_enlace_es_no_disponible():
    info = _info_equipo({"modulo_es": None})
    info.actualizar()
    assert {f["clave"]: f for f in info.filas}["enlace_io"]["disponible"] is False


@pytest.mark.req("MOD-01")
def test_info_equipo_conserva_el_enlace_si_falla_la_consulta():
    # T20-03: con "modbus" (antes "serial", retirado)
    info = _info_equipo({"enlace_io": "modbus"})
    info.actualizar()
    info._backend.get.side_effect = lambda ruta, **kw: (_ for _ in ()).throw(ConnectionError())
    info.actualizar()
    assert {f["clave"]: f for f in info.filas}["enlace_io"]["valorClave"] == "enlace_io_modbus"


def test_tarjeta_simple_namespace_no_rompe():
    # perfil sin board_id con el enlace Modbus: emparejada False (solo aviso, FW-D7)
    from autoclave.installation.profile import modulo_es_emparejado
    assert modulo_es_emparejado(SimpleNamespace(board_id=None), _MAC) is False

"""E6 — FW-D7: emparejamiento tarjeta–equipo (board_id en el perfil), su
herramienta de instalación, /status.tarjeta, audit_log en cada conexión e
Información del sistema."""

import importlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoclave.installation.profile import tarjeta_emparejada, validate_profile_data

_ID = "A1B2C3D4E5F6"

_PERFIL = {
    "machine_id": "ACV-2026-SN1", "model_id": "SPK", "serial_number": "SN1",
    "door_count": 2, "door_type": "simple", "equipment_class": "piso_lab",
    "door_id": 1, "role": "operator_front", "created_at": "2026-05-25T05:49:47",
    "cooling_level": 3, "locked": True,
}


# ---------------------------------------------------------------------------
# Perfil
# ---------------------------------------------------------------------------

def test_board_id_es_opcional():
    assert validate_profile_data(dict(_PERFIL)) == []


def test_board_id_valido():
    assert validate_profile_data({**_PERFIL, "board_id": _ID}) == []


@pytest.mark.parametrize("valor", ["a1b2c3d4e5f6", "A1B2C3", "A1B2C3D4E5FG", 12, None])
def test_board_id_invalido(valor):
    errores = validate_profile_data({**_PERFIL, "board_id": valor})
    assert any("board_id" in e for e in errores)


def test_storage_carga_board_id(tmp_path, monkeypatch):
    from autoclave.installation import storage
    f = tmp_path / "installation_profile.json"
    f.write_text(json.dumps({**_PERFIL, "board_id": _ID}), encoding="utf-8")
    monkeypatch.setattr(storage, "INSTALLATION_FILE", f)
    assert storage.load().board_id == _ID


def test_storage_sin_board_id_es_none(tmp_path, monkeypatch):
    from autoclave.installation import storage
    f = tmp_path / "installation_profile.json"
    f.write_text(json.dumps(_PERFIL), encoding="utf-8")
    monkeypatch.setattr(storage, "INSTALLATION_FILE", f)
    assert storage.load().board_id is None


@pytest.mark.parametrize("perfil,ident,esperado", [
    (SimpleNamespace(board_id=_ID), _ID, True),
    (SimpleNamespace(board_id=_ID), "FFFFFFFFFFFF", False),
    (SimpleNamespace(board_id=None), _ID, False),          # sin emparejar
    (None, _ID, False),
    (SimpleNamespace(board_id=_ID), None, None),           # sin tarjeta
])
def test_tarjeta_emparejada(perfil, ident, esperado):
    assert tarjeta_emparejada(perfil, ident) is esperado


# ---------------------------------------------------------------------------
# tools/emparejar_tarjeta.py
# ---------------------------------------------------------------------------

_RUTA = Path(__file__).resolve().parents[1] / "tools" / "emparejar_tarjeta.py"


@pytest.fixture
def herramienta():
    spec = importlib.util.spec_from_file_location("emparejar_tarjeta", _RUTA)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _perfil(tmp_path, **extra):
    f = tmp_path / "installation_profile.json"
    f.write_text(json.dumps({**_PERFIL, **extra}), encoding="utf-8")
    return f


def test_herramienta_registra_el_id(tmp_path, herramienta):
    f = _perfil(tmp_path)
    assert herramienta.main(["--perfil", str(f), "--id", _ID, "--si"]) == 0
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data["board_id"] == _ID
    assert data["locked"] is True
    assert list(tmp_path.glob("installation_profile.json.*.bak"))
    registro = (tmp_path / "installation_profile_cambios.log").read_text(encoding="utf-8")
    assert "emparejar_tarjeta" in registro and _ID in registro


def test_herramienta_normaliza_a_mayuscula(tmp_path, herramienta):
    f = _perfil(tmp_path)
    assert herramienta.main(["--perfil", str(f), "--id", _ID.lower(), "--si"]) == 0
    assert json.loads(f.read_text(encoding="utf-8"))["board_id"] == _ID


@pytest.mark.parametrize("ident", ["A1B2C3", "ZZZZZZZZZZZZ", ""])
def test_herramienta_rechaza_id_invalido(tmp_path, herramienta, ident):
    f = _perfil(tmp_path)
    assert herramienta.main(["--perfil", str(f), "--id", ident, "--si"]) == 1
    assert "board_id" not in json.loads(f.read_text(encoding="utf-8"))
    assert not list(tmp_path.glob("*.bak"))


def test_herramienta_sin_confirmar_no_escribe(tmp_path, herramienta, monkeypatch):
    f = _perfil(tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "no")
    assert herramienta.main(["--perfil", str(f), "--id", _ID]) == 1
    assert "board_id" not in json.loads(f.read_text(encoding="utf-8"))


def test_herramienta_mostrar(tmp_path, herramienta, capsys):
    f = _perfil(tmp_path, board_id=_ID)
    assert herramienta.main(["--perfil", str(f), "--mostrar"]) == 0
    assert _ID in capsys.readouterr().out


def test_herramienta_mostrar_sin_registrar(tmp_path, herramienta, capsys):
    f = _perfil(tmp_path)
    assert herramienta.main(["--perfil", str(f), "--mostrar"]) == 0
    assert "sin registrar" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# /status.tarjeta
# ---------------------------------------------------------------------------

@pytest.fixture
def status_client():
    ctx = MagicMock()
    for key in list(sys.modules):
        if "autoclave.backend.server" in key or key.startswith(("autoclave.backend.dependencias", "autoclave.backend.rutas")):
            del sys.modules[key]
    with patch("autoclave.backend.context.BackendContext", return_value=ctx):
        srv = importlib.import_module("autoclave.backend.server")
    from fastapi.testclient import TestClient
    ctx.estado.estado_puertas = {}
    ctx.estado.sensores_temp = {}
    ctx.estado.sensores_pres = {}
    ctx.estado.sensores_di = {}
    ctx.estado.salidas_do = {}
    ctx.estado.flags = {}
    ctx.estado.Alarmas_activas = []
    ctx.serial.get_diagnostico.return_value = {"lineas_invalidas_total": 0}
    return TestClient(srv.app), ctx


def test_status_expone_tarjeta_emparejada(status_client):
    client, ctx = status_client
    ctx.serial.tarjeta.return_value = {"version": "1.0.0", "protocolo": 2, "id": _ID}
    ctx.profile = SimpleNamespace(board_id=_ID)
    assert client.get("/status").json()["tarjeta"] == {
        "version": "1.0.0", "id": _ID, "emparejada": True}


def test_status_tarjeta_distinta(status_client):
    client, ctx = status_client
    ctx.serial.tarjeta.return_value = {"version": "1.0.0", "protocolo": 2, "id": _ID}
    ctx.profile = SimpleNamespace(board_id="FFFFFFFFFFFF")
    assert client.get("/status").json()["tarjeta"]["emparejada"] is False


def test_status_sin_tarjeta(status_client):
    client, ctx = status_client
    ctx.serial.tarjeta.return_value = {"version": None, "protocolo": None, "id": None}
    ctx.profile = SimpleNamespace(board_id=_ID)
    assert client.get("/status").json()["tarjeta"] == {
        "version": None, "id": None, "emparejada": None}


def test_status_tarjeta_con_enlace_sin_metodo(status_client):
    client, ctx = status_client
    ctx.serial.tarjeta.side_effect = AttributeError
    assert client.get("/status").json()["tarjeta"] == {
        "version": None, "id": None, "emparejada": None}


# ---------------------------------------------------------------------------
# audit_log en cada conexión (BackendContext)
# ---------------------------------------------------------------------------

def _ctx(board_id):
    from autoclave.backend.context import BackendContext
    ctx = BackendContext.__new__(BackendContext)
    ctx.db = MagicMock()
    ctx.profile = SimpleNamespace(board_id=board_id)
    return ctx


def test_conexion_emparejada_se_audita():
    ctx = _ctx(_ID)
    ctx._al_conectar_tarjeta({"version": "1.0.0", "protocolo": 2, "id": _ID})
    args, kwargs = ctx.db.registrar_auditoria.call_args
    assert args[0] == "tarjeta_conectada"
    assert kwargs["valor_nuevo"] == {"version": "1.0.0", "protocolo": 2, "id": _ID}
    assert kwargs["detalle"]["emparejada"] is True


@pytest.mark.parametrize("board_id", ["FFFFFFFFFFFF", None])
def test_conexion_no_emparejada_se_audita_y_advierte(board_id, caplog):
    ctx = _ctx(board_id)
    with caplog.at_level("WARNING"):
        ctx._al_conectar_tarjeta({"version": "1.0.0", "protocolo": 2, "id": _ID})
    assert ctx.db.registrar_auditoria.call_args.kwargs["detalle"]["emparejada"] is False
    assert any("emparej" in r.getMessage() for r in caplog.records)


def test_conexion_sin_base_de_datos_no_falla():
    ctx = _ctx(_ID)
    ctx.db = None
    ctx._al_conectar_tarjeta({"version": "1.0.0", "protocolo": 2, "id": _ID})


def test_fallo_de_la_bitacora_no_se_propaga():
    ctx = _ctx(_ID)
    ctx.db.registrar_auditoria.side_effect = RuntimeError("disco")
    ctx._al_conectar_tarjeta({"version": "1.0.0", "protocolo": 2, "id": _ID})


def test_build_modbus_registra_al_conectar_antes_de_arrancar():
    # T20-03: antes build_serial con factory.SerialLink; ahora build_modbus con
    # ModbusLink parcheado en su módulo (import diferido; sin red)
    from autoclave.devices.factory import factory
    callback = MagicMock()
    with patch("autoclave.protocols.modbus_link.ModbusLink") as cls:
        instancia = cls.return_value
        orden = []
        instancia.start.side_effect = lambda: orden.append(("start", instancia.al_conectar))
        factory.build_modbus(MagicMock(), al_conectar=callback)
    assert orden == [("start", callback)]


# ---------------------------------------------------------------------------
# Información del sistema
# ---------------------------------------------------------------------------

def _filas(tarjeta):
    from autoclave.ui_qml.bridge.info_equipo import filas_equipo
    return {f["clave"]: f for f in filas_equipo(None, 1, "1.0", [], tarjeta)}


def test_info_sistema_muestra_version_e_id_de_la_tarjeta():
    filas = _filas({"version": "1.0.0", "id": _ID, "emparejada": True})
    assert filas["version_modulo_es"] == {"clave": "version_modulo_es", "valor": "1.0.0",
                                        "disponible": True}
    assert filas["id_modulo_es"]["valor"] == _ID
    assert filas["emparejamiento_modulo_es"]["valorClave"] == "modulo_es_emparejada"


@pytest.mark.parametrize("emparejada,clave", [(False, "modulo_es_no_emparejada"),
                                              (None, None)])
def test_info_sistema_emparejamiento(emparejada, clave):
    filas = _filas({"version": "1.0.0", "id": _ID, "emparejada": emparejada})
    assert filas["emparejamiento_modulo_es"].get("valorClave") == clave


def test_info_sistema_sin_dato_de_tarjeta():
    filas = _filas(None)
    assert filas["version_modulo_es"]["valor"] is None
    assert filas["version_modulo_es"]["disponible"] is True
    assert filas["id_modulo_es"]["valor"] is None


def test_info_equipo_consulta_status_para_la_tarjeta():
    from autoclave.ui_qml.bridge.info_equipo import InfoEquipo
    backend = MagicMock()
    backend.get.side_effect = lambda ruta, **kw: (
        [] if ruta == "/cycle/history"
        else {"tarjeta": {"version": "1.0.0", "id": _ID, "emparejada": True}})
    info = InfoEquipo(None, 1, backend, "1.0", ejecutar=lambda tarea: tarea())
    info.actualizar()
    filas = {f["clave"]: f for f in info.filas}
    assert filas["version_modulo_es"]["valor"] == "1.0.0"
    assert filas["id_modulo_es"]["valor"] == _ID


def test_textos_de_tarjeta_en_es_json():
    ruta = Path(__file__).resolve().parents[1] / "src/autoclave/i18n/es.json"
    equipo = json.loads(ruta.read_text(encoding="utf-8"))["equipo"]
    for clave in ("id_modulo_es", "emparejamiento_modulo_es", "modulo_es_emparejada",
                  "modulo_es_no_emparejada"):
        assert equipo.get(clave)

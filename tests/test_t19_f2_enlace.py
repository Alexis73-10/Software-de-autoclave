# Tanda 19, F2: selección del enlace de E/S (MOD-01) e interfaz común (MOD-02).

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from autoclave.config import enlace_io
from autoclave.devices.factory import factory
from autoclave.protocols import enlace as enlace_mod
from autoclave.protocols import serial_link
from autoclave.utils.resources import resource_path


@pytest.mark.req("MOD-01")
def test_archivo_del_producto_selecciona_modbus():
    assert enlace_io.leer_enlace(resource_path(enlace_io.CONFIG_RELATIVE_PATH)) == "modbus"


@pytest.mark.req("MOD-01")
@pytest.mark.parametrize("contenido,esperado", [
    ({"enlace": "serial"}, "serial"),
    ({"enlace": "modbus"}, "modbus"),
    ({"enlace": " Serial "}, "serial"),
    ({"enlace": "rtu"}, "modbus"),
    ({"enlace": 1}, "modbus"),
    ({}, "modbus"),
    (["serial"], "modbus"),
])
def test_valores_admitidos_y_defecto(tmp_path, contenido, esperado):
    ruta = tmp_path / "enlace_io.json"
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    assert enlace_io.leer_enlace(str(ruta)) == esperado


@pytest.mark.req("MOD-01")
def test_archivo_ausente_o_invalido_da_modbus(tmp_path):
    assert enlace_io.leer_enlace(str(tmp_path / "no_existe.json")) == "modbus"
    malo = tmp_path / "malo.json"
    malo.write_text("{no es json", encoding="utf-8")
    assert enlace_io.leer_enlace(str(malo)) == "modbus"


@pytest.mark.req("MOD-01")
def test_se_lee_una_vez_por_proceso(monkeypatch):
    llamadas = []
    monkeypatch.setattr(enlace_io, "leer_enlace", lambda ruta=None: llamadas.append(1) or "serial")
    enlace_io.fijar_enlace(None)
    assert enlace_io.enlace_activo() == "serial"
    assert enlace_io.enlace_activo() == "serial"
    assert llamadas == [1]


@pytest.mark.req("MOD-01")
def test_fijar_enlace_rechaza_valores_no_admitidos():
    with pytest.raises(ValueError):
        enlace_io.fijar_enlace("rtu")


@pytest.mark.req("MOD-01")
def test_build_enlace_serial_usa_build_serial():
    enlace_io.fijar_enlace("serial")
    with patch.object(factory, "build_serial") as bs, patch.object(factory, "build_modbus") as bm:
        r = factory.build_enlace("units", al_conectar="cb")
    bs.assert_called_once_with("units", al_conectar="cb")
    bm.assert_not_called()
    assert r is bs.return_value


@pytest.mark.req("MOD-01")
def test_build_enlace_modbus_usa_build_modbus(enlace_modbus):
    with patch.object(factory, "build_serial") as bs, patch.object(factory, "build_modbus") as bm:
        r = factory.build_enlace("units", al_conectar="cb")
    bm.assert_called_once_with("units", al_conectar="cb")
    bs.assert_not_called()
    assert r is bm.return_value


@pytest.mark.req("MOD-01")
def test_build_modbus_sin_modulo_da_error_claro(monkeypatch):
    monkeypatch.setitem(sys.modules, "autoclave.protocols.modbus_link", None)
    with pytest.raises(RuntimeError, match="enlace_io.json"):
        factory.build_modbus(MagicMock())


@pytest.mark.req("MOD-01")
def test_contexto_construye_con_build_enlace():
    from autoclave.backend import context as ctx_mod
    assert not hasattr(ctx_mod, "build_serial")
    assert ctx_mod.build_enlace is factory.build_enlace


@pytest.mark.req("MOD-02")
def test_evento_tarjeta_se_reexporta_desde_serial_link():
    assert serial_link.EventoTarjeta is enlace_mod.EventoTarjeta


@pytest.mark.req("MOD-02")
def test_serial_link_cumple_la_interfaz():
    for nombre in enlace_mod.MIEMBROS_ENLACE:
        assert hasattr(serial_link.SerialLink, nombre) or nombre in ("on_update", "al_conectar"), nombre
    enlace = serial_link.SerialLink()
    assert isinstance(enlace, enlace_mod.EnlaceES)
    for nombre in enlace_mod.MIEMBROS_ENLACE:
        assert hasattr(enlace, nombre), nombre


@pytest.mark.req("MOD-02")
def test_miembros_del_protocol_coinciden_con_la_lista():
    anotados = set(getattr(enlace_mod.EnlaceES, "__annotations__", {}))
    metodos = {n for n in vars(enlace_mod.EnlaceES) if not n.startswith("_")}
    assert anotados | metodos == set(enlace_mod.MIEMBROS_ENLACE)


@pytest.fixture
def status_client():
    import importlib
    from fastapi.testclient import TestClient
    ctx = MagicMock()
    for key in list(sys.modules):
        if "autoclave.backend.server" in key or key.startswith(("autoclave.backend.dependencias", "autoclave.backend.rutas")):
            del sys.modules[key]
    with patch("autoclave.backend.context.BackendContext", return_value=ctx):
        srv = importlib.import_module("autoclave.backend.server")
    ctx.estado.estado_puertas = {}
    ctx.estado.sensores_temp = {}
    ctx.estado.sensores_pres = {}
    ctx.estado.sensores_di = {}
    ctx.estado.salidas_do = {}
    ctx.estado.flags = {}
    ctx.estado.Alarmas_activas = []
    ctx.serial.get_diagnostico.return_value = {"lineas_invalidas_total": 0}
    ctx.serial.tarjeta.return_value = {"version": None, "protocolo": None, "id": None}
    return TestClient(srv.app)


@pytest.mark.req("MOD-01")
@pytest.mark.parametrize("valor", ["serial", "modbus"])
def test_status_publica_el_enlace_activo(status_client, valor):
    enlace_io.fijar_enlace(valor)
    assert status_client.get("/status").json()["enlace_io"] == valor

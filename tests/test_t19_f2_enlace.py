# Tanda 19, F2: selección del enlace de E/S (MOD-01) e interfaz común (MOD-02).
#
# Tanda 20 (T20-03): el enlace serial y su selección por config/enlace_io.json
# se retiraron. Se borraron las pruebas de la selección por archivo y de la
# reexportación/conformidad de serial_link; build_enlace construye siempre
# ModbusLink y /status publica la constante "modbus".

import sys
from unittest.mock import MagicMock, patch

import pytest

from autoclave.devices.factory import factory
from autoclave.protocols import enlace as enlace_mod


@pytest.mark.req("MOD-01")
def test_build_enlace_modbus_usa_build_modbus():
    with patch.object(factory, "build_modbus") as bm:
        r = factory.build_enlace("units", al_conectar="cb")
    bm.assert_called_once_with("units", al_conectar="cb")
    assert r is bm.return_value


@pytest.mark.req("MOD-01")
def test_build_modbus_sin_modulo_da_error_claro(monkeypatch):
    monkeypatch.setitem(sys.modules, "autoclave.protocols.modbus_link", None)
    # T20-03: el mensaje ya no remite a «usar 'serial' en config/enlace_io.json»
    with pytest.raises(RuntimeError, match="enlace Modbus no está disponible"):
        factory.build_modbus(MagicMock())


@pytest.mark.req("MOD-01")
def test_contexto_construye_con_build_enlace():
    from autoclave.backend import context as ctx_mod
    assert not hasattr(ctx_mod, "build_serial")
    assert ctx_mod.build_enlace is factory.build_enlace


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
def test_status_publica_el_enlace_activo(status_client):
    # T20-03: valor constante "modbus" (antes parametrizada con "serial")
    assert status_client.get("/status").json()["enlace_io"] == "modbus"

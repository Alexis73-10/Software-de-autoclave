# tests/test_e1_supply_inputs_loop_status.py
#
# E1-1: ControlLoop no vigila suministro_electrico si el perfil no tiene la
# entrada; /status expone entradas_no_monitoreadas; aviso al arrancar.

import importlib
import logging
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from autoclave.state_machine.machine.enum_global import GlobalState

_SOLO_AIRE = {"agua_bomba": False, "agua_generador": False, "aire_comprimido": True,
              "vapor_suministro": False, "suministro_electrico": False}


class _FakeEstado:
    def __init__(self, suministro_electrico):
        self._flags = {"PARO_EMERGENCIA": False, "FALLO_SUMINISTRO_ELECTRICO": False}
        self._state = GlobalState.PREPARACION
        self.sensores_di = {"paro_emergencia": 1, "suministro_electrico": suministro_electrico}

    def get_machine_state(self):
        return self._state

    def get_flag(self, name):
        return self._flags.get(name, False)

    def set_flag(self, name, value):
        self._flags[name] = value

    def update(self, data):
        pass


def _loop(estado, profile):
    from autoclave.services.domain.loop.control_loop import ControlLoop
    cm = MagicMock()
    cm.get_selected_cycle.return_value = MagicMock()
    with patch("autoclave.services.domain.loop.control_loop.StateMachine") as sm_cls:
        loop = ControlLoop(units=MagicMock(), door_service=MagicMock(), doors=[],
                           estado=estado, link=MagicMock(), set_do=MagicMock(),
                           alarm_manager=MagicMock(), cycle_manager=cm,
                           config_manager=MagicMock(), profile=profile)
    loop.link.is_connected.return_value = True
    return loop, sm_cls


def test_control_loop_pasa_el_perfil_a_la_maquina_de_estados():
    perfil = SimpleNamespace(supply_inputs=_SOLO_AIRE)
    _, sm_cls = _loop(_FakeEstado(0), perfil)
    assert sm_cls.call_args.kwargs["profile"] is perfil


def test_suministro_electrico_no_aplica_no_activa_el_fallo():
    estado = _FakeEstado(suministro_electrico=0)
    loop, _ = _loop(estado, SimpleNamespace(supply_inputs=_SOLO_AIRE))
    loop._tick()
    assert estado.get_flag("FALLO_SUMINISTRO_ELECTRICO") is False
    loop.set_do.bomba_vacio_off.assert_not_called()


def test_suministro_electrico_requerido_sin_entrada_activa_el_fallo():
    estado = _FakeEstado(suministro_electrico=0)
    loop, _ = _loop(estado, None)
    loop._tick()
    assert estado.get_flag("FALLO_SUMINISTRO_ELECTRICO") is True


def test_set_active_cycle_conserva_el_perfil():
    perfil = SimpleNamespace(supply_inputs=_SOLO_AIRE)
    loop, _ = _loop(_FakeEstado(1), perfil)
    with patch("autoclave.services.domain.loop.control_loop.StateMachine") as sm_cls:
        loop.set_active_cycle(MagicMock())
    assert sm_cls.call_args.kwargs["profile"] is perfil


# ---------------------------------------------------------------------------
# /status
# ---------------------------------------------------------------------------

@pytest.fixture
def status_client():
    ctx = MagicMock()
    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
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
    return TestClient(srv.app), ctx


def test_status_expone_entradas_no_monitoreadas(status_client):
    client, ctx = status_client
    ctx.profile = SimpleNamespace(supply_inputs=_SOLO_AIRE)
    resp = client.get("/status")
    assert resp.status_code == 200
    assert resp.json()["entradas_no_monitoreadas"] == [
        "agua_bomba", "agua_generador", "vapor_suministro", "suministro_electrico"]


def test_status_sin_campo_lista_vacia(status_client):
    client, ctx = status_client
    ctx.profile = SimpleNamespace()
    assert client.get("/status").json()["entradas_no_monitoreadas"] == []


# ---------------------------------------------------------------------------
# Aviso al arrancar
# ---------------------------------------------------------------------------

def test_aviso_al_arrancar_lista_las_entradas(caplog):
    from autoclave.backend.context import avisar_entradas_no_monitoreadas
    with caplog.at_level(logging.WARNING):
        avisar_entradas_no_monitoreadas(SimpleNamespace(supply_inputs=_SOLO_AIRE))
    avisos = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(avisos) == 1
    assert "vapor_suministro" in avisos[0].getMessage()
    assert "suministro_electrico" in avisos[0].getMessage()


def test_sin_entradas_no_monitoreadas_no_avisa(caplog):
    from autoclave.backend.context import avisar_entradas_no_monitoreadas
    with caplog.at_level(logging.WARNING):
        avisar_entradas_no_monitoreadas(SimpleNamespace(supply_inputs=None))
    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


# ---------------------------------------------------------------------------
# Adenda A-2: sondas de temperatura no vigiladas en /status y al arrancar
# ---------------------------------------------------------------------------

def test_status_expone_sondas_no_vigiladas(status_client):
    client, ctx = status_client
    ctx.profile = SimpleNamespace(temperature_probes={"temp_ref": False})
    assert client.get("/status").json()["sondas_no_vigiladas"] == ["temp_ref"]


def test_status_sin_campo_de_sondas_lista_vacia(status_client):
    client, ctx = status_client
    ctx.profile = SimpleNamespace()
    assert client.get("/status").json()["sondas_no_vigiladas"] == []


def test_aviso_al_arrancar_lista_las_sondas(caplog):
    from autoclave.backend.context import avisar_entradas_no_monitoreadas
    with caplog.at_level(logging.WARNING):
        avisar_entradas_no_monitoreadas(SimpleNamespace(temperature_probes={"temp_ref": False}))
    avisos = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(avisos) == 1 and "temp_ref" in avisos[0]

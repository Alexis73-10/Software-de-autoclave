"""P1 (tanda 7): recorrido de la instalación del 22-oct (asistente, E/S,
calibración, apagado) con el backend doble, sin hardware. Cada prueba cubre
un bloqueo encontrado en el recorrido."""

import threading
import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.core.runtime import io_names
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cabecera, cargar_servidor


# ── Paso 5 (E/S): el vigilante del dueño del modo prueba no debe morir ──────
# `from datetime import time` en server.py tapaba el módulo `time`: el hilo
# hacía una sola pasada y caía en `time.sleep` (AttributeError). Después,
# una sesión dueña que caducara o cerrara NO sacaba del modo prueba.

def test_vigilante_del_modo_prueba_sigue_vivo_tras_varias_pasadas(tmp_path, monkeypatch):
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    pasadas = []
    listo = threading.Event()

    def revisar():
        pasadas.append(1)
        if len(pasadas) >= 3:
            listo.set()
        return False

    monkeypatch.setattr(srv, "_revisar_dueno_modo_prueba", revisar)
    hilo = threading.Thread(target=srv._vigilar_dueno_modo_prueba, args=(0.01,), daemon=True)
    hilo.start()
    assert listo.wait(3.0), f"el vigilante se detuvo tras {len(pasadas)} pasada(s)"
    assert hilo.is_alive()


def test_server_conserva_el_modulo_time():
    import autoclave.backend.server as s
    assert s.time is time


# ── Paso 5 (E/S): toda salida que la pantalla muestra se puede accionar ─────
# /io/channels da el nombre del YAML (aire_atmosferico_camara) pero el PATCH
# lo buscaba tal cual en EstadoAutoclave.map_do (errata aire_admosferico_camara)
# y respondía 404: el botón aparecía habilitado y la salida nunca cambiaba.

@pytest.fixture
def prueba_salidas():
    ctx = MagicMock()
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.estado.get_flag.return_value = False
    ctx.estado.sensores_di = {}
    ctx.doors = []
    ctx.control_loop.test_mode_active = True
    ctx.control_loop.apagando = False
    ctx.setdo.salida_bloqueada.return_value = False
    srv, _ = cargar_servidor(ctx)
    cab = cabecera(srv, "tecnico", "tec1")
    srv._token_modo_prueba = cab["Authorization"].split()[1]
    return TestClient(srv.app, headers=cab), ctx


def _nombres_do_mostrados():
    return [c["name"] for c in io_names.canales_digitales("DO")]


def test_hay_salidas_configuradas_en_el_equipo_activo():
    assert "aire_atmosferico_camara" in _nombres_do_mostrados()


@pytest.mark.parametrize("nombre", _nombres_do_mostrados())
@pytest.mark.parametrize("valor", [True, False])
def test_cada_salida_mostrada_se_acciona(prueba_salidas, nombre, valor):
    client, ctx = prueba_salidas
    momentanea = valor and nombre in io_names.SALIDAS_MOMENTANEAS
    cuerpo = {"value": valor, **({"momentanea": True} if momentanea else {})}
    resp = client.patch(f"/io/test/output/{nombre}", json=cuerpo)
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == nombre


# ── Paso 4: primer usuario en una base nueva ────────────────────────────────

def test_base_nueva_ingeniero_semilla_cambia_clave_crea_tecnico_y_entra_a_modo_prueba(tmp_path):
    """Recorrido del primer ingreso: ingeniero/ingeniero1234 (semilla) exige
    cambiar la clave; con la clave nueva crea un técnico; el técnico cambia la
    suya y puede entrar al modo prueba de E/S."""
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "nueva.db")
    ctx.sin_base_de_datos = False
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    ctx.control_loop.enter_test_mode.return_value = (True, "")
    ctx.control_loop.test_mode_active = False
    srv, _ = cargar_servidor(ctx)
    c = TestClient(srv.app)

    r = c.post("/auth/login", json={"usuario": "ingeniero", "clave": "ingeniero1234"})
    assert r.status_code == 200, r.text
    assert r.json()["debe_cambiar_clave"] is True
    cab = {"Authorization": f"Bearer {r.json()['token']}"}
    # con la clave pendiente no puede entrar al modo prueba
    assert c.post("/io/test/enter", headers=cab).status_code in (401, 403, 409)
    r = c.post("/auth/change_password", headers=cab,
               json={"clave_actual": "ingeniero1234", "clave_nueva": "Ingeniero2026",
                     "confirmacion": "Ingeniero2026"})
    assert r.status_code == 200, r.text

    r = c.post("/auth/login", json={"usuario": "ingeniero", "clave": "Ingeniero2026"})
    assert r.status_code == 200 and r.json()["debe_cambiar_clave"] is False
    cab = {"Authorization": f"Bearer {r.json()['token']}"}
    r = c.post("/usuarios", headers=cab,
               json={"nombre": "Cristian", "usuario": "cristian", "clave": "Temporal2026",
                     "confirmacion": "Temporal2026", "rol": "tecnico"})
    assert r.status_code == 200, r.text

    r = c.post("/auth/login", json={"usuario": "cristian", "clave": "Temporal2026"})
    assert r.status_code == 200, r.text
    cab_t = {"Authorization": f"Bearer {r.json()['token']}"}
    if r.json()["debe_cambiar_clave"]:
        assert c.post("/auth/change_password", headers=cab_t,
                      json={"clave_actual": "Temporal2026", "clave_nueva": "Cristian2026",
                            "confirmacion": "Cristian2026"}).status_code == 200
        r = c.post("/auth/login", json={"usuario": "cristian", "clave": "Cristian2026"})
        cab_t = {"Authorization": f"Bearer {r.json()['token']}"}
    assert c.post("/io/test/enter", headers=cab_t).status_code == 200


def test_apagar_windows_rechazado_queda_en_el_log(monkeypatch, caplog):
    """Paso 9: si Windows rechaza `shutdown` (política, permisos) el lazo ya
    se detuvo; al menos debe quedar el motivo en backend.log."""
    import subprocess
    import autoclave.backend.server as s
    llamadas = []

    def run(cmd, **kw):
        llamadas.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 1190, stdout="", stderr="Acceso denegado")

    monkeypatch.setattr(subprocess, "run", run)
    with caplog.at_level("ERROR"):
        s._apagar_windows()
    assert llamadas[0][0] == ["shutdown", "/s", "/t", "0"]
    assert any("1190" in r.getMessage() and "Acceso denegado" in r.getMessage()
               for r in caplog.records)


def test_aire_atmosferico_va_al_canal_fisico_de_la_errata(prueba_salidas):
    client, ctx = prueba_salidas
    assert client.patch("/io/test/output/aire_atmosferico_camara",
                        json={"value": True}).status_code == 200
    canal = EstadoAutoclave.map_do["aire_admosferico_camara"] + 1
    ctx.setdo.set_output.assert_called_once_with(canal, True)

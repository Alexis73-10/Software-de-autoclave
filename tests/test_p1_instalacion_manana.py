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
    # D8-3.19 (tanda 8): el aire atmosférico solo se abre con la cámara a
    # presión atmosférica
    ctx.estado.sensores_pres = {"pres_camara": 75.0}
    _atm = {"presion_atmosferica": 75.0, "rango_presion_atm": 5.0}
    ctx.config_manager.get.side_effect = lambda k, d=None: _atm.get(k, d)
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


# ── Paso 6: la pantalla de calibración pide cada sensor por el nombre de
# /io/channels (temp_referencia); el backend lo buscaba sin el alias (temp_ref)
# y respondía 404: la sonda de referencia no se podía calibrar desde la QML.

_CAL_YAML = """
calibration:
  user:
    temperature:
      - {gain: 1.0, offset: 0.0}
      - {gain: 1.0, offset: 0.0}
      - {gain: 1.0, offset: 0.0}
      - {gain: 1.0, offset: 0.0}
      - {gain: 1.0, offset: 0.0}
    pressure:
      - {gain: 1.0, offset: 0.0}
      - {gain: 1.0, offset: 0.0}
      - {gain: 1.0, offset: 0.0}
      - {gain: 1.0, offset: 0.0}
"""


@pytest.fixture
def calibracion(tmp_path):
    ruta = tmp_path / "calibration.yaml"
    ruta.write_text(_CAL_YAML, encoding="utf-8")
    ctx = MagicMock()
    ctx.db.get_auditoria.return_value = []
    ctx.sin_base_de_datos = False
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    srv, _ = cargar_servidor(ctx)
    srv.CALIBRATION_PATH = ruta
    return TestClient(srv.app, headers=cabecera(srv, "tecnico")), ctx, ruta


def _sensores_mostrados():
    return ([("temperature", s["name"]) for s in io_names.sensores("temperature")]
            + [("pressure", s["name"]) for s in io_names.sensores("pressure")])


def test_la_referencia_esta_entre_los_sensores_mostrados():
    assert ("temperature", "temp_referencia") in _sensores_mostrados()


@pytest.mark.parametrize("tipo,nombre", _sensores_mostrados())
def test_cada_sensor_mostrado_se_lee_para_calibrar(calibracion, tipo, nombre):
    client, _, _ = calibracion
    assert client.get(f"/calibration/{tipo}/{nombre}").status_code == 200


def test_calibrar_referencia_por_su_nombre_mostrado_escribe_su_canal(calibracion):
    client, ctx, ruta = calibracion
    r = client.patch("/calibration/temperature/temp_referencia",
                     json={"shown_low": 30.0, "real_low": 31.0,
                           "shown_high": 120.0, "real_high": 121.0})
    assert r.status_code == 200, r.text
    from autoclave.config import load_config
    temps = load_config(ruta).calibration.user.temperature
    canal = EstadoAutoclave.map_temp["temp_ref"]
    assert temps[canal].offset == pytest.approx(1.0)
    assert all(t.offset == 0.0 for i, t in enumerate(temps) if i != canal)
    # la auditoría usa el nombre canónico: el historial es uno solo
    assert ctx.db.registrar_auditoria.call_args.kwargs["entidad"] == "temperature/temp_ref"
    r = client.post("/calibration/temperature/temp_referencia/restaurar",
                    json={"destino": "defecto"})
    assert r.status_code == 200, r.text


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

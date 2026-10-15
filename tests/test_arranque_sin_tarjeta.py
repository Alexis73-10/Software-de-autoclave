# tests/test_arranque_sin_tarjeta.py
#
# Seguridad de la etapa 7 del arranque sin tarjeta (fase B, D-E): con el serial
# sin respuesta (E/S no verificadas) POST /cycle/start se rechaza y no se manda
# ninguna salida digital encendida; al conectarse la tarjeta, el arranque
# retoma desde la etapa 7 sin reiniciar el backend.
#
# Integración real: BackendContext, secuencia de arranque, ControlLoop, máquina
# de estados, puertas, configuración y ciclos del repo. Solo se sustituyen el
# perfil (no hay installation_profile.json en el repo), la BD (SQLite en
# tmp_path), la impresora y el enlace serial (registra cada comando).

import threading
import time
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.backend import context as ctx_mod
from autoclave.backend.arranque.secuencia import ejecutar_arranque
from autoclave.backend.context import BackendContext
from autoclave.devices.puertas.door_type import DoorType
from autoclave.installation.equipment import EquipmentClass
from autoclave.installation.profile import InstallationProfile, Role
from autoclave.protocols.serial_link import SerialLink
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.sensor_calibration_audit import SensorCalibrationAuditDB
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.backend_doble import cargar_servidor
from tests.alarmas_helpers import ids_viejos_activados, ids_viejos_activos, ids_viejos_resueltos


class _EnlaceSinTarjeta(SerialLink):
    """SerialLink real sin abrir puerto: no conecta hasta `conectada = True`
    y registra todo lo que se le ordena."""
    def __init__(self, units):
        super().__init__(on_update=units.update_from_serial)
        self.conectada = False
        self.salidas = []          # (canal, estado) de cada set_output
        self.all_off_llamadas = 0

    def start(self):
        pass

    def stop(self):
        pass

    def is_connected(self) -> bool:
        return self.conectada

    def edad_ultima_di(self, now=None):
        return None

    def set_output(self, channel, state) -> bool:
        self.salidas.append((channel, state))
        return False

    def all_off(self, timeout=1.0) -> bool:
        self.all_off_llamadas += 1
        return False


def _perfil():
    return InstallationProfile(
        machine_id="TEST-001", model_id="MX-TEST", serial_number="ACV-TEST",
        equipment_class=EquipmentClass.PISO, door_count=2, door_type=DoorType.ADVANCED,
        cooling_level=0, door_id=1, role=Role.OPERATOR_FRONT,
        created_at=datetime(2026, 1, 1), locked=False,
    )


def _esperar(condicion, max_s=10.0):
    fin = time.monotonic() + max_s
    while time.monotonic() < fin:
        if condicion():
            return True
        time.sleep(0.02)
    return condicion()


def _etapa(reg, clave):
    return next(e for e in reg.instantanea()["etapas"] if e["clave"] == clave)


@pytest.fixture
def backend(monkeypatch, tmp_path):
    enlaces = []

    def build_serial(units, al_conectar=None):
        enlaces.append(_EnlaceSinTarjeta(units))
        return enlaces[-1]

    monkeypatch.setattr(ctx_mod, "get_installation_profile", _perfil)
    monkeypatch.setattr(ctx_mod, "build_serial", build_serial)
    monkeypatch.setattr(ctx_mod, "DbManager", lambda: DbManager(tmp_path / "autoclave.db"))
    monkeypatch.setattr(ctx_mod, "SensorCalibrationAuditDB",
                        lambda: SensorCalibrationAuditDB(tmp_path / "calibracion.db"))
    monkeypatch.setattr(ctx_mod, "RealtimePrinter", MagicMock)

    ctx = BackendContext()
    srv, _ = cargar_servidor(ctx)
    srv.preparar_arranque()
    hilo = threading.Thread(
        target=ejecutar_arranque, args=(ctx, srv.registro_arranque),
        kwargs={"al_cancelar_prueba": srv._prueba_cancelada_por_paro,
                "al_operable": srv._contexto_operable.set,
                "detener": srv._detener_arranque,
                "plazo_es_s": 0.3, "pausa_es_s": 0.05},
        daemon=True)
    hilo.start()
    yield srv, ctx, enlaces, hilo, TestClient(srv.app)
    srv._detener_arranque.set()
    if ctx.control_loop is not None:
        ctx.control_loop.stop()
    hilo.join(2)


def test_sin_tarjeta_no_se_inicia_ciclo_ni_se_enciende_ninguna_salida(backend):
    srv, ctx, enlaces, _, client = backend
    reg = srv.registro_arranque

    # la etapa 7 se queda reintentando con ARR_SIN_ES, sin fallo bloqueante
    assert _esperar(lambda: _etapa(reg, "conectando_modulos_es")["codigo"] == "ARR_SIN_ES")
    assert _etapa(reg, "conectando_modulos_es")["estado"] == "en_curso"
    assert _etapa(reg, "verificando_sensores")["estado"] == "pendiente"
    assert reg.fallo_bloqueante is False
    # contexto operable: la UI puede leer el estado y mostrar la alarma (D-E)
    assert srv._contexto_operable.is_set()
    status = client.get("/status")
    assert status.status_code == 200
    assert status.json()["card_connected"] is False

    time.sleep(0.5)   # el ControlLoop corre varios ticks sin enlace
    r = client.post("/cycle/start")
    assert r.status_code == 409
    assert not ctx.estado.get_flag("START_CICLO")
    assert not ctx.estado.get_flag("LISTO_PARA_CICLO")
    assert ctx.estado.get_machine_state() != GlobalState.CICLO

    # alarma de la pantalla de espera (D-E) y paro publicado: sin datos = paro (A-3)
    # COM-01 (antes NO_HAY_CONEXION): sin conexión nunca establecida aparece
    # al agotar la tolerancia de 5 s (alarmas Parte A, a2dcbc7)
    assert _esperar(lambda: "NO_HAY_CONEXION" in ids_viejos_activos(ctx.alarm_manager), 8.0)
    assert ctx.estado.get_flag("PARO_EMERGENCIA") is True

    [enlace] = enlaces
    assert [s for s in enlace.salidas if s[1]] == []   # ninguna salida encendida


def test_al_conectar_la_tarjeta_el_arranque_retoma_sin_reiniciar(backend):
    srv, ctx, enlaces, hilo, client = backend
    reg = srv.registro_arranque
    assert _esperar(lambda: _etapa(reg, "conectando_modulos_es")["codigo"] == "ARR_SIN_ES")
    loop, hilo_loop = ctx.control_loop, ctx.control_loop.thread

    enlaces[0].conectada = True
    assert _esperar(lambda: reg.terminado)
    assert _etapa(reg, "conectando_modulos_es") == {
        "clave": "conectando_modulos_es", "estado": "ok", "codigo": None, "peso": 2.0}
    assert _etapa(reg, "verificando_sensores")["estado"] == "ok"
    # mismo backend: el mismo ControlLoop y su hilo, sin reconstruir nada
    assert len(enlaces) == 1
    assert ctx.control_loop is loop and ctx.control_loop.thread is hilo_loop
    assert hilo_loop.is_alive()
    hilo.join(2)
    assert not hilo.is_alive()                 # la secuencia terminó, no se relanzó
    assert client.get("/arranque").json()["terminado"] is True

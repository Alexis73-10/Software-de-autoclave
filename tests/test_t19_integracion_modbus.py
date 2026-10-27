# Tanda 19, I.2: integración del backend completo con `enlace: modbus` contra
# el simulador M31 (127.0.0.1, puerto libre): arranque, conexión verificada,
# lectura de temperatura y presión, una orden de salida, pérdida y reconexión.
#
# Real: BackendContext, secuencia de arranque, build_enlace → ModbusLink,
# Units con calibration_modbus.yaml, ControlLoop, máquina de estados y rutas.
# Se sustituyen solo el perfil, las BD (tmp_path), la impresora y la
# configuración del enlace (apunta al simulador, con tiempos cortos).

import threading
import time
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.backend import context as ctx_mod
from autoclave.backend.arranque.secuencia import ejecutar_arranque
from autoclave.backend.context import BackendContext
from autoclave.config import enlace_io
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.puertas.door_type import DoorType
from autoclave.installation.equipment import EquipmentClass
from autoclave.installation.profile import InstallationProfile, Role
from autoclave.protocols import modbus_link
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.sensor_calibration_audit import SensorCalibrationAuditDB
from tests.helpers.backend_doble import cargar_servidor
from tests.helpers.m31_simulado import M31Simulado, config_para, esperar


def _perfil():
    return InstallationProfile(
        machine_id="TEST-001", model_id="MX-TEST", serial_number="ACV-TEST",
        equipment_class=EquipmentClass.MESA_N, door_count=1, door_type=DoorType.SIMPLE,
        cooling_level=0, door_id=1, role=Role.OPERATOR_FRONT,
        created_at=datetime(2026, 1, 1), locked=False,
    )


def _etapa(reg, clave):
    return next(e for e in reg.instantanea()["etapas"] if e["clave"] == clave)


@pytest.fixture
def planta(monkeypatch, tmp_path, enlace_modbus):
    sim = M31Simulado()
    sim.iniciar()
    # Paro de emergencia NC sin pulsar (DI de fábrica) y puerta cerrada
    sim.di[EstadoAutoclave.map_di["paro_emergencia"]] = True
    sim.temperaturas[0] = 1342          # 134,2 °C en la Principal (PT100 1)
    sim.corrientes[0] = 12000           # AI 09: 200 kPa abs (4–20 mA → 0–400)
    monkeypatch.setattr(modbus_link, "cargar_config", lambda *a, **k: config_para(sim))

    monkeypatch.setattr(ctx_mod, "get_installation_profile", _perfil)
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
                "plazo_es_s": 10.0, "pausa_es_s": 0.05},
        daemon=True)
    hilo.start()
    yield sim, srv, ctx, TestClient(srv.app)
    srv._detener_arranque.set()
    if ctx.control_loop is not None:
        ctx.control_loop.stop()
    hilo.join(3)
    if ctx.serial is not None:
        ctx.serial.stop()
    sim.detener()


@pytest.mark.req("MOD-01")
@pytest.mark.req("MOD-06")
def test_backend_completo_con_el_simulador_m31(planta):
    sim, srv, ctx, client = planta
    assert enlace_io.enlace_activo() == "modbus"

    # Arranque y conexión verificada
    assert esperar(lambda: _etapa(srv.registro_arranque, "conectando_modulos_es")["estado"] == "ok",
                   timeout=20)
    assert isinstance(ctx.serial, modbus_link.ModbusLink)
    from autoclave.utils.paths import calibration_path
    assert calibration_path().name == "calibration_modbus.yaml"
    assert esperar(lambda: client.get("/status").json()["card_connected"] is True, timeout=10)
    st = client.get("/status").json()
    assert st["enlace_io"] == "modbus"
    assert st["tarjeta"]["id"] == "A1B2C3D4E5F6"
    assert st["comunicacion"]["modulos"]["enlace"] == "modbus"

    # Lectura de temperatura (décimas → °C) y presión (µA → kPa abs)
    assert esperar(lambda: abs((ctx.estado.sensores_temp.get("temp_camara") or 0) - 134.2) < 0.3, timeout=10), \
        ctx.estado.sensores_temp
    assert esperar(lambda: abs((ctx.estado.sensores_pres.get("pres_camara") or 0) - 200.0) < 1.0, timeout=10), \
        ctx.estado.sensores_pres

    # Una orden de salida: DO 13 (libre de fábrica) llega a la bobina 12
    assert ctx.serial.set_output(13, True) is True
    assert esperar(lambda: sim.bobinas[12] is True, timeout=3)
    assert ctx.serial.set_output(13, False) is True
    assert esperar(lambda: sim.bobinas[12] is False, timeout=3)

    # Pérdida: el módulo deja de contestar → sin conexión
    sim.silencio = True
    assert esperar(lambda: client.get("/status").json()["card_connected"] is False, timeout=10)
    # Reconexión: vuelve a contestar → conexión verificada otra vez
    sim.silencio = False
    assert esperar(lambda: client.get("/status").json()["card_connected"] is True, timeout=15)
    assert esperar(lambda: abs((ctx.estado.sensores_temp.get("temp_camara") or 0) - 134.2) < 0.3, timeout=10)

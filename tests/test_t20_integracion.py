# Tanda 20, I.2: integración del backend completo (solo Modbus) contra el
# simulador M31 con la composición real de 5 esclavos (ADB-01/02): arranque,
# configuración de seguridad distinta → escritura, reinicio del módulo y
# relectura (ADB-04), lecturas, una salida, pérdida y reconexión; y el rol
# configurar-modulo contra el simulador (correcto, composición distinta,
# contraseña escrita y releída, sin escribir bobinas ni configuración).
#
# Real: BackendContext, secuencia de arranque, build_enlace → ModbusLink,
# Units con calibration_modbus.yaml, ControlLoop, máquina de estados y rutas.
# Se sustituyen el perfil, las BD (tmp_path), la impresora y la configuración
# del enlace (apunta al simulador, 127.0.0.1 y puerto libre, tiempos cortos).

import json
import threading
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.backend import context as ctx_mod
from autoclave.backend.arranque.secuencia import ejecutar_arranque
from autoclave.backend.context import BackendContext
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.devices.puertas.door_type import DoorType
from autoclave.estacion import configurar_modulo as cm
from autoclave.installation.equipment import EquipmentClass
from autoclave.installation.profile import InstallationProfile, Role
from autoclave.protocols import modbus_link
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.sensor_calibration_audit import SensorCalibrationAuditDB
from tests.helpers import m31_simulado as m31
from tests.helpers.backend_doble import cargar_servidor
from tests.helpers.m31_simulado import M31Simulado, config_para, esperar

MAC_BANCO = "005404849DB1"


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
def sim():
    s = M31Simulado()
    s.fijar_mac(MAC_BANCO)
    s.iniciar()
    yield s
    s.detener()


@pytest.fixture
def planta(monkeypatch, tmp_path, sim):
    sim.di[EstadoAutoclave.map_di["paro_emergencia"]] = True   # paro NC sin pulsar
    sim.temperaturas[0] = 1342          # 134,2 °C en la Principal (PT100 1)
    sim.corrientes[0] = 12000           # AI 09: 200 kPa abs
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
    yield srv, ctx, TestClient(srv.app)
    srv._detener_arranque.set()
    if ctx.control_loop is not None:
        ctx.control_loop.stop()
    hilo.join(3)
    if ctx.serial is not None:
        ctx.serial.stop()


@pytest.mark.req("T20-02")
@pytest.mark.req("ADB-04")
def test_backend_completo_composicion_real_y_reinicio_del_modulo(planta, sim):
    srv, ctx, client = planta
    # El simulador arranca con la configuración de fábrica: distinta de la de
    # seguridad → el software la escribe, reinicia el módulo y la relee.
    assert esperar(lambda: _etapa(srv.registro_arranque, "conectando_modulos_es")["estado"] == "ok",
                   timeout=25)
    assert esperar(lambda: client.get("/status").json()["card_connected"] is True, timeout=10)
    assert sim.reinicios == 1
    assert sim.holding[m31.TIEMPO_DESCONEXION] == 5 and sim.holding[m31.MODO_FALLA] == 1
    assert all(sim.holding[m31.DO_FALLA + i] == 1 for i in range(32))
    assert not any(d == m31.BANDERA_FALLA for _, d, _v in sim.escrituras)   # ADB-05

    st = client.get("/status").json()
    assert st["enlace_io"] == "modbus"
    assert st["tarjeta"]["id"] == MAC_BANCO                                    # ADB-03
    assert st["tarjeta"]["version"] == "9232-0-13 / 10,12,12,12,10"            # ADB-02
    assert st["comunicacion"]["modulos"]["enlace"] == "modbus"

    assert esperar(lambda: abs((ctx.estado.sensores_temp.get("temp_camara") or 0) - 134.2) < 0.3,
                   timeout=10)
    assert esperar(lambda: abs((ctx.estado.sensores_pres.get("pres_camara") or 0) - 200.0) < 1.0,
                   timeout=10)

    assert ctx.serial.set_output(13, True) is True
    assert esperar(lambda: sim.bobinas[12] is True, timeout=3)
    assert ctx.serial.set_output(13, False) is True
    assert esperar(lambda: sim.bobinas[12] is False, timeout=3)

    # Pérdida y reconexión: la configuración ya coincide → sin otro reinicio.
    sim.silencio = True
    assert esperar(lambda: client.get("/status").json()["card_connected"] is False, timeout=10)
    sim.silencio = False
    assert esperar(lambda: client.get("/status").json()["card_connected"] is True, timeout=15)
    assert sim.reinicios == 1


@pytest.fixture
def rol(monkeypatch, tmp_path, sim):
    monkeypatch.setattr(cm, "backend_escuchando", lambda: False)
    monkeypatch.setattr(cm, "PRESUPUESTO_S", 5.0)
    salida = tmp_path / "resultado.json"

    def correr(*extra):
        codigo = cm.main(["--ip", "127.0.0.1", "--puerto", str(sim.puerto),
                          "--resultado", str(salida), *extra])
        return codigo, json.loads(salida.read_text(encoding="ascii"))
    return correr


@pytest.mark.req("T20-04")
def test_rol_contra_el_simulador_sin_escribir_bobinas_ni_configuracion(rol, sim, tmp_path):
    archivo = tmp_path / "clave.txt"
    archivo.write_text("Pr1eba", encoding="ascii")          # contraseña ficticia
    codigo, res = rol("--clave-archivo", str(archivo))
    assert codigo == 0 and res["ok"] is True and res["codigo"] == "ok"
    assert res["n_modulos"] == 5 and res["mac"] == MAC_BANCO and res["clave_cambiada"] is True
    assert not archivo.exists()
    assert sim.credenciales_web() == ("admin", "Pr1eba")
    assert sim.escrituras_bobinas() == []
    assert sim.reinicios == 0
    assert {d for _, d, _v in sim.escrituras} <= {0x758B, 0x7590}

    sim.fijar_modelos(m31.MODELO_PRINCIPAL_DEFECTO,
                      ["M31-GXAXX0A00-U", "M31-GAXXXA000-U", "M31-GXXAX00A0-U", "M31-GXDXX0600-U",
                       "M31-GXXAX00A0-U"])
    codigo, res = rol()
    assert codigo == 4 and res["ok"] is False and res["codigo"] == "composicion"
    assert sim.escrituras_bobinas() == []

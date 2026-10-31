# tests/test_t19_s2_calibracion.py
#
# Tanda 19 (MOD-04): archivo de calibración del enlace de E/S
# (calibration_modbus.yaml; tanda 20, T20-03: la calibración serial
# calibration.yaml y su plantilla neutra se retiraron), en desarrollo y en el
# compilado (copia en data/), el escritor de calibración, el respaldo y el
# verificador de la entrega neutra.

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from autoclave.config import load_config
from autoclave.utils import paths
from tests.test_p1_rutas_build_congelado import _bundle, _correr

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "src" / "autoclave" / "config"
CAL_MODBUS = CONFIG / "calibration_modbus.yaml"
VERIFICADOR = RAIZ / "tools" / "verificar_calibracion_neutra.py"


# ── ruta según el enlace ───────────────────────────────────────────────────

@pytest.mark.req("MOD-04")
def test_calibration_path_en_desarrollo_segun_el_enlace():
    # T20-03: solo el caso Modbus (el serial se retiró)
    assert paths.calibration_path() == CAL_MODBUS


@pytest.mark.req("MOD-04")
def test_nombre_calibracion():
    # T20-03: nombre_calibracion(enlace) se retiró con la selección de enlace
    assert paths.CALIBRACION_MODBUS == "calibration_modbus.yaml"


@pytest.mark.req("MOD-04")
def test_calibration_path_de_dependencias_en_pruebas_es_la_modbus():
    """T20-03: antes conftest fijaba "serial" y CALIBRATION_PATH quedaba en
    calibration.yaml; con el enlace único es la de Modbus."""
    from autoclave.backend import dependencias
    assert Path(dependencias.CALIBRATION_PATH).name == "calibration_modbus.yaml"


@pytest.mark.req("MOD-04")
def test_compilado_modbus_siembra_su_propia_copia_en_data(tmp_path):
    exe = tmp_path / "USB" / "Autoclave" / "Autoclave.exe"
    meipass = _bundle(tmp_path, "meipass")
    r = _correr(tmp_path, meipass, exe, "marcar")
    copia = exe.parent / "data" / "calibration_modbus.yaml"
    assert Path(r["calibracion"]) == copia
    assert r["marca"]
    # la copia salió de la empaquetada del enlace Modbus
    assert load_config(copia).calibration.factory.pressure[0].adc_min == 4000
    # la del serial (retirada, T20-03) no se crea
    assert not (exe.parent / "data" / "calibration.yaml").exists()
    # reinicio con Modbus: se conserva lo guardado
    assert _correr(tmp_path, meipass, exe)["marca"]
    # (el caso «el serial tiene su propia copia» se borró: T20-03)


@pytest.mark.req("MOD-04")
def test_compilado_modbus_instalado_en_programdata(tmp_path):
    exe = tmp_path / "PF" / "Especifika" / "Autoclave" / "Autoclave.exe"
    datos = tmp_path / "PD" / "Especifika" / "Autoclave"
    r = _correr(tmp_path, _bundle(tmp_path, "meipass"), exe)
    assert Path(r["calibracion"]) == datos / "data" / "calibration_modbus.yaml"
    assert not (exe.parent / "data").exists()


# ── escritor ───────────────────────────────────────────────────────────────

@pytest.mark.req("MOD-04")
def test_escritor_escribe_en_el_archivo_modbus_que_se_le_pasa(tmp_path):
    from autoclave.config.calibration_writer import write_user_calibration
    copia = tmp_path / "calibration_modbus.yaml"
    shutil.copyfile(CAL_MODBUS, copia)
    write_user_calibration(copia, "pressure", 0, 1.01, -0.5, 100.0, 100.5, 300.0, 302.5)
    cfg = load_config(copia)
    assert cfg.calibration.user.pressure[0].gain == 1.01
    assert cfg.calibration.user.pressure[0].offset == -0.5
    # la fábrica (escala y piso de señal) queda intacta
    assert cfg.calibration.factory.pressure[0].adc_piso_senal == 3850
    assert cfg.calibration.factory == load_config(CAL_MODBUS).calibration.factory
    assert CAL_MODBUS.read_bytes() != copia.read_bytes()


# ── respaldo ───────────────────────────────────────────────────────────────

EQUIPO = {"serie": "ACV-2026-001", "modelo": "M-1"}


@pytest.fixture
def api_respaldo(tmp_path, monkeypatch):
    """Backend con la calibración Modbus activa (copia en tmp)."""
    from fastapi.testclient import TestClient
    from autoclave.core.managers.config_manager import ConfigManager
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.helpers.backend_doble import (cabecera, cargar_servidor, modulo_backend,
                                             parchear_en_backend)
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    c = ConfigManager(); c.load_config(); c.vincular_bd(ctx.db)
    ctx.config_manager = c
    ctx.sin_base_de_datos = False
    perfil = MagicMock(); perfil.serial_number = EQUIPO["serie"]; perfil.model_id = EQUIPO["modelo"]
    ctx.profile = perfil
    programas = tmp_path / "user"; programas.mkdir()
    ctx.cycle_manager.carpeta.return_value = str(programas)
    usb = tmp_path / "usb"; usb.mkdir()
    calib = tmp_path / "calibration_modbus.yaml"
    shutil.copyfile(CAL_MODBUS, calib)
    srv, _ = cargar_servidor(ctx)
    parchear_en_backend(monkeypatch, "CALIBRATION_PATH", calib)
    monkeypatch.setattr(modulo_backend("rutas.respaldo"), "_unidades_usb",
                        lambda: [{"ruta": str(usb), "libre_bytes": 8e9}])
    monkeypatch.setattr(modulo_backend("rutas.respaldo"), "_version_sw", lambda: "1.2.0")
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    yield TestClient(srv.app), srv, ctx, cabecera, usb, calib
    ctx.db.close()


def _zip(usb, contenido):
    from datetime import datetime
    from autoclave.core.runtime import respaldo as rp
    datos = rp.crear(EQUIPO, {"perfil_calibracion": True}, contenido, "tec", "1.2.0")
    carpeta = usb / rp.CARPETA
    carpeta.mkdir(exist_ok=True)
    ruta = carpeta / rp.nombre_archivo(EQUIPO["serie"], datetime(2026, 10, 27))
    ruta.write_bytes(datos)
    return ruta


# Calibración de un equipo con el enlace serial retirado (T20-03): escala de
# fábrica en cuentas del ADC de 12 bits y usuario neutro (pasaría la
# plausibilidad). Antes se leía de config/plantillas/calibration_neutra.yaml.
_CAL_SERIAL_EN_LINEA = yaml.safe_dump({"calibration": {
    "factory": {
        "temperature": [{"adc_min": 0, "adc_max": 4095, "temp_min": 0, "temp_max": 200,
                         "gain": 1.0, "offset": 0.0}] * 8,
        "pressure": [{"adc_min": 819, "adc_max": 3276, "pres_min": 0, "pres_max": 400,
                      "gain": 1.0, "offset": 0.0}] * 8},
    "user": {"temperature": [{"gain": 1.0, "offset": 0.0}] * 8,
             "pressure": [{"gain": 1.0, "offset": 0.0}] * 8}}}).encode("utf-8")


@pytest.mark.req("MOD-04")
def test_respaldo_de_otro_enlace_se_rechaza(api_respaldo):
    """Una calibración del serial (cuentas del ADC) pisaría la escala de
    fábrica en µA de la de Modbus: se rechaza sin escribir nada."""
    cliente, srv, ctx, cab, usb, calib = api_respaldo
    # la serial con la calibración de usuario neutra (pasaría la plausibilidad)
    ruta = _zip(usb, {"calibracion.yaml": _CAL_SERIAL_EN_LINEA})
    antes = calib.read_bytes()
    r = cliente.post("/backup/restore", json={"unidad": str(usb), "archivo": ruta.name,
                                              "confirmar": True}, headers=cab(srv, "ingeniero"))
    assert r.status_code == 422 and r.json()["codigo"] == "calibracion_otro_enlace"
    assert calib.read_bytes() == antes
    filas = ctx.db.get_auditoria(evento="respaldo_rechazado")
    assert filas


@pytest.mark.req("MOD-04")
def test_respaldo_del_mismo_enlace_se_restaura(api_respaldo):
    cliente, srv, ctx, cab, usb, calib = api_respaldo
    texto = CAL_MODBUS.read_text(encoding="utf-8") + "\n# MARCA-RESPALDO\n"
    ruta = _zip(usb, {"calibracion.yaml": texto.encode("utf-8")})
    r = cliente.post("/backup/restore", json={"unidad": str(usb), "archivo": ruta.name,
                                              "confirmar": True}, headers=cab(srv, "ingeniero"))
    assert r.status_code == 200, r.text
    assert "MARCA-RESPALDO" in calib.read_text(encoding="utf-8")


# ── verificador de la entrega neutra ───────────────────────────────────────

def _dist(tmp_path, modbus: bytes | None):
    destino = tmp_path / "Autoclave" / "_internal" / "autoclave" / "config"
    destino.mkdir(parents=True)
    # T20-03: la compilación ya no lleva calibration.yaml (plantilla serial)
    if modbus is not None:
        (destino / "calibration_modbus.yaml").write_bytes(modbus)
    return tmp_path / "Autoclave"


def _verificar(dist):
    return subprocess.run([sys.executable, str(VERIFICADOR), str(dist)],
                          capture_output=True, text=True)


@pytest.mark.req("MOD-04")
def test_verificador_acepta_la_calibracion_modbus_del_repo(tmp_path):
    r = _verificar(_dist(tmp_path, CAL_MODBUS.read_bytes()))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Modbus" in r.stdout


@pytest.mark.req("MOD-04")
def test_verificador_rechaza_usuario_modbus_no_neutro(tmp_path):
    datos = yaml.safe_load(CAL_MODBUS.read_text(encoding="utf-8"))
    datos["calibration"]["user"]["pressure"][0] = {"gain": 1.3, "offset": -70.0}
    r = _verificar(_dist(tmp_path, yaml.safe_dump(datos).encode("utf-8")))
    assert r.returncode == 1 and "pressure[0]" in r.stdout


@pytest.mark.req("MOD-04")
def test_verificador_sin_calibracion_modbus_falla(tmp_path):
    """Revisión R (V19-s2-01): el enlace empaquetado es Modbus; sin
    calibration_modbus.yaml la entrega no se publica (antes solo avisaba y
    esta prueba se llamaba ..._solo_avisa con salida 0)."""
    r = _verificar(_dist(tmp_path, None))
    assert r.returncode == 1 and "FALLA" in r.stdout

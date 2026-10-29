# tests/test_t23_ain_calibracion.py
#
# Tanda 23 (AIN-04): calibración de presión con 16 entradas. Una copia de
# data/ o un respaldo con 8 entradas de presión se completa al cargar con las
# nominales para los canales 8-15 sin tocar los canales 0-7; calibrar AI 09-16
# completa el archivo; un respaldo Modbus de 8 entradas se acepta.

import logging
from pathlib import Path

import pytest
import yaml

from autoclave.config import load_config
from autoclave.config.calibration_writer import write_user_calibration
from autoclave.config.completar_presion import (FABRICA_PRESION_NOMINAL, USUARIO_PRESION_NOMINAL,
                                                completar_presion)
from autoclave.core.runtime import asignacion_io as aio
from autoclave.utils.resources import resource_path
from tests.test_r8_reasignacion_api import api, respaldo  # noqa: F401  (fixtures)

CALIBRACION = Path(resource_path("autoclave/config/calibration_modbus.yaml"))


@pytest.fixture(autouse=True)
def _mapas_de_fabrica():
    aio.restablecer_memoria_fabrica_codigo()
    yield
    aio.restablecer_memoria_fabrica_codigo()


def _calibracion_de_8(ruta: Path) -> dict:
    """Copia del archivo de la compilación recortada a 8 entradas de presión
    (como una copia de data/ de antes de la tanda 23), con los canales 0-7
    distintos de la nominal para comprobar que no se tocan."""
    datos = yaml.safe_load(CALIBRACION.read_text(encoding="utf-8"))
    cal = datos["calibration"]
    cal["factory"]["pressure"] = cal["factory"]["pressure"][:8]
    cal["user"]["pressure"] = [{"gain": 1.0 + i / 100, "offset": float(i)} for i in range(8)]
    cal["factory"]["pressure"][3]["adc_piso_senal"] = 3800      # distinto a propósito
    ruta.write_text(yaml.safe_dump(datos, sort_keys=False), encoding="utf-8")
    return datos


def test_el_archivo_de_la_compilacion_trae_16():
    datos = yaml.safe_load(CALIBRACION.read_text(encoding="utf-8"))
    cal = datos["calibration"]
    assert len(cal["factory"]["pressure"]) == 16 and len(cal["user"]["pressure"]) == 16
    assert len(cal["factory"]["temperature"]) == 8 and len(cal["user"]["temperature"]) == 8
    assert all(c == FABRICA_PRESION_NOMINAL for c in cal["factory"]["pressure"])
    assert all(c == USUARIO_PRESION_NOMINAL for c in cal["user"]["pressure"])


@pytest.mark.req("AIN-04")
def test_ocho_entradas_se_completan_a_16_sin_tocar_0_a_7(tmp_path, caplog):
    ruta = tmp_path / "calibration_modbus.yaml"
    original = _calibracion_de_8(ruta)
    with caplog.at_level(logging.WARNING, logger="autoclave.config.completar_presion"):
        cfg = load_config(ruta)
    assert "AIN-04" in caplog.text
    fab, usr = cfg.calibration.factory.pressure, cfg.calibration.user.pressure
    assert len(fab) == 16 and len(usr) == 16
    for i in range(8):
        orig_f = original["calibration"]["factory"]["pressure"][i]
        assert fab[i].model_dump(exclude_unset=True) == orig_f
        assert (usr[i].gain, usr[i].offset) == (1.0 + i / 100, float(i))
    assert fab[3].adc_piso_senal == 3800
    for i in range(8, 16):
        assert (fab[i].adc_min, fab[i].adc_max, fab[i].pres_min, fab[i].pres_max,
                fab[i].adc_piso_senal) == (4000, 20000, 0, 400, 3850)
        assert (usr[i].gain, usr[i].offset) == (1.0, 0.0)
    # el archivo no se reescribe al cargar
    assert len(yaml.safe_load(ruta.read_text(encoding="utf-8"))["calibration"]["user"]["pressure"]) == 8


def test_otros_largos_no_se_tocan():
    for n in (0, 7, 9, 16):
        datos = {"calibration": {"factory": {"pressure": [{}] * n}, "user": {"pressure": [{}] * n}}}
        assert completar_presion(datos) is False
        assert len(datos["calibration"]["factory"]["pressure"]) == n
    assert completar_presion({}) is False and completar_presion({"calibration": None}) is False


def test_calibrar_ai_09_completa_el_archivo(tmp_path):
    ruta = tmp_path / "calibration_modbus.yaml"
    _calibracion_de_8(ruta)
    write_user_calibration(ruta, "pressure", 8, 1.05, -2.0, 100, 101, 300, 302)
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    usr = datos["calibration"]["user"]["pressure"]
    assert len(usr) == 16 and len(datos["calibration"]["factory"]["pressure"]) == 16
    assert usr[8] == {"gain": 1.05, "offset": -2.0}
    assert usr[0] == {"gain": 1.0, "offset": 0.0} and usr[7] == {"gain": 1.07, "offset": 7.0}


@pytest.mark.req("AIN-04")
def test_largos_de_calibracion_y_ai_09_16_asignables(api, tmp_path, monkeypatch):  # noqa: F811
    """Con la copia de data/ de 8 entradas, la validación de la reasignación
    ve 16 entradas de presión: AI 09-16 no dan puerto_sin_calibracion."""
    from tests.helpers.backend_doble import parchear_en_backend
    from autoclave.backend import server_reasignacion as sr
    ruta = tmp_path / "calibration_modbus.yaml"
    _calibracion_de_8(ruta)
    parchear_en_backend(monkeypatch, "CALIBRATION_PATH", ruta)
    largos = sr._largos_calibracion()
    assert largos == {"temperatura": 8, "presion": 16}
    nueva = aio.combinar(aio.fabrica_codigo(), {"pres_camara": 16})
    assert aio.puertos_sin_calibracion(nueva, largos) == []


@pytest.mark.req("AIN-04")
def test_respaldo_modbus_de_8_entradas_se_acepta(respaldo):  # noqa: F811
    from autoclave.core.runtime import respaldo as rp
    cliente, _srv, ctx, cab, usb = respaldo
    activa = usb.parent / "calibration.yaml"          # la del fixture (CALIBRATION_PATH)
    assert len(yaml.safe_load(activa.read_text(encoding="utf-8"))["calibration"]["factory"]["pressure"]) == 16
    recortado = usb.parent / "recortado.yaml"
    _calibracion_de_8(recortado)
    # misma fábrica que la activa en 0-7 (sin el cambio de prueba del canal 3)
    datos = yaml.safe_load(recortado.read_text(encoding="utf-8"))
    datos["calibration"]["factory"]["pressure"][3]["adc_piso_senal"] = 3850
    datos["calibration"]["user"]["pressure"] = [{"gain": 1.0, "offset": 0.0}] * 8
    contenido = {"perfil.json": b"{}",
                 "calibracion.yaml": yaml.safe_dump(datos, sort_keys=False).encode("utf-8")}
    zipb = rp.crear({"serie": "ACV-2026-001", "modelo": "M-1"}, {"perfil_calibracion": True},
                    contenido, "ines", "1.2.0")
    carpeta = usb / rp.CARPETA
    carpeta.mkdir()
    (carpeta / "respaldo_ACV-2026-001_c8.zip").write_bytes(zipb)
    r = cliente.post("/backup/restore", json={"unidad": str(usb), "archivo": "respaldo_ACV-2026-001_c8.zip",
                                              "confirmar": True}, headers=cab())
    assert r.status_code == 200, r.text
    assert r.json()["calibracion"] is True
    cfg = load_config(activa)
    assert len(cfg.calibration.factory.pressure) == 16 and len(cfg.calibration.user.pressure) == 16
    # una fábrica distinta en 0-7 sigue rechazándose (calibracion_otro_enlace)
    datos["calibration"]["factory"]["pressure"][3]["adc_piso_senal"] = 3800
    contenido["calibracion.yaml"] = yaml.safe_dump(datos, sort_keys=False).encode("utf-8")
    (carpeta / "respaldo_ACV-2026-001_c9.zip").write_bytes(
        rp.crear({"serie": "ACV-2026-001", "modelo": "M-1"}, {"perfil_calibracion": True},
                 contenido, "ines", "1.2.0"))
    r = cliente.post("/backup/restore", json={"unidad": str(usb), "archivo": "respaldo_ACV-2026-001_c9.zip",
                                              "confirmar": True}, headers=cab())
    assert r.status_code == 422 and r.json()["codigo"] == "calibracion_otro_enlace"

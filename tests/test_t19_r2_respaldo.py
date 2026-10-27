# tests/test_t19_r2_respaldo.py
#
# Revisión R de la tanda 19 (V19-s2-02): al restaurar un respaldo, la
# calibración se rechaza (422 calibracion_otro_enlace) si CUALQUIER campo de la
# sección calibration.factory (temperatura o presión) difiere de la activa, no
# solo adc_min/adc_max de presión. En serial esto también rechaza un respaldo
# con otra fábrica del mismo enlace (falla cerrada).

import shutil

import pytest
import yaml

from tests.test_t19_s2_calibracion import (CAL_MODBUS, PLANTILLA,  # noqa: F401
                                           _zip, api_respaldo)


def _restaurar(cliente, srv, cab, usb, ruta):
    return cliente.post("/backup/restore", json={"unidad": str(usb), "archivo": ruta.name,
                                                 "confirmar": True},
                        headers=cab(srv, "ingeniero"))


def _con_cambio(base, tipo, canal, campo, valor):
    datos = yaml.safe_load(base.read_text(encoding="utf-8"))
    datos["calibration"]["factory"][tipo][canal][campo] = valor
    return yaml.safe_dump(datos, allow_unicode=True).encode("utf-8")


@pytest.mark.req("MOD-04")
@pytest.mark.parametrize("tipo,canal,campo,valor", [
    ("temperature", 0, "temp_max", 200),        # escala de temperatura
    ("temperature", 5, "adc_max", 4095),
    ("pressure", 3, "adc_piso_senal", 3600),    # misma adc_min/adc_max de presión
    ("pressure", 7, "pres_max", 500),
])
def test_modbus_rechaza_fabrica_distinta_en_cualquier_campo(api_respaldo, tipo, canal,
                                                             campo, valor):
    cliente, srv, ctx, cab, usb, calib = api_respaldo
    antes = calib.read_bytes()
    ruta = _zip(usb, {"calibracion.yaml": _con_cambio(CAL_MODBUS, tipo, canal, campo, valor)})
    r = _restaurar(cliente, srv, cab, usb, ruta)
    assert r.status_code == 422 and r.json()["codigo"] == "calibracion_otro_enlace"
    assert "fábrica" in r.text
    assert calib.read_bytes() == antes


@pytest.mark.req("MOD-04")
def test_serial_rechaza_otra_fabrica_del_mismo_enlace(api_respaldo, tmp_path, monkeypatch):
    """Con la calibración serial activa, un respaldo serial con otra fábrica
    (otra escala de una sonda de temperatura) se rechaza: falla cerrada."""
    from tests.helpers.backend_doble import parchear_en_backend
    cliente, srv, ctx, cab, usb, _ = api_respaldo
    activa = tmp_path / "calibration.yaml"
    shutil.copyfile(PLANTILLA, activa)
    parchear_en_backend(monkeypatch, "CALIBRATION_PATH", activa)
    antes = activa.read_bytes()
    ruta = _zip(usb, {"calibracion.yaml": _con_cambio(PLANTILLA, "temperature", 2,
                                                      "adc_max", 4000)})
    r = _restaurar(cliente, srv, cab, usb, ruta)
    assert r.status_code == 422 and r.json()["codigo"] == "calibracion_otro_enlace"
    assert activa.read_bytes() == antes


@pytest.mark.req("MOD-04")
def test_serial_misma_fabrica_se_restaura(api_respaldo, tmp_path, monkeypatch):
    from tests.helpers.backend_doble import parchear_en_backend
    cliente, srv, ctx, cab, usb, _ = api_respaldo
    activa = tmp_path / "calibration.yaml"
    shutil.copyfile(PLANTILLA, activa)
    parchear_en_backend(monkeypatch, "CALIBRATION_PATH", activa)
    texto = PLANTILLA.read_text(encoding="utf-8") + "\n# MARCA-R2\n"
    ruta = _zip(usb, {"calibracion.yaml": texto.encode("utf-8")})
    r = _restaurar(cliente, srv, cab, usb, ruta)
    assert r.status_code == 200, r.text
    assert "MARCA-R2" in activa.read_text(encoding="utf-8")

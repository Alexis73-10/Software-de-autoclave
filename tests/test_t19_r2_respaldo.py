# tests/test_t19_r2_respaldo.py
#
# Revisión R de la tanda 19 (V19-s2-02): al restaurar un respaldo, la
# calibración se rechaza (422 calibracion_otro_enlace) si CUALQUIER campo de la
# sección calibration.factory (temperatura o presión) difiere de la activa, no
# solo adc_min/adc_max de presión. (Los casos con la calibración serial activa
# se borraron: enlace retirado en la tanda 20, T20-03.)

import pytest
import yaml

from tests.test_t19_s2_calibracion import (CAL_MODBUS,  # noqa: F401
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

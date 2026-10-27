# tests/test_t19_r2_verificador.py
#
# Revisión R de la tanda 19 (V19-s2-01): tools/verificar_calibracion_neutra.py
# FALLA (salida 1) si el compilado no trae calibration_modbus.yaml y compara su
# sección de fábrica contra los valores nominales de MOD-04, además de exigir
# la calibración de usuario neutra.

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "src" / "autoclave" / "config"
CAL_MODBUS = CONFIG / "calibration_modbus.yaml"
PLANTILLA = CONFIG / "plantillas" / "calibration_neutra.yaml"
VERIFICADOR = RAIZ / "tools" / "verificar_calibracion_neutra.py"


def _dist(tmp_path, modbus):
    destino = tmp_path / "Autoclave" / "_internal" / "autoclave" / "config"
    destino.mkdir(parents=True)
    (destino / "calibration.yaml").write_bytes(PLANTILLA.read_bytes())
    if modbus is not None:
        (destino / "calibration_modbus.yaml").write_bytes(modbus)
    return tmp_path / "Autoclave"


def _verificar(dist):
    return subprocess.run([sys.executable, str(VERIFICADOR), str(dist)],
                          capture_output=True, text=True, encoding="utf-8")


def _modbus_con(tipo, canal, cambio):
    datos = yaml.safe_load(CAL_MODBUS.read_text(encoding="utf-8"))
    c = datos["calibration"]["factory"][tipo][canal]
    for clave, valor in cambio.items():
        if valor is _QUITAR:
            c.pop(clave)
        else:
            c[clave] = valor
    return yaml.safe_dump(datos, allow_unicode=True).encode("utf-8")


_QUITAR = object()


@pytest.mark.req("MOD-04")
def test_falla_si_falta_la_calibracion_modbus(tmp_path):
    r = _verificar(_dist(tmp_path, None))
    assert r.returncode == 1
    assert "FALLA" in r.stdout and "calibration_modbus.yaml" in r.stdout


@pytest.mark.req("MOD-04")
def test_acepta_la_del_repositorio(tmp_path):
    r = _verificar(_dist(tmp_path, CAL_MODBUS.read_bytes()))
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.req("MOD-04")
@pytest.mark.parametrize("tipo,canal,cambio", [
    ("temperature", 0, {"adc_max": 4095}),
    ("temperature", 7, {"temp_max": 200}),
    ("temperature", 6, {"temp_min": -10}),
    ("temperature", 3, {"adc_min": 1}),
    ("temperature", 2, {"gain": 1.1}),
    ("pressure", 0, {"adc_min": 4100}),
    ("pressure", 7, {"adc_max": 21000}),
    ("pressure", 4, {"pres_max": 500}),
    ("pressure", 5, {"pres_min": -5}),
    ("pressure", 1, {"adc_piso_senal": 3600}),
    ("pressure", 2, {"adc_piso_senal": _QUITAR}),
    ("pressure", 3, {"adc_falla_bajo": 3500}),
    ("pressure", 3, {"adc_falla_alto": None}),
    ("pressure", 6, {"margen_falla_bajo": 0.05}),
    ("pressure", 6, {"margen_falla_alto": 0.1}),
    ("pressure", 0, {"offset": 2.0}),
    ("pressure", 0, {"poly": [0.0, 1.0]}),
    ("temperature", 1, {"campo_raro": 1}),
])
def test_rechaza_fabrica_no_nominal(tmp_path, tipo, canal, cambio):
    r = _verificar(_dist(tmp_path, _modbus_con(tipo, canal, cambio)))
    assert r.returncode == 1, r.stdout
    assert f"fábrica {tipo}[{canal}]" in r.stdout


@pytest.mark.req("MOD-04")
def test_acepta_margenes_escritos_con_su_valor_por_defecto(tmp_path):
    cambio = {"margen_falla_bajo": 0.025, "margen_falla_alto": 0.0625,
              "pres_falla_bajo_kpa": -10.0, "poly": None}
    r = _verificar(_dist(tmp_path, _modbus_con("pressure", 0, cambio)))
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.req("MOD-04")
def test_rechaza_menos_de_8_canales_de_fabrica(tmp_path):
    datos = yaml.safe_load(CAL_MODBUS.read_text(encoding="utf-8"))
    datos["calibration"]["factory"]["temperature"] = datos["calibration"]["factory"]["temperature"][:6]
    r = _verificar(_dist(tmp_path, yaml.safe_dump(datos).encode("utf-8")))
    assert r.returncode == 1 and "fábrica temperature" in r.stdout


@pytest.mark.req("MOD-04")
def test_sigue_exigiendo_usuario_neutro(tmp_path):
    datos = yaml.safe_load(CAL_MODBUS.read_text(encoding="utf-8"))
    datos["calibration"]["user"]["temperature"][4] = {"gain": 1.0, "offset": 0.5}
    r = _verificar(_dist(tmp_path, yaml.safe_dump(datos).encode("utf-8")))
    assert r.returncode == 1 and "usuario temperature[4]" in r.stdout

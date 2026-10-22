# tests/test_q1rev_params_ciclo_fabrica_migrada.py
"""Revisión Q1 (SEN-07b): la pantalla de parámetros de PySide pasa los
parámetros de fábrica por migrar_parametros(), para que un factory/*.json viejo
también muestre los dos rangos nuevos como referencia."""

import json

import pytest

pytest.importorskip("PySide6")


def test_load_factory_params_migra_el_rango_viejo(tmp_path):
    from autoclave.ui_pyside.views.params_ciclo.params_ciclo import _load_factory_params
    (tmp_path / "factory").mkdir()
    (tmp_path / "user").mkdir()
    viejo = {"parameters": {"calentamiento": {
        "rango_calentamiento": {"value": 3.0, "type": "float", "unit": "kPa",
                                "clase": "sin_conversion", "min": 0, "max": 30}}}}
    (tmp_path / "factory" / "p.json").write_text(json.dumps(viejo), encoding="utf-8")
    (tmp_path / "user" / "p.json").write_text(json.dumps(viejo), encoding="utf-8")

    cal = _load_factory_params(str(tmp_path / "user" / "p.json"))["calentamiento"]

    assert "rango_calentamiento" not in cal
    assert cal["rango_calentamiento_temp"]["value"] == 3.0
    assert cal["rango_calentamiento_temp"]["unit"] == "°C"
    assert cal["rango_calentamiento_pres"]["unit"] == "kPa"


def test_load_factory_params_sin_archivo_devuelve_vacio(tmp_path):
    from autoclave.ui_pyside.views.params_ciclo.params_ciclo import _load_factory_params
    assert _load_factory_params(str(tmp_path / "user" / "no.json")) == {}

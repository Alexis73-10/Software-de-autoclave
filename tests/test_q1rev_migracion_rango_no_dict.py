# tests/test_q1rev_migracion_rango_no_dict.py
"""Revisión Q1 (SAF-04 / SEN-07a): si `rango_calentamiento` viejo no es un
dict, la migración crea los dos rangos nuevos con el defecto de fábrica (2,0;
mismas min/max/clase que el catálogo) y deja una advertencia en el log, en vez
de borrarlo sin crear nada."""

import logging

import pytest

from autoclave.core.managers.cycle_manager import migrar_parametros


@pytest.mark.parametrize("viejo", [3.5, None, "x", [1, 2]])
def test_rango_viejo_no_dict_crea_los_dos_con_el_defecto(viejo, caplog):
    params = {"calentamiento": {"factor_calentamiento": {"value": 50},
                                "rango_calentamiento": viejo,
                                "tasa_calentamiento": {"value": 50.0}}}
    with caplog.at_level(logging.WARNING):
        assert migrar_parametros(params) is True
    cal = params["calentamiento"]
    assert list(cal) == ["factor_calentamiento", "rango_calentamiento_temp",
                         "rango_calentamiento_pres", "tasa_calentamiento"]
    assert cal["rango_calentamiento_temp"] == {
        "value": 2.0, "type": "float", "unit": "°C", "clase": "diferencia",
        "min": 0, "max": 30}
    assert cal["rango_calentamiento_pres"] == {
        "value": 2.0, "type": "float", "unit": "kPa", "clase": "diferencia",
        "min": 0, "max": 30}
    assert any("defecto" in r.getMessage() for r in caplog.records)


def test_rango_viejo_no_dict_respeta_una_clave_nueva_existente():
    params = {"calentamiento": {"rango_calentamiento": 9,
                                "rango_calentamiento_temp": {"value": 1.0, "unit": "°C"}}}
    migrar_parametros(params)
    cal = params["calentamiento"]
    assert cal["rango_calentamiento_temp"] == {"value": 1.0, "unit": "°C"}
    assert cal["rango_calentamiento_pres"]["value"] == 2.0

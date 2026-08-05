import pytest
from autoclave.core.managers.cycle_manager import Cycle


def _cycle():
    return Cycle(
        cycle_id="test",
        name="Test",
        parameters={
            "esterilizacion": {
                "temperatura_esterilizacion": {
                    "value": 134.0, "type": "float", "unit": "°C", "min": 100, "max": 140
                },
                "factor_esterilizacion": {
                    "value": 70, "type": "int", "unit": "%", "min": 0, "max": 100
                },
            },
            "descompresion": {
                "modo_3": {
                    "presion_cambio": {
                        "value": 150, "type": "int", "unit": "kPa", "min": 0, "max": 500
                    }
                }
            },
            "finalizacion": {
                "apertura_automatica": {"value": False, "type": "bool", "unit": ""}
            },
            "prevacio": {
                "conteo_pulso_a": {"value": 4, "unit": "", "min": 0, "max": 100}
            },
        },
    )


def test_set_param_actualiza_valor_y_lo_devuelve():
    cycle = _cycle()
    result = cycle.set_param("esterilizacion", ["temperatura_esterilizacion"], 135.0)
    assert result == 135.0
    assert cycle.parameters["esterilizacion"]["temperatura_esterilizacion"]["value"] == 135.0


def test_set_param_coerciona_tipo_float_desde_string_o_int():
    cycle = _cycle()
    cycle.set_param("esterilizacion", ["temperatura_esterilizacion"], 135)
    assert cycle.parameters["esterilizacion"]["temperatura_esterilizacion"]["value"] == 135.0
    assert isinstance(cycle.parameters["esterilizacion"]["temperatura_esterilizacion"]["value"], float)


def test_set_param_coerciona_tipo_int():
    cycle = _cycle()
    cycle.set_param("esterilizacion", ["factor_esterilizacion"], 80.0)
    assert cycle.parameters["esterilizacion"]["factor_esterilizacion"]["value"] == 80
    assert isinstance(cycle.parameters["esterilizacion"]["factor_esterilizacion"]["value"], int)


def test_set_param_coerciona_tipo_bool():
    cycle = _cycle()
    cycle.set_param("finalizacion", ["apertura_automatica"], 1)
    assert cycle.parameters["finalizacion"]["apertura_automatica"]["value"] is True


def test_set_param_navega_paths_anidados():
    cycle = _cycle()
    cycle.set_param("descompresion", ["modo_3", "presion_cambio"], 200)
    assert cycle.parameters["descompresion"]["modo_3"]["presion_cambio"]["value"] == 200


def test_set_param_sin_type_asume_int():
    cycle = _cycle()
    cycle.set_param("prevacio", ["conteo_pulso_a"], 7)
    assert cycle.parameters["prevacio"]["conteo_pulso_a"]["value"] == 7


def test_set_param_rechaza_fase_inexistente():
    cycle = _cycle()
    with pytest.raises(KeyError):
        cycle.set_param("no_existe", ["x"], 1)


def test_set_param_rechaza_path_inexistente():
    cycle = _cycle()
    with pytest.raises(KeyError):
        cycle.set_param("esterilizacion", ["no_existe"], 1)


def test_set_param_rechaza_path_anidado_inexistente():
    cycle = _cycle()
    with pytest.raises(KeyError):
        cycle.set_param("descompresion", ["modo_9", "presion_cambio"], 1)


def test_set_param_rechaza_valor_bajo_el_minimo():
    cycle = _cycle()
    with pytest.raises(ValueError):
        cycle.set_param("esterilizacion", ["temperatura_esterilizacion"], 50.0)
    # no debe mutar el valor original ante un rechazo
    assert cycle.parameters["esterilizacion"]["temperatura_esterilizacion"]["value"] == 134.0


def test_set_param_rechaza_valor_sobre_el_maximo():
    cycle = _cycle()
    with pytest.raises(ValueError):
        cycle.set_param("esterilizacion", ["temperatura_esterilizacion"], 999.0)
    assert cycle.parameters["esterilizacion"]["temperatura_esterilizacion"]["value"] == 134.0


def test_set_param_rechaza_valor_no_numerico():
    cycle = _cycle()
    with pytest.raises((TypeError, ValueError)):
        cycle.set_param("esterilizacion", ["temperatura_esterilizacion"], "abc")

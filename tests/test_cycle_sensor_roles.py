import pytest
from autoclave.core.managers.cycle_manager import Cycle


def _cycle(sensor_roles=None, display_slots=None):
    return Cycle(
        cycle_id="test", name="Test", parameters={},
        sensor_roles=sensor_roles, display_slots=display_slots,
    )


def test_get_principal_sensor_por_defecto_sin_roles_configurados():
    cycle = _cycle()
    assert cycle.get_principal_sensor() == "temp_camara"


def test_get_principal_sensor_devuelve_el_marcado():
    cycle = _cycle(sensor_roles={"temp_camara": "referencia", "temp_2_camara": "principal"})
    assert cycle.get_principal_sensor() == "temp_2_camara"


def test_get_referencia_sensor_none_si_no_hay_ninguno():
    cycle = _cycle(sensor_roles={"temp_camara": "principal"})
    assert cycle.get_referencia_sensor() is None


def test_get_referencia_sensor_devuelve_el_marcado():
    cycle = _cycle(sensor_roles={"temp_camara": "referencia", "temp_2_camara": "principal"})
    assert cycle.get_referencia_sensor() == "temp_camara"


def test_display_slots_por_defecto_vacio():
    cycle = _cycle()
    assert cycle.display_slots == [None, None, None]


def test_set_sensor_roles_actualiza_el_dict():
    cycle = _cycle(sensor_roles={"temp_camara": "principal"})
    cycle.set_sensor_roles({"temp_camara": "referencia", "temp_2_camara": "principal"})
    assert cycle.sensor_roles == {"temp_camara": "referencia", "temp_2_camara": "principal"}


def test_set_sensor_roles_rechaza_dos_principales():
    cycle = _cycle(sensor_roles={"temp_camara": "principal"})
    with pytest.raises(ValueError):
        cycle.set_sensor_roles({"temp_camara": "principal", "temp_2_camara": "principal"})
    # no debe mutar ante el rechazo
    assert cycle.sensor_roles == {"temp_camara": "principal"}


def test_set_sensor_roles_rechaza_sensor_desconocido():
    cycle = _cycle()
    with pytest.raises(ValueError):
        cycle.set_sensor_roles({"sensor_inventado": "principal"})


def test_set_sensor_roles_rechaza_rol_invalido():
    cycle = _cycle()
    with pytest.raises(ValueError):
        cycle.set_sensor_roles({"temp_camara": "rol_inventado"})


def test_set_sensor_roles_acepta_no_en_uso_repetido():
    cycle = _cycle()
    cycle.set_sensor_roles({"temp_camara": "no_en_uso", "temp_ref": "no_en_uso"})
    assert cycle.sensor_roles == {"temp_camara": "no_en_uso", "temp_ref": "no_en_uso"}


def test_set_display_slots_actualiza_la_lista():
    cycle = _cycle()
    cycle.set_display_slots(["temp_camara", "pres_camara", None])
    assert cycle.display_slots == ["temp_camara", "pres_camara", None]


def test_set_display_slots_rechaza_longitud_incorrecta():
    cycle = _cycle()
    with pytest.raises(ValueError):
        cycle.set_display_slots(["temp_camara", "pres_camara"])


def test_set_display_slots_rechaza_sensor_desconocido():
    cycle = _cycle()
    with pytest.raises(ValueError):
        cycle.set_display_slots(["sensor_inventado", None, None])


def test_set_display_slots_acepta_sensor_de_presion():
    cycle = _cycle()
    cycle.set_display_slots(["pres_empaque_1", None, None])
    assert cycle.display_slots == ["pres_empaque_1", None, None]

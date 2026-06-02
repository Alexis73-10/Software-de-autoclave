from autoclave.installation.profile import validate_profile_data, ProfileValidationError

VALID_DATA = {
    "machine_id":      "ACV-2026-SN001",
    "model_id":        "MX-500",
    "serial_number":   "SN001",
    "equipment_class": "piso",
    "door_count":      2,
    "door_type":       "advanced",
    "cooling_level":   2,
    "door_id":         1,
    "role":            "operator_front",
    "created_at":      "2026-01-01T00:00:00",
    "locked":          True,
}


def test_valid_profile_returns_no_errors():
    assert validate_profile_data(VALID_DATA) == []


def test_missing_field_reported():
    data = {**VALID_DATA}
    del data["serial_number"]
    errors = validate_profile_data(data)
    assert any("serial_number" in e for e in errors)


def test_wrong_type_reported():
    data = {**VALID_DATA, "door_count": "dos"}
    errors = validate_profile_data(data)
    assert any("door_count" in e for e in errors)


def test_invalid_door_count():
    data = {**VALID_DATA, "door_count": 5}
    errors = validate_profile_data(data)
    assert any("door_count" in e for e in errors)


def test_invalid_equipment_class():
    data = {**VALID_DATA, "equipment_class": "diagonal"}
    errors = validate_profile_data(data)
    assert any("equipment_class" in e for e in errors)


def test_invalid_door_type():
    data = {**VALID_DATA, "door_type": "giratoria"}
    errors = validate_profile_data(data)
    assert any("door_type" in e for e in errors)


def test_door_count_excede_max_para_perfil():
    # Mesa N tiene door_count_max=1; door_count=2 debe fallar
    data = {**VALID_DATA, "equipment_class": "mesa_n", "door_count": 2}
    errors = validate_profile_data(data)
    assert any("door_count" in e for e in errors)


def test_cooling_level_excede_max_para_perfil():
    # Mesa N tiene cooling_level_max=0; cooling_level=1 debe fallar
    data = {**VALID_DATA, "equipment_class": "mesa_n", "door_count": 1, "cooling_level": 1}
    errors = validate_profile_data(data)
    assert any("cooling_level" in e for e in errors)


def test_piso_acepta_dos_puertas_y_cooling():
    data = {**VALID_DATA, "equipment_class": "piso", "door_count": 2, "cooling_level": 4}
    assert validate_profile_data(data) == []


def test_profile_validation_error_contains_messages():
    errors = ["campo faltante: 'serial_number'"]
    exc = ProfileValidationError(errors)
    assert "serial_number" in str(exc)
    assert exc.errors == errors

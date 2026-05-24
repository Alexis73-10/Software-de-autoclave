from autoclave.installation.profile import validate_profile_data, ProfileValidationError

VALID_DATA = {
    "machine_id": "ACV-2026-SN001",
    "model_id": "MX-500",
    "serial_number": "SN001",
    "door_count": 2,
    "door_type": "advanced",
    "equipment_type": "horizontal",
    "drying_type": "vacuum",
    "door_id": 1,
    "role": "operator_front",
    "created_at": "2026-01-01T00:00:00",
    "locked": True,
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

def test_invalid_door_type():
    data = {**VALID_DATA, "door_type": "giratoria"}
    errors = validate_profile_data(data)
    assert any("door_type" in e for e in errors)

def test_invalid_equipment_type():
    data = {**VALID_DATA, "equipment_type": "diagonal"}
    errors = validate_profile_data(data)
    assert any("equipment_type" in e for e in errors)

def test_invalid_drying_type():
    data = {**VALID_DATA, "drying_type": "solar"}
    errors = validate_profile_data(data)
    assert any("drying_type" in e for e in errors)

def test_profile_validation_error_contains_messages():
    errors = ["campo faltante: 'serial_number'"]
    exc = ProfileValidationError(errors)
    assert "serial_number" in str(exc)
    assert exc.errors == errors

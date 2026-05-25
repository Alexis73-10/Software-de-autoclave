# tests/test_activation.py
from datetime import date
from autoclave.installation.activation import (
    generate_installation_code,
    validate_installation_code,
    generate_factory_key,
    validate_factory_key,
)

TODAY     = date(2026, 5, 24)
YESTERDAY = date(2026, 5, 23)
SERIAL    = "SN123456"

# --- Installation code ---

def test_installation_code_length():
    assert len(generate_installation_code(SERIAL, TODAY)) == 12

def test_installation_code_is_uppercase():
    assert generate_installation_code(SERIAL, TODAY).isupper()

def test_installation_code_deterministic_same_day():
    assert generate_installation_code(SERIAL, TODAY) == generate_installation_code(SERIAL, TODAY)

def test_installation_code_differs_by_day():
    assert generate_installation_code(SERIAL, TODAY) != generate_installation_code(SERIAL, YESTERDAY)

def test_installation_code_differs_by_serial():
    assert generate_installation_code(SERIAL, TODAY) != generate_installation_code("SN999999", TODAY)

def test_validate_installation_code_correct():
    code = generate_installation_code(SERIAL, TODAY)
    assert validate_installation_code(SERIAL, code, TODAY) is True

def test_validate_installation_code_wrong_day():
    code = generate_installation_code(SERIAL, YESTERDAY)
    assert validate_installation_code(SERIAL, code, TODAY) is False

def test_validate_installation_code_wrong_serial():
    code = generate_installation_code(SERIAL, TODAY)
    assert validate_installation_code("SN999999", code, TODAY) is False

def test_validate_installation_code_case_insensitive():
    code = generate_installation_code(SERIAL, TODAY)
    assert validate_installation_code("sn123456", code.lower(), TODAY) is True

def test_validate_installation_code_strips_whitespace():
    code = generate_installation_code(SERIAL, TODAY)
    assert validate_installation_code(SERIAL, f"  {code}  ", TODAY) is True

# --- Factory key ---

def test_factory_key_length():
    assert len(generate_factory_key(SERIAL, TODAY)) == 12

def test_factory_key_deterministic_same_day():
    assert generate_factory_key(SERIAL, TODAY) == generate_factory_key(SERIAL, TODAY)

def test_factory_key_differs_by_day():
    assert generate_factory_key(SERIAL, TODAY) != generate_factory_key(SERIAL, YESTERDAY)

def test_validate_factory_key_correct():
    key = generate_factory_key(SERIAL, TODAY)
    assert validate_factory_key(SERIAL, key, TODAY) is True

def test_validate_factory_key_wrong_day():
    key = generate_factory_key(SERIAL, YESTERDAY)
    assert validate_factory_key(SERIAL, key, TODAY) is False

# --- Cross-type: codes cannot be used interchangeably ---

def test_installation_code_rejected_as_factory_key():
    code = generate_installation_code(SERIAL, TODAY)
    assert validate_factory_key(SERIAL, code, TODAY) is False

def test_factory_key_rejected_as_installation_code():
    key = generate_factory_key(SERIAL, TODAY)
    assert validate_installation_code(SERIAL, key, TODAY) is False

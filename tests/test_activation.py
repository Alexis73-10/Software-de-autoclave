from autoclave.installation.activation import generate_code, validate_code

def test_generate_code_is_deterministic():
    assert generate_code("SN123456") == generate_code("SN123456")

def test_generate_code_length():
    assert len(generate_code("SN123456")) == 12

def test_validate_code_correct():
    code = generate_code("SN123456")
    assert validate_code("SN123456", code) is True

def test_validate_code_wrong_code():
    assert validate_code("SN123456", "WRONGCODE123") is False

def test_validate_code_case_insensitive():
    code = generate_code("SN123456")
    assert validate_code("sn123456", code.lower()) is True

def test_validate_code_different_serial():
    code = generate_code("SN123456")
    assert validate_code("SN999999", code) is False

def test_validate_code_strips_whitespace():
    code = generate_code("SN123456")
    assert validate_code("SN123456", f"  {code}  ") is True

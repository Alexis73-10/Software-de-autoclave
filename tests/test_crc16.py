from autoclave.protocols.crc16 import agregar_crc, crc16_ccitt_false, validar_linea


def test_vector_obligatorio_123456789():
    assert crc16_ccitt_false(b"123456789") == 0x29B1


def test_payload_vacio_es_valor_inicial():
    assert crc16_ccitt_false(b"") == 0xFFFF


def test_agregar_crc_formato_hex_mayuscula():
    assert agregar_crc("123456789") == "123456789*29B1"


def test_validar_linea_valida_devuelve_payload():
    linea = agregar_crc("AI:1,2,3")
    assert validar_linea(linea) == "AI:1,2,3"


def test_validar_linea_crc_erroneo():
    assert validar_linea("123456789*29B2") is None


def test_validar_linea_payload_alterado():
    assert validar_linea("123456788*29B1") is None


def test_validar_linea_sin_sufijo():
    assert validar_linea("ACK") is None


def test_validar_linea_sufijo_mal_formado():
    assert validar_linea("123456789*29b1") is None   # minúscula no permitida
    assert validar_linea("123456789*29B") is None
    assert validar_linea("123456789*29B10") is None
    assert validar_linea("123456789*ZZZZ") is None


def test_validar_linea_payload_con_asterisco_usa_el_ultimo():
    linea = agregar_crc("A*B")
    assert validar_linea(linea) == "A*B"


def test_validar_linea_no_ascii():
    assert validar_linea("AI:ñ*0000") is None

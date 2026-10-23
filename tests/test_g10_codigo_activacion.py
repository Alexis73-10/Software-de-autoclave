"""G10 (tanda 10, D10-2): el código de activación y la clave de fábrica se
normalizan antes de comparar (mayúsculas, sin espacios ni guiones, 0->O, 1->I,
8->B), y el generador muestra los códigos en una fuente monoespaciada que
distingue O de 0."""

import re
from datetime import date
from pathlib import Path

import pytest

from autoclave.installation.activation import (
    generate_factory_key,
    generate_installation_code,
    normalizar_codigo,
    validate_factory_key,
    validate_installation_code,
)
from autoclave.ui_qml.bridge.puente_instalacion import PuenteInstalacion

SERIE = "SN128745"
DIA = date(2026, 10, 23)


# --- caso real del equipo de pruebas (23-oct-2026) ---

def test_generador_produce_el_codigo_del_caso_real():
    assert generate_installation_code(SERIE, DIA) == "FR4QAXQ3O43N"


@pytest.mark.parametrize("tecleado", [
    "FR4QAXQ3O43N",       # tal cual (letra O)
    "FR4QAXQ3043N",       # con cero en vez de O: el caso rechazado en campo
    "fr4qaxq3043n",       # minúsculas
    "  FR4Q AXQ3 043N  ",  # espacios
    "FR4Q-AXQ3-043N",     # guiones
    "fr4q - axq3-o43n",   # mezcla
])
def test_caso_real_valido(tecleado):
    assert validate_installation_code(SERIE, tecleado, DIA) is True


def test_caso_real_otro_dia_sigue_invalido():
    assert validate_installation_code(SERIE, "FR4QAXQ3043N", date(2026, 10, 22)) is False
    assert validate_installation_code(SERIE, "FR4QAXQ3043N", date(2026, 10, 24)) is False


def test_caso_real_otra_serie_sigue_invalido():
    assert validate_installation_code("SN128746", "FR4QAXQ3043N", DIA) is False


# --- normalización ---

def test_normalizar_codigo():
    assert normalizar_codigo(" ab-c d ") == "ABCD"
    assert normalizar_codigo("0189") == "OIB9"
    assert normalizar_codigo("") == ""


def test_normalizar_no_altera_un_codigo_generado():
    # Base32 no usa 0, 1, 8 ni 9: un código generado queda idéntico.
    for dia in (DIA, date(2026, 1, 1), date(2027, 6, 15)):
        for gen in (generate_installation_code, generate_factory_key):
            codigo = gen(SERIE, dia)
            assert normalizar_codigo(codigo) == codigo


def test_clave_fabrica_normalizada():
    clave = generate_factory_key(SERIE, DIA)
    tecleada = "-".join(clave[i:i + 4] for i in range(0, 12, 4)).lower()
    tecleada = tecleada.replace("O", "0").replace("o", "0").replace("I", "1").replace("i", "1") \
        .replace("B", "8").replace("b", "8")
    assert validate_factory_key(SERIE, tecleada, DIA) is True
    assert validate_factory_key(SERIE, tecleada, date(2026, 10, 22)) is False


def test_codigos_no_intercambiables_tras_normalizar():
    assert validate_factory_key(SERIE, "FR4QAXQ3043N", DIA) is False
    assert validate_installation_code(SERIE, generate_factory_key(SERIE, DIA), DIA) is False


# --- el asistente pasa por la misma validación ---

def test_asistente_acepta_el_caso_real_con_cero():
    validar = lambda serie, codigo: validate_installation_code(serie, codigo, DIA)  # noqa: E731
    puente = PuenteInstalacion(validar_codigo=validar)
    assert puente.validarCodigo("sn128745", "FR4QAXQ3043N") is True
    assert puente.validarCodigo("SN128745", "FR4Q-AXQ3-043N") is True
    puente_otro_dia = PuenteInstalacion(
        validar_codigo=lambda s, c: validate_installation_code(s, c, date(2026, 10, 22)))
    assert puente_otro_dia.validarCodigo("SN128745", "FR4QAXQ3043N") is False


def test_asistente_usa_por_defecto_la_validacion_comun():
    import inspect
    firma = inspect.signature(PuenteInstalacion.__init__)
    assert firma.parameters["validar_codigo"].default is validate_installation_code


# --- D10-2.2: fuente del generador ---

def test_generador_muestra_codigos_en_fuente_que_distingue_o_de_cero():
    fuente = (Path(__file__).resolve().parents[1] / "tools" / "generador" / "app.py").read_text(encoding="utf-8")
    regla = re.search(r"\.code\{([^}]*)\}", fuente)
    assert regla, "no se encontró la regla CSS .code"
    familia = re.search(r"font-family:([^;}]*)", regla.group(1)).group(1)
    familias = [f.strip().strip('"').strip("'") for f in familia.split(",")]
    assert familias[0] == "Consolas"
    assert "Cascadia Mono" in familias
    assert familias[-1] == "monospace"

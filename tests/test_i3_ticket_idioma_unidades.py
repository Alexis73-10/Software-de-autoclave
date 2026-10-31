"""I3 (tanda 5): el ticket de ciclo en el idioma y las unidades vigentes al
generarlo; los valores guardados siguen en °C y kPa absolutos."""

import pytest

from autoclave.services.domain.logging import ticket_formatter as tf

META = {"numero_ciclo": 12, "serie": "S1", "modelo": "M", "version_sw": "1.0",
        "nombre_ciclo": "Instrumental 134", "tipo_ciclo": "solido",
        "temp_esterilizacion": 134.0, "tiempo_esterilizacion": 3.5,
        "fecha_inicio": "2026-10-20T10:00:00"}
ATM = 74.6


@pytest.fixture(autouse=True)
def _sin_proveedor():
    tf.fijar_proveedor(None)
    yield
    tf.fijar_proveedor(None)


def test_por_defecto_igual_que_antes():
    texto = tf.format_header(META)
    assert "Fecha: 20/OCT/2026" in texto and "Temp. Ester.: 134.0 C" in texto
    assert texto.endswith("  Hora      C      kPa")
    assert "Unidades" not in texto
    assert tf.format_row({"fase_codigo": "E", "timestamp_rel": "00:01", "temp_camara": 134.2,
                          "pres_camara": 304.1}) == "E 00:01 0134.2 0304.1"


def test_ingles_fahrenheit_y_psig():
    p = tf.Presentacion("en", "F", "psi", ATM)
    h = tf.format_header(META, p)
    assert "Date: 20/OCT/2026" in h and "Steril. temp.: 273.2 F" in h
    assert "Units: F, psig (v=inHg vacuum)" in h
    fila = tf.format_row({"fase_codigo": "E", "timestamp_rel": "00:01", "temp_camara": 134.0,
                          "pres_camara": ATM + 6.894757 * 29.5}, p)
    assert "0273.2" in fila and "0029.5" in fila and not fila.endswith("v")
    vacio = tf.format_row({"fase_codigo": "V", "timestamp_rel": "00:02", "temp_camara": 20.0,
                           "pres_camara": ATM - 3.386389 * 15}, p)
    assert vacio.endswith("0015.0v")
    pie = tf.format_footer("COMPLETADO", "2026-10-20T10:40:00", temp_final=80.0, p=p)
    assert "Status: COMPLETED" in pie and "Final temp.: 176 F" in pie and "End time" in pie


def test_psi_sin_p_atm_no_inventa():
    p = tf.Presentacion("es", "C", "psi", None)
    assert tf.format_row({"fase_codigo": "E", "timestamp_rel": "00:01", "temp_camara": 1.0,
                          "pres_camara": 200.0}, p).endswith(" -----")


def test_temperatura_en_texto_se_convierte_y_si_no_se_puede_no_se_muestra():
    p = tf.Presentacion("es", "F", "kPa", ATM)
    assert "273.2 F" in tf.format_header({**META, "temp_esterilizacion": "134.0"}, p)
    assert "--- F" in tf.format_header({**META, "temp_esterilizacion": "abc"}, p)


def test_motivo_en_ingles_por_codigo():
    p = tf.Presentacion("en", "C", "kPa", None)
    assert tf.motivo_ticket("PRE-04", "x", p) == "PRE-04 - High chamber pressure"
    assert tf.motivo_ticket(None, "texto libre", p) == "texto libre"


@pytest.mark.parametrize("p", [tf.Presentacion("en", "F", "psi", ATM), tf.Presentacion()])
def test_todo_el_ticket_se_codifica_en_cp437(p):
    texto = (tf.format_header(META, p)
             + tf.format_row({"fase_codigo": "E", "timestamp_rel": "00:01", "temp_camara": 134.0,
                              "pres_camara": 300.0}, p)
             + tf.format_footer("FALLO_ESTERILIZACION", "2026-10-20T10:40:00",
                                motivo=tf.motivo_ticket("CIC-04", "", p), p=p))
    texto.encode("cp437")


def test_proveedor_roto_cae_al_espanol():
    def roto():
        raise RuntimeError("x")
    tf.fijar_proveedor(roto)
    assert tf.presentacion_actual() == tf.Presentacion()


def test_reimpresion_usa_una_sola_presentacion():
    tf.fijar_proveedor(lambda: tf.Presentacion("en", "F", "kPa", ATM))
    ciclo = {**META, "resultado": "CANCELADO", "fecha_fin": "2026-10-20T10:40:00",
             "codigo_fallo": None, "motivo_fallo": None, "operador": "ana"}
    t = tf.format_ticket(ciclo, [{"fase_codigo": "E", "timestamp_rel": "00:01",
                                  "temp_camara": 134.0, "pres_camara": 300.0}])
    assert "Status: CANCELLED" in t and "Operator: ana" in t and "0273.2" in t

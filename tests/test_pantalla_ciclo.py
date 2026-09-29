# tests/test_pantalla_ciclo.py
#
# Extracción y formato de los datos de la tarjeta de parámetros de la
# pantalla de ciclo (Pantallas/Ciclo.qml) a partir de las respuestas REST
# del backend: GET /cycle (consignas del ciclo seleccionado) y GET /status
# (lecturas de cámara). Presentación con coma decimal (D-19).

from autoclave.ui_qml.domain.pantalla_ciclo import (
    SIN_DATO,
    formatear_minutos,
    formatear_presion,
    formatear_temp_camara,
    formatear_temperatura,
    lecturas_de_status,
    parametros_de_ciclo,
)


def _p(valor, unidad=""):
    return {"value": valor, "type": "float", "unit": unidad, "min": 0, "max": 9999}


def _ciclo(temp=134.0, t_ester=3.5, t_secado=15.0, nombre="Bowe & Dick"):
    return {
        "id": "bowe_dick",
        "name": nombre,
        "parameters": {
            "esterilizacion": {
                "temperatura_esterilizacion": _p(temp, "°C"),
                "tiempo_esterilizacion": _p(t_ester, "min"),
            },
            "secado": {"tiempo_secado": _p(t_secado, "min")},
        },
    }


def _status(temp=85.0, pres=100.8):
    return {"sensors": {"temperature": {"camara": temp}, "pressure": {"camara": pres}}}


# ── formatos ─────────────────────────────────────────────────────────────

def test_temperatura_con_un_decimal_y_coma():
    assert formatear_temperatura(134.0) == "134,0"


def test_temp_camara_rellena_tres_digitos_enteros():
    assert formatear_temp_camara(85.0) == "085,0"
    assert formatear_temp_camara(134.26) == "134,3"


def test_minutos_enteros_sin_decimal_y_fraccion_con_un_decimal():
    assert formatear_minutos(15.0) == "15"
    assert formatear_minutos(3.5) == "3,5"


def test_presion_con_un_decimal():
    assert formatear_presion(100.8) == "100,8"


def test_valor_ausente_o_no_numerico_se_muestra_sin_dato():
    for fmt in (formatear_temperatura, formatear_temp_camara, formatear_minutos, formatear_presion):
        assert fmt(None) == SIN_DATO
        assert fmt("134") == SIN_DATO
        assert fmt(True) == SIN_DATO
        assert fmt(float("nan")) == SIN_DATO


# ── GET /cycle ───────────────────────────────────────────────────────────

def test_parametros_de_ciclo_extrae_consignas_formateadas():
    assert parametros_de_ciclo(_ciclo()) == {
        "programa": "BOWE & DICK",
        "temp_esterilizacion": "134,0",
        "tiempo_esterilizacion": "3,5",
        "tiempo_secado": "15",
    }


def test_parametros_de_ciclo_refleja_otro_ciclo():
    datos = parametros_de_ciclo(_ciclo(temp=121.0, t_ester=20.0, t_secado=1.0, nombre="Instrumental 121"))
    assert datos["programa"] == "INSTRUMENTAL 121"
    assert datos["temp_esterilizacion"] == "121,0"
    assert datos["tiempo_esterilizacion"] == "20"
    assert datos["tiempo_secado"] == "1"


def test_parametro_faltante_se_muestra_sin_dato_sin_tumbar_el_resto():
    ciclo = _ciclo()
    del ciclo["parameters"]["secado"]
    datos = parametros_de_ciclo(ciclo)
    assert datos["tiempo_secado"] == SIN_DATO
    assert datos["temp_esterilizacion"] == "134,0"


def test_respuesta_de_ciclo_mal_formada_da_todo_sin_dato():
    for malo in (None, [], "x", {"parameters": "x"}):
        datos = parametros_de_ciclo(malo)
        assert set(datos.values()) == {SIN_DATO}


# ── GET /status ──────────────────────────────────────────────────────────

def test_lecturas_de_status_extrae_temp_y_presion_de_camara():
    assert lecturas_de_status(_status()) == {"temp_camara": "085,0", "presion_camara": "100,8"}


def test_sensor_de_camara_ausente_se_muestra_sin_dato():
    datos = lecturas_de_status(_status(temp=None))
    assert datos["temp_camara"] == SIN_DATO
    assert datos["presion_camara"] == "100,8"


def test_status_mal_formado_da_todo_sin_dato():
    for malo in (None, {}, {"sensors": []}, {"sensors": {"temperature": 5}}):
        assert set(lecturas_de_status(malo).values()) == {SIN_DATO}

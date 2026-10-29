# Dominio puro de OPCIONES › Entradas / Salidas (D-ES-04, D-ES-05, D-ES-13).
import pytest

from autoclave.ui_qml.domain import entradas_salidas as d

_CH_DI = [{"name": "paro_emergencia", "estado_key": "paro_emergencia", "i18n": "io.di.paro_emergencia", "id": "DI 11"}]
_CH_DO = [{"name": "vapor_camara", "estado_key": "vapor_camara", "i18n": "io.do.vapor_camara",
           "id": "DO 04", "momentanea": False, "bloqueada": False}]
_ST = {"estado_tarjeta": "ok", "card_connected": True, "test_mode_active": False,
       "sensors": {"digital_inputs": {"paro_emergencia": 1}, "digital_outputs": {"vapor_camara": 1},
                   "temperature": {"camara": 121.5}, "pressure": {"camara": 205.0},
                   "adc": {"temp_camara": 2100, "pres_camara": 2400}}}


def test_enlace_ok_solo_con_modulo_es_ok():
    assert d.enlace_ok(_ST) is True
    assert d.enlace_ok({**_ST, "estado_tarjeta": "desconectada"}) is False
    assert d.enlace_ok(None) is False


def test_entradas_nivel_crudo_activo_inactivo():
    e = d.presentar_entradas(_CH_DI, _ST)[0]
    assert e["activo"] is True and e["id"] == "DI 11"
    st = {**_ST, "sensors": {**_ST["sensors"], "digital_inputs": {"paro_emergencia": 0}}}
    assert d.presentar_entradas(_CH_DI, st)[0]["activo"] is False


def test_entradas_sin_datos_nunca_cero():
    assert d.presentar_entradas(_CH_DI, None)[0]["activo"] is None
    assert d.presentar_entradas(_CH_DI, {**_ST, "estado_tarjeta": "desconectada"})[0]["activo"] is None
    # valor fuera de 0/1 tampoco se inventa
    st = {**_ST, "sensors": {**_ST["sensors"], "digital_inputs": {"paro_emergencia": 7}}}
    assert d.presentar_entradas(_CH_DI, st)[0]["activo"] is None


def test_salidas_estado_y_sin_datos():
    assert d.presentar_salidas(_CH_DO, _ST)[0]["encendida"] is True
    assert d.presentar_salidas(_CH_DO, None)[0]["encendida"] is None


def test_sensor_con_lectura_y_adc():
    s = {"name": "temp_camara", "estado_key": "temp_camara", "i18n": "io.ai.temp_camara", "id": "AI 01"}
    r = d.presentar_sensores([s], "temperature", _ST, {"temp_camara": "camara"})[0]
    assert r["valor"] == 121.5 and r["adc"] == 2100 and r["valido"] is True


def test_sensor_sin_lectura_valida():
    s = {"name": "temp_camara", "estado_key": "temp_camara", "i18n": "x", "id": "AI 01"}
    st = {**_ST, "sensors": {**_ST["sensors"], "temperature": {"camara": None}}}
    r = d.presentar_sensores([s], "temperature", st, {"temp_camara": "camara"})[0]
    assert r["valor"] is None and r["valido"] is False


def test_calculo_de_calibracion_por_puntos():
    # ganancia/offset actual 1/0: lectura 12 -> real 9.54, lectura 322 -> real 300
    g, o = d.calcular_calibracion(12.0, 9.54, 322.0, 300.0, 1.0, 0.0)
    assert g == pytest.approx((300 - 9.54) / (322 - 12))
    assert 12 * g + o == pytest.approx(9.54)


def test_calculo_rechaza_puntos_iguales():
    with pytest.raises(ValueError):
        d.calcular_calibracion(5.0, 4.0, 5.0, 6.0, 1.0, 0.0)


def test_origen_lectura_editada_pasa_a_escrita():
    assert d.origen_de("capturada", editada=False) == "capturada"
    assert d.origen_de("capturada", editada=True) == "escrita"
    assert d.origen_de("escrita", editada=False) == "escrita"


# ── permisos (§3, OPC-28) ───────────────────────────────────────────────────
from autoclave.ui_qml.domain import permisos_opciones as p


@pytest.mark.parametrize("rol,estado,esperado", [
    ("tecnico", "PREPARADO", True), ("ingeniero", "PREPARACION", True),
    ("tecnico", "FALLA", True),
    ("tecnico", "CICLO", False), ("ingeniero", "CICLO", False),
    ("tecnico", "HIBERNACION", False), ("tecnico", "EMERGENCIA", False),
    ("admin", "PREPARADO", False), ("", "PREPARADO", False), (None, "PREPARADO", False),
])
def test_permiso_modo_prueba(rol, estado, esperado):
    assert p.puede_modo_prueba(rol, estado) is esperado


@pytest.mark.parametrize("rol,estado,esperado", [
    ("tecnico", "PREPARADO", True), ("tecnico", "CICLO", False),
    ("ingeniero", "CICLO", True), ("ingeniero", "PREPARADO", True),
    ("admin", "PREPARADO", False), (None, "PREPARADO", False),
])
def test_permiso_calibrar(rol, estado, esperado):
    assert p.puede_calibrar(rol, estado) is esperado

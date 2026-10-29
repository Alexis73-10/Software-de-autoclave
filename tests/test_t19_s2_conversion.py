# tests/test_t19_s2_conversion.py
#
# Tanda 19 (MOD-03, MOD-04): conversión de temperatura y presión con el enlace
# Modbus (módulos M31-U) y con un canal crudo None. Tanda 20 (T20-03): el
# enlace serial se retiró; sus casos se borraron y ya no hace falta fijar el
# enlace (es único).

import math
from pathlib import Path

import pytest

from autoclave.config import load_config
from autoclave.hal.measures import converters
from autoclave.hal.measures.units import Units

CONFIG = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "config"
CAL_MODBUS = CONFIG / "calibration_modbus.yaml"


@pytest.fixture(autouse=True)
def _filtros_limpios():
    def limpiar():
        converters.reiniciar_presiones()
        for i in range(8):
            converters._ma_temp[i].buffer.clear()
            converters._oe_temp[i].reset()
    limpiar()
    yield
    limpiar()


@pytest.fixture
def cfg_modbus():
    return load_config(CAL_MODBUS)


def _ai(temps=None, pres=None):
    """Trama AI de 16 canales: temperatura en 0-7 y presión en 8-15."""
    t = list(temps or []) + [None] * (8 - len(temps or []))
    p = list(pres or []) + [None] * (8 - len(pres or []))
    return t + p


# ── fábrica Modbus ─────────────────────────────────────────────────────────

@pytest.mark.req("MOD-04")
@pytest.mark.parametrize("decimas,grados", [(1210, 121.0), (1340, 134.0), (0, 0.0),
                                            (-50, -5.0), (5, 0.5), (2000, 200.0)])
def test_fabrica_modbus_temperatura_decimas_a_grados(cfg_modbus, decimas, grados):
    assert converters.convert_temperatures(_ai([decimas]), cfg_modbus)[0] == grados


@pytest.mark.req("MOD-03")
def test_cero_decimas_es_valido_en_modbus(cfg_modbus):
    """El centinela 0/4095 = sin sonda era propio del ADC de la tarjeta serial
    (retirada en la tanda 20, T20-03: se borró la parte serial de esta prueba).
    Revisión R (V19-s2-03): en Modbus 4095 décimas (409,5 °C) queda fuera del
    rango plausible de la PT100 (-500..2500 décimas) y da None; antes esta
    prueba fijaba 409,5 °C."""
    assert converters.convert_temperatures(_ai([0, 4095]), cfg_modbus)[:2] == [0.0, None]


@pytest.mark.req("MOD-04")
@pytest.mark.parametrize("micro_a,kpa", [(4000, 0.0), (20000, 400.0), (12000, 200.0),
                                         (8000, 100.0), (16000, 300.0)])
def test_fabrica_modbus_presion_microamperios_a_kpa(cfg_modbus, micro_a, kpa):
    assert converters.convert_pressures(_ai(pres=[micro_a]), cfg_modbus)[0] == kpa


@pytest.mark.req("MOD-04")
def test_umbrales_de_lazo_modbus_3600_y_21000(cfg_modbus):
    calib = cfg_modbus.calibration.factory.pressure[0]
    assert converters.umbrales_falla_presion(calib) == (3600.0, 21000.0)
    # (el caso del tope del ADC de 12 bits del serial se borró: T20-03)


@pytest.mark.req("MOD-03")
@pytest.mark.parametrize("micro_a", [0, 3599, 21001, 25000])
def test_falla_de_lazo_modbus(cfg_modbus, micro_a):
    """0 µA (el módulo entrega 0 por debajo de 3,85 mA) y más de 21 mA:
    falla del transductor tras el debounce, sin lectura (None, nunca 0)."""
    # primero una lectura buena, para ver que la falla no repite el último valor
    assert converters.convert_pressures(_ai(pres=[12000]), cfg_modbus)[0] == 200.0
    salidas = [converters.convert_pressures(_ai(pres=[micro_a]), cfg_modbus)[0]
               for _ in range(converters.DEBOUNCE_LECTURAS_PRESION)]
    assert salidas[-1] is None
    assert converters.presion_en_falla(0) is True


@pytest.mark.req("MOD-03")
@pytest.mark.parametrize("micro_a", [3600, 21000])
def test_en_el_umbral_no_hay_falla(cfg_modbus, micro_a):
    for _ in range(converters.DEBOUNCE_LECTURAS_PRESION + 1):
        v = converters.convert_pressures(_ai(pres=[micro_a]), cfg_modbus)[0]
    assert converters.presion_en_falla(0) is False
    assert v is not None


@pytest.mark.req("MOD-03")
def test_modbus_sin_calibracion_de_fabrica_no_usa_raw_4095():
    """El fallback raw/4095 solo tiene sentido con el ADC de la tarjeta: con
    Modbus y sin calibración de fábrica no hay lectura (falla cerrada)."""
    assert converters.convert_temperatures(_ai([1210]), {})[0] is None
    assert converters.convert_pressures(_ai(pres=[12000]), {})[0] is None


# ── None por canal ─────────────────────────────────────────────────────────

@pytest.mark.req("MOD-03")
@pytest.mark.parametrize("malo", [None, "x", True, float("nan"), float("inf")])
def test_temperatura_none_en_un_canal_no_afecta_a_los_demas(cfg_modbus, malo):
    completo = converters.convert_temperatures(_ai([1210, 1300, 250, 0, 1000, 500]), cfg_modbus)
    for i in range(8):
        converters._ma_temp[i].buffer.clear()
        converters._oe_temp[i].reset()
    con_none = converters.convert_temperatures(_ai([1210, malo, 250, 0, 1000, 500]), cfg_modbus)
    assert con_none[1] is None
    assert [v for i, v in enumerate(con_none) if i != 1] == \
        [v for i, v in enumerate(completo) if i != 1]


@pytest.mark.req("MOD-03")
def test_temperatura_none_reinicia_el_filtro_del_canal(cfg_modbus):
    for _ in range(5):
        converters.convert_temperatures(_ai([1000, 1000]), cfg_modbus)
    assert converters.convert_temperatures(_ai([1000, None]), cfg_modbus)[1] is None
    assert len(converters._ma_temp[1].buffer) == 0 and converters._oe_temp[1].x_prev is None
    # sin el reinicio, la mediana y el filtro mezclarían los 100,0 °C anteriores
    assert converters.convert_temperatures(_ai([1000, 1300]), cfg_modbus)[1] == 130.0
    # el canal 0 siguió filtrando sin cortes
    assert len(converters._ma_temp[0].buffer) == 5


@pytest.mark.req("MOD-03")
def test_presion_none_en_un_canal_no_afecta_a_los_demas(cfg_modbus):
    p = converters.convert_pressures(_ai(pres=[None, 12000, 8000]), cfg_modbus)
    assert p[0] is None and p[1] == 200.0 and p[2] == 100.0


@pytest.mark.req("MOD-03")
def test_presion_none_reinicia_el_filtro_y_no_cuenta_en_el_detector(cfg_modbus):
    for _ in range(5):
        converters.convert_pressures(_ai(pres=[8000, 8000]), cfg_modbus)
    det = converters._det_pres[0]
    # dos lecturas fuera de rango (sin falla declarada todavía)
    converters.convert_pressures(_ai(pres=[0, 8000]), cfg_modbus)
    converters.convert_pressures(_ai(pres=[0, 8000]), cfg_modbus)
    assert det.seguidas == 2 and det.en_falla is False
    p = converters.convert_pressures(_ai(pres=[None, 8000]), cfg_modbus)
    assert p[0] is None and p[1] == 100.0
    assert det.ultimo is None
    assert det.seguidas == 2 and det.en_falla is False      # no contó (DECISIÓN SIN CONFIRMAR)
    assert len(converters._ma_pres[0].buffer) == 0 and converters._oe_pres[0].x_prev is None
    # una lectura buena tras el None: valor exacto (filtros reiniciados)
    assert converters.convert_pressures(_ai(pres=[16000, 8000]), cfg_modbus)[0] == 300.0


@pytest.mark.req("MOD-03")
def test_presion_none_conserva_una_falla_declarada(cfg_modbus):
    for _ in range(converters.DEBOUNCE_LECTURAS_PRESION):
        converters.convert_pressures(_ai(pres=[0]), cfg_modbus)
    assert converters.presion_en_falla(0) is True
    assert converters.convert_pressures(_ai(pres=[None]), cfg_modbus)[0] is None
    assert converters.presion_en_falla(0) is True
    # se levanta con lecturas dentro de rango, como siempre
    for _ in range(converters.DEBOUNCE_LECTURAS_PRESION):
        v = converters.convert_pressures(_ai(pres=[12000]), cfg_modbus)[0]
    assert converters.presion_en_falla(0) is False and v == 200.0


@pytest.mark.req("MOD-03")
def test_indice_faltante_es_none(cfg_modbus):
    assert converters.convert_pressures([1000] * 9, cfg_modbus)[1:] == [None] * 15
    assert converters.convert_temperatures([1000] * 3, cfg_modbus)[3:] == [None] * 5


@pytest.mark.req("MOD-03")
def test_none_no_congela_las_demas_lecturas_en_units():
    """Antes un None lanzaba TypeError en el convertidor y Units dejaba las 16
    lecturas congeladas en silencio."""
    u = Units(CAL_MODBUS)
    u.update_from_serial({"ai": _ai([1210, None], [12000, None]), "ai_seq": 1,
                          "port_open": True, "data_alive": True})
    d = u.get_all()
    assert d["temperature"][:2] == [121.0, None]
    assert d["pressure"][:2] == [200.0, None]
    u.update_from_serial({"ai": _ai([1250, 1300], [12000, 8000]), "ai_seq": 2,
                          "port_open": True, "data_alive": True})
    d = u.get_all()
    assert d["temperature"][1] == 130.0 and d["pressure"][1] == 100.0


@pytest.mark.req("MOD-03")
def test_estado_inicial_del_enlace_no_es_cero_grados():
    """ai_seq 0 es el estado inicial (nunca una trama real): con Modbus sus
    ceros no se publican como 0,0 °C."""
    u = Units(CAL_MODBUS)
    u.update_from_serial({"ai": [0] * 16, "ai_seq": 0, "port_open": True, "data_alive": True})
    assert u.get_all()["temperature"] == [None] * 8


# ── piso de señal (MOD-04) ─────────────────────────────────────────────────

def _alimentar(u, micro_a, veces=Units.TRAMAS_SENAL_PRESION):
    for _ in range(veces):
        u.update_from_serial({"ai": _ai([1000], [micro_a]), "port_open": True,
                              "data_alive": True})


@pytest.mark.req("MOD-04")
def test_piso_de_senal_3850():
    u = Units(CAL_MODBUS)
    assert u._piso_adc_presion(0) == 3850
    _alimentar(u, 3850)
    assert u.senal_presion_presente(0) is False         # señal: estrictamente mayor
    _alimentar(u, 3851)
    assert u.senal_presion_presente(0) is True
    _alimentar(u, 0, veces=1)
    assert u.senal_presion_presente(0) is False


@pytest.mark.req("MOD-04")
def test_sin_adc_piso_senal_se_usa_adc_min(tmp_path):
    # T20-03: antes con calibration.yaml (serial, retirada); ahora con la
    # calibración Modbus sin adc_piso_senal
    texto = CAL_MODBUS.read_text(encoding="utf-8")
    sin_piso = "\n".join(l for l in texto.splitlines() if "adc_piso_senal" not in l)
    assert sin_piso != texto
    ruta = tmp_path / "calibration_modbus.yaml"
    ruta.write_text(sin_piso, encoding="utf-8")
    u = Units(ruta)
    assert u._config.calibration.factory.pressure[0].adc_piso_senal is None
    assert u._piso_adc_presion(0) == u._config.calibration.factory.pressure[0].adc_min


@pytest.mark.req("MOD-04")
def test_esquema_adc_piso_senal():
    from pydantic import ValidationError
    from autoclave.config.schema import FactorySensorCalibration
    assert FactorySensorCalibration().adc_piso_senal is None
    assert FactorySensorCalibration(adc_piso_senal=3850).adc_piso_senal == 3850
    with pytest.raises(ValidationError):
        FactorySensorCalibration(adc_piso_senal=-1)


def test_calibracion_modbus_valida_y_neutra(cfg_modbus):
    cal = cfg_modbus.calibration
    assert len(cal.factory.temperature) == 8 and len(cal.factory.pressure) == 16   # AIN-04
    assert all(c.adc_min == 0 and c.adc_max == 1000 and c.temp_min == 0 and c.temp_max == 100
               for c in cal.factory.temperature)
    assert all(c.adc_min == 4000 and c.adc_max == 20000 and c.pres_min == 0
               and c.pres_max == 400 and c.adc_piso_senal == 3850
               for c in cal.factory.pressure)
    for lista, n in ((cal.user.temperature, 8), (cal.user.pressure, 16)):
        assert len(lista) == n
        assert all(s.gain == 1.0 and s.offset == 0.0 and not s.poly for s in lista)
    assert not math.isnan(cal.factory.pressure[0].margen_falla_alto)

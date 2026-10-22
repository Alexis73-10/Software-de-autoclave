"""S1 (tanda 8, D8-1.1): detección de transductor de presión 4-20 mA sin señal
sobre la señal CRUDA (cuentas ADC), antes de calibrar y recortar.

Umbrales NAMUR NE43 traducidos con la calibración de fábrica del canal
(adc_min = 4 mA, adc_max = 20 mA):
    bajo = adc_min - margen_falla_bajo * (adc_max - adc_min)
    alto = adc_max + margen_falla_alto * (adc_max - adc_min)
3 lecturas seguidas fuera de rango declaran la falla y 3 dentro la levantan.
En falla el canal entrega None, nunca 0."""

import pytest

from autoclave.config.schema import AppConfig, FactorySensorCalibration
from autoclave.hal.measures import converters
from autoclave.hal.measures.units import Units

N = converters.DEBOUNCE_LECTURAS_PRESION


def _config(adc_min=819, adc_max=3276, **extra):
    """Canal 0 de presión con una calibración de fábrica 4-20 mA típica
    (0-20 mA en 0-4095: 4 mA = 819, 20 mA = 3276)."""
    cfg = AppConfig()
    cfg.calibration.factory.pressure[0] = FactorySensorCalibration(
        adc_min=adc_min, adc_max=adc_max, pres_min=0.0, pres_max=400.0, **extra)
    return cfg


def _raw(cuentas):
    return [0] * 8 + [cuentas] + [0] * 7


@pytest.fixture(autouse=True)
def _limpio():
    converters.reiniciar_presiones()
    yield
    converters.reiniciar_presiones()


def _leer(cfg, cuentas, veces=1, nueva=True):
    v = None
    for _ in range(veces):
        v = converters.convert_pressures(_raw(cuentas), cfg, nueva_muestra=nueva)[0]
    return v


def test_umbrales_namur_con_los_margenes_por_defecto():
    calib = _config().calibration.factory.pressure[0]
    bajo, alto = converters.umbrales_falla_presion(calib)
    span = 3276 - 819
    assert bajo == pytest.approx(819 - 0.025 * span)       # 3,6 mA
    assert alto == pytest.approx(3276 + 0.0625 * span)     # 21 mA


def test_margenes_son_parametros_de_configuracion():
    calib = _config(margen_falla_bajo=0.1, margen_falla_alto=0.02).calibration.factory.pressure[0]
    bajo, alto = converters.umbrales_falla_presion(calib)
    span = 3276 - 819
    assert bajo == pytest.approx(819 - 0.1 * span)
    assert alto == pytest.approx(3276 + 0.02 * span)


def test_lazo_abierto_bajo_declara_falla_tras_3_lecturas_y_entrega_none():
    cfg = _config()
    assert _leer(cfg, 2000, veces=5) is not None
    for i in range(N - 1):
        v = _leer(cfg, 0)
        assert v is not None and v > 0, "antes de 3 lecturas sigue el último valor"
    assert _leer(cfg, 0) is None
    assert converters.presion_en_falla(0) is True
    # nunca 0 mientras dura la falla
    assert _leer(cfg, 0, veces=10) is None


def test_sobrecorriente_alta_declara_falla():
    cfg = _config()
    _leer(cfg, 2000, veces=5)
    assert _leer(cfg, 4000, veces=N) is None


def test_una_o_dos_lecturas_fuera_no_declaran_falla_y_se_reinicia_el_conteo():
    cfg = _config()
    _leer(cfg, 2000, veces=5)
    _leer(cfg, 0, veces=N - 1)
    assert _leer(cfg, 2000) is not None
    _leer(cfg, 0, veces=N - 1)
    assert converters.presion_en_falla(0) is False


def test_recuperacion_exige_3_lecturas_dentro():
    cfg = _config()
    _leer(cfg, 0, veces=N)
    assert converters.presion_en_falla(0)
    for _ in range(N - 1):
        assert _leer(cfg, 2000) is None
    v = _leer(cfg, 2000)
    assert v is not None and v > 0
    assert converters.presion_en_falla(0) is False


def test_recuperacion_interrumpida_reinicia_el_conteo():
    cfg = _config()
    _leer(cfg, 0, veces=N)
    _leer(cfg, 2000, veces=N - 1)
    _leer(cfg, 0)
    assert _leer(cfg, 2000, veces=N - 1) is None


def test_al_recuperar_no_arrastra_el_valor_previo_del_filtro():
    """Tras la falla los filtros arrancan de cero (como la temperatura)."""
    cfg = _config()
    _leer(cfg, 3000, veces=20)
    _leer(cfg, 0, veces=N)
    v = _leer(cfg, 1000, veces=N)
    esperado = (1000 - 819) * 400.0 / (3276 - 819)
    assert v == pytest.approx(esperado, abs=0.5)


def test_las_muestras_fuera_de_rango_no_entran_al_filtro():
    cfg = _config()
    _leer(cfg, 2000, veces=10)
    previo = _leer(cfg, 2000)
    assert _leer(cfg, 0) == pytest.approx(previo, abs=0.05)


def test_sin_muestra_nueva_no_avanza_el_conteo():
    """Units notifica también por tramas DI/DO con la misma AI: solo una trama
    AI nueva cuenta como lectura."""
    cfg = _config()
    _leer(cfg, 2000, veces=5)
    _leer(cfg, 0)                         # 1 lectura nueva
    _leer(cfg, 0, veces=10, nueva=False)  # repeticiones de la misma trama
    assert converters.presion_en_falla(0) is False
    _leer(cfg, 0, veces=N - 1)
    assert converters.presion_en_falla(0) is True


def test_primera_lectura_fuera_sin_valor_previo_es_none_nunca_cero():
    cfg = _config()
    assert _leer(cfg, 0) is None


def test_tarjeta_que_satura_en_4095_antes_de_21_ma_deja_inactiva_la_alta():
    cfg = _config(adc_min=5, adc_max=4050)
    calib = cfg.calibration.factory.pressure[0]
    _, alto = converters.umbrales_falla_presion(calib)
    assert alto is None
    _leer(cfg, 2000, veces=5)
    assert _leer(cfg, 4095, veces=N + 2) is not None


def test_piso_de_saturacion_cuando_el_umbral_bajo_queda_bajo_cero():
    """Calibración real del equipo (adc_min 5): 3,6 mA cae por debajo de 0
    cuentas; el lazo abierto se ve como 0 cuentas (piso de saturación)."""
    cfg = _config(adc_min=5, adc_max=4050)
    _leer(cfg, 2000, veces=5)
    assert _leer(cfg, 3, veces=N) is not None      # dentro (sobre el piso)
    assert _leer(cfg, 0, veces=N) is None


def test_umbral_explicito_en_cuentas_reemplaza_el_calculado():
    cfg = _config(adc_min=5, adc_max=4050, adc_falla_bajo=20, adc_falla_alto=4080)
    calib = cfg.calibration.factory.pressure[0]
    assert converters.umbrales_falla_presion(calib) == (20, 4080)
    _leer(cfg, 2000, veces=5)
    assert _leer(cfg, 12, veces=N) is None
    converters.reiniciar_presiones()
    _leer(cfg, 2000, veces=5)
    assert _leer(cfg, 4090, veces=N) is None


def test_canal_sin_calibracion_de_fabrica_conserva_el_comportamiento_previo():
    cfg = AppConfig()
    assert converters.umbrales_falla_presion(cfg.calibration.factory.pressure[0]) == (None, None)
    v = converters.convert_pressures(_raw(0), {})[0]
    assert v == 0.0


def test_units_arranca_sin_lectura_de_presion():
    u = Units()
    assert u.get_all()["pressure"] == [None] * 8


def test_units_solo_cuenta_tramas_ai_nuevas(tmp_path):
    u = Units()
    u._config = _config()
    base = {"port_open": True, "data_alive": True}
    u.update_from_serial({**base, "ai": _raw(2000), "ai_seq": 1})
    u.update_from_serial({**base, "ai": _raw(2000), "ai_seq": 2})
    for _ in range(5):          # la misma trama AI notificada por DI/DO
        u.update_from_serial({**base, "ai": _raw(0), "ai_seq": 3})
    assert u.get_pressure(0) is not None
    u.update_from_serial({**base, "ai": _raw(0), "ai_seq": 4})
    u.update_from_serial({**base, "ai": _raw(0), "ai_seq": 5})
    assert u.get_pressure(0) is None

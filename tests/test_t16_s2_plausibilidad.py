"""Tanda 16, s2: P7 / D-14.7, filtro de plausibilidad de las lecturas vivas en
EstadoAutoclave.update()."""
import logging
import math

import pytest

from autoclave.core.managers.catalogo_parametros import CALIBRACION_PLAUSIBLE
from autoclave.core.runtime import status as status_mod
from autoclave.core.runtime.status import EstadoAutoclave

pytestmark = pytest.mark.req("T16-S2")

_LOGGER = status_mod.__name__


def _temps(t0, t1=120.0, t2=120.0, t4=40.0):
    return {"temperature": [t0, t1, t2, 0.0, t4, 0.0]}


def test_rangos_coinciden_con_calibracion_plausible():
    assert status_mod.RANGO_PLAUSIBLE_TEMP_C == CALIBRACION_PLAUSIBLE["temperature"]["rango"]
    assert status_mod.RANGO_PLAUSIBLE_PRES_KPA == CALIBRACION_PLAUSIBLE["pressure"]["rango"]


def test_temperatura_fuera_de_rango_se_publica_como_none():
    e = EstadoAutoclave()
    e.update({"temperature": [200.1, -0.1, 134.0, 0.0, 250.0, 0.0]})
    assert e.sensores_temp["temp_camara"] is None
    assert e.sensores_temp["temp_2_camara"] is None
    assert e.sensores_temp["temp_ref"] == 134.0
    assert e.sensores_temp["temp_drenaje"] is None


def test_bordes_de_temperatura_son_validos_y_cero_no_cambia():
    e = EstadoAutoclave()
    e.update({"temperature": [0.0, 200.0, 0, 0.0, 199.9, 0.0]})
    assert e.sensores_temp["temp_camara"] == 0.0
    assert e.sensores_temp["temp_2_camara"] == 200.0
    assert e.sensores_temp["temp_ref"] == 0
    assert e.sensores_temp["temp_drenaje"] == 199.9


def test_presion_fuera_de_rango_se_publica_como_none():
    e = EstadoAutoclave()
    e.update({"pressure": [450.1, -10.1, -10.0, 450.0]})
    assert e.sensores_pres["pres_camara"] is None
    assert e.sensores_pres["pres_chaqueta"] is None
    assert e.sensores_pres["pres_empaque_1"] == -10.0
    assert e.sensores_pres["pres_empaque_2"] == 450.0


def test_no_numerico_y_no_finito_pasan_como_antes():
    e = EstadoAutoclave()
    e.update({"temperature": [float("nan"), None, "x", 0.0, float("inf"), 0.0],
              "pressure": [float("-inf"), None, True, 100.0]})
    assert math.isnan(e.sensores_temp["temp_camara"])
    assert e.sensores_temp["temp_2_camara"] is None
    assert e.sensores_temp["temp_ref"] == "x"
    assert e.sensores_temp["temp_drenaje"] == float("inf")
    assert e.sensores_pres["pres_camara"] == float("-inf")
    assert e.sensores_pres["pres_empaque_1"] is True


def test_lista_corta_sigue_ignorando_el_faltante():
    e = EstadoAutoclave()
    e.update({"temperature": [130.0, 131.0, 132.0, 0.0, 40.0, 0.0]})
    e.update({"temperature": [500.0]})
    assert e.sensores_temp["temp_camara"] is None
    assert e.sensores_temp["temp_2_camara"] == 131.0


def test_log_una_vez_por_episodio_y_canal(caplog):
    caplog.set_level(logging.INFO, logger=_LOGGER)
    e = EstadoAutoclave()
    for _ in range(3):
        e.update(_temps(250.0))
    avisos = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(avisos) == 1
    assert "temp_camara" in avisos[0].getMessage()
    assert "250.0" in avisos[0].getMessage()

    caplog.clear()
    e.update(_temps(130.0))
    infos = [r for r in caplog.records if r.levelno == logging.INFO]
    assert len(infos) == 1 and "temp_camara" in infos[0].getMessage()
    assert e.sensores_temp["temp_camara"] == 130.0

    caplog.clear()
    e.update(_temps(-50.0))
    e.update(_temps(-51.0))
    avisos = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(avisos) == 1 and "-50.0" in avisos[0].getMessage()


def test_episodios_independientes_por_canal(caplog):
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    e = EstadoAutoclave()
    e.update({"temperature": [250.0, 120.0, 120.0, 0.0, 40.0, 0.0],
              "pressure": [500.0, 100.0, 100.0, 100.0]})
    e.update({"temperature": [250.0, 300.0, 120.0, 0.0, 40.0, 0.0],
              "pressure": [500.0, 100.0, 100.0, 100.0]})
    canales = sorted(r.getMessage().split(" = ")[0].split(": ")[-1] for r in caplog.records)
    assert canales == ["pres_camara", "temp_2_camara", "temp_camara"]


def test_sin_lectura_intermedia_no_rearma_el_episodio(caplog):
    caplog.set_level(logging.INFO, logger=_LOGGER)
    e = EstadoAutoclave()
    e.update(_temps(250.0))
    e.update(_temps(None))
    e.update(_temps(250.0))
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1
    assert not [r for r in caplog.records if r.levelno == logging.INFO]

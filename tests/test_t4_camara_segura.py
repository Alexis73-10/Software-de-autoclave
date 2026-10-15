"""T4 (E2, tanda 2026-10-14): cámara segura con el sensor Principal, "NO ABRIR"
en /status y condición de inicio de ciclo (planeacion_fin_de_ciclo_y_puertas §5)."""

import math
from types import SimpleNamespace

import pytest

from autoclave.core.runtime.camara_segura import evaluar

_CFG = {"presion_admosferica": 101.3, "rango_presion_atm": 10.0, "temp_max_apertura": 80.0}


def _estado(pres=101.3, **temps):
    t = {"temp_camara": 40.0, "temp_2_camara": 40.0, "temp_ref": 40.0}
    t.update(temps)
    return SimpleNamespace(sensores_pres={"pres_camara": pres}, sensores_temp=t)


class _Config(dict):
    def get(self, k, default=None):
        return super().get(k, default)


def test_segura_en_rango():
    assert evaluar(_estado(), _Config(_CFG), None) == (True, "")


@pytest.mark.parametrize("pres,motivo", [
    (120.0, "Sobrepresión"), (80.0, "vacío"), (None, "presión"), (math.nan, "presión")])
def test_presion_fuera_o_ausente_no_es_segura(pres, motivo):
    segura, texto = evaluar(_estado(pres=pres), _Config(_CFG), None)
    assert segura is False and motivo in texto


@pytest.mark.parametrize("temp", [80.1, None, math.inf])
def test_temperatura_alta_o_ausente_no_es_segura(temp):
    segura, _ = evaluar(_estado(temp_camara=temp), _Config(_CFG), None)
    assert segura is False


def test_limite_exacto_es_seguro():
    assert evaluar(_estado(pres=111.3, temp_camara=80.0), _Config(_CFG), None)[0] is True


@pytest.mark.parametrize("falta", list(_CFG))
def test_sin_configuracion_falla_cerrada(falta):
    cfg = _Config({k: v for k, v in _CFG.items() if k != falta})
    segura, texto = evaluar(_estado(), cfg, None)
    assert segura is False and falta in texto


def test_usa_el_sensor_principal_del_programa():
    programa = SimpleNamespace(sensores={"temp_camara": "no_en_uso",
                                         "temp_2_camara": "principal", "temp_ref": "no_en_uso"})
    estado = _estado(temp_camara=30.0, temp_2_camara=95.0)
    assert evaluar(estado, _Config(_CFG), programa)[0] is False
    estado = _estado(temp_camara=None, temp_2_camara=30.0)    # temp_camara no en uso
    assert evaluar(estado, _Config(_CFG), programa)[0] is True


def test_principal_none_no_es_segura_aunque_otra_sonda_lea():
    programa = SimpleNamespace(sensores={"temp_camara": "no_en_uso",
                                         "temp_2_camara": "no_en_uso", "temp_ref": "principal"})
    assert evaluar(_estado(temp_ref=None), _Config(_CFG), programa)[0] is False

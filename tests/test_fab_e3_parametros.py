# tests/test_fab_e3_parametros.py
#
# Modo fábrica, Etapa 3 (D-08, FAB-08, P-03): parámetros del equipo de
# fábrica (`parametros_fabrica_equipo.json`) como valor de fábrica de
# ConfigManager. Carpeta de datos en tmp_path; nunca toca data/ del repo.

import json
import logging

import pytest

from autoclave.core.managers.config_manager import ConfigManager
from autoclave.core.runtime import fabrica_equipo as fe
from autoclave.utils.resources import resource_path


class _BdDoble:
    """system_params en memoria."""

    def __init__(self):
        self.filas = {}

    def listar_parametros_sistema(self):
        return dict(self.filas)

    def guardar_parametro_sistema(self, clave, valor, defecto, minimo, maximo, usuario="", fecha=None):
        self.filas[clave] = {"valor": valor, "usuario": usuario, "fecha": fecha}


@pytest.fixture
def datos(tmp_path, monkeypatch):
    monkeypatch.setattr(fe, "carpeta_datos", lambda: tmp_path)
    return tmp_path


def _genericos() -> dict:
    with open(resource_path("autoclave/config/global_params.json"), encoding="utf-8") as f:
        return {k: v["value"] for k, v in json.load(f).items()}


def _cm(bd=None) -> ConfigManager:
    c = ConfigManager()
    c.load_config()
    if bd is not None:
        c.vincular_bd(bd)
    return c


def _escribir(datos, contenido) -> None:
    texto = contenido if isinstance(contenido, str) else json.dumps(contenido)
    (datos / fe.NOMBRE_PARAMETROS).write_text(texto, encoding="utf-8")


def test_ruta_en_la_carpeta_de_datos(datos):
    assert fe.ruta_parametros() == datos / "parametros_fabrica_equipo.json"
    assert fe.ruta_calibracion() == datos / "calibracion_fabrica_equipo.yaml"


def test_sin_archivo_todo_igual(datos):
    c = _cm()
    gen = _genericos()
    assert {k: c._fabrica[k] for k in gen} == gen
    assert c.get("timeout_puerta") == gen["timeout_puerta"]


def test_archivo_valido_reemplaza_el_generico(datos):
    _escribir(datos, {"timeout_puerta": 90, "presion_atmosferica": 74.6,
                      "presion_suministro_vapor": 340})
    c = _cm()
    assert c._fabrica["timeout_puerta"] == 90
    assert c._fabrica["presion_atmosferica"] == 74.6          # solo lectura también
    assert c.describir("timeout_puerta")["defecto"] == 90
    # sin base rigen los de fábrica: los del equipo
    assert c.get("timeout_puerta") == 90
    assert c.get("presion_suministro_vapor") == 340
    # lo que no trae el archivo sigue con el genérico
    assert c._fabrica["temp_max_apertura"] == _genericos()["temp_max_apertura"]


def test_alias_aceptado(datos):
    _escribir(datos, {"presion_admosferica": 76.0})
    assert _cm()._fabrica["presion_atmosferica"] == 76.0


def test_p03_restablecer_da_el_valor_del_equipo(datos):
    bd = _BdDoble()
    c = _cm(bd)
    c.fijar("timeout_puerta", 90)
    c.fijar("temp_max_apertura", 75)
    # el cierre consolida los vigentes
    escritos = fe.escribir_parametros_fabrica_equipo(c)
    assert escritos["timeout_puerta"] == 90
    assert json.loads(fe.ruta_parametros().read_text(encoding="utf-8"))["temp_max_apertura"] == 75
    # en campo: arranque nuevo, cambio y restaurar
    bd2 = _BdDoble()
    c2 = _cm(bd2)
    c2.fijar("timeout_puerta", 200)
    anterior, nuevo = c2.restablecer("timeout_puerta")
    assert (anterior, nuevo) == (200, 90)
    assert c2.get("timeout_puerta") == 90
    assert c2.restablecer("temp_max_apertura")[1] == 75
    assert c2._fabrica["timeout_puerta"] != _genericos()["timeout_puerta"]


def test_escritura_atomica_sin_temporales(datos):
    fe.escribir_parametros_fabrica_equipo(_cm(_BdDoble()), datos / "x.json")
    assert sorted(p.name for p in datos.iterdir()) == ["x.json"]


def test_clave_desconocida_y_valor_invalido_se_ignoran(datos, caplog):
    _escribir(datos, {"no_existe": 3, "timeout_puerta": 9999, "temp_max_apertura": "alto",
                      "max_aislamientos_camara": 2.5, "tiempo_standby": 20})
    with caplog.at_level(logging.WARNING):
        c = _cm()
    gen = _genericos()
    assert c._fabrica["timeout_puerta"] == gen["timeout_puerta"]
    assert c._fabrica["temp_max_apertura"] == gen["temp_max_apertura"]
    assert c._fabrica["max_aislamientos_camara"] == gen["max_aislamientos_camara"]
    assert "no_existe" not in c._fabrica
    assert c._fabrica["tiempo_standby"] == 20                 # la válida sí se aplica
    texto = caplog.text
    assert "no_existe" in texto and "timeout_puerta" in texto


@pytest.mark.parametrize("contenido", [
    {"presion_suministro_vapor": 390},                         # suministro >= alivio
    {"presion_alivio_camara": 395, "presion_fondo_escala": 390},  # alivio > fondo
    {"presion_max_chaqueta_control": 380},                     # corte > alivio chaqueta - 10
    {"presion_empaque": 100},                                  # empaque < atm + 20
])
def test_incoherente_se_ignora_entero(datos, caplog, contenido):
    _escribir(datos, {"timeout_puerta": 90, **contenido})
    with caplog.at_level(logging.WARNING):
        c = _cm()
    gen = _genericos()
    assert {k: c._fabrica[k] for k in gen} == gen
    assert c.get("timeout_puerta") == gen["timeout_puerta"]
    assert "incoherente" in caplog.text


@pytest.mark.parametrize("texto", ["{no es json", "[1, 2]", ""])
def test_ilegible_rigen_los_genericos(datos, caplog, texto):
    _escribir(datos, texto)
    with caplog.at_level(logging.WARNING):
        c = _cm()
    gen = _genericos()
    assert {k: c._fabrica[k] for k in gen} == gen


def test_ruta_explicita(tmp_path):
    ruta = tmp_path / "otra.json"
    ruta.write_text('{"timeout_puerta": 100}', encoding="utf-8")
    c = ConfigManager()
    c.load_config(ruta_fabrica_equipo=ruta)
    assert c._fabrica["timeout_puerta"] == 100


def test_fila_de_la_base_sigue_mandando_sobre_el_valor(datos):
    _escribir(datos, {"timeout_puerta": 90})
    bd = _BdDoble()
    bd.filas["timeout_puerta"] = {"valor": 120, "usuario": "u", "fecha": "2026-11-22T00:00:00"}
    c = _cm(bd)
    assert c.get("timeout_puerta") == 120
    assert c.describir("timeout_puerta")["defecto"] == 90
    assert c.restablecer("timeout_puerta")[1] == 90

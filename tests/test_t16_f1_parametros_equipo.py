# tests/test_t16_f1_parametros_equipo.py
#
# F1 (tanda 16): parámetros del equipo nuevos (VCH-AIS, D-CHQ, DEU-01) en
# global_params.json, sus lectores con recorte y defecto
# (core/managers/limites_equipo.py) y la regla de coherencia de los límites
# de presión en el ConfigManager.

import json
from pathlib import Path

import pytest

from autoclave.core.managers import limites_equipo as le
from autoclave.core.managers.config_manager import ConfigManager, ErrorParametro, GRUPOS

pytestmark = pytest.mark.req("T16-F1")

RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave"
FABRICA = json.loads((RAIZ / "config" / "global_params.json").read_text(encoding="utf-8"))

ESPERADO = {
    "timeout_aislamiento_camara": ("chaqueta", 3, 1, 10),
    "max_aislamientos_camara": ("chaqueta", 6, 2, 20),
    "ventana_aislamientos_camara": ("chaqueta", 15, 5, 60),
    "presion_max_chaqueta_control": ("chaqueta", 375, 300, 990),
    "presion_fondo_escala": ("chaqueta", 400, 100, 1000),
    "presion_suministro_vapor": ("chaqueta", 350, 100, 1000),
    "presion_alivio_camara": ("chaqueta", 385, 100, 1000),
    "presion_alivio_chaqueta": ("chaqueta", 385, 100, 1000),
}


class _Config:
    def __init__(self, **valores):
        self.valores = valores

    def get(self, clave, default=None):
        return self.valores.get(clave, default)


@pytest.mark.parametrize("clave", sorted(ESPERADO))
def test_fabrica(clave):
    grupo, defecto, minimo, maximo = ESPERADO[clave]
    e = FABRICA[clave]
    assert (e["grupo"], e["value"], e["min"], e["max"]) == (grupo, defecto, minimo, maximo)
    assert e["grupo"] in GRUPOS


def test_defectos_sin_config():
    assert le.limites_presion(None) == le.LimitesPresion(400.0, 350.0, 385.0, 385.0)
    assert le.presion_max_chaqueta_control(None) == 375.0
    assert le.timeout_aislamiento_camara_s(None) == 180.0
    assert le.max_aislamientos_camara(None) == 6
    assert le.ventana_aislamientos_camara_s(None) == 900.0


@pytest.mark.parametrize("valor", [None, "x", True, float("nan"), float("inf")])
def test_valor_invalido_usa_defecto(valor):
    cfg = _Config(timeout_aislamiento_camara=valor, max_aislamientos_camara=valor,
                  ventana_aislamientos_camara=valor, presion_max_chaqueta_control=valor,
                  presion_alivio_camara=valor)
    assert le.timeout_aislamiento_camara_s(cfg) == 180.0
    assert le.max_aislamientos_camara(cfg) == 6
    assert le.ventana_aislamientos_camara_s(cfg) == 900.0
    assert le.presion_max_chaqueta_control(cfg) == 375.0
    assert le.limites_presion(cfg).alivio_camara == 385.0


def test_recorte_al_rango():
    cfg = _Config(timeout_aislamiento_camara=0, max_aislamientos_camara=99,
                  ventana_aislamientos_camara=1000, presion_max_chaqueta_control=200)
    assert le.timeout_aislamiento_camara_s(cfg) == 60.0
    assert le.max_aislamientos_camara(cfg) == 20
    assert le.ventana_aislamientos_camara_s(cfg) == 3600.0
    assert le.presion_max_chaqueta_control(cfg) == 300.0


def test_corte_chaqueta_bajo_el_alivio():
    """D-CHQ: el corte nunca queda a menos de 10 kPa del alivio de chaqueta."""
    cfg = _Config(presion_max_chaqueta_control=999, presion_alivio_chaqueta=360)
    assert le.presion_max_chaqueta_control(cfg) == 350.0
    # el defecto también se recorta con un alivio bajo
    assert le.presion_max_chaqueta_control(_Config(presion_alivio_chaqueta=360)) == 350.0


def test_limites_vigentes_y_recorte():
    cfg = _Config(presion_fondo_escala=600, presion_suministro_vapor=300,
                  presion_alivio_camara=500, presion_alivio_chaqueta=450)
    assert le.limites_presion(cfg) == le.LimitesPresion(600.0, 300.0, 500.0, 450.0)
    cfg = _Config(presion_fondo_escala=5000, presion_suministro_vapor=350,
                  presion_alivio_camara=385, presion_alivio_chaqueta=385)
    assert le.limites_presion(cfg).fondo_escala == 1000.0


@pytest.mark.parametrize("valores", [
    dict(presion_suministro_vapor=390),            # suministro >= alivio
    dict(presion_alivio_camara=410),               # alivio > fondo
    dict(presion_alivio_chaqueta=350),             # alivio == suministro
])
def test_limites_incoherentes_rigen_los_de_fabrica(valores):
    base = dict(presion_fondo_escala=400, presion_suministro_vapor=350,
                presion_alivio_camara=385, presion_alivio_chaqueta=385)
    base.update(valores)
    assert le.limites_presion(_Config(**base)) == le.LIMITES_DEFECTO


# ── ConfigManager: coherencia al guardar ─────────────────────────────────

@pytest.fixture
def cm(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    c = ConfigManager()
    c.load_config()
    d = DbManager(db_path=tmp_path / "t.db")
    c.vincular_bd(d)
    yield c
    d.close()


@pytest.mark.parametrize("clave,valor", [
    ("presion_suministro_vapor", 385),      # suministro == alivio
    ("presion_alivio_camara", 401),         # alivio sobre el fondo de escala
    ("presion_fondo_escala", 380),          # fondo bajo los alivios
    ("presion_alivio_chaqueta", 380),       # corte 375 > 380 - 10
    ("presion_max_chaqueta_control", 376),  # corte > alivio 385 - 10
])
def test_config_manager_rechaza_incoherentes(cm, clave, valor):
    with pytest.raises(ErrorParametro) as e:
        cm.fijar(clave, valor, "ing")
    assert e.value.codigo == "incoherente"


def test_config_manager_acepta_coherentes(cm):
    assert cm.fijar("presion_max_chaqueta_control", 370, "ing")[1] == 370
    assert cm.fijar("presion_alivio_chaqueta", 380, "ing")[1] == 380
    assert cm.fijar("presion_fondo_escala", 500, "ing")[1] == 500
    assert cm.fijar("presion_alivio_camara", 450, "ing")[1] == 450
    assert le.limites_presion(cm) == le.LimitesPresion(500.0, 350.0, 450.0, 380.0)
    assert le.presion_max_chaqueta_control(cm) == 370.0

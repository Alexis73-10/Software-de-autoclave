"""PRI-01..04 (9-nov): programa de fábrica 6, Prion 134 °C / 30 min."""
import copy
import json
import logging
from pathlib import Path

import pytest

from autoclave import i18n
from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import CycleManager
from tests.helpers import planta_vapor as pv

pytestmark = pytest.mark.req("PRI")

CICLOS = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "cycles"
CAMBIOS = {("esterilizacion", "tiempo_esterilizacion"): 30,
           ("secado", "tiempo_secado"): 30}


def _json(carpeta, nombre):
    return json.loads((CICLOS / carpeta / nombre).read_text(encoding="utf-8"))


@pytest.mark.parametrize("carpeta", ["factory", "user"])
def test_valores_pri02_pri03(carpeta):
    d = _json(carpeta, "prion.json")
    assert (d["cycle_id"], d["cycle_number"], d["display_name"]) == ("prion", 6, "Prion 134°C")
    p = d["parameters"]
    assert p["esterilizacion"]["temperatura_esterilizacion"]["value"] == 134
    assert p["esterilizacion"]["tiempo_esterilizacion"]["value"] == 30
    assert p["secado"]["tiempo_secado"]["value"] == 30 <= p["secado"]["tiempo_secado"]["max"]
    assert p["globals"]["F0"]["value"] is False
    assert p["globals"]["tipo_carga"]["value"] == "solido"
    assert p["finalizacion"]["apertura_automatica"]["value"] is False


def test_nombre_clave_solo_en_fabrica():
    assert _json("factory", "prion.json")["nombre_clave"] == "ciclos_fabrica.prion.nombre"
    assert "nombre_clave" not in _json("user", "prion.json")


@pytest.mark.parametrize("carpeta", ["factory", "user"])
def test_igual_a_instrumental_134_salvo_lo_listado(carpeta):
    base, prion = _json(carpeta, "instrumental_134.json"), _json(carpeta, "prion.json")
    esperado = copy.deepcopy(base)
    for k in ("cycle_id", "cycle_number", "display_name", "nombre_clave"):
        esperado.pop(k, None)
        prion = {a: b for a, b in prion.items()}
    for (sec, clave), v in CAMBIOS.items():
        esperado["parameters"][sec][clave]["value"] = v
    obtenido = {k: v for k, v in prion.items()
                if k not in ("cycle_id", "cycle_number", "display_name", "nombre_clave")}
    assert obtenido == esperado


def test_i18n_es_en():
    for idioma in ("es", "en"):
        assert i18n.t("ciclos_fabrica.prion.nombre", idioma) == "Prion 134°C"


def test_carga_limpia_numero_6_de_fabrica_sin_migraciones():
    cm = CycleManager()
    cm.load_all_cycles()
    c = cm.cycles["prion"]
    assert c.number == 6 and not getattr(c, "danado", None)
    assert cp.errores_programa(c.parameters) == []
    assert cp.errores_brecha_recuperacion(c.parameters) == []
    assert not c.migraciones_correctivas and not c.migraciones_no_aplicadas
    assert cm.errores_carga == []
    assert cm.fabrica[6].id == "prion"
    assert sorted(x.number for x in cm.cycles.values()) == [1, 2, 3, 4, 5, 6]


@pytest.fixture
def _sin_log():
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


@pytest.mark.parametrize("modo", ["camara", "chaqueta"])
def test_planta_ciclo_completo_caudal_abierto(modo, monkeypatch, _sin_log):
    """Planta simulada (provisional): CALENTAMIENTO y ESTERILIZACION (el
    secado no se modela). 30 min de exposición, sin aislamientos."""
    prog = pv._programa(CICLOS / "factory" / "prion.json")
    r = pv.simular(modo, prog, limite_s=9000.0, monkeypatch=monkeypatch,
                   planta_kw=dict(ajustes=dict(pv.VARIANTES_CAUDAL["abierto"])))
    assert r.resultado == "COMPLETADO", (r.resultado, r.motivo, r.alarma)
    assert r.aislamientos == 0
    assert 30 * 60 <= len(r.ester()) * pv.DT <= 30 * 60 + 5
    assert r.t_min_ester >= 134.0 - 0.1

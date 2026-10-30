"""J12 (tanda 12): valores de los 8 JSON de programa.

C-07.1: brecha_segura_temperatura = 1.0. C-13.4: esterilizacion.
timeout_excursion_referencia = 5 min (int, 1–30). C-05.3: globals.
delta_temp_chaqueta = 1.5 y margen_flujo_chaqueta = 15. Los 8 cargan sin
errores y ningún programa de fábrica queda rechazado (T10)."""

import glob
import json
from pathlib import Path

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import CycleManager, migrar_parametros

RAIZ = Path(__file__).resolve().parents[1]
PROGRAMAS = sorted(glob.glob(str(RAIZ / "src" / "autoclave" / "cycles" / "*" / "*.json")))


def test_son_los_8_programas():
    assert len(PROGRAMAS) == 8


@pytest.mark.parametrize("ruta", PROGRAMAS, ids=lambda r: "/".join(Path(r).parts[-2:]))
def test_valores_nuevos(ruta):
    p = json.loads(Path(ruta).read_text(encoding="utf-8"))["parameters"]
    est, g = p["esterilizacion"], p["globals"]
    t = est["timeout_excursion_referencia"]
    assert (t["value"], t["type"], t["unit"], t["min"], t["max"]) == (5, "int", "min", 1, 30)
    d = g["delta_temp_chaqueta"]
    assert (d["value"], d["clase"], d["min"], d["max"]) == (1.5, "diferencia", 0, 5)
    m = g["margen_flujo_chaqueta"]
    assert (m["value"], m["unit"], m["clase"], m["min"], m["max"]) == (15.0, "kPa", "diferencia", 0, 40)
    # nada que migrar en los JSON entregados
    correcciones = []
    assert migrar_parametros(p, correcciones) is False and correcciones == []


@pytest.mark.parametrize("ruta", PROGRAMAS, ids=lambda r: "/".join(Path(r).parts[-2:]))
def test_sin_errores_al_cargar(ruta):
    p = json.loads(Path(ruta).read_text(encoding="utf-8"))["parameters"]
    assert cp.errores_programa(p) == []


def test_ninguno_rechazado_ni_danado_en_la_carga_real():
    cm = CycleManager()
    cm.load_all_cycles()
    assert cm.errores_carga == []
    assert all(not c.danado for c in cm.cycles.values())
    assert all(not c.danado for c in cm.fabrica.values())
    assert cm.migraciones_correctivas() == []
    # sin advertencias en los de fábrica (300 + 50 = 350 no supera el suministro)
    for c in cm.fabrica.values():
        assert cp.advertencias_programa(c.parameters) == []


def test_catalogo_timeout_excursion_referencia():
    hoja = {"type": "int", "min": 1, "max": 30}
    assert cp.coercionar(hoja, "esterilizacion", ["timeout_excursion_referencia"], 1) == 1
    assert cp.coercionar(hoja, "esterilizacion", ["timeout_excursion_referencia"], 30) == 30
    for malo in (0, 31, 5.5):
        with pytest.raises(ValueError):
            cp.coercionar({"type": "int"}, "esterilizacion", ["timeout_excursion_referencia"], malo)


def test_etiquetas_i18n_de_los_parametros_nuevos():
    from autoclave import i18n
    for clave in ("globals.delta_temp_chaqueta", "globals.margen_flujo_chaqueta",
                  "esterilizacion.timeout_excursion_referencia"):
        for idioma in ("es", "en"):
            assert i18n.existe("parametros." + clave, idioma)
            assert i18n.existe("parametros_desc." + clave, idioma)


@pytest.mark.parametrize("ruta", PROGRAMAS, ids=lambda r: "/".join(Path(r).parts[-2:]))
def test_c_07_1_brecha_segura_temperatura_1(ruta):
    """C-07.1: el control apunta a T_est + 1 K, dentro de la banda de +3 K.
    OJO al unir: sin el techo en RECUPERACION de E12 (C-08.3) los ensayos de
    simulador fallan por presión alta (ver informe J12)."""
    p = json.loads(Path(ruta).read_text(encoding="utf-8"))["parameters"]
    assert p["esterilizacion"]["brecha_segura_temperatura"]["value"] == 1.0

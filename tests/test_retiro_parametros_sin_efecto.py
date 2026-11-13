"""9-nov: retiro de los parámetros de programa y de equipo que ningún módulo del
control leía (sección «estabilizacion», globals.enfriar_chaqueta_secado y el
parámetro de equipo timeout_chaqueta). ciclos_multiples se conserva."""
import copy
import glob
import json
import os

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import migrar_parametros

RAIZ = os.path.join(os.path.dirname(__file__), "..", "src", "autoclave")


def _programas():
    return sorted(glob.glob(os.path.join(RAIZ, "cycles", "factory", "*.json")))


def _viejo():
    """Un programa instalado con las claves retiradas."""
    hoja = {"value": 1, "type": "int", "unit": "", "min": 0, "max": 1}
    return {
        "globals": {"ciclos_multiples": dict(hoja), "enfriar_chaqueta_secado": dict(hoja)},
        "estabilizacion": {"tiempo_estabilizacion": dict(hoja), "timeout_recuperacion": dict(hoja)},
        "calentamiento": {"temperatura_calentamiento": {"value": 134.0}},
    }


def test_programas_de_fabrica_sin_claves_retiradas():
    assert _programas()
    for ruta in _programas():
        parametros = json.load(open(ruta, encoding="utf-8"))["parameters"]
        assert "estabilizacion" not in parametros, ruta
        assert "enfriar_chaqueta_secado" not in parametros["globals"], ruta
        assert "ciclos_multiples" in parametros["globals"], ruta   # se conserva


def test_global_params_sin_timeout_chaqueta():
    datos = json.load(open(os.path.join(RAIZ, "config", "global_params.json"), encoding="utf-8"))
    assert "timeout_chaqueta" not in datos


def test_migracion_quita_claves_y_audita():
    p = _viejo()
    agregadas = []
    assert migrar_parametros(p, agregadas=agregadas) is True
    assert "estabilizacion" not in p
    assert "enfriar_chaqueta_secado" not in p["globals"]
    assert "ciclos_multiples" in p["globals"]
    assert p["calentamiento"]["temperatura_calentamiento"]["value"] == 134.0
    retirados = {(a["fase"], a["parametro"]) for a in agregadas
                 if a["origen"] == cp.ORIGEN_RETIRO_SIN_EFECTO}
    assert retirados == {("estabilizacion", "tiempo_estabilizacion"),
                         ("estabilizacion", "timeout_recuperacion"),
                         ("globals", "enfriar_chaqueta_secado")}
    assert all(a["nuevo"] is None for a in agregadas if a["origen"] == cp.ORIGEN_RETIRO_SIN_EFECTO)


def test_migracion_idempotente():
    p = _viejo()
    migrar_parametros(p, agregadas=[])
    antes = copy.deepcopy(p)
    agregadas = []
    migrar_parametros(p, agregadas=agregadas)
    assert p == antes
    assert not [a for a in agregadas if a["origen"] == cp.ORIGEN_RETIRO_SIN_EFECTO]


def test_catalogo_sin_limites_de_la_seccion_retirada():
    assert not [c for c in cp.__dict__.values()
                if isinstance(c, tuple) and ("estabilizacion", "temperatura_estabilizacion") in c]

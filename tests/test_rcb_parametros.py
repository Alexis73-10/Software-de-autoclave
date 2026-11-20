"""RCB-03: parámetros `registro_carga_obligatorio` e `impresion_carga` en los
programas, su migración al cargar (auditoría, .bak, idempotente, sin SIS-06),
el catálogo y los rótulos es/en."""

import glob
import json
import os
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import Cycle, migrar_parametros

pytestmark = pytest.mark.req("REQ-109")

_RAIZ = os.path.join(os.path.dirname(__file__), "..", "src", "autoclave")
_PROGRAMAS = sorted(glob.glob(os.path.join(_RAIZ, "cycles", "*", "*.json")))


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def test_los_12_programas_traen_los_dos_parametros():
    assert len(_PROGRAMAS) == 12
    for ruta in _PROGRAMAS:
        datos = _leer(ruta)
        g = datos["parameters"]["globals"]
        assert g["registro_carga_obligatorio"] == {"value": False, "type": "bool"}, ruta
        hoja = g["impresion_carga"]
        assert hoja["type"] == "enum" and hoja["options"] == list(cp.IMPRESION_CARGA_OPCIONES)
        esperado = "ninguna" if datos["cycle_id"] == "bowe_dick" else "lote_elementos"
        assert hoja["value"] == esperado, ruta
        for fase, path in (("globals", ["registro_carga_obligatorio"]),
                           ("globals", ["impresion_carga"])):
            hoja = g[path[0]]
            assert cp.coercionar(hoja, fase, path, hoja["value"]) == hoja["value"]


def _sin_claves_rcb(ruta):
    datos = _leer(ruta)
    g = datos["parameters"]["globals"]
    g.pop("registro_carga_obligatorio")
    g.pop("impresion_carga")
    return datos


def _ruta(nombre):
    return next(r for r in _PROGRAMAS if r.endswith(os.path.join("user", nombre)))


def test_migracion_agrega_con_auditoria_y_es_idempotente():
    datos = _sin_claves_rcb(_ruta("textiles.json"))
    prog = Cycle(datos["cycle_id"], "x", datos["parameters"], datos["cycle_number"],
                 migrar_recuperacion=True)
    g = prog.parameters["globals"]
    assert g["registro_carga_obligatorio"]["value"] is False
    assert g["impresion_carga"]["value"] == "lote_elementos"
    filas = [m for m in prog.migraciones_agregadas if m["origen"] == cp.ORIGEN_MIGRACION_RCB]
    assert {m["parametro"] for m in filas} == {"registro_carga_obligatorio", "impresion_carga"}
    assert all(m["anterior"] is None and m["fase"] == "globals" for m in filas)
    # sin SIS-06: nada en las correctivas
    assert not [m for m in prog.migraciones_correctivas
                if m.get("origen") == cp.ORIGEN_MIGRACION_RCB]
    # idempotente
    ag = []
    migrar_parametros(prog.parameters, [], recuperacion=True, agregadas=ag)
    assert not [m for m in ag if m["origen"] == cp.ORIGEN_MIGRACION_RCB]


def test_migracion_bowie_dick_usa_ninguna():
    datos = _sin_claves_rcb(_ruta("bowe_dick.json"))
    prog = Cycle(datos["cycle_id"], "x", datos["parameters"], datos["cycle_number"],
                 migrar_recuperacion=True)
    assert prog.parameters["globals"]["impresion_carga"]["value"] == "ninguna"


def test_migracion_no_pisa_valores_existentes():
    datos = _leer(_ruta("textiles.json"))
    g = datos["parameters"]["globals"]
    g["registro_carga_obligatorio"]["value"] = True
    g["impresion_carga"]["value"] = "lote"
    ag = []
    migrar_parametros(datos["parameters"], [], recuperacion=True, agregadas=ag)
    assert g["registro_carga_obligatorio"]["value"] is True
    assert g["impresion_carga"]["value"] == "lote"
    assert not [m for m in ag if m["origen"] == cp.ORIGEN_MIGRACION_RCB]


def test_lectores_fallan_hacia_el_defecto():
    assert cp.impresion_carga({}) == "lote_elementos"
    assert cp.impresion_carga({"globals": {"impresion_carga": {"value": "rara"}}}) == "lote_elementos"
    assert cp.impresion_carga({"globals": {"impresion_carga": {"value": "lote"}}}) == "lote"
    assert cp.impresion_carga(None) == "lote_elementos"
    assert cp.registro_carga_obligatorio({}) is False
    assert cp.registro_carga_obligatorio(
        {"globals": {"registro_carga_obligatorio": {"value": "true"}}}) is False
    assert cp.registro_carga_obligatorio(
        {"globals": {"registro_carga_obligatorio": {"value": True}}}) is True


def test_coercion_rechaza_opcion_desconocida():
    hoja = {"value": "lote", "type": "enum", "options": list(cp.IMPRESION_CARGA_OPCIONES)}
    with pytest.raises(ValueError):
        cp.coercionar(hoja, "globals", ["impresion_carga"], "todo")
    with pytest.raises(ValueError):
        cp.coercionar({"value": False, "type": "bool"}, "globals",
                      ["registro_carga_obligatorio"], 1)


def test_auditoria_y_reescritura_del_backend(tmp_path):
    """El backend audita las agregadas como param_ciclo_cambio y reescribe el
    JSON de usuario con .bak."""
    from autoclave.backend.context import BackendContext
    from autoclave.core.managers.cycle_manager import CycleManager
    datos = _sin_claves_rcb(_ruta("textiles.json"))
    archivo = tmp_path / "textiles.json"
    archivo.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    prog = Cycle(datos["cycle_id"], "x", datos["parameters"], datos["cycle_number"],
                 migrar_recuperacion=True)
    prog.source, prog._path = "user", str(archivo)
    cm = CycleManager.__new__(CycleManager)
    cm.cycles = {prog.id: prog}
    db = MagicMock()
    ctx = BackendContext.__new__(BackendContext)
    ctx.cycle_manager, ctx.db = cm, db
    BackendContext.auditar_migraciones_correctivas(ctx)
    filas = [f for lote in db.registrar_auditoria_lote.call_args_list for f in lote.args[0]
             if f["detalle"]["origen"] == cp.ORIGEN_MIGRACION_RCB]
    assert {f["entidad"] for f in filas} == {f"{prog.id}/globals/registro_carga_obligatorio",
                                             f"{prog.id}/globals/impresion_carga"}
    assert all(f["evento"] == "param_ciclo_cambio" for f in filas)
    assert os.path.exists(str(archivo) + ".bak")
    g = _leer(archivo)["parameters"]["globals"]
    assert g["impresion_carga"]["value"] == "lote_elementos"


def test_rotulos_y_ayuda_es_en():
    for idioma in ("es", "en"):
        d = _leer(os.path.join(_RAIZ, "i18n", f"{idioma}.json"))
        for clave in ("registro_carga_obligatorio", "impresion_carga"):
            assert d["parametros"]["globals"][clave]
            assert d["parametros_desc"]["globals"][clave]
        for opcion in cp.IMPRESION_CARGA_OPCIONES:
            assert d["opciones"][f"valor_{opcion}"]

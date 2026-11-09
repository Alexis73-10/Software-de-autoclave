"""CRI-04 (tanda 35): migración de significado de brecha_segura_presion."""
import json

from autoclave.core.managers import catalogo_parametros as cp
from autoclave.core.managers.cycle_manager import Cycle, migrar_parametros
from tests.helpers import planta_vapor as pv


def _parametros(**valores):
    return pv.programa_liquidos(**valores).parameters


def _cargar(parametros):
    datos = json.loads(pv.PROGRAMA_LIQUIDOS.read_text(encoding="utf-8"))
    return Cycle(datos["cycle_id"], "x", parametros, datos.get("cycle_number"),
                 migrar_recuperacion=True)


def _de_brecha(lista):
    return [m for m in lista if m["parametro"] == "brecha_segura_presion"]


def test_una_fila_y_marca_sin_cambiar_el_valor():
    prog = _cargar(_parametros(esterilizacion__brecha_segura_presion=1.5))
    filas = _de_brecha(prog.migraciones_agregadas)
    assert len(filas) == 1
    m = filas[0]
    assert m["origen"] == "migración CRI: brecha_segura_presion medida sobre Psat"
    assert m["anterior"] == m["nuevo"] == 1.5
    hoja = prog.parameters["esterilizacion"]["brecha_segura_presion"]
    assert hoja["value"] == 1.5 and hoja[cp.MARCA_MIGRACION_CRI] is True
    assert not _de_brecha(prog.migraciones_correctivas)      # sin SIS-06


def test_idempotente_con_marca():
    parametros = _parametros()
    ag = []
    assert migrar_parametros(parametros, [], recuperacion=True, agregadas=ag)
    assert len(_de_brecha(ag)) == 1
    ag2 = []
    migrar_parametros(parametros, [], recuperacion=True, agregadas=ag2)
    assert not _de_brecha(ag2)


def test_sin_recuperacion_no_migra():
    """Copias e instantaneas conservan lo que tenian (no piden la migracion)."""
    parametros = _parametros()
    ag = []
    migrar_parametros(parametros, [], recuperacion=False, agregadas=ag)
    assert not _de_brecha(ag)
    assert cp.MARCA_MIGRACION_CRI not in parametros["esterilizacion"]["brecha_segura_presion"]


def test_valor_no_numerico_ni_auditoria_ni_marca():
    parametros = _parametros()
    parametros["esterilizacion"]["brecha_segura_presion"]["value"] = None
    ag = []
    migrar_parametros(parametros, [], recuperacion=True, agregadas=ag)
    assert not _de_brecha(ag)
    assert cp.MARCA_MIGRACION_CRI not in parametros["esterilizacion"]["brecha_segura_presion"]


def test_auditoria_param_ciclo_cambio_del_backend():
    """El backend audita las `agregadas` como param_ciclo_cambio con el origen."""
    from unittest.mock import MagicMock
    from autoclave.backend.context import BackendContext
    from autoclave.core.managers.cycle_manager import CycleManager
    prog = _cargar(_parametros())
    prog.source = "factory"
    cm = CycleManager.__new__(CycleManager)
    cm.cycles = {prog.id: prog}
    db = MagicMock()
    ctx = BackendContext.__new__(BackendContext)
    ctx.cycle_manager, ctx.db = cm, db
    BackendContext.auditar_migraciones_correctivas(ctx)
    filas = [f for lote in db.registrar_auditoria_lote.call_args_list for f in lote.args[0]
             if f["entidad"].endswith("/brecha_segura_presion")]
    assert len(filas) == 1
    assert filas[0]["evento"] == "param_ciclo_cambio"
    assert filas[0]["detalle"]["origen"] == cp.ORIGEN_MIGRACION_CRI

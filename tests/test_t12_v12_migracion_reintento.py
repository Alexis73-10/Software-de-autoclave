# Tanda 12, V12 (SAF-07): un reintento de abrir_base_datos no duplica la
# auditoría de la migración correctiva ni pisa el .bak con el valor migrado;
# un programa dañado no se audita, no se reescribe ni se avisa.

import json

from autoclave.services.domain.logging.db_manager import DbManager
from tests.test_t12_c04_migracion_aviso import _contexto, _ids, _instalar


def test_reintento_no_duplica_ni_pisa_el_bak(tmp_path):
    ruta = _instalar(tmp_path)
    ctx = _contexto(tmp_path)
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.auditar_migraciones_correctivas()
    ctx.auditar_migraciones_correctivas()        # reintento del bucle de arranque
    assert len(ctx.db.get_auditoria(evento="param_ciclo_cambio")) == 1
    bak = json.loads((ruta.parent / "bowe_dick.json.bak").read_text(encoding="utf-8"))
    assert bak["parameters"]["calentamiento"]["presion_add_calentamiento"]["value"] == 99.0


def test_programa_danado_no_se_audita_ni_se_avisa(tmp_path):
    ruta = _instalar(tmp_path)
    ctx = _contexto(tmp_path)
    ctx.cycle_manager.cycles["bowe_dick"].danado = ["simulado"]
    ctx._avisar_migraciones_correctivas()
    assert _ids(ctx) == []
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.auditar_migraciones_correctivas()
    assert ctx.db.get_auditoria(evento="param_ciclo_cambio") == []
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["parameters"]["calentamiento"]["presion_add_calentamiento"]["value"] == 99.0

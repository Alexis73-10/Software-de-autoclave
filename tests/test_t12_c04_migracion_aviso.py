"""J12 (tanda 12, C-04.4): migración correctiva al cargar un programa.

Un presion_add_* > 30 kPa baja a 9 y, además del log: fila en la auditoría de
parámetros (programa, parámetro, valor anterior y nuevo, origen "migración
tanda 12") y aviso no bloqueante SIS-06 en las alarmas activas, que son las
que listan la bandeja de Preciclo y la campana (PanelNotificaciones)."""

import json
import shutil
from pathlib import Path

import pytest

from autoclave.backend.context import BackendContext
from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.alarms.catalogo import CATALOGO, MIGRACION_CORRECTIVA, SIS_06, Nivel
from tests.helpers.backend_doble import modulo_backend

RAIZ = Path(__file__).resolve().parents[1]
CICLOS = RAIZ / "src" / "autoclave" / "cycles"


def _instalar(tmp_path, presion_add=99.0):
    """Copia de cycles/ con el B&D de usuario como quedó instalado en la G."""
    destino = tmp_path / "cycles"
    shutil.copytree(CICLOS / "factory", destino / "factory")
    (destino / "user").mkdir()
    datos = json.loads((CICLOS / "user" / "bowe_dick.json").read_text(encoding="utf-8"))
    datos["parameters"]["calentamiento"]["presion_add_calentamiento"]["value"] = presion_add
    ruta = destino / "user" / "bowe_dick.json"
    ruta.write_text(json.dumps(datos, indent=4, ensure_ascii=False), encoding="utf-8")
    return ruta


def _contexto(tmp_path):
    ctx = BackendContext()
    cm = CycleManager()
    cm.raiz = str(tmp_path)
    cm.load_all_cycles()
    ctx.cycle_manager = cm
    return ctx


def _ids(ctx):
    return [i.definicion.codigo for i in ctx.alarm_manager.activas()]


def test_sis_06_es_aviso_no_bloqueante():
    d = CATALOGO[SIS_06]
    assert MIGRACION_CORRECTIVA == SIS_06
    assert d.nivel is Nivel.AVISO and d.bloquea_inicio is False


def test_aviso_activo_al_cargar(tmp_path):
    _instalar(tmp_path)
    ctx = _contexto(tmp_path)
    ctx._avisar_migraciones_correctivas()
    assert _ids(ctx) == [SIS_06]
    inst = ctx.alarm_manager.activas()[0]
    assert inst.valores["parametro"] == "presion_add_calentamiento"
    assert (inst.valores["anterior"], inst.valores["nuevo"]) == ("99", "9")
    assert "99" in inst.descripcion and "9 kPa" in inst.descripcion
    assert ctx.alarm_manager.has_blocking_alarm() is False


def test_sin_migracion_no_hay_aviso(tmp_path):
    _instalar(tmp_path, presion_add=9.0)
    ctx = _contexto(tmp_path)
    ctx._avisar_migraciones_correctivas()
    assert _ids(ctx) == []


def test_fila_de_auditoria_y_archivo_reescrito(tmp_path):
    ruta = _instalar(tmp_path)
    ctx = _contexto(tmp_path)
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.auditar_migraciones_correctivas()
    filas = ctx.db.get_auditoria(evento="param_ciclo_cambio")
    assert len(filas) == 1
    f = filas[0]
    assert f["entidad"] == "bowe_dick/calentamiento/presion_add_calentamiento"
    assert (f["valor_anterior"], f["valor_nuevo"]) == ("99.0", "9.0")
    assert f["usuario"] == "sistema"
    assert f["detalle"]["origen"] == "migración tanda 12"
    assert f["detalle"]["automatico"] is True and f["detalle"]["programa"] == "bowe_dick"
    # archivo = memoria = bitácora; la versión anterior queda en .bak
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["parameters"]["calentamiento"]["presion_add_calentamiento"]["value"] == 9.0
    bak = json.loads((ruta.parent / "bowe_dick.json.bak").read_text(encoding="utf-8"))
    assert bak["parameters"]["calentamiento"]["presion_add_calentamiento"]["value"] == 99.0
    # el siguiente arranque ya no migra ni avisa
    ctx2 = _contexto(tmp_path)
    assert ctx2.cycle_manager.migraciones_correctivas() == []


def test_sin_auditoria_el_archivo_no_se_toca(tmp_path):
    ruta = _instalar(tmp_path)
    ctx = _contexto(tmp_path)

    class BdRota:
        def registrar_auditoria_lote(self, filas):
            raise RuntimeError("base ocupada")

    ctx.db = BdRota()
    ctx.auditar_migraciones_correctivas()            # no lanza
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["parameters"]["calentamiento"]["presion_add_calentamiento"]["value"] == 99.0
    # en memoria el programa ya corre con 9
    assert ctx.cycle_manager.cycles["bowe_dick"].get_param(
        "calentamiento", "presion_add_calentamiento") == 9.0


def test_backend_expone_el_aviso_en_status_es_y_en(tmp_path):
    from autoclave.backend import server
    _instalar(tmp_path)
    ctx = _contexto(tmp_path)
    ctx._avisar_migraciones_correctivas()
    dto = modulo_backend("rutas.sistema")._alarma_dto(ctx.alarm_manager.activas()[0])
    assert dto["codigo"] == SIS_06 and dto["level"] == "ALERTA"
    assert dto["requiere_reconocimiento"] is False
    es, en = dto["textos"]["es"], dto["textos"]["en"]
    assert es["titulo"] == "Programa corregido al cargarlo"
    assert en["titulo"] == "Program corrected on loading"
    assert "presion_add_calentamiento" in es["descripcion"] and "99" in es["descripcion"]
    assert "changed to 9 kPa" in en["descripcion"]


def test_la_campana_y_preciclo_lo_listan(tmp_path):
    """El mismo modelo de alarmas activas alimenta la tarjeta de alarmas de
    Preciclo y PanelNotificaciones (raiz.alarmas en PantallaPreciclo.qml)."""
    pytest.importorskip("PySide6")
    from autoclave.backend import server
    from autoclave.ui_qml.bridge.ui_bridge import AlarmListModel
    _instalar(tmp_path)
    ctx = _contexto(tmp_path)
    ctx._avisar_migraciones_correctivas()
    modelo = AlarmListModel()
    modelo.establecer([modulo_backend("rutas.sistema")._alarma_dto(i) for i in ctx.alarm_manager.activas()])
    filas = modelo.filas()
    assert modelo.count == 1 and filas[0]["level"] == "ALERTA"
    assert filas[0]["id"].startswith(SIS_06)
    assert "99" in filas[0]["descripciones"]["es"] and "99" in filas[0]["descripciones"]["en"]
    qml = (RAIZ / "src" / "autoclave" / "ui_qml" / "qml" / "Pantallas" / "PantallaPreciclo.qml"
           ).read_text(encoding="utf-8")
    assert "alarmas: raiz.alarmas" in qml               # la campana usa el mismo modelo

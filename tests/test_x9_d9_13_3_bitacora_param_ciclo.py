"""X9 (tanda 9), D9-13.3 ★: pendientes de la revisión de D8-5.7 (V8a).

- TMG-01: el cambio se aplica al ciclo en curso solo DESPUÉS de registrar la
  bitácora; si la bitácora falla, la copia del ciclo en curso nunca recibió el
  valor (antes se aplicaba y la reversión no la alcanzaba si la fase ya había
  iniciado).
- SAF-01: las filas del cambio y de su arrastre van en una sola transacción
  (`DbManager.registrar_auditoria_lote`): todas o ninguna.
- SAF-02: doble falla (bitácora y luego el JSON al revertir): el programa
  queda marcado en disco (`<programa>.json.sin_bitacora`) y, al cargarlo, no
  es ejecutable hasta que un guardado correcto lo reescriba.
"""

import json
import os
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState

RAIZ = Path(__file__).resolve().parents[1]


# ── SAF-01: método por lote en db_manager ──────────────────────────────────

def test_lote_registra_todas_las_filas(tmp_path):
    db = DbManager(tmp_path / "a.db")
    ids = db.registrar_auditoria_lote([
        {"evento": "param_ciclo_cambio", "usuario": "u", "rol": "tecnico", "entidad": "p/g/a",
         "valor_anterior": 1, "valor_nuevo": 2, "detalle": {"aplica": "siguiente"}},
        {"evento": "param_ciclo_cambio", "usuario": "u", "rol": "tecnico", "entidad": "p/d/modo",
         "valor_anterior": 4, "valor_nuevo": 1, "detalle": {"automatico": True}},
    ])
    assert len(ids) == 2 and ids[0] < ids[1]
    filas = db.get_auditoria(evento="param_ciclo_cambio")
    assert {f["entidad"] for f in filas} == {"p/g/a", "p/d/modo"}
    assert {f["valor_nuevo"] for f in filas} == {"2", "1"}


def test_lote_que_falla_no_deja_ninguna_fila(tmp_path):
    db = DbManager(tmp_path / "a.db")
    with pytest.raises(TypeError):
        db.registrar_auditoria_lote([
            {"evento": "param_ciclo_cambio", "entidad": "p/g/a", "valor_nuevo": 2},
            {"evento": "param_ciclo_cambio", "entidad": "p/d/modo",
             "detalle": {"no_serializable": object()}},
        ])
    assert db.get_auditoria(evento="param_ciclo_cambio") == []
    # la conexión sigue usable tras el rollback
    db.registrar_auditoria("otra", entidad="e")
    assert len(db.get_auditoria(evento="otra")) == 1


def test_lote_que_falla_en_la_base_no_deja_ninguna_fila(tmp_path):
    db = DbManager(tmp_path / "a.db")
    with db._lock:
        db._conn.execute(
            "CREATE TRIGGER x9_falla BEFORE INSERT ON audit_log WHEN NEW.entidad = 'mala' "
            "BEGIN SELECT RAISE(ABORT, 'falla simulada'); END")
        db._conn.commit()
    with pytest.raises(sqlite3.DatabaseError):
        db.registrar_auditoria_lote([{"evento": "param_ciclo_cambio", "entidad": "buena"},
                                     {"evento": "param_ciclo_cambio", "entidad": "mala"}])
    assert db.get_auditoria(evento="param_ciclo_cambio") == []


def test_lote_vacio_no_hace_nada(tmp_path):
    db = DbManager(tmp_path / "a.db")
    assert db.registrar_auditoria_lote([]) == []


# ── Endpoint PATCH /cycle/parameter con base real ─────────────────────────

@pytest.fixture
def cm(tmp_path):
    origen = RAIZ / "src" / "autoclave" / "cycles"
    for sub in ("factory", "user"):
        shutil.copytree(origen / sub, tmp_path / "cycles" / sub)
    m = CycleManager()
    m.raiz = str(tmp_path)
    m.load_all_cycles()
    return m


@pytest.fixture
def servidor(cm, tmp_path):
    from fastapi.testclient import TestClient
    from tests.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.cycle_manager = cm
    ctx.sin_base_de_datos = False
    ctx.db = DbManager(tmp_path / "bd.db")
    ctx.estado.fase_ciclo = "CALENTAMIENTO"
    ctx.cycle_logger.ciclo_id_pantalla = 7
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app, headers=cabecera(srv, "ingeniero")), cm, ctx, srv


def _patch(client, cycle_id, fase, path, valor):
    return client.patch("/cycle/parameter", json={"cycle_id": cycle_id, "fase": fase,
                                                  "path": path, "value": valor})


def _filas(ctx, evento="param_ciclo_cambio"):
    return list(reversed(ctx.db.get_auditoria(evento=evento, limite=100)))


def _en_ciclo(ctx, cycle_id, pendiente=True, aplica=True):
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    ctx.control_loop.cycle.id = cycle_id
    ctx.control_loop.fase_pendiente_en_curso.return_value = pendiente
    ctx.control_loop.aplicar_a_ciclo_en_curso.return_value = aplica


def _secado(cm, cycle_id="instrumental_121"):
    c = cm.cycles[cycle_id]
    hoja = c.parameters["secado"]["tiempo_secado"]
    nuevo = hoja["max"] if hoja["value"] != hoja["max"] else hoja["min"]
    return c, hoja["value"], nuevo


def test_tmg01_aplica_al_ciclo_en_curso_despues_de_la_bitacora(servidor):
    client, cm, ctx, _ = servidor
    c, _, nuevo = _secado(cm)
    _en_ciclo(ctx, c.id)
    orden = []
    real = ctx.db.registrar_auditoria_lote

    def lote(filas):
        orden.append("bitacora")
        return real(filas)
    ctx.db.registrar_auditoria_lote = lote
    ctx.control_loop.aplicar_a_ciclo_en_curso.side_effect = lambda *a: orden.append("aplica") or True
    r = _patch(client, c.id, "secado", ["tiempo_secado"], nuevo)
    assert r.status_code == 200, r.text
    assert r.json()["aplica"] == "en_curso"
    assert orden == ["bitacora", "aplica"]
    assert _filas(ctx)[0]["detalle"]["aplica"] == "en_curso"


def test_tmg01_sin_bitacora_el_ciclo_en_curso_nunca_recibe_el_valor(servidor):
    client, cm, ctx, _ = servidor
    c, previo, nuevo = _secado(cm)
    _en_ciclo(ctx, c.id)
    ctx.db.registrar_auditoria_lote = MagicMock(side_effect=sqlite3.OperationalError("locked"))
    r = _patch(client, c.id, "secado", ["tiempo_secado"], nuevo)
    assert r.status_code == 503 and r.json()["codigo"] == "BASE_OCUPADA"
    ctx.control_loop.aplicar_a_ciclo_en_curso.assert_not_called()
    assert c.get_param("secado", "tiempo_secado") == previo


def test_tmg01_si_la_fase_inicia_entre_medias_rige_desde_el_siguiente(servidor):
    """La fase estaba pendiente al decidir (bajo _sm_lock) pero inició antes de
    aplicar: el ciclo sigue con el valor anterior (el registrado como
    anterior) y una fila propia corrige el `aplica` de la primera."""
    client, cm, ctx, _ = servidor
    c, previo, nuevo = _secado(cm)
    _en_ciclo(ctx, c.id, pendiente=True, aplica=False)
    r = _patch(client, c.id, "secado", ["tiempo_secado"], nuevo)
    assert r.status_code == 200 and r.json()["aplica"] == "siguiente"
    assert c.get_param("secado", "tiempo_secado") == nuevo     # programa almacenado
    corr = _filas(ctx, "param_ciclo_no_aplicado_en_curso")
    assert len(corr) == 1
    assert corr[0]["entidad"] == f"{c.id}/secado/tiempo_secado"
    assert corr[0]["detalle"]["aplica"] == "siguiente"


def test_tmg01_fase_ya_iniciada_no_intenta_aplicar(servidor):
    client, cm, ctx, _ = servidor
    c, _, nuevo = _secado(cm)
    _en_ciclo(ctx, c.id, pendiente=False)
    r = _patch(client, c.id, "secado", ["tiempo_secado"], nuevo)
    assert r.status_code == 200 and r.json()["aplica"] == "siguiente"
    ctx.control_loop.aplicar_a_ciclo_en_curso.assert_not_called()
    assert _filas(ctx)[0]["detalle"]["aplica"] == "siguiente"
    assert _filas(ctx, "param_ciclo_no_aplicado_en_curso") == []


def test_saf01_cambio_y_arrastre_en_una_sola_transaccion(servidor):
    client, cm, ctx, _ = servidor
    llamadas = []
    real = ctx.db.registrar_auditoria_lote

    def lote(filas):
        llamadas.append([f["entidad"] for f in filas])
        return real(filas)
    ctx.db.registrar_auditoria_lote = lote
    ctx.db.registrar_auditoria = MagicMock(side_effect=AssertionError("fila suelta"))
    r = _patch(client, "liquidos", "globals", ["tipo_carga"], "solido")
    assert r.status_code == 200, r.text
    assert llamadas == [["liquidos/globals/tipo_carga", "liquidos/descompresion/modo"]]
    filas = _filas(ctx)
    assert [f["entidad"] for f in filas] == ["liquidos/globals/tipo_carga",
                                             "liquidos/descompresion/modo"]
    assert filas[1]["detalle"]["automatico"] is True


def test_saf01_si_falla_la_fila_del_arrastre_no_queda_ninguna(servidor):
    client, cm, ctx, _ = servidor
    with ctx.db._lock:
        ctx.db._conn.execute(
            "CREATE TRIGGER x9_falla BEFORE INSERT ON audit_log "
            "WHEN NEW.entidad = 'liquidos/descompresion/modo' "
            "BEGIN SELECT RAISE(ABORT, 'falla simulada'); END")
        ctx.db._conn.commit()
    r = _patch(client, "liquidos", "globals", ["tipo_carga"], "solido")
    assert r.status_code == 503
    assert _filas(ctx) == []
    c = cm.cycles["liquidos"]
    assert c.get_param("globals", "tipo_carga") == "liquido"
    assert c.get_param("descompresion", "modo") == 4
    persistido = json.loads(Path(c._path).read_text(encoding="utf-8"))
    assert persistido["parameters"]["globals"]["tipo_carga"]["value"] == "liquido"
    assert not os.path.exists(c._path + ".sin_bitacora")


# ── SAF-02: doble falla bitácora + JSON ────────────────────────────────────

def _doble_falla(servidor):
    client, cm, ctx, srv = servidor
    c, previo, nuevo = _secado(cm)
    ctx.db.registrar_auditoria_lote = MagicMock(side_effect=sqlite3.OperationalError("locked"))
    real = srv._escribir_json_programa
    llamadas = {"n": 0}

    def escribir(cycle, cambiar):
        llamadas["n"] += 1
        if llamadas["n"] >= 2:                      # la reversión del JSON falla
            raise OSError("disco lleno")
        real(cycle, cambiar)
    srv._escribir_json_programa = escribir
    r = _patch(client, c.id, "secado", ["tiempo_secado"], nuevo)
    srv._escribir_json_programa = real
    return r, c, previo, nuevo


def test_saf02_doble_falla_marca_el_programa_en_disco(servidor):
    r, c, previo, nuevo = _doble_falla(servidor)
    assert r.status_code == 503
    # la memoria vuelve al valor registrado; el disco quedó con el no registrado
    assert c.get_param("secado", "tiempo_secado") == previo
    disco = json.loads(Path(c._path).read_text(encoding="utf-8"))
    assert disco["parameters"]["secado"]["tiempo_secado"]["value"] == nuevo
    assert os.path.exists(c._path + ".sin_bitacora")


def test_saf02_al_cargar_un_programa_marcado_no_es_ejecutable(servidor, tmp_path):
    _, c, _, _ = _doble_falla(servidor)
    m = CycleManager()
    m.raiz = str(tmp_path)
    m.load_all_cycles()
    recargado = m.cycles[c.id]
    assert recargado.danado and "bitácora" in recargado.danado[0]


def test_saf02_un_guardado_correcto_quita_la_marca(servidor):
    client, cm, ctx, _ = servidor
    _, c, previo, nuevo = _doble_falla(servidor)
    ctx.db.registrar_auditoria_lote = DbManager.registrar_auditoria_lote.__get__(ctx.db)
    r = _patch(client, c.id, "secado", ["tiempo_secado"], nuevo)
    assert r.status_code == 200, r.text
    assert not os.path.exists(c._path + ".sin_bitacora")
    disco = json.loads(Path(c._path).read_text(encoding="utf-8"))
    assert disco["parameters"]["secado"]["tiempo_secado"]["value"] == nuevo


def test_saf02_falla_solo_el_json_no_marca(servidor):
    """Si lo que falla es la escritura del JSON (antes de la bitácora), el
    archivo no cambió (escritura atómica): no hay nada sin registrar."""
    client, cm, ctx, srv = servidor
    c, previo, nuevo = _secado(cm)
    real = srv._escribir_json_programa

    def escribir(cycle, cambiar):
        raise OSError("disco lleno")
    srv._escribir_json_programa = escribir
    r = _patch(client, c.id, "secado", ["tiempo_secado"], nuevo)
    srv._escribir_json_programa = real
    assert r.status_code == 503
    assert c.get_param("secado", "tiempo_secado") == previo
    assert _filas(ctx) == []
    assert not os.path.exists(c._path + ".sin_bitacora")


# ── Predicción bajo _sm_lock: CicloState.fase_pendiente ───────────────────

def test_ciclo_fase_pendiente_no_modifica_la_copia():
    from tests.test_t17_copia_programa import _ciclo, _parametro
    ciclo, programa = _ciclo(fase_idx=2)                       # CALENTAMIENTO en curso
    path, _ = _parametro(programa, "secado")
    antes = json.dumps(ciclo.programa_en_curso.parameters, sort_keys=True)
    assert ciclo.fase_pendiente("secado", path) is True
    assert ciclo.fase_pendiente("calentamiento", ["temperatura_calentamiento"]) is False
    assert ciclo.fase_pendiente("globals", ["tipo_carga"]) is False
    assert json.dumps(ciclo.programa_en_curso.parameters, sort_keys=True) == antes


def test_control_loop_fase_pendiente_solo_en_ciclo():
    from tests.test_t17_copia_programa import _loop
    loop, _ = _loop(GlobalState.PREPARADO)
    assert loop.fase_pendiente_en_curso("secado", ["x"]) is False
    loop.state_machine.ciclo.fase_pendiente.assert_not_called()
    loop, _ = _loop(GlobalState.CICLO)
    loop.state_machine.ciclo.fase_pendiente.return_value = True
    assert loop.fase_pendiente_en_curso("secado", ["x"]) is True

"""RCB-04: inicio del ciclo con la carga. POST /cycle/start valida la carga
bajo el lock de la máquina (422 carga_invalida, 409 carga_requerida, sin
START_CICLO), la deja resuelta en `estado.carga_inicio` y la bitácora del
inicio lleva lote y n_elementos; el CycleLogger la escribe con la fila del
ciclo (misma transacción), en el respaldo y en el ticket, y la reimportación
la restaura. Dos inicios seguidos no se cruzan (HAZ-RCB-01)."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.core.runtime.respaldo_ciclos import RespaldoCiclos, reimportar
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.state_machine.machine.enum_global import GlobalState
from tests.helpers.backend_doble import cabecera, cargar_servidor, modulo_backend

pytestmark = pytest.mark.req("REQ-110")

CARGA = {"lote": "L-001", "elementos": [{"codigo": "A1", "cantidad": 2, "manual": False},
                                        {"codigo": "ZZ9", "cantidad": 1, "manual": True}]}


def _programa(obligatorio=False, impresion="lote_elementos"):
    return {"globals": {"registro_carga_obligatorio": {"value": obligatorio, "type": "bool"},
                        "impresion_carga": {"value": impresion, "type": "enum",
                                            "options": ["ninguna", "lote", "lote_elementos"]}}}


@pytest.fixture
def api(monkeypatch, tmp_path):
    db = DbManager(tmp_path / "t.db")
    db.alta_catalogo_carga("A1", "Pinza Kelly", "ines")
    ctx = MagicMock()
    ctx.db = db
    ctx.sin_base_de_datos = False
    ctx.control_loop.bloqueo_configuracion = None
    ctx.control_loop.apagando = False
    ctx.control_loop.test_mode_active = False
    ctx.control_loop.salidas_sin_confirmar_pendiente = False
    ctx.control_loop.cycle.danado = []
    ctx.control_loop.cycle.id = "prog1"
    ctx.control_loop.cycle.parameters = _programa()
    ctx.control_loop.cycle.get_param.side_effect = lambda *a, default=None: default
    ctx.estado = SimpleNamespace(
        get_flag=lambda f: f == "LISTO_PARA_CICLO", set_flag=MagicMock(), operador_inicio="",
        carga_inicio="basura de un inicio anterior",
        sensores_pres={"pres_camara": 101.0, "pres_chaqueta": 300.0})
    ctx.cap.has_liquids = True
    srv, _ = cargar_servidor(ctx)
    monkeypatch.setattr(modulo_backend("rutas.ciclo").sc, "verificar_inicio", lambda *a: None)
    monkeypatch.setattr(modulo_backend("rutas.ciclo"), "_rechazo_salidas_pendientes", lambda: None)
    yield TestClient(srv.app), ctx, srv
    db.close()


def _inicio_marcado(ctx) -> bool:
    return ("START_CICLO", True) in [c.args for c in ctx.estado.set_flag.call_args_list]


def _fila_inicio(ctx):
    filas = [dict(f) for f in ctx.db.get_auditoria(evento="ciclo_iniciado", limite=5)]
    return filas[0] if filas else None


def test_inicio_con_carga_resuelta_y_bitacora(api):
    client, ctx, srv = api
    r = client.post("/cycle/start", json={"carga": CARGA}, headers=cabecera(srv, "operador"))
    assert r.status_code == 200, r.text
    assert _inicio_marcado(ctx)
    carga = ctx.estado.carga_inicio
    assert carga == {"lote": "L-001", "impresion": "lote_elementos", "elementos": [
        {"codigo": "A1", "nombre": "Pinza Kelly", "en_catalogo": True, "cantidad": 2,
         "manual": False, "orden": 0},
        {"codigo": "ZZ9", "nombre": None, "en_catalogo": False, "cantidad": 1,
         "manual": True, "orden": 1}]}
    detalle = _fila_inicio(ctx)["detalle"]
    detalle = json.loads(detalle) if isinstance(detalle, str) else detalle
    assert detalle["lote"] == "L-001" and detalle["n_elementos"] == 3
    assert "elementos" not in detalle                 # RCB-04.6: sin la lista


def test_sin_carga_y_opcional_inicia_como_hoy_y_limpia_la_anterior(api):
    client, ctx, srv = api
    r = client.post("/cycle/start", json={}, headers=cabecera(srv, "operador"))
    assert r.status_code == 200 and _inicio_marcado(ctx)
    assert ctx.estado.carga_inicio is None
    detalle = _fila_inicio(ctx)["detalle"]
    detalle = json.loads(detalle) if isinstance(detalle, str) else detalle
    assert "lote" not in detalle


@pytest.mark.parametrize("carga", [
    {"lote": "", "elementos": [{"codigo": "A1", "cantidad": 1}]},     # elementos sin lote
    {"lote": "L|1", "elementos": []},
    {"lote": "L1", "elementos": [{"codigo": "A1", "cantidad": 0}]},
    {"lote": "L1", "elementos": [{"codigo": "A1", "cantidad": 1000}]},
    {"lote": "L1", "elementos": [{"codigo": "A1", "cantidad": 1}, {"codigo": "A1", "cantidad": 1}]},
    {"lote": "L1", "elementos": [{"codigo": f"C{i}", "cantidad": 1} for i in range(201)]},
    {"lote": "L1", "elementos": "no"},
    "texto",
])
def test_carga_invalida_422_sin_ciclo(api, carga):
    client, ctx, srv = api
    r = client.post("/cycle/start", json={"carga": carga}, headers=cabecera(srv, "operador"))
    assert r.status_code == 422 and r.json()["codigo"] == "carga_invalida"
    assert not _inicio_marcado(ctx)
    assert ctx.estado.carga_inicio == "basura de un inicio anterior"   # no se tocó
    assert _fila_inicio(ctx) is None


@pytest.mark.parametrize("carga", [None, {"lote": "L1", "elementos": []}])
def test_obligatoria_sin_lote_o_sin_elementos_409(api, carga):
    client, ctx, srv = api
    ctx.control_loop.cycle.parameters = _programa(obligatorio=True)
    cuerpo = {} if carga is None else {"carga": carga}
    r = client.post("/cycle/start", json=cuerpo, headers=cabecera(srv, "operador"))
    assert r.status_code == 409 and r.json()["codigo"] == "carga_requerida"
    assert not _inicio_marcado(ctx)


def test_obligatoria_con_carga_inicia(api):
    client, ctx, srv = api
    ctx.control_loop.cycle.parameters = _programa(obligatorio=True, impresion="lote")
    r = client.post("/cycle/start", json={"carga": CARGA}, headers=cabecera(srv, "operador"))
    assert r.status_code == 200 and _inicio_marcado(ctx)
    assert ctx.estado.carga_inicio["impresion"] == "lote"


def test_no_listo_rechaza_antes_que_la_carga(api):
    client, ctx, srv = api
    ctx.estado.get_flag = lambda f: False
    r = client.post("/cycle/start", json={"carga": "texto"}, headers=cabecera(srv, "operador"))
    assert r.status_code == 409 and not _inicio_marcado(ctx)


def test_catalogo_ilegible_no_impide_el_inicio(api, monkeypatch):
    client, ctx, srv = api
    monkeypatch.setattr(ctx.db, "catalogo_carga_activo", MagicMock(side_effect=RuntimeError))
    r = client.post("/cycle/start", json={"carga": CARGA}, headers=cabecera(srv, "operador"))
    assert r.status_code == 200
    assert all(not e["en_catalogo"] for e in ctx.estado.carga_inicio["elementos"])


def test_codigos_con_texto_es_en():
    from autoclave.ui_qml import sesion_backend as sb
    for codigo in ("carga_requerida", "carga_invalida"):
        assert codigo in sb._CLAVES_INICIO_CICLO
    for idioma in ("es", "en"):
        from pathlib import Path
        d = json.loads((Path(__file__).resolve().parents[1] / "src" / "autoclave" / "i18n"
                        / f"{idioma}.json").read_text(encoding="utf-8"))
        assert d["registro_carga"]["err_requerida"] and d["registro_carga"]["err_invalida"]


# ── CycleLogger: base, respaldo y ticket ────────────────────────────────────

class _Estado:
    def __init__(self):
        self.maquina = GlobalState.PREPARADO
        self.fase_ciclo = "ESTERILIZACION"
        self.sub_estado_ciclo = ""
        self.sensores_temp = {"temp_camara": 134.0}
        self.sensores_pres = {"pres_camara": 304.0}
        self.motivo_fallo = ""
        self.codigo_fallo = ""
        self.valores_fallo = None
        self.f0_acumulado = 0.0
        self.avisos_ciclo = []
        self.operador_inicio = ""
        self.carga_inicio = None

    def get_machine_state(self):
        return self.maquina


class _Programa:
    id, name, number = "instrumental_134", "Instrumental 134", 2

    def get_param(self, seccion, nombre, default=None):
        return {("esterilizacion", "temperatura_esterilizacion"): 134,
                ("esterilizacion", "tiempo_esterilizacion"): 4}.get((seccion, nombre), default)

    def instantanea(self):
        return {"id": self.id}


class _Impresora:
    def __init__(self):
        self.trozos = []

    def enqueue(self, texto):
        self.trozos.append(texto)


def _logger(tmp_path, db):
    from autoclave.installation.equipment import EquipmentClass
    from autoclave.services.domain.logging.cycle_logger import CycleLogger
    estado = _Estado()
    impresora = _Impresora()
    respaldo = RespaldoCiclos(tmp_path / "respaldo")
    perfil = SimpleNamespace(serial_number="S1", model_id="M1",
                             equipment_class=EquipmentClass.PISO_LAB)
    reloj = SimpleNamespace(t=1000.0)
    cl = CycleLogger(db, estado, {"intervalo_impresion": 180,
                                  "intervalo_impresion_esterilizacion": 99999},
                     perfil, SimpleNamespace(get_selected_cycle=lambda: _Programa()),
                     printer=impresora, reloj_mono=lambda: reloj.t, respaldo=respaldo)
    return cl, estado, impresora, respaldo


def _carga_resuelta(lote, codigos):
    return {"lote": lote, "impresion": "lote_elementos",
            "elementos": [{"codigo": c, "nombre": f"N{c}" if i == 0 else None,
                           "en_catalogo": i == 0, "cantidad": i + 1, "manual": i == 1,
                           "orden": i} for i, c in enumerate(codigos)]}


def test_dos_inicios_seguidos_cada_carga_en_su_ciclo(tmp_path):
    db = DbManager(tmp_path / "a.db")
    cl, estado, impresora, _ = _logger(tmp_path, db)
    estado.carga_inicio = _carga_resuelta("LOTE-A", ["A1", "A2"])
    estado.maquina = GlobalState.CICLO
    cl.update()
    assert estado.carga_inicio is None                    # consumida
    estado.maquina = GlobalState.PREPARADO
    cl.update()
    estado.carga_inicio = _carga_resuelta("LOTE-B", ["B1"])
    estado.maquina = GlobalState.CICLO
    cl.update()
    cl.detener()                                          # vacía la cola de la base
    filas = [dict(f) for f in db._conn.execute("SELECT id, lote_carga FROM ciclos ORDER BY id")]
    assert [f["lote_carga"] for f in filas] == ["LOTE-A", "LOTE-B"]
    a, b = (db.get_carga_ciclo(f["id"]) for f in filas)
    assert [e["codigo"] for e in a["elementos"]] == ["A1", "A2"]
    assert a["elementos"][0]["nombre"] == "NA1" and a["elementos"][1]["manual"] is True
    assert [e["codigo"] for e in b["elementos"]] == ["B1"]
    assert a["impresion"] == "lote_elementos"
    db.close()


def test_sin_carga_el_ciclo_queda_sin_lote(tmp_path):
    db = DbManager(tmp_path / "a.db")
    cl, estado, impresora, _ = _logger(tmp_path, db)
    estado.maquina = GlobalState.CICLO
    cl.update()
    cl.detener()
    fila = db._conn.execute("SELECT id, lote_carga, impresion_carga FROM ciclos").fetchone()
    assert fila["lote_carga"] is None and fila["impresion_carga"] is None
    assert db.get_carga_ciclo(fila["id"]) is None
    db.close()


def test_respaldo_y_reimportacion_restauran_la_carga(tmp_path):
    """La base falla al crear el ciclo: la carga queda en el respaldo y se
    restaura al reimportar."""
    db = DbManager(tmp_path / "a.db")
    falla = MagicMock(side_effect=RuntimeError("base caída"))
    original = db.crear_ciclo
    db.crear_ciclo = falla
    cl, estado, impresora, respaldo = _logger(tmp_path, db)
    estado.carga_inicio = _carga_resuelta("LOTE-R", ["R1", "R2"])
    estado.maquina = GlobalState.CICLO
    cl.update()
    cl.detener()
    archivos = respaldo.pendientes()
    assert len(archivos) == 1
    encabezado = respaldo.leer(archivos[0])["encabezado"]
    assert encabezado["carga"]["lote"] == "LOTE-R"
    db.crear_ciclo = original
    resultado = reimportar(respaldo, db, "Ciclo interrumpido")
    assert len(resultado["importados"]) == 1
    fila = db._conn.execute("SELECT id, lote_carga FROM ciclos").fetchone()
    carga = db.get_carga_ciclo(fila["id"])
    assert carga["lote"] == "LOTE-R" and [e["codigo"] for e in carga["elementos"]] == ["R1", "R2"]
    assert carga["elementos"][0]["nombre"] == "NR1" and carga["elementos"][0]["en_catalogo"]
    assert carga["elementos"][1]["nombre"] is None and carga["elementos"][1]["manual"]
    db.close()


def test_respaldo_con_carga_danada_importa_el_ciclo_sin_carga(tmp_path):
    db = DbManager(tmp_path / "a.db")
    encabezado = {"uuid": "u1", "numero": 1, "fecha_inicio": "2026-11-19T10:00:00",
                  "carga": {"lote": "L|X", "elementos": []}}
    assert db.importar_ciclo_respaldo(encabezado, [], None, "int") == "importado"
    fila = db._conn.execute("SELECT id, lote_carga FROM ciclos").fetchone()
    assert fila["lote_carga"] is None
    db.close()


def test_crear_ciclo_con_carga_es_una_transaccion(tmp_path):
    """Si la carga no se puede escribir, tampoco queda la fila del ciclo."""
    db = DbManager(tmp_path / "a.db")
    mala = {"lote": "L1", "impresion": "lote",
            "elementos": [{"codigo": "A1", "cantidad": None}]}          # NOT NULL
    with pytest.raises(Exception):
        db.crear_ciclo(numero=1, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                       modelo="M", serie="S", version_sw="1", carga=mala)
    assert db._conn.execute("SELECT COUNT(*) FROM ciclos").fetchone()[0] == 0
    db.close()

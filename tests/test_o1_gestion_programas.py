"""O1 (tanda 5): gestión de programas (habilitar, duplicar, borrar) y modelo
de defectos (cycles/factory, cycles/defecto, cycles/user)."""

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import gestion_programas as gp
from autoclave.core.managers.cycle_manager import CycleManager

RAIZ = Path(__file__).resolve().parents[1]
CICLOS = RAIZ / "src" / "autoclave" / "cycles"


@pytest.fixture
def cm(tmp_path):
    for sub in ("factory", "user"):
        destino = tmp_path / "cycles" / sub
        destino.mkdir(parents=True)
        for f in (CICLOS / sub).glob("*.json"):
            shutil.copy2(f, destino / f.name)
    m = CycleManager()
    m.raiz = str(tmp_path)
    m.load_all_cycles()
    return m


def test_sin_carpeta_de_defecto_el_defecto_es_el_de_fabrica(cm):
    assert cm.defectos == {}
    assert cm.defecto(2) is cm.fabrica[2]


def test_defecto_del_hospital_manda_sobre_fabrica(cm, tmp_path):
    carpeta = tmp_path / "cycles" / "defecto"
    carpeta.mkdir()
    prog = cm.cycles["134_instrumental"]
    params = json.loads(json.dumps(prog.parameters))
    params["esterilizacion"]["tiempo_esterilizacion"]["value"] = 7.5
    (carpeta / "x.json").write_text(json.dumps({"cycle_id": prog.id, "cycle_number": 2,
                                                "parameters": params}), encoding="utf-8")
    cm.load_all_cycles()
    assert cm.defecto(2).get_param("esterilizacion", "tiempo_esterilizacion") == 7.5


def test_duplicar_crea_programa_personalizado_con_numero_nuevo_y_defecto(cm, tmp_path):
    origen = cm.cycles["134_instrumental"]
    origen.parameters["esterilizacion"]["tiempo_esterilizacion"]["value"] = 5.0
    gp.fijar_habilitado(cm, 2, True, None)   # fuerza escritura del origen sin cambiar nada
    nuevo = gp.duplicar(cm, 2, "  Instrumental lento ")
    assert nuevo.number == max(n for n in cm.fabrica) + 1 or nuevo.number > 4
    assert nuevo.name == "Instrumental lento" and nuevo.personalizado and nuevo.habilitado
    data = json.loads(Path(nuevo._path).read_text(encoding="utf-8"))
    assert data["cycle_number"] == nuevo.number and data["personalizado"] is True
    defecto = cm.defecto(nuevo.number)
    assert defecto is not None
    assert (tmp_path / "cycles" / "defecto" / f"{nuevo.id}.json").exists()
    # tras recargar sigue igual
    cm.load_all_cycles()
    assert cm.cycles[nuevo.id].personalizado is True
    assert cm.defecto(nuevo.number).get_param("globals", "F0") == origen.get_param("globals", "F0")


@pytest.mark.parametrize("nombre", ["", "   ", None, "x" * 41, 3])
def test_duplicar_rechaza_nombre_invalido(cm, nombre):
    with pytest.raises(gp.ErrorPrograma) as e:
        gp.duplicar(cm, 2, nombre)
    assert e.value.estado_http == 422


def test_borrar_solo_personalizados_y_nunca_reutiliza_el_numero(cm):
    with pytest.raises(gp.ErrorPrograma) as e:
        gp.borrar(cm, 2, None)
    assert e.value.codigo == "programa_de_fabrica"
    nuevo = gp.duplicar(cm, 2, "Temporal")
    n = nuevo.number
    gp.borrar(cm, n, None)
    assert nuevo.id not in cm.cycles and not Path(nuevo._path).exists()
    otro = gp.duplicar(cm, 2, "Otro")
    assert otro.number == n + 1                       # el número borrado no vuelve
    cm.load_all_cycles()
    assert gp.numero_nuevo(cm) == n + 2


def test_no_se_borra_ni_deshabilita_el_programa_activo(cm):
    nuevo = gp.duplicar(cm, 2, "Activo")
    with pytest.raises(gp.ErrorPrograma) as e:
        gp.borrar(cm, nuevo.number, nuevo.id)
    assert e.value.codigo == "programa_activo"
    with pytest.raises(gp.ErrorPrograma) as e:
        gp.fijar_habilitado(cm, nuevo.number, False, nuevo.id)
    assert e.value.codigo == "programa_activo"


def test_deshabilitar_persiste_y_solo_booleanos(cm):
    assert gp.fijar_habilitado(cm, 1, False, None) == (True, False)
    cm.load_all_cycles()
    assert next(c for c in cm.cycles.values() if c.number == 1).habilitado is False
    with pytest.raises(gp.ErrorPrograma):
        gp.fijar_habilitado(cm, 1, "false", None)


# ── endpoints ──────────────────────────────────────────────────────────────

@pytest.fixture
def api(cm, tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.state_machine.machine.enum_global import GlobalState
    from autoclave.services.domain.logging.db_manager import DbManager
    from tests.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.cycle_manager = cm
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.sin_base_de_datos = False
    ctx.control_loop.cycle.id = "134_instrumental"
    srv, _ = cargar_servidor(ctx)
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    return TestClient(srv.app), srv, ctx, cabecera


def _estado(ctx, estado):
    from autoclave.state_machine.machine.enum_global import GlobalState
    ctx.estado.get_machine_state.return_value = getattr(GlobalState, estado)


def test_api_duplicar_habilitar_borrar_con_auditoria(api):
    client, srv, ctx, cabecera = api
    h = cabecera(srv, "tecnico")
    r = client.post("/programas/1/duplicar", headers=h, json={"nombre": "Copia"})
    assert r.status_code == 200, r.text
    n = r.json()["numero"]
    progs = {p["numero"]: p for p in client.get("/programas").json()["programas"]}
    assert progs[n]["personalizado"] is True and progs[n]["habilitado"] is True
    assert client.put(f"/programas/{n}/habilitado", headers=h,
                      json={"habilitado": False}).status_code == 200
    sel = [p["numero"] for p in client.get("/programas/seleccionables").json()["programas"]]
    assert n not in sel
    assert client.delete(f"/programas/{n}", headers=h).status_code == 200
    eventos = [f["evento"] for f in ctx.db.get_auditoria(limite=20)]
    assert {"programa_duplicado", "programa_habilitado", "programa_borrado"} <= set(eventos)


def test_api_sin_sesion_o_admin_rechaza(api):
    client, srv, ctx, cabecera = api
    assert client.post("/programas/1/duplicar", json={"nombre": "x"}).status_code == 401
    assert client.post("/programas/1/duplicar", headers=cabecera(srv, "admin"),
                       json={"nombre": "x"}).status_code == 403


def test_api_tecnico_no_en_ciclo_ingeniero_si(api):
    client, srv, ctx, cabecera = api
    _estado(ctx, "CICLO")
    assert client.post("/programas/1/duplicar", headers=cabecera(srv, "tecnico"),
                       json={"nombre": "x"}).status_code == 409
    assert client.post("/programas/1/duplicar", headers=cabecera(srv, "ingeniero"),
                       json={"nombre": "x"}).status_code == 200


def test_api_no_borra_de_fabrica_ni_el_activo(api):
    client, srv, ctx, cabecera = api
    h = cabecera(srv, "ingeniero")
    assert client.delete("/programas/2", headers=h).status_code == 422
    assert client.put("/programas/2/habilitado", headers=h,
                      json={"habilitado": False}).status_code == 409    # 2 es el activo


def test_api_seleccionar_un_programa_deshabilitado_se_rechaza(api):
    client, srv, ctx, cabecera = api
    h = cabecera(srv, "tecnico")
    client.put("/programas/1/habilitado", headers=h, json={"habilitado": False})
    c1 = next(c for c in ctx.cycle_manager.cycles.values() if c.number == 1)
    r = client.post("/cycle/select", json={"cycle_id": c1.id, "origen": "puerta_1"})
    assert r.status_code == 409


def test_api_la_seccion_usa_el_defecto_del_hospital(api):
    client, srv, ctx, cabecera = api
    h = cabecera(srv, "tecnico")
    origen = ctx.cycle_manager.cycles["134_instrumental"]
    origen.parameters["esterilizacion"]["tiempo_esterilizacion"]["value"] = 6.0
    n = client.post("/programas/2/duplicar", headers=h, json={"nombre": "D"}).json()["numero"]
    p = {x["clave"]: x for x in client.get(f"/programas/{n}/seccion/esterilizacion").json()["parametros"]}
    assert p["tiempo_esterilizacion"]["defecto"] == 6.0
    assert p["tiempo_esterilizacion"]["modificado"] is False


# ── entradas mostradas ─────────────────────────────────────────────────────

_HAB = ["temp_camara", "temp_referencia", "pres_camara", "pres_chaqueta"]


def test_entradas_por_omision_y_cardinalidad(cm):
    c = gp.programa(cm, 2)
    assert gp.entradas_de(c, _HAB) == ["temp_camara", "temp_referencia", "pres_camara"]
    for malas in ([], ["temp_camara"] * 2, _HAB, "temp_camara", [1]):
        with pytest.raises(gp.ErrorPrograma):
            gp.fijar_entradas(cm, 2, malas, _HAB)
    with pytest.raises(gp.ErrorPrograma) as e:
        gp.fijar_entradas(cm, 2, ["temp_drenaje_cam"], _HAB)
    assert e.value.codigo == "SENSOR_NO_DISPONIBLE"
    gp.fijar_entradas(cm, 2, ["pres_chaqueta"], _HAB)
    cm.load_all_cycles()
    assert gp.entradas_de(gp.programa(cm, 2), _HAB) == ["pres_chaqueta"]


def test_api_entradas_mostradas(api, monkeypatch):
    client, srv, ctx, cabecera = api
    monkeypatch.setattr(srv, "_ai_habilitadas", lambda: list(_HAB))
    assert client.get("/cycle/display-inputs?programa=2").json()["entradas"] == [
        "temp_camara", "temp_referencia", "pres_camara"]
    r = client.put("/cycle/display-inputs", headers=cabecera(srv, "tecnico"),
                   json={"programa": 2, "entradas": ["temp_camara", "pres_chaqueta"]})
    assert r.status_code == 200, r.text
    assert client.get("/cycle/display-inputs?programa=2").json()["entradas"] == [
        "temp_camara", "pres_chaqueta"]
    assert client.put("/cycle/display-inputs", json={"programa": 2, "entradas": ["x"]}).status_code == 401


# ── revisión O1 (safety-reviewer) ──────────────────────────────────────────

@pytest.mark.parametrize("nombre", ["instrumental 134", "  INSTRUMENTAL   134 ", "a\nb", "x\x07"])
def test_duplicar_rechaza_nombre_repetido_o_con_control(cm, nombre):
    with pytest.raises(gp.ErrorPrograma):
        gp.duplicar(cm, 2, nombre)


def _sin_auditoria(ctx, monkeypatch):
    def falla(*a, **k):
        raise RuntimeError("bitácora caída")
    monkeypatch.setattr(ctx.db, "registrar_auditoria", falla)


def test_auditoria_fallida_revierte_el_duplicado(api, monkeypatch):
    client, srv, ctx, cabecera = api
    antes = set(ctx.cycle_manager.cycles)
    _sin_auditoria(ctx, monkeypatch)
    r = client.post("/programas/1/duplicar", headers=cabecera(srv, "tecnico"), json={"nombre": "Sin bitácora"})
    assert r.status_code == 503
    assert set(ctx.cycle_manager.cycles) == antes
    carpeta = Path(ctx.cycle_manager.carpeta("cycles/user"))
    assert not any(p.name.startswith("programa_") for p in carpeta.glob("*.json"))


def test_auditoria_fallida_revierte_el_borrado(api, monkeypatch):
    client, srv, ctx, cabecera = api
    h = cabecera(srv, "tecnico")
    n = client.post("/programas/1/duplicar", headers=h, json={"nombre": "Para borrar"}).json()["numero"]
    c = gp.programa(ctx.cycle_manager, n)
    _sin_auditoria(ctx, monkeypatch)
    assert client.delete(f"/programas/{n}", headers=h).status_code == 503
    assert gp.programa(ctx.cycle_manager, n) is c and Path(c._path).exists()
    assert ctx.cycle_manager.defecto(n) is not None


def test_borrado_confirmado_elimina_los_apartados(api):
    client, srv, ctx, cabecera = api
    h = cabecera(srv, "tecnico")
    n = client.post("/programas/1/duplicar", headers=h, json={"nombre": "Borrar"}).json()["numero"]
    ruta = Path(gp.programa(ctx.cycle_manager, n)._path)
    assert client.delete(f"/programas/{n}", headers=h).status_code == 200
    assert not ruta.exists() and not Path(str(ruta) + ".borrado").exists()


def test_auditoria_fallida_revierte_habilitado_y_entradas(api, monkeypatch):
    client, srv, ctx, cabecera = api
    h = cabecera(srv, "tecnico")
    monkeypatch.setattr(srv, "_ai_habilitadas", lambda: list(_HAB))
    _sin_auditoria(ctx, monkeypatch)
    assert client.put("/programas/1/habilitado", headers=h, json={"habilitado": False}).status_code == 503
    c1 = gp.programa(ctx.cycle_manager, 1)
    assert c1.habilitado is True
    assert json.loads(Path(c1._path).read_text(encoding="utf-8")).get("habilitado", True) is True
    assert client.put("/cycle/display-inputs", headers=h,
                      json={"programa": 1, "entradas": ["pres_chaqueta"]}).status_code == 503
    assert gp.entradas_de(gp.programa(ctx.cycle_manager, 1), _HAB) == [
        "temp_camara", "temp_referencia", "pres_camara"]
    assert "entradas_mostradas" not in json.loads(Path(c1._path).read_text(encoding="utf-8"))

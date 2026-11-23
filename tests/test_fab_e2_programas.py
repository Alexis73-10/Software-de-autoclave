"""Modo fábrica, Etapa 2: programas de fábrica del equipo y numeración
(planeacion_modo_fabrica.md §5.3, D-05..D-07, FAB-09, FAB-13; decisiones
DF-06 y PA-07; prueba de aceptación P-02).

Todo en una copia temporal de cycles/: nunca se escribe en src/autoclave/cycles.
"""

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autoclave.core.managers import gestion_programas as gp
from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.utils import resources

pytestmark = [pytest.mark.req("FAB-09"), pytest.mark.req("DF-06"), pytest.mark.req("PA-07")]

RAIZ = Path(__file__).resolve().parents[1]
CICLOS = RAIZ / "src" / "autoclave" / "cycles"


def _copiar_ciclos(tmp_path) -> Path:
    raiz = tmp_path / "cycles"
    shutil.copytree(CICLOS / "factory", raiz / "factory")
    (raiz / "user").mkdir(parents=True)
    for f in (CICLOS / "user").glob("*.json"):
        shutil.copy2(f, raiz / "user" / f.name)
    return raiz


def _cargar(tmp_path) -> CycleManager:
    m = CycleManager()
    m.raiz = str(tmp_path)
    m.load_all_cycles()
    return m


@pytest.fixture
def cm(tmp_path):
    _copiar_ciclos(tmp_path)
    return _cargar(tmp_path)


def _usuario(tmp_path) -> Path:
    return tmp_path / "cycles" / "user"


def _numeros_usados(tmp_path):
    ruta = _usuario(tmp_path) / gp.NUMEROS_USADOS
    return ruta.read_text(encoding="utf-8") if ruta.exists() else None


def _numeros(cm):
    return sorted(c.number for c in cm.cycles.values() if c.number is not None)


# ── FÁBRICA: crear y duplicar ───────────────────────────────────────────────

def test_fabrica_crea_hasta_10_y_el_undecimo_se_rechaza(cm, tmp_path):
    assert _numeros(cm) == [1, 2, 3, 4, 5, 6]
    usados_antes = _numeros_usados(tmp_path)
    creados = [gp.duplicar(cm, 2, f"Fabrica {i}", modo_fabrica=True) for i in range(4)]
    assert [c.number for c in creados] == [7, 8, 9, 10]
    for c in creados:
        data = json.loads(Path(c._path).read_text(encoding="utf-8"))
        assert data["fabrica_equipo"] is True and "personalizado" not in data
        assert Path(c._path).parent == _usuario(tmp_path)
        assert c.fabrica_equipo is True and c.personalizado is False
    with pytest.raises(gp.ErrorPrograma) as e:
        gp.duplicar(cm, 2, "Undécimo", modo_fabrica=True)
    assert (e.value.codigo, e.value.estado_http) == ("maximo_programas_fabrica", 409)
    # numeros_usados.json no cambia en FÁBRICA
    assert _numeros_usados(tmp_path) == usados_antes
    # tras recargar, siguen siendo de fábrica del equipo y editables
    cm.load_all_cycles()
    assert _numeros(cm) == list(range(1, 11))
    assert all(cm.cycles[c.id].fabrica_equipo for c in creados)
    assert all(cm.cycles[c.id].source == "user" for c in creados)


def test_borrar_el_1_lo_deja_libre_y_el_siguiente_toma_el_1(cm, tmp_path):
    usados_antes = _numeros_usados(tmp_path)
    for i in range(4):
        gp.duplicar(cm, 2, f"F{i}", modo_fabrica=True)
    c = gp.borrar_fabrica(cm, "bowe_dick", activo_id="134_instrumental")
    gp.confirmar_borrado(c)
    assert c._numero_borrado == 1
    assert not (_usuario(tmp_path) / "bowe_dick.json").exists()
    nuevo = gp.duplicar(cm, 2, "Nuevo uno", modo_fabrica=True)
    assert nuevo.number == 1
    assert nuevo.id != "bowe_dick"
    assert _numeros_usados(tmp_path) == usados_antes
    cm.load_all_cycles()
    assert cm.cycles[nuevo.id].number == 1 and "bowe_dick" not in cm.cycles


def test_borrar_heredado_no_reaparece_desde_factory_ni_tras_actualizacion(cm, tmp_path):
    c = gp.borrar_fabrica(cm, "bowe_dick", activo_id=None)
    gp.confirmar_borrado(c)
    borrados = resources.leer_lista_ids(str(_usuario(tmp_path)), resources.MARCA_FABRICA_BORRADOS)
    vistos = resources.leer_lista_ids(str(_usuario(tmp_path)), resources.MARCA_FABRICA_VISTOS)
    assert "bowe_dick" in borrados and "bowe_dick" in vistos
    cm.load_all_cycles()
    assert "bowe_dick" not in cm.cycles and 1 not in cm.fabrica
    assert _numeros(cm) == [2, 3, 4, 5, 6]
    # «actualización simulada»: factory/ se refresca con el paquete y se vuelve
    # a sembrar y a cargar
    shutil.rmtree(tmp_path / "cycles" / "factory")
    shutil.copytree(CICLOS / "factory", tmp_path / "cycles" / "factory")
    assert resources.sembrar_faltantes_usuario(str(tmp_path / "cycles")) == []
    cm2 = _cargar(tmp_path)
    assert "bowe_dick" not in cm2.cycles
    assert not (_usuario(tmp_path) / "bowe_dick.json").exists()


def test_borrar_generico_nuevo_no_lo_resiembra(cm, tmp_path):
    c = gp.borrar_fabrica(cm, "prion", activo_id=None)
    gp.confirmar_borrado(c)
    # aunque se pierda fabrica_vistos.lst, la lista de borrados manda
    (_usuario(tmp_path) / resources.MARCA_FABRICA_VISTOS).unlink()
    assert resources.sembrar_faltantes_usuario(str(tmp_path / "cycles")) == []
    assert "prion" not in _cargar(tmp_path).cycles


def test_borrar_fabrica_quita_bak_y_defecto_por_numero(cm, tmp_path):
    nuevo = gp.duplicar(cm, 2, "Con defecto", modo_fabrica=True)
    defecto = tmp_path / "cycles" / "defecto"
    # un defecto con otro nombre de archivo pero el mismo cycle_number
    (defecto / "otro_nombre.json").write_text(json.dumps(
        {"cycle_id": "x", "cycle_number": nuevo.number, "parameters": {}}), encoding="utf-8")
    Path(nuevo._path + ".bak").write_text("{}", encoding="utf-8")
    c = gp.borrar_fabrica(cm, nuevo.id, activo_id=None)
    gp.confirmar_borrado(c)
    assert not Path(nuevo._path).exists() and not Path(nuevo._path + ".bak").exists()
    assert list(defecto.glob("*.json")) == []
    assert not any(p.name.endswith(".borrado") for p in (tmp_path / "cycles").rglob("*"))
    assert nuevo.number not in cm.defectos


def test_borrar_fabrica_rechaza_personalizado_activo_e_inexistente(cm):
    with pytest.raises(gp.ErrorPrograma) as e:
        gp.borrar_fabrica(cm, "134_instrumental", activo_id="134_instrumental")
    assert e.value.codigo == "programa_activo"
    with pytest.raises(gp.ErrorPrograma) as e:
        gp.borrar_fabrica(cm, "no_existe", activo_id=None)
    assert e.value.estado_http == 404
    personal = gp.duplicar(cm, 2, "Personal")            # ENTREGADO
    with pytest.raises(gp.ErrorPrograma) as e:
        gp.borrar_fabrica(cm, personal.id, activo_id=None)
    assert (e.value.codigo, e.value.estado_http) == ("no_es_programa_de_fabrica", 422)


def test_deshacer_borrado_fabrica_restaura_todo(cm, tmp_path):
    usuario = str(_usuario(tmp_path))
    vistos_antes = resources.leer_lista_ids(usuario, resources.MARCA_FABRICA_VISTOS)
    c = gp.borrar_fabrica(cm, "bowe_dick", activo_id=None)
    gp.deshacer_borrado_fabrica(cm, c)
    assert (_usuario(tmp_path) / "bowe_dick.json").exists()
    assert "bowe_dick" in cm.cycles and cm.fabrica[1].id == "bowe_dick"
    assert resources.leer_lista_ids(usuario, resources.MARCA_FABRICA_BORRADOS) is None
    assert resources.leer_lista_ids(usuario, resources.MARCA_FABRICA_VISTOS) == vistos_antes
    assert "bowe_dick" in _cargar(tmp_path).cycles


def test_id_de_un_programa_borrado_no_se_reutiliza(cm):
    a = gp.duplicar(cm, 2, "A", modo_fabrica=True)
    gp.confirmar_borrado(gp.borrar_fabrica(cm, a.id, activo_id=None))
    b = gp.duplicar(cm, 2, "B", modo_fabrica=True)
    assert b.number == a.number and b.id != a.id


def test_numero_libre_cuenta_generico_que_cedio_su_numero(cm, tmp_path):
    # un genérico sin copia de usuario que cedió su número sigue ocupándolo
    (_usuario(tmp_path) / "prion.json").unlink()
    cm.load_all_cycles()
    assert cm.cycles["prion"].number is None             # PRI-07
    assert gp.numero_fabrica_libre(cm) == 7


# ── ENTREGADO (PA-07) ────────────────────────────────────────────────────────

def test_entregado_un_programa_de_usuario_nuevo_empieza_en_11(cm, tmp_path):
    nuevo = gp.duplicar(cm, 2, "Usuario")
    assert nuevo.number == 11 and nuevo.personalizado and not nuevo.fabrica_equipo
    otro = gp.duplicar(cm, 2, "Usuario 2")
    assert otro.number == 12
    # los existentes no se renumeran
    assert cm.cycles["bowe_dick"].number == 1


def test_entregado_duplicar_un_fabrica_equipo_da_personalizado(cm):
    fab = gp.duplicar(cm, 2, "Del equipo", modo_fabrica=True)
    copia = gp.duplicar(cm, fab.number, "Copia de usuario")
    data = json.loads(Path(copia._path).read_text(encoding="utf-8"))
    assert data["personalizado"] is True and "fabrica_equipo" not in data
    assert copia.number >= 11


def test_entregado_borrar_fabrica_equipo_por_la_ruta_normal_422(cm):
    fab = gp.duplicar(cm, 2, "Del equipo", modo_fabrica=True)
    with pytest.raises(gp.ErrorPrograma) as e:
        gp.borrar(cm, fab.number, None)
    assert (e.value.codigo, e.value.estado_http) == ("programa_de_fabrica", 422)


def test_sin_lista_de_borrados_la_carga_no_cambia(cm, tmp_path):
    assert not (_usuario(tmp_path) / resources.MARCA_FABRICA_BORRADOS).exists()
    assert _numeros(cm) == [1, 2, 3, 4, 5, 6]
    assert sorted(cm.fabrica) == [1, 2, 3, 4, 5, 6]


# ── endpoints ──────────────────────────────────────────────────────────────

def _api(cm, tmp_path, modo_fabrica: bool):
    from fastapi.testclient import TestClient
    from autoclave.state_machine.machine.enum_global import GlobalState
    from autoclave.services.domain.logging.db_manager import DbManager
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.cycle_manager = cm
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.sin_base_de_datos = False
    ctx.modo_fabrica.return_value = modo_fabrica
    ctx.control_loop.cycle.id = "134_instrumental"
    srv, _ = cargar_servidor(ctx)
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    return TestClient(srv.app), srv, ctx, cabecera


def test_api_fabrica_crear_borrar_y_publicar(cm, tmp_path):
    client, srv, ctx, cabecera = _api(cm, tmp_path, True)
    h = cabecera(srv, "ingeniero")
    r = client.post("/programas/2/duplicar", headers=h, json={"nombre": "Equipo", "crear": True})
    assert r.status_code == 200, r.text
    n, cid = r.json()["numero"], r.json()["cycle_id"]
    assert n == 7
    progs = {p["numero"]: p for p in client.get("/programas").json()["programas"]}
    assert progs[n]["fabrica_equipo"] is True and progs[n]["personalizado"] is False
    assert progs[n]["editable"] is True
    assert progs[1]["fabrica_equipo"] is False
    # técnico no crea en FÁBRICA (D-02)
    assert client.post("/programas/2/duplicar", headers=cabecera(srv, "tecnico"),
                       json={"nombre": "Tec"}).status_code == 403
    # borrar por la ruta de fábrica: auditado con id, número y nombre
    r = client.delete(f"/fabrica/programas/{cid}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "cycle_id": cid, "numero": n}
    fila = next(f for f in ctx.db.get_auditoria(limite=20)
                if f["evento"] == "programa_fabrica_borrado")
    assert fila["usuario"] == "usuario_ingeniero"
    anterior = fila["valor_anterior"]
    anterior = json.loads(anterior) if isinstance(anterior, str) else anterior
    assert anterior == {"numero": n, "cycle_id": cid, "nombre": "Equipo"}
    # el seleccionado no se borra; un técnico tampoco
    assert client.delete("/fabrica/programas/134_instrumental", headers=h).status_code == 409
    assert client.delete("/fabrica/programas/bowe_dick",
                         headers=cabecera(srv, "tecnico")).status_code == 403


def test_api_fabrica_borrar_en_ciclo_se_rechaza(cm, tmp_path):
    from autoclave.state_machine.machine.enum_global import GlobalState
    client, srv, ctx, cabecera = _api(cm, tmp_path, True)
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    r = client.delete("/fabrica/programas/bowe_dick", headers=cabecera(srv, "ingeniero"))
    assert r.status_code == 409
    assert "bowe_dick" in cm.cycles


def test_api_entregado_ruta_de_fabrica_409_para_todos(cm, tmp_path):
    client, srv, ctx, cabecera = _api(cm, tmp_path, False)
    for h in ({}, cabecera(srv, "ingeniero"), cabecera(srv, "tecnico"), cabecera(srv, "admin")):
        r = client.delete("/fabrica/programas/bowe_dick", headers=h)
        assert r.status_code == 409 and "solo_modo_fabrica" in r.text
    assert "bowe_dick" in cm.cycles


def test_api_entregado_crear_da_11_y_borrar_fabrica_equipo_422(cm, tmp_path):
    fab = gp.duplicar(cm, 2, "Del equipo", modo_fabrica=True)
    client, srv, ctx, cabecera = _api(cm, tmp_path, False)
    h = cabecera(srv, "tecnico")
    r = client.post("/programas/2/duplicar", headers=h, json={"nombre": "Usuario"})
    assert r.status_code == 200 and r.json()["numero"] == 11
    r = client.delete(f"/programas/{fab.number}", headers=cabecera(srv, "ingeniero"))
    assert r.status_code == 422 and "programa_de_fabrica" in r.text


def test_api_fabrica_auditoria_fallida_revierte_el_borrado(cm, tmp_path):
    client, srv, ctx, cabecera = _api(cm, tmp_path, True)
    ctx.db = MagicMock()
    ctx.db.registrar_auditoria.side_effect = RuntimeError("base ocupada")
    r = client.delete("/fabrica/programas/bowe_dick", headers=cabecera(srv, "ingeniero"))
    assert r.status_code == 503
    assert "bowe_dick" in cm.cycles
    assert (_usuario(tmp_path) / "bowe_dick.json").exists()
    assert not (_usuario(tmp_path) / resources.MARCA_FABRICA_BORRADOS).exists()

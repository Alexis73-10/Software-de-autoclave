"""C9 (tanda 9, D9-10): Manejo de ciclos en Opciones avanzadas — reglas del
backend. Crear = duplicar con nombre nuevo (bitácora `programa_creado`);
duplicar, habilitar/deshabilitar y borrar solo FUERA DE CICLO, también para el
ingeniero (antes el ingeniero podía en CICLO); nunca se borra uno de fábrica."""

import pytest

from tests.test_o1_gestion_programas import api, cm, _estado  # noqa: F401  (fixtures)
from tests.backend_doble import parchear_en_backend


def _eventos(ctx):
    return [f["evento"] for f in ctx.db.get_auditoria(limite=50)]


def test_crear_es_duplicar_con_evento_propio(api):  # noqa: F811
    client, srv, ctx, cabecera = api
    h = cabecera(srv, "tecnico")
    r = client.post("/programas/1/duplicar", headers=h, json={"nombre": "Nuevo", "crear": True})
    assert r.status_code == 200, r.text
    n = r.json()["numero"]
    progs = {p["numero"]: p for p in client.get("/programas").json()["programas"]}
    assert progs[n]["personalizado"] is True and progs[n]["nombre"] == "Nuevo"
    filas = ctx.db.get_auditoria(limite=10)
    assert filas[0]["evento"] == "programa_creado"
    assert "programa_duplicado" not in _eventos(ctx)


def test_duplicar_sigue_registrando_duplicado(api):  # noqa: F811
    client, srv, ctx, cabecera = api
    r = client.post("/programas/1/duplicar", headers=cabecera(srv, "ingeniero"),
                    json={"nombre": "Copia"})
    assert r.status_code == 200, r.text
    assert "programa_duplicado" in _eventos(ctx) and "programa_creado" not in _eventos(ctx)


def test_crear_solo_acepta_booleano(api):  # noqa: F811
    client, srv, ctx, cabecera = api
    r = client.post("/programas/1/duplicar", headers=cabecera(srv, "tecnico"),
                    json={"nombre": "Nuevo", "crear": "si"})
    assert r.status_code == 422


@pytest.mark.parametrize("rol", ["tecnico", "ingeniero"])
def test_en_ciclo_nadie_gestiona_programas(api, rol):  # noqa: F811
    client, srv, ctx, cabecera = api
    h = cabecera(srv, rol)
    # un personalizado para poder intentar borrarlo
    n = client.post("/programas/1/duplicar", headers=h, json={"nombre": "Copia"}).json()["numero"]
    _estado(ctx, "CICLO")
    assert client.post("/programas/1/duplicar", headers=h,
                       json={"nombre": "Otra", "crear": True}).status_code == 409
    assert client.put(f"/programas/{n}/habilitado", headers=h,
                      json={"habilitado": False}).status_code == 409
    assert client.delete(f"/programas/{n}", headers=h).status_code == 409
    progs = {p["numero"]: p for p in client.get("/programas").json()["programas"]}
    assert n in progs and progs[n]["habilitado"] is True
    assert "Otra" not in [p["nombre"] for p in progs.values()]


@pytest.mark.parametrize("estado", ["PREPARACION", "PREPARADO", "FALLA"])
def test_fuera_de_ciclo_el_tecnico_gestiona(api, estado):  # noqa: F811
    client, srv, ctx, cabecera = api
    _estado(ctx, estado)
    h = cabecera(srv, "tecnico")
    r = client.post("/programas/1/duplicar", headers=h, json={"nombre": "Nuevo", "crear": True})
    assert r.status_code == 200, r.text
    n = r.json()["numero"]
    assert client.put(f"/programas/{n}/habilitado", headers=h,
                      json={"habilitado": False}).status_code == 200
    assert client.delete(f"/programas/{n}", headers=h).status_code == 200
    assert {"programa_creado", "programa_habilitado", "programa_borrado"} <= set(_eventos(ctx))


def test_nunca_se_borra_uno_de_fabrica(api):  # noqa: F811
    client, srv, ctx, cabecera = api
    for rol in ("tecnico", "ingeniero"):
        assert client.delete("/programas/1", headers=cabecera(srv, rol)).status_code == 422


def test_las_entradas_mostradas_conservan_la_excepcion_del_ingeniero(api, monkeypatch):  # noqa: F811
    # D9-10 solo cambia crear/duplicar/habilitar/borrar; las entradas mostradas
    # (Parámetros del ciclo) siguen como antes: el ingeniero también en CICLO
    client, srv, ctx, cabecera = api
    parchear_en_backend(monkeypatch, "_ai_habilitadas", lambda: ["temp_camara", "pres_camara"])
    _estado(ctx, "CICLO")
    r = client.put("/cycle/display-inputs", headers=cabecera(srv, "ingeniero"),
                   json={"programa": 1, "entradas": ["temp_camara"]})
    assert r.status_code == 200, r.text


def test_la_bitacora_describe_los_eventos_de_programas():
    import json
    from pathlib import Path
    from autoclave.core.runtime import bitacora
    raiz = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "i18n"
    cats = {i: json.loads((raiz / f"{i}.json").read_text(encoding="utf-8")) for i in ("es", "en")}
    for ev in ("programa_creado", "programa_duplicado", "programa_habilitado", "programa_borrado"):
        assert ev in bitacora.EVENTOS
        for idioma, cat in cats.items():
            assert isinstance(cat["bitacora"]["ev"].get(ev), str), (ev, idioma)
            assert isinstance(cat["bitacora"]["tipo"].get(ev), str), (ev, idioma)
        assert isinstance(cat["bitacora"]["ev"].get("programa_deshabilitado"), str)


def test_la_bitacora_distingue_habilitar_de_deshabilitar():
    from autoclave.core.runtime import bitacora
    fila = {"evento": "programa_habilitado", "entidad": "/programas/5/habilitado",
            "valor_anterior": '{"habilitado": true}', "valor_nuevo": '{"habilitado": false}'}
    assert bitacora.presentar(fila, {}, {})["clave_texto"] == "bitacora.ev.programa_deshabilitado"
    fila.update(valor_anterior='{"habilitado": false}', valor_nuevo='{"habilitado": true}')
    assert bitacora.presentar(fila, {}, {})["clave_texto"] == "bitacora.ev.programa_habilitado"

"""B6 (tanda 4): GET /programas/seleccionables — orden por uso, marcas, y
disponibilidad del cambio de programa."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.services.domain.logging.db_manager import DbManager
from tests.backend_doble import cargar_servidor


def _ciclo(numero, nombre, temp=134.0, tiempo=3.5, source="user", danado=None, liquido=False):
    params = {("esterilizacion", "temperatura_esterilizacion"): temp,
              ("esterilizacion", "tiempo_esterilizacion"): tiempo,
              ("globals", "tipo_carga"): "liquido" if liquido else "solido"}
    return SimpleNamespace(id=f"prog_{numero}", name=nombre, number=numero, source=source,
                           danado=danado, get_param=lambda s, n, default=None, _p=params: _p.get((s, n), default),
                           parameters={"globals": {"tipo_carga": {"value": "liquido" if liquido else "solido"}}})


PREDEFINIDOS = [(1, "Bowie & Dick"), (2, "Instrumental 134"), (3, "Instrumental 121"), (4, "Líquidos")]


@pytest.fixture
def entorno(tmp_path):
    db = DbManager(db_path=tmp_path / "t.db")
    ctx = MagicMock()
    ctx.db = db
    ctx.sin_base_de_datos = False
    ctx.cap = SimpleNamespace(has_liquids=True)
    ctx.cycle_manager.cycles = {f"prog_{n}": _ciclo(n, nombre, liquido=(n == 4))
                                for n, nombre in PREDEFINIDOS}
    loop = MagicMock()
    loop.bloqueo_maquina.return_value = nullcontext()
    loop._motivo_no_cambiar_ciclo.return_value = None
    loop.cycle = SimpleNamespace(id="prog_2")
    ctx.control_loop = loop
    srv, _ = cargar_servidor(ctx)
    return TestClient(srv.app), db, ctx, loop


def _grabar(db, numero_programa, veces, resultado="COMPLETADO"):
    base = 1000 + numero_programa * 100
    for i in range(veces):
        cid = db._conn.execute(
            "INSERT INTO ciclos (numero_ciclo, fecha_inicio, resultado, numero_programa)"
            " VALUES (?,?,?,?)", (base + i, "2026-10-20T08:00:00", resultado, numero_programa)).lastrowid
        assert cid
    db._conn.commit()


def _numeros(r):
    return [p["numero"] for p in r.json()["programas"]]


def test_sin_historial_orden_predefinido_y_sin_marcas(entorno):
    client, *_ = entorno
    r = client.get("/programas/seleccionables")
    assert r.status_code == 200 and _numeros(r) == [1, 2, 3, 4]
    assert not any(p["mas_usado"] for p in r.json()["programas"]) and r.json()["orden"] == "predefinido"


def test_los_tres_mas_usados_primero_de_mayor_a_menor(entorno):
    client, db, *_ = entorno
    _grabar(db, 3, 5)
    _grabar(db, 4, 9)
    _grabar(db, 1, 2)
    _grabar(db, 2, 1)
    r = client.get("/programas/seleccionables")
    assert _numeros(r) == [4, 3, 1, 2]
    marcas = [p["mas_usado"] for p in r.json()["programas"]]
    assert marcas == [True, True, True, False] and r.json()["orden"] == "uso"


def test_empates_se_resuelven_por_el_orden_predefinido(entorno):
    client, db, *_ = entorno
    _grabar(db, 4, 3)
    _grabar(db, 2, 3)
    _grabar(db, 1, 3)
    _grabar(db, 3, 3)
    r = client.get("/programas/seleccionables")
    assert _numeros(r) == [1, 2, 3, 4]                 # los 3 primeros por número; el 4.º queda sin marca
    assert [p["mas_usado"] for p in r.json()["programas"]] == [True, True, True, False]


def test_menos_de_tres_con_historial_se_marcan_solo_esos(entorno):
    client, db, *_ = entorno
    _grabar(db, 3, 2)
    r = client.get("/programas/seleccionables")
    assert _numeros(r) == [3, 1, 2, 4]
    assert [p["mas_usado"] for p in r.json()["programas"]] == [True, False, False, False]


def test_cuenta_ciclos_abortados_pero_no_los_que_siguen_en_curso(entorno):
    client, db, *_ = entorno
    _grabar(db, 2, 2, resultado="CANCELADO")
    _grabar(db, 1, 5, resultado=None)                  # en curso: no cuenta
    r = client.get("/programas/seleccionables")
    assert _numeros(r)[0] == 2 and r.json()["programas"][0]["ciclos"] == 2
    assert [p for p in r.json()["programas"] if p["numero"] == 1][0]["ciclos"] == 0


def test_modo_sin_base_de_datos_usa_el_orden_predefinido(entorno):
    client, db, ctx, _ = entorno
    _grabar(db, 4, 9)
    ctx.sin_base_de_datos = True
    r = client.get("/programas/seleccionables")
    assert _numeros(r) == [1, 2, 3, 4] and not any(p["mas_usado"] for p in r.json()["programas"])


def test_base_que_falla_no_rompe_la_lista(entorno):
    client, db, ctx, _ = entorno
    ctx.db = MagicMock()
    ctx.db.conteo_ciclos_por_programa.side_effect = RuntimeError("disco")
    r = client.get("/programas/seleccionables")
    assert r.status_code == 200 and _numeros(r) == [1, 2, 3, 4]


def test_cada_fila_trae_numero_nombre_y_parametros_clave(entorno):
    client, *_ = entorno
    fila = client.get("/programas/seleccionables").json()["programas"][1]
    assert fila["numero"] == 2 and fila["nombre"] == "Instrumental 134"
    assert fila["temperatura"] == 134.0 and fila["tiempo"] == 3.5 and fila["cycle_id"] == "prog_2"


def test_marca_el_programa_seleccionado(entorno):
    client, *_ = entorno
    r = client.get("/programas/seleccionables")
    assert [p["numero"] for p in r.json()["programas"] if p["seleccionado"]] == [2]


def test_no_lista_danados_de_fabrica_ni_liquidos_sin_capacidad(entorno):
    client, db, ctx, _ = entorno
    ctx.cycle_manager.cycles["prog_3"].danado = ["fuera de catálogo"]
    ctx.cycle_manager.cycles["prog_1"].source = "factory"
    ctx.cap = SimpleNamespace(has_liquids=False)
    assert _numeros(client.get("/programas/seleccionables")) == [2]


def test_programas_de_usuario_adicionales_se_incluyen(entorno):
    client, db, ctx, _ = entorno
    ctx.cycle_manager.cycles["prog_5"] = _ciclo(5, "Textiles 121", temp=121.0, tiempo=20.0)
    assert _numeros(client.get("/programas/seleccionables")) == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("motivo", [None,
                                    "No se puede cambiar de ciclo mientras hay uno en curso.",
                                    "No se puede cambiar de ciclo mientras la cámara se lleva a estado seguro."])
def test_seleccionable_y_motivo_vienen_de_la_regla_del_backend(entorno, motivo):
    client, db, ctx, loop = entorno
    loop._motivo_no_cambiar_ciclo.return_value = motivo
    d = client.get("/programas/seleccionables").json()
    assert d["seleccionable"] is (motivo is None) and d["motivo"] == (motivo or "")


def test_es_de_solo_lectura_y_sin_sesion(entorno):
    client, *_ = entorno
    assert client.get("/programas/seleccionables").status_code == 200       # sin token, como /cycle/select
    assert client.post("/programas/seleccionables").status_code in (404, 405)

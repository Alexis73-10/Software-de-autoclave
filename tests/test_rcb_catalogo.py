"""RCB-08: catálogo de carga (servicio puro, base, rutas, roles, bitácora e
importación CSV desde USB con vista previa y aplicación todo o nada) y su
paso por el respaldo (RCB-08.6)."""

import json
import sqlite3
from unittest.mock import MagicMock

import pytest

from autoclave.core.runtime import bitacora
from autoclave.core.runtime import registro_carga as rc
from tests.helpers.backend_doble import parchear_en_backend

pytestmark = pytest.mark.req("REQ-114")


# ── reglas puras ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("texto,esperado", [
    ("  ABC-123  ", "ABC-123"), ("a" * 64, "a" * 64), ("x y", "x y"), ("~!", "~!")])
def test_codigo_valido(texto, esperado):
    assert rc.validar_codigo(texto) == (esperado, None)


@pytest.mark.parametrize("texto,motivo", [
    ("", rc.MOTIVO_VACIO), ("   ", rc.MOTIVO_VACIO), ("a" * 65, rc.MOTIVO_LARGO),
    ("a|b", rc.MOTIVO_CARACTER), ("ñandú", rc.MOTIVO_CARACTER), ("a\x07b", rc.MOTIVO_CARACTER),
    (None, rc.MOTIVO_TIPO), (12, rc.MOTIVO_TIPO)])
def test_codigo_invalido(texto, motivo):
    assert rc.validar_codigo(texto) == (None, motivo)


def test_nombre():
    assert rc.validar_nombre("  Pinza   Kelly  ") == ("Pinza Kelly", None)
    assert rc.validar_nombre("Tijera ñandú") == ("Tijera ñandú", None)
    assert rc.validar_nombre("x" * 61)[1] == rc.MOTIVO_LARGO
    assert rc.validar_nombre("a|b")[1] == rc.MOTIVO_CARACTER
    assert rc.validar_nombre("a\x00b")[1] == rc.MOTIVO_CARACTER
    assert rc.validar_nombre("  ")[1] == rc.MOTIVO_VACIO


def test_csv_vista_previa_mixta():
    datos = ("\ufeffcodigo;nombre\n"
             "A1;Pinza\n"          # cambio de nombre
             "B2;Tijera\n"         # alta
             "C3;Bandeja\n"        # sin cambio
             "D4;Separador\n"      # reactivado (mismo nombre, de baja)
             "E5;Gasa\n"           # cambio + reactivado
             "bad|code;X\n"        # rechazada
             "B2;Otra\n"           # duplicada
             "solo_una_columna\n"  # columnas
             "\n").encode("utf-8")
    catalogo = {"A1": {"nombre": "Pinza vieja", "activo": True},
                "C3": {"nombre": "Bandeja", "activo": True},
                "D4": {"nombre": "Separador", "activo": False},
                "E5": {"nombre": "Gasas", "activo": False}}
    v = rc.analizar_csv(datos, catalogo)
    assert v["ok"] and v["error"] is None
    assert v["altas"] == [{"codigo": "B2", "nombre": "Tijera"}]
    assert [(c["codigo"], c["reactivado"]) for c in v["cambios"]] == [("A1", False), ("E5", True)]
    assert v["reactivados"] == [{"codigo": "D4", "nombre": "Separador"}]
    assert v["sin_cambio"] == 1
    assert [(r["linea"], r["motivo"]) for r in v["rechazadas"]] == [
        (7, rc.MOTIVO_CARACTER), (8, rc.MOTIVO_DUPLICADO), (9, rc.MOTIVO_COLUMNAS)]
    assert rc.filas_a_aplicar(v) == [("B2", "Tijera"), ("A1", "Pinza"), ("E5", "Gasa"),
                                     ("D4", "Separador")]


def test_csv_coma_y_errores_de_archivo():
    v = rc.analizar_csv(b'codigo,nombre\n"Z9","Caja, grande"\n', {})
    assert v["ok"] and v["altas"] == [{"codigo": "Z9", "nombre": "Caja, grande"}]
    assert rc.analizar_csv(b"cod;nom\nA;B\n", {})["error"] == "sin_encabezado"
    assert rc.analizar_csv(b"\xff\xfe\x00", {})["error"] == "codificacion"
    muchas = ("codigo;nombre\n" + "".join(f"C{i};N{i}\n" for i in range(rc.MAX_FILAS_CSV + 1)))
    assert rc.analizar_csv(muchas.encode(), {})["error"] == "muchas_filas"
    assert rc.filas_a_aplicar(rc.analizar_csv(b"", {})) == []


def test_eventos_en_bitacora_y_categoria():
    for ev in ("catalogo_carga_alta", "catalogo_carga_editado", "catalogo_carga_baja",
               "catalogo_carga_reactivado", "catalogo_carga_importado"):
        assert ev in bitacora.EVENTOS_REGISTRADOS
        assert bitacora.categoria_de(ev) == "configuracion"


# ── base ───────────────────────────────────────────────────────────────────

def test_base_alta_baja_reactivacion_y_todo_o_nada(tmp_path):
    from autoclave.services.domain.logging.db_manager import DbManager
    db = DbManager(db_path=tmp_path / "c.db")
    assert db.alta_catalogo_carga("A1", "Pinza", "ines")[0] == "alta"
    assert db.alta_catalogo_carga("A1", "Otra", "ines")[0] == "existe"
    id_ = db.listar_catalogo_carga()[0]["id"]
    db.modificar_catalogo_carga(id_, "ines", activo=False)
    assert db.catalogo_carga_activo() == {}
    resultado, anterior = db.alta_catalogo_carga("A1", "Pinza nueva", "ines")
    assert resultado == "reactivado" and anterior["nombre"] == "Pinza"
    assert db.catalogo_carga_activo() == {"A1": "Pinza nueva"}
    assert len(db.listar_catalogo_carga()) == 1          # misma fila, no otra
    # todo o nada: un fallo a mitad no deja nada
    with pytest.raises(sqlite3.Error):
        db.aplicar_catalogo_carga([("B2", "Tijera"), ("C3", None)], "ines")   # NOT NULL
    assert set(db.catalogo_carga_activo()) == {"A1"}
    assert db.aplicar_catalogo_carga([("B2", "Tijera"), ("A1", "Pinza nueva")], "ines") == {
        "altas": 1, "cambios": 0, "reactivados": 0}
    db.close()


# ── rutas ──────────────────────────────────────────────────────────────────

@pytest.fixture
def api(tmp_path):
    from fastapi.testclient import TestClient
    from autoclave.services.domain.logging.db_manager import DbManager
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.helpers.backend_doble import cabecera, cargar_servidor
    ctx = MagicMock()
    ctx.db = DbManager(db_path=tmp_path / "t.db")
    ctx.sin_base_de_datos = False
    srv, _ = cargar_servidor(ctx)
    ctx.control_loop.test_mode_active = False
    ctx.estado.get_machine_state.return_value = GlobalState.PREPARADO
    yield TestClient(srv.app), srv, ctx, cabecera
    ctx.db.close()


def _eventos(ctx, evento):
    return [dict(f) for f in ctx.db.get_auditoria(evento=evento)]


@pytest.mark.parametrize("rol,esperado", [("operador", 403), ("tecnico", 403), ("admin", 200),
                                          ("ingeniero", 200)])
def test_roles_alta(api, rol, esperado):
    client, srv, ctx, cab = api
    r = client.post("/carga/catalogo", json={"codigo": "A1", "nombre": "Pinza"},
                    headers=cab(srv, rol))
    assert r.status_code == esperado


def test_lectura_libre_y_flujo_con_bitacora(api):
    client, srv, ctx, cab = api
    h = cab(srv, "ingeniero", usuario="ines")
    assert client.get("/carga/catalogo").json() == {"elementos": []}
    assert client.post("/carga/catalogo", headers=h,
                       json={"codigo": " A1 ", "nombre": "Pinza"}).json()["codigo"] == "A1"
    r = client.post("/carga/catalogo", headers=h, json={"codigo": "A1", "nombre": "X"})
    assert r.status_code == 409 and r.json()["codigo"] == "codigo_existe"
    r = client.post("/carga/catalogo", headers=h, json={"codigo": "a|b", "nombre": "X"})
    assert r.status_code == 422 and r.json()["errores"][0] == {"campo": "codigo",
                                                                "codigo": "caracter"}
    id_ = client.get("/carga/catalogo").json()["elementos"][0]["id"]
    assert client.patch(f"/carga/catalogo/{id_}", headers=h,
                        json={"nombre": "Pinza Kelly"}).status_code == 200
    assert client.patch(f"/carga/catalogo/{id_}", headers=h, json={"activo": False}).status_code == 200
    assert client.get("/carga/catalogo?activos=true").json()["elementos"] == []
    assert client.patch(f"/carga/catalogo/{id_}", headers=h, json={"activo": True}).status_code == 200
    assert client.patch("/carga/catalogo/999", headers=h, json={"activo": True}).status_code == 404
    assert client.patch(f"/carga/catalogo/{id_}", headers=h, json={}).status_code == 422
    alta = _eventos(ctx, "catalogo_carga_alta")[0]
    assert alta["entidad"] == "A1" and alta["valor_nuevo"] == "Pinza" and alta["usuario"] == "ines"
    editado = _eventos(ctx, "catalogo_carga_editado")[0]
    assert (editado["valor_anterior"], editado["valor_nuevo"]) == ("Pinza", "Pinza Kelly")
    assert len(_eventos(ctx, "catalogo_carga_baja")) == 1
    assert len(_eventos(ctx, "catalogo_carga_reactivado")) == 1
    assert client.patch(f"/carga/catalogo/{id_}", headers=cab(srv, "tecnico"),
                        json={"activo": False}).status_code == 403


def test_importar_csv_vista_previa_y_aplicacion(api, tmp_path, monkeypatch):
    client, srv, ctx, cab = api
    usb = tmp_path / "usb"
    usb.mkdir()
    (usb / "catalogo.csv").write_bytes("codigo;nombre\nA1;Pinza\nB2;Tijera\nmal|;X\n".encode())
    (usb / "otro.txt").write_text("x")
    parchear_en_backend(monkeypatch, "_unidades_usb", lambda: [{"ruta": str(usb), "libre_bytes": 1}])
    h = cab(srv, "admin", usuario="ana")
    lista = client.get("/carga/catalogo/usb", headers=h).json()["unidades"]
    assert [a["archivo"] for a in lista[0]["archivos"]] == ["catalogo.csv"]
    cuerpo = {"unidad": str(usb), "archivo": "catalogo.csv"}
    vista = client.post("/carga/catalogo/importar", headers=h, json=cuerpo).json()
    assert vista["aplicado"] is False and len(vista["altas"]) == 2 and len(vista["rechazadas"]) == 1
    assert client.get("/carga/catalogo").json()["elementos"] == []      # nada aún
    # huella vieja → no aplica
    r = client.post("/carga/catalogo/importar", headers=h,
                    json={**cuerpo, "aplicar": True, "huella": "otra"})
    assert r.status_code == 409 and r.json()["codigo"] == "csv_cambio"
    r = client.post("/carga/catalogo/importar", headers=h,
                    json={**cuerpo, "aplicar": True, "huella": vista["huella"]})
    assert r.status_code == 200 and r.json()["altas"] == 2
    assert {e["codigo"] for e in client.get("/carga/catalogo").json()["elementos"]} == {"A1", "B2"}
    fila = _eventos(ctx, "catalogo_carga_importado")[0]
    assert fila["detalle"] == {"altas": 2, "cambios": 0, "reactivados": 0,
                                           "rechazadas": 1, "sin_cambio": 0}
    # nombre fuera de la raíz o inexistente
    assert client.post("/carga/catalogo/importar", headers=h,
                       json={"unidad": str(usb), "archivo": "../x.csv"}).status_code == 422
    assert client.post("/carga/catalogo/importar", headers=h,
                       json={"unidad": "Z:\\", "archivo": "catalogo.csv"}).status_code == 404
    assert client.post("/carga/catalogo/importar", headers=cab(srv, "tecnico"),
                       json=cuerpo).status_code == 403


def test_importar_csv_invalido(api, tmp_path, monkeypatch):
    client, srv, ctx, cab = api
    usb = tmp_path / "usb"
    usb.mkdir()
    (usb / "malo.csv").write_bytes(b"nada;que;ver\n")
    parchear_en_backend(monkeypatch, "_unidades_usb", lambda: [{"ruta": str(usb), "libre_bytes": 1}])
    r = client.post("/carga/catalogo/importar", headers=cab(srv, "ingeniero"),
                    json={"unidad": str(usb), "archivo": "malo.csv"})
    assert r.status_code == 422 and r.json()["motivo"] == "sin_encabezado"


def test_respaldo_lleva_y_restaura_el_catalogo():
    from autoclave.backend.rutas import respaldo as rr
    datos = {"catalogo_carga.json": json.dumps(
        [{"codigo": "A1", "nombre": "Pinza", "activo": True},
         {"codigo": "B2", "nombre": "Tijera", "activo": False}]).encode()}
    assert rr._catalogo_carga_del_respaldo(datos) == [("A1", "Pinza")]
    assert rr._catalogo_carga_del_respaldo({}) is None
    for malo in ([{"codigo": "a|b", "nombre": "X", "activo": True}],
                 [{"codigo": "A", "nombre": "X"}], {"no": "lista"},
                 [{"codigo": "A", "nombre": "X", "activo": True}] * 2):
        with pytest.raises(ValueError):
            rr._catalogo_carga_del_respaldo({"catalogo_carga.json": json.dumps(malo).encode()})

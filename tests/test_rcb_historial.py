"""RCB-07.2/07.3: búsqueda inversa en Historial (GET /cycle/history?carga=,
exacta y sin distinguir mayúsculas, por lote o por código) y la carga del
ciclo abierto en el puente del Historial."""

import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from autoclave.services.domain.logging.db_manager import DbManager
from tests.helpers.backend_doble import cargar_servidor

pytestmark = pytest.mark.req("REQ-113")


def _carga(lote, codigos):
    return {"lote": lote, "impresion": "lote_elementos",
            "elementos": [{"codigo": c, "nombre": None, "en_catalogo": False, "cantidad": 1}
                          for c in codigos]}


@pytest.fixture
def api(tmp_path):
    db = DbManager(tmp_path / "h.db")
    ids = {}
    for n, (lote, codigos) in enumerate([("LT-01", ["A1", "B2"]), ("lt-02", ["a1"]),
                                         (None, None), ("LT-03", ["C3"])], start=1):
        ids[n] = db.crear_ciclo(numero=n, tipo="t", nombre="N", temp_ester=134, tiempo_ester=4,
                                modelo="M", serie="S", version_sw="1",
                                carga=_carga(lote, codigos) if lote else None)
    ctx = MagicMock()
    ctx.db = db
    ctx.cycle_manager.cycles = {}
    srv, _ = cargar_servidor(ctx)
    yield TestClient(srv.app), ids
    db.close()


def _numeros(r):
    return sorted(c["numero_ciclo"] for c in r.json()["ciclos"])


def test_busqueda_por_lote_exacta_sin_mayusculas(api):
    client, ids = api
    assert _numeros(client.get("/cycle/history", params={"carga": "lt-01"})) == [1]
    assert _numeros(client.get("/cycle/history", params={"carga": "LT-02"})) == [2]
    assert _numeros(client.get("/cycle/history", params={"carga": "LT-0"})) == []   # exacta


def test_busqueda_por_codigo(api):
    client, ids = api
    r = client.get("/cycle/history", params={"carga": "A1"})
    assert _numeros(r) == [1, 2]
    assert r.json()["carga"] == "A1" and r.json()["truncado"] is False
    fila = r.json()["ciclos"][0]
    assert {"id", "numero_ciclo", "programa_nombre", "resultado", "lote"} <= set(fila)


def test_texto_invalido_422_y_sin_carga_como_antes(api):
    client, ids = api
    r = client.get("/cycle/history", params={"carga": "a|b"})
    assert r.status_code == 422 and r.json()["codigo"] == "carga_invalida"
    lista = client.get("/cycle/history").json()
    assert isinstance(lista, list) and len(lista) == 4


def test_puente_busca_y_limpia(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    backend = MagicMock()
    pedidos = []

    def get(ruta, params=None):
        pedidos.append((ruta, params))
        if ruta == "/cycle/history":
            return {"carga": params["carga"], "truncado": False, "ciclos": [
                {"id": 1, "numero_ciclo": 1, "fecha_inicio": "2026-11-19T10:00:00",
                 "programa_nombre": "P", "resultado": "COMPLETADO"}]}
        if ruta.endswith("/ticket"):
            return {"ciclo": {"resultado": "CANCELADO", "operador": "Ana",
                              "carga": _carga("LT-01", ["A1"])}}
        if ruta.endswith("/graph"):
            return {"lecturas": []}
        return {"ciclos": [], "truncado": False}

    backend.get.side_effect = get
    h = CiclosHistorial(backend, ejecutar=lambda t: t())
    assert h.buscarCarga("a|b") is False and not pedidos
    assert h.buscarCarga("  LT-01 ") is True
    assert pedidos[-1] == ("/cycle/history", {"carga": "LT-01"})
    assert h.busquedaCarga == "LT-01" and len(h.ciclos) == 1
    h.cargarGrafica(1)
    h.cargarCarga(1)
    assert h.cargaCiclo["filas"] and "NO ESTÉRIL" in h.cargaCiclo["no_esteril"].upper()
    h.limpiarGrafica()
    assert h.cargaCiclo == {}
    h.limpiarBusquedaCarga()
    assert h.busquedaCarga == "" and pedidos[-1][0] == "/cycle/list"

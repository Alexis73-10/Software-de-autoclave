"""Tanda 17 (s3) — backend de BIT-05: filtro por categoría de GET /audit_log.

`categoria` (una de bitacora.CATEGORIAS) filtra con los eventos de la
categoría; sin ella, todas; una desconocida da 422. La respuesta trae
`categorias` además de `usuarios` y `tipos`. Se combina con usuario y fechas.
"""

import pytest

from autoclave.core.runtime import bitacora
from tests.test_o2e_bitacora import api  # noqa: F401  (fixture)

pytestmark = pytest.mark.req("BIT-05")


def _sembrar(db):
    db.registrar_auditoria("login_ok", usuario="ana", rol="admin")
    db.registrar_auditoria("login_ok", usuario="tomas", rol="admin")
    db.registrar_auditoria("param_sistema_cambio", usuario="ines", rol="ingeniero",
                           entidad="temp_max_apertura", valor_anterior={"temp_max_apertura": 80},
                           valor_nuevo={"temp_max_apertura": 90})
    db.registrar_auditoria("modo_prueba_entra", usuario="ana", rol="tecnico")
    db.registrar_auditoria("respaldo_exportado", usuario="ana", rol="admin")


def test_filtra_por_categoria(api):
    client, srv, ctx, cab = api
    _sembrar(ctx.db)
    h = cab(srv, "admin")
    todas = client.get("/audit_log", headers=h).json()
    assert todas["categorias"] == list(bitacora.CATEGORIAS)
    for cat in bitacora.CATEGORIAS:
        d = client.get("/audit_log", params={"categoria": cat, "por_pagina": 100},
                       headers=h).json()
        assert {bitacora.categoria_de(f["evento"]) for f in d["filas"]} <= {cat}, cat
    usuarios = client.get("/audit_log", params={"categoria": "usuarios_sesion"},
                          headers=h).json()
    assert {f["evento"] for f in usuarios["filas"]} == {"login_ok"}
    seguridad = client.get("/audit_log", params={"categoria": "seguridad"}, headers=h).json()
    assert [f["evento"] for f in seguridad["filas"]] == ["modo_prueba_entra"]
    conf = client.get("/audit_log", params={"categoria": "configuracion"}, headers=h).json()
    assert [f["evento"] for f in conf["filas"]] == ["param_sistema_cambio"]
    # suma de las categorías = todas
    total = sum(client.get("/audit_log", params={"categoria": c}, headers=h).json()["total"]
                for c in bitacora.CATEGORIAS)
    assert total == todas["total"]


def test_categoria_con_usuario_y_fechas(api):
    client, srv, ctx, cab = api
    _sembrar(ctx.db)
    h = cab(srv, "tecnico")
    d = client.get("/audit_log", params={"categoria": "usuarios_sesion", "usuario": "ana",
                                         "hasta": "2999-01-01"}, headers=h).json()
    assert d["total"] == 1 and d["filas"][0]["usuario"] == "ana"
    futuro = client.get("/audit_log", params={"categoria": "usuarios_sesion",
                                              "desde": "2999-01-01"}, headers=h).json()
    assert futuro["total"] == 0


def test_categoria_desconocida_422(api):
    client, srv, ctx, cab = api
    r = client.get("/audit_log", params={"categoria": "otra"}, headers=cab(srv, "admin"))
    assert r.status_code == 422


def test_evento_sin_clasificar_cae_en_sistema(api):
    client, srv, ctx, cab = api
    ctx.db.registrar_auditoria("evento_nuevo_sin_clasificar", usuario="ana", rol="admin")
    d = client.get("/audit_log", params={"categoria": "sistema"},
                   headers=cab(srv, "admin")).json()
    assert "evento_nuevo_sin_clasificar" in {f["evento"] for f in d["filas"]}

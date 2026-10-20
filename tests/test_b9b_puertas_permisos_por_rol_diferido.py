"""B9b (tanda 4) — DIFERIDO: permisos por rol de las puertas en la ruta HTTP
(S3e, D-S3e-1 de la tanda 2).

El equipo de pruebas tiene 2 puertas MANUALES (sin actuador), así que el
contrato de abajo no se implementa en esta versión. Estas pruebas describen el
contrato esperado para equipos con puertas automáticas y están marcadas
`xfail(strict=True)`: el día que se implemente fallarán como XPASS y habrá que
quitar la marca.

Contrato esperado (hoy NO se cumple):
- Sin sesión, cada pantalla opera solo su puerta (409 `puerta_ajena`): esto SÍ
  se cumple hoy y se verifica en test_s3_source_door.py.
- Con sesión de técnico o ingeniero (rol de servicio) se puede operar la OTRA
  puerta, y la orden queda auditada con el usuario.
- Un operador (rol sin servicio) con sesión sigue limitado a su puerta.
"""

import pytest

from tests.backend_doble import cabecera
from tests.test_puertas_fallas_endpoints import entorno, _eventos  # noqa: F401

DIFERIDO = pytest.mark.xfail(
    strict=True,
    reason="B9b DIFERIDO: permisos por rol de las puertas en HTTP solo se implementan "
           "para equipos con puertas automáticas; el equipo de pruebas tiene 2 manuales")


@DIFERIDO
@pytest.mark.parametrize("rol", ["tecnico", "ingeniero"])
def test_el_rol_de_servicio_puede_operar_la_otra_puerta(entorno, rol):
    cliente, ctx, est, _ = entorno
    from tests.backend_doble import cargar_servidor  # noqa: F401
    import autoclave.backend.server as srv
    r = cliente.post("/doors/Puerta 2/open", json={"source_door": 1},
                     headers=cabecera(srv, rol))
    assert r.status_code == 200


@DIFERIDO
def test_la_orden_de_servicio_queda_auditada_con_el_usuario(entorno):
    cliente, ctx, est, _ = entorno
    import autoclave.backend.server as srv
    cliente.post("/doors/Puerta 2/open", json={"source_door": 1},
                 headers=cabecera(srv, "tecnico", usuario="tec1"))
    filas = _eventos(ctx, "puerta_orden")
    assert filas and filas[0]["usuario"] == "tec1"


def test_hoy_sin_sesion_la_puerta_ajena_sigue_rechazada(entorno):
    """Lo que SÍ vale hoy (no es xfail): sin sesión, puerta ajena → 409."""
    cliente, *_ = entorno
    r = cliente.post("/doors/Puerta 2/open", json={"source_door": 1})
    assert r.status_code == 409 and r.json()["codigo"] == "puerta_ajena"

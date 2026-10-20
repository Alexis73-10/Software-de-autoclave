"""S3e (tanda 2; T9 SAF-03): qué significan `door_id` y `source_door` con dos
pantallas en un solo PC.

- `door_id` (perfil de instalación) = la puerta del PC principal: identifica la
  ventana principal (backend, Apagar equipo). NO decide qué puerta puede operar
  cada pantalla.
- `source_door` (cuerpo de /doors/<puerta>/open|close) = la puerta que la
  pantalla que manda la orden controla (1 o 2), DECLARADA por el cliente (no
  autenticada). Cada pantalla opera solo su puerta: una orden para otra puerta
  se rechaza (guarda contra un error de la UI), un valor fuera de rango es
  inválido, y cada orden (aceptada o rechazada) queda en la bitácora con el
  origen. Sin `source_door` (clientes antiguos) se acepta y queda como
  'desconocido'."""

import pytest

from autoclave.devices.puertas.enum_doors import DoorState
from tests.test_puertas_fallas_endpoints import entorno, _eventos  # noqa: F401


def _orden(cliente, puerta, accion="open", **cuerpo):
    return cliente.post(f"/doors/{puerta}/{accion}", json=cuerpo)


def test_cada_pantalla_opera_solo_su_puerta(entorno):
    cliente, _, est, _ = entorno
    r = _orden(cliente, "Puerta 2", source_door=1)
    assert r.status_code == 409 and r.json()["codigo"] == "puerta_ajena"
    assert est.puertas["Puerta 2"] == DoorState.CERRADO          # nada se movió


def test_la_pantalla_de_la_puerta_2_opera_la_puerta_2(entorno):
    cliente, _, est, _ = entorno
    est.puertas["Puerta 2"] = DoorState.ABIERTO
    r = _orden(cliente, "Puerta 2", "close", source_door=2)
    assert r.status_code == 200 and r.json()["source_door"] == 2


@pytest.mark.parametrize("valor", [0, 3, -1, "1", True, 1.5, None])
def test_source_door_invalido(entorno, valor):
    cliente, _, est, _ = entorno
    r = _orden(cliente, "Puerta 1", source_door=valor)
    if valor is None:
        assert r.status_code == 200          # ausente = cliente antiguo
    else:
        assert r.status_code == 422 and r.json()["codigo"] == "source_door_invalido"
        assert est.puertas["Puerta 1"] == DoorState.CERRADO


def test_cada_orden_queda_en_la_bitacora_con_el_origen(entorno):
    cliente, ctx, _, _ = entorno
    _orden(cliente, "Puerta 1", source_door=1)
    (e,) = _eventos(ctx, "puerta_orden")
    assert e["entidad"] == "Puerta 1" and e["detalle"]["source_door"] == 1


def test_orden_rechazada_tambien_queda_auditada(entorno):
    cliente, ctx, _, _ = entorno
    _orden(cliente, "Puerta 2", source_door=1)
    (e,) = _eventos(ctx, "puerta_orden_rechazada")
    assert e["detalle"]["codigo"] == "puerta_ajena" and e["detalle"]["source_door"] == 1


def test_sin_source_door_queda_como_desconocido(entorno):
    cliente, ctx, _, _ = entorno
    assert _orden(cliente, "Puerta 1").status_code == 200
    (e,) = _eventos(ctx, "puerta_orden")
    assert e["detalle"]["source_door"] == "desconocido"

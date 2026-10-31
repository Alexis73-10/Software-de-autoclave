"""S3e (tanda 2; T9 SAF-03): qué significan `door_id` y `source_door` con dos
pantallas en un solo PC.

- `door_id` (perfil de instalación) = la puerta del PC principal: identifica la
  ventana principal (backend, Apagar equipo). NO decide qué puerta puede operar
  cada pantalla.
- `source_door` (cuerpo de /doors/<puerta>/open|close) = la puerta que la
  pantalla que manda la orden controla (1 o 2), DECLARADA por el cliente (no
  autenticada). Cada pantalla opera solo su puerta: una orden para otra puerta
  se rechaza (guarda contra un error de la UI), un valor fuera de rango es
  inválido, y cada orden (aceptada o rechazada) queda registrada con el
  origen (D9-6, tanda 9: en el log de desarrollo, ya no en la bitácora). Sin `source_door` (clientes antiguos) se acepta y queda como
  'desconocido'."""

import logging

import pytest

from autoclave.devices.puertas.enum_doors import DoorState
from tests.test_puertas_fallas_endpoints import entorno, _eventos  # noqa: F401


def _orden(cliente, puerta, accion="open", **cuerpo):
    return cliente.post(f"/doors/{puerta}/{accion}", json=cuerpo)


def _log_dev(caplog, evento):
    """D9-6 (tanda 9): campos de los eventos que quedan solo en el log de
    desarrollo (`_log_desarrollo` del backend)."""
    return [r.args[2] for r in caplog.records
            if r.name == "autoclave.backend.server" and isinstance(r.args, tuple)
            and len(r.args) == 3 and r.args[0] == evento]


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


def test_cada_orden_queda_en_el_log_con_el_origen(entorno, caplog):
    cliente, ctx, _, _ = entorno
    with caplog.at_level(logging.INFO):
        _orden(cliente, "Puerta 1", source_door=1)
    assert _eventos(ctx, "puerta_orden") == []                   # D9-6: fuera de la bitácora
    (e,) = _log_dev(caplog, "puerta_orden")
    assert e["entidad"] == "Puerta 1" and e["source_door"] == 1


def test_orden_rechazada_tambien_queda_en_el_log(entorno, caplog):
    cliente, ctx, _, _ = entorno
    with caplog.at_level(logging.INFO):
        _orden(cliente, "Puerta 2", source_door=1)
    assert _eventos(ctx, "puerta_orden_rechazada") == []
    (e,) = _log_dev(caplog, "puerta_orden_rechazada")
    assert e["codigo"] == "puerta_ajena" and e["source_door"] == 1


def test_sin_source_door_queda_como_desconocido(entorno, caplog):
    cliente, ctx, _, _ = entorno
    with caplog.at_level(logging.INFO):
        assert _orden(cliente, "Puerta 1").status_code == 200
    (e,) = _log_dev(caplog, "puerta_orden")
    assert e["source_door"] == "desconocido"

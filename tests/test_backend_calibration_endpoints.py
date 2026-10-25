import textwrap
import pytest
from unittest.mock import MagicMock

from tests.helpers.backend_doble import cabecera, cargar_servidor, fijar_en_backend


@pytest.fixture
def calib_client(tmp_path):
    yaml_path = tmp_path / "calibration.yaml"
    yaml_path.write_text(textwrap.dedent("""
        calibration:
          user:
            temperature:
              - gain: 1.0
                offset: 0.0
            pressure:
              - gain: 1.3466
                offset: -67.11
    """), encoding="utf-8")

    mock_ctx = MagicMock()
    mock_ctx.db.get_auditoria.return_value = []   # sin cambios en audit_log
    srv, _ = cargar_servidor(mock_ctx)

    fijar_en_backend("CALIBRATION_PATH", yaml_path)

    from fastapi.testclient import TestClient
    # solo ingeniero calibra (planeacion_backend_autenticacion.md, decisión 25)
    return TestClient(srv.app, headers=cabecera(srv, "ingeniero")), mock_ctx, yaml_path


def test_get_calibration_404_tipo_invalido(calib_client):
    client, _, _ = calib_client
    resp = client.get("/calibration/no_existe/temp_camara")
    assert resp.status_code == 404


def test_get_calibration_404_sensor_invalido(calib_client):
    client, _, _ = calib_client
    resp = client.get("/calibration/temperature/no_existe")
    assert resp.status_code == 404


def test_get_calibration_devuelve_valores_actuales(calib_client):
    client, mock_ctx, _ = calib_client
    mock_ctx.calibration_audit.get_last_change.return_value = None
    resp = client.get("/calibration/pressure/pres_camara")
    assert resp.status_code == 200
    data = resp.json()
    assert data["gain"] == 1.3466
    assert data["offset"] == -67.11
    assert data["is_poly"] is False
    assert data["poly"] is None
    assert data["last_change"] is None


def test_patch_calibration_422_valores_faltantes(calib_client):
    client, _, _ = calib_client
    resp = client.patch("/calibration/pressure/pres_camara", json={"shown_low": 12.0})
    assert resp.status_code == 422


def test_patch_calibration_422_puntos_iguales(calib_client):
    client, _, _ = calib_client
    resp = client.patch("/calibration/pressure/pres_camara", json={
        "shown_low": 12.0, "real_low": 9.54, "shown_high": 12.0, "real_high": 300.0,
    })
    assert resp.status_code == 422


def test_patch_calibration_sin_git_autocommit(calib_client):
    # decisión 9: git_autocommit se eliminó del backend
    import autoclave.backend.server as srv
    assert not hasattr(srv, "git_autocommit")


def test_patch_calibration_actualiza_yaml_recarga_y_audita(calib_client):
    client, mock_ctx, yaml_path = calib_client
    resp = client.patch("/calibration/pressure/pres_camara", json={
        "shown_low": 12.0, "real_low": 9.54, "shown_high": 322.0, "real_high": 300.0,
        "usuario": "tecnico1",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert round(data["gain"], 6) == pytest.approx(1.261721, abs=1e-6)
    assert round(data["offset"], 6) == pytest.approx(-64.583518, abs=1e-5)

    on_disk = yaml_path.read_text(encoding="utf-8")
    assert "1.261721" in on_disk

    mock_ctx.units.reload_calibration.assert_called_once_with(yaml_path)

    # auditoría en audit_log con el usuario del token; `usuario` del cuerpo se
    # ignora y la tabla histórica ya no recibe escrituras (§5.10)
    mock_ctx.calibration_audit.log_change.assert_not_called()
    mock_ctx.db.registrar_auditoria.assert_called_once()
    args, kwargs = mock_ctx.db.registrar_auditoria.call_args
    assert args[0] == "calibracion_cambio"
    assert kwargs["usuario"] == "usuario_ingeniero"
    assert kwargs["rol"] == "ingeniero"
    assert kwargs["entidad"] == "pressure/pres_camara"
    assert kwargs["valor_anterior"] == {"gain": 1.3466, "offset": -67.11}
    assert kwargs["valor_nuevo"]["gain"] == pytest.approx(1.261721, abs=1e-6)


# ── B-ES-3 / D-ES-13: origen de la lectura (capturada o escrita) ────────────

_PUNTOS = {"shown_low": 12.0, "real_low": 9.54, "shown_high": 322.0, "real_high": 300.0}


def test_patch_origen_lectura_valido_queda_en_detalle(calib_client):
    client, ctx, _ = calib_client
    origen = {"bajo": "capturada", "alto": "escrita"}
    resp = client.patch("/calibration/pressure/pres_camara",
                        json={**_PUNTOS, "origen_lectura": origen})
    assert resp.status_code == 200, resp.text
    detalle = ctx.db.registrar_auditoria.call_args.kwargs["detalle"]
    assert detalle["origen_lectura"] == origen


@pytest.mark.parametrize("origen", [
    {"bajo": "capturada"},                          # falta alto
    {"bajo": "capturada", "alto": "manual"},         # valor inválido
    {"bajo": "capturada", "alto": "escrita", "x": 1},
    "capturada",
    [],
])
def test_patch_origen_lectura_invalido_422(calib_client, origen):
    client, ctx, yaml_path = calib_client
    previo = yaml_path.read_text(encoding="utf-8")
    resp = client.patch("/calibration/pressure/pres_camara",
                        json={**_PUNTOS, "origen_lectura": origen})
    assert resp.status_code == 422
    assert yaml_path.read_text(encoding="utf-8") == previo
    ctx.db.registrar_auditoria.assert_not_called()


def test_patch_sin_origen_lectura_sigue_aceptado_para_clientes_antiguos(calib_client):
    client, ctx, _ = calib_client
    assert client.patch("/calibration/pressure/pres_camara", json=_PUNTOS).status_code == 200
    assert "origen_lectura" not in ctx.db.registrar_auditoria.call_args.kwargs["detalle"]


# ── B-ES-4 / §7.4: restaurar por defecto y último ───────────────────────────

def _ruta(sensor="pres_camara"):
    return f"/calibration/pressure/{sensor}/restaurar"


def test_restaurar_defecto_deja_calibracion_neutra_y_audita(calib_client):
    client, ctx, yaml_path = calib_client
    resp = client.post(_ruta(), json={"destino": "defecto"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["gain"] == 1.0 and resp.json()["offset"] == 0.0
    ctx.units.reload_calibration.assert_called_once_with(yaml_path)
    args, kwargs = ctx.db.registrar_auditoria.call_args
    assert args[0] == "calibracion_cambio"
    assert kwargs["valor_anterior"] == {"gain": 1.3466, "offset": -67.11}
    assert kwargs["valor_nuevo"] == {"gain": 1.0, "offset": 0.0}
    assert kwargs["detalle"]["accion"] == "restaurar_defecto"


def test_restaurar_ultimo_usa_valor_anterior_de_la_ultima_modificacion(calib_client):
    client, ctx, _ = calib_client
    ctx.db.get_auditoria.return_value = [{
        "ts": "2026-10-01T10:00:00", "usuario": "ing", "valor_anterior": '{"gain": 1.1, "offset": -2.5}',
    }]
    resp = client.post(_ruta(), json={"destino": "ultimo"})
    assert resp.status_code == 200, resp.text
    assert (resp.json()["gain"], resp.json()["offset"]) == (1.1, -2.5)
    assert ctx.db.registrar_auditoria.call_args.kwargs["detalle"]["accion"] == "restaurar_ultimo"


def test_restaurar_ultimo_sin_historial_409(calib_client):
    client, ctx, yaml_path = calib_client
    ctx.db.get_auditoria.return_value = []
    previo = yaml_path.read_text(encoding="utf-8")
    resp = client.post(_ruta(), json={"destino": "ultimo"})
    assert resp.status_code == 409
    assert yaml_path.read_text(encoding="utf-8") == previo


@pytest.mark.parametrize("cuerpo", [{}, {"destino": "otro"}, {"destino": 3}])
def test_restaurar_destino_invalido_422(calib_client, cuerpo):
    client, _, _ = calib_client
    assert client.post(_ruta(), json=cuerpo).status_code == 422


def test_restaurar_sensor_desconocido_404(calib_client):
    client, _, _ = calib_client
    assert client.post(_ruta("no_existe"), json={"destino": "defecto"}).status_code == 404


def test_restaurar_falla_la_auditoria_revierte_el_archivo(calib_client):
    client, ctx, yaml_path = calib_client
    previo = yaml_path.read_text(encoding="utf-8")
    ctx.db.registrar_auditoria.side_effect = RuntimeError("bd")
    resp = client.post(_ruta(), json={"destino": "defecto"})
    assert resp.status_code == 503
    assert yaml_path.read_text(encoding="utf-8") == previo


def test_restaurar_sin_base_de_datos_503(calib_client):
    client, ctx, _ = calib_client
    ctx.sin_base_de_datos = True
    assert client.post(_ruta(), json={"destino": "defecto"}).status_code == 503


def test_restaurar_ingeniero_permitido_en_ciclo(calib_client):
    from autoclave.state_machine.machine.enum_global import GlobalState
    client, ctx, _ = calib_client
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    assert client.post(_ruta(), json={"destino": "defecto"}).status_code == 200


def test_restaurar_tecnico_en_ciclo_409(calib_client):
    from autoclave.state_machine.machine.enum_global import GlobalState
    from tests.helpers.backend_doble import cabecera
    client, ctx, _ = calib_client
    ctx.estado.get_machine_state.return_value = GlobalState.CICLO
    srv = __import__("autoclave.backend.server", fromlist=["x"])
    resp = client.post(_ruta(), json={"destino": "defecto"}, headers=cabecera(srv, "tecnico"))
    assert resp.status_code == 409

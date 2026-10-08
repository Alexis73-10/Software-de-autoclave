import textwrap
import pytest
from unittest.mock import MagicMock

from tests.backend_doble import cabecera, cargar_servidor


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

    srv.CALIBRATION_PATH = yaml_path

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

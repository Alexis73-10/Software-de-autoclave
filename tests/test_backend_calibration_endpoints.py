import sys
import importlib
import textwrap
import pytest
from unittest.mock import MagicMock, patch


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

    for key in list(sys.modules):
        if "autoclave.backend.server" in key:
            del sys.modules[key]

    with patch("autoclave.backend.context.BackendContext", return_value=mock_ctx):
        srv = importlib.import_module("autoclave.backend.server")

    srv.CALIBRATION_PATH = yaml_path

    from fastapi.testclient import TestClient
    return TestClient(srv.app), mock_ctx, yaml_path


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

    mock_ctx.calibration_audit.log_change.assert_called_once()
    args = mock_ctx.calibration_audit.log_change.call_args.args
    assert args[0] == "pressure"
    assert args[1] == "pres_camara"
    assert args[-1] == "tecnico1"

import pytest
from autoclave.services.domain.logging.sensor_calibration_audit import SensorCalibrationAuditDB


@pytest.fixture
def db(tmp_path):
    return SensorCalibrationAuditDB(db_path=tmp_path / "test.db")


def test_get_last_change_returns_none_when_no_history(db):
    assert db.get_last_change("temperature", "temp_camara") is None


def test_log_and_retrieve_last_change(db):
    db.log_change(
        "temperature", "temp_camara", 20.0, 20.0, 131.3, 132.5,
        None, None, 1.010345, 1.090435, "admin",
    )
    result = db.get_last_change("temperature", "temp_camara")
    assert result is not None
    assert result["usuario"] == "admin"
    assert len(result["timestamp"]) == 16   # "YYYY-MM-DD HH:MM"


def test_get_last_change_returns_most_recent(db):
    db.log_change("pressure", "pres_camara", 12.0, 9.0, 322.0, 299.0,
                   1.3466, -67.11, 1.26, -64.5, "user1")
    db.log_change("pressure", "pres_camara", 12.0, 9.54, 322.0, 300.0,
                   1.26, -64.5, 1.261721, -64.583518, "user2")
    assert db.get_last_change("pressure", "pres_camara")["usuario"] == "user2"


def test_get_last_change_distingue_por_sensor(db):
    db.log_change("temperature", "temp_camara", 20.0, 20.0, 131.3, 132.5,
                   None, None, 1.010345, 1.090435, "admin")
    assert db.get_last_change("temperature", "temp_chaqueta") is None

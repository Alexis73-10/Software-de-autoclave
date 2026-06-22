import pytest
from autoclave.services.domain.logging.cycle_params_audit import CycleParamsAuditDB


@pytest.fixture
def db(tmp_path):
    return CycleParamsAuditDB(db_path=tmp_path / "test.db")


def test_get_last_change_returns_none_when_no_history(db):
    assert db.get_last_change("c1", "purga", "tiempo_purga") is None


def test_log_and_retrieve_last_change(db):
    db.log_change("c1", "purga", "tiempo_purga", 0, 5, "admin")
    result = db.get_last_change("c1", "purga", "tiempo_purga")
    assert result is not None
    assert result["usuario"] == "admin"
    assert len(result["timestamp"]) == 16   # "YYYY-MM-DD HH:MM"


def test_get_last_change_returns_most_recent(db):
    db.log_change("c1", "purga", "tiempo_purga", 0, 3, "user1")
    db.log_change("c1", "purga", "tiempo_purga", 3, 7, "user2")
    assert db.get_last_change("c1", "purga", "tiempo_purga")["usuario"] == "user2"

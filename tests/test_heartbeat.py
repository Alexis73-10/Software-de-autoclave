import json
from datetime import datetime
from pathlib import Path


def test_write_timestamp_crea_archivo(tmp_path):
    from autoclave.devices.printer.heartbeat import write_timestamp
    p = tmp_path / "last_shutdown.json"
    write_timestamp(p)
    assert p.exists()


def test_write_timestamp_es_iso_valido(tmp_path):
    from autoclave.devices.printer.heartbeat import write_timestamp
    p = tmp_path / "last_shutdown.json"
    write_timestamp(p)
    data = json.loads(p.read_text())
    dt = datetime.fromisoformat(data["timestamp"])
    assert isinstance(dt, datetime)


def test_read_last_shutdown_parsea_fecha(tmp_path):
    from autoclave.devices.printer.heartbeat import read_last_shutdown
    p = tmp_path / "last_shutdown.json"
    p.write_text(json.dumps({"timestamp": "2026-07-02T10:15:08"}))
    dt = read_last_shutdown(p)
    assert dt == datetime(2026, 7, 2, 10, 15, 8)


def test_read_last_shutdown_ausente_retorna_none(tmp_path):
    from autoclave.devices.printer.heartbeat import read_last_shutdown
    p = tmp_path / "no_existe.json"
    assert read_last_shutdown(p) is None


def test_read_last_shutdown_corrupto_retorna_none(tmp_path):
    from autoclave.devices.printer.heartbeat import read_last_shutdown
    p = tmp_path / "last_shutdown.json"
    p.write_text("esto-no-es-json-{{{")
    assert read_last_shutdown(p) is None

# tests/test_clock_guard.py
import pytest
from datetime import datetime, timedelta
from autoclave.installation.clock_guard import check_system_clock, ClockTamperedError

INSTALLED_AT = datetime(2026, 5, 20, 10, 0, 0)


def test_clock_ok_when_today_is_after_install(monkeypatch):
    monkeypatch.setattr(
        "autoclave.installation.clock_guard._today",
        lambda: (INSTALLED_AT + timedelta(days=4)).date(),
    )
    check_system_clock(INSTALLED_AT)  # should not raise


def test_clock_ok_same_day(monkeypatch):
    monkeypatch.setattr(
        "autoclave.installation.clock_guard._today",
        lambda: INSTALLED_AT.date(),
    )
    check_system_clock(INSTALLED_AT)  # should not raise


def test_clock_tampered_when_today_is_before_install(monkeypatch):
    monkeypatch.setattr(
        "autoclave.installation.clock_guard._today",
        lambda: (INSTALLED_AT - timedelta(days=1)).date(),
    )
    with pytest.raises(ClockTamperedError):
        check_system_clock(INSTALLED_AT)


def test_clock_tampered_message_contains_dates(monkeypatch):
    monkeypatch.setattr(
        "autoclave.installation.clock_guard._today",
        lambda: (INSTALLED_AT - timedelta(days=1)).date(),
    )
    with pytest.raises(ClockTamperedError, match="2026-05-19"):
        check_system_clock(INSTALLED_AT)

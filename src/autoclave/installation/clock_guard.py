# src/autoclave/installation/clock_guard.py
from datetime import datetime, date


class ClockTamperedError(Exception):
    pass


def _today() -> date:
    return date.today()


def check_system_clock(installed_at: datetime) -> None:
    today = _today()
    if today < installed_at.date():
        raise ClockTamperedError(
            f"Reloj del sistema ({today}) es anterior a la fecha de instalación "
            f"({installed_at.date()}). Verifique la fecha y hora del sistema."
        )

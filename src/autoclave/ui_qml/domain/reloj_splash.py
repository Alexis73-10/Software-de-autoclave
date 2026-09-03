# src/autoclave/ui_qml/domain/reloj_splash.py
from datetime import datetime

_MESES = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
]


def formatear_hora(dt: datetime) -> str:
    return f"{dt.hour:02d}:{dt.minute:02d}"


def formatear_fecha(dt: datetime) -> str:
    mes = _MESES[dt.month - 1]
    return f"{dt.day:02d} {mes} - {dt.year}"

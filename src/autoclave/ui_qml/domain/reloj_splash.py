# src/autoclave/ui_qml/domain/reloj_splash.py
from datetime import datetime

_MESES = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
]


def formatear_hora(dt: datetime) -> str:
    return f"{dt.hour:02d}:{dt.minute:02d}"


def formatear_fecha(dt: datetime, idioma: str | None = None) -> str:
    mes = _MESES[dt.month - 1]
    try:                                   # I4 (tanda 6): mes del catálogo
        from autoclave import i18n
        meses = i18n.valor("fecha.meses", idioma)
        if isinstance(meses, list) and len(meses) == 12:
            mes = str(meses[dt.month - 1]).lower()
    except Exception:
        pass
    return f"{dt.day:02d} {mes} - {dt.year}"

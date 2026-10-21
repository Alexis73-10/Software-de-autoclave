from datetime import datetime

# Mismo estilo de divisor corto que ticket_formatter.py (confirmado
# funcionando en la impresora térmica real) — las barras de 48 "=" y el
# título centrado que este ticket usaba antes fueron el formato que se
# abandonó ahí por dar problemas de impresión.
_DIV = "-" * 24

_MENSAJES = {
    ("TARJETA", False): "TARJETA: DESCONECTADA",
    ("TARJETA", True):  "TARJETA: RECONECTADA",
    ("BACKEND", False): "BACKEND: SIN RESPUESTA",
    ("BACKEND", True):  "BACKEND: RECONECTADO",
}
# I4 (tanda 6): en inglés (cp437, sin tildes); la clave sigue siendo el código
_MENSAJES_EN = {
    ("TARJETA", False): "BOARD: DISCONNECTED",
    ("TARJETA", True):  "BOARD: RECONNECTED",
    ("BACKEND", False): "BACKEND: NOT RESPONDING",
    ("BACKEND", True):  "BACKEND: RECONNECTED",
}


def _idioma(idioma: str | None) -> str:
    if idioma in ("es", "en"):
        return idioma
    try:
        from autoclave.services.domain.logging.ticket_formatter import presentacion_actual
        return presentacion_actual().idioma
    except Exception:
        return "es"


def format_connectivity_ticket(subsystem: str, ok: bool, when: datetime,
                               idioma: str | None = None) -> str:
    mensajes = _MENSAJES_EN if _idioma(idioma) == "en" else _MENSAJES
    mensaje = mensajes[(subsystem, ok)]
    lines = [
        " ",
        _DIV,
        mensaje,
        when.strftime("%Y-%m-%d %H:%M:%S"),
        _DIV,
    ] + [""] * 5  # avance de papel en blanco para poder cortar sin abrir la tapa
    return "\n".join(lines)

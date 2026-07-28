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


def format_connectivity_ticket(subsystem: str, ok: bool, when: datetime) -> str:
    mensaje = _MENSAJES[(subsystem, ok)]
    lines = [
        " ",
        _DIV,
        mensaje,
        when.strftime("%Y-%m-%d %H:%M:%S"),
        _DIV,
    ] + [""] * 5  # avance de papel en blanco para poder cortar sin abrir la tapa
    return "\n".join(lines)

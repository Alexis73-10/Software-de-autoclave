from datetime import datetime

# Mismo estilo de divisor corto que ticket_formatter.py (confirmado
# funcionando en la impresora térmica real) — las barras de 48 "=" y el
# título centrado que este ticket usaba antes fueron el formato que se
# abandonó ahí por dar problemas de impresión.
_DIV = "-" * 24

# MES-01 (tanda 23): "MODULO" sin tilde: cp437 no tiene la "Ó" mayúscula.
_MENSAJES = {
    ("MODULO_ES", False): "MODULO E/S: DESCONECTADO",
    ("MODULO_ES", True):  "MODULO E/S: RECONECTADO",
    ("BACKEND", False): "BACKEND: SIN RESPUESTA",
    ("BACKEND", True):  "BACKEND: RECONECTADO",
}
# I4 (tanda 6): en inglés (cp437, sin tildes); la clave sigue siendo el código
_MENSAJES_EN = {
    ("MODULO_ES", False): "I/O MODULE: DISCONNECTED",
    ("MODULO_ES", True):  "I/O MODULE: RECONNECTED",
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

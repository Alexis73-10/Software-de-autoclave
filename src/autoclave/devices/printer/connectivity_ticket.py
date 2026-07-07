from datetime import datetime

_W   = 48
_SEP = "=" * _W

_MENSAJES = {
    ("TARJETA", False): "TARJETA: DESCONECTADA",
    ("TARJETA", True):  "TARJETA: RECONECTADA",
    ("BACKEND", False): "BACKEND: SIN RESPUESTA",
    ("BACKEND", True):  "BACKEND: RECONECTADO",
}


def format_connectivity_ticket(subsystem: str, ok: bool, when: datetime) -> str:
    mensaje = _MENSAJES[(subsystem, ok)]
    lines = [
        _SEP,
        "ESPECIFIKA -- AUTOCLAVE".center(_W),
        _SEP,
        f" {mensaje}",
        f" {when.strftime('%Y-%m-%d %H:%M:%S')}",
        _SEP,
        "",
    ]
    return "\n".join(lines)

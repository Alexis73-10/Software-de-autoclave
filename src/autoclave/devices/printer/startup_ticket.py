# devices/printer/startup_ticket.py
#
# Ticket de arranque del equipo. I4 (tanda 6; I18N-18): el estado de cada
# subsistema es un CÓDIGO ("ok", "fallo", "sin_datos") y el rótulo se busca al
# imprimir, en el idioma vigente; "Sistema listo" / "FALLO EN ARRANQUE" se
# decide por el código, nunca comparando el texto mostrado. Todo el texto es
# cp437 (impresora térmica): sin tildes en inglés y solo caracteres de cp437
# en español.

from datetime import datetime
from autoclave.installation.profile import InstallationProfile

_W   = 48
_SEP = "=" * _W
_DIV = "-" * _W

OK, FALLO, SIN_DATOS = "ok", "fallo", "sin_datos"
ESTADOS = (OK, FALLO, SIN_DATOS)

_TXT = {
    "es": {"modelo": "Modelo:", "serie": "Serie:", "clase": "Clase:", "software": "Software:",
           "encendido": "ENCENDIDO", "apagado": "APAGADO", "primer": "Primer encendido",
           "listo": "Sistema listo", "fallo_arranque": "** FALLO EN ARRANQUE **",
           OK: "OK", FALLO: "FALLO", SIN_DATOS: "Sin datos",
           "backend": "Backend", "tarjeta": "Tarjeta"},
    "en": {"modelo": "Model:", "serie": "Serial:", "clase": "Class:", "software": "Software:",
           "encendido": "POWER ON", "apagado": "POWER OFF", "primer": "First power-on",
           "listo": "System ready", "fallo_arranque": "** STARTUP FAILURE **",
           OK: "OK", FALLO: "FAILED", SIN_DATOS: "No data",
           "backend": "Backend", "tarjeta": "Control board"},
}

# Valores de texto antiguos (antes de I18N-18): se siguen aceptando
_LEGADO = {"OK": OK, "FALLO": FALLO, "ERROR": FALLO, "Sin datos": SIN_DATOS}


def _idioma(idioma: str | None) -> str:
    if idioma in _TXT:
        return idioma
    try:
        from autoclave.services.domain.logging.ticket_formatter import presentacion_actual
        return presentacion_actual().idioma
    except Exception:
        return "es"


def _estado(valor) -> str:
    """Código de estado; un valor desconocido cuenta como fallo (falla cerrada)."""
    if valor in ESTADOS:
        return valor
    return _LEGADO.get(valor, FALLO)


def format_startup_ticket(
    profile: InstallationProfile,
    version: str,
    last_shutdown: datetime | None,
    startup_time: datetime,
    status: list[tuple[str, str]] | None = None,
    idioma: str | None = None,
) -> str:
    """status: [(subsistema, código)]; el subsistema "backend"/"tarjeta" se
    traduce, otro se imprime tal cual."""
    tx = _TXT[_idioma(idioma)]
    apagado = (
        last_shutdown.strftime("%Y-%m-%d  %H:%M:%S")
        if last_shutdown is not None
        else tx["primer"]
    )
    estados = [(rotulo, _estado(valor)) for rotulo, valor in (status or [])]
    all_ok = all(codigo == OK for _, codigo in estados)
    footer = tx["listo"] if all_ok else tx["fallo_arranque"]

    lines = [
        _SEP,
        "ESPECIFIKA -- AUTOCLAVE".center(_W),
        _SEP,
        f"{tx['modelo']:<16}{profile.model_id}",
        f"{tx['serie']:<16}{profile.serial_number}",
        f"{tx['clase']:<16}{profile.equipment_class.value}",
        f"{tx['software']:<16}v{version}",
        _DIV,
        f"{tx['encendido']:<16}{startup_time.strftime('%Y-%m-%d  %H:%M:%S')}",
        f"{tx['apagado']:<16}{apagado}",
    ]
    if estados:
        lines.append(_DIV)
        for rotulo, codigo in estados:
            nombre = tx.get(str(rotulo).lower(), rotulo) if str(rotulo).lower() in ("backend", "tarjeta") else rotulo
            lines.append(f"{nombre + ':':<16}{tx[codigo]}")
    lines += [
        _DIV,
        footer.center(_W),
        _SEP,
    ] + [""] * 5  # avance de papel en blanco para poder cortar sin abrir la tapa
    return "\n".join(lines)

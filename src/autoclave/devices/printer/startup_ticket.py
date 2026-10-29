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
           "backend": "Backend", "modulo_es": "Módulo E/S"},
    "en": {"modelo": "Model:", "serie": "Serial:", "clase": "Class:", "software": "Software:",
           "encendido": "POWER ON", "apagado": "POWER OFF", "primer": "First power-on",
           "listo": "System ready", "fallo_arranque": "** STARTUP FAILURE **",
           OK: "OK", FALLO: "FAILED", SIN_DATOS: "No data",
           "backend": "Backend", "modulo_es": "I/O module"},
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


def _nombre_clase(clase, idioma: str) -> str:
    """E2 (tanda 8; D8-0): nombre de la familia desde el catálogo i18n
    ("Hospitalario"/"Laboratorio"); el valor interno solo si no hay texto."""
    valor = str(getattr(clase, "value", clase))
    try:
        from autoclave import i18n
        clave = f"equipo.clase_{valor}"
        if i18n.existe(clave, idioma):
            return i18n.t(clave, idioma)
    except Exception:
        pass
    return valor


def _estado(valor) -> str:
    """Código de estado; un valor desconocido cuenta como fallo (falla cerrada)."""
    if valor in ESTADOS:
        return valor
    return _LEGADO.get(valor, FALLO)


def _lineas_software(rotulo: str, version: str) -> list[str]:
    """VER-05: la versión de una compilación de verificación
    ("1.0.0-alpha.2.dev+g1a2b3c4.sucio") puede no caber junto al rótulo: va
    entonces en la línea siguiente, sin cortarse."""
    linea = f"{rotulo:<16}v{version}"
    if len(linea) <= _W:
        return [linea]
    return [rotulo, f"  v{version}"[:_W]]


def format_startup_ticket(
    profile: InstallationProfile,
    version: str,
    last_shutdown: datetime | None,
    startup_time: datetime,
    status: list[tuple[str, str]] | None = None,
    idioma: str | None = None,
) -> str:
    """status: [(subsistema, código)]; el subsistema "backend"/"modulo_es" se
    traduce, otro se imprime tal cual."""
    idioma = _idioma(idioma)
    tx = _TXT[idioma]
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
        f"{tx['clase']:<16}{_nombre_clase(profile.equipment_class, idioma)}",
        *_lineas_software(tx['software'], version),
        _DIV,
        f"{tx['encendido']:<16}{startup_time.strftime('%Y-%m-%d  %H:%M:%S')}",
        f"{tx['apagado']:<16}{apagado}",
    ]
    if estados:
        lines.append(_DIV)
        for rotulo, codigo in estados:
            nombre = tx.get(str(rotulo).lower(), rotulo) if str(rotulo).lower() in ("backend", "modulo_es") else rotulo
            lines.append(f"{nombre + ':':<16}{tx[codigo]}")
    lines += [
        _DIV,
        footer.center(_W),
        _SEP,
    ] + [""] * 5  # avance de papel en blanco para poder cortar sin abrir la tapa
    return "\n".join(lines)

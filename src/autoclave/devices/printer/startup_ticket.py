from datetime import datetime
from autoclave.installation.profile import InstallationProfile

_W   = 48
_SEP = "=" * _W
_DIV = "-" * _W


def format_startup_ticket(
    profile: InstallationProfile,
    version: str,
    last_shutdown: datetime | None,
    startup_time: datetime,
    status: list[tuple[str, str]] | None = None,
) -> str:
    apagado = (
        last_shutdown.strftime("%Y-%m-%d  %H:%M:%S")
        if last_shutdown is not None
        else "Primer encendido"
    )
    all_ok = status is None or all(v not in ("FALLO", "ERROR", "Sin datos") for _, v in status)
    footer = "Sistema listo" if all_ok else "** FALLO EN ARRANQUE **"

    lines = [
        _SEP,
        "ESPECIFIKA -- AUTOCLAVE".center(_W),
        _SEP,
        f"{'Modelo:':<16}{profile.model_id}",
        f"{'Serie:':<16}{profile.serial_number}",
        f"{'Clase:':<16}{profile.equipment_class.value}",
        f"{'Software:':<16}v{version}",
        _DIV,
        f"{'ENCENDIDO':<16}{startup_time.strftime('%Y-%m-%d  %H:%M:%S')}",
        f"{'APAGADO':<16}{apagado}",
    ]
    if status:
        lines.append(_DIV)
        for label, value in status:
            lines.append(f"{label + ':':<16}{value}")
    lines += [
        _DIV,
        footer.center(_W),
        _SEP,
    ] + [""] * 5  # avance de papel en blanco para poder cortar sin abrir la tapa
    return "\n".join(lines)

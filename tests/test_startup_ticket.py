from datetime import datetime
from unittest.mock import MagicMock
from autoclave.installation.equipment import EquipmentClass


def _profile():
    p = MagicMock()
    p.model_id = "MESA_B"
    p.serial_number = "AUT-2024-001"
    p.equipment_class = EquipmentClass.MESA_B
    return p


def test_ticket_contiene_modelo():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
    )
    assert "MESA_B" in text


def test_ticket_contiene_serie():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
    )
    assert "AUT-2024-001" in text


def test_ticket_contiene_version():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
    )
    assert "v0.4.0" in text


def test_ticket_contiene_hora_encendido():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
    )
    assert "10:47:23" in text


def test_ticket_contiene_hora_apagado():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
    )
    assert "10:15:08" in text


def test_ticket_primer_encendido_cuando_none():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        None,
        datetime(2026, 7, 2, 10, 47, 23),
    )
    assert "Primer encendido" in text


def test_ninguna_linea_supera_48_chars():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
    )
    for linea in text.splitlines():
        assert len(linea) <= 48, f"Línea demasiado larga ({len(linea)}): {linea!r}"


def test_status_aparece_en_ticket():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
        status=[("Backend", "OK"), ("Tarjeta", "OK")],
    )
    assert "Backend:" in text
    assert "Tarjeta:" in text


def test_footer_fallo_cuando_hay_error():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        None,
        datetime(2026, 7, 2, 10, 47, 23),
        status=[("Backend", "FALLO"), ("Tarjeta", "FALLO")],
    )
    assert "FALLO EN ARRANQUE" in text
    assert "Sistema listo" not in text


def test_footer_sistema_listo_cuando_ok():
    from autoclave.devices.printer.startup_ticket import format_startup_ticket
    text = format_startup_ticket(
        _profile(), "0.4.0",
        datetime(2026, 7, 2, 10, 15, 8),
        datetime(2026, 7, 2, 10, 47, 23),
        status=[("Backend", "OK"), ("Tarjeta", "OK")],
    )
    assert "Sistema listo" in text
    assert "FALLO" not in text

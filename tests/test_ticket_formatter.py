from autoclave.services.domain.logging.ticket_formatter import (
    format_footer,
    format_header,
    format_row,
    format_ticket,
)


def _ciclo():
    return {
        "numero_ciclo": 7,
        "serie": "SN-001",
        "modelo": "SPK-AVH-450",
        "version_sw": "0.4.0",
        "nombre_ciclo": "Bowie-Dick",
        "tipo_ciclo": "bowe_dick",
        "temp_esterilizacion": 134.0,
        "tiempo_esterilizacion": 3.5,
        "fecha_inicio": "2026-07-06T08:00:00",
        "fecha_fin": "2026-07-06T08:45:00",
        "resultado": "COMPLETADO",
        "motivo_fallo": "",
    }


def _lecturas():
    return [
        {"fase_codigo": "PH", "timestamp_rel": "00:00:00", "temp_camara": 25.0, "pres_camara": 74.5},
        {"fase_codigo": "S", "timestamp_rel": "00:20:00", "temp_camara": 134.2, "pres_camara": 210.0},
        {"fase_codigo": "E", "timestamp_rel": "00:45:00", "temp_camara": 60.0, "pres_camara": 75.0},
    ]


def test_format_header_incluye_numero_de_ciclo_y_serie():
    header = format_header(_ciclo())
    assert "Ciclo No.: 000007" in header
    assert "Num serie: SN-001" in header
    assert "Modelo: SPK-AVH-450" in header
    assert "SoftW.: 0.4.0" in header


def test_format_header_incluye_temp_y_tiempo_esterilizacion():
    header = format_header(_ciclo())
    assert "Temp. Ester.: 134.0 C" in header
    assert "Tiempo Ester.: 3.5 min" in header


def test_format_header_no_incluye_temp_final():
    """Temp. final sólo se conoce al cerrar el ciclo — no puede ir en el
    encabezado de un ticket que se imprime en tiempo real."""
    header = format_header(_ciclo())
    assert "Temp. final" not in header


def test_format_row_formatea_una_lectura():
    row = format_row({"fase_codigo": "S", "timestamp_rel": "00:20:00", "temp_camara": 134.2, "pres_camara": 210.0})
    assert row == "S 00:20:00 0134.2 0210.0"


def test_format_row_maneja_valores_none():
    row = format_row({"fase_codigo": "F", "timestamp_rel": "00:05:00", "temp_camara": None, "pres_camara": None})
    assert "--" in row


def test_format_footer_incluye_estado_y_hora_fin():
    footer = format_footer("COMPLETADO", "2026-07-06T08:45:00")
    assert "Estado: COMPLETADO" in footer
    assert "Hora fin: 08:45:00" in footer


def test_format_footer_incluye_temp_final():
    footer = format_footer("COMPLETADO", "2026-07-06T08:45:00", temp_final=60.0)
    assert "Temp. final: 60 C" in footer


def test_format_footer_sin_motivo_no_agrega_linea():
    footer = format_footer("COMPLETADO", "2026-07-06T08:45:00")
    assert "Motivo:" not in footer


def test_format_footer_con_motivo_agrega_linea():
    footer = format_footer(
        "FALLO_ESTERILIZACION", "2026-07-06T08:45:00",
        motivo="Temperatura baja: 100.0°C < 134.0°C",
    )
    assert "Motivo: Temperatura baja: 100.0°C < 134.0°C" in footer


def test_format_footer_termina_con_avance_de_papel_para_corte():
    """Deja suficiente papel en blanco al final para poder cortar sin tener
    que avanzarlo manualmente."""
    footer = format_footer("COMPLETADO", "2026-07-06T08:45:00")
    lineas = footer.split("\n")
    assert lineas[-5:] == [""] * 5


def test_header_filas_pie_equivalen_a_format_ticket():
    ciclo = _ciclo()
    lecturas = _lecturas()

    ensamblado = "\n".join(
        [format_header(ciclo)]
        + [format_row(r) for r in lecturas]
        + [format_footer(
            ciclo["resultado"], ciclo["fecha_fin"],
            temp_final=lecturas[-1]["temp_camara"], motivo=None,
        )]
    )

    assert ensamblado == format_ticket(ciclo, lecturas)

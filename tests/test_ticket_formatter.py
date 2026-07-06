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
        "nombre_ciclo": "Bowie-Dick",
        "tipo_ciclo": "bowe_dick",
        "operador": "Juan",
        "temp_esterilizacion": 134.0,
        "tiempo_esterilizacion": 3.5,
        "fecha_inicio": "2026-07-06T08:00:00",
        "fecha_fin": "2026-07-06T08:45:00",
        "resultado": "COMPLETADO",
    }


def _lecturas():
    return [
        {"fase_codigo": "PH", "timestamp_rel": "00:00:00", "temp_camara": 25.0, "pres_camara": 74.5},
        {"fase_codigo": "S", "timestamp_rel": "00:20:00", "temp_camara": 134.2, "pres_camara": 210.0},
        {"fase_codigo": "E", "timestamp_rel": "00:45:00", "temp_camara": 60.0, "pres_camara": 75.0},
    ]


def test_format_header_incluye_numero_de_ciclo_y_serie():
    meta = _ciclo()
    header = format_header(meta)
    assert "00007" in header
    assert "SN-001" in header
    assert "ESPECIFIKA -- AUTOCLAVE MX-500" in header


def test_format_header_usa_tipo_ciclo_si_no_hay_nombre():
    meta = _ciclo()
    meta["nombre_ciclo"] = ""
    header = format_header(meta)
    assert "bowe_dick" in header


def test_format_row_formatea_una_lectura():
    row = format_row({"fase_codigo": "S", "timestamp_rel": "00:20:00", "temp_camara": 134.2, "pres_camara": 210.0})
    assert row == f"  {'00:20:00':<10}{'Esteriliz.':<12}{'134.2':>8}  {'210.0':>9}"


def test_format_row_maneja_valores_none():
    row = format_row({"fase_codigo": "F", "timestamp_rel": "00:05:00", "temp_camara": None, "pres_camara": None})
    assert "--" in row


def test_format_footer_incluye_resultado_y_fin():
    footer = format_footer("COMPLETADO", "2026-07-06T08:45:00")
    assert "Resultado:   COMPLETADO" in footer
    assert "2026-07-06 08:45:00" in footer


def test_header_filas_pie_equivalen_a_format_ticket():
    ciclo = _ciclo()
    lecturas = _lecturas()

    meta = {
        "numero_ciclo": ciclo["numero_ciclo"],
        "serie": ciclo["serie"],
        "nombre_ciclo": ciclo["nombre_ciclo"],
        "tipo_ciclo": ciclo["tipo_ciclo"],
        "operador": ciclo["operador"],
        "temp_esterilizacion": ciclo["temp_esterilizacion"],
        "tiempo_esterilizacion": ciclo["tiempo_esterilizacion"],
        "fecha_inicio": ciclo["fecha_inicio"],
    }
    ensamblado = "\n".join(
        [format_header(meta)]
        + [format_row(r) for r in lecturas]
        + [format_footer(ciclo["resultado"], ciclo["fecha_fin"])]
    )

    assert ensamblado == format_ticket(ciclo, lecturas)

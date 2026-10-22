# services/domain/logging/ticket_mantenimiento.py
#
# Tickets de Mantenimiento (O2f, tanda 6; planeacion_opciones.md v4 §3.4):
# página de prueba de la impresora y "ganancias y compensaciones" de todos los
# sensores. Mismo idioma vigente que el ticket de ciclo (presentacion_actual).
# Las ganancias y la presión de referencia son datos de calibración: van en
# kPa absolutos y sin convertir (regla 5 de la tanda 6: E/S y calibración
# quedan fuera del módulo de unidades). Texto cp437 (sin "°").

from datetime import datetime

from autoclave.services.domain.logging.ticket_formatter import presentacion_actual

ANCHO = 32

_TXT = {
    "es": {"prueba": "PAGINA DE PRUEBA", "impresora_ok": "Impresora funcionando",
           "fecha": "Fecha", "serie": "Num serie", "modelo": "Modelo",
           "caracteres": "Caracteres", "ganancias": "GANANCIAS Y COMPENSACIONES",
           "sensor": "Sensor", "ganancia": "Gan.", "compensacion": "Comp.",
           "polinomio": "polinomio", "temperatura": "Temperatura", "presion": "Presion",
           "atm": "P. atm. ref.", "calibrada": "Calibrada", "sin_dato": "sin dato",
           "fin": "--- fin ---"},
    "en": {"prueba": "TEST PAGE", "impresora_ok": "Printer working",
           "fecha": "Date", "serie": "Serial No", "modelo": "Model",
           "caracteres": "Characters", "ganancias": "GAINS AND OFFSETS",
           "sensor": "Sensor", "ganancia": "Gain", "compensacion": "Offs.",
           "polinomio": "polynomial", "temperatura": "Temperature", "presion": "Pressure",
           "atm": "Ref. atm. p.", "calibrada": "Calibrated", "sin_dato": "no data",
           "fin": "--- end ---"},
}


def _t(idioma: str, clave: str) -> str:
    return _TXT.get(idioma, _TXT["es"])[clave]


def _cabecera(titulo: str, meta: dict, idioma: str, ahora: datetime) -> list[str]:
    return [
        "=" * ANCHO,
        titulo.center(ANCHO),
        "=" * ANCHO,
        f"{_t(idioma, 'fecha')}: {ahora.strftime('%Y-%m-%d %H:%M')}",
        f"{_t(idioma, 'serie')}: {meta.get('serie', '')}",
        f"{_t(idioma, 'modelo')}: {meta.get('modelo', '')}",
        "-" * ANCHO,
    ]


def pagina_prueba(meta: dict, ahora: datetime | None = None, idioma: str | None = None) -> str:
    idioma = idioma or presentacion_actual().idioma
    ahora = ahora or datetime.now()
    lineas = _cabecera(_t(idioma, "prueba"), meta, idioma, ahora)
    lineas += [
        _t(idioma, "impresora_ok"),
        f"{_t(idioma, 'caracteres')}:",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "abcdefghijklmnopqrstuvwxyz",
        "0123456789 .,:;-+/()%",
        "1234567890" * 3 + "12",
        _t(idioma, "fin"),
        "",
    ]
    return "\n".join(lineas) + "\n"


def _num(v, decimales: int) -> str:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return "-"
    return f"{v:.{decimales}f}"


def ganancias(meta: dict, sensores: list[dict], p_atm=None, fecha_atm: str | None = None,
              ahora: datetime | None = None, idioma: str | None = None) -> str:
    """`sensores`: [{tipo, sensor, gain, offset, poly}] (calibración de usuario)."""
    idioma = idioma or presentacion_actual().idioma
    ahora = ahora or datetime.now()
    lineas = _cabecera(_t(idioma, "ganancias"), meta, idioma, ahora)
    for tipo, rotulo in (("temperature", "temperatura"), ("pressure", "presion")):
        grupo = [s for s in sensores if s.get("tipo") == tipo]
        if not grupo:
            continue
        lineas.append(_t(idioma, rotulo))
        lineas.append(f"  {_t(idioma, 'ganancia'):>13} {_t(idioma, 'compensacion'):>8}")
        for s in grupo:
            lineas.append(str(s.get("sensor", ""))[:ANCHO])
            if s.get("poly"):
                lineas.append(f"  {_t(idioma, 'polinomio')}")
            else:
                lineas.append(f"  {_num(s.get('gain'), 4):>13} {_num(s.get('offset'), 3):>8}")
        lineas.append("-" * ANCHO)
    atm = _num(p_atm, 2)
    lineas.append(f"{_t(idioma, 'atm')}: {atm + ' kPa abs' if atm != '-' else _t(idioma, 'sin_dato')}")
    if fecha_atm:
        lineas.append(f"{_t(idioma, 'calibrada')}: {str(fecha_atm)[:16].replace('T', ' ')}")
    lineas += [_t(idioma, "fin"), ""]
    return "\n".join(lineas) + "\n"

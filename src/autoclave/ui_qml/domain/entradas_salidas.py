# ui_qml/domain/entradas_salidas.py
#
# OPCIONES › Entradas / Salidas (planeacion_opciones_entradas_salidas.md): da
# forma a GET /status y GET /io/channels para QML. Sin datos vigentes de la
# tarjeta nunca se inventa un 0 (D-ES-04): el valor queda en None y la pantalla
# muestra "Sin datos". La UI no interpreta el significado de una entrada
# (ES-11): muestra el nivel crudo.

from autoclave.hal.measures.calibration_tools import fit_two_point, invert_user_calibration


def enlace_ok(status) -> bool:
    return (isinstance(status, dict) and status.get("estado_tarjeta") == "ok"
            and status.get("card_connected") is True)


def _sensores(status) -> dict:
    s = status.get("sensors") if isinstance(status, dict) else None
    return s if isinstance(s, dict) else {}


def _nivel(valor):
    if isinstance(valor, bool):
        return valor
    return (valor == 1) if isinstance(valor, int) and valor in (0, 1) else None


def presentar_entradas(canales, status) -> list[dict]:
    vivo = enlace_ok(status)
    crudas = _sensores(status).get("digital_inputs") or {}
    return [{"name": c["name"], "i18n": c["i18n"], "id": c["id"],
             "activo": _nivel(crudas.get(c["estado_key"])) if vivo else None}
            for c in canales]


def presentar_salidas(canales, status) -> list[dict]:
    vivo = enlace_ok(status)
    salidas = _sensores(status).get("digital_outputs") or {}
    return [{"name": c["name"], "i18n": c["i18n"], "id": c["id"],
             "momentanea": bool(c.get("momentanea")), "bloqueada": bool(c.get("bloqueada")),
             "encendida": _nivel(salidas.get(c["estado_key"])) if vivo else None}
            for c in canales]


def _numero(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def presentar_sensores(sensores, tipo: str, status, claves_corta: dict) -> list[dict]:
    """`claves_corta`: clave de EstadoAutoclave -> clave de /status
    (temp_camara -> camara). Valor en °C o kPa absolutos (D-ES-05)."""
    sens = _sensores(status)
    lecturas = sens.get(tipo) or {}
    adc = sens.get("adc") or {}
    vivo = enlace_ok(status)
    salida = []
    for s in sensores:
        valor = _numero(lecturas.get(claves_corta.get(s["estado_key"]))) if vivo else None
        cuentas = adc.get(s["estado_key"]) if vivo else None
        salida.append({"name": s["name"], "i18n": s["i18n"], "id": s["id"],
                       "estado_key": s["estado_key"], "valor": valor,
                       "adc": cuentas if isinstance(cuentas, int) else None,
                       "valido": valor is not None})
    return salida


def calcular_calibracion(shown_low, real_low, shown_high, real_high,
                         gain_actual, offset_actual, poly=None) -> tuple[float, float]:
    """Misma fórmula del backend: se invierte la calibración de usuario vigente
    para volver a la salida de fábrica y se ajusta la recta nueva sobre ella."""
    fv_low = invert_user_calibration(shown_low, gain_actual, offset_actual, poly)
    fv_high = invert_user_calibration(shown_high, gain_actual, offset_actual, poly)
    return fit_two_point(fv_low, real_low, fv_high, real_high)


def origen_de(origen: str, editada: bool) -> str:
    """Una lectura capturada que el usuario edita después cuenta como escrita (§7.3)."""
    return "escrita" if (editada or origen != "capturada") else "capturada"

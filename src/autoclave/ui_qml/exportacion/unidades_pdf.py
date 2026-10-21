# ui_qml/exportacion/unidades_pdf.py
#
# I4 (tanda 6): la gráfica y los datos de los PDF (ciclo, consolidado) en las
# unidades vigentes. Los valores guardados siguen en °C y kPa absolutos; aquí
# solo se presentan, sin Qt (lo usan el puente y las pruebas).
#
# En psi la gráfica usa psig en un solo eje continuo (negativo por debajo de la
# atmosférica), para no partir la curva entre psig e inHg como en el ticket.
# Sin P_atm válida, en psi la serie de presión queda vacía: nunca un número
# inventado (DECISIÓN SIN CONFIRMAR I4-3).

from autoclave.core.runtime import unidades as u


def _temp(v, unidad):
    return None if v is None else u.temp_a_mostrar(v, unidad)


def _pres(v, unidad, p_atm):
    if v is None:
        return None
    if unidad == "psi":
        if p_atm is None:
            return None
        return (v - p_atm) / u.KPA_POR_PSI
    return u.pres_a_mostrar(v, unidad, p_atm)[0]


def simbolo_pres_grafica(unidad: str) -> str:
    return "psig" if unidad == "psi" else u.simbolo_pres(unidad)


def grafica(datos: dict, temperatura: str, presion: str, p_atm) -> dict:
    """Copia de AcumuladorGrafica.datos() con las series convertidas."""
    if temperatura == "C" and presion == "kPa":
        return datos
    salida = dict(datos)
    for clave in ("temp_camara", "temp_ref"):
        salida[clave] = [_temp(v, temperatura) for v in datos.get(clave) or []]
    salida["pres_camara"] = [_pres(v, presion, p_atm) for v in datos.get("pres_camara") or []]
    return salida


def consigna(c: dict | None, temperatura: str, presion: str, p_atm) -> dict | None:
    """La consigna de esterilización convertida; sin presión convertible, None
    (no se dibuja una consigna a medias)."""
    if not c or (temperatura == "C" and presion == "kPa"):
        return c
    pres = _pres(c.get("pres"), presion, p_atm)
    temp = _temp(c.get("temp"), temperatura)
    if pres is None or temp is None:
        return None
    return {**c, "temp": temp, "pres": pres}


def textos_ejes(textos: dict, temperatura: str, presion: str) -> dict:
    """Rótulos de los ejes con el símbolo de la unidad vigente."""
    return {**textos, "eje_temp": u.simbolo_temp(temperatura),
            "eje_pres": simbolo_pres_grafica(presion)}


def rotulo_unidades(temperatura: str, presion: str) -> str:
    """"°C, kPa abs" / "°F, psig": lo que dice la cabecera del PDF."""
    sp = simbolo_pres_grafica(presion)
    return f"{u.simbolo_temp(temperatura)}, {sp}" + ("" if presion == "psi" else " abs")

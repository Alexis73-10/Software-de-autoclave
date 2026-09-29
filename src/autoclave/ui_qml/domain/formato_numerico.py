# ui_qml/domain/formato_numerico.py
#
# Conversión decimal coma/punto (D-19): coma en presentación y entrada de
# la interfaz, punto en persistencia/API/JSON. Único punto del código que
# hace esta conversión — ver CLAUDE.md / planeacion_ui_dual_pantalla.md §13.3.

def formatear_decimal(valor: float, decimales: int = 1) -> str:
    """Formatea un número para presentación en pantalla, con coma como
    separador decimal (ej. 134.0 -> "134,0")."""
    return f"{valor:.{decimales}f}".replace(".", ",")


def parsear_decimal(texto: str) -> float:
    """Convierte texto ingresado en el teclado numérico (coma decimal) a
    float. Rechaza un punto literal: el teclado numérico no tiene tecla de
    punto (D-18), así que un punto en la entrada es inválido, no un
    separador alternativo."""
    if "." in texto:
        raise ValueError(f"Separador decimal inválido: {texto!r} (se espera coma)")
    return float(texto.replace(",", "."))

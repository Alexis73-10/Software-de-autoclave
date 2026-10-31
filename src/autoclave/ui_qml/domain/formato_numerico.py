# ui_qml/domain/formato_numerico.py
#
# Punto decimal en toda la interfaz, entrada y presentación, igual que en
# persistencia/API/JSON (TEC-D14 de planeacion_teclados_qml.md, que revoca
# D-18/D-19 de planeacion_ui_dual_pantalla.md). Único módulo que formatea y
# parsea decimales de la interfaz.

import re

# Solo las formas que puede producir el teclado numérico: signo opcional,
# dígitos y un punto. float() aceptaría además "1e3", "inf", "nan", "1_000",
# espacios y "+5", que aquí son entradas inválidas.
_DECIMAL = re.compile(r"-?(\d+\.?\d*|\.\d+)")


def formatear_decimal(valor: float, decimales: int = 1) -> str:
    """Formatea un número para presentación en pantalla, con punto como
    separador decimal (ej. 134.0 -> "134.0")."""
    return f"{valor:.{decimales}f}"


def parsear_decimal(texto: str) -> float:
    """Convierte texto ingresado en el teclado numérico (punto decimal) a
    float. Rechaza la coma: el teclado numérico no tiene tecla de coma
    (TEC-D02), así que una coma en la entrada es inválida, no un separador
    alternativo. También rechaza parciales ("-", ".", "-.")."""
    if not _DECIMAL.fullmatch(texto):
        raise ValueError(f"Número decimal inválido: {texto!r} (se espera punto decimal)")
    return float(texto)

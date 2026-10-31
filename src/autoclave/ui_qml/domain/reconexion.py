# ui_qml/domain/reconexion.py
#
# Retroceso exponencial de reconexión del cliente WebSocket (§6.4 del plan
# de interfaz dual-pantalla): "Reintento con retroceso exponencial 1, 2,
# 4, 8, máximo 15 s."

_TECHO_SEG = 15


def siguiente_intervalo_reintento(intento: int) -> int:
    """Segundos a esperar antes del reintento número `intento` (1-indexado):
    1, 2, 4, 8, luego techado a 15."""
    if intento < 1:
        raise ValueError(f"intento debe ser >= 1, recibido {intento!r}")
    return min(2 ** (intento - 1), _TECHO_SEG)

# autoclave.protocols.crc16
# -------------------------
# CRC-16/CCITT-FALSE para el protocolo serial v2 PC <-> ESP32
# (ver docs/mis_plans/planeacion_protocolo_serial_esp32.md, sección 4.1).
#
# Parámetros: polinomio 0x1021, valor inicial 0xFFFF, sin reflexión de
# entrada ni de salida, sin XOR final. Vector de prueba: "123456789" -> 0x29B1.
#
# Formato de línea: <payload>*HHHH  (HHHH = CRC en 4 dígitos hex mayúscula,
# calculado solo sobre los bytes del payload; el "\n" final no forma parte
# de la línea que reciben estas funciones).

from __future__ import annotations

from typing import Optional

_POLY = 0x1021
_INIT = 0xFFFF


def crc16_ccitt_false(data: bytes) -> int:
    crc = _INIT
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ _POLY) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def agregar_crc(payload: str) -> str:
    """Devuelve `payload*HHHH` (sin terminador de línea)."""
    crc = crc16_ccitt_false(payload.encode("ascii"))
    return f"{payload}*{crc:04X}"


def validar_linea(linea: str) -> Optional[str]:
    """Valida una línea `payload*HHHH` (ya sin `\\r\\n`) y devuelve el payload
    si el CRC coincide; None en cualquier otro caso (sin sufijo, sufijo mal
    formado, hex en minúscula, payload no ASCII o CRC distinto)."""
    sep = linea.rfind("*")
    if sep < 0:
        return None
    payload, sufijo = linea[:sep], linea[sep + 1:]
    if len(sufijo) != 4 or any(c not in "0123456789ABCDEF" for c in sufijo):
        return None
    try:
        datos = payload.encode("ascii")
    except UnicodeEncodeError:
        return None
    if crc16_ccitt_false(datos) != int(sufijo, 16):
        return None
    return payload

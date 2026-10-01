# ui_qml/domain/teclado_numerico.py
#
# Lógica pura del teclado numérico en pantalla (§13.1): acumulación de
# texto tecla-a-tecla y validación de rango en vivo, con punto decimal
# (TEC-D14 de planeacion_teclados_qml.md). Vive en domain, no en el
# componente QML (§13.3) — el componente solo llama estas funciones.

import math
from dataclasses import dataclass

from .formato_numerico import formatear_decimal, parsear_decimal


# Distribución de calculadora del diseñador (pág. 24 de la especificación):
# 7-8-9 arriba; la fila inferior es signo, 0 y punto.
SIGNO = "-"
PUNTO = "."
FILAS_TECLAS = ("789", "456", "123", SIGNO + "0" + PUNTO)


@dataclass(frozen=True)
class EstadoTecladoNumerico:
    texto: str
    valor: float | None
    valido: bool


def agregar_digito(texto: str, digito: str, decimales: int | None = None) -> str:
    """Con `decimales` indicado, no acepta un dígito que exceda esa cantidad
    de posiciones tras el punto (§7). Sin él, no hay tope. Cualquier cosa
    que no sea un solo dígito 0-9 se ignora."""
    if len(digito) != 1 or digito not in "0123456789":
        return texto
    if decimales is not None and "." in texto:
        if len(texto.split(".", 1)[1]) >= decimales:
            return texto
    return texto + digito


def agregar_punto(texto: str, decimales: int) -> str:
    """Punto decimal, nunca coma (TEC-D14): uno solo, y solo si el parámetro
    admite decimales (§7)."""
    if decimales <= 0 or "." in texto:
        return texto
    return texto + "."


def permite_negativo(minimo: float | None) -> bool:
    """La tecla de signo está bloqueada si `minimo` es mayor o igual a 0 (§7)."""
    return minimo is None or minimo < 0


def alternar_signo(texto: str, permite_negativo: bool) -> str:
    """Alterna el signo del valor completo; con el campo vacío deja un "-"
    pendiente (§7). Inerte donde el campo no admite negativos."""
    if not permite_negativo:
        return texto
    if texto.startswith("-"):
        return texto[1:]
    return "-" + texto


def borrar(texto: str) -> str:
    return texto[:-1]


def evaluar(texto: str, minimo: float | None = None, maximo: float | None = None) -> EstadoTecladoNumerico:
    """Valida el texto acumulado en vivo. Texto vacío o incompleto (ej.
    "-", "." o "-." solos) es inválido sin lanzar excepción — Confirmar en
    ese estado no entrega valor y muestra el rango (§7)."""
    try:
        valor = parsear_decimal(texto)
    except ValueError:
        return EstadoTecladoNumerico(texto=texto, valor=None, valido=False)

    if minimo is not None and valor < minimo:
        return EstadoTecladoNumerico(texto=texto, valor=valor, valido=False)
    if maximo is not None and valor > maximo:
        return EstadoTecladoNumerico(texto=texto, valor=valor, valido=False)

    return EstadoTecladoNumerico(texto=texto, valor=valor, valido=True)


def _finito(valor) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor) if math.isfinite(valor) else None


def texto_inicial(valor, decimales: int) -> str:
    """Texto editable con el que abre el teclado: el valor actual del campo
    con los decimales del campo, o vacío si no hay un número válido."""
    v = _finito(valor)
    return "" if v is None else formatear_decimal(v, decimales)


def texto_limite(valor, decimales: int) -> str:
    """Límite del rango para el encabezado y el aviso de fuera de rango
    (TEC-D13, PROV-04), con punto decimal. Vacío si el campo no tiene ese
    límite."""
    v = _finito(valor)
    return "" if v is None else formatear_decimal(v, decimales)

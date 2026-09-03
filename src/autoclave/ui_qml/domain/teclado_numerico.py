# ui_qml/domain/teclado_numerico.py
#
# Lógica pura del teclado numérico en pantalla (§13.1): acumulación de
# texto tecla-a-tecla y validación de rango en vivo. Vive en domain, no en
# el componente QML (§13.3) — el componente solo llama estas funciones.

from dataclasses import dataclass

from .formato_numerico import parsear_decimal


@dataclass(frozen=True)
class EstadoTecladoNumerico:
    texto: str
    valor: float | None
    valido: bool


def agregar_digito(texto: str, digito: str) -> str:
    return texto + digito


def agregar_coma(texto: str) -> str:
    """Sin punto decimal en el teclado (D-18) — coma, y solo una."""
    if "," in texto:
        return texto
    return texto + ","


def alternar_signo(texto: str, permite_negativo: bool) -> str:
    """Signo negativo solo donde el campo lo admita (§13.1)."""
    if not permite_negativo:
        return texto
    if texto.startswith("-"):
        return texto[1:]
    return "-" + texto


def borrar(texto: str) -> str:
    return texto[:-1]


def evaluar(texto: str, minimo: float | None = None, maximo: float | None = None) -> EstadoTecladoNumerico:
    """Valida el texto acumulado en vivo. Texto vacío o incompleto (ej.
    "-" o "," solos) es inválido sin lanzar excepción — el botón de
    confirmación del teclado se deshabilita en ese estado."""
    try:
        valor = parsear_decimal(texto)
    except ValueError:
        return EstadoTecladoNumerico(texto=texto, valor=None, valido=False)

    if minimo is not None and valor < minimo:
        return EstadoTecladoNumerico(texto=texto, valor=valor, valido=False)
    if maximo is not None and valor > maximo:
        return EstadoTecladoNumerico(texto=texto, valor=valor, valido=False)

    return EstadoTecladoNumerico(texto=texto, valor=valor, valido=True)

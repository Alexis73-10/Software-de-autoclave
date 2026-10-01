# ui_qml/domain/teclado_alfanumerico.py
#
# Lógica pura del teclado alfanumérico en pantalla (TEC-D03/D05/D09 y §7 de
# planeacion_teclados_qml.md): juego de caracteres permitido, acumulación de
# texto con longitud máxima y tecla Aa de un solo uso. Vive en domain, no en
# el componente QML (TEC-D15).
#
# Tres capas que comparten retícula: letras (distribución del diseñador,
# pág. 25 de la especificación), dígitos y símbolos. Estas dos últimas se
# modelan como conjuntos de caracteres, sin filas: su posición en la
# retícula está pendiente del diseñador (Paso 7 del plan).

# Sin tildes ni diéresis, con ñ.
FILAS_QWERTY_ES = (
    "qwertyuiop",
    "asdfghjklñ",
    "zxcvbnm",
)

DIGITOS = "0123456789"

# Los 11 símbolos de TEC-D03, sin repetir el guion.
SIMBOLOS = "@._-()?+*/="

ESPACIO = " "

CAPAS = ("letras", "digitos", "simbolos")
CAPA_INICIAL = "letras"

_LETRAS = frozenset("".join(FILAS_QWERTY_ES))
_PERMITIDOS = _LETRAS | {c.upper() for c in _LETRAS} | set(DIGITOS) | set(SIMBOLOS) | {ESPACIO}


def caracter_permitido(caracter: str) -> bool:
    return len(caracter) == 1 and caracter in _PERMITIDOS


def _es_letra(caracter: str) -> bool:
    return caracter.lower() in _LETRAS


def agregar_caracter(texto: str, caracter: str, longitud_maxima: int = 0) -> str:
    """`longitud_maxima` 0 = sin límite. Al alcanzarla no se agrega nada
    (TEC-D09)."""
    if longitud_maxima > 0 and len(texto) >= longitud_maxima:
        return texto
    return texto + caracter


def borrar(texto: str) -> str:
    return texto[:-1]


def alternar_mayusculas(mayusculas: bool) -> bool:
    return not mayusculas


# Aa se arma siempre que el texto está vacío (precisión de Cristian a TEC-D05,
# 2026-09-30): al abrir un campo vacío y cuando Borrar o el borrado total lo
# dejan vacío. Abrir con texto existente no la arma. Tocar Aa armada la
# desarma (alternar_mayusculas), también con el campo vacío.

def aa_al_abrir(valor_inicial: str) -> bool:
    return valor_inicial == ""


def aa_tras_borrar(texto: str, mayusculas: bool) -> bool:
    """`texto` es el resultado del borrado."""
    return True if texto == "" else mayusculas


def transformar_caracter(caracter: str, mayusculas: bool) -> str:
    """Aplica mayúsculas/minúsculas a una letra. Sin efecto sobre símbolos
    o dígitos (str.upper()/lower() ya son identidad para esos)."""
    return caracter.upper() if mayusculas else caracter.lower()


def pulsar_caracter(texto: str, caracter: str, mayusculas: bool,
                    longitud_maxima: int) -> tuple[str, bool]:
    """Una tecla de carácter. Devuelve (texto, mayusculas) nuevos.

    Aa es de un solo uso (TEC-D05): con Aa armada, la siguiente letra sale en
    mayúscula y Aa se desarma. Dígitos, símbolos y espacio no la consumen,
    y tampoco una letra que no entra por longitud. Un carácter fuera del
    juego permitido se ignora."""
    if not caracter_permitido(caracter):
        return texto, mayusculas
    if not _es_letra(caracter):
        return agregar_caracter(texto, caracter, longitud_maxima), mayusculas
    nuevo = agregar_caracter(texto, transformar_caracter(caracter, mayusculas), longitud_maxima)
    if nuevo == texto:
        return texto, mayusculas
    return nuevo, False

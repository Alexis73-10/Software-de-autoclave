# ui_qml/domain/teclado_alfanumerico.py
#
# Lógica pura del teclado alfanumérico en pantalla (TEC-D03/D05/D09 y §7 de
# planeacion_teclados_qml.md): juego de caracteres permitido, acumulación de
# texto con longitud máxima y tecla Aa de un solo uso. Vive en domain, no en
# el componente QML (TEC-D15).
#
# Dos capas que comparten retícula: letras (distribución del diseñador,
# pág. 25 de la especificación) y "?123", dígitos y símbolos juntos como en
# el teclado de Google para Android. Decisión de Cristian (2026-10-01): une
# las capas 123 y @._ de TEC-D03 en una sola para darle más ancho a la
# barra espaciadora; el juego de caracteres de TEC-D03 no cambia.

# Sin tildes ni diéresis, con ñ.
FILAS_QWERTY_ES = (
    "qwertyuiop",
    "asdfghjklñ",
    "zxcvbnm",
)

DIGITOS = "0123456789"

# Los 11 símbolos de TEC-D03, sin repetir el guion, más 6 que agregó Cristian
# (2026-10-01) para completar la fila 3 de la capa ?123: ¿ ¡ ! : " '.
# Siguen excluidos # $ % & , ; (la coma, por el punto decimal de TEC-D14).
SIMBOLOS = "@._-()?+*/=" + "¿¡!:\"'"

ESPACIO = " "

# Capa ?123 sobre las posiciones de las letras: fila 1 (10 teclas) los
# dígitos, fila 2 (10) y fila 3 (7, tras Aa) los 17 símbolos. Una fila más
# corta que la de letras dejaría sin tecla las posiciones finales.
FILAS_NUMEROS = (
    "1234567890",
    "@._-+*/=()",
    "¿?¡!:\"'",
)

CAPAS = ("letras", "numeros")
CAPA_INICIAL = "letras"

_LETRAS = frozenset("".join(FILAS_QWERTY_ES))
_PERMITIDOS = _LETRAS | {c.upper() for c in _LETRAS} | set(DIGITOS) | set(SIMBOLOS) | {ESPACIO}


def filas_de_capa(capa: str) -> tuple[str, ...]:
    return FILAS_NUMEROS if capa == "numeros" else FILAS_QWERTY_ES


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

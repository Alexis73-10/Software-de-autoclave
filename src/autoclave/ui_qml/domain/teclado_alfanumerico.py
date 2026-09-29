# ui_qml/domain/teclado_alfanumerico.py
#
# Lógica pura del teclado alfanumérico en pantalla (§13.2): distribución
# QWERTY español, acumulación de texto y alternancia mayúsculas/minúsculas
# y capa de símbolos. Vive en domain, no en el componente QML (§13.3).

# Sin tildes (D-18) — con ñ (obligatoria, §13.2).
FILAS_QWERTY_ES = (
    "qwertyuiop",
    "asdfghjklñ",
    "zxcvbnm",
)

# Incluye @ (obligatorio, §13.2).
FILAS_SIMBOLOS = (
    "1234567890",
    "@#$%&*-+=",
    "!?,.;:()/",
)


def agregar_caracter(texto: str, caracter: str) -> str:
    return texto + caracter


def borrar(texto: str) -> str:
    return texto[:-1]


def alternar_mayusculas(mayusculas: bool) -> bool:
    return not mayusculas


def alternar_capa_simbolos(capa_simbolos: bool) -> bool:
    return not capa_simbolos


def transformar_caracter(caracter: str, mayusculas: bool) -> str:
    """Aplica mayúsculas/minúsculas a una letra. Sin efecto sobre símbolos
    o dígitos (str.upper()/lower() ya son identidad para esos)."""
    return caracter.upper() if mayusculas else caracter.lower()

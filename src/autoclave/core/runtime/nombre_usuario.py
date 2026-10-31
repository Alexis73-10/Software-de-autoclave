# core/runtime/nombre_usuario.py
#
# U11 (tanda 11, D11-6; revisión de seguridad SAF-01): comparación y forma
# válida de los nombres de usuario. Una sola función de comparación para la
# unicidad al crear, la búsqueda del inicio de sesión, el contador de bloqueo
# y el simulador.
#
# - normalizar_usuario: NFKC y después casefold. NFKC pliega las formas de
#   compatibilidad (letras de ancho completo, ligaduras) y casefold las
#   mayúsculas, también fuera de ASCII (Ñ). Letras de otros alfabetos que
#   solo se parecen (alfa griega, A cirílica) siguen siendo distintas; por eso
#   caracter_permitido limita los nombres nuevos a letras latinas.
# - caracter_permitido: letras latinas (con tildes y ñ), dígitos ASCII y . _ -.
#   Rechaza en particular los caracteres de formato (categoría Unicode Cf,
#   p. ej. espacio de ancho cero) y de control (Cc). Solo se aplica al crear:
#   un usuario existente con un nombre que ya no sería válido sigue entrando.
# - NOMBRES_RESERVADOS: `sistema` (autor de registros automáticos de la
#   bitácora) y `semilla` (marca creado_por de las cuentas del sistema).

import unicodedata

NOMBRES_RESERVADOS = frozenset({"sistema", "semilla"})
_SIGNOS = frozenset("._-")


def normalizar_usuario(usuario: str) -> str:
    return unicodedata.normalize("NFKC", usuario or "").casefold()


def caracter_permitido(c: str) -> bool:
    if c in _SIGNOS or (c.isascii() and c.isalnum()):
        return True
    if unicodedata.category(c) not in ("Lu", "Ll"):
        return False                       # Cf, Cc, marcas combinantes, espacios, signos
    return unicodedata.name(c, "").startswith("LATIN ")   # excluye ancho completo y otros alfabetos


def formato_valido(usuario: str) -> bool:
    return all(caracter_permitido(c) for c in usuario)


def es_reservado(usuario: str) -> bool:
    return normalizar_usuario(usuario) in NOMBRES_RESERVADOS

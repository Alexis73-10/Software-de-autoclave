# ui_pyside/services/validacion_usuario.py
#
# Reglas de la pantalla Nuevo Usuario (planeacion_nuevo_usuario.md, D-07,
# P-04, P-05). Única fuente de reglas: las aplica el backend en POST /usuarios
# (planeacion_backend_autenticacion.md, §4.1) y el puente y el QML solo
# muestran los mensajes. Sin Qt ni base de datos: la unicidad del usuario la
# consulta quien llama, vía `existe_usuario`. El Código/ID de creación (D-12)
# ya no se exige: se eliminó de la pantalla.

from autoclave.ui_pyside.services.roles import VALORES_ROL

NOMBRE_MAX = 50
USUARIO_MIN, USUARIO_MAX = 3, 30
PASSWORD_MIN, PASSWORD_MAX = 8, 64

OBLIGATORIO = "Campo obligatorio"
USUARIO_FORMATO = f"Sin espacios, de {USUARIO_MIN} a {USUARIO_MAX} caracteres"
USUARIO_EXISTE = "El usuario ya existe"
PASSWORD_CORTA = f"Mínimo {PASSWORD_MIN} caracteres"
PASSWORD_LARGA = f"Máximo {PASSWORD_MAX} caracteres"
NO_COINCIDEN = "Las contraseñas no coinciden"
SELECCIONE_ROL = "Seleccione un rol"
NOMBRE_LARGO = f"Máximo {NOMBRE_MAX} caracteres"


def validar_nuevo_usuario(nombre: str, usuario: str, password: str,
                          confirmacion: str, rol: str,
                          existe_usuario) -> dict[str, str]:
    """Devuelve {campo: mensaje} con todos los errores; vacío si es válido.
    `existe_usuario(usuario) -> bool` solo se consulta si el formato es válido."""
    errores = {}

    nombre = nombre.strip()
    if not nombre:
        errores["nombre"] = OBLIGATORIO
    elif len(nombre) > NOMBRE_MAX:
        errores["nombre"] = NOMBRE_LARGO

    if not usuario:
        errores["usuario"] = OBLIGATORIO
    elif (not USUARIO_MIN <= len(usuario) <= USUARIO_MAX
          or any(c.isspace() for c in usuario)):
        errores["usuario"] = USUARIO_FORMATO
    elif existe_usuario(usuario):
        errores["usuario"] = USUARIO_EXISTE

    if not password:
        errores["password"] = OBLIGATORIO
    elif len(password) < PASSWORD_MIN:
        errores["password"] = PASSWORD_CORTA
    elif len(password) > PASSWORD_MAX:
        errores["password"] = PASSWORD_LARGA

    if not confirmacion:
        errores["confirmacion"] = OBLIGATORIO
    elif confirmacion != password:
        errores["confirmacion"] = NO_COINCIDEN

    if rol not in VALORES_ROL:
        errores["rol"] = SELECCIONE_ROL

    return errores

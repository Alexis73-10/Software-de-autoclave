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

# Códigos estables por campo (contrato v7, decisión 34): el backend los envía
# en el 422 y la UI los traduce con es.json. Los textos de abajo son los de
# siempre; solo los usa la envoltura validar_nuevo_usuario (pantalla PySide y
# puente actual), que se retira cuando el puente traduzca por clave (T-8).
COD_OBLIGATORIO = "obligatorio"
COD_FORMATO = "formato"          # solo usuario
COD_EXISTE = "existe"            # solo usuario, validación local con existe_usuario
COD_CORTA = "corta"
COD_LARGA = "larga"
COD_NO_COINCIDEN = "no_coinciden"   # solo confirmacion
COD_ROL_INVALIDO = "rol_invalido"   # solo rol
COD_IGUAL_ACTUAL = "igual_actual"   # solo clave_nueva (cambio de contraseña)

OBLIGATORIO = "Campo obligatorio"
USUARIO_FORMATO = f"Sin espacios, de {USUARIO_MIN} a {USUARIO_MAX} caracteres"
USUARIO_EXISTE = "El usuario ya existe"
PASSWORD_CORTA = f"Mínimo {PASSWORD_MIN} caracteres"
PASSWORD_LARGA = f"Máximo {PASSWORD_MAX} caracteres"
NO_COINCIDEN = "Las contraseñas no coinciden"
SELECCIONE_ROL = "Seleccione un rol"
NOMBRE_LARGO = f"Máximo {NOMBRE_MAX} caracteres"
IGUAL_ACTUAL = "La nueva contraseña debe ser distinta de la actual"


def codigo_clave(clave: str) -> str | None:
    """Código del error de una contraseña nueva, o None si es válida."""
    if not clave:
        return COD_OBLIGATORIO
    if len(clave) < PASSWORD_MIN:
        return COD_CORTA
    if len(clave) > PASSWORD_MAX:
        return COD_LARGA
    return None


def codigo_confirmacion(confirmacion: str, clave: str) -> str | None:
    if not confirmacion:
        return COD_OBLIGATORIO
    if confirmacion != clave:
        return COD_NO_COINCIDEN
    return None


def codigos_nuevo_usuario(nombre: str, usuario: str, clave: str, confirmacion: str,
                          rol: str, existe_usuario) -> dict[str, str]:
    """{campo: código} con los nombres de campo del cuerpo de POST /usuarios
    (nombre, usuario, clave, confirmacion, rol), en ese orden; vacío si es
    válido. `existe_usuario(usuario) -> bool` solo se consulta si el formato
    es válido."""
    errores = {}

    nombre = nombre.strip()
    if not nombre:
        errores["nombre"] = COD_OBLIGATORIO
    elif len(nombre) > NOMBRE_MAX:
        errores["nombre"] = COD_LARGA

    if not usuario:
        errores["usuario"] = COD_OBLIGATORIO
    elif (not USUARIO_MIN <= len(usuario) <= USUARIO_MAX
          or any(c.isspace() for c in usuario)):
        errores["usuario"] = COD_FORMATO
    elif existe_usuario(usuario):
        errores["usuario"] = COD_EXISTE

    for campo, codigo in (("clave", codigo_clave(clave)),
                          ("confirmacion", codigo_confirmacion(confirmacion, clave))):
        if codigo:
            errores[campo] = codigo

    if rol not in VALORES_ROL:
        errores["rol"] = COD_ROL_INVALIDO

    return errores


_TEXTOS = {
    ("nombre", COD_OBLIGATORIO): OBLIGATORIO, ("nombre", COD_LARGA): NOMBRE_LARGO,
    ("usuario", COD_OBLIGATORIO): OBLIGATORIO, ("usuario", COD_FORMATO): USUARIO_FORMATO,
    ("usuario", COD_EXISTE): USUARIO_EXISTE,
    ("clave", COD_OBLIGATORIO): OBLIGATORIO, ("clave", COD_CORTA): PASSWORD_CORTA,
    ("clave", COD_LARGA): PASSWORD_LARGA,
    ("confirmacion", COD_OBLIGATORIO): OBLIGATORIO,
    ("confirmacion", COD_NO_COINCIDEN): NO_COINCIDEN,
    ("rol", COD_ROL_INVALIDO): SELECCIONE_ROL,
}

# La pantalla Nuevo usuario nombra "password" al campo que el cuerpo llama "clave"
_CAMPO_PANTALLA = {"clave": "password"}


def texto_error(campo: str, codigo: str) -> str:
    """Texto actual de un error de Nuevo usuario (campo del cuerpo + código)."""
    return _TEXTOS.get((campo, codigo), OBLIGATORIO if codigo == COD_OBLIGATORIO else codigo)


def campo_pantalla(campo: str) -> str:
    return _CAMPO_PANTALLA.get(campo, campo)


def validar_nuevo_usuario(nombre: str, usuario: str, password: str,
                          confirmacion: str, rol: str,
                          existe_usuario) -> dict[str, str]:
    """Envoltura de textos: {campo de pantalla: mensaje} con todos los errores;
    vacío si es válido. Mismo resultado que antes de los códigos."""
    codigos = codigos_nuevo_usuario(nombre, usuario, password, confirmacion, rol,
                                    existe_usuario)
    return {campo_pantalla(c): texto_error(c, cod) for c, cod in codigos.items()}

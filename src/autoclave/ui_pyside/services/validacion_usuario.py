# ui_pyside/services/validacion_usuario.py
#
# Reglas de la pantalla Nuevo Usuario (planeacion_nuevo_usuario.md, D-07,
# P-04, P-05). Única fuente de reglas: las aplica el backend en POST /usuarios
# (planeacion_backend_autenticacion.md, §4.1) y el puente y el QML solo
# muestran los mensajes. Sin Qt ni base de datos: la unicidad del usuario la
# consulta quien llama, vía `existe_usuario`. El Código/ID de creación (D-12)
# ya no se exige: se eliminó de la pantalla.

from autoclave.core.runtime.nombre_usuario import es_reservado, formato_valido
from autoclave.ui_pyside.services.roles import VALORES_ROL

NOMBRE_MAX = 50
USUARIO_MIN, USUARIO_MAX = 3, 30
PASSWORD_MIN, PASSWORD_MAX = 8, 64

# Códigos estables por campo (contrato v7, decisión 34): el backend los envía
# en el 422 y la UI los traduce con es.json (error_ui).
COD_OBLIGATORIO = "obligatorio"
COD_FORMATO = "formato"          # solo usuario
COD_EXISTE = "existe"            # solo usuario, validación local con existe_usuario
COD_RESERVADO = "reservado"      # solo usuario: `sistema` y `semilla` (U11, SAF-01)
COD_CORTA = "corta"
COD_LARGA = "larga"
COD_NO_COINCIDEN = "no_coinciden"   # solo confirmacion
COD_ROL_INVALIDO = "rol_invalido"   # solo rol
COD_IGUAL_ACTUAL = "igual_actual"   # solo clave_nueva (cambio de contraseña)

# Texto del 409 del backend (detail); la UI muestra usuarios.usuario_existe
USUARIO_EXISTE = "El usuario ya existe"


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
          or not formato_valido(usuario)):          # SAF-01 de U11: latinas, dígitos y . _ -
        errores["usuario"] = COD_FORMATO
    elif es_reservado(usuario):
        errores["usuario"] = COD_RESERVADO
    elif existe_usuario(usuario):
        errores["usuario"] = COD_EXISTE

    for campo, codigo in (("clave", codigo_clave(clave)),
                          ("confirmacion", codigo_confirmacion(confirmacion, clave))):
        if codigo:
            errores[campo] = codigo

    if rol not in VALORES_ROL:
        errores["rol"] = COD_ROL_INVALIDO

    return errores


# La pantalla Nuevo usuario nombra "password" al campo que el cuerpo llama "clave"
_CAMPO_PANTALLA = {"clave": "password"}


def campo_pantalla(campo: str) -> str:
    return _CAMPO_PANTALLA.get(campo, campo)


def error_ui(campo: str, codigo: str) -> dict:
    """Error para la pantalla: {"clave": <seccion.clave de es.json>,
    "valores": {marcador: valor}}. `campo` es el nombre del cuerpo (clave,
    clave_nueva, nombre, usuario, ...); los límites salen de este módulo, la
    misma fuente que usa el backend."""
    if codigo == COD_EXISTE:
        return {"clave": "usuarios.usuario_existe", "valores": {}}
    valores = {}
    if codigo == COD_CORTA:
        valores = {"min": PASSWORD_MIN}
    elif codigo == COD_LARGA:
        valores = {"max": NOMBRE_MAX if campo == "nombre" else PASSWORD_MAX}
    elif codigo == COD_FORMATO:
        valores = {"min": USUARIO_MIN, "max": USUARIO_MAX}
    return {"clave": f"validacion.{codigo}", "valores": valores}

# ui_pyside/services/roles.py
#
# Roles de usuario (planeacion_nuevo_usuario.md, P-03). Único lugar donde se
# definen: el valor se guarda en usuarios.rol (sin acento, minúscula) y la
# etiqueta es la que ve el operador. Los nombres siguen siendo provisionales;
# cambiarlos aquí no requiere tocar la pantalla.
#
# Ojo: calibracion_sensor._ROLES_PERMITIDOS compara contra estos valores.

# Roles válidos (planeacion_backend_autenticacion.md, decisión 25): biomedico
# se eliminó. El backend toma de aquí los valores para sus permisos.

ROL_ADMIN = "admin"
ROL_TECNICO = "tecnico"
ROL_INGENIERO = "ingeniero"

ROLES = (
    (ROL_ADMIN,     "Admin"),
    (ROL_TECNICO,   "Técnico"),
    (ROL_INGENIERO, "Ingeniero"),
)

VALORES_ROL = frozenset(valor for valor, _ in ROLES)

# Quién crea a quién (decisión 26): ingeniero crea admin, técnico e ingeniero;
# admin crea admin y técnico; técnico no crea. Lo impone el backend en
# POST /usuarios; la pantalla solo ofrece los roles permitidos.
ROLES_CREABLES = {
    ROL_INGENIERO: frozenset({ROL_ADMIN, ROL_TECNICO, ROL_INGENIERO}),
    ROL_ADMIN:     frozenset({ROL_ADMIN, ROL_TECNICO}),
}

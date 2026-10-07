# ui_pyside/services/roles.py
#
# Roles de usuario (planeacion_nuevo_usuario.md, P-03). Único lugar donde se
# definen: el valor se guarda en usuarios.rol (sin acento, minúscula) y la
# etiqueta es la que ve el operador. Los nombres siguen siendo provisionales;
# cambiarlos aquí no requiere tocar la pantalla.
#
# Ojo: calibracion_sensor._ROLES_PERMITIDOS compara contra estos valores.

ROL_ADMIN = "admin"

ROLES = (
    (ROL_ADMIN,   "Admin"),
    ("tecnico",   "Técnico"),
    ("biomedico", "Biomédico"),
    ("ingeniero", "Ingeniero"),
)

VALORES_ROL = frozenset(valor for valor, _ in ROLES)

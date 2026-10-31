# core/runtime/sesion_inactividad.py
#
# Plazo de inactividad de una sesión: fuente única para la UI QML (cierra la
# sesión de su ventana sin toques ni teclas) y para el backend (caduca el token
# sin peticiones autenticadas; B7 de la tanda 4). Neutral: no importa Qt.

SESION_INACTIVIDAD_S = 5 * 60
# La UI avisa al backend (GET /auth/sesion) como máximo cada SESION_KEEPALIVE_S
# mientras el operador usa una pantalla con token.
SESION_KEEPALIVE_S = 30
# El token del backend dura un poco más que la sesión de la UI (SAF-02/TMG-04 de
# la revisión de B7): el último aviso puede haber salido hasta un keepalive
# antes del último toque, y la UI debe ser la que cierra la sesión (con su
# logout y su mensaje de inactividad), no el backend por su cuenta.
PLAZO_TOKEN_BACKEND_S = SESION_INACTIVIDAD_S + 2 * SESION_KEEPALIVE_S

# core/runtime/sesion_inactividad.py
#
# Plazo de inactividad de una sesión: fuente única para la UI QML (cierra la
# sesión de su ventana sin toques ni teclas) y para el backend (caduca el token
# sin peticiones autenticadas; B7 de la tanda 4). Neutral: no importa Qt.

SESION_INACTIVIDAD_S = 5 * 60

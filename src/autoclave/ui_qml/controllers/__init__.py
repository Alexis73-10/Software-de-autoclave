# Login.qml usa LoginController: se registra (qmlRegisterType al importar) con
# cualquier import de este paquete, para que todo host de Main.qml que ya
# importa los controladores de los teclados lo tenga sin otro import.
from autoclave.ui_qml.controllers import login_controller  # noqa: F401
# Opciones.qml y Main.qml usan OpcionesController (sesión y permisos de OPCIONES).
from autoclave.ui_qml.controllers import opciones_controller  # noqa: F401
from autoclave.ui_qml.controllers import parametros_ciclo_controller  # noqa: F401
# OPCIONES › Mantenimiento (M1, tanda 3).
from autoclave.ui_qml.controllers import mantenimiento_controller  # noqa: F401
# CambioClave.qml usa CambioClaveController (cambio de contraseña obligatorio, T-8).
from autoclave.ui_qml.controllers import cambio_clave_controller  # noqa: F401
# OPCIONES > Entradas / Salidas.
from autoclave.ui_qml.controllers import entradas_salidas_controller  # noqa: F401
# U1 (tanda 5): las pantallas que muestran °C/kPa usan el singleton Unidades.
from autoclave.ui_qml.bridge import unidades_qml  # noqa: F401
# OPCIONES > Parámetros del equipo (P2, tanda 5).
from autoclave.ui_qml.controllers import parametros_equipo_controller  # noqa: F401
# OPCIONES > Usuarios (O2b, tanda 6).
from autoclave.ui_qml.controllers import usuarios_controller  # noqa: F401

# Login.qml usa LoginController: se registra (qmlRegisterType al importar) con
# cualquier import de este paquete, para que todo host de Main.qml que ya
# importa los controladores de los teclados lo tenga sin otro import.
from autoclave.ui_qml.controllers import login_controller  # noqa: F401
# Opciones.qml y Main.qml usan OpcionesController (sesión y permisos de OPCIONES).
from autoclave.ui_qml.controllers import opciones_controller  # noqa: F401
# CambioClave.qml usa CambioClaveController (cambio de contraseña obligatorio, T-8).
from autoclave.ui_qml.controllers import cambio_clave_controller  # noqa: F401

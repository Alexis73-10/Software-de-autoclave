# Modo oscuro: el singleton Autoclave.Apariencia se registra al importar
# cualquier módulo del puente, porque las raíces de ventana (Main.qml,
# InstalacionVentana.qml, ReposoInstalacionVentana.qml, NuevoUsuarioHost.qml)
# lo importan y los arneses que cargan esas raíces solo importan i18n_qml u
# otros módulos del puente, no ui_qml/app.py.
from autoclave.ui_qml.bridge import apariencia_qml  # noqa: F401
# FASE 6 (P1): el singleton Autoclave.Operaciones (registro de operaciones
# críticas que bloquean la navegación de Opciones), por el mismo motivo.
from autoclave.ui_qml import operacion_critica  # noqa: F401,E402
# Tanda 26 (ALD): singleton Autoclave.DetalleAviso (detalle de las filas sintéticas).
from autoclave.ui_qml.bridge import detalle_aviso_qml  # noqa: F401

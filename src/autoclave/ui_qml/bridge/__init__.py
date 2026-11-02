# Modo oscuro: el singleton Autoclave.Apariencia se registra al importar
# cualquier módulo del puente, porque las raíces de ventana (Main.qml,
# InstalacionVentana.qml, ReposoInstalacionVentana.qml, NuevoUsuarioHost.qml)
# lo importan y los arneses que cargan esas raíces solo importan i18n_qml u
# otros módulos del puente, no ui_qml/app.py.
from autoclave.ui_qml.bridge import apariencia_qml  # noqa: F401

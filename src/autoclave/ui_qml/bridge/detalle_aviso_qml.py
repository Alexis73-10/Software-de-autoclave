# ui_qml/bridge/detalle_aviso_qml.py
#
# Tanda 26 (ALD): singleton QML `DetalleAviso` (módulo "Autoclave.DetalleAviso"
# 1.0), puente delgado sobre ui_qml/domain/detalle_aviso.py. La QML llama
#   DetalleAviso.armar("no_abrir", puente.contextoAviso)
# y pasa la fila a VentanaDetalleAlarma.abrirDesde(); aquí no hay lógica ni
# textos, solo la llamada al módulo de dominio. Se registra al importar
# (ui_qml/bridge/__init__.py), igual que Apariencia.

from PySide6.QtCore import QObject, Slot
from PySide6.QtQml import QQmlEngine, qmlRegisterSingletonType

from autoclave.ui_qml.domain import detalle_aviso

URI = "Autoclave.DetalleAviso"


class DetalleAvisoQml(QObject):
    @Slot(str, "QVariant", result="QVariantMap")
    def armar(self, clave, contexto=None) -> dict:
        if hasattr(contexto, "toVariant"):       # objeto JS (QJSValue) → dict
            contexto = contexto.toVariant()
        return detalle_aviso.armar(clave, contexto if isinstance(contexto, dict) else {})

    @Slot("QVariant", str, result=str)
    def textoEspera(self, contexto=None, idioma="es") -> str:
        """A10 (tanda 28): nota de la fila de estado seguro en curso (pausa
        por modo prueba o motivo pendiente con valor y límite)."""
        if hasattr(contexto, "toVariant"):
            contexto = contexto.toVariant()
        return detalle_aviso.texto_espera(contexto if isinstance(contexto, dict) else {}, idioma)


instancia = DetalleAvisoQml()


def _fabrica(_engine):
    QQmlEngine.setObjectOwnership(instancia, QQmlEngine.ObjectOwnership.CppOwnership)
    return instancia


qmlRegisterSingletonType(DetalleAvisoQml, URI, 1, 0, "DetalleAviso", _fabrica)

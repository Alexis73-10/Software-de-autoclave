# ui_qml/bridge/posicion_card_qml.py
#
# Tanda 28 (A11): singleton QML `PosicionCard` (módulo "Autoclave.PosicionCard"
# 1.0), puente delgado sobre ui_qml/domain/posicion_card.py. GraficaCiclo.qml
# llama PosicionCard.posicionar(area, xCursor, ancho, alto, curvas, reserva) y
# solo dibuja la card donde se le dice. Se registra al importar
# (ui_qml/bridge/__init__.py).

from PySide6.QtCore import QObject, Slot
from PySide6.QtQml import QQmlEngine, qmlRegisterSingletonType

from autoclave.ui_qml.domain import posicion_card

URI = "Autoclave.PosicionCard"


def _aPython(v):
    return v.toVariant() if hasattr(v, "toVariant") else v      # QJSValue → Python


class PosicionCardQml(QObject):
    @Slot("QVariant", float, float, float, "QVariant", float, result="QVariantMap")
    def posicionar(self, area, x_cursor, ancho, alto, curvas, reserva) -> dict:
        return posicion_card.posicionar_card(
            _aPython(area), x_cursor, ancho, alto, _aPython(curvas), reserva)


instancia = PosicionCardQml()


def _fabrica(_engine):
    QQmlEngine.setObjectOwnership(instancia, QQmlEngine.ObjectOwnership.CppOwnership)
    return instancia


qmlRegisterSingletonType(PosicionCardQml, URI, 1, 0, "PosicionCard", _fabrica)

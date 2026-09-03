# ui_qml/controllers/teclado_numerico_controller.py
#
# Puente QObject entre domain/teclado_numerico.py (funciones puras) y el
# componente QML TecladoNumerico. Sin lógica propia más allá de delegar a
# domain y traducir el resultado a Qt Properties/Signals — la lógica de
# acumulación de texto y validación vive únicamente en domain (§13.3).

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml.domain import teclado_numerico as dominio


class TecladoNumericoController(QObject):
    textoChanged = Signal()
    valorChanged = Signal()
    validoChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._texto = ""
        self._minimo = float("-inf")
        self._maximo = float("inf")
        self._permite_negativo = False
        self._valor = None
        self._valido = False

    def _set_texto(self, texto: str) -> None:
        if texto == self._texto:
            return
        self._texto = texto
        self.textoChanged.emit()
        self._reevaluar()

    def _reevaluar(self) -> None:
        estado = dominio.evaluar(self._texto, self._minimo, self._maximo)
        if estado.valor != self._valor:
            self._valor = estado.valor
            self.valorChanged.emit()
        if estado.valido != self._valido:
            self._valido = estado.valido
            self.validoChanged.emit()

    @Property(str, notify=textoChanged)
    def texto(self) -> str:
        return self._texto

    @Property("QVariant", notify=valorChanged)
    def valor(self):
        return self._valor

    @Property(bool, notify=validoChanged)
    def valido(self) -> bool:
        return self._valido

    @Property(float)
    def minimo(self) -> float:
        return self._minimo

    @minimo.setter
    def minimo(self, value: float) -> None:
        self._minimo = value
        self._reevaluar()

    @Property(float)
    def maximo(self) -> float:
        return self._maximo

    @maximo.setter
    def maximo(self, value: float) -> None:
        self._maximo = value
        self._reevaluar()

    @Property(bool)
    def permiteNegativo(self) -> bool:
        return self._permite_negativo

    @permiteNegativo.setter
    def permiteNegativo(self, value: bool) -> None:
        self._permite_negativo = value

    @Slot(str)
    def presionarDigito(self, digito: str) -> None:
        self._set_texto(dominio.agregar_digito(self._texto, digito))

    @Slot()
    def presionarComa(self) -> None:
        self._set_texto(dominio.agregar_coma(self._texto))

    @Slot()
    def presionarSigno(self) -> None:
        self._set_texto(dominio.alternar_signo(self._texto, self._permite_negativo))

    @Slot()
    def borrar(self) -> None:
        self._set_texto(dominio.borrar(self._texto))

    @Slot()
    def limpiar(self) -> None:
        self._set_texto("")


qmlRegisterType(TecladoNumericoController, "Autoclave.Controllers", 1, 0, "TecladoNumericoController")

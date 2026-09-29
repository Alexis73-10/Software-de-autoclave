# ui_qml/controllers/teclado_alfanumerico_controller.py
#
# Puente QObject entre domain/teclado_alfanumerico.py (funciones puras) y
# el componente QML TecladoAlfanumerico. Sin lógica propia más allá de
# delegar a domain y traducir el resultado a Qt Properties/Signals.

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml.domain import teclado_alfanumerico as dominio


class TecladoAlfanumericoController(QObject):
    textoChanged = Signal()
    mayusculasChanged = Signal()
    capaSimbolosChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._texto = ""
        self._mayusculas = False
        self._capa_simbolos = False

    def _set_texto(self, texto: str) -> None:
        if texto == self._texto:
            return
        self._texto = texto
        self.textoChanged.emit()

    @Property(str, notify=textoChanged)
    def texto(self) -> str:
        return self._texto

    @Property(bool, notify=mayusculasChanged)
    def mayusculas(self) -> bool:
        return self._mayusculas

    @Property(bool, notify=capaSimbolosChanged)
    def capaSimbolos(self) -> bool:
        return self._capa_simbolos

    @Property("QVariantList", constant=True)
    def filasLetras(self):
        return list(dominio.FILAS_QWERTY_ES)

    @Property("QVariantList", constant=True)
    def filasSimbolos(self):
        return list(dominio.FILAS_SIMBOLOS)

    @Slot(str)
    def presionarCaracter(self, caracter: str) -> None:
        caracter_transformado = dominio.transformar_caracter(caracter, self._mayusculas)
        self._set_texto(dominio.agregar_caracter(self._texto, caracter_transformado))

    @Slot()
    def alternarMayusculas(self) -> None:
        self._mayusculas = dominio.alternar_mayusculas(self._mayusculas)
        self.mayusculasChanged.emit()

    @Slot()
    def alternarCapaSimbolos(self) -> None:
        self._capa_simbolos = dominio.alternar_capa_simbolos(self._capa_simbolos)
        self.capaSimbolosChanged.emit()

    @Slot()
    def borrar(self) -> None:
        self._set_texto(dominio.borrar(self._texto))

    @Slot()
    def limpiar(self) -> None:
        self._set_texto("")


qmlRegisterType(TecladoAlfanumericoController, "Autoclave.Controllers", 1, 0, "TecladoAlfanumericoController")

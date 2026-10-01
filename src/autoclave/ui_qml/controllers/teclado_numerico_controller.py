# ui_qml/controllers/teclado_numerico_controller.py
#
# Puente QObject entre domain/teclado_numerico.py (funciones puras) y el
# componente QML TecladoNumerico. Sin lógica propia más allá de delegar a
# domain y traducir el resultado a Qt Properties/Signals — la lógica de
# acumulación de texto y validación vive únicamente en domain (TEC-D15).
#
# Uso desde el panel: abrir(titulo, unidad, valorInicial, minimo, maximo,
# decimales) configura el campo de una vez y descarta lo anterior; el valor
# solo sale por `confirmado` y solo si es válido (TEC-D08). Confirmar con un
# valor inválido no entrega nada y levanta `fueraDeRango` para mostrar el
# rango, que se oculta con la siguiente tecla.

import time

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml.controllers.pulsacion_borrar import PulsacionBorrar
from autoclave.ui_qml.domain import teclado_numerico as dominio


class TecladoNumericoController(QObject):
    textoChanged = Signal()
    valorChanged = Signal()
    validoChanged = Signal()
    campoChanged = Signal()          # titulo, unidad, límites, decimales
    fueraDeRangoChanged = Signal()
    confirmado = Signal(float)
    cancelado = Signal()

    def __init__(self, parent=None, reloj=time.monotonic):
        super().__init__(parent)
        self._texto = ""
        self._titulo = ""
        self._unidad = ""
        self._minimo = float("-inf")
        self._maximo = float("inf")
        self._decimales = 0
        self._valor = None
        self._valido = False
        self._fuera_de_rango = False
        self._borrado = PulsacionBorrar(self.borrar, self.limpiar, reloj=reloj, parent=self)

    def _set_texto(self, texto: str) -> None:
        self._set_fuera_de_rango(False)
        if texto == self._texto:
            return
        self._texto = texto
        self.textoChanged.emit()
        self._reevaluar()

    def _set_fuera_de_rango(self, valor: bool) -> None:
        if valor != self._fuera_de_rango:
            self._fuera_de_rango = valor
            self.fueraDeRangoChanged.emit()

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

    @Property(bool, notify=fueraDeRangoChanged)
    def fueraDeRango(self) -> bool:
        return self._fuera_de_rango

    @Property(str, notify=campoChanged)
    def titulo(self) -> str:
        return self._titulo

    @Property(str, notify=campoChanged)
    def unidad(self) -> str:
        return self._unidad

    @Property(float, notify=campoChanged)
    def minimo(self) -> float:
        return self._minimo

    @minimo.setter
    def minimo(self, value: float) -> None:
        self._minimo = value
        self.campoChanged.emit()
        self._reevaluar()

    @Property(float, notify=campoChanged)
    def maximo(self) -> float:
        return self._maximo

    @maximo.setter
    def maximo(self, value: float) -> None:
        self._maximo = value
        self.campoChanged.emit()
        self._reevaluar()

    @Property(int, notify=campoChanged)
    def decimales(self) -> int:
        return self._decimales

    @decimales.setter
    def decimales(self, value: int) -> None:
        self._decimales = value
        self.campoChanged.emit()

    @Property("QVariantList", constant=True)
    def filasTeclas(self):
        return list(dominio.FILAS_TECLAS)

    @Property(str, constant=True)
    def teclaSigno(self) -> str:
        return dominio.SIGNO

    @Property(str, constant=True)
    def teclaPunto(self) -> str:
        return dominio.PUNTO

    @Property(bool, notify=campoChanged)
    def permiteNegativo(self) -> bool:
        return dominio.permite_negativo(self._minimo)

    @Property(str, notify=campoChanged)
    def minimoTexto(self) -> str:
        return dominio.texto_limite(self._minimo, self._decimales)

    @Property(str, notify=campoChanged)
    def maximoTexto(self) -> str:
        return dominio.texto_limite(self._maximo, self._decimales)

    @Slot(str, str, "QVariant", float, float, int)
    def abrir(self, titulo: str, unidad: str, valor_inicial, minimo: float, maximo: float,
              decimales: int) -> None:
        self._borrado.cancelar()
        self._titulo = titulo
        self._unidad = unidad
        self._minimo = minimo
        self._maximo = maximo
        self._decimales = decimales
        self.campoChanged.emit()
        self._set_texto(dominio.texto_inicial(valor_inicial, decimales))
        self._reevaluar()

    @Slot(str)
    def presionarDigito(self, digito: str) -> None:
        self._set_texto(dominio.agregar_digito(self._texto, digito, self._decimales))

    @Slot(str)
    def presionarTecla(self, tecla: str) -> None:
        """Una tecla de la rejilla (filasTeclas): signo, punto o dígito."""
        if tecla == dominio.SIGNO:
            self.presionarSigno()
        elif tecla == dominio.PUNTO:
            self.presionarPunto()
        else:
            self.presionarDigito(tecla)

    @Slot()
    def presionarPunto(self) -> None:
        self._set_texto(dominio.agregar_punto(self._texto, self._decimales))

    @Slot()
    def presionarSigno(self) -> None:
        self._set_texto(dominio.alternar_signo(self._texto, dominio.permite_negativo(self._minimo)))

    @Slot()
    def borrar(self) -> None:
        self._set_texto(dominio.borrar(self._texto))

    @Slot()
    def limpiar(self) -> None:
        self._set_texto("")

    # Borrar desde QML (TEC-D12): onPressed -> presionarBorrar, onReleased ->
    # soltarBorrar, onCanceled -> cancelarPulsacionBorrar.
    @Slot()
    def presionarBorrar(self) -> None:
        self._borrado.presionar()

    @Slot()
    def soltarBorrar(self) -> None:
        self._borrado.soltar()

    @Slot()
    def cancelarPulsacionBorrar(self) -> None:
        self._borrado.cancelar()

    @Slot()
    def confirmar(self) -> None:
        estado = dominio.evaluar(self._texto, self._minimo, self._maximo)
        if not estado.valido:
            self._set_fuera_de_rango(True)
            return
        self._set_fuera_de_rango(False)
        self.confirmado.emit(estado.valor)

    @Slot()
    def cancelar(self) -> None:
        self._borrado.cancelar()
        self._set_texto("")
        self.cancelado.emit()


qmlRegisterType(TecladoNumericoController, "Autoclave.Controllers", 1, 0, "TecladoNumericoController")

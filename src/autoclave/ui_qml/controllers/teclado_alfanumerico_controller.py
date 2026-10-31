# ui_qml/controllers/teclado_alfanumerico_controller.py
#
# Puente QObject entre domain/teclado_alfanumerico.py (funciones puras) y
# el componente QML TecladoAlfanumerico. Sin lógica propia más allá de
# delegar a domain y traducir el resultado a Qt Properties/Signals (TEC-D15).
#
# Uso desde el panel: abrir(titulo, valorInicial, longitudMaxima) configura
# el campo, arma Aa si el campo abre vacío y vuelve a la capa de letras. Confirmar entrega el texto
# tal cual, incluido vacío (TEC-D09); cada pantalla valida su contenido.
#
# Reemplazo al abrir (pedido 2026-10-20): si el campo abre con texto, la
# primera tecla de carácter lo sobrescribe en vez de seguir escribiendo al
# final, como un "seleccionar todo". Por eso Aa se arma también en ese caso:
# lo que se escriba empieza un texto nuevo. Borrar antes de escribir edita el
# texto existente (quita un carácter) y vuelve a desarmar Aa.

import time

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml.controllers.pulsacion_borrar import PulsacionBorrar
from autoclave.ui_qml.domain import teclado_alfanumerico as dominio


class TecladoAlfanumericoController(QObject):
    textoChanged = Signal()
    mayusculasChanged = Signal()
    capaChanged = Signal()
    campoChanged = Signal()          # titulo, longitudMaxima
    confirmado = Signal(str)
    cancelado = Signal()

    # Dos toques a Aa dentro de esta ventana fijan las mayúsculas
    _VENTANA_DOBLE_TOQUE_S = 0.4

    def __init__(self, parent=None, reloj=time.monotonic):
        super().__init__(parent)
        self._reloj = reloj
        self._texto = ""
        self._titulo = ""
        self._longitud_maxima = 0
        self._mayusculas = True      # TEC-D05: inicia en mayúscula
        self._fijas = False          # mayúsculas fijas (doble toque en Aa)
        self._ultimo_toque_aa = None
        self._capa = dominio.CAPA_INICIAL
        self._reemplazar = False     # la próxima tecla sobrescribe el texto abierto
        self._borrado = PulsacionBorrar(self.borrar, self.limpiar, reloj=reloj, parent=self)

    def _set_texto(self, texto: str) -> None:
        if texto == self._texto:
            return
        self._texto = texto
        self.textoChanged.emit()

    def _set_mayusculas(self, valor: bool) -> None:
        if valor != self._mayusculas:
            self._mayusculas = valor
            self.mayusculasChanged.emit()

    def _set_capa(self, capa: str) -> None:
        if capa != self._capa:
            self._capa = capa
            self.capaChanged.emit()

    @Property(str, notify=textoChanged)
    def texto(self) -> str:
        return self._texto

    @Property(bool, notify=mayusculasChanged)
    def mayusculas(self) -> bool:
        """Aa armada: la siguiente letra sale en mayúscula."""
        return self._mayusculas

    @Property(bool, notify=mayusculasChanged)
    def mayusculasFijas(self) -> bool:
        """Bloqueo de mayúsculas: Aa no se desarma tras cada letra."""
        return self._fijas

    @Property(str, notify=capaChanged)
    def capa(self) -> str:
        return self._capa

    @Property(str, notify=campoChanged)
    def titulo(self) -> str:
        return self._titulo

    @Property(int, notify=campoChanged)
    def longitudMaxima(self) -> int:
        return self._longitud_maxima

    @Property("QVariantList", constant=True)
    def filasLetras(self):
        return list(dominio.FILAS_QWERTY_ES)

    @Property("QVariantList", notify=capaChanged)
    def filasCapa(self):
        """Filas de la capa activa sobre las posiciones de las letras."""
        return list(dominio.filas_de_capa(self._capa))

    @Property(str, constant=True)
    def digitos(self) -> str:
        return dominio.DIGITOS

    @Property(str, constant=True)
    def simbolos(self) -> str:
        return dominio.SIMBOLOS

    @Slot(str, str, int)
    def abrir(self, titulo: str, valor_inicial: str, longitud_maxima: int) -> None:
        self._borrado.cancelar()
        self._titulo = titulo
        self._longitud_maxima = longitud_maxima
        self.campoChanged.emit()
        self._set_texto(valor_inicial)
        self._fijas = False
        self._ultimo_toque_aa = None
        self._reemplazar = valor_inicial != ""
        self._set_mayusculas(True)   # vacío o a reemplazar: empieza texto nuevo
        self._set_capa(dominio.CAPA_INICIAL)

    @Slot(str)
    def presionarCaracter(self, caracter: str) -> None:
        base = "" if self._reemplazar else self._texto
        texto, mayusculas = dominio.pulsar_caracter(
            base, caracter, self._mayusculas, self._longitud_maxima)
        if texto == base:
            return                   # tecla ignorada: no consume el reemplazo
        self._reemplazar = False
        self._set_texto(texto)
        self._set_mayusculas(mayusculas or self._fijas)

    @Slot()
    def alternarMayusculas(self) -> None:
        """Toque simple en Aa; con mayúsculas fijas lo suelta."""
        if self._fijas:
            self._fijas = False
            self._set_mayusculas(False)
            self.mayusculasChanged.emit()
            return
        self._set_mayusculas(dominio.alternar_mayusculas(self._mayusculas))

    @Slot()
    def tocarMayusculas(self) -> None:
        """Toque en Aa desde QML: el segundo toque seguido fija las mayúsculas."""
        ahora = self._reloj()
        doble = (self._ultimo_toque_aa is not None
                 and ahora - self._ultimo_toque_aa <= self._VENTANA_DOBLE_TOQUE_S)
        if doble and not self._fijas:
            self._ultimo_toque_aa = None
            self._fijas = True
            self._set_mayusculas(True)
            self.mayusculasChanged.emit()
            return
        self._ultimo_toque_aa = ahora
        self.alternarMayusculas()

    @Slot(str)
    def cambiarCapa(self, capa: str) -> None:
        if capa in dominio.CAPAS:
            self._set_capa(capa)

    @Slot()
    def borrar(self) -> None:
        if self._reemplazar:
            # editar el texto abierto en vez de reemplazarlo
            self._reemplazar = False
            self._set_mayusculas(self._fijas)
        self._set_texto(dominio.borrar(self._texto))
        self._set_mayusculas(dominio.aa_tras_borrar(self._texto, self._mayusculas))

    @Slot()
    def limpiar(self) -> None:
        self._reemplazar = False
        self._set_texto("")
        self._set_mayusculas(dominio.aa_tras_borrar(self._texto, self._mayusculas))

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
        self.confirmado.emit(self._texto)

    @Slot()
    def cancelar(self) -> None:
        self._borrado.cancelar()
        self._reemplazar = False
        self._set_texto("")
        self.cancelado.emit()


qmlRegisterType(TecladoAlfanumericoController, "Autoclave.Controllers", 1, 0, "TecladoAlfanumericoController")

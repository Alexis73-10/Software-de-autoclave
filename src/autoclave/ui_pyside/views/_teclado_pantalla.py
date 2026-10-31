# ui_pyside/views/_teclado_pantalla.py
#
# C1a (tanda 6, P3-1 de la tanda 5): teclado en pantalla para la UI PySide.
# El equipo es táctil y no tiene teclado físico: QInputDialog no sirve. Este
# módulo da un diálogo de credenciales y diálogos de texto/número con teclado
# propio, y `conectar_teclado` para que un QLineEdit o un spinbox existente
# abra el teclado al tocarlo.
#
# - La lógica de las teclas es la MISMA de los teclados QML: se reutiliza
#   ui_qml/domain/teclado_alfanumerico.py y teclado_numerico.py (juego de
#   caracteres TEC-D03, Aa de un solo uso TEC-D05, punto decimal TEC-D14,
#   validación de rango en vivo).
# - Tamaño de tecla igual al de los teclados QML (Tema/Teclado.qml, TEC-D11):
#   96 x 88 px de diseño, radio 12, separación 14, sobre un lienzo de 1200 px
#   de ancho; se escala por el ancho de la pantalla (nunca más grande).
# - Estilo de qfluentwidgets (PushButton / PrimaryPushButton / LineEdit).

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import LineEdit, PrimaryPushButton, PushButton

from autoclave import i18n
from autoclave.ui_qml.domain import teclado_alfanumerico as ta
from autoclave.ui_qml.domain import teclado_numerico as tn

# TEC-D11 (Tema/Teclado.qml): px de diseño del lienzo de 1200
ANCHO_TECLA = 96
ALTO_TECLA = 88
RADIO_TECLA = 12
SEPARACION = 14
ANCHO_DISENO = 1200

MODO_ALFANUMERICO = "alfanumerico"
MODO_NUMERICO = "numerico"


def factor_escala() -> float:
    """Ancho de pantalla / 1200, sin agrandar nunca (mínimo 0,5)."""
    pantalla = QGuiApplication.primaryScreen()
    if pantalla is None:
        return 1.0
    ancho = pantalla.availableGeometry().width()
    return max(0.5, min(1.0, ancho / ANCHO_DISENO))


def _px(valor: float, factor: float) -> int:
    return max(1, round(valor * factor))


def _estilo_tecla(factor: float) -> str:
    return (f"border-radius: {_px(RADIO_TECLA, factor)}px;"
            f" font-size: {_px(30, factor)}px;")


class _Tecla(PushButton):
    # qfluentwidgets reenvía __init__(texto, parent) a __init__(parent): por eso
    # el texto va con setText y los argumentos propios tienen valor por defecto
    def __init__(self, texto: str = "", factor: float = 1.0, ancho: float = ANCHO_TECLA, parent=None):
        super().__init__(parent)
        self.setText(texto)
        self.setFixedSize(_px(ancho, factor), _px(ALTO_TECLA, factor))
        self.setStyleSheet(_estilo_tecla(factor))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


class _TeclaPrimaria(PrimaryPushButton):
    def __init__(self, texto: str = "", factor: float = 1.0, ancho: float = ANCHO_TECLA, parent=None):
        super().__init__(parent)
        self.setText(texto)
        self.setFixedSize(_px(ancho, factor), _px(ALTO_TECLA, factor))
        self.setStyleSheet(_estilo_tecla(factor))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


# ── teclado alfanumérico ──────────────────────────────────────────────────

class TecladoAlfanumerico(QWidget):
    """Letras (QWERTY español con ñ) y capa ?123. Emite `cambiado(texto)`
    en cada tecla, `confirmado()` y `cancelado()`."""

    cambiado = Signal(str)
    confirmado = Signal()
    cancelado = Signal()

    def __init__(self, longitud_maxima: int = 0, parent=None, factor: float | None = None):
        super().__init__(parent)
        self._factor = factor_escala() if factor is None else factor
        self._longitud_maxima = longitud_maxima
        self._texto = ""
        self._mayusculas = ta.aa_al_abrir("")
        self._capa = ta.CAPA_INICIAL
        self._teclas_caracter: list[_Tecla] = []
        self._construir()
        self._rotular()

    # estado
    @property
    def texto(self) -> str:
        return self._texto

    @property
    def mayusculas(self) -> bool:
        return self._mayusculas

    @property
    def capa(self) -> str:
        return self._capa

    def fijar_texto(self, texto: str) -> None:
        self._texto = texto or ""
        self._mayusculas = ta.aa_al_abrir(self._texto)
        self._rotular()

    # acciones (también las usan las pruebas)
    def pulsar(self, caracter: str) -> None:
        self._texto, self._mayusculas = ta.pulsar_caracter(
            self._texto, caracter, self._mayusculas, self._longitud_maxima)
        self._rotular()
        self.cambiado.emit(self._texto)

    def pulsar_posicion(self, fila: int, columna: int) -> None:
        self.pulsar(ta.filas_de_capa(self._capa)[fila][columna])

    def borrar(self) -> None:
        self._texto = ta.borrar(self._texto)
        self._mayusculas = ta.aa_tras_borrar(self._texto, self._mayusculas)
        self._rotular()
        self.cambiado.emit(self._texto)

    def alternar_mayusculas(self) -> None:
        self._mayusculas = ta.alternar_mayusculas(self._mayusculas)
        self._rotular()

    def alternar_capa(self) -> None:
        self._capa = "numeros" if self._capa == "letras" else "letras"
        self._rotular()

    # construcción
    def _construir(self) -> None:
        f = self._factor
        sep = _px(SEPARACION, f)
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(sep)
        self._filas: list[list[_Tecla]] = []
        for i, fila in enumerate(ta.FILAS_QWERTY_ES):
            h = QHBoxLayout()
            h.setSpacing(sep)
            h.addStretch(1)
            if i == 2:
                self.tecla_aa = _Tecla(i18n.t("teclado.aa"), f, ANCHO_TECLA * 1.5)
                self.tecla_aa.setCheckable(True)
                self.tecla_aa.clicked.connect(self.alternar_mayusculas)
                h.addWidget(self.tecla_aa)
            teclas = []
            for j in range(len(fila)):
                t = _Tecla("", f)
                t.clicked.connect(lambda _=False, a=i, b=j: self.pulsar_posicion(a, b))
                h.addWidget(t)
                teclas.append(t)
            if i == 2:
                self.tecla_borrar = _Tecla("⌫ " + i18n.t("acciones.borrar"), f, ANCHO_TECLA * 2)
                self.tecla_borrar.clicked.connect(self.borrar)
                h.addWidget(self.tecla_borrar)
            h.addStretch(1)
            raiz.addLayout(h)
            self._filas.append(teclas)
        h = QHBoxLayout()
        h.setSpacing(sep)
        self.tecla_capa = _Tecla("", f, ANCHO_TECLA * 1.5)
        self.tecla_capa.clicked.connect(self.alternar_capa)
        self.tecla_cancelar = _Tecla(i18n.t("acciones.cancelar"), f, ANCHO_TECLA * 2)
        self.tecla_cancelar.clicked.connect(self.cancelado.emit)
        self.tecla_espacio = _Tecla(i18n.t("teclado.espacio"), f, ANCHO_TECLA * 4)
        self.tecla_espacio.clicked.connect(lambda: self.pulsar(ta.ESPACIO))
        self.tecla_confirmar = _TeclaPrimaria(i18n.t("acciones.confirmar"), f, ANCHO_TECLA * 2)
        self.tecla_confirmar.clicked.connect(self.confirmado.emit)
        for w in (self.tecla_capa, self.tecla_cancelar, self.tecla_espacio, self.tecla_confirmar):
            h.addWidget(w)
        raiz.addLayout(h)

    def _rotular(self) -> None:
        filas = ta.filas_de_capa(self._capa)
        for i, teclas in enumerate(self._filas):
            fila = filas[i] if i < len(filas) else ""
            for j, t in enumerate(teclas):
                c = fila[j] if j < len(fila) else ""
                t.setVisible(c != "")
                t.setText(ta.transformar_caracter(c, self._mayusculas) if c else "")
        self.tecla_aa.setChecked(self._mayusculas)
        self.tecla_aa.setVisible(self._capa == "letras")
        self.tecla_capa.setText(i18n.t("teclado.capa_numeros") if self._capa == "letras"
                                else i18n.t("teclado.capa_letras"))


# ── teclado numérico ──────────────────────────────────────────────────────

class TecladoNumerico(QWidget):
    """Calculadora 7-8-9 arriba; signo, 0 y punto abajo. Confirmar solo con
    un valor válido dentro de [minimo, maximo]."""

    cambiado = Signal(str)
    confirmado = Signal()
    cancelado = Signal()

    def __init__(self, minimo=None, maximo=None, decimales: int = 0, parent=None,
                 factor: float | None = None):
        super().__init__(parent)
        self._factor = factor_escala() if factor is None else factor
        self._minimo, self._maximo, self._decimales = minimo, maximo, decimales
        self._texto = ""
        self._construir()
        self._actualizar()

    @property
    def texto(self) -> str:
        return self._texto

    def estado(self) -> tn.EstadoTecladoNumerico:
        return tn.evaluar(self._texto, self._minimo, self._maximo)

    def fijar_texto(self, texto: str) -> None:
        self._texto = texto or ""
        # revisión C1a (SAF-03): la primera tecla reemplaza el valor inicial
        self._reemplazar = self._texto != ""
        self._actualizar()

    def pulsar(self, tecla: str) -> None:
        if getattr(self, "_reemplazar", False) and tecla != tn.SIGNO:
            self._texto = ""
        self._reemplazar = False
        if tecla == tn.PUNTO:
            self._texto = tn.agregar_punto(self._texto, self._decimales)
        elif tecla == tn.SIGNO:
            self._texto = tn.alternar_signo(self._texto, tn.permite_negativo(self._minimo))
        else:
            self._texto = tn.agregar_digito(self._texto, tecla, self._decimales)
        self._actualizar()
        self.cambiado.emit(self._texto)

    def borrar(self) -> None:
        self._reemplazar = False
        self._texto = tn.borrar(self._texto)
        self._actualizar()
        self.cambiado.emit(self._texto)

    def _construir(self) -> None:
        f = self._factor
        sep = _px(SEPARACION, f)
        rejilla = QGridLayout(self)
        rejilla.setContentsMargins(0, 0, 0, 0)
        rejilla.setSpacing(sep)
        self.teclas: dict[str, _Tecla] = {}
        for i, fila in enumerate(tn.FILAS_TECLAS):
            for j, c in enumerate(fila):
                t = _Tecla(c, f)
                t.clicked.connect(lambda _=False, k=c: self.pulsar(k))
                rejilla.addWidget(t, i, j)
                self.teclas[c] = t
        self.tecla_borrar = _Tecla("⌫", f, ANCHO_TECLA * 2)
        self.tecla_borrar.clicked.connect(self.borrar)
        self.tecla_cancelar = _Tecla(i18n.t("acciones.cancelar"), f, ANCHO_TECLA * 2)
        self.tecla_cancelar.clicked.connect(self.cancelado.emit)
        self.tecla_confirmar = _TeclaPrimaria(i18n.t("acciones.confirmar"), f, ANCHO_TECLA * 2)
        self.tecla_confirmar.clicked.connect(self.confirmado.emit)
        rejilla.addWidget(self.tecla_borrar, 0, 3)
        rejilla.addWidget(self.tecla_cancelar, 2, 3)
        rejilla.addWidget(self.tecla_confirmar, 3, 3)

    def _actualizar(self) -> None:
        self.teclas[tn.SIGNO].setEnabled(tn.permite_negativo(self._minimo))
        self.teclas[tn.PUNTO].setEnabled(self._decimales > 0)
        self.tecla_confirmar.setEnabled(self.estado().valido)


# ── diálogos ──────────────────────────────────────────────────────────────

class _CampoTactil(LineEdit):
    """Campo de solo lectura: el texto lo pone el teclado en pantalla."""
    tocado = Signal()

    def __init__(self, secreto: bool = False, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMinimumHeight(56)
        if secreto:
            self.setEchoMode(QLineEdit.EchoMode.Password)

    def mousePressEvent(self, e):
        self.tocado.emit()
        super().mousePressEvent(e)


class DialogoTexto(QDialog):
    """Pide un texto o un número con el teclado en pantalla."""

    def __init__(self, padre, titulo: str, etiqueta: str, inicial: str = "",
                 secreto: bool = False, modo: str = MODO_ALFANUMERICO,
                 minimo=None, maximo=None, decimales: int = 0, longitud_maxima: int = 0):
        super().__init__(padre)
        self.setWindowTitle(titulo)
        self.setModal(True)
        self._modo = modo
        lay = QVBoxLayout(self)
        self.etiqueta = QLabel(etiqueta)
        self.etiqueta.setWordWrap(True)
        lay.addWidget(self.etiqueta)
        self.campo = _CampoTactil(secreto)
        lay.addWidget(self.campo)
        self.aviso = QLabel("")
        lay.addWidget(self.aviso)
        if modo == MODO_NUMERICO:
            self.teclado = TecladoNumerico(minimo, maximo, decimales, self)
            if minimo is not None or maximo is not None:
                self.aviso.setText(i18n.t("teclado.rango",
                                          minimo=tn.texto_limite(minimo, decimales) or "—",
                                          maximo=tn.texto_limite(maximo, decimales) or "—",
                                          unidad=""))
        else:
            self.teclado = TecladoAlfanumerico(longitud_maxima, self)
        self.teclado.fijar_texto(inicial)
        self.campo.setText(inicial)
        self.teclado.cambiado.connect(self.campo.setText)
        self.teclado.confirmado.connect(self._confirmar)
        self.teclado.cancelado.connect(self.reject)
        lay.addWidget(self.teclado)

    def _confirmar(self) -> None:
        if self._modo == MODO_NUMERICO and not self.teclado.estado().valido:
            return
        self.accept()

    def valor(self):
        if self._modo == MODO_NUMERICO:
            return self.teclado.estado().valor
        return self.teclado.texto


class DialogoCredenciales(QDialog):
    """Usuario y contraseña con un solo teclado alfanumérico. Confirmar en
    el usuario pasa a la contraseña; en la contraseña acepta si ambos
    campos tienen texto."""

    def __init__(self, padre, titulo: str, mensaje: str, usuario_previo: str = ""):
        super().__init__(padre)
        self.setWindowTitle(titulo)
        self.setModal(True)
        lay = QVBoxLayout(self)
        self.mensaje = QLabel(mensaje)
        self.mensaje.setWordWrap(True)
        lay.addWidget(self.mensaje)
        lay.addWidget(QLabel(i18n.t("formulario.nombre_usuario")))
        self.campo_usuario = _CampoTactil(False)
        lay.addWidget(self.campo_usuario)
        lay.addWidget(QLabel(i18n.t("formulario.contrasena")))
        self.campo_clave = _CampoTactil(True)
        lay.addWidget(self.campo_clave)
        self.teclado = TecladoAlfanumerico(0, self)
        lay.addWidget(self.teclado)
        self._textos = {"usuario": usuario_previo or "", "clave": ""}
        self.campo_usuario.setText(self._textos["usuario"])
        # revisión C1a (SAF-02): con usuario previo solo reingresa esa persona
        self._usuario_fijo = bool(self._textos["usuario"])
        if self._usuario_fijo:
            self.campo_usuario.setEnabled(False)
        else:
            self.campo_usuario.tocado.connect(lambda: self.activar("usuario"))
        self.campo_clave.tocado.connect(lambda: self.activar("clave"))
        self.teclado.cambiado.connect(self._al_cambiar)
        self.teclado.confirmado.connect(self._confirmar)
        self.teclado.cancelado.connect(self.reject)
        self._activo = ""
        self.activar("clave" if self._textos["usuario"] else "usuario")

    @property
    def activo(self) -> str:
        return self._activo

    def activar(self, campo: str) -> None:
        self._activo = campo
        self.teclado.fijar_texto(self._textos[campo])
        for nombre, w in (("usuario", self.campo_usuario), ("clave", self.campo_clave)):
            w.setStyleSheet("border: 2px solid #2563eb;" if nombre == campo else "")

    def _al_cambiar(self, texto: str) -> None:
        self._textos[self._activo] = texto
        (self.campo_usuario if self._activo == "usuario" else self.campo_clave).setText(texto)

    def _confirmar(self) -> None:
        if self._activo == "usuario":
            self.activar("clave")
            return
        if self._textos["usuario"].strip() and self._textos["clave"]:
            self.accept()
        elif not self._textos["usuario"].strip():
            self.activar("usuario")

    def credenciales(self) -> tuple[str, str]:
        return self._textos["usuario"].strip(), self._textos["clave"]


# ── funciones de uso ──────────────────────────────────────────────────────

def pedir_credenciales(padre, titulo: str, mensaje: str, usuario_previo: str = ""):
    """(usuario, clave) o None si se cancela."""
    dlg = DialogoCredenciales(padre, titulo, mensaje, usuario_previo)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    usuario, clave = dlg.credenciales()
    return (usuario, clave) if usuario and clave else None


def pedir_texto(padre, titulo: str, etiqueta: str, inicial: str = "", secreto: bool = False,
                longitud_maxima: int = 0):
    """Texto tecleado o None si se cancela."""
    dlg = DialogoTexto(padre, titulo, etiqueta, inicial, secreto, MODO_ALFANUMERICO,
                       longitud_maxima=longitud_maxima)
    return dlg.valor() if dlg.exec() == QDialog.DialogCode.Accepted else None


def pedir_numero(padre, titulo: str, etiqueta: str, inicial=None, minimo=None, maximo=None,
                 decimales: int = 0):
    """Número dentro de [minimo, maximo] o None si se cancela."""
    dlg = DialogoTexto(padre, titulo, etiqueta, tn.texto_inicial(inicial, decimales), False,
                       MODO_NUMERICO, minimo, maximo, decimales)
    return dlg.valor() if dlg.exec() == QDialog.DialogCode.Accepted else None


class _AbrirAlTocar(QObject):
    def __init__(self, destino, abrir):
        super().__init__(destino)
        self._abrir = abrir

    def eventFilter(self, obj, evento):
        if evento.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.TouchEnd):
            # revisión C1a (SAF-04): una sola apertura aunque lleguen toque y ratón
            if obj.isEnabled() and not getattr(self, "_abierto", False):
                self._abierto = True
                try:
                    self._abrir()
                finally:
                    self._abierto = False
            return True
        if evento.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.TouchBegin):
            return True
        return False


def conectar_teclado(campo, titulo: str, etiqueta: str = "", secreto: bool | None = None):
    """Al tocar `campo` (QLineEdit o spinbox) se abre el teclado en pantalla.
    En un spinbox el valor se valida contra su mínimo y máximo."""
    if isinstance(campo, QAbstractSpinBox):
        editor = campo.lineEdit()
        decimales = campo.decimals() if hasattr(campo, "decimals") else 0

        def abrir():
            v = pedir_numero(campo.window(), titulo, etiqueta or titulo, campo.value(),
                             campo.minimum(), campo.maximum(), decimales)
            if v is not None:
                campo.setValue(v if decimales else int(round(v)))
    else:
        editor = campo
        oculto = (campo.echoMode() == QLineEdit.EchoMode.Password) if secreto is None else secreto

        def abrir():
            v = pedir_texto(campo.window(), titulo, etiqueta or titulo,
                            "" if oculto else campo.text(), oculto, campo.maxLength()
                            if campo.maxLength() < 32767 else 0)
            if v is not None:
                campo.setText(v)
    filtro = _AbrirAlTocar(editor, abrir)
    editor.installEventFilter(filtro)
    editor._teclado_pantalla = filtro          # mantiene viva la referencia
    editor._abrir_teclado = abrir             # para pruebas
    return filtro


def conectar_todos(raiz, titulo: str = "") -> int:
    """Conecta el teclado en pantalla a todos los QLineEdit y spinboxes hijos
    de `raiz` (una sola vez cada uno). Devuelve cuántos conectó."""
    n = 0
    for spin in raiz.findChildren(QAbstractSpinBox):
        if getattr(spin.lineEdit(), "_teclado_pantalla", None) is None:
            conectar_teclado(spin, titulo or spin.accessibleName() or raiz.windowTitle())
            n += 1
    for campo in raiz.findChildren(QLineEdit):
        if isinstance(campo.parent(), QAbstractSpinBox) or campo.isReadOnly():
            continue
        if getattr(campo, "_teclado_pantalla", None) is None:
            conectar_teclado(campo, titulo or campo.placeholderText() or raiz.windowTitle())
            n += 1
    return n

# ui_qml/bridge/i18n_qml.py
#
# Singleton QML `I18n` (módulo "Autoclave.I18n" 1.0) sobre el módulo
# autoclave.i18n: una sola lógica de textos para QML y Python (planeacion_i18n.md
# §3.4, F1). Se registra al importar este módulo (lo hace ui_qml/app.py).
#
# Uso obligatorio en QML, para que el binding se re-evalúe al cambiar idioma:
#   import Autoclave.I18n
#   text: I18n.t("seccion.clave", I18n.lang)
#   text: I18n.t("sesion.bloqueado", I18n.lang, { tiempo: 30 })
#   readonly property var meses: I18n.valor("fecha.meses", I18n.lang)

import math
import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtQml import QJSValue, QQmlEngine, qmlRegisterSingletonType

from autoclave import i18n

URI = "Autoclave.I18n"
# I4 (tanda 6): cada ventana sigue el idioma del backend (GET /language), igual
# que Unidades sigue GET /units: así la segunda pantalla del equipo de dos
# puertas aplica el idioma vigente al arrancar y al cambiarlo desde la otra.
INTERVALO_MS = 3000


def como_texto_js(v) -> str:
    """Convierte un parámetro como lo haría String(v) en JavaScript: los
    números de QML llegan como float (5 -> 5.0) y deben verse "5"."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        if math.isinf(v):
            return "Infinity" if v > 0 else "-Infinity"
        if v.is_integer() and abs(v) < 1e21:
            return str(int(v))
        return repr(v)
    return str(v)


class I18nQml(QObject):
    langChanged = Signal()
    _recibido = Signal(object, str)    # desde el hilo de consulta

    def __init__(self, parent=None, consultar=None, sondear: bool = False):
        super().__init__(parent)
        i18n.al_cambiar_idioma(lambda _idioma: self.langChanged.emit())
        self._consultar = consultar or self._consultar_backend
        self._ocupado = False
        self._recibido.connect(self._aplicar_respuesta)
        self._timer = QTimer(self)
        self._timer.setInterval(INTERVALO_MS)
        self._timer.timeout.connect(self.refrescar)
        if sondear:
            self._timer.start()

    # ── seguimiento del backend (I4) ───────────────────────────────────

    @staticmethod
    def _consultar_backend():
        from autoclave.ui_qml.sesion_backend import transporte_http
        estado, datos = transporte_http("GET", "/language", None, None, 1.0)
        return datos if estado == 200 else None

    @Slot()
    def refrescar(self) -> None:
        if self._ocupado:
            return
        self._ocupado = True
        antes = i18n.idioma()

        def trabajo():
            datos = None
            try:
                datos = self._consultar()
            except Exception:
                datos = None
            finally:                      # M-01: siempre libera _ocupado
                self._recibido.emit(datos, antes)
        try:
            threading.Thread(target=trabajo, daemon=True, name="idioma").start()
        except Exception:                 # SAF-02: el sondeo no queda detenido
            self._ocupado = False

    def aplicar(self, datos, idioma_al_pedir: str | None = None) -> None:
        """Aplica una respuesta de GET /language. Sin respuesta o inválida se
        conserva el idioma vigente. Si el idioma cambió localmente mientras la
        consulta estaba en vuelo (PUT desde esta ventana), la respuesta vieja se
        descarta: la siguiente consulta trae el valor nuevo."""
        self._ocupado = False
        if idioma_al_pedir is not None and idioma_al_pedir != i18n.idioma():
            return
        nuevo = datos.get("idioma") if isinstance(datos, dict) else None
        if nuevo in i18n.IDIOMAS and nuevo != i18n.idioma():
            i18n.fijar_idioma(nuevo)

    def _aplicar_respuesta(self, datos, idioma_al_pedir: str) -> None:
        self.aplicar(datos, idioma_al_pedir)

    @Property(str, notify=langChanged)
    def lang(self) -> str:
        return i18n.idioma()

    @staticmethod
    def _idioma_valido(lang: str) -> str | None:
        return lang if lang in i18n.IDIOMAS else None

    @Slot(str, str, result=str)
    @Slot(str, str, "QVariant", result=str)
    def t(self, clave: str, lang: str, params=None) -> str:
        """Texto de la clave; `params` es un objeto JS opcional {nombre: valor}."""
        if isinstance(params, QJSValue):
            params = params.toVariant()
        return i18n.traducir(clave, self._idioma_valido(lang),
                             params if isinstance(params, dict) else None, como_texto_js)

    @Slot(str, str, result="QVariant")
    def valor(self, clave: str, lang: str):
        """Valor crudo (lista u objeto, p. ej. fecha.meses o fases); null si no existe."""
        return i18n.valor(clave, self._idioma_valido(lang))

    @Slot(str, str, result=bool)
    def existe(self, clave: str, lang: str) -> bool:
        """True si la clave tiene texto (para respaldos propios de la pantalla)."""
        return i18n.existe(clave, self._idioma_valido(lang))


# Una sola instancia para todos los motores QML del proceso (las pruebas crean
# varios): el motor no la adopta, así no la destruye al cerrarse.
instancia = I18nQml()


def _fabrica(_motor):
    QQmlEngine.setObjectOwnership(instancia, QQmlEngine.ObjectOwnership.CppOwnership)
    # El sondeo arranca la primera vez que un motor QML pide el singleton.
    if not instancia._timer.isActive():
        instancia._timer.start()
        instancia.refrescar()
    return instancia


qmlRegisterSingletonType(I18nQml, URI, 1, 0, "I18n", _fabrica)

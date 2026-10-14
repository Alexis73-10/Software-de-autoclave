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

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtQml import QJSValue, QQmlEngine, qmlRegisterSingletonType

from autoclave import i18n

URI = "Autoclave.I18n"


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

    def __init__(self, parent=None):
        super().__init__(parent)
        i18n.al_cambiar_idioma(lambda _idioma: self.langChanged.emit())

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
    return instancia


qmlRegisterSingletonType(I18nQml, URI, 1, 0, "I18n", _fabrica)

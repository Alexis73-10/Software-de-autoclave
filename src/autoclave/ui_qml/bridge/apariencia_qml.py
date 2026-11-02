# ui_qml/bridge/apariencia_qml.py
#
# Modo oscuro: singleton QML `Apariencia` (módulo "Autoclave.Apariencia" 1.0)
# con el tema vigente de la interfaz. Se registra al importar este módulo (lo
# hace ui_qml/app.py), igual que I18n y Unidades.
#
# Solo lo leen las raíces de ventana (Main.qml, InstalacionVentana.qml,
# ReposoInstalacionVentana.qml, NuevoUsuarioHost.qml), que enlazan
#   Binding { target: Colores; property: "oscuro"; value: Apariencia.oscuro }
# Ninguna pantalla ni lógica pregunta por el tema: solo leen Colores.*.
#
# Cada ventana sigue el tema del backend (GET /theme cada 3 s, como I4 del
# idioma): la segunda pantalla aplica el tema vigente al arrancar y al
# cambiarlo desde la otra. Valor inicial claro; respuesta ausente o inválida
# conserva el vigente.

import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtQml import QQmlEngine, qmlRegisterSingletonType

URI = "Autoclave.Apariencia"
TEMAS = ("claro", "oscuro")
POR_DEFECTO = "claro"
INTERVALO_MS = 3000


class AparienciaQml(QObject):
    temaChanged = Signal()
    _recibido = Signal(object, str)    # desde el hilo de consulta

    def __init__(self, parent=None, consultar=None, sondear: bool = False):
        super().__init__(parent)
        self._tema = POR_DEFECTO
        self._consultar = consultar or self._consultar_backend
        self._ocupado = False
        self._recibido.connect(self._aplicar_respuesta)
        self._timer = QTimer(self)
        self._timer.setInterval(INTERVALO_MS)
        self._timer.timeout.connect(self.refrescar)
        if sondear:
            self._timer.start()

    # ── seguimiento del backend ──────────────────────────────────────────

    @staticmethod
    def _consultar_backend():
        from autoclave.ui_qml.sesion_backend import transporte_http
        estado, datos = transporte_http("GET", "/theme", None, None, 1.0)
        return datos if estado == 200 else None

    @Slot()
    def refrescar(self) -> None:
        if self._ocupado:
            return
        self._ocupado = True
        antes = self._tema

        def trabajo():
            datos = None
            try:
                datos = self._consultar()
            except Exception:
                datos = None
            finally:                      # siempre libera _ocupado
                self._recibido.emit(datos, antes)
        try:
            threading.Thread(target=trabajo, daemon=True, name="tema").start()
        except Exception:                 # el sondeo no queda detenido
            self._ocupado = False

    def aplicar(self, datos, tema_al_pedir: str | None = None) -> None:
        """Aplica una respuesta de GET /theme. Sin respuesta o inválida se
        conserva el tema vigente. Si el tema cambió localmente mientras la
        consulta estaba en vuelo (PUT desde esta ventana), la respuesta vieja
        se descarta: la siguiente consulta trae el valor nuevo."""
        self._ocupado = False
        if tema_al_pedir is not None and tema_al_pedir != self._tema:
            return
        nuevo = datos.get("tema") if isinstance(datos, dict) else None
        if nuevo in TEMAS:
            self.fijar(nuevo)

    def _aplicar_respuesta(self, datos, tema_al_pedir: str) -> None:
        self.aplicar(datos, tema_al_pedir)

    def fijar(self, tema: str) -> bool:
        """Cambio local inmediato (lo usa el slot fijarTema tras el PUT).
        Un valor inválido no cambia nada."""
        if tema not in TEMAS:
            return False
        if tema != self._tema:
            self._tema = tema
            self.temaChanged.emit()
        return True

    @Property(str, notify=temaChanged)
    def tema(self) -> str:
        return self._tema

    @Property(bool, notify=temaChanged)
    def oscuro(self) -> bool:
        return self._tema == "oscuro"


# Una sola instancia para todos los motores QML del proceso (las pruebas crean
# varios): el motor no la adopta, así no la destruye al cerrarse.
instancia = AparienciaQml()


def _fabrica(_motor):
    QQmlEngine.setObjectOwnership(instancia, QQmlEngine.ObjectOwnership.CppOwnership)
    # El sondeo arranca la primera vez que un motor QML pide el singleton.
    if not instancia._timer.isActive():
        instancia._timer.start()
        instancia.refrescar()
    return instancia


qmlRegisterSingletonType(AparienciaQml, URI, 1, 0, "Apariencia", _fabrica)

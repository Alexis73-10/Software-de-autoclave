# ui_qml/controllers/ciclo_controller.py
#
# Puente QObject entre domain/pantalla_ciclo.py y Pantallas/Ciclo.qml: publica
# las consignas del ciclo seleccionado y las lecturas de cámara.
#
# Transporte provisional: sondeo REST a GET /status y GET /cycle cada
# `intervalo_ms`, con QNetworkAccessManager (asíncrono, no bloquea la UI).
# El contrato definitivo es el WebSocket /ws/telemetry (D-12,
# planeacion_ui_dual_pantalla.md §6.2), que el backend aún no expone; al
# llegar, solo cambia el transporte: aplicar_ciclo/aplicar_status se conservan.
#
# Pérdida de conexión (§6.4): los valores se congelan y `conectado` baja a
# false para que la pantalla los marque como no vigentes.

import json

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtQml import qmlRegisterType

from autoclave.ui_qml.domain import pantalla_ciclo as dominio

URL_BACKEND = "http://localhost:8000"
_TIMEOUT_MS = 800   # mismo timeout que BackendClient


class CicloController(QObject):
    datosChanged = Signal()
    conectadoChanged = Signal()

    def __init__(self, parent=None, url_base=URL_BACKEND, intervalo_ms=1000, iniciar=True):
        super().__init__(parent)
        self._url_base = url_base.rstrip("/")
        self._datos = {**dominio.parametros_de_ciclo(None), **dominio.lecturas_de_status(None)}
        self._conectado = False
        self._pendientes = set()

        self._red = QNetworkAccessManager(self)
        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self.sondear)
        if iniciar:
            self._timer.start()
            QTimer.singleShot(0, self.sondear)

    # ── entrada de datos (independiente del transporte) ──────────────────

    def aplicar_ciclo(self, ciclo) -> None:
        """Respuesta de GET /cycle; None si no hay ciclo seleccionado."""
        self._actualizar(dominio.parametros_de_ciclo(ciclo))

    def aplicar_status(self, status) -> None:
        """Respuesta de GET /status. Una respuesta implica backend alcanzable."""
        self._actualizar(dominio.lecturas_de_status(status))
        self._fijar_conectado(True)

    def marcar_sin_conexion(self) -> None:
        self._fijar_conectado(False)

    def _actualizar(self, nuevos: dict) -> None:
        if any(self._datos.get(k) != v for k, v in nuevos.items()):
            self._datos.update(nuevos)
            self.datosChanged.emit()

    def _fijar_conectado(self, valor: bool) -> None:
        if valor != self._conectado:
            self._conectado = valor
            self.conectadoChanged.emit()

    # ── transporte REST ──────────────────────────────────────────────────

    def sondear(self) -> None:
        for ruta in ("/status", "/cycle"):
            if ruta not in self._pendientes:   # no apilar peticiones si el backend va lento
                self._pedir(ruta)

    def _pedir(self, ruta: str) -> None:
        peticion = QNetworkRequest(QUrl(self._url_base + ruta))
        peticion.setTransferTimeout(_TIMEOUT_MS)
        self._pendientes.add(ruta)
        respuesta = self._red.get(peticion)
        respuesta.finished.connect(lambda: self._al_responder(ruta, respuesta))

    def _al_responder(self, ruta: str, respuesta: QNetworkReply) -> None:
        self._pendientes.discard(ruta)
        http = respuesta.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        cuerpo = bytes(respuesta.readAll().data())
        respuesta.deleteLater()

        if http is None:                      # sin respuesta HTTP: backend caído o timeout
            self.marcar_sin_conexion()
            return
        try:
            datos = json.loads(cuerpo) if http == 200 else None
        except ValueError:
            datos = None                      # frontera: cuerpo inválido = sin dato

        if ruta == "/status":
            if datos is None:
                self.marcar_sin_conexion()
            else:
                self.aplicar_status(datos)
        else:
            self.aplicar_ciclo(datos)         # 404 = no hay ciclo seleccionado

    # ── propiedades para QML ─────────────────────────────────────────────

    @Property(str, notify=datosChanged)
    def programa(self) -> str:
        return self._datos["programa"]

    @Property(str, notify=datosChanged)
    def tempEsterilizacion(self) -> str:
        return self._datos["temp_esterilizacion"]

    @Property(str, notify=datosChanged)
    def tiempoEsterilizacion(self) -> str:
        return self._datos["tiempo_esterilizacion"]

    @Property(str, notify=datosChanged)
    def tiempoSecado(self) -> str:
        return self._datos["tiempo_secado"]

    @Property(str, notify=datosChanged)
    def tempCamara(self) -> str:
        return self._datos["temp_camara"]

    @Property(str, notify=datosChanged)
    def presionCamara(self) -> str:
        return self._datos["presion_camara"]

    @Property(bool, notify=conectadoChanged)
    def conectado(self) -> bool:
        return self._conectado


qmlRegisterType(CicloController, "Autoclave.Controllers", 1, 0, "CicloController")

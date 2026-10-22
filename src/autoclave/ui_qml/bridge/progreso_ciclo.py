# ui_qml/bridge/progreso_ciclo.py
#
# Puente de SOLO LECTURA para la pantalla de ciclo en curso
# (planeacion_pantalla_ciclo_en_curso.md §6 B1/B2 y §8). Cada INTERVALO_MS,
# mientras `activo` (la pantalla visible), consulta en un hilo:
#   GET /cycle/current/progress  -> fases, transcurrido y restante (s)
#   GET /cycle/current/graph     -> histórico al entrar, luego solo lo nuevo
# y publica el resultado en el hilo de la GUI. Los tiempos los mide el backend
# con reloj monotónico; aquí solo se reenvían (C-01). Sin conexión se conservan
# los últimos datos y se reintenta en el siguiente tick.

import logging
import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from autoclave.ui_qml.domain.ciclo_en_curso import AcumuladorGrafica, normalizar_progreso

logger = logging.getLogger(__name__)

# Decisión delegada (plan §14): progreso y lecturas incrementales cada 1 s.
INTERVALO_MS = 1000


def _en_unidad_vigente(datos: dict) -> dict:
    """O3 (tanda 6): la gráfica se dibuja en la unidad vigente (U1)."""
    from autoclave.ui_qml.domain import entradas_mostradas, pantalla_ciclo
    t, p, _p_atm = pantalla_ciclo._vigentes()
    return entradas_mostradas.convertir_datos_grafica(datos, t, p)


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="progreso-ciclo").start()


class ProgresoCiclo(QObject):
    activoChanged = Signal()
    progresoChanged = Signal()
    graficaChanged = Signal()
    _recibido = Signal(object, object)   # (progreso, grafica) desde el hilo de trabajo

    def __init__(self, backend_client, parent=None, intervalo_ms: int = INTERVALO_MS,
                 ejecutar=_en_hilo, iniciar: bool = True):
        super().__init__(parent)
        self._backend = backend_client
        self._ejecutar = ejecutar
        self._activo = False
        self._consultando = False
        self._progreso = normalizar_progreso(None)
        self._acumulador = AcumuladorGrafica()
        self._datos = self._acumulador.datos()
        self._fases_grafica: list = []
        self._recibido.connect(self._al_recibir)

        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self.refrescar)
        self._iniciar = iniciar

    def detener(self) -> None:
        self._timer.stop()

    # ── sondeo ───────────────────────────────────────────────────────────

    @Slot()
    def refrescar(self) -> None:
        if not self._activo or self._consultando:
            return
        self._consultando = True
        desde_id = self._acumulador.desde_id

        def tarea():
            progreso = grafica = None
            try:
                progreso = self._backend.get("/cycle/current/progress")
                if isinstance(progreso, dict) and progreso.get("activo") is True:
                    params = {"desde_id": desde_id} if desde_id is not None else None
                    grafica = self._backend.get("/cycle/current/graph", params=params)
            except Exception as e:
                logger.debug("progreso del ciclo no disponible: %s", e)
                progreso = grafica = None
            self._recibido.emit(progreso, grafica)

        self._ejecutar(tarea)

    def _al_recibir(self, progreso, grafica) -> None:
        self._consultando = False
        if progreso is None:
            return   # sin conexión: se conservan los últimos datos

        nuevo = normalizar_progreso(progreso)
        if not nuevo["activo"]:
            grafica = {"ciclo_db_id": None, "lecturas": []}
        if nuevo != self._progreso:
            self._progreso = nuevo
            self.progresoChanged.emit()

        cambio = self._acumulador.incorporar(grafica)
        fases = self._acumulador.inicios_de_fase(nuevo["aplicables"])
        if cambio or fases != self._fases_grafica:
            self._datos = _en_unidad_vigente(self._acumulador.datos())
            self._fases_grafica = fases
            self.graficaChanged.emit()

    # ── propiedades para QML ─────────────────────────────────────────────

    def _get_activo(self) -> bool:
        return self._activo

    def _set_activo(self, valor: bool) -> None:
        valor = bool(valor)
        if valor == self._activo:
            return
        self._activo = valor
        if valor and self._iniciar:
            self._timer.start()
            QTimer.singleShot(0, self.refrescar)
        elif not valor:
            self._timer.stop()
        self.activoChanged.emit()

    # La pantalla lo activa mientras está visible: sin pantalla no se consulta.
    activo = Property(bool, _get_activo, _set_activo, notify=activoChanged)

    @Property(bool, notify=progresoChanged)
    def hayCiclo(self) -> bool:
        return self._progreso["activo"]

    @Property(str, notify=progresoChanged)
    def faseCiclo(self) -> str:
        return self._progreso["fase_ciclo"]

    # "" mientras el ciclo corre; "exitoso" / "cancelado" / "fallo" al terminar
    # (la máquina sigue en CICLO esperando la confirmación del operador)
    @Property(str, notify=progresoChanged)
    def resultado(self) -> str:
        return self._progreso["resultado"] or ""

    @Property("QVariantList", notify=progresoChanged)
    def fases(self) -> list:
        return self._progreso["fases"]

    @Property("QVariant", notify=progresoChanged)
    def transcurridoS(self):
        return self._progreso["transcurrido_s"]

    @Property("QVariant", notify=progresoChanged)
    def restanteS(self):
        return self._progreso["restante_s"]

    @Property(float, notify=progresoChanged)
    def tiempoActualMin(self) -> float:
        t = self._progreso["transcurrido_s"]
        return t / 60.0 if t is not None else 0.0

    @Property("QVariantMap", notify=graficaChanged)
    def datosGrafica(self) -> dict:
        return self._datos

    @Property("QVariantList", notify=graficaChanged)
    def fasesGrafica(self) -> list:
        return self._fases_grafica

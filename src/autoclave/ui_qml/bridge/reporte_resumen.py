# ui_qml/bridge/reporte_resumen.py
#
# Resumen de ciclos por periodo de la pantalla Reportes del Menú Principal:
# consulta de SOLO LECTURA a GET /report/summary?periodo=&fecha= fuera del hilo
# de la GUI, bajo demanda (al abrir la pestaña o mover el periodo), sin sondeo.
# El periodo es de calendario y se recorre con flechas (NavegadorPeriodo), como
# en el Historial. Una respuesta que llega tarde (ya se pidió otro periodo) se
# descarta.

import logging
import threading
from datetime import date

from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave.ui_qml.domain import reporte_resumen as dominio
from autoclave.ui_qml.domain.navegador_periodo import NavegadorPeriodo
from autoclave.utils.periodos import PERIODOS

logger = logging.getLogger(__name__)


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="reporte-resumen").start()


class ReporteResumen(QObject):
    periodoChanged = Signal()
    datosChanged = Signal()
    cargandoChanged = Signal()
    _recibido = Signal(int, object)          # emitida desde el hilo de trabajo

    def __init__(self, backend_client, parent=None, ejecutar=_en_hilo, hoy=date.today):
        super().__init__(parent)
        self._backend = backend_client
        self._ejecutar = ejecutar
        self._navegador = NavegadorPeriodo(hoy)
        self._pedido = 0
        self._cargando = False
        self._sin_conexion = False
        self._datos = dominio.presentable(None)
        self._recibido.connect(self._al_recibir)

    @Slot(str)
    def consultar(self, periodo: str) -> None:
        """Resumen del periodo de calendario actual (al abrir la ventana)."""
        if periodo not in PERIODOS:
            logger.warning("Periodo de reporte desconocido: %r", periodo)
            return
        self._navegador.ir_al_actual(periodo)
        self._pedir()

    @Slot(str)
    def cambiarPeriodo(self, periodo: str) -> None:
        """Filtros Diario / Semanal / Mensual: conserva la fecha que se está viendo."""
        if periodo not in PERIODOS:
            logger.warning("Periodo de reporte desconocido: %r", periodo)
            return
        self._navegador.cambiar(periodo)
        self._pedir()

    @Slot(int)
    def moverPeriodo(self, pasos: int) -> None:
        if self._navegador.mover(pasos):
            self._pedir()

    def _pedir(self) -> None:
        self._pedido += 1
        pedido = self._pedido
        params = {"periodo": self._navegador.periodo, "fecha": self._navegador.fecha.isoformat()}
        self.periodoChanged.emit()
        self._fijar_cargando(True)

        def tarea():
            try:
                respuesta = self._backend.get("/report/summary", params=params)
            except Exception as e:
                logger.debug("resumen del periodo no disponible: %s", e)
                respuesta = None
            self._recibido.emit(pedido, respuesta)

        self._ejecutar(tarea)

    def _al_recibir(self, pedido: int, respuesta) -> None:
        if pedido != self._pedido:
            return   # llegó tarde: ya se pidió otro periodo
        self._fijar_cargando(False)
        self._sin_conexion = not isinstance(respuesta, dict)
        self._datos = dominio.presentable(respuesta)
        self.datosChanged.emit()

    def _fijar_cargando(self, valor: bool) -> None:
        if self._cargando != valor:
            self._cargando = valor
            self.cargandoChanged.emit()

    # ── propiedades para QML (solo lectura) ──────────────────────────────

    @Property(str, notify=periodoChanged)
    def periodo(self) -> str:
        return self._navegador.periodo

    @Property(str, notify=periodoChanged)
    def fecha(self) -> str:
        """Fecha del periodo mostrado (ISO), para imprimirlo o enviarlo."""
        return self._navegador.fecha.isoformat() if self._navegador.fecha else ""

    @Property(str, notify=periodoChanged)
    def rotuloPeriodo(self) -> str:
        return self._navegador.rotulo

    @Property(bool, notify=periodoChanged)
    def esPeriodoActual(self) -> bool:
        return self._navegador.es_actual

    @Property("QVariantMap", notify=datosChanged)
    def datos(self) -> dict:
        """total, totales [{clave, cantidad, porcentaje, fraccion}], por_programa
        [{programa, total, completados, fallos, cancelados, sin_cierre}], causas
        [{causa, cantidad}] (domain/reporte_resumen.py)."""
        return self._datos

    @Property(bool, notify=datosChanged)
    def hayCiclos(self) -> bool:
        return self._datos["total"] != "0"

    @Property(bool, notify=datosChanged)
    def sinConexion(self) -> bool:
        return self._sin_conexion

    @Property(bool, notify=cargandoChanged)
    def cargando(self) -> bool:
        return self._cargando

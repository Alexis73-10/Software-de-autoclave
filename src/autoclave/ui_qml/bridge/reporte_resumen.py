# ui_qml/bridge/reporte_resumen.py
#
# Resumen de ciclos por periodo de la pantalla Reportes del Menú Principal:
# consulta de SOLO LECTURA a GET /report/summary?periodo=&fecha= fuera del hilo
# de la GUI, bajo demanda (al abrir la pestaña o mover el periodo), sin sondeo.
# El periodo es de calendario y se recorre con flechas (NavegadorPeriodo), como
# en el Historial. Una respuesta que llega tarde (ya se pidió otro periodo) se
# descarta.
#
# D8-5.6 (tanda 8): tocar un tipo de fallo del resumen pide los ciclos del
# periodo con ese fallo (GET /report/failures), paginados; cambiar de periodo
# cierra ese listado.

import logging
import threading
from datetime import date

from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave.ui_qml.domain import reporte_resumen as dominio
from autoclave.ui_qml.domain.resumen_sistema import ciclo_presentable
from autoclave.ui_qml.domain.navegador_periodo import NavegadorPeriodo
from autoclave.utils.periodos import PERIODOS

logger = logging.getLogger(__name__)


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="reporte-resumen").start()


class ReporteResumen(QObject):
    periodoChanged = Signal()
    datosChanged = Signal()
    cargandoChanged = Signal()
    falloChanged = Signal()
    _recibido = Signal(int, object)          # emitida desde el hilo de trabajo
    _fallo_recibido = Signal(int, object)

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
        # D8-5.6: ciclos de un tipo de fallo ("" = listado cerrado)
        self._pedido_fallo = 0
        self._causa = ""
        self._ciclos_fallo: list = []
        self._pagina_fallo = 1
        self._paginas_fallo = 1
        self._total_fallo = 0
        self._cargando_fallo = False
        self._sin_conexion_fallo = False
        self._fallo_recibido.connect(self._al_recibir_fallo)

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
        self.cerrarFallo()   # el listado de un fallo es del periodo anterior
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

    # ── D8-5.6: ciclos de un tipo de fallo ───────────────────────────────

    @Slot(str)
    def abrirFallo(self, causa: str) -> None:
        """Ciclos del periodo visto que cerraron con `causa`, primera página."""
        if not causa:
            return
        self._causa = causa
        self._ciclos_fallo = []
        self._pagina_fallo = 1
        self._paginas_fallo = 1
        self._total_fallo = 0
        self._sin_conexion_fallo = False
        self._pedir_fallo(1)

    @Slot(int)
    def moverPaginaFallo(self, pasos: int) -> None:
        pagina = self._pagina_fallo + pasos
        if self._causa and 1 <= pagina <= self._paginas_fallo and pagina != self._pagina_fallo:
            self._pedir_fallo(pagina)

    @Slot()
    def cerrarFallo(self) -> None:
        self._pedido_fallo += 1     # descarta la respuesta que esté en camino
        if self._causa or self._ciclos_fallo or self._cargando_fallo:
            self._causa = ""
            self._ciclos_fallo = []
            self._cargando_fallo = False
            self._sin_conexion_fallo = False
            self.falloChanged.emit()

    def _pedir_fallo(self, pagina: int) -> None:
        self._pedido_fallo += 1
        pedido = self._pedido_fallo
        params = {"periodo": self._navegador.periodo, "fecha": self._navegador.fecha.isoformat(),
                  "causa": self._causa, "pagina": pagina}
        self._cargando_fallo = True
        self.falloChanged.emit()

        def tarea():
            try:
                respuesta = self._backend.get("/report/failures", params=params)
            except Exception as e:
                logger.debug("ciclos del fallo no disponibles: %s", e)
                respuesta = None
            self._fallo_recibido.emit(pedido, respuesta)

        self._ejecutar(tarea)

    def _al_recibir_fallo(self, pedido: int, respuesta) -> None:
        if pedido != self._pedido_fallo:
            return   # llegó tarde: ya se cerró o se pidió otra página
        self._cargando_fallo = False
        r = respuesta if isinstance(respuesta, dict) else None
        self._sin_conexion_fallo = r is None
        if r is not None:
            ciclos = r.get("ciclos") if isinstance(r.get("ciclos"), list) else []
            self._ciclos_fallo = [ciclo_presentable(c) for c in ciclos if isinstance(c, dict)]
            self._pagina_fallo = self._positivo(r.get("pagina"), 1)
            self._paginas_fallo = max(self._pagina_fallo, self._positivo(r.get("paginas"), 1))
            total = r.get("total")
            self._total_fallo = (total if isinstance(total, int) and not isinstance(total, bool)
                                 and total >= 0 else len(self._ciclos_fallo))
        self.falloChanged.emit()

    @staticmethod
    def _positivo(valor, defecto: int) -> int:
        return valor if isinstance(valor, int) and not isinstance(valor, bool) and valor >= 1 else defecto

    @Property(str, notify=falloChanged)
    def causaFallo(self) -> str:
        """Tipo de fallo desplegado ("" = se ve el resumen)."""
        return self._causa

    @Property("QVariantList", notify=falloChanged)
    def ciclosFallo(self) -> list:
        """Filas como las del Historial (resumen_sistema.ciclo_presentable)."""
        return self._ciclos_fallo

    @Property(int, notify=falloChanged)
    def paginaFallo(self) -> int:
        return self._pagina_fallo

    @Property(int, notify=falloChanged)
    def paginasFallo(self) -> int:
        return self._paginas_fallo

    @Property(int, notify=falloChanged)
    def totalFallo(self) -> int:
        return self._total_fallo

    @Property(bool, notify=falloChanged)
    def cargandoFallo(self) -> bool:
        return self._cargando_fallo

    @Property(bool, notify=falloChanged)
    def sinConexionFallo(self) -> bool:
        return self._sin_conexion_fallo

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

# ui_qml/bridge/reporte_dashboard.py
#
# Dashboard de Reportes (planeacion_dashboard_reportes.md §9): consultas de SOLO
# LECTURA a GET /report/dashboard, /report/calendar, /report/day-cycles,
# /maintenance y /maintenance/records, fuera del hilo de la GUI y bajo demanda
# (al abrir la pantalla o mover el periodo, programa o día), sin sondeo. Una
# respuesta que llega tarde (ya se pidió otra cosa) se descarta. Todo el texto y
# la geometría salen de domain/reporte_dashboard.py; QML solo dibuja.
#
# ReporteResumen (bridge/reporte_resumen.py) se conserva mientras otra pantalla
# lo use. Apertura: Mes del mes actual con el programa 01 (DR-D06); el backend
# cae al primero disponible si el 01 no aplica.

import logging
import threading
from datetime import date

from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave import i18n
from autoclave.ui_qml.domain import reporte_dashboard as dominio
from autoclave.ui_qml.domain.navegador_periodo import NavegadorPeriodo
from autoclave.ui_qml.domain.resumen_sistema import lista_presentable
from autoclave.utils.periodos import PERIODOS_REPORTES

logger = logging.getLogger(__name__)

PROGRAMA_INICIAL = 1      # el 01 (DR-D06)
LIMITE_REGISTROS = 500    # /maintenance/records admite hasta 500


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="reporte-dashboard").start()


class ReporteDashboard(QObject):
    periodoChanged = Signal()
    datosChanged = Signal()
    cargandoChanged = Signal()
    programaChanged = Signal()
    diaChanged = Signal()
    _recibido = Signal(int, object)          # emitidas desde el hilo de trabajo
    _dia_recibido = Signal(int, object)

    def __init__(self, backend_client, parent=None, ejecutar=_en_hilo, hoy=date.today,
                 idioma=None, t=None):
        super().__init__(parent)
        self._backend = backend_client
        self._ejecutar = ejecutar
        self._hoy = hoy
        self._idioma = idioma or i18n.idioma
        self._t = t or dominio._t_defecto
        self._navegador = NavegadorPeriodo(hoy)
        self._navegador.ir_al_actual("mes")
        self._programa = PROGRAMA_INICIAL
        self._desde_anio = False        # se llegó a la vista de mes tocando un mes del año
        self._pedido = 0
        self._cargando = False
        self._error = False
        self._crudo: tuple | None = None   # (dashboard, calendario, mantenimiento, registros)
        self._datos = dominio.presentable(None, None, self._idioma(), self._t)
        self._mant = dominio.mantenimiento(None, None, None, None, self._idioma(), self._t)
        # panel del día
        self._pedido_dia = 0
        self._dia = ""
        self._panel_dia: dict = {}
        self._ciclos_dia: list = []
        self._cargando_dia = False
        self._error_dia = False
        self._recibido.connect(self._al_recibir)
        self._dia_recibido.connect(self._al_recibir_dia)

    # ── acciones desde QML ───────────────────────────────────────────────

    @Slot()
    def consultar(self) -> None:
        """Al abrir la pantalla: Mes del mes actual, programa 01, sin día elegido."""
        self._navegador.ir_al_actual("mes")
        self._programa = PROGRAMA_INICIAL
        self._desde_anio = False
        self._dia = ""
        self._pedir()

    @Slot()
    def reintentar(self) -> None:
        self._pedir()

    @Slot(str)
    def cambiarPeriodo(self, periodo: str) -> None:
        """Día / Semana / Mes / Año alrededor de la fecha que se está viendo."""
        if periodo not in PERIODOS_REPORTES:
            logger.warning("Periodo de reporte desconocido: %r", periodo)
            return
        self._navegador.cambiar(periodo)
        self._desde_anio = False
        self._pedir()

    @Slot()
    def anterior(self) -> None:
        self._mover(-1)

    @Slot()
    def siguiente(self) -> None:
        self._mover(1)      # sin efecto en el periodo actual: nunca pasa de hoy

    def _mover(self, pasos: int) -> None:
        if self._navegador.mover(pasos):
            self._desde_anio = False
            self._pedir()

    @Slot(int)
    def elegirPrograma(self, numero: int) -> None:
        if isinstance(numero, int) and numero >= 1 and numero != self._programa:
            self._programa = numero
            self._pedir()

    @Slot(int)
    def elegirMes(self, mes: int) -> None:
        """Vista de Año: abre la vista de mes de ese mes (habilita «Ver año»)."""
        if self._navegador.periodo != "anio" or not 1 <= mes <= 12 or self._navegador.fecha is None:
            return
        destino = date(self._navegador.fecha.year, mes, 1)
        hoy = self._hoy()
        if destino > hoy:
            return
        self._navegador.periodo = "mes"
        self._navegador.fecha = hoy if (destino.year, destino.month) == (hoy.year, hoy.month) else destino
        self._desde_anio = True
        self._pedir()

    @Slot()
    def verAnio(self) -> None:
        self._navegador.cambiar("anio")
        self._desde_anio = False
        self._pedir()

    @Slot(str)
    def elegirDia(self, fecha_iso: str) -> None:
        """Panel del día del programa elegido (GET /report/day-cycles)."""
        try:
            date.fromisoformat(fecha_iso)
        except (TypeError, ValueError):
            return
        self._dia = fecha_iso
        self._pedir_dia()

    @Slot()
    def cerrarDia(self) -> None:
        self._cerrar_dia()
        self.diaChanged.emit()

    @Slot()
    def actualizarIdioma(self) -> None:
        """Re-arma los textos con el idioma vigente sin volver a consultar."""
        if self._crudo is not None:
            self._armar()
            self.datosChanged.emit()

    # ── consulta principal ───────────────────────────────────────────────

    def _cerrar_dia(self) -> None:
        self._pedido_dia += 1          # descarta la respuesta que esté en camino
        self._dia = ""
        self._panel_dia = {}
        self._ciclos_dia = []
        self._cargando_dia = False
        self._error_dia = False

    def _pedir(self) -> None:
        self._cerrar_dia()
        self._pedido += 1
        pedido = self._pedido
        periodo, fecha = self._navegador.periodo, self._navegador.fecha.isoformat()
        base = {"periodo": periodo, "fecha": fecha}
        programa = self._programa
        self._error = False
        self.periodoChanged.emit()
        self.diaChanged.emit()
        self._fijar_cargando(True)

        def tarea():
            try:
                dash = self._backend.get("/report/dashboard", params=dict(base))
                cal = self._backend.get("/report/calendar", params={**base, "programa": programa})
                if not (isinstance(dash, dict) and isinstance(cal, dict)):
                    raise ValueError("respuesta inesperada")
            except Exception as e:
                logger.debug("dashboard de reportes no disponible: %s", e)
                self._recibido.emit(pedido, None)
                return
            mant = self._opcional("/maintenance")
            reg = self._opcional("/maintenance/records", params={"limite": LIMITE_REGISTROS})
            registros = reg.get("registros") if isinstance(reg, dict) and isinstance(reg.get("registros"), list) else None
            self._recibido.emit(pedido, (dash, cal, mant, registros))

        self._ejecutar(tarea)

    def _opcional(self, ruta: str, params=None):
        """Consulta que puede faltar (sin sesión /maintenance/records responde 401/403)."""
        try:
            return self._backend.get(ruta, params=params) if params else self._backend.get(ruta)
        except Exception as e:
            logger.debug("%s no disponible: %s", ruta, e)
            return None

    def _al_recibir(self, pedido: int, crudo) -> None:
        if pedido != self._pedido:
            return   # llegó tarde: ya se pidió otra cosa
        self._fijar_cargando(False)
        self._error = crudo is None
        if crudo is not None:
            self._crudo = crudo
            self._armar()
            prog = self._datos["calendario"].get("programa")
            if isinstance(prog, int) and prog != self._programa:
                self._programa = prog          # el backend resolvió otro (no hay 01)
                self.programaChanged.emit()
        self.datosChanged.emit()
        self.programaChanged.emit()

    def _armar(self) -> None:
        dash, cal, mant, registros = self._crudo
        idioma = self._idioma()
        self._datos = dominio.presentable(dash, cal, idioma, self._t)
        desde = dominio._fecha(dash.get("desde")) if isinstance(dash, dict) else None
        hasta = dominio._fecha(dash.get("hasta")) if isinstance(dash, dict) else None
        self._mant = dominio.mantenimiento(mant, registros, desde, hasta, idioma, self._t)

    def _fijar_cargando(self, valor: bool) -> None:
        if self._cargando != valor:
            self._cargando = valor
            self.cargandoChanged.emit()

    # ── panel del día ────────────────────────────────────────────────────

    def _pedir_dia(self) -> None:
        self._pedido_dia += 1
        pedido = self._pedido_dia
        fecha, programa = self._dia, self._programa
        self._cargando_dia = True
        self._error_dia = False
        self.diaChanged.emit()

        def tarea():
            try:
                r = self._backend.get("/report/day-cycles", params={"programa": programa, "fecha": fecha})
                if not isinstance(r, dict):
                    raise ValueError("respuesta inesperada")
            except Exception as e:
                logger.debug("ciclos del día no disponibles: %s", e)
                self._dia_recibido.emit(pedido, None)
                return
            n_otros = None
            if r.get("estado") == "falto":      # «El equipo realizó N ciclos de otros programas»
                d = self._opcional("/report/dashboard", params={"periodo": "dia", "fecha": fecha})
                if isinstance(d, dict) and isinstance(d.get("indicadores"), dict):
                    n_otros = dominio._entero(d["indicadores"].get("total"))
            self._dia_recibido.emit(pedido, (r, n_otros))

        self._ejecutar(tarea)

    def _al_recibir_dia(self, pedido: int, crudo) -> None:
        if pedido != self._pedido_dia:
            return
        self._cargando_dia = False
        self._error_dia = crudo is None
        if crudo is not None:
            r, n_otros = crudo
            self._panel_dia = dominio.panel_dia(r, self._idioma(), self._t, n_otros)
            ciclos = r.get("ciclos") if isinstance(r.get("ciclos"), list) else []
            self._ciclos_dia = lista_presentable({"ciclos": ciclos})["ciclos"]
        self.diaChanged.emit()

    # ── propiedades para QML (solo lectura) ──────────────────────────────

    @Property(str, notify=periodoChanged)
    def periodo(self) -> str:
        return self._navegador.periodo

    @Property(str, notify=periodoChanged)
    def fecha(self) -> str:
        """Fecha del periodo mostrado (ISO), para imprimirlo o enviarlo."""
        return self._navegador.fecha.isoformat() if self._navegador.fecha else ""

    @Property("QVariantList", constant=True)
    def periodosValidos(self) -> list:
        return list(PERIODOS_REPORTES)

    @Property(bool, notify=periodoChanged)
    def esPeriodoActual(self) -> bool:
        return self._navegador.es_actual

    @Property(bool, notify=periodoChanged)
    def puedeSiguiente(self) -> bool:
        return not self._navegador.es_actual

    @Property(bool, notify=periodoChanged)
    def puedeVerAnio(self) -> bool:
        """Se llegó a este mes desde la vista de Año: mostrar «Ver año»."""
        return self._desde_anio

    @Property(bool, notify=cargandoChanged)
    def cargando(self) -> bool:
        return self._cargando

    @Property(bool, notify=datosChanged)
    def hayError(self) -> bool:
        """La última consulta falló: la pantalla muestra textoError y «Reintentar»."""
        return self._error

    @Property(str, notify=datosChanged)
    def textoError(self) -> str:
        return self._t("reportes.dash_error", self._idioma())

    @Property(str, notify=datosChanged)
    def textoReintentar(self) -> str:
        return self._t("reportes.dash_reintentar", self._idioma())

    @Property("QVariantMap", notify=datosChanged)
    def datos(self) -> dict:
        """presentable(): valido, encabezado, indicadores, dona, serie, programas,
        calendario, causas, alarmas, operadores (domain/reporte_dashboard.py)."""
        return self._datos

    @Property("QVariantMap", notify=datosChanged)
    def mantenimiento(self) -> dict:
        """REP-09 (domain.mantenimiento)."""
        return self._mant

    @Property(bool, notify=datosChanged)
    def hayCiclos(self) -> bool:
        return not self._datos["dona"]["vacia"]

    @Property(int, notify=programaChanged)
    def programa(self) -> int:
        """Número del programa del calendario (el backend resuelve el 01 o el primero)."""
        return self._programa

    @Property(str, notify=diaChanged)
    def diaElegido(self) -> str:
        return self._dia

    @Property("QVariantMap", notify=diaChanged)
    def panelDia(self) -> dict:
        return self._panel_dia

    @Property("QVariantList", notify=diaChanged)
    def ciclosDia(self) -> list:
        """Intentos del día como las filas del Historial (resumen_sistema)."""
        return self._ciclos_dia

    @Property(bool, notify=diaChanged)
    def cargandoDia(self) -> bool:
        return self._cargando_dia

    @Property(bool, notify=diaChanged)
    def errorDia(self) -> bool:
        return self._error_dia

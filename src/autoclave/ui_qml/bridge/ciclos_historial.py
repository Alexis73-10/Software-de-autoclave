# ui_qml/bridge/ciclos_historial.py
#
# Listado de ciclos para las ventanas de Ciclos hoy e Historial del Menú
# Principal (planeacion_menu_principal_ui_qml.md): consulta de SOLO LECTURA a
#   GET /cycle/list?periodo=dia|semana|mes&terminados=...[&fecha=...]  -> filas del listado
#   GET /cycle/history/{id}/graph                                     -> curva del ciclo elegido
# fuera del hilo de la GUI (patrón de InfoEquipo / ResumenSistema). Se consulta
# bajo demanda (al abrir la ventana o cambiar de periodo), sin sondeo.
#
# Historial: el periodo es de calendario (utils/periodos.py) y se recorre con las
# flechas (moverPeriodo), sin pasar del actual. También guarda los ciclos marcados
# para imprimir o enviar por correo; se desmarcan al pedir otro listado.
#
# Si se pide otro periodo u otro ciclo antes de que llegue la respuesta anterior,
# la respuesta vieja se descarta (cada pedido lleva su número).

import logging
import threading
from datetime import date

from PySide6.QtCore import Property, QObject, Signal, Slot

from autoclave.core.runtime.progreso_ciclo import FASES_UI
from autoclave.ui_qml.domain import resumen_sistema as dominio
from autoclave.ui_qml.domain.ciclo_en_curso import AcumuladorGrafica
from autoclave.ui_qml.domain.navegador_periodo import NavegadorPeriodo

logger = logging.getLogger(__name__)

PERIODOS = ("dia", "semana", "mes")
_GRAFICA_VACIA = {"t_min": [], "temp_camara": [], "temp_ref": [], "pres_camara": []}


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="ciclos-historial").start()


class CiclosHistorial(QObject):
    ciclosChanged = Signal()
    sinConexionChanged = Signal()
    cargandoChanged = Signal()
    graficaChanged = Signal()
    periodoChanged = Signal()
    seleccionChanged = Signal()
    _lista_recibida = Signal(int, str, object)     # emitidas desde el hilo de trabajo
    _grafica_recibida = Signal(int, object)

    def __init__(self, backend_client, parent=None, ejecutar=_en_hilo, hoy=date.today):
        super().__init__(parent)
        self._backend = backend_client
        self._ejecutar = ejecutar
        self._navegador = NavegadorPeriodo(hoy)   # periodo del Historial
        self._seleccionados: list = []
        self._pedido_lista = 0
        self._periodo = ""
        self._ciclos: list = []
        self._truncado = False
        self._sin_conexion = False
        self._cargando = False
        self._pedido_grafica = 0
        self._grafica_disponible = False
        self._datos_grafica = dict(_GRAFICA_VACIA)
        self._fases_grafica: list = []
        self._lista_recibida.connect(self._al_recibir_lista)
        self._grafica_recibida.connect(self._al_recibir_grafica)

    # ── listado ──────────────────────────────────────────────────────────

    @Slot(str, bool)
    def consultar(self, periodo: str, terminados: bool) -> None:
        """Ciclos del periodo actual. terminados=True: los que cuenta "Ciclos hoy"
        (terminados desde las 00:00); False: por fecha de inicio."""
        if periodo not in PERIODOS:
            logger.warning("Periodo de historial desconocido: %r", periodo)
            return
        self._pedir_lista(periodo, {"periodo": periodo, "terminados": "true" if terminados else "false"})

    @Slot(str)
    def consultarHistorial(self, periodo: str) -> None:
        """Historial al abrirse: ciclos del periodo de calendario actual, por fecha de inicio."""
        if periodo not in PERIODOS:
            logger.warning("Periodo de historial desconocido: %r", periodo)
            return
        self._navegador.ir_al_actual(periodo)
        self._pedir_periodo()

    @Slot(str)
    def cambiarPeriodo(self, periodo: str) -> None:
        """Filtros Diario / Semanal / Mensual: conserva la fecha que se está viendo."""
        if periodo not in PERIODOS:
            logger.warning("Periodo de historial desconocido: %r", periodo)
            return
        self._navegador.cambiar(periodo)
        self._pedir_periodo()

    @Slot(int)
    def moverPeriodo(self, pasos: int) -> None:
        """Flechas del Historial: `pasos` periodos antes (negativo) o después, sin
        pasar del actual."""
        if self._navegador.mover(pasos):
            self._pedir_periodo()

    def _pedir_periodo(self) -> None:
        n = self._navegador
        self.periodoChanged.emit()
        self._pedir_lista(n.periodo, {"periodo": n.periodo, "terminados": "false",
                                      "fecha": n.fecha.isoformat()})

    def _pedir_lista(self, periodo: str, params: dict) -> None:
        self._pedido_lista += 1
        pedido = self._pedido_lista
        self._fijar_cargando(True)
        self._fijar_seleccion([])

        def tarea():
            try:
                respuesta = self._backend.get("/cycle/list", params=params)
            except Exception as e:
                logger.debug("listado de ciclos no disponible: %s", e)
                respuesta = None
            self._lista_recibida.emit(pedido, periodo, respuesta)

        self._ejecutar(tarea)

    def _al_recibir_lista(self, pedido: int, periodo: str, respuesta) -> None:
        if pedido != self._pedido_lista:
            return   # llegó tarde: ya se pidió otro periodo
        self._fijar_cargando(False)
        valida = isinstance(respuesta, dict)
        if self._sin_conexion == valida:
            self._sin_conexion = not valida
            self.sinConexionChanged.emit()
        lista = dominio.lista_presentable(respuesta if valida else None)
        self._periodo = periodo
        self._ciclos = lista["ciclos"]
        self._truncado = lista["truncado"]
        self.ciclosChanged.emit()

    def _fijar_cargando(self, valor: bool) -> None:
        if self._cargando != valor:
            self._cargando = valor
            self.cargandoChanged.emit()

    # ── ciclos marcados (imprimir / enviar) ──────────────────────────────

    def _ids_listado(self) -> list:
        return [c["id"] for c in self._ciclos]

    def _fijar_seleccion(self, ids: list) -> None:
        if ids != self._seleccionados:
            self._seleccionados = ids
            self.seleccionChanged.emit()

    @Slot(int)
    def alternarSeleccion(self, ciclo_id: int) -> None:
        if ciclo_id in self._seleccionados:
            self._fijar_seleccion([i for i in self._seleccionados if i != ciclo_id])
        elif ciclo_id in self._ids_listado():
            self._fijar_seleccion(self._seleccionados + [ciclo_id])

    @Slot(bool)
    def seleccionarTodos(self, marcar: bool) -> None:
        self._fijar_seleccion(self._ids_listado() if marcar else [])

    # ── curva del ciclo elegido ──────────────────────────────────────────

    @Slot(int)
    def cargarGrafica(self, ciclo_id: int) -> None:
        self.limpiarGrafica()
        if ciclo_id < 0:
            return
        pedido = self._pedido_grafica

        def tarea():
            try:
                grafica = self._backend.get(f"/cycle/history/{ciclo_id}/graph")
            except Exception as e:
                logger.debug("curva del ciclo %s no disponible: %s", ciclo_id, e)
                grafica = None
            self._grafica_recibida.emit(pedido, grafica)

        self._ejecutar(tarea)

    @Slot()
    def limpiarGrafica(self) -> None:
        """Al volver a la lista: descarta la curva mostrada y la que esté en camino."""
        self._pedido_grafica += 1
        if self._grafica_disponible or self._datos_grafica["t_min"]:
            self._grafica_disponible = False
            self._datos_grafica = dict(_GRAFICA_VACIA)
            self._fases_grafica = []
            self.graficaChanged.emit()

    def _al_recibir_grafica(self, pedido: int, grafica) -> None:
        if pedido != self._pedido_grafica:
            return   # el ciclo ya no está elegido
        acumulador = AcumuladorGrafica()
        acumulador.incorporar(grafica)
        self._datos_grafica = acumulador.datos()
        self._fases_grafica = acumulador.inicios_de_fase(FASES_UI)
        self._grafica_disponible = len(self._datos_grafica["t_min"]) > 0
        self.graficaChanged.emit()

    # ── propiedades para QML (solo lectura) ──────────────────────────────

    @Property("QVariantList", notify=ciclosChanged)
    def ciclos(self) -> list:
        """Filas: id, numero, fecha, hora, programa, programa_nombre, resultado
        (COMPLETADO / CANCELADO / FALLO o ""), resultado_detalle, operador y
        no_conforme (P4, tanda 16)."""
        return self._ciclos

    @Property(bool, notify=ciclosChanged)
    def truncado(self) -> bool:
        return self._truncado

    @Property(str, notify=ciclosChanged)
    def periodo(self) -> str:
        return self._periodo

    @Property(str, notify=periodoChanged)
    def rotuloPeriodo(self) -> str:
        """Periodo del Historial entre las flechas ("Octubre 2026")."""
        return self._navegador.rotulo

    @Property(bool, notify=periodoChanged)
    def esPeriodoActual(self) -> bool:
        """La flecha siguiente se apaga en el periodo actual."""
        return self._navegador.es_actual

    @Property("QVariantList", notify=seleccionChanged)
    def seleccionados(self) -> list:
        """ids de los ciclos marcados, en el orden en que se marcaron."""
        return self._seleccionados

    @Property(bool, notify=seleccionChanged)
    def todosSeleccionados(self) -> bool:
        return bool(self._ciclos) and len(self._seleccionados) == len(self._ciclos)

    @Property(bool, notify=sinConexionChanged)
    def sinConexion(self) -> bool:
        return self._sin_conexion

    @Property(bool, notify=cargandoChanged)
    def cargando(self) -> bool:
        return self._cargando

    @Property(bool, notify=graficaChanged)
    def graficaDisponible(self) -> bool:
        return self._grafica_disponible

    @Property("QVariantMap", notify=graficaChanged)
    def datosGrafica(self) -> dict:
        return self._datos_grafica

    @Property("QVariantList", notify=graficaChanged)
    def fasesGrafica(self) -> list:
        return self._fases_grafica

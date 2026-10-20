# ui_qml/bridge/resumen_sistema.py
#
# Resumen del Sistema del Menú Principal (planeacion_menu_principal_ui_qml.md
# §6.3 y §6.5): consulta de SOLO LECTURA a GET /cycle/summary, fuera del hilo
# de la GUI (patrón de InfoEquipo), al activarse la pantalla (iniciar) y luego
# cada 10 s. Expone a QML los textos ya formateados (domain/resumen_sistema.py).
#
# Sin respuesta del backend (D-16): sinConexion = True y los datos pasan a "—";
# la última respuesta buena se conserva internamente y vuelve a mostrarse en
# cuanto el backend responde. Antes de la primera respuesta no se avisa.
#
# Curva del último ciclo (ventana flotante, D-21): bajo demanda con
# cargarGraficaUltimo() -> GET /cycle/history/{id}/graph, no en el sondeo de
# 10 s. Mismo formato que la gráfica del ciclo en curso (AcumuladorGrafica).

import logging
import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from autoclave.core.runtime.progreso_ciclo import FASES_UI
from autoclave.ui_qml.domain import resumen_sistema as dominio
from autoclave.ui_qml.domain.ciclo_en_curso import AcumuladorGrafica

logger = logging.getLogger(__name__)

INTERVALO_MS = 10_000   # provisional (§6.5); ajustable


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="resumen-sistema").start()


class ResumenSistema(QObject):
    datosChanged = Signal()
    sinConexionChanged = Signal()
    sondeandoChanged = Signal()
    graficaUltimoChanged = Signal()
    _respuesta_recibida = Signal(object)   # emitida desde el hilo de trabajo
    _grafica_recibida = Signal(object)     # emitida desde el hilo de trabajo

    def __init__(self, backend_client, parent=None, ejecutar=_en_hilo,
                 intervalo_ms: int = INTERVALO_MS):
        super().__init__(parent)
        self._backend = backend_client
        self._ejecutar = ejecutar
        self._consultando = False
        self._ultima = None          # última respuesta válida (estado interno)
        self._sin_conexion = False
        self._datos = dominio.resumen_presentable(None)
        self._respuesta_recibida.connect(self._al_recibir)

        self._cargando_grafica = False
        self._grafica_disponible = False
        self._grafica = AcumuladorGrafica()
        self._datos_grafica = self._grafica.datos()
        self._fases_grafica: list = []
        self._grafica_recibida.connect(self._al_recibir_grafica)

        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self.consultar)

    # ── consulta ─────────────────────────────────────────────────────────

    @Slot()
    def iniciar(self) -> None:
        """Al activarse la pantalla: consulta ya y arma el sondeo."""
        self.consultar()
        if not self._timer.isActive():
            self._timer.start()
            self.sondeandoChanged.emit()

    @Slot()
    def detener(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self.sondeandoChanged.emit()

    @Slot()
    def consultar(self) -> None:
        if self._consultando:
            return
        self._consultando = True

        def tarea():
            try:
                respuesta = self._backend.get("/cycle/summary")
            except Exception as e:
                logger.debug("resumen del sistema no disponible: %s", e)
                respuesta = None
            self._respuesta_recibida.emit(respuesta)

        self._ejecutar(tarea)

    def _al_recibir(self, respuesta) -> None:
        self._consultando = False
        valida = isinstance(respuesta, dict)
        if valida:
            self._ultima = respuesta
        if self._sin_conexion == valida:
            self._sin_conexion = not valida
            self.sinConexionChanged.emit()
        datos = dominio.resumen_presentable(self._ultima if valida else None)
        if datos != self._datos:
            self._datos = datos
            self.datosChanged.emit()

    @Slot()
    def cargarGraficaUltimo(self) -> None:
        """Pide la curva del último ciclo conocido (al abrir su ventana flotante)."""
        ciclo_id = dominio.id_ultimo_ciclo(self._ultima)
        if ciclo_id is None or self._cargando_grafica:
            return
        self._cargando_grafica = True

        def tarea():
            try:
                grafica = self._backend.get(f"/cycle/history/{ciclo_id}/graph")
            except Exception as e:
                logger.debug("curva del último ciclo no disponible: %s", e)
                grafica = None
            self._grafica_recibida.emit(grafica)

        self._ejecutar(tarea)

    def _al_recibir_grafica(self, grafica) -> None:
        self._cargando_grafica = False
        acumulador = AcumuladorGrafica()   # cada carga es la serie completa
        acumulador.incorporar(grafica)
        datos = acumulador.datos()
        disponible = len(datos["t_min"]) > 0
        fases = acumulador.inicios_de_fase(FASES_UI)
        if (disponible, datos, fases) != (self._grafica_disponible, self._datos_grafica,
                                          self._fases_grafica):
            self._grafica = acumulador
            self._grafica_disponible = disponible
            self._datos_grafica = datos
            self._fases_grafica = fases
            self.graficaUltimoChanged.emit()

    # ── propiedades para QML (solo lectura) ──────────────────────────────

    @Property(bool, notify=sinConexionChanged)
    def sinConexion(self) -> bool:
        return self._sin_conexion

    @Property(bool, notify=sondeandoChanged)
    def sondeando(self) -> bool:
        return self._timer.isActive()

    @Property(int, constant=True)
    def intervaloMs(self) -> int:
        return self._timer.interval()

    @Property(str, notify=datosChanged)
    def ciclosTotales(self) -> str:
        return self._datos["ciclos_totales"]

    @Property(str, notify=datosChanged)
    def ciclosHoy(self) -> str:
        return self._datos["ciclos_hoy"]

    @Property(str, notify=datosChanged)
    def ultimoFecha(self) -> str:
        return self._datos["ultimo_fecha"]

    @Property(str, notify=datosChanged)
    def ultimoHora(self) -> str:
        return self._datos["ultimo_hora"]

    @Property(str, notify=datosChanged)
    def ultimoPrograma(self) -> str:
        return self._datos["ultimo_programa"]

    @Property(str, notify=datosChanged)
    def ultimoProgramaNombre(self) -> str:
        return self._datos["ultimo_programa_nombre"]

    @Property(str, notify=datosChanged)
    def ultimoResultado(self) -> str:
        """Clave COMPLETADO / FALLO / CANCELADO, o "" (la pantalla muestra "—")."""
        return self._datos["ultimo_resultado"]

    @Property(str, notify=datosChanged)
    def ultimoResultadoDetalle(self) -> str:
        """Cierre tal como se guardó (p. ej. FALLO_CALENTAMIENTO), o "" si no dice más que la clave."""
        return self._datos["ultimo_resultado_detalle"]

    @Property(str, notify=datosChanged)
    def ultimoOperador(self) -> str:
        """Quién envió el ciclo; "—" mientras no se guarde (Paso 1 b del informe de Fase 2)."""
        return self._datos["ultimo_operador"]

    @Property(bool, notify=graficaUltimoChanged)
    def graficaUltimoDisponible(self) -> bool:
        return self._grafica_disponible

    @Property("QVariantMap", notify=graficaUltimoChanged)
    def datosGraficaUltimo(self) -> dict:
        """Arreglos paralelos para GraficaCiclo.qml: t_min, temp_camara, temp_ref, pres_camara."""
        return self._datos_grafica

    @Property("QVariantList", notify=graficaUltimoChanged)
    def fasesGraficaUltimo(self) -> list:
        return self._fases_grafica

    @Property(str, constant=True)
    def proximoMantenimiento(self) -> str:
        # MP-06b / B-03: no existe fuente de mantenimiento en el sistema
        return dominio.SIN_DATO


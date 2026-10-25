# ui_qml/bridge/comandos_sistema.py
#
# Comandos de seguridad del sistema para QML (E5, tanda 2026-10-14):
# - "Confirmar y llevar a estado seguro" (fin de ciclo §15.2): POST
#   /safe-state/confirm, cualquier operador, sin rol.
# - "Apagar equipo" (fin de ciclo §16, D-20): POST /system/shutdown, solo
#   desde la ventana principal (puerta 1). Se permite en cualquier estado salvo
#   ciclo en curso (A1, tanda 3), también con la cámara NO segura: `camaraNoSegura`
#   deja a la pantalla avisar antes de confirmar. El backend vuelve a validar
#   estado y ventana; si lo rechaza, `mensaje` lleva el motivo.
# Las peticiones corren fuera del hilo de la GUI.

import logging
import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from autoclave.cliente.ui_service_backend import APAGADO_INCIERTO

logger = logging.getLogger(__name__)

VENTANA_PRINCIPAL = 1
# D8-3.21: tras un apagado aceptado se consulta si Windows lo rechazó
PERIODO_VIGILANCIA_APAGADO_MS = 2000

# D8-2.15 (tanda 8): motivos de rechazo de DESPEJAR (claves del catálogo i18n)
MOTIVOS_DESPEJAR = frozenset({
    "notificaciones.despejar_sin_enlace",
    "notificaciones.despejar_no_activa",
    "notificaciones.despejar_rechazado",
    "notificaciones.despejar_sin_respuesta",
    "notificaciones.despejar_sin_confirmacion",
})


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="comandos-sistema").start()


class ComandosSistema(QObject):
    ocupadoChanged = Signal()
    mensajeChanged = Signal()
    mensajeDespejarChanged = Signal()
    camaraNoSeguraChanged = Signal()
    apagadoRechazadoChanged = Signal()
    # S4 (CIC-10): el aviso pide abrir la asignación de sondas (OPCIONES)
    asignarSondaSolicitada = Signal()
    _terminado = Signal(str, bool, str)   # (petición, ok, motivo); desde el hilo de trabajo
    _estadoApagadoLeido = Signal(object)   # emitida desde el hilo de trabajo

    def __init__(self, puente, ui_service, door: int, parent=None, ejecutar=_en_hilo):
        super().__init__(parent)
        self._puente = puente
        self._ui = ui_service
        self._door = int(door)
        self._ejecutar = ejecutar
        self._ocupado = False
        self._mensaje = ""
        self._mensaje_despejar = ""   # D8-2.15: clave del catálogo del rechazo de DESPEJAR
        self._apagando = False   # la petición en curso es la de apagar
        self._terminado.connect(self._al_terminar)
        # D8-3.21: Windows rechazó el apagado ("apáguelo manualmente")
        self._apagado_rechazado = False
        self._consultando_apagado = False
        self._vigilancia_apagado = QTimer(self)
        self._vigilancia_apagado.setInterval(PERIODO_VIGILANCIA_APAGADO_MS)
        self._vigilancia_apagado.timeout.connect(self._consultarApagado)
        self._estadoApagadoLeido.connect(self._al_leer_estado_apagado)
        # el aviso de "NO ABRIR" sigue a la bandera del puente
        self._puente.seguridadChanged.connect(self.camaraNoSeguraChanged)

    @Property(bool, constant=True)
    def ventanaPrincipal(self) -> bool:
        return self._door == VENTANA_PRINCIPAL

    @Property(bool, notify=camaraNoSeguraChanged)
    def camaraNoSegura(self) -> bool:
        """Falla cerrada: sin dato del puente cuenta como NO segura."""
        return getattr(self._puente, "noAbrir", True) is not False

    @Property(bool, notify=apagadoRechazadoChanged)
    def apagadoRechazado(self) -> bool:
        return self._apagado_rechazado

    @Property(bool, notify=ocupadoChanged)
    def ocupado(self) -> bool:
        return self._ocupado

    @Property(str, notify=mensajeChanged)
    def mensaje(self) -> str:
        return self._mensaje

    def _lanzar(self, nombre, llamada) -> None:
        if self._ocupado or not self._puente.connected:
            return
        self._fijar_ocupado(True)
        if nombre == "despejar_alarma":
            self._fijar_mensaje_despejar("")
        else:
            self._fijar_mensaje("")

        def tarea():
            try:
                resultado = llamada()
                ok, motivo = resultado if isinstance(resultado, tuple) else (bool(resultado), "")
            except Exception as e:
                logger.warning("%s error: %s", nombre, e)
                ok, motivo = False, str(e)
            try:
                self._terminado.emit(nombre, ok, motivo)
            except RuntimeError:
                pass   # la ventana se cerró con la petición en curso

        self._ejecutar(tarea)

    @Slot()
    def confirmarEstadoSeguro(self) -> None:
        if not self._puente.estadoSeguroRequiereConfirmacion:
            return
        self._lanzar("confirmar_estado_seguro", self._ui.confirmar_estado_seguro)

    @Slot(str)
    def despejarAlarma(self, clave: str) -> None:
        """P-5 (tanda 6): despeje manual de COM-02/COM-03 (reconocimiento
        explícito, cualquier operador). Fuera de CICLO el backend la resuelve;
        en CICLO solo queda reconocida."""
        if not clave:
            return
        self._lanzar("despejar_alarma", lambda: self._ui.reconocer_alarma(clave, "operador"))

    @Slot()
    def asignarSondaPrincipal(self) -> None:
        """Opción B de CIC-10: la pantalla abre OPCIONES (con su login: solo
        técnico o ingeniero llegan a la asignación de roles). No cambia nada
        por sí mismo: el backend verifica la lectura de la sonda elegida."""
        self.asignarSondaSolicitada.emit()

    @Slot()
    def apagarEquipo(self) -> None:
        if not self.ventanaPrincipal or self._ocupado or not self._puente.connected:
            return
        self._apagando = True
        self._lanzar("apagar_equipo", lambda: self._ui.apagar_equipo("principal"))

    def _al_terminar(self, nombre: str, ok: bool, motivo: str) -> None:
        # TMG-06 de T7: un apagado aceptado deja el botón deshabilitado
        apagado = self._apagando and ok
        # TMG-02 (revisión final de E1): sin respuesta el backend pudo
        # aceptarlo; se vigila igual (solo un rechazo explícito se muestra)
        incierto = self._apagando and not ok and motivo == APAGADO_INCIERTO
        self._apagando = False
        if apagado or incierto:
            self._vigilancia_apagado.start()   # D8-3.21
        if not apagado:
            self._fijar_ocupado(False)
        if nombre == "despejar_alarma":
            # D8-2.15 (tanda 8): el rechazo de DESPEJAR va con su propio texto
            # del catálogo al panel de notificaciones (no al de apagar); un
            # motivo que no sea una clave conocida sale como el genérico
            if ok:
                self._fijar_mensaje_despejar("")
            else:
                self._fijar_mensaje_despejar(motivo if motivo in MOTIVOS_DESPEJAR
                                             else "notificaciones.despejar_rechazado")
            return
        if not ok:
            self._fijar_mensaje(motivo)

    @Slot()
    def descartarMensajeDespejar(self) -> None:
        self._fijar_mensaje_despejar("")

    @Property(str, notify=mensajeDespejarChanged)
    def mensajeDespejar(self) -> str:
        """D8-2.15: "" o la clave del catálogo del último rechazo de DESPEJAR."""
        return self._mensaje_despejar

    def _fijar_mensaje_despejar(self, valor: str) -> None:
        if self._mensaje_despejar != valor:
            self._mensaje_despejar = valor
            self.mensajeDespejarChanged.emit()

    @Slot()
    def _consultarApagado(self) -> None:
        """D8-3.21: pregunta al backend (fuera del hilo de la GUI) si Windows
        rechazó el apagado. Solo un `True` explícito lo da por rechazado."""
        if self._consultando_apagado:
            return
        self._consultando_apagado = True

        def tarea():
            try:
                estado = self._ui.estado_apagado()
            except Exception as e:
                logger.debug("estado_apagado error: %s", e)
                estado = None
            try:
                self._estadoApagadoLeido.emit(estado)
            except RuntimeError:
                pass

        self._ejecutar(tarea)

    def _al_leer_estado_apagado(self, estado) -> None:
        self._consultando_apagado = False
        if not isinstance(estado, dict) or estado.get("windows_rechazado") is not True:
            return
        self._vigilancia_apagado.stop()
        if not self._apagado_rechazado:
            self._apagado_rechazado = True
            self.apagadoRechazadoChanged.emit()

    def _fijar_ocupado(self, valor: bool) -> None:
        if self._ocupado != valor:
            self._ocupado = valor
            self.ocupadoChanged.emit()

    def _fijar_mensaje(self, valor: str) -> None:
        if self._mensaje != valor:
            self._mensaje = valor
            self.mensajeChanged.emit()

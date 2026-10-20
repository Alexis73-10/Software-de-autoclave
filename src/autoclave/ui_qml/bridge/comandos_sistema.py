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

from PySide6.QtCore import Property, QObject, Signal, Slot

logger = logging.getLogger(__name__)

VENTANA_PRINCIPAL = 1


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="comandos-sistema").start()


class ComandosSistema(QObject):
    ocupadoChanged = Signal()
    mensajeChanged = Signal()
    camaraNoSeguraChanged = Signal()
    # S4 (CIC-10): el aviso pide abrir la asignación de sondas (OPCIONES)
    asignarSondaSolicitada = Signal()
    _terminado = Signal(bool, str)   # emitida desde el hilo de trabajo

    def __init__(self, puente, ui_service, door: int, parent=None, ejecutar=_en_hilo):
        super().__init__(parent)
        self._puente = puente
        self._ui = ui_service
        self._door = int(door)
        self._ejecutar = ejecutar
        self._ocupado = False
        self._mensaje = ""
        self._apagando = False   # la petición en curso es la de apagar
        self._terminado.connect(self._al_terminar)
        # el aviso de "NO ABRIR" sigue a la bandera del puente
        self._puente.seguridadChanged.connect(self.camaraNoSeguraChanged)

    @Property(bool, constant=True)
    def ventanaPrincipal(self) -> bool:
        return self._door == VENTANA_PRINCIPAL

    @Property(bool, notify=camaraNoSeguraChanged)
    def camaraNoSegura(self) -> bool:
        """Falla cerrada: sin dato del puente cuenta como NO segura."""
        return getattr(self._puente, "noAbrir", True) is not False

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
        self._fijar_mensaje("")

        def tarea():
            try:
                resultado = llamada()
                ok, motivo = resultado if isinstance(resultado, tuple) else (bool(resultado), "")
            except Exception as e:
                logger.warning("%s error: %s", nombre, e)
                ok, motivo = False, str(e)
            try:
                self._terminado.emit(ok, motivo)
            except RuntimeError:
                pass   # la ventana se cerró con la petición en curso

        self._ejecutar(tarea)

    @Slot()
    def confirmarEstadoSeguro(self) -> None:
        if not self._puente.estadoSeguroRequiereConfirmacion:
            return
        self._lanzar("confirmar_estado_seguro", self._ui.confirmar_estado_seguro)

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

    def _al_terminar(self, ok: bool, motivo: str) -> None:
        # TMG-06 de T7: un apagado aceptado deja el botón deshabilitado
        apagado = self._apagando and ok
        self._apagando = False
        if not apagado:
            self._fijar_ocupado(False)
        if not ok:
            self._fijar_mensaje(motivo)

    def _fijar_ocupado(self, valor: bool) -> None:
        if self._ocupado != valor:
            self._ocupado = valor
            self.ocupadoChanged.emit()

    def _fijar_mensaje(self, valor: str) -> None:
        if self._mensaje != valor:
            self._mensaje = valor
            self.mensajeChanged.emit()

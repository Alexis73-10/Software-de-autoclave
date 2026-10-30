# ui_qml/bridge/standby.py
#
# Standby simultáneo de las dos pantallas QML: tras `tiempo_standby` minutos
# (parámetro global) sin actividad en NINGUNA de las dos, ambas vuelven a la
# pantalla de arranque a la vez; un toque en cualquiera de ellas las devuelve a
# ambas a la pantalla principal. Es la única transición simultánea.
#
# Referencia común: el backend (POST /ui/activity, "ui_inactividad_s" en
# GET /status), porque las pantallas pueden ser procesos o PCs distintos.
# Cada UI decide sola con el mismo dato, así que cambian juntas (con la
# latencia del sondeo, < 1 s).
#
# Reglas (decisiones de seguridad/usabilidad, no del mockup):
#   - nunca en standby durante CICLO, FALLA o EMERGENCIA, ni con el paro
#     real activo (U4: no el módulo E/S sin datos) o el estado seguro en curso o pendiente de confirmar (U1 de la
#     tanda 2: esos avisos ya no se dibujan sobre todas las pantallas, sino en
#     el panel de la campana, que la pantalla de arranque taparía);
#   - un cambio de estado del equipo o una alarma nueva cuenta como actividad
#     (despierta ambas pantallas y reinicia el conteo), para que no pasen
#     inadvertidos detrás de la pantalla de arranque;
#   - sin conexión con el backend, cada pantalla usa solo su inactividad local;
#   - con el menú de configuración PySide abierto se considera actividad;
#   - al abrir, la UI arranca siempre en la pantalla de arranque: no cuenta la
#     actividad que el backend registró antes de que esta UI arrancara (backend
#     que ya corría), ni los cambios de estado/alarmas de los primeros
#     GRACIA_ARRANQUE_S segundos desde que el backend responde (transiciones
#     propias del encendido).
# Tiempos con time.monotonic() (CLAUDE.md: timers de proceso nunca con time.time()).

import logging
import threading
import time

from PySide6.QtCore import QEvent, Property, QObject, QTimer, Signal, Slot

logger = logging.getLogger(__name__)

MINUTOS_DEFECTO = 10      # O2a: defecto de planeacion_opciones.md v4 §3.2
GRACIA_ARRANQUE_S = 10.0
ESTADOS_SIN_STANDBY = {"CICLO", "FALLA"}   # P-8 (tanda 6): EMERGENCIA retirado
_EVENTOS_ACTIVIDAD = {
    QEvent.Type.MouseButtonPress, QEvent.Type.TouchBegin, QEvent.Type.KeyPress,
}


def minutos_standby(valor) -> float:
    """tiempo_standby de los parámetros globales; defecto si falta o es
    inválido. 0 = suspensión desactivada (O2a: antes se convertía en 5)."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor != valor or valor < 0:
        return MINUTOS_DEFECTO
    return float(valor)


def debe_estar_en_standby(conectado: bool, inactividad_backend, inactividad_local,
                          minutos: float, estado, seguridad_pendiente: bool = False) -> bool:
    """inactividad_* en segundos; None = sin actividad registrada (infinita).
    seguridad_pendiente: paro activo o estado seguro activo/por confirmar."""
    if minutos <= 0:                     # 0 = suspensión desactivada
        return False
    if conectado and (estado in ESTADOS_SIN_STANDBY or seguridad_pendiente):
        return False
    infinito = float("inf")
    candidatos = [infinito if inactividad_local is None else inactividad_local]
    if conectado:
        candidatos.append(infinito if inactividad_backend is None else inactividad_backend)
    return min(candidatos) >= minutos * 60


def _en_hilo(tarea) -> None:
    threading.Thread(target=tarea, daemon=True, name="actividad-ui").start()


class Standby(QObject):
    activoChanged = Signal()

    def __init__(self, ui_service, backend_client, parent=None, reloj=time.monotonic,
                 ejecutar=_en_hilo, intervalo_ms: int = 500, iniciar: bool = True,
                 envio_min_s: float = 1.0, mantener_despierto=None,
                 gracia_arranque_s: float = GRACIA_ARRANQUE_S,
                 registrar_suspension: bool = False):
        super().__init__(parent)
        self._registrar_suspension = registrar_suspension   # O2e: bitácora en el backend
        self._ui = ui_service
        self._backend = backend_client
        self._reloj = reloj
        self._ejecutar = ejecutar
        self._envio_min_s = envio_min_s
        self._mantener_despierto = mantener_despierto or (lambda: False)
        self._inicio = reloj()
        self._gracia_arranque_s = gracia_arranque_s
        # Primer instante (monotonic) con respuesta del backend: la gracia del
        # arranque cuenta desde ahí (backend más lento que la UI, 19-oct)
        self._inicio_conectado = None

        self._activo = True           # la app arranca en la pantalla de arranque
        self._ultima_local = None     # último toque en ESTA pantalla
        self._ultimo_envio = None
        self._estado_previo = None    # para detectar cambios de estado / alarmas nuevas
        self._alarmas_previas = None
        self._seguridad_previa = False

        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self.evaluar)
        if iniciar:
            self._timer.start()

    def detener(self) -> None:
        self._timer.stop()

    # ── actividad ────────────────────────────────────────────────────────

    @Slot()
    def registrarActividad(self) -> None:
        """Toque o tecla en esta pantalla."""
        forzar = self._activo   # despertando: avisar ya a la otra pantalla
        self._marcar_actividad(forzar)
        self.evaluar()

    def _marcar_actividad(self, forzar: bool) -> None:
        ahora = self._reloj()
        self._ultima_local = ahora
        if forzar or self._ultimo_envio is None or ahora - self._ultimo_envio >= self._envio_min_s:
            self._ultimo_envio = ahora

            def tarea():
                try:
                    self._backend.post("/ui/activity")
                except Exception as e:   # sin backend: queda la inactividad local
                    logger.debug("POST /ui/activity falló: %s", e)

            self._ejecutar(tarea)

    def eventFilter(self, obj, evento) -> bool:
        if evento.type() in _EVENTOS_ACTIVIDAD:
            self.registrarActividad()
        return False   # nunca consume el evento

    # ── decisión ─────────────────────────────────────────────────────────

    @Slot()
    def evaluar(self) -> None:
        conectado = bool(self._ui.connected)
        estado = None
        seguridad = False
        if conectado:
            if self._inicio_conectado is None:
                self._inicio_conectado = self._reloj()
            estado = self._ui.get_estado_global()
            seguridad = self._seguridad_pendiente()
            if self._hubo_evento_de_equipo(estado, seguridad) and not self._en_gracia_arranque():
                self._marcar_actividad(forzar=True)
        if self._mantener_despierto():
            self._marcar_actividad(forzar=False)

        local = None if self._ultima_local is None else self._reloj() - self._ultima_local
        activo = debe_estar_en_standby(
            conectado,
            self._inactividad_backend() if conectado else None,
            local,
            minutos_standby(self._ui.get_config_param("tiempo_standby")),
            estado,
            seguridad,
        )
        if activo != self._activo:
            self._activo = activo
            logger.info("Standby %s", "activado" if activo else "desactivado")
            self._informar_suspension(activo)
            self.activoChanged.emit()

    def _informar_suspension(self, activo: bool) -> None:
        """O2e: suspension_entra/_sale al backend (D9-6: solo su log), fuera del hilo
        de la GUI; un fallo solo queda en el log."""
        def tarea():
            try:
                self._backend.post("/ui/standby", {"activa": bool(activo)})
            except Exception as e:
                logger.debug("no se pudo registrar la suspensión: %s", e)
        if getattr(self, "_registrar_suspension", False) and self._ui.connected:
            _en_hilo(tarea)

    def _en_gracia_arranque(self) -> bool:
        inicio = self._inicio if self._inicio_conectado is None else self._inicio_conectado
        return self._reloj() - inicio < self._gracia_arranque_s

    def _inactividad_backend(self):
        """Inactividad común del backend, o None si el último toque es anterior
        al arranque de esta UI (no debe sacarla de la pantalla de arranque)."""
        inactividad = self._ui.get_inactividad_ui()
        if inactividad is None or inactividad > self._reloj() - self._inicio:
            return None
        return inactividad

    def _seguridad_pendiente(self) -> bool:
        """Paro real activo, o estado seguro activo o esperando confirmación.
        U4: PARO_EMERGENCIA solo (sin PARO_REAL) es el módulo E/S sin datos; con
        él la pantalla pasaba a la principal mientras el módulo E/S conectaba y
        volvía sola al reposo al conectar (observación del 19-oct). El módulo E/S
        desconectado se ve al tocar y su alarma (COM-01) despierta igual."""
        es = self._ui.get_campo("estado_seguro", {})
        es = es if isinstance(es, dict) else {}
        return (bool(self._ui.get_estado_flag("PARO_REAL"))
                or es.get("activo") is True or es.get("requiere_confirmacion") is True)

    def _hubo_evento_de_equipo(self, estado, seguridad: bool = False) -> bool:
        alarmas = {a.get("id") for a in self._ui.get_alarmas() if isinstance(a, dict)}
        primera = self._estado_previo is None and self._alarmas_previas is None
        evento = not primera and (estado != self._estado_previo
                                  or bool(alarmas - (self._alarmas_previas or set()))
                                  # aparición y fin del paro/estado seguro: el fin
                                  # también da tiempo_standby completo (TMG-04)
                                  or seguridad != self._seguridad_previa)
        self._estado_previo, self._alarmas_previas = estado, alarmas
        self._seguridad_previa = seguridad
        return evento

    @Property(bool, notify=activoChanged)
    def activo(self) -> bool:
        """True = mostrar la pantalla de arranque."""
        return self._activo

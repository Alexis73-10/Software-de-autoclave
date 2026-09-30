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
#   - nunca en standby durante CICLO, FALLA o EMERGENCIA;
#   - un cambio de estado del equipo o una alarma nueva cuenta como actividad
#     (despierta ambas pantallas y reinicia el conteo), para que no pasen
#     inadvertidos detrás de la pantalla de arranque;
#   - sin conexión con el backend, cada pantalla usa solo su inactividad local;
#   - con el menú de configuración PySide abierto se considera actividad.
# Tiempos con time.monotonic() (CLAUDE.md: timers de proceso nunca con time.time()).

import logging
import threading
import time

from PySide6.QtCore import QEvent, Property, QObject, QTimer, Signal, Slot

logger = logging.getLogger(__name__)

MINUTOS_DEFECTO = 5
ESTADOS_SIN_STANDBY = {"CICLO", "FALLA", "EMERGENCIA"}
_EVENTOS_ACTIVIDAD = {
    QEvent.Type.MouseButtonPress, QEvent.Type.TouchBegin, QEvent.Type.KeyPress,
}


def minutos_standby(valor) -> float:
    """tiempo_standby de los parámetros globales; defecto si falta o es inválido."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor <= 0:
        return MINUTOS_DEFECTO
    return float(valor)


def debe_estar_en_standby(conectado: bool, inactividad_backend, inactividad_local,
                          minutos: float, estado) -> bool:
    """inactividad_* en segundos; None = sin actividad registrada (infinita)."""
    if conectado and estado in ESTADOS_SIN_STANDBY:
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
                 envio_min_s: float = 1.0, mantener_despierto=None):
        super().__init__(parent)
        self._ui = ui_service
        self._backend = backend_client
        self._reloj = reloj
        self._ejecutar = ejecutar
        self._envio_min_s = envio_min_s
        self._mantener_despierto = mantener_despierto or (lambda: False)

        self._activo = True           # la app arranca en la pantalla de arranque
        self._ultima_local = None     # último toque en ESTA pantalla
        self._ultimo_envio = None
        self._estado_previo = None    # para detectar cambios de estado / alarmas nuevas
        self._alarmas_previas = None

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
        if conectado:
            estado = self._ui.get_estado_global()
            if self._hubo_evento_de_equipo(estado):
                self._marcar_actividad(forzar=True)
        if self._mantener_despierto():
            self._marcar_actividad(forzar=False)

        local = None if self._ultima_local is None else self._reloj() - self._ultima_local
        activo = debe_estar_en_standby(
            conectado,
            self._ui.get_inactividad_ui() if conectado else None,
            local,
            minutos_standby(self._ui.get_config_param("tiempo_standby")),
            estado,
        )
        if activo != self._activo:
            self._activo = activo
            logger.info("Standby %s", "activado" if activo else "desactivado")
            self.activoChanged.emit()

    def _hubo_evento_de_equipo(self, estado) -> bool:
        alarmas = {a.get("id") for a in self._ui.get_alarmas() if isinstance(a, dict)}
        primera = self._estado_previo is None and self._alarmas_previas is None
        evento = not primera and (estado != self._estado_previo
                                  or bool(alarmas - (self._alarmas_previas or set())))
        self._estado_previo, self._alarmas_previas = estado, alarmas
        return evento

    @Property(bool, notify=activoChanged)
    def activo(self) -> bool:
        """True = mostrar la pantalla de arranque."""
        return self._activo

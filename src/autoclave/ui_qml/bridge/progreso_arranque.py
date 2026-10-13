# ui_qml/bridge/progreso_arranque.py
#
# Fuente de progreso del arranque para la intro (IntroArranque.qml), según
# planeacion_animacion_arranque.md §6. Expone a QML:
#   fraccion        0–1, etapas completadas / total
#   proceso         clave del texto del proceso en curso (sección "arranque" de
#                   assets/textos/<idioma>.json)
#   terminado       el arranque terminó
#   falloBloqueante el arranque no puede continuar
#
# PROVISIONAL (ARR-03): la secuencia de arranque real (etapas, verificación de
# sensores, clasificación de fallos) aún no tiene plan, así que este objeto es
# un SIMULADOR con las etapas de ejemplo de la previsualización
# (docs/diseno/referencias/intro_arranque_preview.mp4). No está conectado al
# flujo real: no espera ni condiciona nada del backend ni del lanzador.
#
# Para probar los criterios de aceptación §10.3 y §10.4 sin tocar código,
# AUTOCLAVE_INTRO_SIMULACION (leída en app.py) admite:
#   (vacía)         arranque normal
#   fallo:<s>       fallo bloqueante a los <s> segundos (p. ej. fallo:1.5)
#   sin_progreso    no publica ningún progreso (la intro declara el fallo a los 20 s)

import logging

from PySide6.QtCore import Property, QObject, QTimer, Signal

logger = logging.getLogger(__name__)

# (clave de texto, duración en s) — etapas y ritmo de la previsualización
ETAPAS_EJEMPLO = (
    ("iniciando_servicios", 1.0),
    ("conectando_tarjeta", 1.2),
    ("verificando_sensores", 1.2),
    ("abriendo_base_datos", 1.0),
)


def parse_simulacion(valor: str | None) -> dict:
    """Opciones del simulador a partir de AUTOCLAVE_INTRO_SIMULACION."""
    valor = (valor or "").strip().lower()
    if not valor:
        return {}
    if valor == "sin_progreso":
        return {"sin_progreso": True}
    if valor.startswith("fallo:"):
        try:
            segundos = float(valor.split(":", 1)[1])
            if segundos >= 0:
                return {"fallo_en_s": segundos}
        except ValueError:
            pass
    logger.warning("AUTOCLAVE_INTRO_SIMULACION no válida (%r): se simula un arranque normal", valor)
    return {}


class SimuladorProgresoArranque(QObject):
    cambiado = Signal()

    def __init__(self, etapas=ETAPAS_EJEMPLO, fallo_en_s: float | None = None,
                 sin_progreso: bool = False, parent=None):
        super().__init__(parent)
        self._etapas = tuple(etapas)
        self._fallo_en_s = fallo_en_s
        self._sin_progreso = sin_progreso
        self._completadas = 0
        self._fallo = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.avanzar)
        self._timer_fallo = QTimer(self)
        self._timer_fallo.setSingleShot(True)
        self._timer_fallo.timeout.connect(self.declarar_fallo)

    def iniciar(self) -> None:
        """Arranca la simulación (desde t = 0, en paralelo con el resto)."""
        if self._fallo_en_s is not None:
            self._timer_fallo.start(round(self._fallo_en_s * 1000))
        if not self._sin_progreso:
            self._programar_siguiente()

    def detener(self) -> None:
        self._timer.stop()
        self._timer_fallo.stop()

    def _programar_siguiente(self) -> None:
        if self._completadas < len(self._etapas) and not self._fallo:
            self._timer.start(round(self._etapas[self._completadas][1] * 1000))

    def avanzar(self) -> None:
        """Completa la etapa en curso y programa la siguiente."""
        if self._fallo or self._completadas >= len(self._etapas):
            return
        self._completadas += 1
        self.cambiado.emit()
        self._programar_siguiente()

    def declarar_fallo(self) -> None:
        if self._fallo:
            return
        self._fallo = True
        self._timer.stop()
        logger.warning("Arranque simulado: fallo bloqueante")
        self.cambiado.emit()

    def _get_fraccion(self) -> float:
        return self._completadas / len(self._etapas) if self._etapas else 1.0

    def _get_proceso(self) -> str:
        if self._sin_progreso or not self._etapas:
            return ""
        i = min(self._completadas, len(self._etapas) - 1)
        return self._etapas[i][0]

    def _get_terminado(self) -> bool:
        return not self._fallo and self._completadas >= len(self._etapas)

    def _get_fallo(self) -> bool:
        return self._fallo

    fraccion = Property(float, _get_fraccion, notify=cambiado)
    proceso = Property(str, _get_proceso, notify=cambiado)
    terminado = Property(bool, _get_terminado, notify=cambiado)
    falloBloqueante = Property(bool, _get_fallo, notify=cambiado)

# ui_qml/bridge/progreso_arranque.py
#
# Fuente de progreso del arranque para la intro (IntroArranque.qml), según
# planeacion_animacion_arranque.md §6. Expone a QML:
#   fraccion        0–1, etapas completadas / total
#   proceso         clave del texto del proceso en curso (sección "arranque" de
#                   autoclave/i18n/<idioma>.json)
#   terminado       el arranque terminó
#   falloBloqueante el arranque no puede continuar
#
# La UI usa ProgresoArranqueBackend (abajo), que lee GET /arranque. El
# SIMULADOR queda solo para pruebas visuales con AUTOCLAVE_INTRO_SIMULACION
# (antes era la única fuente, ARR-03): es un SIMULADOR con las etapas de ejemplo de la previsualización
# (docs/diseno/referencias/intro_arranque_preview.mp4). No está conectado al
# flujo real: no espera ni condiciona nada del backend ni del lanzador.
#
# Para probar los criterios de aceptación §10.3 y §10.4 sin tocar código,
# AUTOCLAVE_INTRO_SIMULACION (leída en app.py) admite:
#   (vacía)         arranque normal
#   fallo:<s>       fallo bloqueante a los <s> segundos (p. ej. fallo:1.5)
#   sin_progreso    no publica ningún progreso (la intro declara el fallo a los 20 s)

import logging
import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

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


# ── ARR-06 (tanda 18): intro de arranque sin perfil de instalación ─────────
#
# Sin perfil (o con uno inválido) el backend no arranca: la barra solo puede
# mostrar las etapas de origen lanzador (backend/arranque/registro.py). Se
# detiene en verificando_instalacion (fracción 0) con el motivo en lugar del
# nombre de la etapa, lo sostiene MENSAJE_SIN_PERFIL_MS desde que la barra se
# ve (reiniciarVista, que llama la intro al completar su animación) y termina:
# la intro hace su salida normal y la ventana pasa al asistente (puerta 1) o
# al Reposo de instalación (puerta 2). No es un fallo ni una alarma.
# TOPE_SIN_PERFIL_MS: si la intro nunca llamara a reiniciarVista, termina
# igual (nunca deja la pantalla trabada en la intro; DECISIÓN SIN CONFIRMAR).

MENSAJE_SIN_PERFIL_MS = 2000          # DECISIÓN SIN CONFIRMAR (duración, ARR-06)
# V18-03: holgado para un primer arranque lento (carga en frío + 3,5 s de intro
# + 2 s de mensaje) y menor que el plazo de 20 s de la intro, que cuenta desde
# su primer cuadro (siempre después de iniciar())
TOPE_SIN_PERFIL_MS = 15000
PROCESO_SIN_PERFIL = {"sin_perfil": "sin_perfil_instalacion",
                      "invalido": "perfil_invalido_instalacion"}


class ProgresoArranqueSinPerfil(QObject):
    """Misma interfaz para QML que SimuladorProgresoArranque. Temporizadores
    de Qt (reloj monotónico)."""

    cambiado = Signal()

    def __init__(self, motivo: str = "sin_perfil", sostener_ms: int = MENSAJE_SIN_PERFIL_MS,
                 tope_ms: int = TOPE_SIN_PERFIL_MS, parent=None):
        super().__init__(parent)
        self._proceso = PROCESO_SIN_PERFIL.get(motivo, PROCESO_SIN_PERFIL["sin_perfil"])
        self._terminado = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(sostener_ms)
        self._timer.timeout.connect(self.terminar)
        self._tope = QTimer(self)
        self._tope.setSingleShot(True)
        self._tope.setInterval(tope_ms)
        self._tope.timeout.connect(self.terminar)

    def iniciar(self) -> None:
        logger.info("Arranque sin perfil de instalación: %s", self._proceso)
        self._tope.start()

    def detener(self) -> None:
        self._timer.stop()
        self._tope.stop()

    @Slot()
    def reiniciarVista(self) -> None:
        """La barra ya se ve: sostiene el mensaje y luego termina."""
        if not self._terminado and not self._timer.isActive():
            self._timer.start()

    @Slot()
    def terminar(self) -> None:
        if self._terminado:
            return
        self._terminado = True
        self.detener()
        self.cambiado.emit()

    fraccion = Property(float, lambda self: 0.0, notify=cambiado)
    proceso = Property(str, lambda self: self._proceso, notify=cambiado)
    terminado = Property(bool, lambda self: self._terminado, notify=cambiado)
    falloBloqueante = Property(bool, lambda self: False, notify=cambiado)


# ── Progreso REAL del backend (GET /arranque) ──────────────────────────────
#
# Observación de Cristian (19-oct): la barra del simulador no mostraba lo que
# pasa de verdad (la tarjeta, el backend). Aquí la intro sigue las etapas que
# publica el backend (backend/arranque/registro.py, contrato de GET /arranque).
# Mientras el backend aún no responde, el proceso es "iniciando_servicios".
# Sin tarjeta, el backend reintenta las E/S para siempre (ARR_SIN_ES a los
# 15 s); la intro termina igual y la pantalla principal muestra "tarjeta
# desconectada" (U4). Solo presentación: no condiciona nada del arranque.

_ETAPA_UI = "preparando_interfaz"      # la completa cada UI: no cuenta aquí
_CODIGO_SIN_ES = "ARR_SIN_ES"
_SIN_RESPUESTA = {"fraccion": 0.0, "proceso": "iniciando_servicios",
                  "terminado": False, "fallo": False}


def resumir_arranque(instantanea) -> dict:
    """fraccion/proceso/terminado/fallo a partir de la respuesta de /arranque.
    None o una respuesta mal formada = el backend aún no responde."""
    if not isinstance(instantanea, dict):
        return dict(_SIN_RESPUESTA)
    etapas = instantanea.get("etapas")
    if not isinstance(etapas, list) or not etapas:
        return dict(_SIN_RESPUESTA)
    try:
        backend = [e for e in etapas if e["clave"] != _ETAPA_UI]
        total = sum(float(e["peso"]) for e in backend)
        hechas = sum(float(e["peso"]) for e in backend if e["estado"] in ("ok", "degradado"))
        sin_es = any(e["clave"] == "conectando_modulos_es" and e["estado"] == "en_curso"
                     and e.get("codigo") == _CODIGO_SIN_ES for e in backend)
    except (KeyError, TypeError, ValueError):
        return dict(_SIN_RESPUESTA)
    fallo = instantanea.get("falloBloqueante") is True
    terminado = not fallo and (instantanea.get("terminado") is True or sin_es)
    proceso = instantanea.get("etapaActual")
    return {
        "fraccion": hechas / total if total > 0 else 0.0,
        "proceso": proceso if isinstance(proceso, str) else "",
        "terminado": terminado,
        "fallo": fallo,
    }


def _etapas_backend(instantanea) -> list:
    """[(clave, peso, completada)] de las etapas del backend, en orden; [] si
    la respuesta no sirve."""
    try:
        return [(e["clave"], float(e["peso"]), e["estado"] in ("ok", "degradado"))
                for e in instantanea["etapas"] if e["clave"] != _ETAPA_UI]
    except (KeyError, TypeError, ValueError):
        return []


class ProgresoArranqueBackend(QObject):
    """Misma interfaz para QML que SimuladorProgresoArranque. `leer()` devuelve
    el JSON de /arranque o lanza; con `en_hilo` cada consulta corre fuera del
    hilo de la GUI y su resultado se aplica en el siguiente tick del timer.

    Repetición visible (19-oct): las etapas de archivos tardan milisegundos y
    la barra solo se ve desde los 3,5 s de intro, cuando el backend ya va por
    las E/S. reiniciarVista() (lo llama la intro al mostrar la barra) vuelve a
    mostrar, una por paso de `permanencia_ms`, las etapas REALES ya cumplidas,
    sin adelantarse nunca al backend; el fallo bloqueante se muestra en el acto."""

    cambiado = Signal()

    def __init__(self, leer, en_hilo: bool = True, intervalo_ms: int = 300,
                 permanencia_ms: int = 350, parent=None):
        super().__init__(parent)
        self._leer = leer
        self._en_hilo = en_hilo
        self._real = dict(_SIN_RESPUESTA)
        self._etapas: list = []
        self._vista: int | None = None   # etapas mostradas como cumplidas; None = sin repetición
        self._publicado = dict(_SIN_RESPUESTA)
        self._pendiente = None          # resultado del hilo, aún sin aplicar
        self._en_vuelo = False
        self._lock = threading.Lock()
        self._timer = QTimer(self)
        self._timer.setInterval(intervalo_ms)
        self._timer.timeout.connect(self.sondear)
        self._timer_vista = QTimer(self)
        self._timer_vista.setInterval(permanencia_ms)
        self._timer_vista.timeout.connect(self.avanzarVista)

    def iniciar(self) -> None:
        self.sondear()
        self._timer.start()

    def detener(self) -> None:
        self._timer.stop()
        self._timer_vista.stop()

    # ── vista ────────────────────────────────────────────────────────────

    def _cumplidas_reales(self) -> int:
        n = 0
        for _, _, completada in self._etapas:
            if not completada:
                break
            n += 1
        return n

    @Slot()
    def reiniciarVista(self) -> None:
        if self._real["fallo"]:
            return
        self._vista = 0
        self._publicar()
        self._timer_vista.start()

    @Slot()
    def avanzarVista(self) -> None:
        if self._vista is None:
            return
        if self._vista < self._cumplidas_reales():
            self._vista += 1
        self._publicar()

    def _publicar(self) -> None:
        real = self._real
        if self._vista is None or real["fallo"] or not self._etapas:
            nuevo = dict(real)
        else:
            cumplidas = self._cumplidas_reales()
            vista = min(self._vista, cumplidas)
            total = sum(p for _, p, _ in self._etapas)
            al_dia = vista >= cumplidas
            nuevo = {
                "fraccion": (real["fraccion"] if al_dia else
                             sum(p for _, p, _ in self._etapas[:vista]) / total if total else 0.0),
                "proceso": real["proceso"] if al_dia else self._etapas[vista][0],
                "terminado": real["terminado"] and al_dia,
                "fallo": False,
            }
            if al_dia and (real["terminado"] or vista >= len(self._etapas)):
                self._timer_vista.stop()
        if nuevo != self._publicado:
            self._publicado = nuevo
            self.cambiado.emit()

    # ── consulta ─────────────────────────────────────────────────────────

    def _consultar(self):
        try:
            return self._leer()
        except Exception as e:     # backend aún no arriba: sin respuesta
            logger.debug("GET /arranque falló: %s", e)
            return None

    def _aplicar(self, respuesta) -> None:
        nuevo = resumir_arranque(respuesta)
        if nuevo["proceso"] != self._real["proceso"]:
            logger.info("Arranque: %s", nuevo["proceso"] or "terminado")
        self._real = nuevo
        etapas = _etapas_backend(respuesta) if isinstance(respuesta, dict) else []
        if etapas or respuesta is None:
            self._etapas = etapas
        if nuevo["fallo"]:
            self._vista = None
            self._timer_vista.stop()
        self._publicar()
        if nuevo["terminado"] or nuevo["fallo"]:
            self._timer.stop()

    def sondear(self) -> None:
        if self._real["terminado"] or self._real["fallo"]:
            self._timer.stop()
            return
        if not self._en_hilo:
            self._aplicar(self._consultar())
            return
        with self._lock:
            listo, self._pendiente = self._pendiente, None
            lanzar = not self._en_vuelo
            if lanzar:
                self._en_vuelo = True
        if listo is not None:
            self._aplicar(listo[0])
        if lanzar and not (self._real["terminado"] or self._real["fallo"]):
            threading.Thread(target=self._hilo, daemon=True, name="progreso-arranque").start()
        elif lanzar:
            with self._lock:
                self._en_vuelo = False

    def _hilo(self) -> None:
        respuesta = self._consultar()
        with self._lock:
            self._pendiente = (respuesta,)
            self._en_vuelo = False

    fraccion = Property(float, lambda self: self._publicado["fraccion"], notify=cambiado)
    proceso = Property(str, lambda self: self._publicado["proceso"], notify=cambiado)
    terminado = Property(bool, lambda self: self._publicado["terminado"], notify=cambiado)
    falloBloqueante = Property(bool, lambda self: self._publicado["fallo"], notify=cambiado)

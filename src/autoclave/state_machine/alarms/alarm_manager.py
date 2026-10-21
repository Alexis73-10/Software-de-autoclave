import logging
import threading
from collections import deque
from datetime import datetime

from autoclave.state_machine.alarms.catalogo import CATALOGO, COM_02, COM_03, Nivel
from autoclave.state_machine.alarms.instancia import (
    EstadoInstancia, EventoAlarma, InstanciaAlarma, clave_de,
)

logger = logging.getLogger(__name__)

DETALLE_NO_DISPONIBLE = "Detalle no disponible."
_MAX_EVENTOS_RECIENTES = 20
# P-5 (tanda 6): despeje manual. No se resuelven al salir de FALLA
# (resolver_todas_por_reinicio) sin el reconocimiento explícito del operador;
# reconocidas fuera de CICLO se resuelven en el acto.
DESPEJE_POR_RECONOCIMIENTO = frozenset({COM_02, COM_03})
_LOG_POR_NIVEL = {
    Nivel.INFORMATIVO: logging.INFO,
    Nivel.AVISO: logging.WARNING,
    Nivel.ALARMA: logging.ERROR,
    Nivel.FALLO_CRITICO: logging.CRITICAL,
}


class AlarmManager:
    """Alarmas del equipo (spec 2026-10-06-sistema-alarmas-parte-a §5).

    API nueva: activar / resolver / reconocer. Las instancias viven aquí,
    protegidas por un candado: reconocer() llega por HTTP mientras el
    ControlLoop activa y resuelve. Los oyentes (historial) se notifican
    fuera del candado."""

    def __init__(self, estado=None, catalogo=None, reloj=None):
        self.estado = estado
        self._catalogo = catalogo if catalogo is not None else CATALOGO
        self._reloj = reloj if reloj is not None else datetime.now
        self._lock = threading.Lock()
        self._instancias: dict[str, InstanciaAlarma] = {}
        self._eventos: deque[InstanciaAlarma] = deque(maxlen=_MAX_EVENTOS_RECIENTES)
        self._oyentes = []

    # ------------------------------------------------------------------
    # API nueva
    # ------------------------------------------------------------------

    def suscribir(self, oyente) -> None:
        self._oyentes.append(oyente)

    def activar(self, codigo: str, origen: str | None = None, **valores) -> InstanciaAlarma:
        definicion = self._catalogo[codigo]          # código desconocido → KeyError
        descripcion = self._renderizar(definicion, valores)
        ahora = self._reloj()
        clave = clave_de(codigo, origen)
        evento = None
        with self._lock:
            if definicion.nivel is Nivel.INFORMATIVO:
                inst = InstanciaAlarma(clave, definicion, origen, dict(valores),
                                       descripcion, ahora, resuelta=ahora)
                self._eventos.append(inst)
                evento = EventoAlarma.APARECIDA
            else:
                inst = self._instancias.get(clave)
                # Una RESUELTA_SIN_RECONOCER que vuelve a aparecer es una
                # ocurrencia nueva (spec §5.2, corrección 2026-10-07): instancia
                # y fila de historial propias, con su hora y ciclo. La vieja
                # sale de memoria; su fila queda resuelta y sin reconocer.
                if inst is None or inst.estado is EstadoInstancia.RESUELTA_SIN_RECONOCER:
                    inst = InstanciaAlarma(clave, definicion, origen, dict(valores),
                                           descripcion, ahora)
                    self._instancias[clave] = inst
                    evento = EventoAlarma.APARECIDA
                else:
                    inst.valores = dict(valores)
                    inst.descripcion = descripcion
        if evento is EventoAlarma.APARECIDA:
            logger.log(_LOG_POR_NIVEL[definicion.nivel], "Alarma %s: %s — %s",
                       clave, definicion.titulo, descripcion)
        self._notificar(evento, inst)
        return inst

    def resolver(self, codigo: str, origen: str | None = None) -> None:
        with self._lock:
            inst = self._resolver_sin_candado(clave_de(codigo, origen))
        if inst is not None:
            logger.info("Alarma resuelta: %s", inst.clave)
            self._notificar(EventoAlarma.RESUELTA, inst)

    def obtener(self, clave: str) -> InstanciaAlarma | None:
        with self._lock:
            return self._instancias.get(clave)

    def reconocer(self, clave: str, usuario: str) -> bool:
        en_ciclo = self._en_ciclo()     # fuera del candado (TMG-08 de T2)
        with self._lock:
            inst = self._instancias.get(clave)
            if inst is None or not inst.nivel.requiere_reconocimiento:
                return False
            if inst.reconocida_por is not None:
                return True
            inst.reconocida_por = usuario
            inst.reconocida_en = self._reloj()
            despejada = None
            if inst.estado is EstadoInstancia.RESUELTA_SIN_RECONOCER:
                del self._instancias[clave]
            elif inst.codigo in DESPEJE_POR_RECONOCIMIENTO and not en_ciclo:
                despejada = self._resolver_sin_candado(clave)
        logger.info("Alarma reconocida: %s por %s", clave, usuario)
        self._notificar(EventoAlarma.RECONOCIDA, inst)
        if despejada is not None:
            logger.info("Alarma despejada al reconocerla: %s", clave)
            self._notificar(EventoAlarma.RESUELTA, despejada)
        return True

    def _en_ciclo(self) -> bool:
        """True si la máquina está en CICLO (sin estado conocido: False)."""
        try:
            estado = self.estado.get_machine_state() if self.estado is not None else None
        except Exception:
            return True
        return getattr(estado, "name", None) == "CICLO"

    def resolver_todas_por_reinicio(self) -> None:
        with self._lock:
            resueltas = [self._resolver_sin_candado(c) for c, i in list(self._instancias.items())
                         if not (i.codigo in DESPEJE_POR_RECONOCIMIENTO
                                 and i.reconocida_por is None)]
        for inst in resueltas:
            if inst is not None:
                self._notificar(EventoAlarma.RESUELTA, inst)

    def activas(self) -> list[InstanciaAlarma]:
        with self._lock:
            instancias = list(self._instancias.values())
        return sorted(instancias, key=lambda i: (-i.nivel.value, i.aparecida))

    def eventos_recientes(self) -> list[InstanciaAlarma]:
        with self._lock:
            return list(self._eventos)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _resolver_sin_candado(self, clave: str) -> InstanciaAlarma | None:
        inst = self._instancias.get(clave)
        if inst is None or inst.estado is not EstadoInstancia.ACTIVA:
            return None
        inst.resuelta = self._reloj()
        if inst.nivel.requiere_reconocimiento and inst.reconocida_por is None:
            inst.estado = EstadoInstancia.RESUELTA_SIN_RECONOCER
        else:
            del self._instancias[clave]
        return inst

    @staticmethod
    def _renderizar(definicion, valores) -> str:
        try:
            return definicion.renderizar(valores)
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            logger.error("Alarma %s: plantilla con valores incompletos (%r): %r",
                         definicion.codigo, exc, valores)
            return DETALLE_NO_DISPONIBLE

    def _notificar(self, evento, inst) -> None:
        if evento is None:
            return
        for oyente in list(self._oyentes):
            try:
                oyente(evento, inst)
            except Exception:
                logger.exception("Oyente de alarmas falló en %s de %s", evento, inst.clave)

    def _activas_nuevas(self, *niveles) -> bool:
        with self._lock:
            return any(i.estado is EstadoInstancia.ACTIVA and (not niveles or i.nivel in niveles)
                       for i in self._instancias.values())

    def has_emergency(self) -> bool:
        return self._activas_nuevas(Nivel.FALLO_CRITICO)

    def has_failure(self) -> bool:
        return self._activas_nuevas(Nivel.ALARMA)

    def has_alert(self) -> bool:
        return self._activas_nuevas(Nivel.AVISO)

    def has_blocking_alarm(self) -> bool:
        with self._lock:
            return any(i.estado is EstadoInstancia.ACTIVA and i.definicion.bloquea_inicio
                       for i in self._instancias.values())

    def has_active_alarms(self) -> bool:
        return self._activas_nuevas()

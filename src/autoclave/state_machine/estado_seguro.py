# state_machine/estado_seguro.py
#
# Protocolo de estado seguro común a todo fallo, cancelación y paro
# (planeacion_fin_de_ciclo_y_puertas.md §15, D-22; tanda 2026-10-14 E3).
#
# Antes (PF-10), al confirmar un FALLO nadie continuaba el protocolo de
# fallo: PREPARACION solo venteaba con la rápida y nunca cerraba la
# descompresión de chaqueta. Ahora, al salir de CICLO con FALLO o CANCELADO,
# la StateMachine entrega aquí el ProtocoloFallo del ciclo y este módulo lo
# sigue ejecutando en el estado siguiente hasta que la cámara sea segura:
#
#  1. Paro activo: no hace nada (los estados mandan ALL_OFF continuo); si
#     es un paro real (PARO_REAL, U4) se marca que hará falta una
#     confirmación nueva. Sin datos de la tarjeta solo se pausa.
#  2. Paro liberado: las salidas siguen en 0, sin avance automático, hasta
#     "Confirmar y llevar a estado seguro" (cualquier operador, sin rol).
#  3. Confirmado: exige datos vigentes; sigue el protocolo de fallo (modo de
#     descompresión del programa; en líquidos nunca la rápida con la carga
#     caliente; modos 4/5 con enfriamiento).
#  4. Estado seguro (cámara segura 3 ticks seguidos): cierra toda válvula del
#     protocolo y termina; FALLA ya puede pasar a PREPARACION.
#
# Cada paso queda en audit_log por el callback `al_evento` (paro activado,
# liberado, confirmado, estado seguro alcanzado con la duración).

import logging
import time

from autoclave.core.runtime import camara_segura
from autoclave.state_machine.alarms.catalogo import CIC_10

logger = logging.getLogger(__name__)

_TICKS_SEGUROS = 3     # convención de debounce de 3 lecturas


class ProtocoloEstadoSeguro:

    def __init__(self, estado, config, profile=None, programas_seguridad=None,
                 al_evento=None, reloj=time.monotonic, alarm_manager=None):
        self.estado = estado
        self.config = config
        self.profile = profile
        self.programas_seguridad = programas_seguridad
        self.al_evento = al_evento
        self._reloj = reloj
        self._protocolo = None
        self._t_inicio = None
        self._ticks_seguros = 0
        self._paro_visto = False
        self._pausado = False
        self.requiere_confirmacion = False
        self.alarm_manager = alarm_manager
        # Callable que mantiene el enfriamiento del drenaje mientras el
        # protocolo ventea (SAF-07 de T5). Lo fija la StateMachine.
        self.mantener_drenaje = None
        self._alarma_bloqueo = None

    @property
    def activo(self) -> bool:
        return self._protocolo is not None

    @property
    def programa(self):
        """Programa (copia del ciclo) con el que corre el protocolo, o None."""
        return getattr(self._protocolo, "cycle", None)

    def reemplazar_programa(self, programa) -> None:
        """S4: el protocolo pasa a usar `programa` (copia con otra asignación
        de sensores) sin mutar la instantánea del ciclo terminado."""
        if self._protocolo is not None and programa is not None:
            self._protocolo.cycle = programa

    @property
    def permite_salir_de_falla(self) -> bool:
        """P-2 (tanda 6): con el protocolo disparado por la pérdida del
        Principal, el operador reconoce y FALLA pasa a PREPARACION sin
        técnico; el protocolo sigue venteando por la lenta allí y el inicio
        de ciclo queda bloqueado mientras siga activo. No aplica si espera la
        confirmación tras un paro.

        D8-2.6 (tanda 8, Cristian): vale igual si se llegó a `solo_lenta` con el
        protocolo ya en marcha por otra causa (R1-P4). "NO ABRIR" no cambia:
        sigue hasta que la cámara sea segura (camara_segura, con el Principal)."""
        return (self.activo and not self.requiere_confirmacion
                and getattr(self._protocolo, "solo_lenta", False) is True)

    @property
    def bloqueado_motivo(self) -> str | None:
        """Motivo vigente por el que el protocolo no puede terminar solo
        (CIC-10), o None. Lo muestra la UI junto al botón de asignar sonda."""
        motivo = getattr(self._protocolo, "bloqueado_motivo", None)
        return motivo if isinstance(motivo, str) else None

    def _evento(self, evento: str, **detalle) -> None:
        logger.info("Estado seguro: %s %s", evento, detalle or "")
        if self.al_evento is None:
            return
        try:
            self.al_evento(evento, detalle)
        except Exception:
            logger.exception("Estado seguro: no se pudo registrar %s", evento)

    def iniciar(self, protocolo, requiere_confirmacion: bool = False) -> None:
        """Toma el ProtocoloFallo ya ejecutado del ciclo terminado."""
        if protocolo is None or not getattr(protocolo, "ejecutado", False):
            return
        self._protocolo = protocolo
        self._t_inicio = self._reloj()
        self._ticks_seguros = 0
        self._paro_visto = False
        # Tras un paro durante el ciclo el protocolo no abrió válvulas: al
        # empezar a actuar se "reanuda" (pulsos y plazo del modo desde cero)
        self._pausado = True
        self.requiere_confirmacion = requiere_confirmacion
        self._evento("estado_seguro_iniciado", requiere_confirmacion=requiere_confirmacion)

    def confirmar(self) -> bool:
        """"Confirmar y llevar a estado seguro". False si no aplica (no hay
        protocolo, no requiere confirmación o el paro sigue activo)."""
        if (not self.activo or not self.requiere_confirmacion
                or self.estado.get_flag("PARO_EMERGENCIA")):
            return False
        self.requiere_confirmacion = False
        self._evento("estado_seguro_confirmado")
        return True

    def terminar(self) -> None:
        """Cierre forzado (p. ej. al entrar a un ciclo nuevo)."""
        if self._protocolo is not None:
            self._protocolo.finalizar()
        self._protocolo = None
        self._resolver_alarma_bloqueo()

    def _actualizar_alarma_bloqueo(self) -> None:
        """SAF-04 de T5: si el protocolo no puede terminar solo, alarma visible
        (CIC-10) con el motivo; se resuelve cuando vuelve a avanzar."""
        if self.alarm_manager is None:
            return
        motivo = getattr(self._protocolo, "bloqueado_motivo", None)
        motivo = motivo if isinstance(motivo, str) else None
        if motivo == self._alarma_bloqueo:
            return
        try:
            if motivo is None:
                self.alarm_manager.resolver(CIC_10)
            else:
                self.alarm_manager.activar(CIC_10, motivo=motivo)
            self._alarma_bloqueo = motivo
        except Exception:
            logger.exception("Estado seguro: no se pudo actualizar la alarma de bloqueo")

    def _resolver_alarma_bloqueo(self) -> None:
        if self.alarm_manager is not None and self._alarma_bloqueo is not None:
            try:
                self.alarm_manager.resolver(CIC_10)
            except Exception:
                logger.exception("Estado seguro: no se pudo resolver la alarma de bloqueo")
        self._alarma_bloqueo = None

    def update(self, datos_vigentes: bool = True) -> None:
        if not self.activo:
            return

        if self.estado.get_flag("PARO_EMERGENCIA"):
            # U4 (D2): solo un paro real exige "Confirmar y llevar a estado
            # seguro". Sin datos de la tarjeta (desconectada o sin tramas) se
            # pausa igual, y al volver los datos sigue sin confirmación.
            if self.estado.get_flag("PARO_REAL"):
                if not self._paro_visto:
                    self._paro_visto = True
                    self._evento("paro_activado")
                self.requiere_confirmacion = True
            self._ticks_seguros = 0
            self._pausado = True
            return
        if self._paro_visto:
            self._paro_visto = False
            self._evento("paro_liberado")

        if self.requiere_confirmacion or not datos_vigentes:
            self._ticks_seguros = 0
            self._pausado = True
            return

        if self._pausado:
            self._pausado = False
            reanudar = getattr(self._protocolo, "reanudar", None)
            if callable(reanudar):
                reanudar()
        solo_lenta_antes = getattr(self._protocolo, "solo_lenta", False) is True
        sellado_antes = getattr(self._protocolo, "sellado", False) is True
        self._protocolo.update()
        if not solo_lenta_antes and getattr(self._protocolo, "solo_lenta", False) is True:
            # R1-P4: el Principal se perdió con el protocolo en marcha
            self._evento("estado_seguro_solo_lenta", motivo="sensor Principal sin lectura")
        sellado = getattr(self._protocolo, "sellado", False) is True
        if not sellado_antes and sellado:
            # D8-2.10: líquidos en modos 4/5, cámara sellada sin venteo
            self._evento("estado_seguro_sellado", motivo="sensor Principal sin lectura")
        elif sellado_antes and not sellado:
            self._evento("estado_seguro_venteo_tras_sellado",
                         motivo=getattr(self._protocolo, "motivo_venteo", None))
        if self.mantener_drenaje is not None:
            try:
                self.mantener_drenaje()
            except Exception:
                logger.exception("Estado seguro: no se pudo mantener el drenaje")
        self._actualizar_alarma_bloqueo()

        programas = None
        if self.programas_seguridad is not None:
            try:
                programas = self.programas_seguridad()
            except Exception:
                logger.exception("Estado seguro: no se pudieron obtener los programas")
                self._ticks_seguros = 0
                return
        if programas is None:
            programas = [getattr(self._protocolo, "cycle", None)]
        temp_max_ciclo = None
        try:
            temp_max_ciclo = self._protocolo.cycle.get_param("finalizacion", "temp_max_apertura")
        except Exception:
            pass
        segura, _ = camara_segura.evaluar(self.estado, self.config, programas, self.profile,
                                          temp_max_ciclo=temp_max_ciclo)
        self._ticks_seguros = self._ticks_seguros + 1 if segura else 0
        if self._ticks_seguros >= _TICKS_SEGUROS:
            duracion = self._reloj() - self._t_inicio if self._t_inicio is not None else None
            self._protocolo.finalizar()
            self._protocolo = None
            self._resolver_alarma_bloqueo()
            self._evento("estado_seguro_alcanzado",
                         duracion_s=round(duracion, 1) if duracion is not None else None)

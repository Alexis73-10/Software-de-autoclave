# state_machine/estado_seguro.py
#
# Hotfix ES (6-nov-2026, decisión de Cristian): se retiró el protocolo
# automático de estado seguro (ProtocoloEstadoSeguro), que seguía corriendo
# el protocolo de fallo después de CICLO y en el arranque con la cámara no
# segura. Cada fase y los estados PREPARACION, PREPARADO y FALLA conservan sus
# recuperaciones, alarmas y bloqueos; PREPARACION/PREPARADO/FALLA nivelan la
# presión de cámara (riesgo HAZ-ES-RET-01).
#
# Queda solo la confirmación por software tras soltar un paro de emergencia
# REAL visto fuera de CICLO (U4, D9-1.2; se conserva por decisión previa de
# Cristian, confirmada el 6-nov): con el paro activo los estados mandan el
# ALL_OFF; al soltarlo las salidas siguen en 0 y nada avanza hasta
# "Confirmar" (cualquier operador). Al confirmar no corre ningún protocolo:
# la StateMachine lleva el equipo a PREPARACION (desde FALLA, el
# reconocimiento de la falla hace lo mismo).
#
# El atributo se sigue llamando `estado_seguro` en el ControlLoop y la
# StateMachine, y /status.estado_seguro conserva su forma con `activo` en
# false, para no romper clientes.

import logging

logger = logging.getLogger(__name__)


class ConfirmacionParo:

    def __init__(self, estado, al_evento=None):
        self.estado = estado
        self.al_evento = al_evento
        self._paro_visto = False
        self.requiere_confirmacion = False

    # Compatibilidad con los clientes de /status.estado_seguro y del backend:
    # el protocolo ya no existe, nunca está activo ni tiene programa.
    @property
    def activo(self) -> bool:
        return False

    @property
    def programa(self):
        return None

    @property
    def causa(self) -> str | None:
        """"paro_liberado" mientras espera la confirmación; si no, None."""
        return "paro_liberado" if self.requiere_confirmacion else None

    def _evento(self, evento: str, **detalle) -> None:
        logger.info("Paro de emergencia: %s %s", evento, detalle or "")
        if self.al_evento is None:
            return
        try:
            self.al_evento(evento, detalle)
        except Exception:
            logger.exception("Paro de emergencia: no se pudo registrar %s", evento)

    def update(self) -> None:
        """Una vez por tick fuera de CICLO (la StateMachine). Solo un paro
        real (PARO_REAL) exige la confirmación; sin datos del módulo E/S no se
        afirma paro."""
        if self.estado.get_flag("PARO_EMERGENCIA"):
            if self.estado.get_flag("PARO_REAL"):
                if not self._paro_visto:
                    self._paro_visto = True
                    self._evento("paro_activado")
                self.requiere_confirmacion = True
            return
        if self._paro_visto:
            self._paro_visto = False
            self._evento("paro_liberado")

    def esperando_confirmacion(self) -> bool:
        """Paro real ya soltado y sin confirmar: las salidas siguen en 0."""
        return (self.requiere_confirmacion is True
                and not self.estado.get_flag("PARO_EMERGENCIA"))

    def confirmar(self) -> bool:
        """"Confirmar" tras soltar el paro. False si no aplica (no hace falta
        o el paro sigue activo)."""
        if not self.requiere_confirmacion or self.estado.get_flag("PARO_EMERGENCIA"):
            return False
        self.requiere_confirmacion = False
        self._evento("estado_seguro_confirmado")
        return True

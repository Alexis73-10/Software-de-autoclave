# autoclave/devices/safety/emergency_stop.py

import logging

logger = logging.getLogger(__name__)

# Texto que acompaña a la alarma PARO_EMERGENCIA (D-16): con el cableado
# viejo (contacto NO) el equipo muestra paro permanente hasta pasarlo a NC.
# U4 (tanda 2): SIS-01 ya solo sale con la entrada en 0 leída del módulo E/S;
# la falta de datos tiene sus propias alarmas (COM-01, TARJETA_SIN_TRAMA_VALIDA).
AVISO_CABLEADO_NC = (
    "La entrada del paro está en 0. Si el botón no está "
    "pulsado, revisar que el cableado sea contacto normalmente cerrado (NC)."
)


class EmergencyStop:
    def __init__(self, estado, flag_name="PARO_EMERGENCIA"):
        """
        :param estado: contenedor donde está set_flag()
        :param flag_name: nombre de la flag en el sistema
        """
        self.estado = estado
        self.flag_name = flag_name

        # Sin datos del módulo E/S (antes del primer cuadro) = paro (D-16)
        self.active = True
        self._last = True
        # U4 (tanda 2): pero no paro real; sin datos no se sabe
        self.real = False
        self.estado.set_flag(self.flag_name, True)
        self.estado.set_flag("PARO_REAL", False)

    # ---------------------------------------------------------------------
    # 🔄 UPDATE
    # ---------------------------------------------------------------------
    def update(self, value):
        """
        Actualiza el estado del paro y lo refleja en el contenedor global.
        `value` es el DI crudo del paro, contacto NC (D-16, seguridad
        intrínseca): 1 = sin paro; 0 o None (sin dato) = paro.
        PARO_REAL (U4) solo con un 0 leído: quien llama pasa None si no hay
        enlace o la trama DI no está vigente.
        """
        self._last = self.active
        self.active = value is None or not bool(value)
        self.real = value is not None and not bool(value)

        self.estado.set_flag(self.flag_name, self.active)
        self.estado.set_flag("PARO_REAL", self.real)

        # (Opcional pero útil)
        if self.active and not self._last:
            logger.warning("Paro de emergencia ACTIVADO")

        elif not self.active and self._last:
            logger.info("Paro de emergencia LIBERADO")

    # ---------------------------------------------------------------------
    # ⚡ EVENTOS (por si luego los necesitas)
    # ---------------------------------------------------------------------
    def rising_edge(self) -> bool:
        return self.active and not self._last

    def falling_edge(self) -> bool:
        return not self.active and self._last

    # ---------------------------------------------------------------------
    def __repr__(self):
        return f"<EmergencyStop active={self.active} real={self.real}>"
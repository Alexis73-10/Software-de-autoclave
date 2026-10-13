# autoclave/devices/safety/emergency_stop.py

import logging

logger = logging.getLogger(__name__)

# Texto que acompaña a la alarma PARO_EMERGENCIA (D-16): con el cableado
# viejo (contacto NO) el equipo muestra paro permanente hasta pasarlo a NC.
AVISO_CABLEADO_NC = (
    "Paro = entrada en 0 o sin datos de la tarjeta. Si el botón no está "
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

        # Sin datos de la tarjeta (antes del primer cuadro) = paro (D-16)
        self.active = True
        self._last = True
        self.estado.set_flag(self.flag_name, True)

    # ---------------------------------------------------------------------
    # 🔄 UPDATE
    # ---------------------------------------------------------------------
    def update(self, value):
        """
        Actualiza el estado del paro y lo refleja en el contenedor global.
        `value` es el DI crudo del paro, contacto NC (D-16, seguridad
        intrínseca): 1 = sin paro; 0 o None (sin dato) = paro.
        """
        self._last = self.active
        self.active = value is None or not bool(value)

        # 🔥 Esto era lo que tú querías
        self.estado.set_flag(self.flag_name, self.active)

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
        return f"<EmergencyStop active={self.active}>"
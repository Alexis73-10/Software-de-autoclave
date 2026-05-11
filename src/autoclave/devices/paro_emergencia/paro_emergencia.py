# autoclave/devices/safety/emergency_stop.py

import logging

logger = logging.getLogger(__name__)


class EmergencyStop:
    def __init__(self, estado, flag_name="PARO_EMERGENCIA"):
        """
        :param estado: contenedor donde está set_flag()
        :param flag_name: nombre de la flag en el sistema
        """
        self.estado = estado
        self.flag_name = flag_name

        self.active = False
        self._last = False

    # ---------------------------------------------------------------------
    # 🔄 UPDATE
    # ---------------------------------------------------------------------
    def update(self, value: bool):
        """
        Actualiza el estado del paro y lo refleja en el contenedor global
        """
        self._last = self.active
        self.active = bool(value)

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
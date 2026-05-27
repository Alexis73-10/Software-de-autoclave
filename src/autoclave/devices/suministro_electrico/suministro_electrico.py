import logging

logger = logging.getLogger(__name__)


class SuministroElectrico:
    def __init__(self, estado, set_do, flag_name="FALLO_SUMINISTRO_ELECTRICO"):
        self.estado = estado
        self.set_do = set_do
        self.flag_name = flag_name
        self.active = False   # True = fallo (sin suministro)
        self._last = False

    def update(self, value: bool):
        """value=True → suministro presente. value=False → corte eléctrico."""
        self._last = self.active
        self.active = not bool(value)

        self.estado.set_flag(self.flag_name, self.active)

        if self.active and not self._last:
            logger.error("Suministro eléctrico: CORTE DETECTADO")
            self.set_do.bomba_vacio_off()
        elif not self.active and self._last:
            logger.info("Suministro eléctrico: RESTAURADO")

    def __repr__(self):
        return f"<SuministroElectrico fallo={self.active}>"

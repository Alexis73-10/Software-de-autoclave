import logging
from autoclave.state_machine.alarms.catalogo import SIS_01

logger = logging.getLogger(__name__)


class FallaState:

    def __init__(self, estado, set_do, alarm_manager):
        self.estado = estado
        self.set_do = set_do
        self.alarm_manager = alarm_manager

    def run(self) -> bool:
        """
        Llamar en cada tick mientras el estado sea FALLA.
        Retorna True cuando el operador reconoció la falla y la máquina
        debe transicionar a PREPARACION.
        """
        if self.estado.get_flag("PARO_EMERGENCIA"):
            self.set_do.reset_all_outputs()
            self.alarm_manager.activar(SIS_01, estado="Falla")
            self.set_do.buzer_emergencia()
            return False

        if self.estado.get_flag("RESET_FALLA"):
            self.estado.set_flag("RESET_FALLA", False)
            logger.info("FallaState: reset solicitado → transicionando a PREPARACION")
            return True

        return False

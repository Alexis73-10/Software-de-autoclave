from autoclave.state_machine.alarms.catalogo import SIS_01
import logging

logger = logging.getLogger(__name__)


class Hibernacion:

    def __init__(self, estado, set_do, alarm_manager):
        self.estado = estado
        self.set_do = set_do
        self.alarm_manager = alarm_manager

    def run(self):
        if self.estado.get_flag("PARO_EMERGENCIA"):
            self.set_do.reset_all_outputs()
            self.alarm_manager.activar(SIS_01, estado="Hibernación")
            self.set_do.buzer_emergencia()

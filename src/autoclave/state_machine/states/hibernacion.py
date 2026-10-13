from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
from autoclave.devices.paro_emergencia.paro_emergencia import AVISO_CABLEADO_NC
import logging

logger = logging.getLogger(__name__)


class Hibernacion:

    def __init__(self, estado, set_do, alarm_manager):
        self.estado = estado
        self.set_do = set_do
        self.alarm_manager = alarm_manager

    def run(self):
        if self.estado.get_flag("PARO_EMERGENCIA"):
            # ALL_OFF limitado: no esperar el ACK en cada tick (A-7)
            self.set_do.apagar_por_paro()
            self.alarm_manager.report(Alarm(
                alarm_id="PARO_EMERGENCIA",
                alarm_type=AlarmType.EMERGENCIA,
                source_state="HIBERNACION",
                description=f"Paro de emergencia activado en estado HIBERNACION. {AVISO_CABLEADO_NC}",
                recoverable=False,
            ))
            self.set_do.buzer_emergencia()

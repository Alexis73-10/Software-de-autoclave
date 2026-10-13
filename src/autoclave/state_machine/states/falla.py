import logging
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
from autoclave.devices.paro_emergencia.paro_emergencia import AVISO_CABLEADO_NC

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
            # §5.9 (OPC-23): un reconocimiento con el paro activo se descarta;
            # tras soltar el paro hay que reconocer de nuevo
            if self.estado.get_flag("RESET_FALLA"):
                self.estado.set_flag("RESET_FALLA", False)
                logger.warning("FallaState: RESET_FALLA descartado con el paro de emergencia activo")
            # ALL_OFF limitado: no esperar el ACK en cada tick (A-7)
            self.set_do.apagar_por_paro()
            self.alarm_manager.report(Alarm(
                alarm_id="PARO_EMERGENCIA",
                alarm_type=AlarmType.EMERGENCIA,
                source_state="FALLA",
                description=f"Paro de emergencia activado en estado FALLA. {AVISO_CABLEADO_NC}",
                recoverable=False,
            ))
            self.set_do.buzer_emergencia()
            return False

        if self.estado.get_flag("RESET_FALLA"):
            self.estado.set_flag("RESET_FALLA", False)
            logger.info("FallaState: reset solicitado → transicionando a PREPARACION")
            return True

        return False

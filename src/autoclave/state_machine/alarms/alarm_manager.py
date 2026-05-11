import logging
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType

logger = logging.getLogger(__name__)


class AlarmManager:
    def __init__(self, estado):
        self.estado = estado
        # Lista compartida de alarmas activas del sistema
        self.active_alarms = self.estado.Alarmas_activas

    def report(self, alarm: Alarm):
        #print("alarm manager:", self.active_alarms)
        if alarm is None:
            return

        # Evitar alarmas duplicadas por ID
        if any(a.id == alarm.id for a in self.active_alarms):
            return

        self.active_alarms.append(alarm)
        logger.info(f"Alarma reportada: {alarm.id} - {alarm.description}")

        # Logging según severidad
        if alarm.type == AlarmType.EMERGENCIA:
            logger.critical(f"ALARMA EMERGENCIA: {alarm.id} - {alarm.description}")
        elif alarm.type == AlarmType.FALLA:
            logger.error(f"ALARMA FALLA: {alarm.id} - {alarm.description}")
        else:
            logger.warning(f"ALARMA ALERTA: {alarm.id} - {alarm.description}")

    def clear(self, alarm_id: str):
        before = len(self.active_alarms)

        self.active_alarms[:] = [
            a for a in self.active_alarms
            if a.id != alarm_id
        ]

        if len(self.active_alarms) < before:
            logger.info(f"Alarma despejada: {alarm_id}")

    def clear_recoverable(self):
        # El criterio vive en la alarma, no aquí
        self.active_alarms[:] = [
            a for a in self.active_alarms
            if not a.is_auto_clearable()
        ]

    def has_emergency(self) -> bool:
        return any(a.type == AlarmType.EMERGENCIA for a in self.active_alarms)

    def has_failure(self) -> bool:
        return any(a.type == AlarmType.FALLA for a in self.active_alarms)

    def has_alert(self) -> bool:
        return any(a.type == AlarmType.ALERTA for a in self.active_alarms)

    def has_blocking_alarm(self) -> bool:
        return any(a.blocks_operation for a in self.active_alarms)

    def has_active_alarms(self) -> bool:
        return bool(self.active_alarms)

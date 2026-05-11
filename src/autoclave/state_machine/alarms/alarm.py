from autoclave.state_machine.alarms.alarm_types import AlarmType


class Alarm:
    def __init__(
        self,
        alarm_id: str,
        alarm_type: AlarmType,
        source_state: str,
        description: str = "",
        recoverable: bool = False,
        blocks_operation: bool = True,
    ):
        self.id = alarm_id
        self.type = alarm_type
        self.source_state = source_state
        self.description = description
        self.recoverable = recoverable
        self.blocks_operation = blocks_operation
        self.active = True

    def clear(self):
        self.active = False

    def is_auto_clearable(self) -> bool:
        """
        Indica si la alarma puede limpiarse automáticamente.
        Solo las ALERTAS recuperables deberían entrar aquí.
        """
        return (
            self.type == AlarmType.ALERTA
            and self.recoverable
        )


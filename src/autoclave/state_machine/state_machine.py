from autoclave.state_machine.machine.eum_global import GlobalState
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state
from autoclave.state_machine.states.ciclo import CicloState
from autoclave.state_machine.states.falla import FallaState
from autoclave.state_machine.states.emergencia import emergencia_run
from autoclave.state_machine.states.hibernacion import hibernacion_run
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
import logging

logger = logging.getLogger(__name__)


class StateMachine:
    def __init__(self, io, estado, set_do, cycle, config):
        self.io            = io
        self.estado        = estado
        self.set_do        = set_do
        self.cycle         = cycle
        self.config        = config

        self.alarm_manager = AlarmManager(estado)

        self.preparacion = preparacion_state(self.alarm_manager, estado, set_do, cycle, config)
        self.preparado   = preparado_state(self.alarm_manager, estado, set_do, cycle, config)
        self.ciclo       = CicloState(estado, set_do, cycle, config, self.alarm_manager)
        self.falla       = FallaState(estado)

        self.prev_state  = None

    # ------------------------------------------------------------------
    # Entry hook — llamado UNA vez al cambiar de estado
    # ------------------------------------------------------------------

    def on_state_entry(self, state: GlobalState):
        if state == GlobalState.PREPARACION:
            self.preparacion.reset()

        elif state == GlobalState.CICLO:
            # Limpiar flags de ciclo anteriores y arrancar el pipeline
            self.estado.set_flag("CICLO_CANCELADO",  False)
            self.estado.set_flag("CICLO_CONFIRMADO", False)
            self.estado.set_flag("LISTO_PARA_CICLO", False)
            self.ciclo.reset()
            logger.info("StateMachine: entrando a CICLO")

        elif state == GlobalState.PREPARADO:
            # Limpiar flag de inicio para evitar auto-arranques
            self.estado.set_flag("START_CICLO", False)
            logger.info("StateMachine: entrando a PREPARADO")

    # ------------------------------------------------------------------
    # Tick principal
    # ------------------------------------------------------------------

    def update(self):
        current_state = self.estado.get_machine_state()

        logger.debug(
            "Actualizando maquina de estados. Estado actual: %s",
            self.estado.estado_maquina.get("Estado")
        )

        # Detectar cambio de estado → disparar hook de entrada
        if current_state != self.prev_state:
            self.on_state_entry(current_state)
            self.prev_state = current_state

        # ==============================================================
        # PREPARACION
        # ==============================================================
        if current_state == GlobalState.PREPARACION:
            logger.debug("Estado actual: PREPARACION")

            if self.preparacion.run():
                self.estado.set_machine_state(GlobalState.PREPARADO)

        # ==============================================================
        # PREPARADO
        # ==============================================================
        elif current_state == GlobalState.PREPARADO:
            logger.debug("Estado actual: PREPARADO")

            listo = bool(self.preparado.run())
            self.estado.set_flag("LISTO_PARA_CICLO", listo)

            # Transición a CICLO: sólo si el sistema está listo Y
            # el operador pulsó "Iniciar ciclo"
            if listo and self.estado.get_flag("START_CICLO"):
                self.estado.set_flag("START_CICLO", False)
                self.estado.set_machine_state(GlobalState.CICLO)

        # ==============================================================
        # CICLO
        # ==============================================================
        elif current_state == GlobalState.CICLO:
            logger.debug("Estado actual: CICLO")

            resultado = self.ciclo.run()

            if resultado == "COMPLETADO":
                logger.info("StateMachine: ciclo completado → PREPARADO")
                self.estado.set_machine_state(GlobalState.PREPARADO)

            elif resultado == "FALLO":
                logger.error("StateMachine: fallo en ciclo → FALLA")
                self.estado.set_machine_state(GlobalState.FALLA)

            elif resultado == "CANCELADO":
                logger.warning("StateMachine: ciclo cancelado → PREPARADO")
                self.estado.set_machine_state(GlobalState.PREPARADO)

            # "EN_CURSO" o "ESPERANDO_CONFIRMACION" → no hacer nada, seguir en CICLO

        # ==============================================================
        # FALLA
        # ==============================================================
        elif current_state == GlobalState.FALLA:
            logger.debug("Estado actual: FALLA")
            if self.falla.run():
                self.estado.Alarmas_activas.clear()
                self.estado.fase_ciclo = ""
                self.estado.set_machine_state(GlobalState.PREPARACION)

        # ==============================================================
        # EMERGENCIA
        # ==============================================================
        elif current_state == GlobalState.EMERGENCIA:
            logger.debug("Estado actual: EMERGENCIA")
            emergencia_run()

        # ==============================================================
        # HIBERNACION
        # ==============================================================
        elif current_state == GlobalState.HIBERNACION:
            logger.debug("Estado actual: HIBERNACION")
            hibernacion_run()

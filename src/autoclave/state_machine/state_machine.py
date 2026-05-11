from autoclave.state_machine.machine.eum_global import GlobalState
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state
from autoclave.state_machine.states.ciclo import ciclo_run
from autoclave.state_machine.states.falla import falla_run
from autoclave.state_machine.states.emergencia import emergencia_run
from autoclave.state_machine.states.hibernacion import hibernacion_run
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
import logging 

logger = logging.getLogger(__name__)

class StateMachine:
    def __init__(self, io, estado, set_do, cycle, config): 
        self.io = io
        self.config = config
        self.alarm_manager = AlarmManager(estado)
        self.preparacion = preparacion_state(self.alarm_manager, estado, set_do, cycle, config)
        self.preparado = preparado_state(self.alarm_manager, estado, set_do, cycle, config)
        self.estado = estado
        self.cycle_number = 0
        self.alert_active = False
        self.prev_state = None


    
    def on_state_entry(self, state):
        if state == GlobalState.PREPARACION:
            self.preparacion.reset()
    
    #==============================
    #MAQUINA DE ESTADOS GLOBAL
    #==============================
    
    def update (self):
        current_state = self.estado.get_machine_state()

        logger.debug(f"Actualizando maquina de estados. Estado actual: {self.estado.estado_maquina['Estado']}")

        if current_state != self.prev_state:
            self.on_state_entry(current_state)
            self.prev_state = current_state


        #==========================
        #PREPARACION
        #==========================
        if current_state == GlobalState.PREPARACION:
            logger.debug("Estado actual: PREPARACION")

            if self.preparacion.run():
                self.estado.set_machine_state(GlobalState.PREPARADO)
                

        #=========================
        #PREPARADO
        #=========================
        elif current_state == GlobalState.PREPARADO:
            logger.debug("Estado actual: STANDBY")
        
            preparado = self.preparado.run()

            if preparado:
                self.estado.set_flag("LISTO_PARA_CICLO", True)
            else:
                self.estado.set_flag("LISTO_PARA_CICLO", False)


        elif current_state == GlobalState.CICLO:
            logger.debug("Estado actual: CICLO")
            # Aquí iría la llamada a la función correspondiente al estado CICLO
            ciclo_run(self)
            
        elif current_state == GlobalState.FALLA:
            logger.debug("Estado actual: FALLA")
            # Lógica para el estado FALLA
            falla_run(self)
        
        elif current_state == GlobalState.EMERGENCIA:
            logger.debug("Estado actual: EMERGENCIA")
            # Lógica para el estado EMERGENCIA
            emergencia_run(self)
        
        elif current_state == GlobalState.HIBERNACION:
            logger.debug("Estado actual: HIBERNACION")
            # Lógica para el estado HIBERNACION
            hibernacion_run(self)
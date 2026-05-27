#aqui vienen las abstracciones fisicas de las puertas
#No habla directamente con el serial, eso lo hace el modulo de hardware
#aqui se definiran:
#- estados
#- validaciones
#- timers
#- deteccion de errores
#esto es logica de maquina, no logica de hardware ni de comunicacion
#rol:
#- define que es una puerta
#- mapea sensores y actuadores asociados a la puerta
#- interpreta estados de la puerta en status.py
#- mantiene estados logico: abiertos/cerrados/erroneos/en transicion
#- detecta inconsistencias y errores en la puerta
#- maneja timaouts y fallos asociados a la puerta
#aqui vive la logica de la puerta


#Aqui estara la maquina de estados de la puerta

#Maquina de estados :
#Entradas 
    # * Posición
    #    * DI3        Puerta 1 cerrada
    #    * DI4         Puerta 1 abierta
    # * Seguridad
    #    * DI7         Atrapamiento 1
    # * Condición
    #    * AI11         Presión del empaque 1 ( Bloqueo )




# Salidas
    # * DO19         Bomba de Vacío
    # * DO20        Actuador 1 apertura
    # * DO9        Vacio empaque 1
    # * DO11        Aire comprimido empaque 1
    # * DO22         Actuador 1 cierre


# Parámetros
    # * Presión atmosférica
    # * Tiempo de apertura
    # * Tiempo de cierre
    # * Presion baja de empaque


# Acciones
    # * Desbloquear
    # * Bloquear
    # * Abrir
    # * Cerrar
    # * Rebote-atrapamiento


# Eventos
    # * Comando Abrir
    # * Comando Cerrar
    # * Atrapamiento detectado
    # * Tiempo agotado
    # * Apertura Detectada
    # * Cierre detectado


# Estados
    # * Desconocido
    #    * Salidas 
    #       * Ninguna
    #    * Entradas
    #       * Puerta cerrada 1 = 0
    #       * Puerta abierta 1 = 0
    #       * Atrapamiento 1 = 0
    #    * Eventos
    #       * Comando Abrir
    # * Cerrada
    #    * Salidas
    #       * ninguna
    #    * Entradas
    #       * Puerta cerrada 1 = 1
    #       * Puerta abierta 1 = 0
    #       * Presión Empaque 1 >= 300 kPa
    #    * Eventos
    #       * Comando Abrir
    # * Abierta
    #    * Salidas
    #       * Ninguna
    #    * Entradas
    #       * Puerta cerrada 1 = 0
    #       * Puerta abierta 1 = 1
    #    * Eventos 
    #       * Comando cerrar
    # * Cerrando
    #    * Salidas
    #       * Bomba de vacío
    #       * Vacio empaque
    #       * Actuador de Cierre
    #    * Entradas
    #       * Puerta cerrada 1 = 0 
    #       * Puerta abierta 1 = 0
    #       * Presión empaque 1 < Presión atmosférica
    #    * Eventos
    #       * Cierre detectado
    #       * Atrapamiento detectado
    #       * Tiempo agotado
    # * Abriendo
    #    * Salidas
    #       * Bomba de vacío
    #       * Vacio empaque
    #       * Actuador de apertura
    #    * Entradas
    #       * Puerta cerrada 1 = 0
    #       * Puerta abierta 1 = 0
    #       * Presión empaque 1 < Presión atmosférica
    #    * Eventos 
    #       * Cierre detectado
    #       * Tiempo agotado
    # * Error
    # * Atrapada
    #    * Salidas
    #       * ninguna
    #    * Entradas
    #       * Atrapamiento 1 = 1
    #    * Eventos
    #       * Apertura automatica


# Transiciones
    # * Desconocido -> Abriendo
    # * Abriendo -> Abierta
    # * Abierta -> Cerrando
    # * Cerrando -> Cerrado
    # * Cerrada -> Abriendo
    # * Abriendo -> Error
    # * Cerrando -> Error
    # * Cerrando -> Atrapada
    # * Atrapada -> Abriendo
    
# Timers
    # * Tiempo de apertura
    # * Tiempo de cierre
    
# Errores
    # * Tiempo de apertura agotado
    # * Tiempo de cierre agotado
    # * Inconsistencia de sensores

# Idea base antes de codigo:
    #La puerta debe porder decir en que estado esta
    #Que evento ocurrio
    #Que accion se esta realizando
    #A que estado nuevo pasar 
    
#Enum de estados de la puerta (Claridad absoluta)
#Nada de strings sueltos
#Esto evita errores tontos y hace el debug legible

from autoclave.devices.puertas.enum_doors import DoorState
from autoclave.devices.puertas.base_puertas import Door
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
import logging
import time


logger = logging.getLogger(__name__)

#============================
# CLASE PUERTA
#============================
class AdvancedDoor(Door):
    def __init__(self, name, di, do, ai, estado, setdo, config, alarm_manager):
        # io: objeto que sabe escribir salidas digitales (hardware/mock)
        self.config = config
        self.name = name
        self.di = di
        self.do = do
        self.ai = ai
        self.estado = estado
        self.set_do = setdo
        self.alarm_manager = alarm_manager

        self.timer_start = None
        self._estabilizacion_start = None
        self._pulso_bloqueo_enviado = False
        self._pulso_desbloqueo_enviado = False
    #============================
    #LECTURA DE ENTRADAS
    #============================
    
    def puerta_abierta(self, ):
        val =self.estado.sensores_di.get(self.di["abierta"])
        return val if val is not None else False
    
    def puerta_cerrada(self, ):
        val = self.estado.sensores_di.get(self.di["cerrada"])
        return val if val is not None else False
    
    def atrapamiento(self, ):
        val = self.estado.sensores_di.get(self.di["atrapamiento"])
        return val if val is not None else False
    
    def presion_empaque(self, ):
        val = self.estado.sensores_pres.get(self.ai["presion_empaque"])
        return val if val is not None else 0.0

    #============================
    #ACCIONES (SALIDAS)
    #============================
    
    #Activa actuador de apertura
    def abrir_on (self):
        self.set_do.set_output(self.do["abrir"], True)
        #logger.info("Actuador de apertura activado.")

    #Desactiva actuador de apertura
    def abrir_off (self):
        self.set_do.set_output(self.do["abrir"], False)
        #logger.info("Actuador de apertura desactivado.")
        

    #Activa actuador de cierre
    def cerrar_on (self):
        self.set_do.set_output(self.do["cerrar"], True)
        #logger.info("Actuador de cierre activado.")
        
    #Desactiva actuador de cierre
    def cerrar_off (self):
        self.set_do.set_output(self.do["cerrar"], False)
        #logger.info("Actuador de cierre desactivado.")
        
        
    #Bloquea la puerta (Aire comprimido al empaque)
    def bloquear_on(self):
        self.set_do.set_output(self.do["bloquear"], True)
        #logger.info("Bloqueo de puerta activado.")
        
        
    def bloquear_off(self):
        self.set_do.set_output(self.do["bloquear"], False)
        #logger.info("Bloqueo de puerta desactivado.")
        
        
    #Desbloquea la puerta (Corta aire comprimido al empaque)
    def desbloquear_on(self):
        self.set_do.set_output(self.do["desbloquear"], True)
        #logger.info("Desbloqueo de puerta activado.")
        
    
    def desbloquear_off(self):
        self.set_do.set_output(self.do["desbloquear"], False)
        #logger.info("Desbloqueo de puerta desactivado.")
        
    #Bomba encendida
    def vacio_on(self):
        self.set_do.bomba_vacio_on()
        #logger.info("Bomba de vacio encendida.")

        
    #Bomba apagada
    def vacio_off(self):
        self.set_do.bomba_vacio_off()
        #logger.info("Bomba de vacio apagada.")
        
    #============================
    #MAQUINA DE ESTADOS
    #============================
    
    def get_state(self):
        return self.estado.get_door_state(self.name)

    def set_state(self, new_state):
        self.estado.update_door_state(self.name, new_state)

    
    
    def update(self):
        #Lógica de transición de estados basada en entradas y eventos
        if self.get_state() is None:
            logger.error("Error: Estado de puerta no definido.")
            self.set_state(DoorState.DESCONOCIDO)
            return       
        elif self.get_state() == DoorState.DESCONOCIDO:
            logger.info("Estado actual: DESCONOCIDO.")
            # Lógica para manejar transiciones desde DESCONOCIDO
            self._from_desconocido()
        
        elif self.get_state() == DoorState.CERRADO:
            #logger.info("Estado actual: CERRADO.")
            # Lógica para manejar comandos y transiciones desde CERRADO
            self._from_cerrado()
        
        elif self.get_state() == DoorState.ABIERTO:
            #logger.info("Estado actual: ABIERTO.")
            # Lógica para manejar comandos y transiciones desde ABIERTO
            self._from_abierto()
        
        elif self.get_state() == DoorState.CERRANDO:
            #logger.info("Estado actual: CERRANDO.")
            # Lógica para manejar transiciones desde CERRANDO
            self._from_cerrando()
        
        elif self.get_state() == DoorState.ABRIENDO:
            #logger.info("Estado actual: ABRIENDO.")
            # Lógica para manejar transiciones desde ABRIENDO
            self._from_abriendo()
        
        elif self.get_state() == DoorState.ATRAPADA:
            #logger.info("Estado actual: ATRAPADA.")
            # Lógica para manejar transiciones desde ATRAPADA
            self._from_atrapada()
        
        elif self.get_state() == DoorState.ERROR:
            #logger.info("Estado actual: ERROR.")
            # Lógica para manejar transiciones desde ERROR
            self._from_error()
            
    #============================
    #TRANSICIONES DE ESTADOS
    #============================
    
    def _from_desconocido(self):
        abierta = self.puerta_abierta()
        cerrada = self.puerta_cerrada()

        if abierta and not cerrada:
            self.vacio_off()
            self.set_state(DoorState.ABIERTO)
            return

        if cerrada and not abierta:
            # estabilización no bloqueante
            if self._estabilizacion_start is None:
                self._estabilizacion_start = time.time()
                return  # esperar al próximo ciclo

            if time.time() - self._estabilizacion_start < 0.3:
                return  # aún esperando

            self._estabilizacion_start = None  # reset
            bloqueo = self.presion_empaque()
            if bloqueo >= self.config.get("presion_empaque"):
                self.set_state(DoorState.CERRADO)
            else:
                self.set_state(DoorState.CERRANDO)
            return

        self.set_state(DoorState.ERROR)
        logger.error(f"Error: Estado inicial de puerta inconsistente.")

    
    def _from_abriendo(self):
        safe_mode = self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO")

        if self.timer_start is None:
            self.timer_start = time.time() + self.config.get("timeout_puerta")
            self._pulso_desbloqueo_enviado = False
            self.bloquear_off()
            self.cerrar_off()
            if safe_mode:
                self.alarm_manager.report(Alarm(
                    alarm_id="ABRIENDO_MODO_SEGURO",
                    alarm_type=AlarmType.ALERTA,
                    source_state="PUERTA",
                    description=f"Puerta {self.name}: abriendo en modo seguro (sin bomba de vacío).",
                    recoverable=True,
                ))
            else:
                self.vacio_on()
            self.desbloquear_on()
            logger.info("Iniciando apertura de puerta%s.", " (modo seguro)" if safe_mode else "")
            return

        if not self._pulso_desbloqueo_enviado:
            self.desbloquear_off()
            self._pulso_desbloqueo_enviado = True

        umbral = (
            (self.config.get("presion_admosferica") or 101.3) +
            (self.config.get("rango_presion_atm") or 20.0)
            if safe_mode
            else self.config.get("vacio_empaque")
        )

        if self.presion_empaque() <= umbral:
            self.abrir_on()

        if self.puerta_abierta() and not self.puerta_cerrada():
            self.abrir_off()
            self.vacio_off()
            self.alarm_manager.clear("ABRIENDO_MODO_SEGURO")
            self.timer_start = None
            self._pulso_desbloqueo_enviado = False
            self.set_state(DoorState.ABIERTO)
            logger.info("Puerta abierta correctamente.")
            return

        if time.time() > self.timer_start:
            self.abrir_off()
            self.vacio_off()
            self.alarm_manager.clear("ABRIENDO_MODO_SEGURO")
            self.timer_start = None
            self._pulso_desbloqueo_enviado = False
            self.set_state(DoorState.ERROR)
            logger.error("Error: Tiempo de apertura agotado.")
    
    def _from_abierto(self):
        # Apaga actuadores propios de esta puerta (no la bomba de vacío que es compartida)
        self.abrir_off()
        self.cerrar_off()
        self.desbloquear_off()
        self.bloquear_off()
        if not self.puerta_abierta():
            self.set_state(DoorState.ERROR)
            logger.error("Error: Inconsistencia detectada, puerta no está abierta.")
            return
        if self.puerta_cerrada():
            self.set_state(DoorState.ERROR)
            logger.error("Error: Inconsistencia detectada, puerta no puede estar abierta y cerrada a la vez.")
            return
    
    def _from_cerrado(self):
        self.cerrar_on()
        if not self.puerta_cerrada():
            self.set_state(DoorState.ERROR)
            logger.error("Error: Inconsistencia detectada, puerta no está cerrada.")
            return
        if self.puerta_abierta():
            self.set_state(DoorState.ERROR)
            logger.error("Error: Inconsistencia detectada, puerta no puede estar abierta y cerrada a la vez.")
            return
        if self.presion_empaque() < self.config.get("presion_empaque"):
            self.bloquear_on()
            logger.warning(f"Puerta {self.name}: presión de empaque baja, re-presurizando.")
        else:
            self.bloquear_off()
        
    
    def _from_cerrando(self):
        safe_mode = self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO")

        if self.timer_start is None:
            self.timer_start = time.time() + self.config.get("timeout_puerta")
            self._pulso_bloqueo_enviado = False
            self._pulso_desbloqueo_enviado = False
            if safe_mode:
                self.alarm_manager.report(Alarm(
                    alarm_id="ABRIENDO_MODO_SEGURO",
                    alarm_type=AlarmType.ALERTA,
                    source_state="PUERTA",
                    description=f"Puerta {self.name}: cerrando en modo seguro (sin bomba de vacío).",
                    recoverable=True,
                ))
            else:
                self.vacio_on()
            self.desbloquear_on()
            logger.info("Iniciando cierre de puerta%s.", " (modo seguro)" if safe_mode else "")

        if not self._pulso_desbloqueo_enviado:
            self.desbloquear_on()
            self._pulso_desbloqueo_enviado = True

        if self.atrapamiento() == 1:
            self.cerrar_off()
            self.alarm_manager.clear("ABRIENDO_MODO_SEGURO")
            self.timer_start = None
            self._pulso_bloqueo_enviado = False
            self._pulso_desbloqueo_enviado = False
            self.set_state(DoorState.ATRAPADA)
            return

        umbral = (
            (self.config.get("presion_admosferica") or 101.3) +
            (self.config.get("rango_presion_atm") or 20.0)
            if safe_mode
            else self.config.get("vacio_empaque")
        )

        if self.presion_empaque() <= umbral and not self.puerta_cerrada():
            self.cerrar_on()

        if self.puerta_cerrada() and not self.puerta_abierta():
            self.desbloquear_off()
            self.vacio_off()
            self.bloquear_on()

            if self.presion_empaque() >= self.config.get("presion_empaque"):
                self.bloquear_off()
                self.alarm_manager.clear("ABRIENDO_MODO_SEGURO")
                self.timer_start = None
                self.set_state(DoorState.CERRADO)
                logger.info("Puerta cerrada correctamente.")
                return

        if time.time() > self.timer_start:
            self.cerrar_off()
            self.vacio_off()
            self.desbloquear_off()
            self.bloquear_off()
            self.alarm_manager.clear("ABRIENDO_MODO_SEGURO")
            self._pulso_bloqueo_enviado = False
            self.timer_start = None
            self.set_state(DoorState.ERROR)
            logger.error("Error: Tiempo de cierre agotado.")
            

    def _from_atrapada(self):
        self.cerrar_off()
        self.timer_start = None
        logger.info("Puerta atrapada, intentando apertura automática.")
        
        if not self.puerta_abierta() :
            self.set_state(DoorState.ABRIENDO)
            logger.info("Iniciando apertura automática de puerta atrapada.")
        
        else:
            self.vacio_off()
            self.set_state(DoorState.ABIERTO)
            logger.info("Puerta liberada y abierta correctamente.")
        
    def _from_error(self):
        #intenta recuperar a estado conocido
        abierta = self.puerta_abierta()
        cerrada = self.puerta_cerrada()
        
        if abierta and not cerrada:
            self.vacio_off()
            self.set_state(DoorState.ABIERTO)
            logger.info("Recuperación de error: Estado detectado ABIERTO.")
            return
        
        if cerrada and not abierta:
            
            if self._estabilizacion_start is None:
                self._estabilizacion_start = time.time()
                return  # esperar al próximo ciclo
            
            if time.time() - self._estabilizacion_start < 0.3:
                return  # aún esperando
            
            self._estabilizacion_start = None  # reset
            bloqueo = self.presion_empaque()
            if bloqueo >= self.config.get("presion_empaque"):
                self.set_state(DoorState.CERRADO)
                logger.info("Recuperación de error: Estado detectado CERRADO.")
                return
            
            else:
                #self.state = DoorState.CERRANDO
                #logger.warning("Recuperación de error: Estado inconsistente, iniciando cierre.")
                return
            
        self.set_state(DoorState.ERROR)
        logger.error("Error persistente: Estado de puerta inconsistente.")
        
        
    #============================
    #COMANDOS EXTERNOS
    #============================
    
    def cmd_abrir(self):
        self.set_state(DoorState.ABRIENDO)
            
    def cmd_cerrar(self):
        if self.get_state() == DoorState.ABIERTO:
            self.set_state(DoorState.CERRANDO)
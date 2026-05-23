# preparacion.py
from autoclave.state_machine.machine.parametros_gobales import parametros_globales
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType 
import logging

logger = logging.getLogger(__name__)

class preparacion_state:
    def __init__(self, alarm_manager, estado, set_do, cycle, config):
        self.step = 0
        self.alarm_manager = alarm_manager
        self.estado = estado
        self.set_do = set_do
        self.cycle = cycle
        self.config = config

    #definicion del estado preparacion:
    # - Realizar la verificacion inicial del equipo.
        # - verificar todas señales de sensores 
        # - verificar suministro de servicios (vapor, agua, aire comprimido)
    # - Preparar el equipo para el ciclo 
        # - suministrar vapor a la chaqueta 
            #- para esto requiere verificar que exista suministro de vapor
        # - verificar la presion de la camara de autoclave
            # -igualar la presion a la atmosferica si es necesario
        # - verificar si la camara tiene agua residual
            # - drenar si es necesario
    # verificar temperatura de drenaje
        # - enfriar si es necesario

    #==============================
    # VERIFICACION INICIAL (SENSORES)
    #==============================
    # Verificar que todos los sonsores esten en funcionamiento (sin importar su valor)
    # - no pueden estar en 0 (fallo de sensor)
    
    def alarm (self, alarm_id, alarm_type):
        alarm = Alarm(
            alarm_id=alarm_id,
            alarm_type=alarm_type,
            source_state="PREPARACION",
            description=f"Fallo {alarm_id} en  PREPARACION.",
            recoverable=True
        )
        self.alarm_manager.report(alarm)
    
    def run(self):
        
        if not self.supervisor():
            self.step = 0
            return False
        
        
        return self.ejecutor()
        
            
    def supervisor(self) -> bool:
        ok = True
        if not self.verificar_sensores():
            ok = False
        if not self.verificar_suministros():
            ok = False
            
        return ok
    
    def ejecutor(self):
        logger.info(f"Ejecución del estado PREPARACION, paso {self.step}")
        if self.estado.sensores_di["paro_emergencia"]:
            self.set_do.reset_all_outputs()
            self.alarm("PARO_EMERGENCIA", AlarmType.EMERGENCIA)
            self.set_do.buzer_emergencia()
            return

        else:
            self.set_do.buzer_off()
            self.alarm_manager.clear("PARO_EMERGENCIA")


        if self.step == 0:
                self.step = 1
        
        elif self.step == 1:
                self.step = 2
        
        elif self.step == 2:
            if self.suministrar_vapor_chaqueta():
                self.step = 3
                
        elif self.step == 3:
            if self.igualar_presion_camara():
                self.step = 4
                
        elif self.step == 4:
            if self.drenar_camara():
                self.step = 5
                
        elif self.step == 5:
            if self.verificar_temperatura_drenaje():
                return True  # Indica que la preparación ha finalizado
            
        return False
    
    def verificar_sensores(self):
            #==============================

            sensores_presion = [
                "pres_camara",
                "pres_chaqueta",
                "pres_empaque_1",
                "pres_empaque_2",
            ]
            
            sensores_temperatura = [
                "temp_camara",
                "temp_2_camara",
                "temp_ref",
                "temp_chaqueta",
                "temp_drenaje_cam",
                "temp_drenaje",
            ]
            ok=True
            for sensor in sensores_presion:
                pres_value = self.estado.sensores_pres[sensor]
                if pres_value == 0:
                    alarm_id = f"ERROR_AI_{sensor.upper()}"
                    self.alarm(alarm_id, AlarmType.ALERTA)
                    logger.info(f"Alarma generada: {alarm_id}")
                    ok = False
                else:
                    self.alarm_manager.clear(f"ERROR_AI_{sensor.upper()}")
                
            for sensor in sensores_temperatura:
                temp_value = self.estado.sensores_temp[sensor]
                if temp_value == 0:
                    alarm_id = f"ERROR_AI_{sensor.upper()}"
                    self.alarm(alarm_id, AlarmType.ALERTA)
                    logger.info(f"Alarma generada: {alarm_id}")
                    ok = False
                else:
                    self.alarm_manager.clear(f"ERROR_AI_{sensor.upper()}")
                
            return ok
        
    def verificar_suministros(self):
        suministros = [
            "vapor_suministro",
            "agua_bomba",
            "agua_generador",
            "aire_comprimido",
        ]
        ok=True
        for suministro in suministros:
            estado_suministro = self.estado.sensores_di[suministro]
            if not estado_suministro:
                alarm_id = f"SUMINISTRO_{suministro.upper()}"
                self.alarm(alarm_id, AlarmType.ALERTA)
                logger.info(f"Alarma generada: {alarm_id}")
                ok = False
            else:
                self.alarm_manager.clear(f"SUMINISTRO_{suministro.upper()}")

        return ok
                
        #==============================
        # PREPARACION DEL EQUIPO
        #==============================
        # se deben cumplir las siguientes condiciones:
        # Suministrar presion de vapor a la chaqueta segun el ciclo seleccionado
        # Verificar presion de la camara igual a la atmosferica
        # Verificar que no haya agua residual en la camara
        # Verificar temperatura de drenaje
    
    def suministrar_vapor_chaqueta(self):
            presion = self.estado.sensores_pres["pres_chaqueta"]
            pres_obj=self.cycle.get_param("globals","presion_chaqueta")
            rango=self.cycle.get_param("globals","rango_presion_chaqueta")

            limite_inf = pres_obj - rango
            limite_sup = pres_obj + rango

            # Verificar suministro
            if not self.estado.sensores_di["vapor_suministro"]:
                alarm_id = "SUMINISTRO_VAPOR"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False
            else:
                self.alarm_manager.clear("SUMINISTRO_VAPOR")

            # Presión dentro de rango → listo
            if limite_inf <= presion <= limite_sup:
                self.set_do.vapor_chaqueta_off()
                self.alarm_manager.clear("CHAQUETA_FRIA")
                self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")
                return True

            # Presión baja → abrir vapor
            if presion < limite_inf:
                self.set_do.vapor_chaqueta_on()
                alarm_id = "CHAQUETA_FRIA"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False

            # Presión alta → cerrar vapor
            elif presion >= limite_sup:
                self.set_do.vapor_chaqueta_off()
                alarm_id = "CHAQUETA_SOBRECALENTADA"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False
    
    def igualar_presion_camara(self):
            presion_camara = self.estado.sensores_pres["pres_camara"]
            presion_atmosferica = self.config.get("presion_admosferica")
            rango_presion_atmosferica = self.config.get("rango_presion_atm")
            pres_cam_min = presion_atmosferica - rango_presion_atmosferica
            pres_cam_max = presion_atmosferica + rango_presion_atmosferica

            if pres_cam_min <= presion_camara <= pres_cam_max:
                # Presión igualada
                self.set_do.aire_admosferico_camara_off()
                self.set_do.descompresion_lenta_off()
                self.alarm_manager.clear("PRESION_CAMARA_BAJA")
                self.alarm_manager.clear("PRESION_CAMARA_ALTA")
                return True

            if presion_camara < presion_atmosferica - rango_presion_atmosferica:
                # Abrir entrada de aire comprimido a la camara
                self.set_do.descompresion_rapida_off()
                self.set_do.aire_admosferico_camara_on()
                alarm_id = "PRESION_CAMARA_BAJA"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False
            
            elif presion_camara > presion_atmosferica + rango_presion_atmosferica:
                # Activar bomba de vacio
                self.set_do.aire_admosferico_camara_off()
                self.set_do.descompresion_rapida_on()
                alarm_id = "PRESION_CAMARA_ALTA"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False
                
    def drenar_camara(self):
            agua_residual = self.estado.sensores_di["agua_camara"]
            if not agua_residual:
                self.set_do.descompresion_rapida_off()
                self.alarm_manager.clear("AGUA_RESIDUAL_CAMARA")
                return True

            self.set_do.descompresion_rapida_on()
            alarm_id = "AGUA_RESIDUAL_CAMARA"
            self.alarm(alarm_id, AlarmType.ALERTA)
            return False
        
    def verificar_temperatura_drenaje(self):
            temp_drenaje = self.estado.sensores_temp["temp_drenaje"]
            temp_segura = self.config.get("temp_segura_drenaje")
            if temp_drenaje <= temp_segura:  # Suponiendo 40°C como temperatura segura
                self.set_do.agua_intercambiador_off()
                self.alarm_manager.clear("TEMPERATURA_DRENAJE_ALTA")
                return True

            self.set_do.agua_intercambiador_on()
            alarm_id = "TEMPERATURA_DRENAJE_ALTA"
            self.alarm(alarm_id, AlarmType.ALERTA)
            return False
        
    def reset(self):
        self.step = 0
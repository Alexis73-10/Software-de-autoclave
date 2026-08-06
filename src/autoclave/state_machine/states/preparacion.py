# preparacion.py
from autoclave.state_machine.machine.parametros_globales import parametros_globales
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
from autoclave.state_machine.states.control_banda import evaluar_banda, ConfirmadorApagado
import logging

logger = logging.getLogger(__name__)

# Palabra que describe cada nivel de alarma — debe coincidir con lo que se
# imprime como "Nivel:" en el ticket de alarmas (impresion_menu.py), para
# que el texto libre de la descripción no contradiga el nivel real.
_NIVEL_TXT = {
    AlarmType.ALERTA:     "Alerta",
    AlarmType.FALLA:      "Fallo",
    AlarmType.EMERGENCIA: "Emergencia",
}


class preparacion_state:
    def __init__(self, alarm_manager, estado, set_do, cycle, config):
        self.alarm_manager = alarm_manager
        self.estado = estado
        self.set_do = set_do
        self.cycle = cycle
        self.config = config

        # Confirmadores de apagado (evitan chattering de valvula)
        self._confirmador_chaqueta = ConfirmadorApagado()
        self._confirmador_drenaje = ConfirmadorApagado()
        self._confirmador_aire_camara = ConfirmadorApagado()

    #definicion del estado preparacion:
    # Todas las condiciones se evalúan en paralelo, cada tick, sin bloquear
    # unas a otras (mismo patrón que preparado_state):
    # - verificar todas las señales de sensores
    # - verificar suministro de servicios (vapor, agua, aire comprimido)
    # - suministrar vapor a la chaqueta
    # - igualar la presión de cámara a la atmosférica si es necesario
    # - drenar la cámara si tiene agua residual
    # - enfriar el drenaje si su temperatura no es segura
    # PREPARACION termina cuando las 4 condiciones están OK en el mismo tick.

    #==============================
    # VERIFICACION INICIAL (SENSORES)
    #==============================
    # Verificar que todos los sonsores esten en funcionamiento (sin importar su valor)
    # - no pueden estar en 0 (fallo de sensor)
    
    def alarm (self, alarm_id, alarm_type, blocks_operation=True):
        nivel = _NIVEL_TXT.get(alarm_type, "Alerta")
        alarm = Alarm(
            alarm_id=alarm_id,
            alarm_type=alarm_type,
            source_state="PREPARACION",
            description=f"{nivel}: {alarm_id} en PREPARACION.",
            recoverable=True,
            blocks_operation=blocks_operation,
        )
        self.alarm_manager.report(alarm)
    
    def run(self):
        if self.estado.sensores_di["paro_emergencia"]:
            self.set_do.reset_all_outputs()
            self.alarm("PARO_EMERGENCIA", AlarmType.EMERGENCIA)
            self.set_do.buzer_emergencia()
            return False
        else:
            self.set_do.buzer_off()
            self.alarm_manager.clear("PARO_EMERGENCIA")

        if not self.supervisor():
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
        logger.info("Ejecución del estado PREPARACION (paralelo)")

        chaqueta_lista = self.suministrar_vapor_chaqueta()
        presion_ok, quiere_rapida_presion = self.igualar_presion_camara()
        drenaje_ok, quiere_rapida_drenaje = self.drenar_camara()
        temp_ok = self.verificar_temperatura_drenaje()

        if quiere_rapida_presion or quiere_rapida_drenaje:
            self.set_do.descompresion_rapida_on()
        else:
            self.set_do.descompresion_rapida_off()

        return chaqueta_lista and presion_ok and drenaje_ok and temp_ok
    
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

            # Verificar suministro. Si no hay vapor, no insistir en abrir la
            # válvula (generaría vapor demasiado húmedo por baja presión de
            # línea): se deja "pendiente", no bloqueante.
            if not self.estado.sensores_di["vapor_suministro"]:
                self.set_do.vapor_chaqueta_off()
                self._confirmador_chaqueta.reset()
                self.alarm("SUMINISTRO_VAPOR", AlarmType.ALERTA, blocks_operation=False)
                self.alarm_manager.clear("CHAQUETA_FRIA")
                self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")
                return True
            else:
                self.alarm_manager.clear("SUMINISTRO_VAPOR")

            r = evaluar_banda(presion, pres_obj, rango, activar_si_bajo=True)

            # Válvula: reacciona en el objetivo, sin esperar a cruzar la banda.
            if r.debe_activar:
                self.set_do.vapor_chaqueta_on()
                self._confirmador_chaqueta.reset()
            elif self._confirmador_chaqueta.confirmar(True):
                self.set_do.vapor_chaqueta_off()

            # Alarma bloqueante: solo al cruzar el borde de la banda.
            if r.fuera_por_debajo:
                alarm_id = "CHAQUETA_FRIA"
                self.alarm(alarm_id, AlarmType.ALERTA)
            else:
                self.alarm_manager.clear("CHAQUETA_FRIA")

            if r.fuera_por_encima:
                alarm_id = "CHAQUETA_SOBRECALENTADA"
                self.alarm(alarm_id, AlarmType.ALERTA)
            else:
                self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")

            return r.dentro_de_banda
    
    def igualar_presion_camara(self):
            """Retorna (ok, quiere_descompresion_rapida). No acciona la
            válvula descompresion_rapida directamente: esa salida es
            compartida con drenar_camara() y se combina en ejecutor()."""
            presion_camara = self.estado.sensores_pres["pres_camara"]
            presion_atmosferica = self.config.get("presion_admosferica")
            rango_presion_atmosferica = self.config.get("rango_presion_atm")
            pres_cam_min = presion_atmosferica - rango_presion_atmosferica
            pres_cam_max = presion_atmosferica + rango_presion_atmosferica

            if pres_cam_min <= presion_camara <= pres_cam_max:
                # Presión igualada
                if self._confirmador_aire_camara.confirmar(True):
                    self.set_do.aire_admosferico_camara_off()
                self.set_do.descompresion_lenta_off()
                self.alarm_manager.clear("PRESION_CAMARA_BAJA")
                self.alarm_manager.clear("PRESION_CAMARA_ALTA")
                return True, False

            if presion_camara < pres_cam_min:
                # Abrir entrada de aire comprimido a la camara
                self.set_do.aire_admosferico_camara_on()
                self._confirmador_aire_camara.reset()
                alarm_id = "PRESION_CAMARA_BAJA"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False, False

            # presion_camara > pres_cam_max: requiere venteo/vacío
            self.set_do.aire_admosferico_camara_off()
            self._confirmador_aire_camara.reset()
            alarm_id = "PRESION_CAMARA_ALTA"
            self.alarm(alarm_id, AlarmType.ALERTA)
            return False, True
                
    def drenar_camara(self):
            """Retorna (ok, quiere_descompresion_rapida). No acciona la
            válvula descompresion_rapida directamente: esa salida es
            compartida con igualar_presion_camara() y se combina en
            ejecutor()."""
            agua_residual = self.estado.sensores_di["agua_camara"]
            if not agua_residual:
                self.alarm_manager.clear("AGUA_RESIDUAL_CAMARA")
                return True, False

            alarm_id = "AGUA_RESIDUAL_CAMARA"
            self.alarm(alarm_id, AlarmType.ALERTA)
            return False, True
        
    def verificar_temperatura_drenaje(self):
            temp_drenaje = self.estado.sensores_temp["temp_drenaje"]
            temp_obj = self.config.get("temp_segura_drenaje")
            rango = self.config.get("rango_temp_drenaje")

            r = evaluar_banda(temp_drenaje, temp_obj, rango, activar_si_bajo=False)

            # Válvula: reacciona en el objetivo, sin esperar a cruzar la banda.
            if r.debe_activar:
                self.set_do.agua_intercambiador_on()
                self._confirmador_drenaje.reset()
            elif self._confirmador_drenaje.confirmar(True):
                self.set_do.agua_intercambiador_off()

            # Alarma bloqueante: solo al cruzar el borde superior de la banda.
            # No hay alarma de lado bajo: no existe accion fisica para
            # "drenaje muy frio", pero el lado bajo si participa del gate de
            # listo/inicio via dentro_de_banda.
            if r.fuera_por_encima:
                alarm_id = "TEMPERATURA_DRENAJE_ALTA"
                self.alarm(alarm_id, AlarmType.ALERTA)
            else:
                self.alarm_manager.clear("TEMPERATURA_DRENAJE_ALTA")

            return r.dentro_de_banda
        
    def reset(self):
        pass
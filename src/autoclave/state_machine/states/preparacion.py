# preparacion.py
from autoclave.state_machine.machine.parametros_globales import parametros_globales
from autoclave.state_machine.alarms.catalogo import (
    PRE_01, PRE_02, PRE_03, PRE_04, PRE_05, PRE_06, SEN_01, SIS_01,
    SUM_03, SUM_04, SUM_05, SUM_06, nombre_legible,
)
from autoclave.state_machine.states.control_banda import evaluar_banda, ConfirmadorApagado
from autoclave.core.runtime.lectura import lectura_valida
from autoclave.installation.profile import entrada_requerida, sensores_empaque, sonda_instalada
import logging

logger = logging.getLogger(__name__)

_ESTADO = "Preparación"
_SUMINISTROS = {"agua_bomba": SUM_03, "agua_generador": SUM_04, "aire_comprimido": SUM_05}


class preparacion_state:
    def __init__(self, alarm_manager, estado, set_do, cycle, config, profile=None):
        self.alarm_manager = alarm_manager
        self.estado = estado
        self.set_do = set_do
        self.cycle = cycle
        self.config = config
        # Perfil de instalación (E1): entradas de suministro y puertas.
        # None = comportamiento previo (todo requerido, 2 puertas con empaque).
        self.profile = profile

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
    
    def run(self):
        # Flag publicado por EmergencyStop, no el DI crudo (E1-5, D-16)
        if self.estado.get_flag("PARO_EMERGENCIA"):
            # ALL_OFF limitado: no esperar el ACK en cada tick (A-7)
            self.set_do.apagar_por_paro()
            self.alarm_manager.activar(SIS_01, estado=_ESTADO)
            self.set_do.buzer_emergencia()
            return False
        else:
            self.set_do.buzer_off()
            self.alarm_manager.resolver(SIS_01)

        if not self.supervisor():
            self._salidas_seguras_supervisor()
            return False

        return self.ejecutor()

    def _salidas_seguras_supervisor(self):
        """Supervisor falló por un sensor analógico (adenda E0/E1, A-2) o por
        un suministro (decisión P4): las salidas no pueden quedar
        congeladas. Vapor de chaqueta y de cámara a OFF; siguen los lazos que no aportan energía (presión de cámara,
        drenaje de cámara y enfriamiento del drenaje, este con A-4)."""
        self.set_do.vapor_chaqueta_off()
        self._confirmador_chaqueta.reset()
        self.set_do.vapor_camara_off()
        self.ejecutor(controlar_chaqueta=False)
        
            
    def supervisor(self) -> bool:
        ok = True
        if not self.verificar_sensores():
            ok = False
        if not self.verificar_suministros():
            ok = False
            
        return ok
    
    def ejecutor(self, controlar_chaqueta=True):
        logger.info("Ejecución del estado PREPARACION (paralelo)")

        chaqueta_lista = self.suministrar_vapor_chaqueta() if controlar_chaqueta else False
        presion_ok, quiere_rapida_presion = self.igualar_presion_camara()
        drenaje_ok, quiere_rapida_drenaje = self.drenar_camara()
        temp_ok = self.verificar_temperatura_drenaje()

        if quiere_rapida_presion or quiere_rapida_drenaje:
            self.set_do.descompresion_rapida_on()
        elif quiere_rapida_presion is not None:
            self.set_do.descompresion_rapida_off()
        # quiere_rapida_presion None: sin dato de presión, sin orden (E0-3)

        return chaqueta_lista and presion_ok and drenaje_ok and temp_ok
    
    def verificar_sensores(self):
            #==============================

            # Empaque solo de las puertas declaradas y si el tipo lo tiene
            # (door_type=simple no tiene sensor de empaque, E1-2)
            sensores_presion = [
                "pres_camara",
                "pres_chaqueta",
            ] + sensores_empaque(self.profile)
            
            sensores_temperatura = [
                "temp_camara",
                "temp_2_camara",
                "temp_ref",
                "temp_drenaje",
            ]
            ok=True
            for sensor in sensores_presion:
                pres_value = self.estado.sensores_pres.get(sensor)
                legible = nombre_legible(sensor)
                # Sin dato / no finito = error de sensor, igual que un 0 (A-5)
                if not lectura_valida(pres_value) or pres_value == 0:
                    self.alarm_manager.activar(SEN_01, origen=legible, sensor=legible,
                                               valor=pres_value)
                    ok = False
                else:
                    self.alarm_manager.resolver(SEN_01, origen=legible)

            for sensor in sensores_temperatura:
                # Canal sin sonda declarado en el perfil: no se vigila (A-2)
                if not sonda_instalada(self.profile, sensor):
                    continue
                temp_value = self.estado.sensores_temp.get(sensor)
                legible = nombre_legible(sensor)
                # None / no finito = sensor desconectado, igual que un 0 (E0-1)
                if not lectura_valida(temp_value) or temp_value == 0:
                    self.alarm_manager.activar(SEN_01, origen=legible, sensor=legible,
                                               valor=temp_value)
                    ok = False
                else:
                    self.alarm_manager.resolver(SEN_01, origen=legible)

            return ok
        
    def verificar_suministros(self):
        ok=True
        for suministro, codigo in _SUMINISTROS.items():
            # Entrada declarada "no aplica" en el perfil: no se vigila (E1-1)
            if not entrada_requerida(self.profile, suministro):
                continue
            estado_suministro = self.estado.sensores_di[suministro]
            if not estado_suministro:
                self.alarm_manager.activar(codigo)
                ok = False
            else:
                self.alarm_manager.resolver(codigo)

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
            presion = self.estado.sensores_pres.get("pres_chaqueta")
            pres_obj=self.cycle.get_param("globals","presion_chaqueta")
            rango=self.cycle.get_param("globals","rango_presion_chaqueta")

            # Sin dato: no lista y vapor OFF; la alarma ERROR_AI_PRES_CHAQUETA
            # la emite verificar_sensores() (E0-3, A-5)
            if not lectura_valida(presion):
                self.set_do.vapor_chaqueta_off()
                self._confirmador_chaqueta.reset()
                return False

            # Verificar suministro. Si no hay vapor, no insistir en abrir la
            # válvula (generaría vapor demasiado húmedo por baja presión de
            # línea): se deja "pendiente", no bloqueante.
            # Sin presostato declarado (E1-1): la chaqueta se controla solo
            # por presión, sin OFF forzado ni alarma SUMINISTRO_VAPOR.
            vigilar_vapor = entrada_requerida(self.profile, "vapor_suministro")
            if vigilar_vapor and not self.estado.sensores_di["vapor_suministro"]:
                self.set_do.vapor_chaqueta_off()
                self._confirmador_chaqueta.reset()
                self.alarm_manager.activar(SUM_06, estado=_ESTADO)
                self.alarm_manager.resolver(PRE_01)
                self.alarm_manager.resolver(PRE_02)
                return True
            elif vigilar_vapor:
                self.alarm_manager.resolver(SUM_06)

            r = evaluar_banda(presion, pres_obj, rango, activar_si_bajo=True)

            # Válvula: reacciona en el objetivo, sin esperar a cruzar la banda.
            if r.debe_activar:
                self.set_do.vapor_chaqueta_on()
                self._confirmador_chaqueta.reset()
            elif self._confirmador_chaqueta.confirmar(True):
                self.set_do.vapor_chaqueta_off()

            # Alarma bloqueante: solo al cruzar el borde de la banda.
            if r.fuera_por_debajo:
                self.alarm_manager.activar(PRE_01, pres=presion, minimo=pres_obj - rango,
                                           objetivo=pres_obj, rango=rango)
            else:
                self.alarm_manager.resolver(PRE_01)

            if r.fuera_por_encima:
                self.alarm_manager.activar(PRE_02, pres=presion, maximo=pres_obj + rango,
                                           objetivo=pres_obj, rango=rango)
            else:
                self.alarm_manager.resolver(PRE_02)

            return r.dentro_de_banda
    
    def igualar_presion_camara(self):
            """Retorna (ok, quiere_descompresion_rapida). No acciona la
            válvula descompresion_rapida directamente: esa salida es
            compartida con drenar_camara() y se combina en ejecutor(). Sin dato de presión retorna (False, None):
            no ordena nada, ni siquiera apagar la rápida."""
            presion_camara = self.estado.sensores_pres.get("pres_camara")
            # Sin dato (antes de la primera trama): sin órdenes (E0-3)
            if not lectura_valida(presion_camara):
                return False, None
            presion_atmosferica = self.config.get("presion_admosferica")
            rango_presion_atmosferica = self.config.get("rango_presion_atm")
            pres_cam_min = presion_atmosferica - rango_presion_atmosferica
            pres_cam_max = presion_atmosferica + rango_presion_atmosferica

            if pres_cam_min <= presion_camara <= pres_cam_max:
                # Presión igualada
                if self._confirmador_aire_camara.confirmar(True):
                    self.set_do.aire_admosferico_camara_off()
                self.set_do.descompresion_lenta_off()
                self.alarm_manager.resolver(PRE_03)
                self.alarm_manager.resolver(PRE_04)
                return True, False

            if presion_camara < pres_cam_min:
                # Abrir entrada de aire comprimido a la camara
                self.set_do.aire_admosferico_camara_on()
                self._confirmador_aire_camara.reset()
                self.alarm_manager.activar(PRE_03, pres=presion_camara, minimo=pres_cam_min)
                return False, False

            # presion_camara > pres_cam_max: requiere venteo/vacío
            self.set_do.aire_admosferico_camara_off()
            self._confirmador_aire_camara.reset()
            self.alarm_manager.activar(PRE_04, pres=presion_camara, maximo=pres_cam_max)
            return False, True
                
    def drenar_camara(self):
            """Retorna (ok, quiere_descompresion_rapida). No acciona la
            válvula descompresion_rapida directamente: esa salida es
            compartida con igualar_presion_camara() y se combina en
            ejecutor()."""
            agua_residual = self.estado.sensores_di["agua_camara"]
            if not agua_residual:
                self.alarm_manager.resolver(PRE_05)
                return True, False

            self.alarm_manager.activar(PRE_05)
            return False, True
        
    def verificar_temperatura_drenaje(self):
            temp_drenaje = self.estado.sensores_temp.get("temp_drenaje")
            temp_obj = self.config.get("temp_segura_drenaje")
            rango = self.config.get("rango_temp_drenaje")

            # Sin sonda declarada o sin lectura válida: enfriar siempre (A-4,
            # reemplaza lo pedido en E0-2). Apagar después exige otra vez la
            # confirmación completa. Sin sonda no bloquea; con sonda caída no
            # queda listo (la alarma la emite verificar_sensores()).
            instalada = sonda_instalada(self.profile, "temp_drenaje")
            if not instalada or not lectura_valida(temp_drenaje):
                self.set_do.agua_intercambiador_on()
                self._confirmador_drenaje.reset()
                return not instalada

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
                self.alarm_manager.activar(PRE_06, temp=temp_drenaje, maximo=temp_obj + rango)
            else:
                self.alarm_manager.resolver(PRE_06)

            return not r.fuera_por_encima
        
    def reset(self):
        pass
from autoclave.state_machine.alarms.alarm import Alarm, AlarmType
from autoclave.state_machine.states.control_banda import evaluar_banda, ConfirmadorApagado
import logging
import time

logger = logging.getLogger(__name__)


class preparado_state:
    def __init__(self, alarm_manager, estado, set_do, cycle, config):
        self.cycle = cycle
        self.alarm_manager = alarm_manager
        self.estado = estado
        self.set_do = set_do
        self.config = config

        # Tiempo requerido para considerar estable
        self.tiempo_estable = self.config.get("tiempo_estable_alarma")

        # Timer de estabilidad
        self.timer_estabilidad = None

        # Confirmadores de apagado (evitan chattering de valvula)
        self._confirmador_chaqueta = ConfirmadorApagado()

    # ==============================
    # ALARMAS
    # ==============================
    def alarm(self, alarm_id, alarm_type, blocks_operation=True):
        alarm = Alarm(
            alarm_id=alarm_id,
            alarm_type=alarm_type,
            source_state="PREPARADO",
            description=f"Error {alarm_id} en estado PREPARADO",
            recoverable=True,
            blocks_operation=blocks_operation,
        )
        self.alarm_manager.report(alarm)

    # ==============================
    # RUN PRINCIPAL
    # ==============================
    def run(self):
        if self.estado.get_flag("PARO_EMERGENCIA"):
            self.set_do.reset_all_outputs()
            self.alarm("PARO_EMERGENCIA", AlarmType.EMERGENCIA)
            self.set_do.buzer_emergencia()
            self.timer_estabilidad = None
            return False
        else:
            self.set_do.buzer_off()
            self.alarm_manager.clear("PARO_EMERGENCIA")

        if not self.supervisor():
            self.timer_estabilidad = None
            return False

        self.ejecutor()

        return self.esta_preparado()

    # ==============================
    # SUPERVISIÓN GENERAL
    # ==============================
    def supervisor(self) -> bool:
        ok = True

        if not self.verificar_sensores():
            ok = False

        if not self.verificar_suministros():
            ok = False

        return ok

    # ==============================
    # EJECUCIÓN CONTINUA (SIN STEPS)
    # ==============================
    def ejecutor(self):

        #logger.info("Estado PREPARADO: control y supervisión activa")

        # 🔧 CONTROL CONTINUO
        self.mantener_chaqueta()
        self.mantener_presion_camara()
        self.mantener_drenaje()

    # ==============================
    # CONTROL CHAQUETA
    # ==============================
    def mantener_chaqueta(self):
        press_chaqueta = self.estado.sensores_pres["pres_chaqueta"]
        press_obj = self.cycle.get_param("globals", "presion_chaqueta")
        rango=self.cycle.get_param("globals","rango_presion_chaqueta")

        # Suministro. Sin vapor, no insistir en abrir la válvula: se deja
        # "pendiente", no bloqueante (no debe frenar esta_preparado()).
        if not self.estado.sensores_di["vapor_suministro"]:
            self.set_do.vapor_chaqueta_off()
            self._confirmador_chaqueta.reset()
            self.alarm("SUMINISTRO_VAPOR", AlarmType.ALERTA, blocks_operation=False)
            self.alarm_manager.clear("CHAQUETA_FRIA")
            self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")
            return True
        else:
            self.alarm_manager.clear("SUMINISTRO_VAPOR")

        r = evaluar_banda(press_chaqueta, press_obj, rango, activar_si_bajo=True)

        # Válvula: reacciona en el objetivo, sin esperar a cruzar la banda.
        if r.debe_activar:
            self.set_do.vapor_chaqueta_on()
            self._confirmador_chaqueta.reset()
        elif self._confirmador_chaqueta.confirmar(True):
            self.set_do.vapor_chaqueta_off()

        # Alarma bloqueante: solo al cruzar el borde de la banda.
        if r.fuera_por_debajo:
            self.generar_alarma_temporizada("CHAQUETA_FRIA")
        else:
            self.alarm_manager.clear("CHAQUETA_FRIA")

        if r.fuera_por_encima:
            self.generar_alarma_temporizada("CHAQUETA_SOBRECALENTADA")
        else:
            self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")

        return r.dentro_de_banda

    # ==============================
    # CONTROL PRESIÓN CÁMARA
    # ==============================
    def mantener_presion_camara(self):
        presion_camara = self.estado.sensores_pres["pres_camara"]
        pres_atm = self.config.get("presion_admosferica")
        rango = self.config.get("rango_presion_atm")

        min_p = pres_atm - rango
        max_p = pres_atm + rango

        if min_p <= presion_camara <= max_p:
            self.set_do.aire_admosferico_camara_off()
            self.set_do.descompresion_rapida_off()
            self.alarm_manager.clear("PRESION_CAMARA_BAJA")
            self.alarm_manager.clear("PRESION_CAMARA_ALTA")
            return True

        if presion_camara < min_p:
            self.set_do.aire_admosferico_camara_on()
            self.set_do.descompresion_rapida_off()
            self.generar_alarma_temporizada("PRESION_CAMARA_BAJA")

        elif presion_camara > max_p:
            self.set_do.aire_admosferico_camara_off()
            self.set_do.descompresion_rapida_on()
            self.generar_alarma_temporizada("PRESION_CAMARA_ALTA")

        return False

    # ==============================
    # CONTROL DRENAJE
    # ==============================
    def mantener_drenaje(self):
        temp = self.estado.sensores_temp["temp_drenaje"]
        temp_segura = self.config.get("temp_segura_drenaje")

        if temp <= temp_segura:
            self.set_do.agua_intercambiador_off()
            self.alarm_manager.clear("TEMP_DRENAJE_ALTA")
            return True

        self.set_do.agua_intercambiador_on()
        self.generar_alarma_temporizada("TEMP_DRENAJE_ALTA")

        return False

    # ==============================
    # TEMPORIZADOR DE ALARMAS
    # ==============================
    def generar_alarma_temporizada(self, alarm_id):
        if self.timer_estabilidad is None:
            self.timer_estabilidad = time.time() + self.tiempo_estable

        if time.time() >= self.timer_estabilidad:
            self.alarm(alarm_id, AlarmType.ALERTA)

    # ==============================
    # PUERTAS CERRADAS
    # ==============================
    def puertas_cerradas(self) -> bool:
        """Ambas puertas deben estar cerradas para que el ciclo pueda arrancar."""
        p1 = bool(self.estado.sensores_di.get("puerta_1_cerrada", 0))
        p2 = bool(self.estado.sensores_di.get("puerta_2_cerrada", 0))

        if not p1:
            self.alarm("PUERTA_1_ABIERTA", AlarmType.ALERTA)
        else:
            self.alarm_manager.clear("PUERTA_1_ABIERTA")

        if not p2:
            self.alarm("PUERTA_2_ABIERTA", AlarmType.ALERTA)
        else:
            self.alarm_manager.clear("PUERTA_2_ABIERTA")

        return p1 and p2

    # ==============================
    # VALIDACIÓN FINAL
    # ==============================
    def esta_preparado(self):

        condiciones = (
            self.puertas_cerradas() and
            self.mantener_chaqueta() and
            self.mantener_presion_camara() and
            self.mantener_drenaje() and
            not self.estado.get_flag("PARO_EMERGENCIA") and
            not self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO")
        )

        if condiciones:
            self.timer_estabilidad = None
            return True

        return False

    # ==============================
    # REUTILIZADOS DE PREPARACIÓN
    # ==============================
    def verificar_sensores(self):
        ok = True

        for sensor, value in self.estado.sensores_pres.items():
            if value == 0:
                self.alarm(f"ERROR_AI_{sensor.upper()}", AlarmType.ALERTA)
                ok = False
            else:
                self.alarm_manager.clear(f"ERROR_AI_{sensor.upper()}")

        for sensor, value in self.estado.sensores_temp.items():
            if value == 0:
                self.alarm(f"ERROR_AI_{sensor.upper()}", AlarmType.ALERTA)
                ok = False
            else:
                self.alarm_manager.clear(f"ERROR_AI_{sensor.upper()}")

        return ok

    def verificar_suministros(self):
        ok = True

        for suministro, estado in self.estado.sensores_di.items():
            if suministro in ["agua_bomba", "agua_generador", "aire_comprimido"]:
                if not estado:
                    self.alarm(f"SUMINISTRO_{suministro.upper()}", AlarmType.ALERTA)
                    ok = False
                else:
                    self.alarm_manager.clear(f"SUMINISTRO_{suministro.upper()}")

        # Suministro eléctrico
        if not self.estado.sensores_di.get("suministro_electrico", 1):
            self.alarm("SUMINISTRO_ELECTRICO", AlarmType.ALERTA)
            ok = False
        else:
            self.alarm_manager.clear("SUMINISTRO_ELECTRICO")

        return ok
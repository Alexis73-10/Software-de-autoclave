from autoclave.state_machine.alarms.catalogo import (
    PRE_01, PRE_02, PRE_03, PRE_04, PRE_06, PUE_01, SEN_01, SIS_01,
    SUM_02, SUM_03, SUM_04, SUM_05, SUM_06, nombre_legible,
)
from autoclave.state_machine.states.control_banda import evaluar_banda, ConfirmadorApagado
import logging
import time

logger = logging.getLogger(__name__)

_ESTADO = "Preparado"
_SUMINISTROS = {"agua_bomba": SUM_03, "agua_generador": SUM_04, "aire_comprimido": SUM_05}


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
        self._confirmador_drenaje = ConfirmadorApagado()
        self._confirmador_aire_camara = ConfirmadorApagado()

    # ==============================
    # RUN PRINCIPAL
    # ==============================
    def run(self):
        if self.estado.get_flag("PARO_EMERGENCIA"):
            self.set_do.reset_all_outputs()
            self.alarm_manager.activar(SIS_01, estado=_ESTADO)
            self.set_do.buzer_emergencia()
            self.timer_estabilidad = None
            return False
        else:
            self.set_do.buzer_off()
            self.alarm_manager.resolver(SIS_01)

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
            self.alarm_manager.activar(SUM_06, estado=_ESTADO)
            self.alarm_manager.resolver(PRE_01)
            self.alarm_manager.resolver(PRE_02)
            return True
        else:
            self.alarm_manager.resolver(SUM_06)

        r = evaluar_banda(press_chaqueta, press_obj, rango, activar_si_bajo=True)

        # Válvula: reacciona en el objetivo, sin esperar a cruzar la banda.
        if r.debe_activar:
            self.set_do.vapor_chaqueta_on()
            self._confirmador_chaqueta.reset()
        elif self._confirmador_chaqueta.confirmar(True):
            self.set_do.vapor_chaqueta_off()

        # Alarma bloqueante: solo al cruzar el borde de la banda.
        if r.fuera_por_debajo:
            self.generar_alarma_temporizada(PRE_01, pres=press_chaqueta,
                                            minimo=press_obj - rango,
                                            objetivo=press_obj, rango=rango)
        else:
            self.alarm_manager.resolver(PRE_01)

        if r.fuera_por_encima:
            self.generar_alarma_temporizada(PRE_02, pres=press_chaqueta,
                                            maximo=press_obj + rango,
                                            objetivo=press_obj, rango=rango)
        else:
            self.alarm_manager.resolver(PRE_02)

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
            if self._confirmador_aire_camara.confirmar(True):
                self.set_do.aire_admosferico_camara_off()
            self.set_do.descompresion_rapida_off()
            self.alarm_manager.resolver(PRE_03)
            self.alarm_manager.resolver(PRE_04)
            return True

        if presion_camara < min_p:
            self.set_do.aire_admosferico_camara_on()
            self._confirmador_aire_camara.reset()
            self.set_do.descompresion_rapida_off()
            self.generar_alarma_temporizada(PRE_03, pres=presion_camara, minimo=min_p)

        elif presion_camara > max_p:
            self.set_do.aire_admosferico_camara_off()
            self._confirmador_aire_camara.reset()
            self.set_do.descompresion_rapida_on()
            self.generar_alarma_temporizada(PRE_04, pres=presion_camara, maximo=max_p)

        return False

    # ==============================
    # CONTROL DRENAJE
    # ==============================
    def mantener_drenaje(self):
        temp = self.estado.sensores_temp["temp_drenaje"]
        temp_obj = self.config.get("temp_segura_drenaje")
        rango = self.config.get("rango_temp_drenaje")

        r = evaluar_banda(temp, temp_obj, rango, activar_si_bajo=False)

        # Válvula: reacciona en el objetivo, sin esperar a cruzar la banda.
        if r.debe_activar:
            self.set_do.agua_intercambiador_on()
            self._confirmador_drenaje.reset()
        elif self._confirmador_drenaje.confirmar(True):
            self.set_do.agua_intercambiador_off()

        # Alarma bloqueante: solo al cruzar el borde superior de la banda.
        # No hay alarma de lado bajo: no existe accion fisica para "drenaje
        # muy frio" (no hay calefactor), pero el lado bajo si participa del
        # gate de listo/inicio via dentro_de_banda.
        if r.fuera_por_encima:
            self.generar_alarma_temporizada(PRE_06, temp=temp, maximo=temp_obj + rango)
        else:
            self.alarm_manager.resolver(PRE_06)

        return not r.fuera_por_encima

    # ==============================
    # TEMPORIZADOR DE ALARMAS
    # ==============================
    def generar_alarma_temporizada(self, codigo, **valores):
        if self.timer_estabilidad is None:
            self.timer_estabilidad = time.monotonic() + self.tiempo_estable

        if time.monotonic() >= self.timer_estabilidad:
            self.alarm_manager.activar(codigo, **valores)

    # ==============================
    # PUERTAS CERRADAS
    # ==============================
    def puertas_cerradas(self) -> bool:
        """Ambas puertas deben estar cerradas para que el ciclo pueda arrancar."""
        p1 = bool(self.estado.sensores_di.get("puerta_1_cerrada", 0))
        p2 = bool(self.estado.sensores_di.get("puerta_2_cerrada", 0))

        for num, cerrada in ((1, p1), (2, p2)):
            puerta = f"Puerta {num}"
            if not cerrada:
                self.alarm_manager.activar(PUE_01, origen=puerta, puerta=puerta)
            else:
                self.alarm_manager.resolver(PUE_01, origen=puerta)

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
            legible = nombre_legible(sensor)
            if value == 0:
                self.alarm_manager.activar(SEN_01, origen=legible, sensor=legible,
                                           valor=value)
                ok = False
            else:
                self.alarm_manager.resolver(SEN_01, origen=legible)

        for sensor, value in self.estado.sensores_temp.items():
            legible = nombre_legible(sensor)
            if value == 0:
                self.alarm_manager.activar(SEN_01, origen=legible, sensor=legible,
                                           valor=value)
                ok = False
            else:
                self.alarm_manager.resolver(SEN_01, origen=legible)

        return ok

    def verificar_suministros(self):
        ok = True

        for suministro, estado in self.estado.sensores_di.items():
            if suministro in _SUMINISTROS:
                if not estado:
                    self.alarm_manager.activar(_SUMINISTROS[suministro])
                    ok = False
                else:
                    self.alarm_manager.resolver(_SUMINISTROS[suministro])

        # Suministro eléctrico
        if not self.estado.sensores_di.get("suministro_electrico", 1):
            self.alarm_manager.activar(SUM_02)
            ok = False
        else:
            self.alarm_manager.resolver(SUM_02)

        return ok
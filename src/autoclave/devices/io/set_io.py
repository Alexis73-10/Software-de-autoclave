# src/autoclave/devices/io/set_io.py
from autoclave.devices.pump.pump import VacuumPump
from autoclave.installation.profile import salidas_vapor_permitidas
import autoclave.devices.buzer.buzer as buzer
import logging
import time

logger = logging.getLogger(__name__)

# Con el paro activo, ALL_OFF a lo sumo una vez por este intervalo, salvo que
# el último DO reportado tenga una salida encendida (adenda E0/E1, A-7).
_INTERVALO_ALL_OFF_PARO_SEG = 1.0
# Salidas que no cuentan como "encendidas" para repetir el ALL_OFF del paro:
# el buzzer suena a propósito durante el paro.
_SALIDAS_IGNORADAS_PARO = frozenset({"buzer_alarma"})
# Canales físicos (1-indexados) de las salidas de fuente de vapor.
_CANALES_VAPOR = {"vapor_generador": 1, "vapor_caldera": 2}


class SetOutput:
    def __init__(self, io, estado, profile=None):
        self.io = io
        self.estado = estado
        self.vacump = VacuumPump(estado, profile=profile)
        self.buzer = buzer.BuzzerPlayer(self.buzer_on, self.buzer_off)
        self._ultimo_all_off_paro: float | None = None
        # E1b (D-23): canales de vapor de la fuente que el equipo no tiene.
        permitidas = salidas_vapor_permitidas(profile)
        self._canales_bloqueados = {canal for nombre, canal in _CANALES_VAPOR.items()
                                    if nombre not in permitidas}
        if self._canales_bloqueados:
            # S1 (tanda 2): que quede constancia al arrancar (p. ej. generador
            # interno: DO1 y DO2 deshabilitadas)
            logger.info("SetOutput: fuente de vapor '%s'; salidas deshabilitadas: %s",
                        getattr(profile, "vapor_source", None),
                        ", ".join(f"DO{c}" for c in sorted(self._canales_bloqueados)))

    def salida_bloqueada(self, index) -> bool:
        """True si el canal es de una fuente de vapor que el equipo no tiene."""
        return index in self._canales_bloqueados

    def set_output(self, index, value):
        # Todo encendido pasa por aquí (lazo, fases, /io/test/output): la
        # fuente de vapor ausente nunca se enciende; se reafirma OFF.
        if value and index in self._canales_bloqueados:
            logger.warning("SetOutput: DO%d es de una fuente de vapor que el equipo "
                           "no tiene (vapor_source); se mantiene apagada", index)
            value = False
        self.io.set_output(index, value)
        
    def vapor_generador_on(self):
        self.set_output(1, True)
        
    def vapor_generador_off(self):
        self.set_output(1, False)
        
    def vapor_caldera_on(self):
        self.set_output(2, True)
        
    def vapor_caldera_off(self):
        self.set_output(2, False)
        
    def vapor_chaqueta_on(self):
        self.set_output(3, True)
        
    def vapor_chaqueta_off(self):
        self.set_output(3, False)
        
    def vapor_camara_on(self):
        self.set_output(4, True)
        
    def vapor_camara_off(self):
        self.set_output(4, False)
        
    def descompresion_rapida_on(self):
        self.set_output(5, True)
        
    def descompresion_rapida_off(self):
        self.set_output(5, False)
        
    def descompresion_lenta_on(self):
        self.set_output(6, True)
        
    def descompresion_lenta_off(self):
        self.set_output(6, False)
        
    def descompresion_chaqueta_on(self):
        self.set_output(7, True)
        
    def descompresion_chaqueta_off(self):
        self.set_output(7, False)
        
    def vacio_camara_on(self):
        self.agua_intercambiador_on()
        self.set_output(8, True)
        
    def vacio_camara_off(self):
        self.set_output(8, False)
        self.agua_intercambiador_off()
        
    def desbloqueo_puerta_1_on(self):
        self.set_output(9, True)
        
    def desbloqueo_puerta_1_off(self):
        self.set_output(9, False)
        
    def desbloqueo_puerta_2_on(self):
        self.set_output(10, True)
        
    def desbloqueo_puerta_2_off(self):
        self.set_output(10, False)
        
    def bloqueo_puerta_1_on(self):
        self.set_output(11, True)
        
    def bloqueo_puerta_1_off(self):
        self.set_output(11, False)
        
    def bloqueo_puerta_2_on(self):
        self.set_output(12, True)
        
    def bloqueo_puerta_2_off(self):
        self.set_output(12, False)
        
    def aire_comprimido_chaqueta_on(self):
        self.set_output(13, True)
        
    def aire_comprimido_chaqueta_off(self):
        self.set_output(13, False)
        
    def aire_comprimido_camara_on(self):
        self.set_output(14, True)
        
    def aire_comprimido_camara_off(self):
        self.set_output(14, False)
        
    def aire_admosferico_camara_on(self):
        self.set_output(15, True)
        
    def aire_admosferico_camara_off(self):
        self.set_output(15, False)
        
    def agua_chaqueta_on(self):
        self.set_output(16, True)
        
    def agua_chaqueta_off(self):
        self.set_output(16, False)
        
    def agua_intercambiador_on(self):
        self.set_output(17, True)
        
    def agua_intercambiador_off(self):
        self.set_output(17, False)
        
    def agua_bomba_on(self):
        self.set_output(18, True)
        
    def agua_bomba_off(self):
        self.set_output(18, False)
        
    def bomba_vacio_on(self):
        if self.vacump.puede_activar():
            self.agua_bomba_on()
            self.set_output(19, True)
            logger.info("Bomba de vacio enviada.")
            
            
    def bomba_vacio_off(self):
        self.set_output(19, False)
        self.agua_bomba_off()
            
    def abrir_puerta_1_on(self):
        self.set_output(20, True)
        
    def abrir_puerta_1_off(self):
        self.set_output(20, False)
        
    def abrir_puerta_2_on(self):
        self.set_output(21, True)
        
    def abrir_puerta_2_off(self):
        self.set_output(21, False)
        
    def cerrar_puerta_1_on(self):
        self.set_output(22, True)
        
    def cerrar_puerta_1_off(self):
        self.set_output(22, False)
        
    def cerrar_puerta_2_on(self):
        self.set_output(23, True)
        
    def cerrar_puerta_2_off(self):
        self.set_output(23, False)
        
    def buzer_on(self):
        self.set_output(24, True)
        
    def buzer_off(self):
        self.set_output(24, False)
        
    def buzer_emergencia(self):
        self.buzer.play(buzer.BEEP_EMERGENCY)

    def buzer_fallo(self):
        """Pitido de aviso: cámara alcanzó condiciones seguras tras fallo/cancelación."""
        self.buzer.play(buzer.BEEP_FALLO, repeticiones=1)

    def reset_all_outputs(self) -> bool:
        """Apaga todas las salidas. Usa ALL_OFF con ACK; si falla, cae a comandos
        individuales (sin confirmación). Retorna True solo si el ESP32 confirmó
        el apagado vía ACK de ALL_OFF."""
        ok = self.io.all_off()
        if not ok:
            for channel in range(1, 25):
                self.io.set_output(channel, False)
        return ok

    def apagar_por_paro(self) -> bool | None:
        """Apagado repetido mientras dura el paro de emergencia. Envía ALL_OFF
        si pasó _INTERVALO_ALL_OFF_PARO_SEG desde el último o si el último DO
        reportado tiene una salida encendida; si no, no hace nada y devuelve
        None. Evita esperar el ACK (hasta 1 s, bajo el lock del lazo) en cada
        tick y que el ALL_OFF corte el patrón del buzzer (TMG-09)."""
        ahora = time.monotonic()
        vencido = (self._ultimo_all_off_paro is None
                   or ahora - self._ultimo_all_off_paro >= _INTERVALO_ALL_OFF_PARO_SEG)
        if not (vencido or self._hay_salida_encendida()):
            return None
        self._ultimo_all_off_paro = ahora
        return self.reset_all_outputs()

    def _hay_salida_encendida(self) -> bool:
        """Según el último DO reportado por la tarjeta. Sin dato = encendida."""
        salidas = getattr(self.estado, "salidas_do", None)
        if not isinstance(salidas, dict):
            return True
        return any(v for k, v in salidas.items() if k not in _SALIDAS_IGNORADAS_PARO)



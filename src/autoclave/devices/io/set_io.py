# src/autoclave/devices/io/set_io.py
from autoclave.devices.pump.pump import VacuumPump
import autoclave.devices.buzer.buzer as buzer
import logging

logger = logging.getLogger(__name__)


class SetOutput:
    def __init__(self, io, estado):
        self.io = io
        self.vacump = VacuumPump(estado)
        self.buzer = buzer.BuzzerPlayer(self.buzer_on, self.buzer_off)
        
    def set_output(self, index, value):
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

    def reset_all_outputs(self):
        """Apaga todas las salidas. Usa ALL_OFF con ACK; si falla, cae a comandos individuales."""
        ok = self.io.all_off()
        if not ok:
            for channel in range(1, 25):
                self.io.set_output(channel, False)



import time

class BuzzerPlayer:
    def __init__(self, buzer_on, buzer_off):
        self.buzer_on = buzer_on
        self.buzer_off = buzer_off

        self.patron = []
        self.index = 0
        self.tiempo_cambio = 0
        self.activo = False

        self.repeticiones = 0
        self.repeticiones_hechas = 0

    def play(self, patron, repeticiones=1):

        if self.activo and self.patron == patron:
            return
        """Inicia un patrón con número de repeticiones"""
        self.patron = patron
        self.index = 0
        self.tiempo_cambio = time.time()
        self.activo = True

        self.repeticiones = repeticiones
        self.repeticiones_hechas = 0

    def stop(self):
        self.activo = False
        self.buzer_off()

    def update(self):
        if not self.activo or not self.patron:
            return

        ahora = time.time()
        estado, duracion = self.patron[self.index]

        # ejecutar estado actual
        if estado:
            self.buzer_on()
        else:
            self.buzer_off()

        # revisar si toca avanzar
        if ahora - self.tiempo_cambio >= duracion:
            self.index += 1
            self.tiempo_cambio = ahora

            if self.index >= len(self.patron):
                self.repeticiones_hechas += 1

                if self.repeticiones_hechas >= self.repeticiones:
                    self.stop()
                    return

                # reiniciar patrón
                self.index = 0


BEEP_EMERGENCY = [
    (1, 0.05), (0, 0.05),
    (1, 0.05), (0, 0.05),
    (1, 0.05), (0, 0.05),
    (1, 0.05), (0, 0.15),
]

BEEP_ALARMA = [
    (1, 0.2), (0, 0.2),
    (1, 0.2), (0, 0.5),
]

BEEP_AVISO = [
    (1, 0.1),
    (0, 0.05),
]
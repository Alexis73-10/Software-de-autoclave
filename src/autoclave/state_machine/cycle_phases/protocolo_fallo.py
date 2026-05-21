# state_machine/cycle_phases/protocolo_fallo.py
#
# Protocolo universal de aborto/fallo.
# Se ejecuta cuando cualquier fase falla, el usuario cancela,
# o se activa el paro de emergencia.
#
# Secuencia:
#   1. Apagar TODAS las salidas digitales
#   2. Evaluar estado de la cámara:
#      - Presurizada  → abrir descompresión lenta (safe default)
#      - En vacío     → abrir válvula de aire atmosférico
#      - Normal       → no hacer nada adicional

import logging

logger = logging.getLogger(__name__)


class ProtocoloFallo:

    def __init__(self, estado, set_do, config):
        self.estado  = estado
        self.set_do  = set_do
        self.config  = config
        self._ejecutado = False

    def reset(self):
        self._ejecutado = False

    def ejecutar(self):
        """
        Llamar UNA vez al detectar el fallo.
        Apaga todo y activa la salida de seguridad correcta.
        """
        if self._ejecutado:
            return

        logger.warning("Protocolo de fallo ejecutado — apagando todas las salidas")

        # 1. Todas las salidas a cero
        self.set_do.reset_all_outputs()

        # 2. Evaluar estado de la cámara
        pres  = self.estado.sensores_pres.get("pres_camara")
        atm   = self.config.get("presion_admosferica") or 101.3
        rango = self.config.get("rango_presion_atm")   or 20.0

        if pres is None:
            logger.warning("Protocolo fallo: presión de cámara desconocida, no se activa salida de seguridad")
        elif pres > atm + rango:
            logger.warning("Protocolo fallo: cámara presurizada (%.1f kPa) → abriendo descompresión lenta", pres)
            self.set_do.descompresion_lenta_on()
        elif pres < atm - rango:
            logger.warning("Protocolo fallo: cámara en vacío (%.1f kPa) → abriendo aire atmosférico", pres)
            self.set_do.aire_admosferico_camara_on()
        else:
            logger.info("Protocolo fallo: cámara a presión normal (%.1f kPa)", pres)

        self._ejecutado = True

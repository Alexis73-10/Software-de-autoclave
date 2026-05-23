# state_machine/cycle_phases/protocolo_fallo.py
#
# Protocolo universal de aborto/fallo.
# Se ejecuta cuando cualquier fase falla, el usuario cancela,
# o se activa el paro de emergencia.
#
# DISPARO (ejecutar — llamar UNA sola vez):
#   1. Apagar todas las salidas
#   2. Según presión inicial:
#        - Presurizada  → abrir descompresión lenta
#        - Normal/vacío → abrir aire atmosférico
#
# MANTENIMIENTO CONTINUO (update — llamar cada tick):
#   - Cuando la presión cae al rango normal:
#       cierra descompresión lenta y abre aire atmosférico
#       (evita vacío parcial por enfriamiento)
#   - Cuando presión < atm - rango: mantiene aire atmosférico
#   - Cuando se alcanzan condiciones seguras (presión normal
#       AND temp_camara <= temp_max_apertura):
#       emite BEEP_FALLO UNA sola vez

import logging

logger = logging.getLogger(__name__)


class ProtocoloFallo:

    def __init__(self, estado, set_do, config):
        self.estado  = estado
        self.set_do  = set_do
        self.config  = config
        self._ejecutado     = False
        self._buzzer_emitido = False

    def reset(self):
        self._ejecutado      = False
        self._buzzer_emitido = False

    # ------------------------------------------------------------------
    # DISPARO — llamar UNA vez al detectar el fallo
    # ------------------------------------------------------------------

    def ejecutar(self):
        if self._ejecutado:
            return

        logger.warning("Protocolo de fallo ejecutado — apagando todas las salidas")

        # 1. Todas las salidas a cero
        self.set_do.reset_all_outputs()

        # 2. Válvula de seguridad inicial según estado de la cámara
        pres  = self.estado.sensores_pres.get("pres_camara")
        atm   = self.config.get("presion_admosferica") or 101.3
        rango = self.config.get("rango_presion_atm")   or 20.0

        if pres is None:
            logger.warning(
                "Protocolo fallo: presión desconocida — no se activa válvula de seguridad"
            )
        elif pres > atm + rango:
            # Cámara presurizada → descompresión lenta
            logger.warning(
                "Protocolo fallo: cámara presurizada (%.1f kPa) → descompresión lenta", pres
            )
            self.set_do.descompresion_lenta_on()
        else:
            # Presión normal o bajo vacío → aire atmosférico
            logger.warning(
                "Protocolo fallo: presión %.1f kPa → aire atmosférico", pres
            )
            self.set_do.aire_admosferico_camara_on()

        self._ejecutado = True

    # ------------------------------------------------------------------
    # MANTENIMIENTO — llamar en cada tick mientras se espera confirmación
    # ------------------------------------------------------------------

    def update(self):
        """
        Gestión continua post-fallo:
          - Transiciona de descompresión lenta a aire atmosférico cuando
            la presión llega al rango normal (evita vacío por enfriamiento).
          - Emite BEEP_FALLO una sola vez cuando la cámara es segura
            (presión normal AND temperatura <= temp_max_apertura).
        """
        if not self._ejecutado:
            return

        pres     = self.estado.sensores_pres.get("pres_camara")
        temp     = self.estado.sensores_temp.get("temp_camara")
        atm      = self.config.get("presion_admosferica") or 101.3
        rango    = self.config.get("rango_presion_atm")   or 20.0
        temp_max = self.config.get("temp_max_apertura")   or 120.0

        if pres is None:
            return

        # ── Gestión dinámica de presión ───────────────────────────────
        if pres > atm + rango:
            # Sigue presurizada: mantener descompresión lenta
            self.set_do.descompresion_lenta_on()
            self.set_do.aire_admosferico_camara_off()
        else:
            # Dentro del rango normal o en vacío:
            # cerrar descompresión lenta y mantener aire atmosférico
            # para evitar caída de presión por enfriamiento
            self.set_do.descompresion_lenta_off()
            self.set_do.aire_admosferico_camara_on()

        # ── Buzzer cuando se alcanzan condiciones seguras ─────────────
        if not self._buzzer_emitido:
            pres_ok = abs(pres - atm) <= rango
            temp_ok = (temp is not None) and (temp <= temp_max)

            if pres_ok and temp_ok:
                logger.info(
                    "Protocolo fallo: condiciones seguras (%.1f kPa / %.1f°C) → buzzer",
                    pres, temp
                )
                self.set_do.buzer_fallo()
                self._buzzer_emitido = True

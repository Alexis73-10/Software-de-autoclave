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

import time
import logging

logger = logging.getLogger(__name__)


class ProtocoloFallo:

    def __init__(self, estado, set_do, cycle, config):
        self.estado  = estado
        self.set_do  = set_do
        self.cycle   = cycle
        self.config  = config
        self._ejecutado       = False
        self._buzzer_emitido  = False
        self._salidas_apagadas = False
        self._presurizado_al_disparo  = False
        self._modo                    = None
        self._sub_etapa                = None
        self._t_timeout_descompresion  = None
        self._escalado                 = False

    def reset(self):
        self._ejecutado       = False
        self._buzzer_emitido  = False
        self._salidas_apagadas = False
        self._presurizado_al_disparo  = False
        self._modo                    = None
        self._sub_etapa                = None
        self._t_timeout_descompresion  = None
        self._escalado                 = False

    # ------------------------------------------------------------------
    # DISPARO — llamar UNA vez al detectar el fallo
    # ------------------------------------------------------------------

    def ejecutar(self):
        if self._ejecutado:
            return

        logger.warning("Protocolo de fallo ejecutado — apagando todas las salidas")

        # 1. Todas las salidas a cero (si no hay enlace serial, esto puede no
        # confirmarse — se reintenta en update() hasta que se confirme).
        self._salidas_apagadas = self.set_do.reset_all_outputs()

        # 2. Válvula de seguridad inicial según estado de la cámara
        pres  = self.estado.sensores_pres.get("pres_camara")
        atm   = self.config.get("presion_admosferica") or 101.3
        rango = self.config.get("rango_presion_atm")   or 20.0

        if pres is None:
            logger.warning(
                "Protocolo fallo: presión desconocida — no se activa válvula de seguridad"
            )
        else:
            self._modo = self.cycle.get_param("descompresion", "modo", default=0) or 0
            self._sub_etapa = "lenta" if self._modo == 3 else None

            if pres > atm + rango:
                self._presurizado_al_disparo = True
                self._t_timeout_descompresion = self._calcular_timeout()
                logger.warning(
                    "Protocolo fallo: cámara presurizada (%.1f kPa) → modo de descompresión %d",
                    pres, self._modo
                )
                self._aplicar_paso_modo(pres)
            elif pres < atm - rango:
                # Vacío real → aire atmosférico, ninguna válvula de descompresión
                logger.warning(
                    "Protocolo fallo: cámara en vacío (%.1f kPa) → aire atmosférico", pres
                )
                self.set_do.aire_admosferico_camara_on()
            else:
                # Rango normal, sin presión que evacuar → deja la válvula
                # de descompresión del modo configurado
                logger.warning(
                    "Protocolo fallo: presión normal (%.1f kPa) → válvula del modo %d",
                    pres, self._modo
                )
                self._aplicar_paso_modo(pres)

        self._ejecutado = True

    # ------------------------------------------------------------------
    # Estrategia de válvulas según el modo de descompresión del ciclo
    # ------------------------------------------------------------------

    def _calcular_timeout(self) -> float:
        timeout_key = "modo_2" if self._modo == 0 else f"modo_{self._modo}"
        timeout_min = self.cycle.get_param("descompresion", timeout_key, "timeout", default=60)
        return time.monotonic() + (timeout_min or 60) * 60

    def _aplicar_paso_modo(self, pres: float) -> None:
        if self._escalado:
            self.set_do.descompresion_chaqueta_on()
            self.set_do.descompresion_rapida_on()
            return

        modo_efectivo = 2 if self._modo == 0 else self._modo

        if modo_efectivo == 1:
            self.set_do.descompresion_rapida_on()
        elif modo_efectivo == 2:
            self.set_do.descompresion_lenta_on()
        elif modo_efectivo == 3:
            if self._sub_etapa == "lenta":
                presion_cambio = self.cycle.get_param(
                    "descompresion", "modo_3", "presion_cambio", default=150
                )
                self.set_do.descompresion_lenta_on()
                if pres <= presion_cambio:
                    self.set_do.descompresion_lenta_off()
                    self._sub_etapa = "rapida"
            else:
                self.set_do.descompresion_rapida_on()
        elif modo_efectivo in (4, 5):
            self.set_do.descompresion_chaqueta_on()
            self.set_do.descompresion_rapida_on()

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

        # Reintentar el apagado si la primera confirmación (ACK de ALL_OFF)
        # no llegó — p.ej. porque el enlace serial cayó justo al fallar.
        if not self._salidas_apagadas:
            self._salidas_apagadas = self.set_do.reset_all_outputs()
            if self._salidas_apagadas:
                logger.info("Protocolo fallo: apagado de salidas confirmado tras reintento")

        pres     = self.estado.sensores_pres.get("pres_camara")
        temp     = self.estado.sensores_temp.get("temp_camara")
        atm      = self.config.get("presion_admosferica") or 101.3
        rango    = self.config.get("rango_presion_atm")   or 20.0
        temp_max = self.config.get("temp_max_apertura")   or 120.0

        if pres is None:
            return

        # ── Gestión dinámica de presión ───────────────────────────────
        if pres > atm + rango:
            if self._presurizado_al_disparo:
                if not self._escalado and time.monotonic() > self._t_timeout_descompresion:
                    logger.error(
                        "Protocolo fallo: timeout del modo %d agotado, escalando a chaqueta+rápida",
                        self._modo,
                    )
                    self._escalado = True
                self._aplicar_paso_modo(pres)
            else:
                # Nunca estuvo presurizada al disparo pero subió después:
                # comportamiento heredado, sin cambios.
                self.set_do.descompresion_lenta_on()
                self.set_do.aire_admosferico_camara_off()
        elif pres < atm - rango:
            # Vacío real → cerrar válvulas de descompresión, aire atmosférico
            self.set_do.descompresion_rapida_off()
            self.set_do.descompresion_lenta_off()
            self.set_do.descompresion_chaqueta_off()
            self.set_do.aire_admosferico_camara_on()
        else:
            # Rango normal → mantener la válvula de descompresión del modo,
            # aire atmosférico cerrado (evita cerrar en falso si la cámara
            # todavía tiene algo de presión residual, no vacío)
            self.set_do.aire_admosferico_camara_off()
            self._aplicar_paso_modo(pres)

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

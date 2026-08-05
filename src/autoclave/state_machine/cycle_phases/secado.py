# state_machine/cycle_phases/secado.py
import time
import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)

_PASO_VACIO_BAJO = "VACIO_BAJO"
_PASO_AIRE_ALTO  = "AIRE_ALTO"


class SecadoFase(BaseFase):
    name = "SECADO"

    def reset(self):
        self._inicializado      = False
        self._timer_fin         = None
        self._timeout_pulso_fin = None
        self._sub_estado        = None
        self.estado.fase_en_sostenimiento = False

    def update(self) -> FaseResult:
        if not self.cap.has_vacuum:
            logger.info("SecadoFase: sin bomba de vacío — fase saltada")
            return FaseResult.COMPLETADO

        tiempo_min = self.cycle.get_param("secado", "tiempo_secado") or 0
        if float(tiempo_min) == 0:
            logger.info("SecadoFase: tiempo_secado=0 — fase saltada")
            return FaseResult.COMPLETADO

        modo = int(self.cycle.get_param("secado", "modo") or 1)

        if not self._inicializado:
            self._timer_fin = time.time() + float(tiempo_min) * 60
            if modo == 3:
                timeout_seg = self.cycle.get_param("secado", "timeout_pulso") or 10
                self._timeout_pulso_fin = time.time() + float(timeout_seg)
                self._sub_estado = _PASO_VACIO_BAJO
            self._inicializado = True
            self.estado.fase_en_sostenimiento = True
            logger.info("SecadoFase: modo %d | %.1f min", modo, float(tiempo_min))

        if modo == 1:
            return self._tick_modo_1()
        if modo == 2:
            return self._tick_modo_2()
        if modo == 3:
            return self._tick_modo_3()

        logger.error("SecadoFase: modo desconocido %d", modo)
        return FaseResult.EN_CURSO

    # ── helpers ─────────────────────────────────────────────────────────

    def _tick_chaqueta(self):
        pres = self.estado.sensores_pres.get("pres_chaqueta")
        if pres is None:
            return
        p_obj = float(self.cycle.get_param("secado", "presion_chaqueta_secado") or 200)
        rango = float(self.cycle.get_param("secado", "rango_chaqueta_secado") or 30)
        if pres < p_obj - rango:
            self.set_do.vapor_chaqueta_on()
        elif pres > p_obj + rango:
            self.set_do.vapor_chaqueta_off()

    def _apagar_todo(self):
        self.set_do.bomba_vacio_off()
        self.set_do.vacio_camara_off()
        self.set_do.aire_admosferico_camara_off()
        self.set_do.vapor_chaqueta_off()
        self.estado.fase_en_sostenimiento = False

    # ── modos ───────────────────────────────────────────────────────────

    def _tick_modo_1(self) -> FaseResult:
        if time.time() >= self._timer_fin:
            self._apagar_todo()
            logger.info("SecadoFase modo 1: COMPLETADO")
            return FaseResult.COMPLETADO
        self._tick_chaqueta()
        self.set_do.bomba_vacio_on()
        self.set_do.vacio_camara_on()
        return FaseResult.EN_CURSO

    def _tick_modo_2(self) -> FaseResult:
        if time.time() >= self._timer_fin:
            self._apagar_todo()
            logger.info("SecadoFase modo 2: COMPLETADO")
            return FaseResult.COMPLETADO
        self._tick_chaqueta()
        self.set_do.bomba_vacio_on()
        self.set_do.vacio_camara_on()
        self.set_do.aire_admosferico_camara_on()
        return FaseResult.EN_CURSO

    def _tick_modo_3(self) -> FaseResult:
        if time.time() >= self._timer_fin:
            self._apagar_todo()
            logger.info("SecadoFase modo 3: COMPLETADO")
            return FaseResult.COMPLETADO

        self._tick_chaqueta()
        pres = self._pres_camara()

        if self._sub_estado == _PASO_VACIO_BAJO:
            presion_baja = float(self.cycle.get_param("secado", "presion_baja_secado") or 20)
            self.set_do.bomba_vacio_on()
            self.set_do.vacio_camara_on()

            if time.time() > self._timeout_pulso_fin:
                logger.error("SecadoFase modo 3: TIMEOUT en VACIO_BAJO")
                self._apagar_todo()
                return FaseResult.FALLO

            if pres is not None and pres <= presion_baja:
                self.set_do.bomba_vacio_off()
                self.set_do.vacio_camara_off()
                timeout_seg = self.cycle.get_param("secado", "timeout_pulso") or 10
                self._timeout_pulso_fin = time.time() + float(timeout_seg)
                self._sub_estado = _PASO_AIRE_ALTO
                logger.info("SecadoFase: %.1f kPa ≤ pres_baja → AIRE_ALTO", pres)

        elif self._sub_estado == _PASO_AIRE_ALTO:
            presion_alta = float(self.cycle.get_param("secado", "presion_alta_secado") or 80)
            self.set_do.aire_admosferico_camara_on()

            if time.time() > self._timeout_pulso_fin:
                logger.error("SecadoFase modo 3: TIMEOUT en AIRE_ALTO")
                self._apagar_todo()
                return FaseResult.FALLO

            if pres is not None and pres >= presion_alta:
                self.set_do.aire_admosferico_camara_off()
                timeout_seg = self.cycle.get_param("secado", "timeout_pulso") or 10
                self._timeout_pulso_fin = time.time() + float(timeout_seg)
                self._sub_estado = _PASO_VACIO_BAJO
                logger.info("SecadoFase: %.1f kPa ≥ pres_alta → VACIO_BAJO", pres)

        return FaseResult.EN_CURSO

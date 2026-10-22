# state_machine/cycle_phases/secado.py
import time
import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)

_PASO_VACIO_BAJO = "VACIO_BAJO"
_PASO_AIRE_ALTO  = "AIRE_ALTO"

# Modos 1/2 (E3, tanda 2026-10-14): antes terminaban COMPLETADO al vencer el
# tiempo sin leer la presión (secado.py:76-95 del commit 74787d8), así que una
# bomba averiada daba un ciclo "exitoso" sin secado. Ahora exigen vacío real:
# presión de cámara bajo atm − rango_presion_atm dentro de timeout_pulso, y
# una pérdida sostenida de ese vacío (debounce de 3 lecturas) es FALLO.
_DEBOUNCE_LECTURAS = 3


class SecadoFase(BaseFase):
    name = "SECADO"
    # D8-2.12 (DECISIÓN SIN CONFIRMAR): la duración del secado tampoco cuenta
    # los segundos sin datos (fin del conteo, no un timeout)
    _VENTANAS_ESTABILIDAD = ("_timer_fin",)

    def reset(self):
        self._inicializado      = False
        self._timer_fin         = None
        self._timeout_pulso_fin = None
        self._sub_estado        = None
        self._vacio_alcanzado   = False
        self._limite_vacio      = None
        self._lecturas_sin_vacio = 0
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
            self._timer_fin = time.monotonic() + float(tiempo_min) * 60
            timeout_seg = self.cycle.get_param("secado", "timeout_pulso") or 10
            if modo == 3:
                self._timeout_pulso_fin = time.monotonic() + float(timeout_seg)
                self._sub_estado = _PASO_VACIO_BAJO
            else:
                self._limite_vacio = time.monotonic() + float(timeout_seg)
            # DESCOMPRESION deja abierta su válvula de reposo; sin cerrarla la
            # bomba no puede hacer vacío (revisión de T5)
            self.set_do.descompresion_rapida_off()
            self.set_do.descompresion_lenta_off()
            self.set_do.descompresion_chaqueta_off()
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

    def _vigilar_vacio(self, modo: int):
        """Modos 1/2: FaseResult.FALLO si no hay vacío real; None si sigue."""
        pres = self._pres_camara()
        umbral = self._pres_atm() - self._rango_atm()
        if pres is not None:
            if pres < umbral:
                self._vacio_alcanzado = True
                self._lecturas_sin_vacio = 0
            elif self._vacio_alcanzado:
                self._lecturas_sin_vacio += 1
                if self._lecturas_sin_vacio >= _DEBOUNCE_LECTURAS:
                    return self._fallo(f"Secado modo {modo}: se perdió el vacío "
                                       f"({pres:.0f} kPa ≥ {umbral:.0f} kPa)")
        if (not self._vacio_alcanzado and self._limite_vacio is not None
                and time.monotonic() > self._limite_vacio):
            return self._fallo(f"Secado modo {modo}: sin vacío real (la presión no bajó de "
                               f"{umbral:.0f} kPa a tiempo); revise la bomba de vacío")
        return None

    def _fallo(self, motivo: str) -> FaseResult:
        logger.error("SecadoFase: FALLO — %s", motivo)
        self._apagar_todo()
        self.estado.motivo_fallo = motivo
        return FaseResult.FALLO

    def _apagar_todo(self):
        self.set_do.bomba_vacio_off()
        self.set_do.vacio_camara_off()
        self.set_do.aire_admosferico_camara_off()
        self.set_do.vapor_chaqueta_off()
        self.estado.fase_en_sostenimiento = False

    # ── modos ───────────────────────────────────────────────────────────

    def _tick_modo_1(self) -> FaseResult:
        fallo = self._vigilar_vacio(1)
        if fallo is not None:
            return fallo
        if time.monotonic() >= self._timer_fin:
            if not self._vacio_alcanzado:
                return self._fallo("Secado modo 1: terminó sin alcanzar vacío real")
            self._apagar_todo()
            logger.info("SecadoFase modo 1: COMPLETADO")
            return FaseResult.COMPLETADO
        self._tick_chaqueta()
        self.set_do.bomba_vacio_on()
        self.set_do.vacio_camara_on()
        return FaseResult.EN_CURSO

    def _tick_modo_2(self) -> FaseResult:
        fallo = self._vigilar_vacio(2)
        if fallo is not None:
            return fallo
        if time.monotonic() >= self._timer_fin:
            if not self._vacio_alcanzado:
                return self._fallo("Secado modo 2: terminó sin alcanzar vacío real")
            self._apagar_todo()
            logger.info("SecadoFase modo 2: COMPLETADO")
            return FaseResult.COMPLETADO
        self._tick_chaqueta()
        self.set_do.bomba_vacio_on()
        self.set_do.vacio_camara_on()
        self.set_do.aire_admosferico_camara_on()
        return FaseResult.EN_CURSO

    def _tick_modo_3(self) -> FaseResult:
        if time.monotonic() >= self._timer_fin:
            self._apagar_todo()
            logger.info("SecadoFase modo 3: COMPLETADO")
            return FaseResult.COMPLETADO

        self._tick_chaqueta()
        pres = self._pres_camara()

        if self._sub_estado == _PASO_VACIO_BAJO:
            presion_baja = float(self.cycle.get_param("secado", "presion_baja_secado") or 20)
            self.set_do.bomba_vacio_on()
            self.set_do.vacio_camara_on()

            if time.monotonic() > self._timeout_pulso_fin:
                return self._fallo("Secado modo 3: no se alcanzó la presión baja de vacío a tiempo")

            if pres is not None and pres <= presion_baja:
                self.set_do.bomba_vacio_off()
                self.set_do.vacio_camara_off()
                timeout_seg = self.cycle.get_param("secado", "timeout_pulso") or 10
                self._timeout_pulso_fin = time.monotonic() + float(timeout_seg)
                self._sub_estado = _PASO_AIRE_ALTO
                logger.info("SecadoFase: %.1f kPa ≤ pres_baja → AIRE_ALTO", pres)

        elif self._sub_estado == _PASO_AIRE_ALTO:
            presion_alta = float(self.cycle.get_param("secado", "presion_alta_secado") or 80)
            self.set_do.aire_admosferico_camara_on()

            if time.monotonic() > self._timeout_pulso_fin:
                return self._fallo("Secado modo 3: no se alcanzó la presión alta de aire a tiempo")

            if pres is not None and pres >= presion_alta:
                self.set_do.aire_admosferico_camara_off()
                timeout_seg = self.cycle.get_param("secado", "timeout_pulso") or 10
                self._timeout_pulso_fin = time.monotonic() + float(timeout_seg)
                self._sub_estado = _PASO_VACIO_BAJO
                logger.info("SecadoFase: %.1f kPa ≥ pres_alta → VACIO_BAJO", pres)

        return FaseResult.EN_CURSO

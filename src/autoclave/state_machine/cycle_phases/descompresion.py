import time
import logging

from autoclave.state_machine.cycle_phases.base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class DescompresionFase(BaseFase):
    name = "DESCOMPRESION"

    def reset(self):
        self._modo             = self.cycle.get_param("descompresion", "modo", default=0)
        self._etapa            = None
        self._sub_etapa        = None
        self._t_inicio         = None
        self._t_timeout        = None
        self._t_pulso_chaqueta = None
        self._chaqueta_abierta = False
        self._t_aire_comprimido = None

    def update(self) -> FaseResult:
        if self._etapa is None:
            self._apagar_todo()
            t_pre = self.cycle.get_param("descompresion", "tiempo_pre_despresurizacion", default=0)
            if t_pre and t_pre > 0:
                self._etapa    = "pre_espera"
                self._t_inicio = time.time()
            else:
                self._etapa = "modo"
                self._iniciar_modo()
            return FaseResult.EN_CURSO

        if self._etapa == "pre_espera":
            t_pre = self.cycle.get_param("descompresion", "tiempo_pre_despresurizacion", default=0)
            if time.time() - self._t_inicio >= t_pre:
                self._etapa = "modo"
                self._iniciar_modo()
            return FaseResult.EN_CURSO

        return self._tick_modo()

    def _iniciar_modo(self):
        self._t_inicio = time.time()
        if self._modo > 0:
            timeout_min     = self.cycle.get_param("descompresion", f"modo_{self._modo}", "timeout", default=60)
            self._t_timeout = self._t_inicio + (timeout_min or 60) * 60
        if self._modo == 3:
            self._sub_etapa = "lenta"
        elif self._modo in (4, 5):
            self._sub_etapa         = "enfriamiento"
            self._t_pulso_chaqueta  = None
            self._chaqueta_abierta  = False
            self._t_aire_comprimido = None

    def _tick_modo(self) -> FaseResult:
        if self._modo > 0 and self._t_timeout and time.time() > self._t_timeout:
            self._apagar_todo()
            logger.error("DescompresionFase: timeout en modo %d", self._modo)
            return FaseResult.FALLO

        _dispatch = {
            0: self._tick_modo_0,
            1: self._tick_modo_1,
            2: self._tick_modo_2,
            3: self._tick_modo_3,
            4: self._tick_modo_4,
            5: self._tick_modo_5,
        }
        handler = _dispatch.get(self._modo)
        if handler is None:
            logger.error("DescompresionFase: modo desconocido %d", self._modo)
            return FaseResult.EN_CURSO
        return handler()

    def _en_presion_atm(self) -> bool:
        p = self._pres_camara()
        return p is not None and p <= self._pres_atm() + self._rango_atm()

    def _apagar_todo(self):
        self.set_do.descompresion_rapida_off()
        self.set_do.descompresion_lenta_off()
        self.set_do.descompresion_chaqueta_off()
        self.set_do.aire_comprimido_camara_off()
        self.set_do.agua_chaqueta_off()

    def _tick_modo_0(self) -> FaseResult:
        if self._en_presion_atm():
            return FaseResult.COMPLETADO
        return FaseResult.EN_CURSO

    def _tick_modo_1(self) -> FaseResult:
        self.set_do.descompresion_rapida_on()
        if self._en_presion_atm():
            self._apagar_todo()
            return FaseResult.COMPLETADO
        return FaseResult.EN_CURSO

    def _tick_modo_2(self) -> FaseResult:
        self.set_do.descompresion_lenta_on()
        if self._en_presion_atm():
            self._apagar_todo()
            return FaseResult.COMPLETADO
        return FaseResult.EN_CURSO

    def _tick_modo_3(self) -> FaseResult:
        if self._sub_etapa == "lenta":
            presion_cambio = self.cycle.get_param("descompresion", "modo_3", "presion_cambio", default=150)
            self.set_do.descompresion_lenta_on()
            p = self._pres_camara()
            if p is not None and p <= presion_cambio:
                self.set_do.descompresion_lenta_off()
                self._sub_etapa = "rapida"
        else:
            self.set_do.descompresion_rapida_on()
            if self._en_presion_atm():
                self._apagar_todo()
                return FaseResult.COMPLETADO
        return FaseResult.EN_CURSO

    def _tick_modo_4(self) -> FaseResult:
        return self._tick_enfriamiento(modo_key="modo_4", use_lenta=False)

    def _tick_modo_5(self) -> FaseResult:
        return self._tick_enfriamiento(modo_key="modo_5", use_lenta=True)

    def _tick_enfriamiento(self, modo_key: str, use_lenta: bool) -> FaseResult:
        if self._sub_etapa == "enfriamiento":
            return self._tick_sub_enfriamiento(modo_key, use_lenta)
        return self._tick_sub_descompresion()

    def _tick_sub_enfriamiento(self, modo_key: str, use_lenta: bool) -> FaseResult:
        now = time.time()

        presion_obj = self.cycle.get_param("descompresion", modo_key, "presion_camara_enfriamiento", default=200)
        p = self._pres_camara()
        if p is not None and p < presion_obj:
            if self._t_aire_comprimido is None or now >= self._t_aire_comprimido:
                self.set_do.aire_comprimido_camara_on()
                self._t_aire_comprimido = now + 3.0
        else:
            self.set_do.aire_comprimido_camara_off()
            self._t_aire_comprimido = None

        self.set_do.agua_chaqueta_on()

        t_on  = self.cycle.get_param("descompresion", modo_key, "tiempo_apertura_chaqueta", default=5)
        t_off = self.cycle.get_param("descompresion", modo_key, "tiempo_cierre_chaqueta",   default=10)

        if t_off == 0:
            self.set_do.descompresion_chaqueta_on()
        else:
            if self._t_pulso_chaqueta is None:
                self._t_pulso_chaqueta = now
                self._chaqueta_abierta = True
                self.set_do.descompresion_chaqueta_on()
            else:
                elapsed = now - self._t_pulso_chaqueta
                if self._chaqueta_abierta and elapsed >= t_on:
                    self.set_do.descompresion_chaqueta_off()
                    self._chaqueta_abierta = False
                    self._t_pulso_chaqueta = now
                elif not self._chaqueta_abierta and elapsed >= t_off:
                    self.set_do.descompresion_chaqueta_on()
                    self._chaqueta_abierta = True
                    self._t_pulso_chaqueta = now

        if use_lenta:
            self.set_do.descompresion_lenta_on()

        temp_obj = self.cycle.get_param("descompresion", modo_key, "temperatura_enfriamiento", default=80.0)
        t = self._temp_camara()
        if t is not None and t <= temp_obj:
            self.set_do.aire_comprimido_camara_off()
            self.set_do.agua_chaqueta_off()
            if use_lenta:
                self.set_do.descompresion_lenta_off()
            self.set_do.descompresion_chaqueta_on()
            self.set_do.descompresion_rapida_on()
            self._sub_etapa = "descompresion"

        return FaseResult.EN_CURSO

    def _tick_sub_descompresion(self) -> FaseResult:
        self.set_do.descompresion_chaqueta_on()
        self.set_do.descompresion_rapida_on()
        if self._en_presion_atm():
            self._apagar_todo()
            return FaseResult.COMPLETADO
        return FaseResult.EN_CURSO

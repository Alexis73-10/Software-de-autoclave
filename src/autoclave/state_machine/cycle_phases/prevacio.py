# state_machine/cycle_phases/prevacio.py
#
# FASE 3 — PRE-VACÍO
#
# Ejecuta N pulsos de vacío/vapor distribuidos en hasta 4 tipos (a, b, c, d).
# Cada tipo tiene sus propios parámetros; si conteo == 0 el tipo se salta.
#
# Flujo de cada pulso:
#   1. DESCOMPRESION → si pres > atm+rango: descompresion_rapida hasta pres ≤ atm+rango
#   2. VACIO_BAJO    → bomba_vacio + vacio_camara hasta pres ≤ presion_baja_pulso_X
#   3. HOLD_BAJO     → mantener vacío durante tiempo_adicional_bajo_X (seg)
#   4. VAPOR_ALTO    → vapor_camara hasta pres ≥ presion_alta_pulso_X
#   5. HOLD_ALTO     → mantener vapor durante tiempo_adicional_alto_X (seg)
#   → siguiente pulso / siguiente tipo / COMPLETADO
#
# Parámetros JSON (sección "prevacio"):
#   conteo_pulso_{x}          — número de pulsos del tipo (0 = saltar)
#   presion_baja_pulso_{x}    — presión objetivo de vacío  [kPa]
#   tiempo_adicional_bajo_{x} — hold en vacío              [seg]
#   presion_alta_pulso_{x}    — presión objetivo de vapor  [kPa]
#   tiempo_adicional_alto_{x} — hold en vapor              [seg]
#   timeout_bajo              — timeout máx. para alcanzar vacío  [min]
#   timeout_alto              — timeout máx. para alcanzar presión [min]

import time
import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)

_TIPOS = ['a', 'b', 'c', 'd']

_PASO_DECOMPRESION = 'DECOMPRESION'
_PASO_VACIO_BAJO   = 'VACIO_BAJO'
_PASO_HOLD_BAJO    = 'HOLD_BAJO'
_PASO_VAPOR_ALTO   = 'VAPOR_ALTO'
_PASO_HOLD_ALTO    = 'HOLD_ALTO'


class PrevacioFase(BaseFase):

    name = "PRE_VACIO"

    def reset(self):
        self._tipo_idx         = 0
        self._pulso_actual     = 1
        self._conteo_tipo      = 0
        self._paso             = None
        self._inicializado     = False
        self._hold_inicio      = None
        self._timeout_bajo_fin = None
        self._timeout_alto_fin = None
        self.estado.fase_en_sostenimiento = False
        if hasattr(self.estado, "prevacio_progreso"):
            self.estado.prevacio_progreso = ""

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------

    def update(self) -> FaseResult:
        if not self._inicializado:
            resultado = self._inicializar()
            if resultado is not None:
                return resultado
        return self._ejecutar_paso()

    # ------------------------------------------------------------------
    # Inicialización: primer tipo con conteo > 0
    # ------------------------------------------------------------------

    def _inicializar(self) -> FaseResult | None:
        while self._tipo_idx < len(_TIPOS):
            tipo   = _TIPOS[self._tipo_idx]
            conteo = int(self.cycle.get_param("prevacio", f"conteo_pulso_{tipo}") or 0)
            if conteo > 0:
                self._conteo_tipo  = conteo
                self._pulso_actual = 1
                self._paso         = _PASO_DECOMPRESION
                self._inicializado = True
                self._actualizar_progreso()
                logger.info("PrevacioFase: tipo %s, %d pulsos — inicio", tipo.upper(), conteo)
                return None
            logger.info("PrevacioFase: tipo %s conteo=0, saltando", tipo.upper())
            self._tipo_idx += 1

        logger.info("PrevacioFase: todos los tipos en 0 — fase saltada")
        return FaseResult.COMPLETADO

    # ------------------------------------------------------------------
    # Máquina de pasos del pulso activo
    # ------------------------------------------------------------------

    def _ejecutar_paso(self) -> FaseResult:
        pres  = self._pres_camara()
        atm   = self._pres_atm()
        rango = self._rango_atm()
        tipo  = _TIPOS[self._tipo_idx]

        # ── 1. DESCOMPRESION ──────────────────────────────────────────
        if self._paso == _PASO_DECOMPRESION:
            if pres is None:
                return FaseResult.EN_CURSO
            if pres > atm + rango:
                self.set_do.descompresion_rapida_on()
            else:
                self.set_do.descompresion_rapida_off()
                timeout_min = self.cycle.get_param("prevacio", "timeout_bajo") or 10
                self._timeout_bajo_fin = time.time() + float(timeout_min) * 60
                self._paso = _PASO_VACIO_BAJO
                logger.info(
                    "PrevacioFase: tipo %s pulso %d/%d — iniciando vacío",
                    tipo.upper(), self._pulso_actual, self._conteo_tipo
                )
            return FaseResult.EN_CURSO

        # ── 2. VACIO BAJO ─────────────────────────────────────────────
        if self._paso == _PASO_VACIO_BAJO:
            if time.time() > self._timeout_bajo_fin:
                logger.error(
                    "PrevacioFase: TIMEOUT vacío bajo (tipo %s pulso %d)",
                    tipo.upper(), self._pulso_actual
                )
                self._apagar_vacio()
                return FaseResult.FALLO

            presion_baja = self.cycle.get_param("prevacio", f"presion_baja_pulso_{tipo}") or 15
            self.set_do.bomba_vacio_on()
            self.set_do.vacio_camara_on()

            if pres is not None and pres <= presion_baja:
                self._hold_inicio = time.time()
                self._paso = _PASO_HOLD_BAJO
                logger.info(
                    "PrevacioFase: vacío bajo alcanzado %.1f kPa (tipo %s pulso %d)",
                    pres, tipo.upper(), self._pulso_actual
                )
            return FaseResult.EN_CURSO

        # ── 3. HOLD BAJO ──────────────────────────────────────────────
        if self._paso == _PASO_HOLD_BAJO:
            tiempo_hold = self.cycle.get_param("prevacio", f"tiempo_adicional_bajo_{tipo}") or 0
            self.set_do.bomba_vacio_on()
            self.set_do.vacio_camara_on()

            if time.time() >= self._hold_inicio + float(tiempo_hold):
                self._apagar_vacio()
                timeout_min = self.cycle.get_param("prevacio", "timeout_alto") or 10
                self._timeout_alto_fin = time.time() + float(timeout_min) * 60
                self._paso = _PASO_VAPOR_ALTO
                logger.info(
                    "PrevacioFase: hold bajo completado (tipo %s pulso %d) — activando vapor",
                    tipo.upper(), self._pulso_actual
                )
            return FaseResult.EN_CURSO

        # ── 4. VAPOR ALTO ─────────────────────────────────────────────
        if self._paso == _PASO_VAPOR_ALTO:
            if time.time() > self._timeout_alto_fin:
                logger.error(
                    "PrevacioFase: TIMEOUT presión alta (tipo %s pulso %d)",
                    tipo.upper(), self._pulso_actual
                )
                self.set_do.vapor_camara_off()
                return FaseResult.FALLO

            presion_alta = self.cycle.get_param("prevacio", f"presion_alta_pulso_{tipo}") or 180
            self.set_do.vapor_camara_on()

            if pres is not None and pres >= presion_alta:
                self._hold_inicio = time.time()
                self._paso = _PASO_HOLD_ALTO
                logger.info(
                    "PrevacioFase: presión alta alcanzada %.1f kPa (tipo %s pulso %d)",
                    pres, tipo.upper(), self._pulso_actual
                )
            return FaseResult.EN_CURSO

        # ── 5. HOLD ALTO ──────────────────────────────────────────────
        if self._paso == _PASO_HOLD_ALTO:
            tiempo_hold = self.cycle.get_param("prevacio", f"tiempo_adicional_alto_{tipo}") or 0
            self.set_do.vapor_camara_on()

            if time.time() >= self._hold_inicio + float(tiempo_hold):
                self.set_do.vapor_camara_off()
                return self._avanzar_pulso()
            return FaseResult.EN_CURSO

        return FaseResult.EN_CURSO

    # ------------------------------------------------------------------
    # Avanzar al siguiente pulso / tipo
    # ------------------------------------------------------------------

    def _avanzar_pulso(self) -> FaseResult:
        self._pulso_actual += 1

        if self._pulso_actual <= self._conteo_tipo:
            self._paso = _PASO_DECOMPRESION
            self._actualizar_progreso()
            tipo = _TIPOS[self._tipo_idx]
            logger.info(
                "PrevacioFase: pulso %d/%d tipo %s",
                self._pulso_actual, self._conteo_tipo, tipo.upper()
            )
            return FaseResult.EN_CURSO

        # Tipo terminado → buscar siguiente con conteo > 0
        self._tipo_idx += 1
        while self._tipo_idx < len(_TIPOS):
            sig_tipo   = _TIPOS[self._tipo_idx]
            sig_conteo = int(self.cycle.get_param("prevacio", f"conteo_pulso_{sig_tipo}") or 0)
            if sig_conteo > 0:
                self._conteo_tipo  = sig_conteo
                self._pulso_actual = 1
                self._paso         = _PASO_DECOMPRESION
                self._actualizar_progreso()
                logger.info(
                    "PrevacioFase: avanzando a tipo %s (%d pulsos)", sig_tipo.upper(), sig_conteo
                )
                return FaseResult.EN_CURSO
            logger.info("PrevacioFase: tipo %s conteo=0, saltando", sig_tipo.upper())
            self._tipo_idx += 1

        logger.info("PrevacioFase: COMPLETADO")
        if hasattr(self.estado, "prevacio_progreso"):
            self.estado.prevacio_progreso = ""
        return FaseResult.COMPLETADO

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apagar_vacio(self):
        self.set_do.bomba_vacio_off()
        self.set_do.vacio_camara_off()

    def _actualizar_progreso(self):
        if hasattr(self.estado, "prevacio_progreso") and self._tipo_idx < len(_TIPOS):
            tipo = _TIPOS[self._tipo_idx]
            self.estado.prevacio_progreso = (
                f"{tipo.upper()}  {self._pulso_actual}/{self._conteo_tipo}"
            )

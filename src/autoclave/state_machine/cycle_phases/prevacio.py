# state_machine/cycle_phases/prevacio.py
#
# FASE 3 — PRE-VACÍO
#
# Ejecuta N pulsos de vacío/vapor distribuidos en hasta 4 tipos (a, b, c, d).
# Cada tipo tiene sus propios parámetros; si conteo == 0 el tipo se salta.
#
# Flujo de cada pulso:
#   1. DESCOMPRESION → si pres > atm+presion_inicio_vacio: descompresion_rapida
#                      hasta pres ≤ atm+presion_inicio_vacio (A12, tanda 28;
#                      antes atm+rango_presion_atm, el rango de cámara segura,
#                      que podía no alcanzarse nunca: el pulso quedaba detenido
#                      sin vapor ni bomba). Tiempo límite timeout_descompresion
#                      → FALLO CIC-20 sin encender la bomba.
#   2. VACIO_BAJO    → bomba_vacio + vacio_camara hasta pres ≤ presion_baja_pulso_X
#   3. HOLD_BAJO     → mantener vacío durante tiempo_adicional_bajo_X (seg)
#   4. VAPOR_ALTO    → vapor_camara + descompresion_lenta hasta pres ≥ presion_alta_pulso_X
#   5. HOLD_ALTO     → mantener vapor_camara + descompresion_lenta durante tiempo_adicional_alto_X (seg)
#   → siguiente pulso / siguiente tipo / COMPLETADO
#
# descompresion_lenta se enciende en espejo de vapor_camara durante los pasos
# VAPOR_ALTO/HOLD_ALTO (sin timer propio) y se apaga junto con vapor_camara al
# cerrar el pulso, sea por éxito o por timeout de presión alta.
#
# Parámetros JSON (sección "prevacio"):
#   conteo_pulso_{x}          — número de pulsos del tipo (0 = saltar)
#   presion_baja_pulso_{x}    — presión objetivo de vacío  [kPa]
#   tiempo_adicional_bajo_{x} — hold en vacío              [seg]
#   presion_alta_pulso_{x}    — presión objetivo de vapor  [kPa]
#   tiempo_adicional_alto_{x} — hold en vapor              [seg]
#   timeout_bajo              — timeout máx. para alcanzar vacío  [min]
#   timeout_alto              — timeout máx. para alcanzar presión [min]
#   presion_inicio_vacio      — kPa sobre la atmosférica para arrancar el vacío (A12)
#   timeout_descompresion     — timeout máx. del paso DECOMPRESION [min] (A12)
#
# A12 (tanda 28), revisión de las demás comparaciones del pulso: VACIO_BAJO y
# VAPOR_ALTO comparan contra presiones absolutas del programa y ya tienen
# tiempo límite (timeout_bajo / timeout_alto → FALLO); una presion_alta_pulso
# subatmosférica se alcanza subiendo desde el vacío, así que no se atascan.
# Solo DECOMPRESION dependía de la atmosférica sin margen ni tiempo límite.

import time
import logging
from .base_fase import BaseFase, FaseResult
from autoclave.core.managers.catalogo_parametros import (
    PRESION_INICIO_VACIO_DEFECTO, TIMEOUT_DESCOMPRESION_DEFECTO)
from autoclave.state_machine.alarms.catalogo import CIC_20

logger = logging.getLogger(__name__)

_TIPOS = ['a', 'b', 'c', 'd']

_PASO_DECOMPRESION   = 'DECOMPRESION'
_PASO_VACIO_BAJO     = 'VACIO_BAJO'
_PASO_HOLD_BAJO      = 'HOLD_BAJO'
_PASO_APAGANDO_VACIO = 'APAGANDO_VACIO'
_PASO_VAPOR_ALTO     = 'VAPOR_ALTO'
_PASO_HOLD_ALTO      = 'HOLD_ALTO'

# Al cerrar el pulso bajo se desenergizan 4 bobinas de 24V casi a la vez
# (bomba_vacio + agua_bomba, vacio_camara + agua_intercambiador). Sin diodo
# flyback en alguna de ellas, el golpe inductivo combinado de apagarlas
# juntas puede acoplarse por EMI al módulo E/S y desconectarlo
# (observado en un equipo de pruebas con la electrónica anterior; la mitigación se conserva con los módulos M31-U). Mitigación temporal: escalonar el apagado en dos grupos
# separados por este intervalo, mientras se verifica/instala supresión en
# las bobinas. No reemplaza el fix de hardware.
_STAGGER_APAGADO_VACIO = 0.15  # segundos


class PrevacioFase(BaseFase):

    name = "PRE_VACIO"
    # D8-2.12: hold bajo / hold alto de cada pulso
    _VENTANAS_ESTABILIDAD = ("_hold_inicio",)

    def reset(self):
        self._tipo_idx         = 0
        self._pulso_actual     = 1
        self._conteo_tipo      = 0
        self._paso             = None
        self._inicializado     = False
        self._hold_inicio      = None
        self._t_apagado_vacio  = None
        self._timeout_bajo_fin = None
        self._timeout_alto_fin = None
        self._timeout_desc_fin = None
        # A12: (código, valores) del FALLO propio; CicloState lo registra
        self.alarma_fallo      = None
        self.estado.fase_en_sostenimiento = False
        if hasattr(self.estado, "prevacio_progreso"):
            self.estado.prevacio_progreso = ""
        if hasattr(self.estado, "sub_estado_ciclo"):
            self.estado.sub_estado_ciclo = ""

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------

    def update(self) -> FaseResult:
        if not self.cap.has_vacuum:
            logger.info("PrevacioFase: sin bomba de vacío — fase saltada")
            return FaseResult.COMPLETADO
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
                self._set_paso(_PASO_DECOMPRESION)
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
        tipo  = _TIPOS[self._tipo_idx]

        # ── 1. DESCOMPRESION ──────────────────────────────────────────
        if self._paso == _PASO_DECOMPRESION:
            margen = self._presion_inicio_vacio()
            # A12: el tiempo límite corre desde el primer tick del paso, también
            # sin lectura de presión (es un límite de seguridad)
            if self._timeout_desc_fin is None:
                self._timeout_desc_fin = (time.monotonic()
                                          + self._timeout_descompresion_min() * 60)
            if time.monotonic() > self._timeout_desc_fin:
                return self._fallo_descompresion(tipo, atm, margen)
            if pres is None:
                return FaseResult.EN_CURSO
            if pres > atm + margen:
                self.set_do.descompresion_rapida_on()
            else:
                self.set_do.descompresion_rapida_off()
                timeout_min = self.cycle.get_param("prevacio", "timeout_bajo") or 10
                self._timeout_bajo_fin = time.monotonic() + float(timeout_min) * 60
                self._set_paso(_PASO_VACIO_BAJO)
                logger.info(
                    "PrevacioFase: tipo %s pulso %d/%d — iniciando vacío",
                    tipo.upper(), self._pulso_actual, self._conteo_tipo
                )
            return FaseResult.EN_CURSO

        # ── 2. VACIO BAJO ─────────────────────────────────────────────
        if self._paso == _PASO_VACIO_BAJO:
            if time.monotonic() > self._timeout_bajo_fin:
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
                self._hold_inicio = time.monotonic()
                self._set_paso(_PASO_HOLD_BAJO)
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

            if time.monotonic() >= self._hold_inicio + float(tiempo_hold):
                self.set_do.bomba_vacio_off()
                self._t_apagado_vacio = time.monotonic()
                self._set_paso(_PASO_APAGANDO_VACIO)
            return FaseResult.EN_CURSO

        # ── 3b. APAGANDO VACIO (escalonado, ver _STAGGER_APAGADO_VACIO) ─
        if self._paso == _PASO_APAGANDO_VACIO:
            if time.monotonic() - self._t_apagado_vacio >= _STAGGER_APAGADO_VACIO:
                self.set_do.vacio_camara_off()
                timeout_min = self.cycle.get_param("prevacio", "timeout_alto") or 10
                self._timeout_alto_fin = time.monotonic() + float(timeout_min) * 60
                self._set_paso(_PASO_VAPOR_ALTO)
                logger.info(
                    "PrevacioFase: hold bajo completado (tipo %s pulso %d) — activando vapor",
                    tipo.upper(), self._pulso_actual
                )
            return FaseResult.EN_CURSO

        # ── 4. VAPOR ALTO ─────────────────────────────────────────────
        if self._paso == _PASO_VAPOR_ALTO:
            if time.monotonic() > self._timeout_alto_fin:
                logger.error(
                    "PrevacioFase: TIMEOUT presión alta (tipo %s pulso %d)",
                    tipo.upper(), self._pulso_actual
                )
                self.set_do.vapor_camara_off()
                self.set_do.descompresion_lenta_off()
                return FaseResult.FALLO

            presion_alta = self.cycle.get_param("prevacio", f"presion_alta_pulso_{tipo}") or 180
            self.set_do.vapor_camara_on()
            self.set_do.descompresion_lenta_on()

            if pres is not None and pres >= presion_alta:
                self._hold_inicio = time.monotonic()
                self._set_paso(_PASO_HOLD_ALTO)
                logger.info(
                    "PrevacioFase: presión alta alcanzada %.1f kPa (tipo %s pulso %d)",
                    pres, tipo.upper(), self._pulso_actual
                )
            return FaseResult.EN_CURSO

        # ── 5. HOLD ALTO ──────────────────────────────────────────────
        if self._paso == _PASO_HOLD_ALTO:
            tiempo_hold = self.cycle.get_param("prevacio", f"tiempo_adicional_alto_{tipo}") or 0
            self.set_do.vapor_camara_on()
            self.set_do.descompresion_lenta_on()

            if time.monotonic() >= self._hold_inicio + float(tiempo_hold):
                self.set_do.vapor_camara_off()
                self.set_do.descompresion_lenta_off()
                return self._avanzar_pulso()
            return FaseResult.EN_CURSO

        return FaseResult.EN_CURSO

    # ------------------------------------------------------------------
    # Avanzar al siguiente pulso / tipo
    # ------------------------------------------------------------------

    def _avanzar_pulso(self) -> FaseResult:
        self._pulso_actual += 1

        if self._pulso_actual <= self._conteo_tipo:
            self._set_paso(_PASO_DECOMPRESION)
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
                self._set_paso(_PASO_DECOMPRESION)
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
        if hasattr(self.estado, "sub_estado_ciclo"):
            self.estado.sub_estado_ciclo = ""
        return FaseResult.COMPLETADO

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _presion_inicio_vacio(self) -> float:
        """A12: prevacio.presion_inicio_vacio (kPa sobre la atmosférica),
        recortado a 2–15 (revisor A12, H1); sin un valor numérico, el defecto (10)."""
        valor = self.cycle.get_param("prevacio", "presion_inicio_vacio")
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor != valor:
            return float(PRESION_INICIO_VACIO_DEFECTO)
        return float(min(max(valor, 2.0), 15.0))

    def _timeout_descompresion_min(self) -> float:
        """A12: prevacio.timeout_descompresion (min), recortado a 1–30; sin un
        valor numérico, el defecto (5)."""
        valor = self.cycle.get_param("prevacio", "timeout_descompresion")
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor != valor:
            return float(TIMEOUT_DESCOMPRESION_DEFECTO)
        return float(min(max(valor, 1), 30))

    def _fallo_descompresion(self, tipo: str, atm: float, margen: float) -> FaseResult:
        """A12: vence timeout_descompresion. Apaga el escape rápido (las
        salidas de la fase) sin encender la bomba; CicloState registra CIC-20
        y ejecuta el protocolo de fallo normal (que ventea la cámara)."""
        minutos = self._timeout_descompresion_min()
        logger.error("PrevacioFase: TIMEOUT descompresión (tipo %s pulso %d): la cámara no bajó "
                     "a %.1f kPa en %g min", tipo.upper(), self._pulso_actual, atm + margen,
                     minutos)
        self.set_do.descompresion_rapida_off()
        pulso = f"{tipo.upper()} {self._pulso_actual}/{self._conteo_tipo}"
        self.alarma_fallo = (CIC_20, {"maximo": atm + margen, "margen": f"{margen:g}",
                                      "minutos": f"{minutos:g}", "pulso": pulso})
        self.estado.motivo_fallo = (
            f"La presión de cámara no bajó a {atm + margen:.1f} kPa en {minutos:g} min "
            f"(descompresión del pulso {pulso} del prevacío)")
        return FaseResult.FALLO

    def _apagar_vacio(self):
        self.set_do.bomba_vacio_off()
        self.set_do.vacio_camara_off()

    def _set_paso(self, paso: str) -> None:
        self._paso = paso
        if paso == _PASO_DECOMPRESION:
            self._timeout_desc_fin = None      # A12: se arma en el primer tick del paso
        if hasattr(self.estado, "sub_estado_ciclo"):
            self.estado.sub_estado_ciclo = paso

    def _actualizar_progreso(self):
        if hasattr(self.estado, "prevacio_progreso") and self._tipo_idx < len(_TIPOS):
            tipo = _TIPOS[self._tipo_idx]
            self.estado.prevacio_progreso = (
                f"{tipo.upper()}  {self._pulso_actual}/{self._conteo_tipo}"
            )

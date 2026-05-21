# state_machine/states/ciclo.py
#
# ESTADO GLOBAL — CICLO
#
# Orquesta el pipeline de fases del ciclo de esterilización:
#
#   PRECALENTAMIENTO → PURGA → PRE_VACIO →
#   CALENTAMIENTO → ESTABILIZACION → ESTERILIZACION
#
# Retorna una de estas cadenas al StateMachine en cada tick:
#   "EN_CURSO"   — ciclo en ejecución, no hacer nada
#   "COMPLETADO" — todas las fases OK → volver a PREPARADO
#   "FALLO"      — fase falló o emergencia → ir a FALLA
#   "CANCELADO"  — usuario abortó → volver a PREPARADO

import logging
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.state_machine.cycle_phases.precalentamiento import PrecalentamientoFase
from autoclave.state_machine.cycle_phases.purga import PurgaFase
from autoclave.state_machine.cycle_phases.prevacio import PrevacioFase
from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase
from autoclave.state_machine.cycle_phases.estabilizacion import EstabilizacionFase
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase

logger = logging.getLogger(__name__)

# Resultado textual que CicloState devuelve al StateMachine
class CicloResultado:
    EN_CURSO   = "EN_CURSO"
    COMPLETADO = "COMPLETADO"
    FALLO      = "FALLO"
    CANCELADO  = "CANCELADO"


class CicloState:
    """
    Orquestador del estado CICLO.

    Dependencias inyectadas por StateMachine:
        estado        → EstadoAutoclave
        set_do        → SetOutput
        cycle         → Cycle  (ciclo seleccionado al inicio del ciclo)
        config        → ConfigManager
        alarm_manager → AlarmManager
    """

    def __init__(self, estado, set_do, cycle, config, alarm_manager):
        self.estado        = estado
        self.set_do        = set_do
        self.cycle         = cycle
        self.config        = config
        self.alarm_manager = alarm_manager

        # Construir pipeline (los objetos se reusan; reset() los reinicia)
        _args = (estado, set_do, cycle, config, alarm_manager)
        self._fases = [
            PrecalentamientoFase(*_args),
            PurgaFase(*_args),
            PrevacioFase(*_args),
            CalentamientoFase(*_args),
            EstabilizacionFase(*_args),
            EsterilizacionFase(*_args),
        ]

        self._protocolo = ProtocoloFallo(estado, set_do, config)
        self._fase_idx  = 0

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def reset(self):
        """
        Llamar UNA vez al entrar al estado CICLO.
        Reinicia todas las fases y el protocolo de fallo.
        """
        self._fase_idx = 0
        self._protocolo.reset()

        for fase in self._fases:
            fase.reset()

        self.estado.fase_ciclo = self._fases[0].name
        logger.info(
            "CicloState: INICIANDO — %d fases | primera: %s",
            len(self._fases), self._fases[0].name
        )

    # ------------------------------------------------------------------
    # Tick principal
    # ------------------------------------------------------------------

    def run(self) -> str:
        """
        Llamar en cada tick del control loop mientras el estado sea CICLO.
        Devuelve CicloResultado.*.
        """

        # ── 1. ¿El usuario canceló? ───────────────────────────────────
        if self.estado.get_flag("CICLO_CANCELADO"):
            logger.warning("CicloState: CANCELADO por operador")
            self.estado.fase_ciclo = "CANCELADO"
            self._protocolo.ejecutar()
            # Limpiar la flag para que no vuelva a disparar
            self.estado.set_flag("CICLO_CANCELADO", False)
            return CicloResultado.CANCELADO

        # ── 2. ¿Paro de emergencia? ───────────────────────────────────
        if self.estado.get_flag("PARO_EMERGENCIA"):
            logger.error("CicloState: ABORTADO por paro de emergencia")
            self.estado.fase_ciclo = "EMERGENCIA"
            self._protocolo.ejecutar()
            return CicloResultado.FALLO

        # ── 3. ¿Ya se completaron todas las fases? ────────────────────
        if self._fase_idx >= len(self._fases):
            logger.info("CicloState: COMPLETADO — todas las fases finalizadas")
            self.estado.fase_ciclo = "COMPLETADO"
            return CicloResultado.COMPLETADO

        # ── 4. Ejecutar la fase actual ────────────────────────────────
        fase = self._fases[self._fase_idx]
        resultado = fase.update()

        if resultado == FaseResult.EN_CURSO:
            return CicloResultado.EN_CURSO

        elif resultado == FaseResult.COMPLETADO:
            logger.info("CicloState: fase %s completada", fase.name)
            self._fase_idx += 1

            if self._fase_idx >= len(self._fases):
                logger.info("CicloState: COMPLETADO")
                self.estado.fase_ciclo = "COMPLETADO"
                return CicloResultado.COMPLETADO

            # Avanzar a la siguiente fase
            siguiente = self._fases[self._fase_idx]
            siguiente.reset()
            self.estado.fase_ciclo = siguiente.name
            logger.info("CicloState: avanzando a fase %s", siguiente.name)
            return CicloResultado.EN_CURSO

        elif resultado == FaseResult.FALLO:
            logger.error("CicloState: FALLO en fase %s", fase.name)
            self.estado.fase_ciclo = f"FALLO_{fase.name}"
            self._protocolo.ejecutar()
            return CicloResultado.FALLO

        # Fallback (no debería ocurrir)
        return CicloResultado.EN_CURSO

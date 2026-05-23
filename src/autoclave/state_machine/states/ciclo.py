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
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
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
    EN_CURSO               = "EN_CURSO"
    COMPLETADO             = "COMPLETADO"
    FALLO                  = "FALLO"
    CANCELADO              = "CANCELADO"
    # Ciclo terminado, esperando confirmación del operador antes de transicionar
    ESPERANDO_CONFIRMACION = "ESPERANDO_CONFIRMACION"


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

        self._protocolo          = ProtocoloFallo(estado, set_do, config)
        self._fase_idx           = 0
        self._resultado_pendiente: str | None = None   # resultado almacenado hasta confirmación

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def reset(self):
        """
        Llamar UNA vez al entrar al estado CICLO.
        Reinicia todas las fases y el protocolo de fallo.
        """
        self._fase_idx            = 0
        self._resultado_pendiente = None
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

    # ------------------------------------------------------------------
    # Supervisores continuos (llamados en cada tick activo)
    # ------------------------------------------------------------------

    def _verificar_puertas(self) -> tuple[bool, str]:
        """
        Verifica que ambas puertas estén cerradas y con presión de empaque.
        Retorna (ok, codigo_fallo).
        El código se usa como fase_ciclo para que la UI muestre el motivo.
        """
        min_empaque = (self.config.get("presion_empaque") or 300) * 0.6

        for num, di_cerrada, sensor_emp in [
            (1, "puerta_1_cerrada", "pres_empaque_1"),
            (2, "puerta_2_cerrada", "pres_empaque_2"),
        ]:
            cerrada = bool(self.estado.sensores_di.get(di_cerrada, 0))
            if not cerrada:
                return False, f"FALLO_PUERTA_{num}_ABIERTA"

            emp = self.estado.sensores_pres.get(sensor_emp)
            if emp is not None and emp < min_empaque:
                return False, f"FALLO_PUERTA_{num}_EMPAQUE"

        return True, ""

    def _mantener_chaqueta(self):
        """Mantiene la presión de la chaqueta durante todas las fases del ciclo."""
        pres = self.estado.sensores_pres.get("pres_chaqueta")
        if pres is None:
            return

        # Si no hay suministro de vapor, no intentar compensar
        if not self.estado.sensores_di.get("vapor_suministro", 0):
            self.set_do.vapor_chaqueta_off()
            return

        press_obj = self.cycle.get_param("globals", "presion_chaqueta") or \
                    self.config.get("presion_chaqueta") or 320
        rango     = self.cycle.get_param("globals", "rango_presion_chaqueta") or \
                    self.config.get("rango_presion_chaqueta") or 50

        if pres < press_obj - rango:
            self.set_do.vapor_chaqueta_on()
        elif pres > press_obj + rango:
            self.set_do.vapor_chaqueta_off()
        # Dentro del rango: no cambiar estado

    # ------------------------------------------------------------------
    # Tick principal
    # ------------------------------------------------------------------

    def run(self) -> str:
        """
        Llamar en cada tick del control loop mientras el estado sea CICLO.
        Devuelve CicloResultado.*.

        Flujo de confirmación:
          - Cuando el ciclo termina (COMPLETADO / FALLO / CANCELADO) el resultado
            se almacena en _resultado_pendiente y se devuelve ESPERANDO_CONFIRMACION.
          - La UI muestra el resultado y espera que el operador confirme.
          - Al confirmar, el endpoint /cycle/acknowledge activa CICLO_CONFIRMADO.
          - En el siguiente tick se devuelve el resultado real y la máquina transiciona.
        """

        # ── 0. ¿Pendiente de confirmación y ya confirmado? ────────────
        if self._resultado_pendiente is not None:
            if self.estado.get_flag("CICLO_CONFIRMADO"):
                logger.info(
                    "CicloState: confirmación recibida → %s", self._resultado_pendiente
                )
                self.estado.set_flag("CICLO_CONFIRMADO", False)
                resultado_final = self._resultado_pendiente
                self._resultado_pendiente = None
                return resultado_final
            # Mantener el protocolo activo (gestión de presión + buzzer)
            self._protocolo.update()
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 1. ¿El usuario canceló? ───────────────────────────────────
        if self.estado.get_flag("CICLO_CANCELADO"):
            logger.warning("CicloState: CANCELADO por operador")
            self.estado.fase_ciclo = "CANCELADO"
            self._protocolo.ejecutar()
            self.estado.set_flag("CICLO_CANCELADO", False)
            self._resultado_pendiente = CicloResultado.CANCELADO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 2. ¿Paro de emergencia? ───────────────────────────────────
        if self.estado.get_flag("PARO_EMERGENCIA"):
            logger.error("CicloState: ABORTADO por paro de emergencia")
            self.estado.fase_ciclo = "EMERGENCIA"
            self.alarm_manager.report(Alarm(
                alarm_id="PARO_EMERGENCIA",
                alarm_type=AlarmType.EMERGENCIA,
                source_state="CICLO",
                description="Paro de emergencia activado durante el ciclo.",
                recoverable=False,
            ))
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 3. Verificar puertas y empaque ────────────────────────────
        puertas_ok, codigo_fallo = self._verificar_puertas()
        if not puertas_ok:
            logger.error("CicloState: FALLO de seguridad — %s", codigo_fallo)
            self.estado.fase_ciclo = codigo_fallo
            self.alarm_manager.report(Alarm(
                alarm_id=codigo_fallo,
                alarm_type=AlarmType.FALLA,
                source_state="CICLO",
                description=f"Fallo de seguridad: {codigo_fallo.replace('_', ' ').lower()}.",
                recoverable=True,
            ))
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 4. Mantener presión de chaqueta ───────────────────────────
        self._mantener_chaqueta()

        # ── 5. ¿Ya se completaron todas las fases? ────────────────────
        if self._fase_idx >= len(self._fases):
            logger.info("CicloState: COMPLETADO — todas las fases finalizadas")
            self.estado.fase_ciclo = "COMPLETADO"
            self._resultado_pendiente = CicloResultado.COMPLETADO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 6. Ejecutar la fase actual ────────────────────────────────
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
                self._resultado_pendiente = CicloResultado.COMPLETADO
                return CicloResultado.ESPERANDO_CONFIRMACION

            # Avanzar a la siguiente fase
            siguiente = self._fases[self._fase_idx]
            siguiente.reset()
            self.estado.fase_ciclo = siguiente.name
            logger.info("CicloState: avanzando a fase %s", siguiente.name)
            return CicloResultado.EN_CURSO

        elif resultado == FaseResult.FALLO:
            logger.error("CicloState: FALLO en fase %s", fase.name)
            self.estado.fase_ciclo = f"FALLO_{fase.name}"
            self.alarm_manager.report(Alarm(
                alarm_id=f"FALLO_{fase.name}",
                alarm_type=AlarmType.FALLA,
                source_state="CICLO",
                description=f"Fallo en la fase {fase.name.replace('_', ' ').lower()}.",
                recoverable=True,
            ))
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # Fallback (no debería ocurrir)
        return CicloResultado.EN_CURSO

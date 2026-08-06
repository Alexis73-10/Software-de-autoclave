# state_machine/states/ciclo.py
#
# ESTADO GLOBAL — CICLO
#
# Orquesta el pipeline de fases del ciclo de esterilización:
#
#   PRECALENTAMIENTO → PURGA → PRE_VACIO →
#   CALENTAMIENTO → ESTERILIZACION
#
# Retorna una de estas cadenas al StateMachine en cada tick:
#   "EN_CURSO"   — ciclo en ejecución, no hacer nada
#   "COMPLETADO" — todas las fases OK → volver a PREPARADO
#   "FALLO"      — fase falló o emergencia → ir a FALLA
#   "CANCELADO"  — usuario abortó → volver a PREPARADO

import logging
import time
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.state_machine.cycle_phases.precalentamiento import PrecalentamientoFase
from autoclave.state_machine.cycle_phases.purga import PurgaFase
from autoclave.state_machine.cycle_phases.prevacio import PrevacioFase
from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from autoclave.state_machine.cycle_phases.descompresion import DescompresionFase
from autoclave.state_machine.cycle_phases.secado import SecadoFase
from autoclave.state_machine.cycle_phases.valvula_reposo import abrir_valvula_modo, cerrar_valvulas_descompresion

logger = logging.getLogger(__name__)

_SENSORES_TEMP_CRITICOS = ["temp_camara"]
_SENSORES_PRES_CRITICOS = ["pres_camara"]
_DEBOUNCE_LECTURAS_DRENAJE = 3

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

    def __init__(self, estado, set_do, cycle, config, alarm_manager, cap=None, door_service=None):
        self.estado        = estado
        self.set_do        = set_do
        self.cycle         = cycle
        self.config        = config
        self.alarm_manager = alarm_manager
        self.cap           = cap
        self.door_service  = door_service
        self._apertura_auto_t_inicio = None
        self._apertura_auto_alarmado = False
        self._contador_drenaje_alta = 0
        self._contador_drenaje_baja = 0

        # Construir pipeline (los objetos se reusan; reset() los reinicia)
        _args = (estado, set_do, cycle, config, alarm_manager, cap)
        self._fases = [
            PrecalentamientoFase(*_args),
            PurgaFase(*_args),
            PrevacioFase(*_args),
            CalentamientoFase(*_args),
            EsterilizacionFase(*_args),
            DescompresionFase(*_args),
            SecadoFase(*_args),
        ]

        self._protocolo          = ProtocoloFallo(estado, set_do, cycle, config)
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
        self._contador_drenaje_alta = 0
        self._contador_drenaje_baja = 0
        self._apertura_auto_t_inicio = None
        self._apertura_auto_alarmado = False
        self.estado.motivo_fallo  = ""
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
        if self._fase_idx < len(self._fases) and isinstance(self._fases[self._fase_idx], SecadoFase):
            return
        pres = self.estado.sensores_pres.get("pres_chaqueta")
        if pres is None:
            return

        # Si no hay suministro de vapor, no intentar compensar
        if not self.estado.sensores_di.get("vapor_suministro", 0):
            self.set_do.vapor_chaqueta_off()
            self.alarm_manager.report(Alarm(
                alarm_id="SUMINISTRO_VAPOR",
                alarm_type=AlarmType.ALERTA,
                source_state="CICLO",
                description="Sin suministro de vapor: chaqueta pendiente hasta que regrese.",
                recoverable=True,
                blocks_operation=False,
            ))
            return
        else:
            self.alarm_manager.clear("SUMINISTRO_VAPOR")

        press_obj = self.cycle.get_param("globals", "presion_chaqueta") or \
                    self.config.get("presion_chaqueta") or 320
        rango     = self.cycle.get_param("globals", "rango_presion_chaqueta") or \
                    self.config.get("rango_presion_chaqueta") or 50

        if pres < press_obj - rango:
            self.set_do.vapor_chaqueta_on()
        elif pres > press_obj + rango:
            self.set_do.vapor_chaqueta_off()
        # Dentro del rango: no cambiar estado

    def _mantener_drenaje(self):
        """Mantiene la temperatura de drenaje durante todo el ciclo, incluyendo
        las esperas de confirmación (COMPLETADO/FALLO/CANCELADO/emergencia).
        Debounce simétrico de _DEBOUNCE_LECTURAS_DRENAJE lecturas consecutivas
        antes de cambiar el estado de la válvula, para evitar activarla por
        oscilaciones de temp_drenaje cerca del umbral. Sensor ausente no
        resetea los contadores en progreso, solo salta el tick."""
        temp = self.estado.sensores_temp.get("temp_drenaje")
        if temp is None:
            return
        temp_segura = self.config.get("temp_segura_drenaje")
        if temp_segura is None:
            return

        if temp > temp_segura:
            self._contador_drenaje_alta += 1
            self._contador_drenaje_baja = 0
        else:
            self._contador_drenaje_baja += 1
            self._contador_drenaje_alta = 0

        if self._contador_drenaje_alta >= _DEBOUNCE_LECTURAS_DRENAJE:
            self.set_do.agua_intercambiador_on()
            self.alarm_manager.report(Alarm(
                alarm_id="TEMP_DRENAJE_ALTA",
                alarm_type=AlarmType.ALERTA,
                source_state="CICLO",
                description="Temperatura de drenaje alta: enfriando.",
                recoverable=True,
                blocks_operation=False,
            ))
        elif self._contador_drenaje_baja >= _DEBOUNCE_LECTURAS_DRENAJE:
            self.set_do.agua_intercambiador_off()
            self.alarm_manager.clear("TEMP_DRENAJE_ALTA")

    def _mantener_valvula_reposo(self):
        """Mientras se espera confirmación tras un COMPLETADO limpio (sin
        ProtocoloFallo, que ya hace su propia gestión continua): si la
        cámara cae en vacío por enfriamiento, abre aire atmosférico; si no,
        mantiene la válvula de descompresión del modo configurado."""
        pres = self.estado.sensores_pres.get("pres_camara")
        if pres is None:
            return
        atm   = self.config.get("presion_admosferica") or 101.3
        rango = self.config.get("rango_presion_atm")   or 20.0

        if pres < atm - rango:
            cerrar_valvulas_descompresion(self.set_do)
            self.set_do.aire_admosferico_camara_on()
        else:
            self.set_do.aire_admosferico_camara_off()
            modo = self.cycle.get_param("descompresion", "modo", default=0) or 0
            abrir_valvula_modo(self.set_do, modo)

    def _mantener_apertura_automatica(self):
        """Si finalizacion.apertura_automatica está activo, abre la puerta de
        descarga y confirma el ciclo sin esperar al operador. Solo se llama
        mientras _resultado_pendiente == COMPLETADO. Secuencia: espera fija
        (tiempo_espera_apertura) → espera a que temp_camara baje a
        temp_max_apertura (avisando por alarma no bloqueante si tarda más de
        timeout_temperatura, sin dejar de esperar) → abrir puerta + confirmar."""
        if self.door_service is None:
            return
        if not self.cycle.get_param("finalizacion", "apertura_automatica", default=False):
            return

        if self._apertura_auto_t_inicio is None:
            self._apertura_auto_t_inicio = time.time()

        tiempo_espera = self.cycle.get_param("finalizacion", "tiempo_espera_apertura", default=60)
        elapsed = time.time() - self._apertura_auto_t_inicio
        if elapsed < tiempo_espera:
            return

        temp = self.estado.sensores_temp.get("temp_camara")
        if temp is None:
            return

        temp_max = self.cycle.get_param("finalizacion", "temp_max_apertura", default=80.0)
        if temp > temp_max:
            timeout_seg = self.cycle.get_param("finalizacion", "timeout_temperatura", default=30) * 60
            if not self._apertura_auto_alarmado and (elapsed - tiempo_espera) > timeout_seg:
                self._apertura_auto_alarmado = True
                self.alarm_manager.report(Alarm(
                    alarm_id="TIMEOUT_APERTURA_AUTOMATICA",
                    alarm_type=AlarmType.ALERTA,
                    source_state="CICLO",
                    description="Apertura automática: la cámara tarda más de lo esperado en enfriar.",
                    recoverable=True,
                    blocks_operation=False,
                ))
            return

        puerta = "Puerta 2" if "Puerta 2" in self.door_service.doors else "Puerta 1"
        ok, _motivo = self.door_service.request_open(puerta)
        if ok:
            if self._apertura_auto_alarmado:
                self.alarm_manager.clear("TIMEOUT_APERTURA_AUTOMATICA")
            self.estado.set_flag("CICLO_CONFIRMADO", True)

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
            # Mantener la válvula de reposo activa mientras se espera
            # confirmación: COMPLETADO limpio usa su propio monitor de
            # presión; el resto (FALLO/CANCELADO/emergencia) ya lo cubre
            # el protocolo de fallo, que corre continuamente. El drenaje
            # se mantiene sin importar la causa de fin de ciclo.
            # _mantener_drenaje() corre DESPUÉS de _protocolo.update(): si el
            # ALL_OFF inicial no se confirmó (ACK perdido por caída serial),
            # update() reintenta reset_all_outputs() y apagaría el agua del
            # intercambiador justo después de que este método la encendiera.
            if self._resultado_pendiente == CicloResultado.COMPLETADO:
                self._mantener_valvula_reposo()
            else:
                self._protocolo.update()
            self._mantener_drenaje()
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
            self.estado.motivo_fallo = "Paro de emergencia activado durante el ciclo."
            self.alarm_manager.report(Alarm(
                alarm_id="PARO_EMERGENCIA",
                alarm_type=AlarmType.EMERGENCIA,
                source_state="CICLO",
                description=self.estado.motivo_fallo,
                recoverable=False,
            ))
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 2b. ¿Fallo de suministro eléctrico? ──────────────────────
        if self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO"):
            logger.error("CicloState: ABORTADO por fallo de suministro eléctrico")
            self.estado.fase_ciclo = "FALLO_SUMINISTRO"
            self.estado.motivo_fallo = "Pérdida de suministro eléctrico durante el ciclo."
            self.alarm_manager.report(Alarm(
                alarm_id="FALLO_SUMINISTRO_ELECTRICO",
                alarm_type=AlarmType.EMERGENCIA,
                source_state="CICLO",
                description=self.estado.motivo_fallo,
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
            self.estado.motivo_fallo = f"Fallo de seguridad: {codigo_fallo.replace('_', ' ').lower()}."
            self.alarm_manager.report(Alarm(
                alarm_id=codigo_fallo,
                alarm_type=AlarmType.FALLA,
                source_state="CICLO",
                description=self.estado.motivo_fallo,
                recoverable=True,
            ))
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 4. Verificar sensores críticos ────────────────────────────
        ausentes = [
            s for s in _SENSORES_TEMP_CRITICOS
            if self.estado.sensores_temp.get(s) is None
        ] + [
            s for s in _SENSORES_PRES_CRITICOS
            if self.estado.sensores_pres.get(s) is None
        ]
        if ausentes:
            logger.error("CicloState: SENSOR_AUSENTE — %s", ausentes)
            self.estado.fase_ciclo = "SENSOR_AUSENTE"
            self.estado.motivo_fallo = f"Sensor crítico ausente: {', '.join(ausentes)}"
            self.alarm_manager.report(Alarm(
                alarm_id="SENSOR_AUSENTE",
                alarm_type=AlarmType.EMERGENCIA,
                source_state="CICLO",
                description=self.estado.motivo_fallo,
                recoverable=False,
            ))
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 5. Mantener presión de chaqueta y temperatura de drenaje ──
        self._mantener_chaqueta()
        self._mantener_drenaje()

        # ── 6. ¿Ya se completaron todas las fases? ────────────────────
        if self._fase_idx >= len(self._fases):
            logger.info("CicloState: COMPLETADO — todas las fases finalizadas")
            self.estado.fase_ciclo = "COMPLETADO"
            self._resultado_pendiente = CicloResultado.COMPLETADO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 7. Ejecutar la fase actual ────────────────────────────────
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
            # La fase puede haber reportado ya un motivo específico (p.ej.
            # EsterilizacionFase._fallo() con la lectura exacta que falló);
            # sólo se usa el genérico si la fase no dejó uno más preciso.
            if not self.estado.motivo_fallo:
                self.estado.motivo_fallo = f"Fallo en la fase {fase.name.replace('_', ' ').lower()}."
            self.alarm_manager.report(Alarm(
                alarm_id=f"FALLO_{fase.name}",
                alarm_type=AlarmType.FALLA,
                source_state="CICLO",
                description=self.estado.motivo_fallo,
                recoverable=True,
            ))
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # Fallback (no debería ocurrir)
        return CicloResultado.EN_CURSO

    # ------------------------------------------------------------------
    # Aborto forzado por el ControlLoop (fuera del tick normal de run())
    # ------------------------------------------------------------------

    def abortar_por_desconexion(self):
        """Llamado por ControlLoop cuando la comunicación serial lleva caída
        más que su tolerancia (ControlLoop._TOLERANCIA_DESCONEXION_SEG)
        durante un ciclo en curso. run() no puede detectarlo por sí mismo
        porque, sin conexión, el ControlLoop deja de invocar
        state_machine.update() (no hay datos frescos de sensores) — así que
        el aborto se dispara directamente desde ControlLoop en vez de
        esperar al siguiente tick normal."""
        if self._resultado_pendiente is not None:
            return  # ya se estaba abortando/terminando por otra causa

        logger.error("CicloState: ABORTADO por pérdida de comunicación serial")
        self.estado.fase_ciclo = "FALLO_CONEXION"
        self.estado.motivo_fallo = "Se perdió la comunicación con el hardware durante el ciclo."
        self.alarm_manager.report(Alarm(
            alarm_id="FALLO_CONEXION",
            alarm_type=AlarmType.EMERGENCIA,
            source_state="CICLO",
            description=self.estado.motivo_fallo,
            recoverable=True,
        ))
        self._protocolo.ejecutar()
        self._resultado_pendiente = CicloResultado.FALLO

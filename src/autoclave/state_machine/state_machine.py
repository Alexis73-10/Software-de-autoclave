from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state
from autoclave.state_machine.states.ciclo import CicloState
from autoclave.state_machine.states.falla import FallaState
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.core.runtime.sensores_ciclo import verificar_inicio
from autoclave.state_machine.estado_seguro import ProtocoloEstadoSeguro
from autoclave.core.runtime import camara_segura
from autoclave.state_machine.states.vaciado_chaqueta import limpiar_en as limpiar_vaciado_chaqueta
import logging

logger = logging.getLogger(__name__)


class StateMachine:
    def __init__(self, io, estado, set_do, cycle, config, cap=None, door_service=None,
                 profile=None, alarm_manager=None, programas_seguridad=None,
                 temp_max_ciclo=None, al_evento_seguridad=None, estado_seguro=None):
        self.io            = io
        self.estado        = estado
        self.set_do        = set_do
        self.cycle         = cycle
        self.config        = config
        self.profile       = profile
        # Callable -> programas cuyos Principales deciden "cámara segura"
        self.programas_seguridad = programas_seguridad

        # Una sola instancia en todo el backend (spec §5.3): la inyecta el
        # ControlLoop. El AlarmManager propio queda solo para usos aislados.
        self.alarm_manager = alarm_manager if alarm_manager is not None else AlarmManager(estado)

        self.preparacion = preparacion_state(self.alarm_manager, estado, set_do, cycle, config, profile)
        self.preparado   = preparado_state(self.alarm_manager, estado, set_do, cycle, config, profile)
        self.preparado.programas_seguridad = programas_seguridad
        self.preparacion.programas_seguridad = programas_seguridad   # T1 (D-19)
        self.preparado.temp_max_ciclo = temp_max_ciclo
        self.ciclo       = CicloState(estado, set_do, cycle, config, self.alarm_manager, cap, door_service,
                                      profile)
        self.falla       = FallaState(estado, set_do, self.alarm_manager)

        self.prev_state  = None

        # Protocolo de estado seguro común (fin de ciclo §15). El ControlLoop
        # lo conserva entre reconstrucciones (set_active_cycle).
        self.estado_seguro = estado_seguro if estado_seguro is not None else ProtocoloEstadoSeguro(
            estado, config, profile=profile, programas_seguridad=programas_seguridad,
            al_evento=al_evento_seguridad)
        self.preparado.estado_seguro_activo = lambda: self.estado_seguro.activo
        self.preparacion.estado_seguro_activo = lambda: self.estado_seguro.activo
        self.estado_seguro.mantener_drenaje = self.ciclo._mantener_drenaje
        if getattr(self.estado_seguro, "alarm_manager", None) is None:
            self.estado_seguro.alarm_manager = self.alarm_manager

    # ------------------------------------------------------------------
    # Entry hook — llamado UNA vez al cambiar de estado
    # ------------------------------------------------------------------

    def on_state_entry(self, state: GlobalState):
        if state == GlobalState.PREPARACION:
            limpiar_vaciado_chaqueta(self.estado, self.set_do)
            self.preparacion.reset()

        elif state == GlobalState.FALLA:
            # El vaciado de chaqueta solo lo conduce PREPARADO
            limpiar_vaciado_chaqueta(self.estado, self.set_do)

        elif state == GlobalState.CICLO:
            # Un ciclo nuevo cierra cualquier protocolo de estado seguro previo
            # antes de reiniciar el ProtocoloFallo que comparte
            if self.estado_seguro.activo:
                self.estado_seguro.terminar()
            # Limpiar flags de ciclo anteriores y arrancar el pipeline
            self.estado.set_flag("CICLO_CANCELADO",  False)
            self.estado.set_flag("CICLO_CONFIRMADO", False)
            self.estado.set_flag("LISTO_PARA_CICLO", False)
            self.ciclo.reset()
            logger.info("StateMachine: entrando a CICLO")

        elif state == GlobalState.PREPARADO:
            # Limpiar flag de inicio para evitar auto-arranques
            self.estado.set_flag("START_CICLO", False)
            logger.info("StateMachine: entrando a PREPARADO")

    def _camara_segura_tras_ciclo(self, datos_vigentes: bool) -> bool:
        """Cámara segura con el Principal del ciclo terminado y los de los
        programas de seguridad (el mayor manda) y el menor temp_max_apertura
        (global o del ciclo). Falla cerrada: cualquier error = no segura."""
        try:
            programa = self.ciclo.cycle
            programas = [programa]
            if self.programas_seguridad is not None:
                programas += [p for p in (self.programas_seguridad() or [])
                              if p is not None and p is not programa]
            temp_max_ciclo = programa.get_param("finalizacion", "temp_max_apertura", default=None)
            segura, motivo = camara_segura.evaluar(self.estado, self.config, programas,
                                                   self.profile, datos_vigentes=datos_vigentes,
                                                   temp_max_ciclo=temp_max_ciclo)
            if not segura:
                logger.info("StateMachine: cámara no segura al reconocer el ciclo: %s", motivo)
            return segura is True
        except Exception:
            logger.exception("StateMachine: no se pudo evaluar la cámara al reconocer el ciclo")
            return False

    # ------------------------------------------------------------------
    # Tick principal
    # ------------------------------------------------------------------

    def update(self, datos_vigentes: bool = True):
        current_state = self.estado.get_machine_state()

        logger.debug(
            "Actualizando maquina de estados. Estado actual: %s",
            self.estado.estado_maquina.get("Estado")
        )

        # Protocolo de estado seguro (§15): fuera de CICLO, antes del estado
        if current_state != GlobalState.CICLO:
            # TMG-04 de T5: un error del estado seguro no impide que el estado
            # corra (ni que FALLA mantenga el ALL_OFF del paro)
            try:
                self.estado_seguro.update(datos_vigentes=datos_vigentes)
            except Exception:
                logger.exception("StateMachine: error en el protocolo de estado seguro")

        # Detectar cambio de estado → disparar hook de entrada
        if current_state != self.prev_state:
            self.on_state_entry(current_state)
            self.prev_state = current_state

        # ==============================================================
        # PREPARACION
        # ==============================================================
        if current_state == GlobalState.PREPARACION:
            logger.debug("Estado actual: PREPARACION")

            if self.preparacion.run():
                self.estado.set_machine_state(GlobalState.PREPARADO)

        # ==============================================================
        # PREPARADO
        # ==============================================================
        elif current_state == GlobalState.PREPARADO:
            logger.debug("Estado actual: PREPARADO")

            listo = bool(self.preparado.run(datos_vigentes=datos_vigentes))
            self.estado.set_flag("LISTO_PARA_CICLO", listo)

            # Transición a CICLO: sólo si el sistema está listo Y
            # el operador pulsó "Iniciar ciclo"
            if listo and self.estado.get_flag("START_CICLO"):
                self.estado.set_flag("START_CICLO", False)
                # RS-06 (tanda §1.1): asignación válida y sensores en uso con
                # lectura. Defensa en profundidad: /cycle/start ya lo rechaza.
                rechazo = verificar_inicio(self.ciclo._programa, self.profile, self.estado)
                if rechazo is not None:
                    logger.error("StateMachine: inicio de ciclo rechazado — %s: %s", *rechazo)
                    return
                self.estado.set_machine_state(GlobalState.CICLO)
                # Entrada inmediata (en este mismo tick, bajo _sm_lock): la
                # copia del programa (T-17) debe existir antes de que el
                # registro del ciclo, el progreso o un PATCH vean CICLO; si
                # no, leerían la copia del ciclo anterior hasta el tick siguiente.
                self.on_state_entry(GlobalState.CICLO)
                self.prev_state = GlobalState.CICLO

        # ==============================================================
        # CICLO
        # ==============================================================
        elif current_state == GlobalState.CICLO:
            logger.debug("Estado actual: CICLO")

            resultado = self.ciclo.run()

            if resultado == "COMPLETADO":
                logger.info("StateMachine: ciclo completado → PREPARADO")
                self.estado.set_machine_state(GlobalState.PREPARADO)
                # P-1 (tanda 6): tras cualquier fin, "NO ABRIR" y sin ciclo
                # nuevo hasta la cámara segura. Si al reconocer el COMPLETADO
                # la cámara no está segura, entra al mismo protocolo de estado
                # seguro que tras un fallo o una cancelación.
                if not self._camara_segura_tras_ciclo(datos_vigentes):
                    logger.warning("StateMachine: COMPLETADO reconocido con la cámara no segura "
                                   "→ protocolo de estado seguro")
                    # TMG-07 / SAF-04 de T2: con paro o sin datos vigentes, sin
                    # válvulas; el estado seguro las abre al volver los datos
                    abrir = (datos_vigentes is True
                             and not self.estado.get_flag("PARO_EMERGENCIA"))
                    self.ciclo._protocolo.ejecutar(abrir_valvulas=abrir)
                    self.estado_seguro.iniciar(self.ciclo._protocolo, origen="completado")

            elif resultado == "FALLO":
                logger.error("StateMachine: fallo en ciclo → FALLA")
                self.estado.set_machine_state(GlobalState.FALLA)
                self.estado_seguro.iniciar(self.ciclo._protocolo, origen="fallo")

            elif resultado == "CANCELADO":
                logger.warning("StateMachine: ciclo cancelado → PREPARADO")
                self.estado.set_machine_state(GlobalState.PREPARADO)
                self.estado_seguro.iniciar(self.ciclo._protocolo, origen="cancelado")

            # "EN_CURSO" o "ESPERANDO_CONFIRMACION" → no hacer nada, seguir en CICLO

        # ==============================================================
        # FALLA
        # ==============================================================
        elif current_state == GlobalState.FALLA:
            logger.debug("Estado actual: FALLA")
            # P-2 (tanda 6): con el Principal perdido, el reconocimiento lleva a
            # PREPARACION aunque el estado seguro siga venteando (sin técnico)
            puede_salir = (not self.estado_seguro.activo
                           or getattr(self.estado_seguro, "permite_salir_de_falla", False) is True)
            if self.falla.run(puede_salir=puede_salir):
                self.alarm_manager.resolver_todas_por_reinicio()
                self.estado.fase_ciclo = ""
                self.estado.set_machine_state(GlobalState.PREPARACION)


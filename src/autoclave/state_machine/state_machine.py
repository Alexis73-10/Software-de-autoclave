from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.state_machine.states.preparacion import preparacion_state
from autoclave.state_machine.states.preparado import preparado_state
from autoclave.state_machine.states.ciclo import CicloState
from autoclave.state_machine.states.falla import FallaState
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.core.runtime.sensores_ciclo import verificar_inicio
from autoclave.state_machine.estado_seguro import ConfirmacionParo
from autoclave.state_machine.states.vaciado_chaqueta import limpiar_en as limpiar_vaciado_chaqueta
from autoclave.state_machine.cycle_phases.valvula_reposo import cerrar_valvulas_descompresion
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
        # Hotfix ES: FALLA nivela la presión de cámara con el mismo lazo que
        # PREPARACION (venteo, en líquidos por la lenta; vacío: aire)
        self.falla.nivelar_presion_camara = self.preparacion.nivelar_presion_camara

        self.prev_state  = None

        # Hotfix ES (6-nov): sin protocolo automático de estado seguro; queda
        # la confirmación tras soltar un paro real fuera de CICLO. El
        # ControlLoop la conserva entre reconstrucciones (set_active_cycle).
        self.estado_seguro = estado_seguro if estado_seguro is not None else ConfirmacionParo(
            estado, al_evento=al_evento_seguridad)

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

    def confirmar_paro(self) -> bool:
        """Hotfix ES: "Confirmar" tras soltar un paro real. Sin protocolo: desde
        PREPARADO el equipo pasa a PREPARACION; PREPARACION sigue igual y FALLA
        sigue esperando su reconocimiento (que también confirma). Bajo el
        _sm_lock del ControlLoop."""
        if self.estado_seguro.confirmar() is not True:
            return False
        if self.estado.get_machine_state() == GlobalState.PREPARADO:
            self.estado.set_machine_state(GlobalState.PREPARACION)
        return True

    def _finalizar_protocolo_ciclo(self) -> None:
        """Hotfix ES: al salir de CICLO tras FALLO o CANCELADO se cierran las
        válvulas del protocolo de fallo del ciclo; el estado siguiente maneja
        la cámara. Un error no impide la transición."""
        try:
            self.ciclo._protocolo.finalizar()
        except Exception:
            logger.exception("StateMachine: no se pudo cerrar el protocolo de fallo del ciclo")

    def _cerrar_valvulas_reposo(self) -> None:
        """Hotfix ES (revisión, MEDIA): al pasar de COMPLETADO a PREPARADO se
        cierran las válvulas de descompresión que dejó abiertas la válvula de
        reposo del modo (en modo 4/5 sólido, descompresion_chaqueta con
        vapor_chaqueta encendida en PREPARADO); el lazo de PREPARADO retoma la
        presión de cámara. Un error no impide la transición."""
        try:
            cerrar_valvulas_descompresion(self.set_do)
        except Exception:
            logger.exception("StateMachine: no se pudieron cerrar las válvulas de descompresión")

    # ------------------------------------------------------------------
    # Tick principal
    # ------------------------------------------------------------------

    def update(self, datos_vigentes: bool = True):
        current_state = self.estado.get_machine_state()

        logger.debug(
            "Actualizando maquina de estados. Estado actual: %s",
            self.estado.estado_maquina.get("Estado")
        )

        # Hotfix ES: fuera de CICLO, seguimiento del paro real. Soltado y sin
        # confirmar, las salidas siguen en 0 y ningún estado avanza (§15.2);
        # con el paro activo cada estado manda su ALL_OFF y SIS-01.
        if current_state != GlobalState.CICLO:
            try:
                self.estado_seguro.update()
                esperando = self.estado_seguro.esperando_confirmacion() is True
            except Exception:
                logger.exception("StateMachine: error en la confirmación del paro")
                esperando = False
            if esperando:
                if current_state != self.prev_state:
                    self.on_state_entry(current_state)
                    self.prev_state = current_state
                self.estado.set_flag("LISTO_PARA_CICLO", False)
                self.set_do.apagar_por_paro()
                self.set_do.buzer_off()
                return

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

            # Hotfix ES (6-nov): ningún fin de ciclo inicia un protocolo de
            # estado seguro; PREPARADO/FALLA nivelan la cámara y "NO ABRIR" y
            # el bloqueo de inicio siguen mientras la cámara no sea segura.
            if resultado == "COMPLETADO":
                logger.info("StateMachine: ciclo completado → PREPARADO")
                self._cerrar_valvulas_reposo()
                self.estado.set_machine_state(GlobalState.PREPARADO)

            elif resultado == "FALLO":
                logger.error("StateMachine: fallo en ciclo → FALLA")
                self._finalizar_protocolo_ciclo()
                self.estado.set_machine_state(GlobalState.FALLA)

            elif resultado == "CANCELADO":
                logger.warning("StateMachine: ciclo cancelado → PREPARADO")
                self._finalizar_protocolo_ciclo()
                self.estado.set_machine_state(GlobalState.PREPARADO)

            # "EN_CURSO" o "ESPERANDO_CONFIRMACION" → no hacer nada, seguir en CICLO

        # ==============================================================
        # FALLA
        # ==============================================================
        elif current_state == GlobalState.FALLA:
            logger.debug("Estado actual: FALLA")
            if self.falla.run():
                self.alarm_manager.resolver_todas_por_reinicio()
                self.estado.fase_ciclo = ""
                self.estado.set_machine_state(GlobalState.PREPARACION)


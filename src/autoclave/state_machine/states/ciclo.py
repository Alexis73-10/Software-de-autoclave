# state_machine/states/ciclo.py
#
# ESTADO GLOBAL — CICLO
#
# Orquesta el pipeline de fases del ciclo de esterilización:
#
#   PRECALENTAMIENTO → PRE_VACIO → CALENTAMIENTO →
#   ESTERILIZACION → DESCOMPRESION → SECADO
#
# Retorna una de estas cadenas al StateMachine en cada tick:
#   "EN_CURSO"   — ciclo en ejecución, no hacer nada
#   "COMPLETADO" — todas las fases OK → volver a PREPARADO
#   "FALLO"      — fase falló o emergencia → ir a FALLA
#   "CANCELADO"  — usuario abortó → volver a PREPARADO

import logging
import time
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.alarms.catalogo import (
    CIC_01, CIC_02, CIC_03, CIC_04, CIC_05, CIC_06, CIC_07, CIC_08,
    COM_02, COM_03, PRE_06, PUE_02, PUE_03, SEN_02, SIS_01, SUM_01, SUM_06, nombre_legible,
)
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo
from autoclave.state_machine.cycle_phases.precalentamiento import PrecalentamientoFase
from autoclave.state_machine.cycle_phases.prevacio import PrevacioFase
from autoclave.state_machine.cycle_phases.calentamiento import CalentamientoFase
from autoclave.state_machine.cycle_phases.esterilizacion import EsterilizacionFase
from autoclave.state_machine.cycle_phases.descompresion import DescompresionFase
from autoclave.state_machine.cycle_phases.secado import SecadoFase
from autoclave.state_machine.cycle_phases.valvula_reposo import abrir_valvula_modo, cerrar_valvulas_descompresion
from autoclave.installation.profile import entrada_requerida, numero_puertas, revisa_empaque
from autoclave.core.runtime.lectura import lectura_valida

logger = logging.getLogger(__name__)

_SENSORES_TEMP_CRITICOS = ["temp_camara"]
_SENSORES_PRES_CRITICOS = ["pres_camara"]
_DEBOUNCE_LECTURAS_DRENAJE = 3
_INTERVALO_REINTENTO_APERTURA_SEG = 5.0
_TIMEOUT_APERTURA_DENEGADA_SEG = 60.0
_CIC_POR_FASE = {
    "PRECALENTAMIENTO": CIC_01, "PRE_VACIO": CIC_02, "CALENTAMIENTO": CIC_03,
    "ESTERILIZACION": CIC_04, "DESCOMPRESION": CIC_05, "SECADO": CIC_06,
}
_MOTIVO_NO_REGISTRADO = "La fase terminó en fallo; el motivo detallado aún no se registra."

# Sección del JSON del programa -> fase del pipeline que la usa (§5.8).
# `estabilizacion` va con CALENTAMIENTO (fusionadas). Las secciones que no están aquí (`globals`, `finalizacion` o
# cualquier otra) rigen todo el ciclo: se tratan como fase ya iniciada.
_SECCION_A_FASE = {
    "precalentamiento": "PRECALENTAMIENTO",
    "prevacio":         "PRE_VACIO",
    "calentamiento":    "CALENTAMIENTO",
    "estabilizacion":   "CALENTAMIENTO",
    "esterilizacion":   "ESTERILIZACION",
    "descompresion":    "DESCOMPRESION",
    "secado":           "SECADO",
}

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
        cycle         → Cycle  (programa almacenado; al entrar en CICLO las
                                fases trabajan con una copia profunda, T-17)
        config        → ConfigManager
        alarm_manager → AlarmManager
    """

    def __init__(self, estado, set_do, cycle, config, alarm_manager, cap=None, door_service=None,
                 profile=None):
        self.estado        = estado
        self.set_do        = set_do
        # Programa almacenado (el que edita PATCH /cycle/parameter). Mientras
        # corre un ciclo, self.cycle, las fases y el protocolo de fallo usan
        # su copia (programa_en_curso), tomada en reset().
        self._programa     = cycle
        self.cycle         = cycle
        self.programa_en_curso = None
        self.config        = config
        self.alarm_manager = alarm_manager
        self.cap           = cap
        self.door_service  = door_service
        # Perfil de instalación (E1): entradas de suministro y puertas.
        # None = comportamiento previo (todo requerido, 2 puertas con empaque).
        self.profile       = profile
        self._apertura_auto_t_inicio = None
        self._apertura_auto_alarmado = False
        self._apertura_auto_ultimo_intento = None
        self._apertura_auto_denegada_desde = None
        self._apertura_auto_alarmado_denegacion = False
        self._contador_drenaje_alta = 0
        self._contador_drenaje_baja = 0

        # Construir pipeline (los objetos se reusan; reset() los reinicia)
        _args = (estado, set_do, cycle, config, alarm_manager, cap)
        self._fases = [
            PrecalentamientoFase(*_args),
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
        Toma la copia profunda del programa (T-17) y reinicia todas las fases
        y el protocolo de fallo, que desde aquí leen la copia.
        """
        self.programa_en_curso = self._programa.copia()
        self.cycle = self.programa_en_curso
        self._protocolo.cycle = self.programa_en_curso
        for fase in self._fases:
            fase.cycle = self.programa_en_curso

        self._fase_idx            = 0
        self._resultado_pendiente = None
        self._contador_drenaje_alta = 0
        self._contador_drenaje_baja = 0
        self._apertura_auto_t_inicio = None
        self._apertura_auto_alarmado = False
        self._apertura_auto_ultimo_intento = None
        self._apertura_auto_denegada_desde = None
        self._apertura_auto_alarmado_denegacion = False
        self.estado.motivo_fallo  = ""
        self.estado.codigo_fallo  = ""
        self.estado.f0_acumulado  = 0.0
        self._protocolo.reset()

        for fase in self._fases:
            fase.reset()

        self.estado.fase_ciclo = self._fases[0].name
        logger.info(
            "CicloState: INICIANDO — %d fases | primera: %s",
            len(self._fases), self._fases[0].name
        )

    # ------------------------------------------------------------------
    # Cambios del ingeniero con el ciclo en curso (T-17, §5.8)
    # ------------------------------------------------------------------

    def aplicar_si_fase_pendiente(self, seccion: str, path: list[str], valor) -> bool:
        """Aplica a la copia del ciclo en curso un cambio ya guardado en el
        programa almacenado, solo si la fase de esa sección aún no ha
        iniciado. Devuelve True si aplicó al ciclo en curso; False si rige
        desde el siguiente (fase iniciada o terminada, sección global, ciclo
        ya terminado o sin copia). Llamar con _sm_lock tomado: así la fase no
        puede avanzar durante la decisión (si inicia en el mismo instante, el
        tick que la inicia ya corrió y cuenta como iniciada)."""
        if self.programa_en_curso is None or self._resultado_pendiente is not None:
            return False
        # un parámetro vinculado (p. ej. temperatura de calentamiento y de
        # esterilización) arrastra a su pareja: se aplica solo si todas las
        # fases afectadas están pendientes, para no dejarlas distintas
        nombres = [f.name for f in self._fases]
        for sec, _ in self.programa_en_curso.vinculados(seccion, path):
            fase = _SECCION_A_FASE.get(sec)
            if fase not in nombres or nombres.index(fase) <= self._fase_idx:
                return False
        try:
            self.programa_en_curso.set_param(seccion, path, valor)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("CicloState: el cambio %s/%s no se aplicó al ciclo en curso: %s",
                           seccion, ".".join(path), exc)
            return False
        logger.info("CicloState: cambio %s/%s aplicado al ciclo en curso (fase pendiente)",
                    seccion, ".".join(path))
        return True

    # ------------------------------------------------------------------
    # Supervisores continuos (llamados en cada tick activo)
    # ------------------------------------------------------------------

    def _fase_actual_legible(self) -> str:
        if self._fase_idx < len(self._fases):
            return nombre_legible(self._fases[self._fase_idx].name)
        return "fin de ciclo"

    def _registrar_fallo(self, codigo, origen=None, **valores):
        """Activa la alarma causante y deja motivo_fallo/codigo_fallo para
        CycleLogger y el ticket (spec §5.4).

        Nunca lanza (SAF-03): el registro de la alarma no puede impedir que
        el llamador ejecute el protocolo de fallo a continuación."""
        try:
            inst = self.alarm_manager.activar(codigo, origen, **valores)
            self.estado.motivo_fallo = f"{inst.codigo} · {inst.titulo}: {inst.descripcion}"
            self.estado.codigo_fallo = inst.codigo
        except Exception:
            logger.exception("CicloState: no se pudo registrar la alarma %s", codigo)
            try:
                self.estado.motivo_fallo = f"{codigo}: no se pudo registrar el detalle de la alarma."
                self.estado.codigo_fallo = codigo
            except Exception:
                logger.exception("CicloState: no se pudo dejar motivo_fallo de %s", codigo)

    def _registrar_fallo_de_fase(self, nombre_fase):
        """Registra el CIC-0x de la fase que devolvió FALLO. Nunca lanza: una
        fase fuera de _CIC_POR_FASE deja un motivo de respaldo legible y el
        llamador igual ejecuta el protocolo de fallo."""
        try:
            # La fase puede haber dejado ya un motivo específico (p.ej.
            # EsterilizacionFase._fallo() con la lectura exacta que falló);
            # sólo se usa el genérico si no dejó uno más preciso.
            motivo = self.estado.motivo_fallo or _MOTIVO_NO_REGISTRADO
            codigo = _CIC_POR_FASE.get(nombre_fase)
            if codigo is None:
                logger.error("CicloState: fase %s sin código CIC asociado", nombre_fase)
                self.estado.motivo_fallo = f"Fallo en la fase {nombre_legible(nombre_fase)}: {motivo}"
                self.estado.codigo_fallo = ""
                return
            self._registrar_fallo(codigo, origen=nombre_legible(nombre_fase), motivo=motivo)
        except Exception:
            logger.exception("CicloState: no se pudo registrar el fallo de la fase %s", nombre_fase)

    def _verificar_puertas(self) -> tuple[bool, str, str | None, dict]:
        """Retorna (ok, fase_ciclo, codigo_alarma, valores). fase_ciclo
        conserva el código histórico (FALLO_PUERTA_n_*) que usan CycleLogger
        y la UI."""
        min_empaque = (self.config.get("presion_empaque") or 300) * 0.6
        con_empaque = revisa_empaque(self.profile)

        for num in range(1, numero_puertas(self.profile) + 1):
            puerta = f"Puerta {num}"
            cerrada = bool(self.estado.sensores_di.get(f"puerta_{num}_cerrada", 0))
            if not cerrada:
                return False, f"FALLO_PUERTA_{num}_ABIERTA", PUE_02, {"puerta": puerta}

            if not con_empaque:
                continue
            emp = self.estado.sensores_pres.get(f"pres_empaque_{num}")
            # Sin lectura válida se omite, como antes con None (A-9)
            if lectura_valida(emp) and emp < min_empaque:
                return (False, f"FALLO_PUERTA_{num}_EMPAQUE", PUE_03,
                        {"puerta": puerta, "pres": emp, "minimo": min_empaque})

        return True, "", None, {}

    def _mantener_chaqueta(self):
        """Mantiene la presión de la chaqueta durante todas las fases del ciclo."""
        if self._fase_idx < len(self._fases) and isinstance(self._fases[self._fase_idx], SecadoFase):
            return
        pres = self.estado.sensores_pres.get("pres_chaqueta")
        # Sin dato: vapor OFF, no se deja la válvula como esté (A-5)
        if not lectura_valida(pres):
            self.set_do.vapor_chaqueta_off()
            return

        # Si no hay suministro de vapor, no intentar compensar. Sin presostato
        # declarado en el perfil (E1-1) se controla solo por presión.
        vigilar_vapor = entrada_requerida(self.profile, "vapor_suministro")
        if vigilar_vapor and not self.estado.sensores_di.get("vapor_suministro", 0):
            self.set_do.vapor_chaqueta_off()
            self.alarm_manager.activar(SUM_06, estado="Ciclo")
            return
        elif vigilar_vapor:
            self.alarm_manager.resolver(SUM_06)

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
        oscilaciones de temp_drenaje cerca del umbral. Sin lectura válida
        (o sin sonda) se enfría siempre y se reinicia el conteo de apagado
        (A-4, reemplaza el "solo salta el tick" anterior)."""
        temp = self.estado.sensores_temp.get("temp_drenaje")
        if not lectura_valida(temp):
            self.set_do.agua_intercambiador_on()
            self._contador_drenaje_baja = 0
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
            self.alarm_manager.activar(PRE_06, temp=temp, maximo=temp_segura)
        elif self._contador_drenaje_baja >= _DEBOUNCE_LECTURAS_DRENAJE:
            self.set_do.agua_intercambiador_off()
            self.alarm_manager.resolver(PRE_06)

    def _mantener_valvula_reposo(self):
        """Mientras se espera confirmación tras un COMPLETADO limpio (sin
        ProtocoloFallo, que ya hace su propia gestión continua): si la
        cámara cae en vacío por enfriamiento, abre aire atmosférico; si no,
        mantiene la válvula de descompresión del modo configurado."""
        pres = self.estado.sensores_pres.get("pres_camara")
        if not lectura_valida(pres):
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
        (tiempo_espera_apertura) → espera a que temp_camara Y pres_camara
        estén en condición segura (mismo criterio fail-closed que el botón
        CONFIRMAR manual: sensor ausente no habilita nada; temp_max_apertura
        nunca por encima del tope global) → confirma solo cuando el estado
        observado de la puerta (no la sola respuesta de request_open)
        muestra que empezó a moverse. Mientras la puerta no responda
        (bloqueo mecánico, interlock, tipo de puerta sin actuador), reintenta
        cada _INTERVALO_REINTENTO_APERTURA_SEG segundos y avisa una sola vez
        por alarma no bloqueante si la denegación se sostiene más de
        _TIMEOUT_APERTURA_DENEGADA_SEG segundos — sin dejar de esperar."""
        if self.door_service is None:
            return
        if not self.cycle.get_param("finalizacion", "apertura_automatica", default=False):
            return

        # Puerta sin actuador (manual): no hay nada que abrir. Se ignora el
        # parámetro en silencio, sin reintentos ni APERTURA_AUTOMATICA_DENEGADA (E1-4).
        puerta = "Puerta 2" if "Puerta 2" in self.door_service.doors else "Puerta 1"
        if not self.door_service.tiene_actuador(puerta):
            return

        if self._apertura_auto_t_inicio is None:
            self._apertura_auto_t_inicio = time.monotonic()

        tiempo_espera = self.cycle.get_param("finalizacion", "tiempo_espera_apertura", default=60)
        if tiempo_espera is None:
            tiempo_espera = 60
        elapsed = time.monotonic() - self._apertura_auto_t_inicio
        if elapsed < tiempo_espera:
            return

        temp = self.estado.sensores_temp.get("temp_camara")
        if not lectura_valida(temp):
            return

        temp_max_ciclo  = self.cycle.get_param("finalizacion", "temp_max_apertura", default=80.0)
        if temp_max_ciclo is None:
            temp_max_ciclo = 80.0
        temp_max_global = self.config.get("temp_max_apertura")
        temp_max = min(temp_max_ciclo, temp_max_global) if temp_max_global is not None else temp_max_ciclo

        if temp > temp_max:
            timeout_min = self.cycle.get_param("finalizacion", "timeout_temperatura", default=30)
            if timeout_min is None:
                timeout_min = 30
            timeout_seg = timeout_min * 60
            if not self._apertura_auto_alarmado and (elapsed - tiempo_espera) > timeout_seg:
                self._apertura_auto_alarmado = True
                self.alarm_manager.activar(
                    CIC_07, temp=temp, maximo=temp_max,
                    minutos=(elapsed - tiempo_espera) / 60)
            return

        pres = self.estado.sensores_pres.get("pres_camara")
        if not lectura_valida(pres):
            return
        presion_atm = self.config.get("presion_admosferica") or 101.3
        rango_atm   = self.config.get("rango_presion_atm")   or 20.0
        if abs(pres - presion_atm) > rango_atm:
            return

        estado_puerta = self.door_service.get_status(puerta)
        if estado_puerta in ("ABRIENDO", "ABIERTO"):
            if self._apertura_auto_alarmado:
                self.alarm_manager.resolver(CIC_07)
            if self._apertura_auto_alarmado_denegacion:
                self.alarm_manager.resolver(CIC_08)
            self.estado.set_flag("CICLO_CONFIRMADO", True)
            return

        ahora = time.monotonic()
        if (self._apertura_auto_ultimo_intento is not None
                and (ahora - self._apertura_auto_ultimo_intento) < _INTERVALO_REINTENTO_APERTURA_SEG):
            return
        self._apertura_auto_ultimo_intento = ahora

        if self._apertura_auto_denegada_desde is None:
            self._apertura_auto_denegada_desde = ahora

        _ok, motivo = self.door_service.request_open(puerta)

        if (not self._apertura_auto_alarmado_denegacion
                and (ahora - self._apertura_auto_denegada_desde) > _TIMEOUT_APERTURA_DENEGADA_SEG):
            self._apertura_auto_alarmado_denegacion = True
            self.alarm_manager.activar(
                CIC_08, puerta=puerta, motivo=motivo or "sin motivo reportado")

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
                self._mantener_apertura_automatica()
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
            self._registrar_fallo(SIS_01, estado="Ciclo")
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 2b. ¿Fallo de suministro eléctrico? ──────────────────────
        if self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO"):
            logger.error("CicloState: ABORTADO por fallo de suministro eléctrico")
            self.estado.fase_ciclo = "FALLO_SUMINISTRO"
            fase = self._fase_actual_legible()
            self._registrar_fallo(SUM_01, origen=fase, fase=fase)
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 3. Verificar puertas y empaque ────────────────────────────
        puertas_ok, fase_fallo, codigo, valores = self._verificar_puertas()
        if not puertas_ok:
            logger.error("CicloState: FALLO de seguridad — %s", fase_fallo)
            self.estado.fase_ciclo = fase_fallo
            self._registrar_fallo(codigo, origen=valores["puerta"],
                                  fase=self._fase_actual_legible(), **valores)
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 4. Verificar sensores críticos ────────────────────────────
        ausentes = [
            s for s in _SENSORES_TEMP_CRITICOS
            if not lectura_valida(self.estado.sensores_temp.get(s))
        ] + [
            s for s in _SENSORES_PRES_CRITICOS
            if not lectura_valida(self.estado.sensores_pres.get(s))
        ]
        if ausentes:
            logger.error("CicloState: SENSOR_AUSENTE — %s", ausentes)
            self.estado.fase_ciclo = "SENSOR_AUSENTE"
            fase = self._fase_actual_legible()
            legibles = [nombre_legible(s) for s in ausentes]
            self._registrar_fallo(SEN_02, origen=fase,
                                  sensores=", ".join(legibles), fase=fase)
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
            self._registrar_fallo_de_fase(fase.name)
            self._protocolo.ejecutar()
            self._resultado_pendiente = CicloResultado.FALLO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # Fallback (no debería ocurrir)
        return CicloResultado.EN_CURSO

    # ------------------------------------------------------------------
    # Aborto forzado por el ControlLoop (fuera del tick normal de run())
    # ------------------------------------------------------------------

    def abortar_por_desconexion(self, segundos: float = 5.0):
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
        fase = self._fase_actual_legible()
        self._registrar_fallo(COM_02, origen=fase, segundos=segundos, fase=fase)
        self._protocolo.ejecutar()
        self._resultado_pendiente = CicloResultado.FALLO

    def abortar_por_falla_io(self, alarm_id: str, motivo: str):
        """Llamado por ControlLoop cuando la tarjeta de E/S informa una falla
        durante un ciclo en curso: watchdog disparado, reinicio, expansor
        fuera de línea o salidas que no siguen lo comandado (plan de
        protocolo serial §7 y §11.5). Análogo a abortar_por_desconexion(): el
        enlace puede quedar sin handshake (WD/BOOT) y entonces run() no corre,
        así que el aborto y el protocolo de fallo se disparan desde aquí.

        Devuelve True si abortó; False si el ciclo ya se estaba terminando
        por otra causa (el ControlLoop entonces la reporta como fuera de
        ciclo, TMG-07)."""
        if self._resultado_pendiente is not None:
            return False  # ya se estaba abortando/terminando por otra causa

        logger.error("CicloState: ABORTADO por falla de la tarjeta de E/S (%s): %s",
                     alarm_id, motivo)
        self.estado.fase_ciclo = "FALLO_IO"
        # P5: resultado FALLO_IO con el id de la tarjeta como causa (origen
        # de COM-03, que es FALLO_CRITICO y no se despeja sola).
        self._registrar_fallo(COM_03, origen=alarm_id, causa=alarm_id, motivo=motivo,
                              fase=self._fase_actual_legible())
        self._protocolo.ejecutar()
        self._resultado_pendiente = CicloResultado.FALLO
        return True

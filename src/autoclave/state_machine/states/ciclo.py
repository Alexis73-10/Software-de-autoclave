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
import math
import time
from autoclave.state_machine.cycle_phases.base_fase import FaseResult
from autoclave.state_machine.alarms.catalogo import (
    CIC_01, CIC_02, CIC_03, CIC_04, CIC_05, CIC_06, CIC_07, CIC_08, CIC_11,
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
from autoclave.core.runtime.lectura import carga_enfriada, lectura_valida
from autoclave.core.runtime.sensores_ciclo import sensor_principal, sensores_en_uso
from autoclave.core.runtime import alarmas_i18n

logger = logging.getLogger(__name__)

# Temperatura: los sensores EN USO del programa (Principal + Referencias),
# tanda §1.1; un sensor no_en_uso no se vigila (se retira la vigilancia fija
# de temp_camara, antiguo S-8).
_SENSORES_PRES_CRITICOS = ["pres_camara"]
_DEBOUNCE_LECTURAS_DRENAJE = 3
# Lecturas seguidas del Principal bajo temperatura_enfriamiento (SAF-01 de T11)
_DEBOUNCE_ENFRIADA = 3
_INTERVALO_REINTENTO_APERTURA_SEG = 5.0
# P-3 (tanda 6): tolerancia a una trama DI vencida con el enlace activo
# (PARO_EMERGENCIA sin PARO_REAL) antes de abortar el ciclo. Nunca mayor que
# el watchdog del firmware (WD_TIMEOUT_MS = 5000 en
# Hardware/Comunicacion_esclava_ESP32_V3) menos 1 s de margen: 4 s
# (DECISIÓN SIN CONFIRMAR: la instrucción permite hasta 5 s). Ojo (TMG-01 de
# T2): ese watchdog mide líneas del PC a la tarjeta; con la DI vencida el PC
# sigue enviando y el watchdog no actúa. Por eso, durante la tolerancia se
# cortan el vapor de cámara y de chaqueta (TMG-02 / SAF-01 de T2).
_TOLERANCIA_DI_VENCIDA_SEG = 4.0
# Tramas DI vigentes, distintas y nuevas, seguidas para reiniciar la
# tolerancia (TMG-03 de T2: una trama intermitente no puede renovarla
# indefinidamente; D8-2.9 / TMG-04: tramas, no ticks)
_TICKS_DI_VIGENTE_REINICIO = 3
# TMG-01 (revisión S2a): el tramo sin datos empieza en la última DI válida
# (la publica ControlLoop en estado.ultima_di_valida_mono), no al detectarlo;
# como mucho este retroceso (vigencia de la DI, 1,5 s, más un tick de 0,5 s)
_RETROCESO_MAX_TRAMO_SEG = 2.0
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
        # Paro durante el ciclo o con el resultado pendiente: no se mueve nada
        # hasta la confirmación (fin de ciclo §15.1-2, TMG-04)
        self._paro_en_espera = False
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
        self._di_vencida_desde = None
        self._ticks_di_vigente = 0
        # T2-a (tanda 7): inicio (monotonic) del tramo en curso en que la fase
        # no corre por la tolerancia de DI vencida; None fuera de él
        self._pausa_sin_datos_desde = None
        # D8-2.7 (tanda 8): el tramo en curso empezó por la desconexión total de
        # la tarjeta (el ControlLoop no corre run()), no por la DI vencida
        self._pausa_por_desconexion = False

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
        self._lecturas_enfriada_reposo = 0
        self._apertura_auto_t_inicio = None
        self._apertura_auto_alarmado = False
        self._apertura_auto_ultimo_intento = None
        self._apertura_auto_denegada_desde = None
        self._apertura_auto_alarmado_denegacion = False
        self.estado.motivo_fallo  = ""
        self.estado.codigo_fallo  = ""
        self.estado.valores_fallo = {}
        self.estado.f0_acumulado  = 0.0
        self.estado.avisos_ciclo  = []
        self.estado.sin_datos_tarjeta_s = 0.0
        self._paro_en_espera = False
        self._di_vencida_desde = None
        self._ticks_di_vigente = 0
        self._pausa_sin_datos_desde = None
        self._pausa_por_desconexion = False
        self._protocolo.reset()

        for fase in self._fases:
            fase.reset()

        self.estado.fase_ciclo = self._fases[0].name
        logger.info(
            "CicloState: INICIANDO — %d fases | primera: %s",
            len(self._fases), self._fases[0].name
        )

    @property
    def tolerancia_di_activa(self) -> bool:
        """R1-P5 (tanda 7): la fase está detenida por la tolerancia de DI
        vencida (sin resultado todavía). /cycle/abort acepta entonces la
        cancelación: la marca se procesa al volver los datos (paso 1 de run)
        o, si la tolerancia vence, el ciclo termina en FALLO_CONEXION y P-7
        la limpia. Leer bajo _sm_lock (guard_estado del backend).

        D8-2.7: el tramo de una desconexión total (marcar_sin_datos_tarjeta)
        no cuenta como tolerancia de DI: R1-P5 no cambia aquí."""
        return (self._resultado_pendiente is None and self._pausa_sin_datos_desde is not None
                and not self._pausa_por_desconexion)

    @property
    def exposicion_en_pausa(self) -> bool:
        """D8-2.7 (tanda 8): hay un tramo sin datos válidos de la tarjeta en
        curso (desconexión total, ventana tras reconectar o tolerancia de DI
        vencida). Esos segundos no cuentan como exposición ni acumulan F0."""
        return self._resultado_pendiente is None and self._pausa_sin_datos_desde is not None

    def marcar_sin_datos_tarjeta(self) -> None:
        """D8-2.7 (tanda 8, decisión de Cristian; SAF-02 / TMG-02 de la
        revisión Q1): el ControlLoop llama aquí en cada tick de CICLO en que no
        corre la máquina de estados por falta de datos (enlace caído antes de
        COM-02, o recién reconectado sin la primera DI). Abre el tramo sin datos
        si no hay uno abierto; lo cierra el primer run() con datos
        (_cerrar_pausa_sin_datos), así que la desconexión, la ventana tras
        reconectar y una tolerancia de DI que siga a continuación son un solo
        tramo. Con el resultado pendiente no hay exposición que pausar."""
        if self._resultado_pendiente is not None:
            return
        # TMG-02 (revisión S2a): las tramas DI contadas antes de la caída no
        # se suman a las de después (3 tramas nuevas SEGUIDAS, D8-2.9)
        self._ticks_di_vigente = 0
        if self._pausa_sin_datos_desde is not None:
            self._revisar_tope_pausa_abierta()
            return
        self._pausa_sin_datos_desde = self._inicio_tramo_sin_datos(time.monotonic())
        self._pausa_por_desconexion = True
        logger.warning("CicloState: sin datos de la tarjeta (desconexión); la fase %s queda "
                       "en pausa", self._fase_actual_legible())

    @property
    def pausa_sin_datos_desde(self):
        """Instante (monotonic) en que empezó el tramo sin datos en curso, o
        None. Lo usa ControlLoop para descontar el F0 acreditado desde ahí
        (TMG-01 de la revisión S2a)."""
        if self._resultado_pendiente is not None:
            return None
        return self._pausa_sin_datos_desde

    def _inicio_tramo_sin_datos(self, ahora: float) -> float:
        """TMG-01 (revisión S2a): el tramo sin datos empieza en la última DI
        válida (estado.ultima_di_valida_mono), con un retroceso máximo de
        _RETROCESO_MAX_TRAMO_SEG; sin ese dato, en `ahora`."""
        ultima = getattr(self.estado, "ultima_di_valida_mono", None)
        if (isinstance(ultima, bool) or not isinstance(ultima, (int, float))
                or not math.isfinite(ultima) or ultima > ahora):
            return ahora
        return max(ultima, ahora - _RETROCESO_MAX_TRAMO_SEG)

    def _revisar_tope_pausa_abierta(self) -> None:
        """SAF-05 (revisión S2a): un enlace que va y viene (menos de 5 s caído,
        menos de la vigencia de la primera DI conectado) nunca llega a COM-02
        y run() no corre: el tramo sin datos queda abierto. En ESTERILIZACION,
        si lo acumulado más el tramo abierto supera pausa_max_esterilizacion_s,
        el ciclo falla con CIC-11 aquí mismo (D8-2.8), sin esperar a run()."""
        if not (0 <= self._fase_idx < len(self._fases)):
            return
        fase = self._fases[self._fase_idx]
        # TMG-12 (re-revisión S2a): sin exposición iniciada no hay pausa que topar
        if getattr(fase, "_timer_fin", None) is None:
            return
        tope = getattr(fase, "_pausa_max_s", None)
        total = getattr(fase, "pausa_total_s", None)
        if (not callable(tope) or isinstance(total, bool)
                or not isinstance(total, (int, float))):
            return
        abierto = max(0.0, time.monotonic() - self._pausa_sin_datos_desde)
        try:
            maximo = float(tope())
        except Exception:
            return
        if total + abierto <= maximo:
            return
        self._cerrar_pausa_sin_datos()          # suma el tramo a la fase y al ticket
        total = getattr(fase, "pausa_total_s", total + abierto)
        logger.error("CicloState: ABORTADO — %.0f s de pausa sin datos en %s (máximo %.0f s)",
                     total, fase.name, maximo)
        self.estado.fase_ciclo = f"FALLO_{fase.name}"
        self._registrar_fallo(CIC_11, origen=nombre_legible(fase.name),
                              segundos=total, maximo=maximo)
        # TMG-12: el resultado antes del protocolo (si este lanza, no se
        # repite el aborto en el tick siguiente)
        self._resultado_pendiente = CicloResultado.FALLO
        self._ejecutar_protocolo_respetando_paro()

    @property
    def ack_confirma_estado_seguro(self) -> bool:
        """P-6 (tanda 6): el reconocimiento del resultado también confirma el
        estado seguro (§15.2): hubo un paro con el ciclo terminando y ya se
        soltó. La UI muestra entonces el texto de §15.2 antes de confirmar."""
        return (self._resultado_pendiente is not None and self._paro_en_espera
                and not self.estado.get_flag("PARO_EMERGENCIA"))

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

    def _fase_en_enfriamiento_con_contrapresion(self) -> bool:
        """D8-2.10: la fase actual es DESCOMPRESION enfriando con
        contrapresión (modos 4/5)."""
        if not (0 <= self._fase_idx < len(self._fases)):
            return False
        fase = self._fases[self._fase_idx]
        try:
            return getattr(fase, "en_enfriamiento_con_contrapresion", False) is True
        except Exception:
            return False

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
            # I4 (tanda 6): los parámetros por separado, para presentar el
            # motivo en cualquier idioma y unidad (planeacion_i18n.md §3.10).
            # Antes que el código (revisión I4, TMG-01): quien lea el código
            # ya encuentra sus parámetros.
            try:
                self.estado.valores_fallo = alarmas_i18n.valores_json(valores)
            except Exception:
                self.estado.valores_fallo = {}
            self.estado.motivo_fallo = f"{inst.codigo} · {inst.titulo}: {inst.descripcion}"
            self.estado.codigo_fallo = inst.codigo
        except Exception:
            logger.exception("CicloState: no se pudo registrar la alarma %s", codigo)
            try:
                self.estado.motivo_fallo = f"{codigo}: no se pudo registrar el detalle de la alarma."
                self.estado.codigo_fallo = codigo
                self.estado.valores_fallo = {}
            except Exception:
                logger.exception("CicloState: no se pudo dejar motivo_fallo de %s", codigo)

    def _registrar_fallo_de_fase(self, nombre_fase, fase=None):
        """Registra el CIC-0x de la fase que devolvió FALLO. Nunca lanza: una
        fase fuera de _CIC_POR_FASE deja un motivo de respaldo legible y el
        llamador igual ejecuta el protocolo de fallo.

        D8-2.8 (tanda 8): si la fase dejó `alarma_fallo` (código propio y sus
        valores, hoy solo CIC-11 de ESTERILIZACION), se registra esa."""
        try:
            propia = getattr(fase, "alarma_fallo", None)
            if (isinstance(propia, tuple) and len(propia) == 2
                    and propia[0] in (CIC_11,) and isinstance(propia[1], dict)):
                self._registrar_fallo(propia[0], origen=nombre_legible(nombre_fase), **propia[1])
                return
            # La fase puede haber dejado ya un motivo específico (p.ej.
            # EsterilizacionFase._fallo() con la lectura exacta que falló);
            # sólo se usa el genérico si no dejó uno más preciso.
            motivo = self.estado.motivo_fallo or _MOTIVO_NO_REGISTRADO
            codigo = _CIC_POR_FASE.get(nombre_fase)
            if codigo is None:
                logger.error("CicloState: fase %s sin código CIC asociado", nombre_fase)
                self.estado.motivo_fallo = f"Fallo en la fase {nombre_legible(nombre_fase)}: {motivo}"
                self.estado.codigo_fallo = ""
                self.estado.valores_fallo = {}
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
        # TMG-01 de T11: en el enfriamiento de los modos 4/5 la chaqueta se
        # ventea y se enfría con agua; reponer su vapor lo anularía
        fase = self._fases[self._fase_idx] if self._fase_idx < len(self._fases) else None
        if getattr(fase, "chaqueta_en_enfriamiento", False) is True:
            self.set_do.vapor_chaqueta_off()
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

    def _ejecutar_protocolo_respetando_paro(self) -> None:
        """Abortos forzados por el ControlLoop: con el paro activo, ALL_OFF sin
        válvulas y confirmación posterior (SAF-05 de T5, §15.1)."""
        if self.estado.get_flag("PARO_EMERGENCIA"):
            self._protocolo.ejecutar(abrir_valvulas=False)
            self._paro_en_espera = True
        else:
            self._protocolo.ejecutar()

    def _cerrar_pausa_sin_datos(self) -> None:
        """T2-a (tanda 7, decisión 1.3 de Cristian): termina el tramo en que la
        fase no corrió por la tolerancia de DI vencida (volvieron los datos o
        el ciclo terminó). Los segundos se suman a estado.sin_datos_tarjeta_s
        (pie del ticket) y la fase en curso los descuenta de su exposición si
        sabe hacerlo (ESTERILIZACION: pausar_exposicion)."""
        desde = self._pausa_sin_datos_desde
        if desde is None:
            return
        self._pausa_sin_datos_desde = None
        self._pausa_por_desconexion = False
        segundos = max(0.0, time.monotonic() - desde)
        previo = getattr(self.estado, "sin_datos_tarjeta_s", 0.0)
        if isinstance(previo, bool) or not isinstance(previo, (int, float)):
            previo = 0.0
        self.estado.sin_datos_tarjeta_s = previo + segundos
        logger.warning("CicloState: %.1f s sin datos de la tarjeta (fase %s)",
                       segundos, self._fase_actual_legible())
        if self._fase_idx < len(self._fases):
            pausar = getattr(self._fases[self._fase_idx], "pausar_exposicion", None)
            if callable(pausar):
                try:
                    pausar(segundos)
                except Exception:
                    logger.exception("CicloState: no se pudo pausar la exposición")
            # D8-2.12 (tanda 8): también las ventanas de estabilidad de la
            # fase (los timeouts siguen corriendo)
            ventanas = getattr(self._fases[self._fase_idx], "pausar_ventanas_estabilidad", None)
            if callable(ventanas):
                try:
                    ventanas(segundos)
                except Exception:
                    logger.exception("CicloState: no se pudieron pausar las ventanas de estabilidad")

    def _principal_enfriada(self, modo) -> bool:
        """Principal en o por debajo de temperatura_enfriamiento del modo
        (líquidos, tanda §1.2). Sin lectura: no enfriada (falla cerrada)."""
        modo_key = f"modo_{2 if not modo else modo}"
        t_enfr = self.cycle.get_param("descompresion", modo_key, "temperatura_enfriamiento",
                                      default=80.0)
        temp = self.estado.sensores_temp.get(sensor_principal(self.cycle))
        # SAF-01 de T11: sin lectura o con 0 no está enfriada, y hacen falta
        # 3 lecturas seguidas (un valor espurio no habilita la rápida)
        if carga_enfriada(temp, t_enfr):
            self._lecturas_enfriada_reposo = getattr(self, "_lecturas_enfriada_reposo", 0) + 1
        else:
            self._lecturas_enfriada_reposo = 0
        return self._lecturas_enfriada_reposo >= _DEBOUNCE_ENFRIADA

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
            liquido = self.cycle.get_param("globals", "tipo_carga", default="solido") == "liquido"
            abrir_valvula_modo(self.set_do, modo, liquido=liquido,
                               enfriada=self._principal_enfriada(modo))

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

        # Principal del programa del ciclo (tanda §1.1); sin lectura = no seguro
        temp = self.estado.sensores_temp.get(sensor_principal(self.cycle))
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
            # P-7 (tanda 6): una cancelación que no llegó a procesarse (el
            # ciclo terminó por otra causa) no queda puesta
            if self.estado.get_flag("CICLO_CANCELADO"):
                self.estado.set_flag("CICLO_CANCELADO", False)
            # TMG-04 (E3): el paro se evalúa también con el resultado pendiente.
            # Paro activo = ALL_OFF continuo; al liberarlo, salidas en 0 y sin
            # avance automático hasta la confirmación (fin de ciclo §15.1-2).
            if self.estado.get_flag("PARO_EMERGENCIA"):
                if not self._paro_en_espera:
                    logger.error("CicloState: paro de emergencia con el resultado pendiente")
                self._paro_en_espera = True
                # una confirmación que entró durante el paro no vale (TMG-06 de T5)
                for bandera in ("CICLO_CONFIRMADO", "RESET_FALLA"):
                    if self.estado.get_flag(bandera):
                        self.estado.set_flag(bandera, False)
                self.set_do.apagar_por_paro()
                return CicloResultado.ESPERANDO_CONFIRMACION
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
            if self._paro_en_espera:
                # Paro liberado sin confirmar: nada se mueve (§15.2)
                return CicloResultado.ESPERANDO_CONFIRMACION
            if self._resultado_pendiente == CicloResultado.COMPLETADO:
                self._mantener_valvula_reposo()
                self._mantener_apertura_automatica()
            else:
                self._protocolo.update()
            self._mantener_drenaje()
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 0b. T2-a: volvieron los datos tras la tolerancia por DI vencida
        if not self.estado.get_flag("PARO_EMERGENCIA"):
            self._cerrar_pausa_sin_datos()

        # ── 1. ¿El usuario canceló? (el paro domina: SAF-05 de T5) ─────
        if self.estado.get_flag("CICLO_CANCELADO") and not self.estado.get_flag("PARO_EMERGENCIA"):
            logger.warning("CicloState: CANCELADO por operador")
            self.estado.fase_ciclo = "CANCELADO"
            self._protocolo.ejecutar()
            self.estado.set_flag("CICLO_CANCELADO", False)
            self._resultado_pendiente = CicloResultado.CANCELADO
            return CicloResultado.ESPERANDO_CONFIRMACION

        # ── 2. ¿Paro de emergencia? ───────────────────────────────────
        if not self.estado.get_flag("PARO_EMERGENCIA"):
            # D8-2.9 (tanda 8, TMG-04): solo suma una trama DI DISTINTA y
            # nueva (la publica ControlLoop en estado.trama_di_nueva); varios
            # ticks que leen la misma trama cuentan una vez. Sin esa
            # información (None, o un estado que no la publica) se cuenta cada
            # tick, como antes de D8-2.9.
            nueva = getattr(self.estado, "trama_di_nueva", None)
            if self._di_vencida_desde is not None and nueva is not False:
                self._ticks_di_vigente += 1
                if self._ticks_di_vigente >= _TICKS_DI_VIGENTE_REINICIO:
                    self._di_vencida_desde = None
                    self._ticks_di_vigente = 0
        else:
            self._ticks_di_vigente = 0
            paro_real = bool(self.estado.get_flag("PARO_REAL"))
            if not paro_real:
                # P-3: trama DI vencida con el enlace hecho. Dentro de la
                # tolerancia no se aborta ni se mueve nada (como una caída
                # breve del enlace): la fase no corre con entradas viejas.
                ahora = time.monotonic()
                if self._di_vencida_desde is None:
                    # TMG-01 (revisión S2a): la tolerancia también cuenta
                    # desde la última DI válida
                    self._di_vencida_desde = self._inicio_tramo_sin_datos(ahora)
                    logger.warning("CicloState: trama DI vencida; tolerancia de %.0f s",
                                   _TOLERANCIA_DI_VENCIDA_SEG)
                if ahora - self._di_vencida_desde < _TOLERANCIA_DI_VENCIDA_SEG:
                    # T2-a: la fase no corre; su exposición queda en pausa
                    if self._pausa_sin_datos_desde is None:
                        self._pausa_sin_datos_desde = self._inicio_tramo_sin_datos(ahora)
                    # D8-2.7: si venía de una desconexión, el mismo tramo
                    # sigue ahora como tolerancia de DI
                    self._pausa_por_desconexion = False
                    # sin aporte de energía mientras no hay datos de entradas
                    self.set_do.vapor_camara_off()
                    self.set_do.vapor_chaqueta_off()
                    return CicloResultado.EN_CURSO
            self._cerrar_pausa_sin_datos()      # T2-a: el tramo sin datos va al ticket
            if paro_real:
                logger.error("CicloState: ABORTADO por paro de emergencia")
                self.estado.fase_ciclo = "EMERGENCIA"
                self._registrar_fallo(SIS_01, estado="Ciclo")
            else:
                # U4 / P-3: con el enlace hecho pero la trama DI vencida no se
                # sabe si hay paro; el protocolo es el mismo (sin válvulas y con
                # confirmación), pero la causa es la comunicación, no SIS-01
                logger.error("CicloState: ABORTADO por trama DI vencida (fallo de comunicación)")
                self.estado.fase_ciclo = "FALLO_CONEXION"
                self._registrar_fallo(COM_03, origen="TARJETA_SIN_TRAMA_VALIDA",
                                      causa="TARJETA_SIN_TRAMA_VALIDA",
                                      motivo="Sin datos vigentes de las entradas de la tarjeta.",
                                      fase=self._fase_actual_legible())
            # §15.1: con el paro activo, ALL_OFF y ninguna válvula
            self._protocolo.ejecutar(abrir_valvulas=False)
            self._paro_en_espera = True
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
        # DECISIÓN SIN CONFIRMAR (tanda §1.1): una Referencia caída también
        # dispara SENSOR_AUSENTE → FALLO, igual que el Principal.
        # SEN-01 de T2: un 0 del sensor de temperatura es "sin señal" (mismo
        # criterio que estado_sensor y temp_seguridad)
        ausentes = [
            s for s in sensores_en_uso(self.cycle)
            if not lectura_valida(self.estado.sensores_temp.get(s))
            or self.estado.sensores_temp.get(s) == 0
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
            # P-2 (tanda 6): con el Principal perdido NO se sigue con la
            # Referencia: el ciclo falla y se ventea solo por la lenta.
            if sensor_principal(self.cycle) in ausentes:
                if self._fase_en_enfriamiento_con_contrapresion():
                    # D8-2.10: líquidos en modos 4/5 quedan sellados (lo
                    # decide el protocolo según el tipo de carga)
                    self._protocolo.ejecutar(solo_lenta=True,
                                             en_enfriamiento_contrapresion=True)
                else:
                    self._protocolo.ejecutar(solo_lenta=True)
            else:
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
            self._registrar_fallo_de_fase(fase.name, fase)
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

        self._cerrar_pausa_sin_datos()          # T2-a
        logger.error("CicloState: ABORTADO por pérdida de comunicación serial")
        self.estado.fase_ciclo = "FALLO_CONEXION"
        fase = self._fase_actual_legible()
        self._registrar_fallo(COM_02, origen=fase, segundos=segundos, fase=fase)
        self._ejecutar_protocolo_respetando_paro()
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

        self._cerrar_pausa_sin_datos()          # T2-a
        logger.error("CicloState: ABORTADO por falla de la tarjeta de E/S (%s): %s",
                     alarm_id, motivo)
        self.estado.fase_ciclo = "FALLO_IO"
        # P5: resultado FALLO_IO con el id de la tarjeta como causa (origen
        # de COM-03, que es FALLO_CRITICO y no se despeja sola).
        self._registrar_fallo(COM_03, origen=alarm_id, causa=alarm_id, motivo=motivo,
                              fase=self._fase_actual_legible())
        self._ejecutar_protocolo_respetando_paro()
        self._resultado_pendiente = CicloResultado.FALLO
        return True

# src/autoclave/devices/io/set_io.py
from autoclave.devices.pump.pump import VacuumPump
from autoclave.installation.profile import salidas_vapor_permitidas
from autoclave.core.runtime.asignacion_io import canal_do
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.state_machine.machine.enum_global import GlobalState
import autoclave.devices.buzer.buzer as buzer
import logging
import time

logger = logging.getLogger(__name__)

# Con el paro activo, ALL_OFF a lo sumo una vez por este intervalo, salvo que
# el último DO reportado tenga una salida encendida (adenda E0/E1, A-7).
_INTERVALO_ALL_OFF_PARO_SEG = 1.0
# Salidas que no cuentan como "encendidas" para repetir el ALL_OFF del paro:
# el buzzer suena a propósito durante el paro.
_SALIDAS_IGNORADAS_PARO = frozenset({"buzer_alarma"})
# D9-9 (revisión B9, SAF-03): en CICLO, el paro sin datos bloquea encendidos
# mientras la máquina siga pidiendo apagar_por_paro (cada tick, ~0,5 s).
_VIGENCIA_PEDIDO_PARO_SEG = 3.0
# Salidas de fuente de vapor (su canal físico sale de la asignación de E/S).
_SALIDAS_VAPOR = ("vapor_generador", "vapor_caldera")
# Canales que el apagado individual (sin ACK del ALL_OFF) apaga siempre,
# además de los de la asignación vigente. Tanda 19 (MOD-05): todos, DO 1-32
# (antes 1-24): el buzzer pasó a DO 25 y los dos enlaces tienen 32 salidas.
_CANALES_APAGADO_BASE = range(1, 33)
# AJ-02 (ajustes 28-oct): agua_intercambiador tiene dos dueños (el vacío de la
# cámara y el control de drenaje). Cada uno fija su propia petición y la
# salida es el OR de las dos, con una sola orden al canal: mientras alguna
# pida ON, el canal no recibe OFF (antes el drenaje frío la apagaba y la fase
# de vacío la volvía a encender en cada tick de 0,5 s).
_AGUA_INTERCAMBIADOR = "agua_intercambiador"


class SetOutput:
    """Órdenes de salida por nombre de función. El canal físico (1-indexado)
    sale de EstadoAutoclave.map_do, que el backend fija una sola vez al
    arrancar con la asignación vigente (R8, D8-5.12; core/runtime/asignacion_io)."""

    def __init__(self, io, estado, profile=None):
        self.io = io
        self.estado = estado
        self.vacump = VacuumPump(estado, profile=profile)
        self.buzer = buzer.BuzzerPlayer(self.buzer_on, self.buzer_off)
        self._ultimo_all_off_paro: float | None = None
        # D9-9: canales ya avisados en el log durante este paro (sin spam por tick)
        self._avisadas_paro: set = set()
        # D9-9: último pedido de apagar_por_paro (monotonic) y, tras el ALL_OFF
        # inmediato del flanco confirmado, no usar el DO reportado una vez
        self._ultimo_pedido_paro: float | None = None
        self._ignorar_do_una_vez = False
        # R8 (SAF-02 de la re-revisión): funciones que el control automático
        # no puede encender (reasignadas sin verificar). El modo prueba usa
        # set_output(canal) directo y sí puede, para poder verificarlas.
        self._inhibidas: frozenset = frozenset()
        self.canales_inhibidos: frozenset = frozenset()
        # AJ-02: peticiones de agua_intercambiador (ver _AGUA_INTERCAMBIADOR).
        # Al arrancar, nadie pidió nada: el canal no se toca hasta la primera
        # orden de alguno de sus dueños.
        self._agua_por_vacio = False
        self._agua_por_drenaje = False
        # E1b (D-23): canales de vapor de la fuente que el equipo no tiene.
        permitidas = salidas_vapor_permitidas(profile)
        self._canales_bloqueados = {canal_do(nombre) for nombre in _SALIDAS_VAPOR
                                    if nombre not in permitidas}
        if self._canales_bloqueados:
            # S1 (tanda 2): que quede constancia al arrancar (p. ej. generador
            # interno: DO1 y DO2 deshabilitadas)
            logger.info("SetOutput: fuente de vapor '%s'; salidas deshabilitadas: %s",
                        getattr(profile, "vapor_source", None),
                        ", ".join(f"DO{c}" for c in sorted(self._canales_bloqueados)))

    @property
    def inhibidas(self) -> frozenset:
        return self._inhibidas

    @inhibidas.setter
    def inhibidas(self, nombres) -> None:
        # Las puertas mandan por canal (devices/puertas): se publica también
        # el conjunto de canales (SAF-02, 3.ª vuelta de la revisión R8).
        nombres = frozenset(nombres)
        canales = set()
        for nombre in nombres:
            try:
                canales.add(canal_do(nombre))
            except Exception:
                logger.exception("SetOutput: canal de %s", nombre)
        self.canales_inhibidos = frozenset(canales)
        self._inhibidas = nombres

    def salida_bloqueada(self, index) -> bool:
        """True si el canal es de una fuente de vapor que el equipo no tiene."""
        return index in self._canales_bloqueados

    def set_output(self, index, value):
        """Orden directa por canal (puertas, modo prueba, cortes del lazo).
        AJ-02: una orden directa al canal de agua_intercambiador deja las dos
        peticiones coherentes con lo ordenado: OFF las apaga a las dos; ON
        cuenta como petición del drenaje (ante duda, el agua queda pedida)."""
        if self._es_canal_agua(index):
            self._agua_por_drenaje = bool(value)
            if not value:
                self._agua_por_vacio = False
        self._escribir(index, value)

    def _es_canal_agua(self, index) -> bool:
        try:
            return index == canal_do(_AGUA_INTERCAMBIADOR)
        except Exception:
            return False

    def _escribir(self, index, value):
        # Todo encendido pasa por aquí (lazo, fases, puertas, /io/test/output):
        # la fuente de vapor ausente nunca se enciende; se reafirma OFF.
        if value and index in self._canales_bloqueados:
            logger.warning("SetOutput: DO%d es de una fuente de vapor que el equipo "
                           "no tiene (vapor_source); se mantiene apagada", index)
            value = False
        # D9-9 (tanda 9): con el paro activo solo el buzzer puede encenderse.
        # Las puertas re-afirman sus salidas en cada tick (cerrar_on en
        # CERRADO, bloquear_on con empaque bajo) y las encendían entre dos
        # ALL_OFF del paro, al mismo tiempo que el buzzer. Se reafirma OFF.
        if value and self._paro_bloquea(index):
            if index not in self._avisadas_paro:
                self._avisadas_paro.add(index)
                logger.warning("SetOutput: DO%d no se enciende con el paro de "
                               "emergencia activo; se mantiene apagada", index)
            value = False
        self.io.set_output(index, value)

    def _paro_bloquea(self, index) -> bool:
        """D9-9: True si el paro impide encender el canal `index`. Paro real
        (PARO_REAL) en cualquier estado; sin datos del módulo E/S
        (PARO_EMERGENCIA sin PARO_REAL) fuera de CICLO, donde los estados ya
        mandan ALL_OFF, y en CICLO solo si la máquina pidió apagar_por_paro
        hace poco (ciclo ya abortado esperando confirmación, SAF-03 de la
        revisión B9): durante la tolerancia de DI vencida (P-3) no se toca
        nada. El buzzer nunca se bloquea. Solo cuenta un flag que sea True de
        verdad (un estado de prueba simulado no bloquea nada)."""
        get_flag = getattr(self.estado, "get_flag", None)
        if get_flag is None:
            return False
        paro_real = get_flag("PARO_REAL") is True
        paro = paro_real or get_flag("PARO_EMERGENCIA") is True
        if not paro:
            self._avisadas_paro.clear()
            self._ultimo_pedido_paro = None     # TMG-03 de la re-revisión
            return False
        try:
            if index == canal_do("buzer_alarma"):
                return False
        except Exception:
            logger.exception("SetOutput: canal del buzzer")
        if paro_real:
            return True
        try:
            if self.estado.get_machine_state() != GlobalState.CICLO:
                return True
        except Exception:
            return True
        pedido = self._ultimo_pedido_paro
        return (pedido is not None
                and time.monotonic() - pedido <= _VIGENCIA_PEDIDO_PARO_SEG)

    def _salida(self, nombre: str, value: bool) -> None:
        """Orden a la salida de la función `nombre` en su canal asignado."""
        if value and nombre in self.inhibidas:
            logger.warning("SetOutput: %s está reasignada sin verificar; se mantiene apagada", nombre)
            value = False
        self._escribir(canal_do(nombre), value)

    def vapor_generador_on(self):
        self._salida("vapor_generador", True)
        
    def vapor_generador_off(self):
        self._salida("vapor_generador", False)
        
    def vapor_caldera_on(self):
        self._salida("vapor_caldera", True)
        
    def vapor_caldera_off(self):
        self._salida("vapor_caldera", False)
        
    def vapor_chaqueta_on(self):
        self._salida("vapor_chaqueta", True)
        
    def vapor_chaqueta_off(self):
        self._salida("vapor_chaqueta", False)
        
    def vapor_camara_on(self):
        self._salida("vapor_camara", True)
        
    def vapor_camara_off(self):
        self._salida("vapor_camara", False)
        
    def descompresion_rapida_on(self):
        self._salida("descompresion_rapida", True)
        
    def descompresion_rapida_off(self):
        self._salida("descompresion_rapida", False)
        
    def descompresion_lenta_on(self):
        self._salida("descompresion_lenta", True)
        
    def descompresion_lenta_off(self):
        self._salida("descompresion_lenta", False)
        
    def descompresion_chaqueta_on(self):
        self._salida("descompresion_chaqueta", True)
        
    def descompresion_chaqueta_off(self):
        self._salida("descompresion_chaqueta", False)
        
    def vacio_camara_on(self):
        # AJ-02: el vacío solo fija su petición de agua (el drenaje la suya)
        self._agua_por_vacio = True
        self._aplicar_agua()
        self._salida("vacio_camara", True)
        
    def vacio_camara_off(self):
        # AJ-02: el agua sigue encendida si el drenaje la pide
        self._salida("vacio_camara", False)
        self._agua_por_vacio = False
        self._aplicar_agua()
        
    def desbloqueo_puerta_1_on(self):
        self._salida("desbloqueo_puerta_1", True)
        
    def desbloqueo_puerta_1_off(self):
        self._salida("desbloqueo_puerta_1", False)
        
    def desbloqueo_puerta_2_on(self):
        self._salida("desbloqueo_puerta_2", True)
        
    def desbloqueo_puerta_2_off(self):
        self._salida("desbloqueo_puerta_2", False)
        
    def bloqueo_puerta_1_on(self):
        self._salida("bloqueo_puerta_1", True)
        
    def bloqueo_puerta_1_off(self):
        self._salida("bloqueo_puerta_1", False)
        
    def bloqueo_puerta_2_on(self):
        self._salida("bloqueo_puerta_2", True)
        
    def bloqueo_puerta_2_off(self):
        self._salida("bloqueo_puerta_2", False)
        
    def aire_comprimido_camara_on(self):
        self._salida("aire_comprimido_camara", True)
        
    def aire_comprimido_camara_off(self):
        self._salida("aire_comprimido_camara", False)
        
    def aire_admosferico_camara_on(self):
        self._salida("aire_admosferico_camara", True)
        
    def aire_admosferico_camara_off(self):
        self._salida("aire_admosferico_camara", False)
        
    def agua_chaqueta_on(self):
        self._salida("agua_chaqueta", True)
        
    def agua_chaqueta_off(self):
        self._salida("agua_chaqueta", False)
        
    def agua_intercambiador_on(self):
        """Petición del control de drenaje (CicloState, PREPARACION,
        PREPARADO); el vacío usa vacio_camara_on/off (AJ-02)."""
        self._agua_por_drenaje = True
        self._aplicar_agua()
        
    def agua_intercambiador_off(self):
        """Retira la petición del drenaje; el agua sigue encendida si el
        vacío de la cámara la pide (AJ-02)."""
        self._agua_por_drenaje = False
        self._aplicar_agua()

    def _aplicar_agua(self):
        """AJ-02: una sola orden al canal con el OR de las dos peticiones
        (respeta inhibidas, canales bloqueados y paro, como toda salida)."""
        self._salida(_AGUA_INTERCAMBIADOR, self._agua_por_vacio or self._agua_por_drenaje)

    @property
    def peticiones_agua_intercambiador(self) -> dict:
        """AJ-02: peticiones vigentes (diagnóstico y pruebas)."""
        return {"vacio": self._agua_por_vacio, "drenaje": self._agua_por_drenaje}
        
    def agua_bomba_on(self):
        self._salida("agua_bomba", True)
        
    def agua_bomba_off(self):
        self._salida("agua_bomba", False)
        
    def bomba_vacio_on(self):
        if self.vacump.puede_activar():
            self.agua_bomba_on()
            self._salida("bomba_vacio", True)
            logger.info("Bomba de vacio enviada.")
            
            
    def bomba_vacio_off(self):
        self._salida("bomba_vacio", False)
        self.agua_bomba_off()
            
    def abrir_puerta_1_on(self):
        self._salida("abrir_puerta_1", True)
        
    def abrir_puerta_1_off(self):
        self._salida("abrir_puerta_1", False)
        
    def abrir_puerta_2_on(self):
        self._salida("abrir_puerta_2", True)
        
    def abrir_puerta_2_off(self):
        self._salida("abrir_puerta_2", False)
        
    def cerrar_puerta_1_on(self):
        self._salida("cerrar_puerta_1", True)
        
    def cerrar_puerta_1_off(self):
        self._salida("cerrar_puerta_1", False)
        
    def cerrar_puerta_2_on(self):
        self._salida("cerrar_puerta_2", True)
        
    def cerrar_puerta_2_off(self):
        self._salida("cerrar_puerta_2", False)
        
    def buzer_on(self):
        self._salida("buzer_alarma", True)
        
    def buzer_off(self):
        self._salida("buzer_alarma", False)
        
    def buzer_emergencia(self):
        self.buzer.play(buzer.BEEP_EMERGENCY)

    def buzer_fallo(self):
        """Pitido de aviso: cámara alcanzó condiciones seguras tras fallo/cancelación."""
        self.buzer.play(buzer.BEEP_FALLO, repeticiones=1)

    def reset_all_outputs(self, timeout: float | None = None) -> bool:
        """Apaga todas las salidas. Usa ALL_OFF con ACK; si falla, cae a comandos
        individuales (sin confirmación). Retorna True solo si el enlace confirmó
        el apagado (ALL_OFF escrito y releído). `timeout`: espera máxima del ACK (None =
        la del enlace)."""
        # TMG-02 de la re-revisión B9: un apagado total con el paro activo (p.
        # ej. el aborto del ciclo por paro sin datos) cuenta como pedido de
        # paro: las puertas del tick siguiente ya no re-encienden nada
        # (nunca impide el ALL_OFF: cualquier error aquí se ignora)
        try:
            if self.estado.get_flag("PARO_EMERGENCIA") is True:
                self._ultimo_pedido_paro = time.monotonic()
        except Exception:
            pass
        ok =self.io.all_off() if timeout is None else self.io.all_off(timeout=timeout)
        if not ok:
            for channel in sorted(set(_CANALES_APAGADO_BASE)
                                  | {i + 1 for i in EstadoAutoclave.map_do.values()}):
                self.io.set_output(channel, False)
        self.anotar_todo_apagado()
        return ok

    def anotar_todo_apagado(self) -> None:
        """AJ-02: tras un apagado total (ALL_OFF confirmado o por órdenes
        individuales, también el que el lazo manda directo al enlace al
        apagar el equipo) no queda ninguna petición de agua; sus dueños la
        vuelven a pedir en el tick siguiente si hace falta (el drenaje
        reafirma cada tick)."""
        self._agua_por_vacio = False
        self._agua_por_drenaje = False

    def apagar_por_paro(self, inmediato: bool = False) -> bool | None:
        """Apagado repetido mientras dura el paro de emergencia. Envía ALL_OFF
        si pasó _INTERVALO_ALL_OFF_PARO_SEG desde el último o si el último DO
        reportado tiene una salida encendida; si no, no hace nada y devuelve
        None. Evita esperar el ACK (hasta 1 s, bajo el lock del lazo) en cada
        tick y que el ALL_OFF corte el patrón del buzzer (TMG-09).
        `inmediato` (D9-9, flanco del paro en ControlLoop): ALL_OFF con ACK
        sin mirar el intervalo; si se confirma, la llamada siguiente (la del
        estado, en el mismo tick) no usa el DO reportado, que todavía es el
        anterior al ALL_OFF (SAF-04/TMG-01 de la revisión B9)."""
        ahora = time.monotonic()
        self._ultimo_pedido_paro = ahora
        vencido = (inmediato or self._ultimo_all_off_paro is None
                   or ahora - self._ultimo_all_off_paro >= _INTERVALO_ALL_OFF_PARO_SEG)
        ignorar_do = self._ignorar_do_una_vez and not inmediato
        self._ignorar_do_una_vez = False
        if not (vencido or (not ignorar_do and self._hay_salida_encendida())):
            return None
        self._ultimo_all_off_paro = ahora
        ok = self.reset_all_outputs()
        self._ignorar_do_una_vez = inmediato and ok is True
        return ok

    def _hay_salida_encendida(self) -> bool:
        """Según el último DO reportado por el módulo E/S. Sin dato = encendida."""
        salidas = getattr(self.estado, "salidas_do", None)
        if not isinstance(salidas, dict):
            return True
        return any(v for k, v in salidas.items() if k not in _SALIDAS_IGNORADAS_PARO)



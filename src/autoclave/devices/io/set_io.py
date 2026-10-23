# src/autoclave/devices/io/set_io.py
from autoclave.devices.pump.pump import VacuumPump
from autoclave.installation.profile import salidas_vapor_permitidas
from autoclave.core.runtime.asignacion_io import canal_do
from autoclave.core.runtime.status import EstadoAutoclave
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
# Salidas de fuente de vapor (su canal físico sale de la asignación de E/S).
_SALIDAS_VAPOR = ("vapor_generador", "vapor_caldera")
# Canales que el apagado individual (sin ACK del ALL_OFF) apaga siempre,
# además de los de la asignación vigente (R8: una salida reasignada a DO 25-32).
_CANALES_APAGADO_BASE = range(1, 25)


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
        # R8 (SAF-02 de la re-revisión): funciones que el control automático
        # no puede encender (reasignadas sin verificar). El modo prueba usa
        # set_output(canal) directo y sí puede, para poder verificarlas.
        self.inhibidas: frozenset = frozenset()
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

    def salida_bloqueada(self, index) -> bool:
        """True si el canal es de una fuente de vapor que el equipo no tiene."""
        return index in self._canales_bloqueados

    def set_output(self, index, value):
        # Todo encendido pasa por aquí (lazo, fases, /io/test/output): la
        # fuente de vapor ausente nunca se enciende; se reafirma OFF.
        if value and index in self._canales_bloqueados:
            logger.warning("SetOutput: DO%d es de una fuente de vapor que el equipo "
                           "no tiene (vapor_source); se mantiene apagada", index)
            value = False
        self.io.set_output(index, value)

    def _salida(self, nombre: str, value: bool) -> None:
        """Orden a la salida de la función `nombre` en su canal asignado."""
        if value and nombre in self.inhibidas:
            logger.warning("SetOutput: %s está reasignada sin verificar; se mantiene apagada", nombre)
            value = False
        self.set_output(canal_do(nombre), value)

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
        self.agua_intercambiador_on()
        self._salida("vacio_camara", True)
        
    def vacio_camara_off(self):
        self._salida("vacio_camara", False)
        self.agua_intercambiador_off()
        
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
        
    def aire_comprimido_chaqueta_on(self):
        self._salida("aire_comprimido_chaqueta", True)
        
    def aire_comprimido_chaqueta_off(self):
        self._salida("aire_comprimido_chaqueta", False)
        
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
        self._salida("agua_intercambiador", True)
        
    def agua_intercambiador_off(self):
        self._salida("agua_intercambiador", False)
        
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

    def reset_all_outputs(self) -> bool:
        """Apaga todas las salidas. Usa ALL_OFF con ACK; si falla, cae a comandos
        individuales (sin confirmación). Retorna True solo si el ESP32 confirmó
        el apagado vía ACK de ALL_OFF."""
        ok = self.io.all_off()
        if not ok:
            for channel in sorted(set(_CANALES_APAGADO_BASE)
                                  | {i + 1 for i in EstadoAutoclave.map_do.values()}):
                self.io.set_output(channel, False)
        return ok

    def apagar_por_paro(self) -> bool | None:
        """Apagado repetido mientras dura el paro de emergencia. Envía ALL_OFF
        si pasó _INTERVALO_ALL_OFF_PARO_SEG desde el último o si el último DO
        reportado tiene una salida encendida; si no, no hace nada y devuelve
        None. Evita esperar el ACK (hasta 1 s, bajo el lock del lazo) en cada
        tick y que el ALL_OFF corte el patrón del buzzer (TMG-09)."""
        ahora = time.monotonic()
        vencido = (self._ultimo_all_off_paro is None
                   or ahora - self._ultimo_all_off_paro >= _INTERVALO_ALL_OFF_PARO_SEG)
        if not (vencido or self._hay_salida_encendida()):
            return None
        self._ultimo_all_off_paro = ahora
        return self.reset_all_outputs()

    def _hay_salida_encendida(self) -> bool:
        """Según el último DO reportado por la tarjeta. Sin dato = encendida."""
        salidas = getattr(self.estado, "salidas_do", None)
        if not isinstance(salidas, dict):
            return True
        return any(v for k, v in salidas.items() if k not in _SALIDAS_IGNORADAS_PARO)



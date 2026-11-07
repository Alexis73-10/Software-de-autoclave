# state_machine/states/entrega_camara.py
#
# Tanda 31 (ENT-01, ENT-02, ENT-12; planeacion_entrega_camara_fin_ciclo.md):
# decide cuándo la cámara queda «entregada» al operador tras el resultado del
# ciclo. Componente puro: no lee sensores, no toca salidas ni alarmas. Lo crea
# y alimenta CicloState (run, paso 0) con el resultado del criterio de cámara
# segura (camara_segura.evaluar del programa del ciclo) y la vigencia de la
# trama AI; publica en estado.entrega_camara lo que necesitan el backend
# (compuerta de /cycle/acknowledge, ENT-03) y la pantalla.
#
# - FALLO / CANCELADO (ENT-01): entregada cuando la cámara es segura, con datos
#   vigentes y sin sellado, en LECTURAS_ENTREGA lecturas de tramas AI distintas
#   seguidas (como _DEBOUNCE_LECTURAS de protocolo_fallo).
# - COMPLETADO (ENT-02): primero la espera fija `tiempo_espera_apertura` desde
#   el COMPLETADO; después, el mismo criterio. Pasado `timeout_temperatura`
#   tras la espera, `timeout_vencido` queda en True (CicloState activa CIC-07
#   una vez) y se sigue esperando.
# - Una vez entregada no se retira. Sin dato para decidir = no entregada
#   (falla cerrada). Tiempos con time.monotonic() (los da quien llama).

import math

from autoclave.core.runtime.motivos import Motivo

# Lecturas seguidas (tramas AI distintas) con la cámara segura para entregar
LECTURAS_ENTREGA = 3

RESULTADO_COMPLETADO = "COMPLETADO"

# Motivos propios (no los da camara_segura)
MOTIVO_SIN_DATO = "sin_datos_vigentes"
MOTIVO_SELLADO = "camara_sellada"


def _motivo_sin_dato() -> Motivo:
    return Motivo(MOTIVO_SIN_DATO, "Sin conexión con el módulo E/S: datos no vigentes")


def _motivo_sellado() -> Motivo:
    return Motivo("camara_sellada", "Cámara sellada: esperando que la carga se enfríe")


def _segundos(valor, defecto: float) -> float:
    """Número finito >= 0, o `defecto`."""
    if isinstance(valor, bool):
        return defecto
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return defecto
    return max(0.0, v) if math.isfinite(v) else defecto


class EntregaCamara:
    """Decisión de entrega de un ciclo (una instancia por resultado)."""

    def __init__(self, resultado: str, ahora: float, tiempo_espera_s=0.0,
                 timeout_s=None):
        self.resultado = resultado
        self._t0 = ahora
        completado = resultado == RESULTADO_COMPLETADO
        # ENT-02: la espera fija y el timeout solo rigen tras un COMPLETADO
        self._espera_s = _segundos(tiempo_espera_s, 0.0) if completado else 0.0
        self._timeout_s = (_segundos(timeout_s, None) if completado and timeout_s is not None
                           else None)
        self.entregada = False
        self.motivos: list = []
        self.timeout_vencido = False
        self._lecturas = 0
        self._ultima_seq = None

    def espera_restante_s(self, ahora: float) -> int | None:
        """Segundos (enteros, hacia arriba) que faltan de la espera fija tras un
        COMPLETADO; None si no hay espera en curso (o ya entregada)."""
        if self.entregada or self._espera_s <= 0:
            return None
        restante = self._espera_s - (ahora - self._t0)
        return int(math.ceil(restante)) if restante > 0 else None

    def actualizar(self, ahora: float, segura: bool, motivos=(), ai_vigente: bool = True,
                   seq_ai=None, sellado: bool = False, exige_seq: bool = False) -> None:
        """Una evaluación (un tick). `segura`: camara_segura.evaluar con datos
        vigentes; `motivos`: los de camara_segura.motivos si no es segura;
        `ai_vigente`/`seq_ai`: trama AI de este tick (vigencia_ai.leer);
        `sellado`: el protocolo de fallo mantiene la cámara sellada (D8-2.10);
        `exige_seq`: hay proveedor de vigencia (ControlLoop), de modo que una
        trama sin número entero no suma lecturas (B1 de la revisión, falla
        cerrada); sin proveedor (dobles de prueba) se cuenta como antes."""
        if self.entregada:
            return
        if self.espera_restante_s(ahora) is not None:
            # ENT-02: durante la espera fija no se cuentan lecturas
            self._lecturas = 0
            self._ultima_seq = None
            self.motivos = []
            return
        ok = segura is True and ai_vigente is True and not sellado
        if not ok:
            self._lecturas = 0
            self._ultima_seq = None
            if ai_vigente is not True:
                self.motivos = [_motivo_sin_dato()]
            elif sellado and segura is True:
                self.motivos = [_motivo_sellado()]
            else:
                lista = list(motivos or ())
                self.motivos = lista or [_motivo_sin_dato()]
            self._revisar_timeout(ahora)
            return
        # B1: con proveedor, sin número de trama válido no se suma (falla cerrada)
        if exige_seq and (isinstance(seq_ai, bool) or not isinstance(seq_ai, int)):
            self.motivos = [_motivo_sin_dato()]
            self._revisar_timeout(ahora)
            return
        # misma trama AI que la última contada: no suma (tramas distintas)
        if seq_ai is not None and seq_ai == self._ultima_seq:
            return
        self._ultima_seq = seq_ai
        self._lecturas += 1
        self.motivos = []
        if self._lecturas >= LECTURAS_ENTREGA:
            self.entregada = True

    def minutos_tras_espera(self, ahora: float) -> float:
        """Minutos transcurridos desde el fin de la espera fija (para CIC-07)."""
        return max(0.0, ahora - self._t0 - self._espera_s) / 60

    def _revisar_timeout(self, ahora: float) -> None:
        if self._timeout_s is None or self.timeout_vencido:
            return
        if (ahora - self._t0 - self._espera_s) > self._timeout_s:
            self.timeout_vencido = True

    def publicar(self, ahora: float, resultado_pendiente: bool) -> dict:
        """Lo que va a estado.entrega_camara (ENT-12). `motivos` son Motivo
        (str con código y valores): el backend los presenta."""
        return {
            "entregada": self.entregada is True,
            "motivos": list(self.motivos),
            "espera_restante_s": self.espera_restante_s(ahora),
            "forzable": (not self.entregada) and resultado_pendiente is True,
        }

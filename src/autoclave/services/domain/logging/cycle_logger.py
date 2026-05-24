# services/domain/logging/cycle_logger.py
#
# Servicio de logging del ciclo.
#
# Responsabilidades:
#   - Detectar automáticamente el inicio/fin del estado CICLO
#   - Registrar lecturas de sensores en la DB según intervalos configurados
#   - Marcar qué lecturas van al ticket de impresión (para_imprimir)
#
# Integración:
#   El control loop llama a cycle_logger.update() en cada tick.
#   El logger NO bloquea: opera en el mismo hilo del control loop.
#
# Mapping de fases a códigos del ticket:
#   W (Warming)        → PRECALENTAMIENTO, PURGA, PRE_VACIO
#   H (Heating)        → CALENTAMIENTO, ESTABILIZACION
#   S (Sterilization)  → ESTERILIZACION
#   E (Exhaust/End)    → COMPLETADO, CANCELADO, FALLO, EMERGENCIA

import time
import logging
from datetime import datetime
from autoclave.state_machine.machine.enum_global import GlobalState

logger = logging.getLogger(__name__)

VERSION_SW = "2.0.0"   # TODO: leer de pyproject.toml si se necesita dinámico

# Fases internas → código del ticket
_FASE_A_CODIGO: dict[str, str] = {
    "PRECALENTAMIENTO": "PH",
    "PURGA":            "PG",
    "PRE_VACIO":        "PV",
    "CALENTAMIENTO":    "H",
    "ESTABILIZACION":   "E",
    "ESTERILIZACION":   "S",
    "COMPLETADO":       "E",
    "CANCELADO":        "F",
    "FALLO":            "F",
    "EMERGENCIA":       "F",
}

# Parámetros de intervalo según el código de fase
_INTERVALO_PARAM: dict[str, str] = {
    "W": "intervalo_impresion",
    "H": "intervalo_impresion",
    "S": "intervalo_imprecion_esterilizacion",   # nota: typo intencional del JSON
    "E": None,
}

_INTERVALO_DEFAULT: dict[str, int] = {
    "W": 180,   # 3 min
    "H": 180,
    "S": 60,    # 1 min
}


class CycleLogger:
    """
    Servicio de logging de datos del ciclo de esterilización.

    Dependencias:
        db            → DbManager
        estado        → EstadoAutoclave
        config        → ConfigManager
        profile       → InstallationProfile
        cycle_manager → CycleManager
    """

    def __init__(self, db, estado, config, profile, cycle_manager):
        self.db            = db
        self.estado        = estado
        self.config        = config
        self.profile       = profile
        self.cycle_manager = cycle_manager

        # Estado interno
        self._activo            = False
        self._ciclo_id: int | None = None
        self._ciclo_inicio      = None    # time.time() al iniciar
        self._ultimo_log        = 0.0     # time.time() del último registro
        self._ultima_fase_codigo = None   # para detectar cambio de fase

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def update(self):
        """
        Llamar en CADA tick del control loop.
        Detecta transiciones CICLO/no-CICLO y registra lecturas.
        """
        current = self.estado.get_machine_state()

        if current == GlobalState.CICLO:
            if not self._activo:
                self._on_inicio()
            else:
                self._tick()
        else:
            if self._activo:
                resultado = self.estado.fase_ciclo or "DESCONOCIDO"
                self._on_fin(resultado)

    @property
    def ciclo_id(self) -> int | None:
        """ID del ciclo activo en la DB (None si no hay ciclo en curso)."""
        return self._ciclo_id

    @property
    def activo(self) -> bool:
        return self._activo

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _on_inicio(self):
        numero = self.db.siguiente_numero_ciclo()

        # Leer metadatos del ciclo seleccionado
        tipo   = ""
        nombre = ""
        temp_e = None
        t_e    = None
        try:
            cycle  = self.cycle_manager.get_selected_cycle()
            tipo   = cycle.id
            nombre = cycle.name
            temp_e = cycle.get_param("temperatura_esterilizacion")
            t_e    = cycle.get_param("tiempo_esterilizacion")
        except Exception as exc:
            logger.warning("CycleLogger: no se pudo leer el ciclo: %s", exc)

        self._ciclo_id = self.db.crear_ciclo(
            numero      = numero,
            tipo        = tipo,
            nombre      = nombre,
            temp_ester  = temp_e,
            tiempo_ester= t_e,
            modelo      = getattr(self.profile, "model_id",      ""),
            serie       = getattr(self.profile, "serial_number", ""),
            version_sw  = VERSION_SW,
        )
        self._ciclo_inicio       = time.time()
        self._ultimo_log         = 0.0    # primera lectura se hace inmediatamente
        self._ultima_fase_codigo = None
        self._activo             = True

        logger.info(
            "CycleLogger: ciclo #%05d iniciado → DB id=%d | %s",
            numero, self._ciclo_id, nombre
        )

    def _on_fin(self, resultado: str):
        if self._ciclo_id is not None:
            # Última lectura con código E
            self._registrar_lectura("E", para_imprimir=True)
            self.db.cerrar_ciclo(self._ciclo_id, resultado)
            logger.info(
                "CycleLogger: ciclo id=%d cerrado → %s", self._ciclo_id, resultado
            )

        self._activo            = False
        self._ciclo_id          = None
        self._ciclo_inicio      = None
        self._ultima_fase_codigo = None

    # ------------------------------------------------------------------
    # Tick: evaluar si es momento de registrar
    # ------------------------------------------------------------------

    def _tick(self):
        fase_nombre  = self.estado.fase_ciclo or ""
        fase_codigo  = _FASE_A_CODIGO.get(fase_nombre, " ")

        # ¿Cambió de fase? → registrar siempre (marca transición)
        cambio_fase = (fase_codigo != self._ultima_fase_codigo)

        if cambio_fase:
            self._registrar_lectura(fase_codigo, para_imprimir=True)
            self._ultima_fase_codigo = fase_codigo
            return   # ya registramos, resetear el timer natural

        # ¿Se cumplió el intervalo?
        param_key = _INTERVALO_PARAM.get(fase_codigo)
        if param_key is None:
            return   # código E → no hay intervalo periódico

        intervalo = self.config.get(param_key) or _INTERVALO_DEFAULT.get(fase_codigo, 60)
        ahora     = time.time()

        if (ahora - self._ultimo_log) >= intervalo:
            self._registrar_lectura(fase_codigo, para_imprimir=True)

    # ------------------------------------------------------------------
    # Escritura a DB
    # ------------------------------------------------------------------

    def _registrar_lectura(self, fase_codigo: str, para_imprimir: bool = False):
        if self._ciclo_id is None:
            return

        ahora   = time.time()
        elapsed = ahora - (self._ciclo_inicio or ahora)

        temp = self.estado.sensores_temp.get("temp_camara")
        pres = self.estado.sensores_pres.get("pres_camara")

        self.db.insertar_lectura(
            ciclo_id      = self._ciclo_id,
            timestamp_rel = _fmt_elapsed(elapsed),
            timestamp_abs = datetime.now().isoformat(),
            fase_codigo   = fase_codigo,
            temp          = temp,
            pres          = pres,
            para_imprimir = para_imprimir,
        )
        self._ultimo_log = ahora

        logger.debug(
            "LOG [%s] %s  %.1f°C  %.1f kPa  imprimir=%s",
            fase_codigo,
            _fmt_elapsed(elapsed),
            temp or 0.0,
            pres or 0.0,
            para_imprimir,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _fmt_elapsed(seconds: float) -> str:
    """Convierte segundos en HH:MM:SS."""
    s = max(0, int(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"

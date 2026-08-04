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
import importlib.metadata
from datetime import datetime
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.services.domain.logging.ticket_formatter import (
    format_footer,
    format_header,
    format_row,
)

logger = logging.getLogger(__name__)


def _software_version() -> str:
    """Versión real instalada del paquete (misma fuente que el ticket de
    arranque en main_window.py) — evita que el ticket de ciclo muestre una
    versión desactualizada o inventada."""
    try:
        return importlib.metadata.version("autoclave")
    except importlib.metadata.PackageNotFoundError:
        return "?"

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

# Fases normales del pipeline (en curso) — cualquier otro valor de
# fase_ciclo (CANCELADO, EMERGENCIA, FALLO_SUMINISTRO, SENSOR_AUSENTE,
# FALLO_PUERTA_*, FALLO_CONEXION, FALLO_<fase>, etc.) representa un cierre
# anormal del ciclo. "COMPLETADO" es el único cierre normal y se maneja
# aparte (ver update()).
_FASES_EN_CURSO: set[str] = {
    "PRECALENTAMIENTO", "PURGA", "PRE_VACIO",
    "CALENTAMIENTO", "ESTABILIZACION", "ESTERILIZACION",
    "SECADO", "DESCOMPRESION",
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

    def __init__(self, db, estado, config, profile, cycle_manager, printer=None):
        self.db            = db
        self.estado        = estado
        self.config        = config
        self.profile       = profile
        self.cycle_manager = cycle_manager
        self.printer       = printer

        # Estado interno
        self._activo            = False
        self._ciclo_id: int | None = None
        self._ciclo_inicio      = None    # time.time() al iniciar
        self._ultimo_log        = 0.0     # time.time() del último registro
        self._ultima_fase_codigo = None   # para detectar cambio de fase
        self._ultimo_sub_estado  = None   # para detectar cambio de paso interno de la fase
        self._ultima_temp        = None   # última temp_camara registrada (→ "Temp. final" del pie)
        # CicloState deja el estado global en CICLO (ESPERANDO_CONFIRMACION)
        # tras un fallo/cancelación/emergencia hasta que el operador confirma
        # — puede tardar. Este flag marca que _on_fin() ya se ejecutó de
        # inmediato al detectar el cierre anormal, para no reprocesar el
        # mismo cierre ni arrancar un ciclo nuevo mientras se espera esa
        # confirmación (ver update()).
        self._cierre_ya_procesado = False

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
            if self._cierre_ya_procesado:
                return  # ya se cerró/imprimió; falta solo la confirmación
            if not self._activo:
                self._on_inicio()
                return
            fase_nombre = self.estado.fase_ciclo or ""
            if fase_nombre != "COMPLETADO" and fase_nombre not in _FASES_EN_CURSO:
                # Cierre anormal (fallo/cancelación/emergencia): no esperar a
                # que el estado global salga de CICLO (puede tardar hasta que
                # el operador confirme) — cerrar e imprimir ahora mismo.
                self._cierre_ya_procesado = True
                self._on_fin(fase_nombre)
            else:
                self._tick()
        else:
            if self._activo:
                resultado = self.estado.fase_ciclo or "DESCONOCIDO"
                self._on_fin(resultado)
            self._cierre_ya_procesado = False

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
            temp_e = cycle.get_param("esterilizacion", "temperatura_esterilizacion")
            t_e    = cycle.get_param("esterilizacion", "tiempo_esterilizacion")
        except Exception as exc:
            logger.warning("CycleLogger: no se pudo leer el ciclo: %s", exc)

        serie      = getattr(self.profile, "serial_number", "")
        modelo     = getattr(self.profile, "model_id", "")
        version_sw = _software_version()

        self._ciclo_id = self.db.crear_ciclo(
            numero      = numero,
            tipo        = tipo,
            nombre      = nombre,
            temp_ester  = temp_e,
            tiempo_ester= t_e,
            modelo      = modelo,
            serie       = serie,
            version_sw  = version_sw,
        )
        self._ciclo_inicio       = time.time()
        self._ultimo_log         = 0.0    # primera lectura se hace inmediatamente
        self._ultima_fase_codigo = None
        self._ultimo_sub_estado  = None
        self._ultima_temp        = None
        self._activo             = True
        self._cierre_ya_procesado = False

        if self.printer is not None:
            meta = {
                "numero_ciclo":          numero,
                "serie":                 serie,
                "modelo":                modelo,
                "version_sw":            version_sw,
                "nombre_ciclo":          nombre,
                "tipo_ciclo":            tipo,
                "temp_esterilizacion":   temp_e,
                "tiempo_esterilizacion": t_e,
                "fecha_inicio":          datetime.now().isoformat(),
            }
            self.printer.enqueue(format_header(meta))

        logger.info(
            "CycleLogger: ciclo #%05d iniciado → DB id=%d | %s",
            numero, self._ciclo_id, nombre
        )

    def _on_fin(self, resultado: str):
        if self._ciclo_id is not None:
            # Última lectura con código E
            self._registrar_lectura("E", para_imprimir=True)
            motivo = getattr(self.estado, "motivo_fallo", "") or None
            self.db.cerrar_ciclo(self._ciclo_id, resultado, motivo)

            if self.printer is not None:
                self.printer.enqueue(format_footer(
                    resultado, datetime.now().isoformat(),
                    temp_final=self._ultima_temp, motivo=motivo,
                ))

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
        sub_estado   = getattr(self.estado, "sub_estado_ciclo", "") or ""

        # ¿Cambió de fase, o de paso interno dentro de la misma fase (p.ej.
        # pulso de vacío bajo → alto)? → registrar siempre, como referencia
        # de presión/temperatura al momento del cambio, sin esperar el
        # intervalo periódico de impresión.
        cambio_fase       = (fase_codigo != self._ultima_fase_codigo)
        cambio_sub_estado = (sub_estado != self._ultimo_sub_estado)

        if cambio_fase or cambio_sub_estado:
            self._registrar_lectura(fase_codigo, para_imprimir=True)
            self._ultima_fase_codigo = fase_codigo
            self._ultimo_sub_estado  = sub_estado
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
        timestamp_rel = _fmt_elapsed(elapsed)

        temp = self.estado.sensores_temp.get("temp_camara")
        pres = self.estado.sensores_pres.get("pres_camara")

        if temp is not None:
            self._ultima_temp = temp

        self.db.insertar_lectura(
            ciclo_id      = self._ciclo_id,
            timestamp_rel = timestamp_rel,
            timestamp_abs = datetime.now().isoformat(),
            fase_codigo   = fase_codigo,
            temp          = temp,
            pres          = pres,
            para_imprimir = para_imprimir,
        )
        self._ultimo_log = ahora

        if para_imprimir and self.printer is not None:
            self.printer.enqueue(format_row({
                "fase_codigo":   fase_codigo,
                "timestamp_rel": timestamp_rel,
                "temp_camara":   temp,
                "pres_camara":   pres,
            }))

        logger.debug(
            "LOG [%s] %s  %.1f°C  %.1f kPa  imprimir=%s",
            fase_codigo,
            timestamp_rel,
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

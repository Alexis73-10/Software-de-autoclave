# services/domain/logging/cycle_logger.py
#
# Servicio de logging del ciclo.
#
# Responsabilidades:
#   - Detectar automáticamente el inicio/fin del estado CICLO
#   - Registrar lecturas de sensores en la DB según intervalos configurados
#   - Marcar qué lecturas van al ticket de impresión (para_imprimir)
#   - Alimentar la pantalla de ciclo en curso: serie de la gráfica cada
#     _PERIODO_GRAFICA_S (lecturas_grafica) y tramos de fase (ciclo_fases),
#     ambos con reloj monotónico (C-01). Independiente del ticket.
#
# Integración:
#   El control loop llama a cycle_logger.update() en cada tick.
#   El logger NO bloquea: opera en el mismo hilo del control loop.
#
# Mapping de fases a códigos del ticket:
#   W (Warming)        → PRECALENTAMIENTO, PRE_VACIO
#   H (Heating)        → CALENTAMIENTO
#   S (Sterilization)  → ESTERILIZACION
#   E (Exhaust/End)    → COMPLETADO, CANCELADO, FALLO, EMERGENCIA

import time
import logging
import json
import queue
import threading
import uuid
from datetime import datetime
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.core.runtime.sensores_ciclo import (asignacion_de, canonica, f0_disponible,
                                                   sensor_principal)
from autoclave.services.domain.logging.ticket_formatter import (
    CLAVE_CANCELADO_POR,
    CLAVE_CONFIRMADO_FORZADO,
    CLAVE_CONFIRMADO_TRAS_PARO,
    CLAVE_SECADO_TRAS_FALLO,
    aviso_secado_tras_fallo,
    f0_objetivo_de_programa,
    format_footer,
    format_header,
    format_row,
    lineas_resultado,
    motivo_ticket,
    presentacion_actual,
)

logger = logging.getLogger(__name__)

# TMG-02 (revisión de B9a): espera máxima por el candado de la base en el tick
ESPERA_BD_EN_TICK_S = 0.05


def _software_version() -> str:
    """Versión con el commit de la compilación (VER-03/VER-05: misma fuente que
    el ticket de arranque, autoclave._version). Antes salía de los metadatos del
    paquete, que el .exe no trae: el registro de ciclo quedaba con "?"."""
    from autoclave._version import version_completa
    return version_completa()

# Fases internas → código del ticket
_FASE_A_CODIGO: dict[str, str] = {
    "PRECALENTAMIENTO": "PH",
    "PRE_VACIO":        "PV",
    "CALENTAMIENTO":    "H",
    "ESTERILIZACION":   "S",
    "COMPLETADO":       "E",
    "CANCELADO":        "F",
    "FALLO":            "F",
    "EMERGENCIA":       "F",
}

# Fases normales del pipeline (en curso) — cualquier otro valor de
# fase_ciclo (CANCELADO, EMERGENCIA, FALLO_SUMINISTRO, SENSOR_AUSENTE,
# FALLO_PUERTA_*, FALLO_CONEXION, FALLO_<fase>, etc.) representa un cierre
# anormal del ciclo. "COMPLETADO" es el cierre normal; también se cierra al
# instante en el registro (PF-17, ver update()).
_FASES_EN_CURSO: set[str] = {
    "PRECALENTAMIENTO", "PRE_VACIO",
    "CALENTAMIENTO", "ESTERILIZACION",
    "SECADO", "DESCOMPRESION",
}

# Parámetros de intervalo según el código de fase
_INTERVALO_PARAM: dict[str, str] = {
    "W": "intervalo_impresion",
    "H": "intervalo_impresion",
    "S": "intervalo_impresion_esterilizacion",   # O2a: errata corregida (alias en ConfigManager)
    "E": None,
}

# Periodo de muestreo de la serie de la gráfica (pantalla de ciclo en curso).
_PERIODO_GRAFICA_S = 1.0

_INTERVALO_DEFAULT: dict[str, int] = {
    "W": 180,   # 3 min
    "H": 180,
    "S": 60,    # 1 min
}

# ENT-06 (tanda 31): filas «E» de la espera de la entrega de la cámara, con
# el mismo parámetro de intervalo general del ticket
_INTERVALO_ESPERA_PARAM = "intervalo_impresion"
_INTERVALO_ESPERA_DEFAULT = 180


def _entrega_registrada(estado) -> bool:
    """ENT-01/02 (tanda 31): True solo si CicloState publicó la cámara como
    entregada (`estado.entrega_camara["entregada"] is True`). Sin dato o con
    otro valor, no entregada (falla cerrada)."""
    entrega = getattr(estado, "entrega_camara", None)
    return isinstance(entrega, dict) and entrega.get("entregada") is True


class _RegistroBD:
    """Registro en la base del ciclo en curso (TMG-01 de T8). `id` lo fija la
    tarea que crea el ciclo; `fallido` corta toda escritura posterior del
    ciclo tras el primer error (el ciclo sigue en el respaldo y el ticket)."""
    __slots__ = ("id", "fallido")

    def __init__(self):
        self.id: int | None = None
        self.fallido = False


class CicloParaAlarma:
    """FC-03 (tanda 21): referencia al ciclo de una alarma que aparece en CICLO,
    tomada en el hilo que activa la alarma (ControlLoop o HTTP) sin esperar.
    El id definitivo se resuelve después, en el hilo escritor del historial de
    alarmas (`resolver`), con espera acotada: cubre el ciclo cuyo id aún no
    fijó la tarea asíncrona que lo crea y el primer tick de CICLO, antes de que
    el CycleLogger abra el registro."""
    __slots__ = ("_logger", "_reg")

    def __init__(self, logger_ciclo, reg):
        self._logger = logger_ciclo
        self._reg = reg      # None: el registro del ciclo aún no existe

    def resolver(self, timeout: float = 5.0, paso: float = 0.02) -> int | None:
        limite = time.monotonic() + timeout
        while True:
            reg = self._reg
            if reg is None:
                # primer tick de CICLO: el registro lo abre update() en el paso 6
                reg = self._logger._reg
                if reg is not None:
                    self._reg = reg
            if reg is not None:
                if reg.id is not None:
                    return reg.id
                if reg.fallido:
                    return None
            if time.monotonic() >= limite:
                return None
            time.sleep(paso)


class EscritorBD:
    """TMG-01 de T8: las escrituras del ciclo en SQLite (lock compartido con el
    backend y timeout de 10 s) salen del hilo del lazo. Un hilo propio las
    ejecuta en orden; la cola es acotada y, llena, `__call__` lanza
    queue.Full (el CycleLogger corta el registro en la base del ciclo).
    `maximo=0`: cola sin límite (el respaldo, S3d: líneas pequeñas y pocas, y
    nunca debe descartarse ni escribirse en línea)."""

    def __init__(self, maximo: int = 1000, nombre: str = "CycleLoggerBD"):
        self._cola: queue.Queue = queue.Queue(maxsize=maximo)
        self._hilo = threading.Thread(target=self._correr, name=nombre, daemon=True)
        self._hilo.start()

    def __call__(self, tarea) -> None:
        self._cola.put_nowait(tarea)

    def _correr(self) -> None:
        while True:
            tarea = self._cola.get()
            if tarea is None:
                return
            try:
                tarea()
            except Exception:
                logger.exception("CycleLogger: error en la escritura en la base")

    def detener(self, timeout: float = 2.0) -> bool:
        """Vacía la cola (las tareas ya encoladas se ejecutan) y detiene el
        hilo. True si terminó dentro de `timeout`."""
        try:
            self._cola.put(None, timeout=timeout)
        except queue.Full:
            logger.warning("EscritorBD: cola llena al detener; quedan tareas sin escribir")
            return False
        self._hilo.join(timeout)
        return not self._hilo.is_alive()


def _en_linea(tarea) -> None:
    tarea()


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

    def __init__(self, db, estado, config, profile, cycle_manager, printer=None,
                 reloj_mono=time.monotonic, contador=None, respaldo=None,
                 sin_base_de_datos=False, ejecutar_bd=None, ejecutar_respaldo=None):
        self.db            = db
        self.estado        = estado
        self.config        = config
        self.profile       = profile
        self.cycle_manager = cycle_manager
        self.printer       = printer
        # Lo fija ControlLoop: devuelve la copia con la que corre el ciclo
        # (T-17). Sin él, el programa seleccionado.
        self.programa_en_ejecucion = None
        # Contador persistente de ciclos (E4, §7.5); sin él, MAX(numero)+1
        self.contador = contador
        # Respaldo JSONL por ciclo (T8, §7.4): se escribe siempre, con y sin base
        self.respaldo = respaldo
        # Arranque sin base de datos (OPERANDO_SIN_BD): el ticket lo indica
        self.sin_base_de_datos = sin_base_de_datos
        # TMG-01 de T8: el backend pasa un EscritorBD (hilo propio); sin él,
        # en línea (pruebas)
        self._ejecutar_bd = ejecutar_bd or _en_linea
        # S3d: hilo FIFO propio del respaldo, independiente de la base (una base
        # atascada no retrasa el respaldo); sin él, comparte el de la base
        self._ejecutar_respaldo_propio = ejecutar_respaldo
        self._lock_aviso = threading.Lock()
        self._numero_en_curso: int | None = None
        # S3c (tanda 2): lo llama (una vez por ciclo, desde el hilo de escritura)
        # cuando la base falla en caliente; el backend pasa a OPERANDO_SIN_BD
        self.al_fallar_bd = None
        self._bd_avisada = False
        self._reg: _RegistroBD | None = None
        self._reg_cerrado: _RegistroBD | None = None   # ciclo ya cerrado, aún en CICLO
        # A13 (tanda 28): ciclo cerrado con el secado tras fallo aún pendiente:
        # (registro, avisos_ticket guardado). Al conocerse el resultado se
        # reescribe su línea en la base (historial, reimpresión y PDF)
        self._secado_pendiente = None
        # FC-13 (tanda 21): hora de pared del cierre del ciclo en pantalla
        self.hora_fin_pantalla: str | None = None
        self.uuid_ciclo: str | None = None
        self._numero_reservado: int | None = None
        self._numero_provisional: int | None = None   # TMG-01: contador no escribible
        self.sin_registro = False

        # Estado interno
        self._activo            = False
        self._operador          = ""      # O1: respaldo/ticket del ciclo en curso
        self._operador_ticket   = ""      # O1: usuario real (sin la leyenda de sin BD)
        self._ciclo_inicio      = None    # time.time() al iniciar
        # Reloj monotónico del último registro (None = registrar ya). Intervalos
        # y tiempo transcurrido con monotonic: un salto del reloj de pared no
        # debe frenar ni inflar el registro (auditoría de temporización T1).
        self._ultimo_log: float | None = None
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
        # ENT-06/07 (tanda 31): resultado ya registrado (fila «E», base y
        # respaldo) y el ciclo sigue abierto hasta la entrega de la cámara o
        # la confirmación. None = sin resultado todavía
        self._resultado: dict | None = None

        # Pantalla de ciclo en curso (reloj monotónico, aparte del ticket)
        self._reloj_mono        = reloj_mono
        self._t0_mono: float | None = None    # inicio del ciclo
        self._t_fin_s: float | None = None    # transcurrido congelado al terminar
        self._fase_seguida: str | None = None
        self._proxima_muestra_s: float | None = None

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def update(self):
        """
        Llamar en CADA tick del control loop.
        Detecta transiciones CICLO/no-CICLO y registra lecturas.
        """
        current = self.estado.get_machine_state()
        if self._secado_pendiente is not None:
            self._seguir_secado_tras_fallo()

        if current == GlobalState.CICLO:
            if self._cierre_ya_procesado:
                return  # ya se cerró/imprimió; falta solo la confirmación
            if not self._activo:
                self._on_inicio_protegido()
                self._seguir_pantalla()
                return
            fase_nombre = self.estado.fase_ciclo or ""
            self._seguir_pantalla()
            if self._resultado is not None:
                # ENT-06 (tanda 31): espera de la entrega de la cámara
                if _entrega_registrada(self.estado):
                    self._cierre_ya_procesado = True
                    self._on_cierre()
                else:
                    self._tick_espera()
            elif fase_nombre not in _FASES_EN_CURSO:
                # Resultado del ciclo (COMPLETADO, fallo, cancelación,
                # emergencia): fila «E», base y respaldo ahora mismo (PF-17,
                # E4: un corte antes de la entrega no lo deja sin resultado).
                # ENT-06/07 (tanda 31): el pie y la fecha de fin, en la entrega
                self._on_resultado(fase_nombre)
                if _entrega_registrada(self.estado):
                    self._cierre_ya_procesado = True
                    self._on_cierre(fila_final=False)
            else:
                self._tick()
        else:
            if self._activo:
                # Salida de CICLO sin entrega registrada (confirmación forzada,
                # tras paro, o cualquier otra vía): se cierra igual
                if self._resultado is None:
                    self._on_resultado(self.estado.fase_ciclo or "DESCONOCIDO")
                    self._on_cierre(fila_final=False)
                else:
                    self._on_cierre()
            self._cierre_ya_procesado = False
            self._resultado = None
            self._reg_cerrado = None
            self.hora_fin_pantalla = None
            self._t0_mono = None
            self._t_fin_s = None

    @property
    def _ciclo_id(self) -> int | None:
        return self._reg.id if self._reg is not None else None

    @property
    def ciclo_id(self) -> int | None:
        """ID del ciclo activo en la DB (None si no hay ciclo en curso)."""
        return self._ciclo_id

    @property
    def activo(self) -> bool:
        return self._activo

    @property
    def ciclo_id_pantalla(self) -> int | None:
        """ID en BD del ciclo que muestra la pantalla de ciclo en curso: el
        activo, o el recién cerrado por fallo/cancelación mientras la máquina
        sigue en CICLO esperando confirmación (ciclo_id ya es None ahí)."""
        if self._ciclo_id is not None:
            return self._ciclo_id
        return self._reg_cerrado.id if self._reg_cerrado is not None else None

    def ciclo_para_alarma(self):
        """FC-03 (tanda 21): ciclo al que pertenece una alarma que aparece
        ahora. Sin E/S ni espera (corre en el hilo que activa la alarma):
        devuelve un int si el id ya se conoce, un `CicloParaAlarma` si falta
        resolverlo (ciclo recién creado o primer tick de CICLO) y None fuera
        de CICLO. Cubre también el ciclo ya cerrado que sigue en CICLO
        esperando la confirmación (`_reg_cerrado`)."""
        reg = self._reg if self._reg is not None else self._reg_cerrado
        if reg is not None:
            if reg.id is not None:
                return reg.id
            return None if reg.fallido else CicloParaAlarma(self, reg)
        try:
            en_ciclo = self.estado.get_machine_state() == GlobalState.CICLO
        except Exception:
            en_ciclo = False
        # sin registro y ya activo: el inicio falló (sin base); nada que esperar
        if en_ciclo and not self._cierre_ya_procesado and not self._activo:
            return CicloParaAlarma(self, None)
        return None

    def transcurrido_s(self) -> float | None:
        """Segundos monotónicos desde el inicio del ciclo, congelados al
        terminar; None sin ciclo."""
        if self._t0_mono is None:
            return None
        if self._t_fin_s is not None:
            return self._t_fin_s
        return self._reloj_mono() - self._t0_mono

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _programa(self):
        if self.programa_en_ejecucion is not None:
            return self.programa_en_ejecucion()
        return self.cycle_manager.get_selected_cycle()

    def _on_inicio_protegido(self) -> None:
        """TMG-01 de T6: un fallo al registrar el inicio (contador o base) no
        sube como excepción del tick (cortaría el latido y el lazo reintentaría
        cada 0,5 s apagando y encendiendo salidas). El ciclo sigue sin registro
        en la base; `sin_registro` lo deja visible y el número reservado se
        conserva (sin huecos por reintentos)."""
        try:
            self._on_inicio()
        except Exception:
            logger.exception("CycleLogger: no se pudo registrar el inicio del ciclo")
            self._reg = None
            self._activo = True
            self.sin_registro = True
            self._t0_mono = self._reloj_mono()

    def _numero_nuevo(self) -> int:
        if self.contador is None:
            return self.db.siguiente_numero_ciclo()
        if self.sin_base_de_datos:
            # sin base (arranque o falla en caliente) no se toca: podría estar
            # bloqueada y este código corre en el tick
            return self._siguiente_protegido(None)
        try:
            # TMG-02: en el tick no se espera la base más de 50 ms
            maximo_bd = self.db.max_numero_ciclo(espera_s=ESPERA_BD_EN_TICK_S)
        except Exception:
            logger.exception("CycleLogger: no se pudo leer MAX(numero) de la base")
            maximo_bd = None
        return self._siguiente_protegido(maximo_bd)

    def _siguiente_protegido(self, maximo_bd: int | None) -> int:
        """TMG-01 (revisión de B9a): si el contador no se puede escribir (tras
        sus reintentos), el ciclo NO puede quedar sin respaldo, base, ticket ni
        marca: se usa un número provisional en memoria, mayor que todo lo
        conocido, y se registra el error. El siguiente ciclo vuelve a intentar
        el contador persistente."""
        try:
            numero = self.contador.siguiente(maximo_bd)
            self._numero_provisional = None
            return numero
        except Exception:
            try:
                leido = int(self.contador.ultimo)
            except Exception:
                leido = 0
            numero = max(leido, int(maximo_bd or 0), self._numero_provisional or 0) + 1
            self._numero_provisional = numero
            logger.exception("CycleLogger: contador de ciclos no escribible; número "
                             "provisional %d (revise el acceso a data/ciclo_contador.json)", numero)
            return numero

    def _on_inicio(self):
        self.sin_registro = False
        if self._numero_reservado is None:
            self._numero_reservado = self._numero_nuevo()
        numero = self._numero_reservado
        self._numero_en_curso = numero
        self.uuid_ciclo = str(uuid.uuid4())

        # Leer metadatos del ciclo seleccionado
        tipo   = ""
        nombre = ""
        temp_e = None
        t_e    = None
        asignacion = ""
        numero_programa = None
        programa_json = None
        cycle = None
        try:
            cycle  = self._programa()
            tipo   = cycle.id
            nombre = cycle.name
            temp_e = cycle.get_param("esterilizacion", "temperatura_esterilizacion")
            t_e    = cycle.get_param("esterilizacion", "tiempo_esterilizacion")
            # RS-08: asignación de sensores vigente al inicio y número de programa
            asignacion = canonica(asignacion_de(cycle))
            numero_programa = getattr(cycle, "number", None)
            if hasattr(cycle, "instantanea"):
                programa_json = json.dumps(cycle.instantanea(), ensure_ascii=False,
                                           sort_keys=True)
        except Exception as exc:
            logger.warning("CycleLogger: no se pudo leer el ciclo: %s", exc)

        serie      = getattr(self.profile, "serial_number", "")
        modelo     = getattr(self.profile, "model_id", "")
        version_sw = _software_version()

        # Marca de ciclo en curso ANTES de la base: si la base falla, la marca
        # permite recuperar el ciclo interrumpido tras un corte (TMG-03 de T6)
        if self.contador is not None:
            try:
                self.contador.marcar_en_curso(
                    numero, json.loads(programa_json) if programa_json else None)
            except Exception:
                logger.exception("CycleLogger: no se pudo marcar el ciclo en curso")

        fecha_inicio = datetime.now().isoformat()
        # O1 (tanda 3): operador que inició el ciclo; se consume (un ciclo que
        # arranca por otra vía no hereda el de uno anterior). Sin base de datos
        # la leyenda del ticket y del respaldo sigue siendo "SIN OPERADOR / SIN BD"
        operador = str(getattr(self.estado, "operador_inicio", "") or "")
        try:
            self.estado.operador_inicio = ""
        except Exception:
            pass
        self._operador_ticket = "" if self.sin_base_de_datos else operador
        self._operador = "SIN OPERADOR / SIN BD" if self.sin_base_de_datos else operador
        datos_ciclo = dict(
            numero      = numero,
            tipo        = tipo,
            nombre      = nombre,
            temp_ester  = temp_e,
            tiempo_ester= t_e,
            modelo      = modelo,
            serie       = serie,
            version_sw  = version_sw,
            asignacion_sensores = asignacion,
            numero_programa = numero_programa,
            programa_json = programa_json,
            operador    = operador,
        )
        # Instalación por automatización: identidad original del equipo. Solo se
        # agrega si existe, para que un ciclo de fabricación quede idéntico
        # (columnas NULL y encabezado del respaldo sin claves nuevas).
        for _clave, _atributo in (("serie_original", "serial_original"),
                                  ("modelo_original", "modelo_original")):
            _valor = getattr(self.profile, _atributo, None)
            if isinstance(_valor, str) and _valor:
                datos_ciclo[_clave] = _valor
        # T8 (§7.4): respaldo antes de la base, con los mismos datos. S3d: el
        # fsync sale del tick; va por el mismo hilo FIFO que la base
        self._bd_avisada = False
        if self.respaldo is not None:
            uuid_ciclo = self.uuid_ciclo
            encabezado = {**datos_ciclo, "fecha_inicio": fecha_inicio,
                          "operador": self._operador}
            self._respaldar(lambda: self.respaldo.encabezado(uuid_ciclo, encabezado))

        # T8 (BD-02, §7.3; TMG-01): la base se escribe fuera del tick y un
        # fallo no detiene el ciclo; el registro sigue en el respaldo y el ticket
        self._reg = _RegistroBD()
        self.sin_registro = self.sin_base_de_datos
        if self.sin_base_de_datos:
            self._reg.fallido = True
        else:
            uuid_ciclo = self.uuid_ciclo
            self._bd("crear el ciclo",
                     lambda _id: self.db.crear_ciclo(uuid=uuid_ciclo, **datos_ciclo), crea=True)
        self._numero_reservado = None
        self._ciclo_inicio       = time.time()
        self._ultimo_log         = None   # primera lectura se hace inmediatamente
        self._ultima_fase_codigo = None
        self._ultimo_sub_estado  = None
        self._ultima_temp        = None
        self._activo             = True
        self._cierre_ya_procesado = False
        self._t0_mono            = self._reloj_mono()
        self._t_fin_s            = None
        self._fase_seguida       = None
        self._proxima_muestra_s  = None
        self._reg_cerrado        = None
        self.hora_fin_pantalla   = None
        self._secado_pendiente   = None     # A13: el del ciclo anterior ya no se sigue
        self._resultado          = None

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
                "fecha_inicio":          fecha_inicio,
                "sin_registro":          self.sin_base_de_datos,
                "operador":              operador,
            }
            # Automatización: el encabezado en vivo muestra la identidad original
            # (solo si existe; en fabricación el meta queda como antes)
            for _clave in ("serie_original", "modelo_original"):
                if _clave in datos_ciclo:
                    meta[_clave] = datos_ciclo[_clave]
            # T29-07: F0 activo y su objetivo, con la misma condición que el
            # «F0 total» del pie (_on_fin); sin F0 el meta queda como antes
            try:
                if (cycle.get_param("globals", "F0") and f0_disponible(self.profile)):
                    meta["f0_activo"] = True
                    meta["f0_objetivo"] = f0_objetivo_de_programa(cycle)
            except Exception as exc:
                logger.warning("CycleLogger: no se pudo leer F0 del ciclo: %s", exc)
            # I3 (tanda 5): idioma y unidades vigentes al iniciar, para todo el ticket
            self._presentacion = presentacion_actual()
            self.printer.enqueue(format_header(meta, self._presentacion))

        logger.info(
            "CycleLogger: ciclo #%05d iniciado → DB id=%s | %s",
            numero, self._ciclo_id, nombre
        )

    def _sin_datos_modulo_es_s(self) -> float | None:
        """T2-a: segundos del ciclo sin datos del módulo E/S, o None."""
        valor = getattr(self.estado, "sin_datos_modulo_es_s", None)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor <= 0:
            return None
        return float(valor)

    def _avisos_ciclo(self, resultado: str) -> tuple[list, float | None]:
        """(avisos del pie, segundos sin datos del módulo E/S) vigentes.
        D8-2.14: van también a la base y al respaldo (reimpresión idéntica)."""
        sin_datos_s = self._sin_datos_modulo_es_s()
        # X9 (D9-13.4): texto o {"clave": ..., parámetros}
        avisos = [a for a in (getattr(self.estado, "avisos_ciclo", None) or [])
                  if isinstance(a, str)
                  or (isinstance(a, dict) and isinstance(a.get("clave"), str))]
        # FC-12 (tanda 21): el usuario identificado que canceló, en el
        # ticket, la base y el respaldo (reimpresión idéntica)
        cancelado_por = getattr(self.estado, "cancelado_por", None)
        if resultado == "CANCELADO" and isinstance(cancelado_por, str) and cancelado_por:
            avisos.append({"clave": CLAVE_CANCELADO_POR, "usuario": cancelado_por})
        # A13 (tanda 28): secado tras fallo del ciclo no completado
        secado = (aviso_secado_tras_fallo(getattr(self.estado, "secado_tras_fallo", None))
                  if str(resultado or "") != "COMPLETADO" else None)
        if secado is not None:
            avisos.append(secado)
        return avisos, sin_datos_s

    def _avisos_confirmacion(self) -> list:
        """ENT-04/05 (tanda 31): línea del pie cuando el ciclo se confirmó sin
        la entrega de la cámara (forzada por un ingeniero o tras un paro)."""
        forzada = getattr(self.estado, "confirmacion_forzada", None)
        if isinstance(forzada, dict) and forzada.get("usuario"):
            motivo = forzada.get("motivo")
            if isinstance(motivo, (list, tuple)):
                motivo = "; ".join(str(m) for m in motivo if m)
            return [{"clave": CLAVE_CONFIRMADO_FORZADO, "usuario": str(forzada["usuario"]),
                     "motivo": str(motivo) if motivo else None}]
        if getattr(self.estado, "confirmado_tras_paro", False) is True:
            return [{"clave": CLAVE_CONFIRMADO_TRAS_PARO}]
        return []

    def _on_resultado(self, resultado: str):
        """ENT-06/07 (tanda 31): instante del resultado (fallo, cancelación o
        COMPLETADO). Fila «E» y, si no es COMPLETADO, «Error de ciclo» y
        «F0 total» en el ticket; resultado, motivo, código, valores y F0 (el de
        este momento) a la base y al respaldo con `fecha_resultado`. Sin pie ni
        fecha de fin: el ciclo sigue abierto hasta la entrega (`_on_cierre`).
        El reloj de la pantalla sigue corriendo (ENT-10)."""
        # T8: también sin registro en la base (respaldo y ticket siguen)
        if not self._activo:
            return
        if self._t0_mono is not None:
            t_res = self._reloj_mono() - self._t0_mono
            self._bd("cerrar la fase", lambda i: self.db.cerrar_fase_abierta(i, t_res),
                     presentacion=True)
        fecha_resultado = datetime.now().isoformat()
        # FC-13 (tanda 21): sello de pared del resultado, para la pantalla
        self.hora_fin_pantalla = datetime.now().isoformat(timespec="seconds")
        # Lectura con código E en el instante del resultado
        self._registrar_lectura("E", para_imprimir=True)
        motivo = getattr(self.estado, "motivo_fallo", "") or None
        codigo = getattr(self.estado, "codigo_fallo", "") or None
        valores = getattr(self.estado, "valores_fallo", None)
        valores = dict(valores) if isinstance(valores, dict) and codigo else {}
        f0_total = None
        try:
            cycle = self._programa()
            # F0 solo en laboratorio (SAF-06 de T3), como las fases
            if (cycle and cycle.get_param("globals", "F0")
                    and f0_disponible(self.profile)):
                f0_total = self.estado.f0_acumulado
        except Exception as exc:
            logger.warning("CycleLogger: no se pudo leer F0 del ciclo: %s", exc)
        avisos, sin_datos_s = self._avisos_ciclo(resultado)
        avisos_ticket = ({"sin_datos_s": sin_datos_s, "avisos": list(avisos)}
                         if sin_datos_s is not None or avisos else None)
        self._resultado = {"resultado": resultado, "motivo": motivo, "codigo": codigo,
                           "valores": valores, "f0_total": f0_total}
        # TMG-03 de T8: primero el respaldo, después la base
        if self.respaldo is not None and self.uuid_ciclo:
            uuid_ciclo = self.uuid_ciclo
            registro = {"fecha_resultado": fecha_resultado, "resultado": resultado,
                        "motivo": motivo, "codigo": codigo, "f0_final": f0_total,
                        "valores": valores}
            if avisos_ticket is not None:
                registro["avisos_ticket"] = avisos_ticket
            self._respaldar(lambda: self.respaldo.resultado(uuid_ciclo, registro))
        # I4: los parámetros solo si los hay (dobles de prueba antiguos)
        extra = {"valores_fallo": valores} if valores else {}
        if avisos_ticket is not None:
            extra["avisos_ticket"] = avisos_ticket
        self._bd("registrar el resultado", lambda i: self.db.registrar_resultado(
            i, resultado, motivo, codigo, f0_final=f0_total,
            fecha_resultado=fecha_resultado, **extra))

        if self.printer is not None:
            p = getattr(self, "_presentacion", None)
            lineas = lineas_resultado(resultado, motivo_ticket(codigo, motivo, p), f0_total, p)
            if lineas:
                self.printer.enqueue("\n".join(lineas))
        logger.info("CycleLogger: ciclo id=%s con resultado %s; espera la entrega de la cámara",
                    self._ciclo_id, resultado)

    def _tick_espera(self):
        """ENT-06 (tanda 31): durante la espera de la entrega, fila «E» cada
        `intervalo_impresion` (Principal y presión) al ticket, la base y el
        respaldo; también tras un COMPLETADO."""
        try:
            intervalo = float(self.config.get(_INTERVALO_ESPERA_PARAM)
                              or _INTERVALO_ESPERA_DEFAULT)
        except Exception:
            intervalo = _INTERVALO_ESPERA_DEFAULT
        if intervalo <= 0:
            intervalo = _INTERVALO_ESPERA_DEFAULT
        if self._ultimo_log is None or (self._reloj_mono() - self._ultimo_log) >= intervalo:
            self._registrar_lectura("E", para_imprimir=True)

    def _on_cierre(self, fila_final: bool = True):
        """ENT-06/07/10 (tanda 31): entrega de la cámara (o confirmación
        forzada, tras paro o salida de CICLO). Fila final «E» (salvo que el
        resultado se haya registrado en este mismo tick), pie completo con la
        hora de la entrega, fecha de fin en la base y cierre del respaldo; el
        reloj de la pantalla se detiene aquí."""
        if self._activo:
            res = self._resultado or {"resultado": self.estado.fase_ciclo or "DESCONOCIDO",
                                      "motivo": None, "codigo": None, "valores": {},
                                      "f0_total": None}
            resultado, motivo, codigo = res["resultado"], res["motivo"], res["codigo"]
            valores, f0_total = res["valores"], res["f0_total"]
            if self._t_fin_s is None and self._t0_mono is not None:
                self._t_fin_s = self._reloj_mono() - self._t0_mono
                t_fin = self._t_fin_s
                self._bd("cerrar la fase", lambda i: self.db.cerrar_fase_abierta(i, t_fin),
                         presentacion=True)
            self._reg_cerrado = self._reg
            if fila_final:
                self._registrar_lectura("E", para_imprimir=True)
            # avisos vigentes ahora (secado tras fallo ya en su estado final)
            avisos, sin_datos_s = self._avisos_ciclo(resultado)
            avisos += self._avisos_confirmacion()
            avisos_ticket = ({"sin_datos_s": sin_datos_s, "avisos": list(avisos)}
                             if sin_datos_s is not None or avisos else None)
            secado = next((a for a in avisos if isinstance(a, dict)
                           and a.get("clave") == CLAVE_SECADO_TRAS_FALLO), None)
            if secado is not None and secado.get("estado") == "pendiente" and self._reg is not None:
                self._secado_pendiente = (self._reg, dict(avisos_ticket))
            fecha_fin = datetime.now().isoformat()
            # TMG-03 de T8: primero el respaldo, después la base
            if self.respaldo is not None and self.uuid_ciclo:
                uuid_ciclo = self.uuid_ciclo
                cierre = {"fecha_fin": fecha_fin, "resultado": resultado,
                          "motivo": motivo, "codigo": codigo, "f0_final": f0_total,
                          "valores": valores}
                if avisos_ticket is not None:
                    cierre["avisos_ticket"] = avisos_ticket
                self._respaldar(lambda: self.respaldo.cierre(uuid_ciclo, cierre))
            extra = {"valores_fallo": valores} if valores else {}
            if avisos_ticket is not None:
                extra["avisos_ticket"] = avisos_ticket
            self._bd("cerrar el ciclo", lambda i: self.db.cerrar_ciclo(
                i, resultado, motivo, codigo, f0_final=f0_total, fecha_fin=fecha_fin, **extra))

            if self.printer is not None:
                self.printer.enqueue(format_footer(
                    resultado, fecha_fin,
                    temp_final=self._ultima_temp,
                    motivo=motivo_ticket(codigo, motivo, getattr(self, "_presentacion", None)),
                    f0_total=f0_total,
                    avisos=list(avisos) or None,
                    operador=self._operador_ticket or None,
                    p=getattr(self, "_presentacion", None),
                    sin_datos_s=sin_datos_s,     # T2-a (tanda 7)
                ))

            logger.info(
                "CycleLogger: ciclo id=%s cerrado → %s", self._ciclo_id, resultado
            )

        self._activo            = False
        self._reg               = None
        self._ciclo_inicio      = None
        self._ultima_fase_codigo = None
        self._numero_reservado  = None
        if self.contador is not None:
            # S3d: la marca se limpia DESPUÉS del cierre del respaldo (mismo hilo
            # FIFO) y solo si sigue siendo la de este ciclo: un corte entre la
            # limpieza y el cierre dejaría un ciclo terminado sin cierre ni marca.
            # ENT-07 (tanda 31): hasta la entrega la marca sigue (un corte en la
            # espera cuenta como ciclo interrumpido)
            numero_cerrado = self._numero_en_curso
            self._numero_en_curso = None
            self._respaldar(lambda: self._limpiar_marca(numero_cerrado))

    def _on_fin(self, resultado: str):
        """Compatibilidad: resultado y cierre en el mismo instante."""
        if self._resultado is None:
            self._on_resultado(resultado)
        self._on_cierre(fila_final=False)

    # ------------------------------------------------------------------
    # Pantalla de ciclo en curso: tramos de fase y serie de la gráfica
    # ------------------------------------------------------------------

    def _seguir_pantalla(self):
        if self._reg is None or self._reg.fallido or self._t0_mono is None:
            return
        fase = self.estado.fase_ciclo or ""
        t = self._reloj_mono() - self._t0_mono
        en_curso = fase in _FASES_EN_CURSO

        if fase != self._fase_seguida:
            if self._fase_seguida is not None:
                self._bd("cerrar la fase", lambda i: self.db.cerrar_fase_abierta(i, t),
                         presentacion=True)
            if en_curso:
                self._bd("abrir la fase", lambda i: self.db.abrir_fase(i, fase, t),
                         presentacion=True)
            # ENT-10 (tanda 31): tras el resultado el reloj sigue hasta la
            # entrega de la cámara (_on_cierre lo detiene)
            self._fase_seguida = fase

        # ENT-10: la serie también se muestrea durante la espera de la entrega
        muestrear = en_curso or (self._resultado is not None and self._t_fin_s is None)
        if muestrear and (self._proxima_muestra_s is None or t >= self._proxima_muestra_s):
            valores = (t, fase,
                       self.estado.sensores_temp.get("temp_camara"),
                       self.estado.sensores_temp.get("temp_ref"),
                       self.estado.sensores_pres.get("pres_camara"),
                       self.estado.sensores_temp.get("temp_2_camara"))
            self._bd("guardar la gráfica",
                     lambda i: self.db.insertar_lectura_grafica(i, *valores),
                     presentacion=True)
            # sin ráfagas de recuperación si un tick llega tarde
            siguiente = (self._proxima_muestra_s or t) + _PERIODO_GRAFICA_S
            self._proxima_muestra_s = siguiente if siguiente > t else t + _PERIODO_GRAFICA_S

    def _seguir_secado_tras_fallo(self) -> None:
        """A13 (tanda 28): con el resultado del secado tras fallo ya conocido,
        reemplaza su línea en `avisos_ticket` del ciclo cerrado (historial,
        reimpresión y PDF). Fuera del tick (ejecutor de la base); un error
        solo queda en el log. El ticket impreso al cierre no cambia."""
        reg, avisos_ticket = self._secado_pendiente
        nuevo = aviso_secado_tras_fallo(getattr(self.estado, "secado_tras_fallo", None))
        if nuevo is None or nuevo.get("estado") == "pendiente":
            return
        self._secado_pendiente = None
        avisos = [nuevo if (isinstance(a, dict) and a.get("clave") == nuevo["clave"]) else a
                  for a in avisos_ticket.get("avisos") or []]
        datos = {"sin_datos_s": avisos_ticket.get("sin_datos_s"), "avisos": avisos}

        def tarea():
            if reg.fallido or reg.id is None:
                return
            try:
                self.db.actualizar_avisos_ticket(reg.id, datos)
            except Exception as exc:
                logger.warning("CycleLogger: no se pudo registrar el secado tras fallo del "
                               "ciclo id=%s: %s", reg.id, exc)
        try:
            self._ejecutar_bd(tarea)
        except Exception:
            logger.exception("CycleLogger: no se pudo encolar el secado tras fallo")

    def _bd(self, que: str, operacion, crea: bool = False, presentacion: bool = False):
        """Escritura del ciclo en la base, fuera del tick (TMG-01 de T8).
        `operacion(id)` corre en el ejecutor con el id del ciclo; sin id (aún no
        creado o fallido) no corre. Un error corta el resto del registro del
        ciclo en la base (cortacircuito), salvo en los datos de pantalla
        (gráfica y tramos), que solo se registran en el log."""
        reg = self._reg
        if reg is None or reg.fallido:
            return

        def tarea():
            if reg.fallido or (not crea and reg.id is None):
                return
            try:
                resultado = operacion(reg.id)
            except Exception as exc:
                if presentacion:
                    logger.warning("CycleLogger: no se pudo %s: %s", que, exc)
                    return
                logger.exception("CycleLogger: no se pudo %s en la base; el ciclo sigue "
                                 "en el respaldo y el ticket", que)
                reg.fallido = True
                # el flag del logger solo si este es el ciclo vigente (o el recién
                # cerrado): una tarea tardía del anterior no marca el nuevo
                if reg is self._reg or reg is self._reg_cerrado:
                    self.sin_registro = True
                self._avisar_bd_fallida(str(exc))
                return
            if crea:
                reg.id = resultado

        try:
            self._ejecutar_bd(tarea)
        except Exception:
            logger.exception("CycleLogger: cola de escritura en la base llena; se corta "
                             "el registro del ciclo en la base")
            reg.fallido = True
            self.sin_registro = True
            self._avisar_bd_fallida("cola de escritura en la base llena")

    def _limpiar_marca(self, numero) -> None:
        try:
            self.contador.limpiar_en_curso(solo_numero=numero)
        except Exception:
            logger.exception("CycleLogger: no se pudo limpiar la marca de ciclo en curso")

    @property
    def _ejecutar_respaldo(self):
        return self._ejecutar_respaldo_propio or self._ejecutar_bd

    def detener(self, timeout: float = 5.0) -> None:
        """Apagado ordenado (S3d): vacía las colas de escritura del respaldo y de
        la base antes de cerrar la base. Llamar con el lazo ya detenido."""
        for ejecutor in {id(e): e for e in (self._ejecutar_respaldo, self._ejecutar_bd)}.values():
            detener = getattr(ejecutor, "detener", None)
            if detener is not None:
                detener(timeout)

    def _respaldar(self, tarea) -> None:
        """S3d (tanda 2): el respaldo JSONL (con su flush y fsync) sale del hilo
        del lazo: va por el mismo ejecutor FIFO que la base, así que se conserva
        "primero el respaldo, después la base" (TMG-03 de T8). Si la cola está
        llena se escribe en línea: el respaldo nunca se descarta. Un corte de
        energía puede perder la última línea todavía en cola; la lectura ya
        descarta una línea incompleta y el ciclo queda como INTERRUMPIDO."""
        try:
            self._ejecutar_respaldo(tarea)
        except Exception:
            logger.warning("CycleLogger: cola de escritura llena; el respaldo se escribe en línea")
            tarea()

    def _avisar_bd_fallida(self, motivo: str) -> None:
        """S3c: la base falló en caliente. Una sola vez por ciclo y sin romper
        nada: el ciclo sigue en el respaldo y el ticket."""
        with self._lock_aviso:
            if self._bd_avisada or self.al_fallar_bd is None:
                return
            self._bd_avisada = True
        try:
            self.al_fallar_bd(motivo)
        except Exception:
            logger.exception("CycleLogger: error al avisar la falla de la base")

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
        ahora     = self._reloj_mono()

        if self._ultimo_log is None or (ahora - self._ultimo_log) >= intervalo:
            self._registrar_lectura(fase_codigo, para_imprimir=True)

    # ------------------------------------------------------------------
    # Escritura a DB
    # ------------------------------------------------------------------

    def _registrar_lectura(self, fase_codigo: str, para_imprimir: bool = False):
        # T8: sin registro en la base, la lectura va igual al respaldo y al ticket
        if not self._activo:
            return

        ahora   = self._reloj_mono()
        elapsed = ahora - self._t0_mono if self._t0_mono is not None else 0.0
        timestamp_rel = _fmt_elapsed(elapsed)

        temp_c = self.estado.sensores_temp.get("temp_camara")
        # El ticket y la temperatura final usan el sensor Principal (RS-08)
        try:
            temp = self.estado.sensores_temp.get(sensor_principal(self._programa()))
        except Exception:
            temp = temp_c
        pres = self.estado.sensores_pres.get("pres_camara")

        if temp is not None:
            self._ultima_temp = temp

        lectura = dict(
            timestamp_rel = timestamp_rel,
            timestamp_abs = datetime.now().isoformat(),
            fase_codigo   = fase_codigo,
            temp          = temp_c,
            pres          = pres,
            para_imprimir = para_imprimir,
            temp_principal = temp,
        )
        # TMG-03 de T8: primero el respaldo, después la base
        if self.respaldo is not None and self.uuid_ciclo:
            uuid_ciclo, copia = self.uuid_ciclo, dict(lectura)
            self._respaldar(lambda: self.respaldo.lectura(uuid_ciclo, copia))
        self._bd("guardar la lectura", lambda i: self.db.insertar_lectura(ciclo_id=i, **lectura))
        self._ultimo_log = ahora

        if para_imprimir and self.printer is not None:
            self.printer.enqueue(format_row({
                "fase_codigo":   fase_codigo,
                "timestamp_rel": timestamp_rel,
                "temp_camara":   temp,      # columna del ticket = Principal
                "pres_camara":   pres,
            }, getattr(self, "_presentacion", None)))

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

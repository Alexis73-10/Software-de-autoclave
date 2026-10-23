# autoclave/backend/context.py

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.services.domain.puertas.ser_puertas import ServicioPuertas
from autoclave.installation.bootstrap import get_installation_profile
from autoclave.installation.clock_guard import ClockTamperedError
from autoclave.installation.equipment import get_capabilities
from autoclave.installation.profile import (entradas_no_monitoreadas, sondas_no_vigiladas,
                                           tarjeta_emparejada)
from autoclave.devices.factory.factory import build_doors_cfg, build_serial
from autoclave.devices.puertas.advanced_door import AdvancedDoor
from autoclave.devices.puertas.door_factory import create_door
from autoclave.devices.io.set_io import SetOutput
from autoclave.hal.measures.units import Units
from autoclave.services.domain.loop.control_loop import ControlLoop
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.catalogo import CONFIGURACION_INVALIDA, OPERANDO_SIN_BD, SEN_09, SIS_03
from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.core.managers.config_manager import ConfigManager
from autoclave.core.managers.validacion_config import errores_config_arranque
from autoclave.services.domain.logging.db_manager import (DB_DEFAULT, BdBloqueadaError, DbManager,
                                                          apartar_base_corrupta, es_base_corrupta)
from autoclave.core.runtime.respaldo_ciclos import RespaldoCiclos, reimportar
from autoclave.services.domain.logging.cycle_logger import CycleLogger, EscritorBD
from autoclave.services.domain.logging.historial_alarmas import HistorialAlarmas
from autoclave.services.domain.logging.sensor_calibration_audit import SensorCalibrationAuditDB
from autoclave.devices.printer.realtime_printer import RealtimePrinter
from autoclave.backend.arranque import secuencia
from autoclave.backend.arranque.secuencia import ErrorArranque
from autoclave.backend.arranque.sin_bd import BdNoDisponible
from autoclave.utils.paths import app_root, calibration_path
from autoclave.core.runtime.contador_ciclos import ContadorCiclos
from autoclave.core.runtime.sensores_ciclo import interpretar_asignacion
from autoclave.core.managers.cycle_manager import Cycle

import os
import json
import logging
import threading
import time

import yaml

logger = logging.getLogger(__name__)

def _programa_desconocido():
    """Programa del ciclo interrumpido cuando no se puede reconstruir: se
    trata como carga líquida (nunca la rápida) con el modo de descompresión
    por omisión (lenta). Lado seguro (TMG-03 de T6)."""
    return Cycle("desconocido", "Programa desconocido",
                 {"globals": {"tipo_carga": {"value": "liquido"}}})


MOTIVO_INTERRUMPIDO = ("Ciclo interrumpido: el equipo se reinició o perdió energía "
                       "sin cerrarlo. El ciclo no se reanuda; la carga NO está estéril.")


def avisar_entradas_no_monitoreadas(profile) -> None:
    """Deja constancia al arrancar de las entradas de suministro que el
    perfil declara sin cablear (E1-1): el equipo no las vigila."""
    no_monitoreadas = entradas_no_monitoreadas(profile)
    if no_monitoreadas:
        logger.warning("Entradas de suministro no monitoreadas (perfil de instalación): %s",
                       ", ".join(no_monitoreadas))
    # Canales de temperatura sin sonda declarada (A-2): no se vigilan
    sin_sonda = sondas_no_vigiladas(profile)
    if sin_sonda:
        logger.warning("Sondas de temperatura no vigiladas (perfil de instalación): %s",
                       ", ".join(sin_sonda))


_LOCK_MANTENIMIENTO = threading.RLock()


class BackendContext:
    """Objetos del backend. El constructor no hace E/S, para que el puerto 8000
    abra desde t = 0: cada parte se construye en su etapa de arranque
    (arranque/secuencia.py), que llama a los métodos de abajo en orden.
    Mientras una parte no existe, su atributo vale None."""

    def __init__(self):
        self.estado = EstadoAutoclave()
        self.alarm_manager = AlarmManager(self.estado)
        self.profile = None
        self.cap = None
        self.cycle_manager = None
        self.config_manager = None
        self.units = None
        self.serial = None
        self.setdo = None
        self.doors = []
        self.servicio_puertas = None
        self.db = None
        self.calibration_audit = None
        self.realtime_printer = None
        self.cycle_logger = None
        self.control_loop = None
        self.sin_base_de_datos = False
        self._lock_sin_bd = threading.Lock()
        self.db_real = None
        # R8: asignación de E/S (cargar_asignacion_io, etapa de configuración)
        self.archivo_asignacion = None
        self.asignacion_fabrica = None
        self.motivo_asignacion = ""
        self.errores_asignacion = []
        self.asignacion_pendiente = []
        self.verificacion_asignacion = {"estado": "sin_cambios", "funciones": {}}

    # ── 1. verificando_instalacion ───────────────────────────────────────────

    def verificar_instalacion(self) -> None:
        try:
            profile = get_installation_profile()
        except ClockTamperedError as e:
            raise ErrorArranque(secuencia.ARR_RELOJ, str(e)) from e
        if profile is None:
            raise ErrorArranque(secuencia.ARR_PERFIL, "Backend sin InstallationProfile")
        self.profile = profile
        self.cap = get_capabilities(profile.equipment_class)
        avisar_entradas_no_monitoreadas(profile)

    # ── 4. cargando_configuracion ────────────────────────────────────────────

    def cargar_configuracion(self) -> str | None:
        """Bloqueante: global_params.json ilegible, ciclo por defecto
        inexistente o configuración inválida. Degradable: un ciclo corrupto."""
        config_manager = ConfigManager()
        try:
            config_manager.load_config()
        except (OSError, ValueError) as e:
            raise ErrorArranque(secuencia.ARR_CONFIG_ILEGIBLE, f"global_params.json: {e}") from e
        self.config_manager = config_manager

        self.cycle_manager = CycleManager()
        self.cycle_manager.load_all_cycles()
        logger.info(f"Ciclos cargados: {list(self.cycle_manager.cycles.keys())}")
        try:
            self.cycle_manager.set_default_cycle("bowe_dick")
        except Exception as e:
            raise ErrorArranque(secuencia.ARR_CICLO_DEFECTO, str(e)) from e

        motivo = self._validar_configuracion()
        if motivo:
            raise ErrorArranque(secuencia.CONFIGURACION_INVALIDA, motivo)
        self.cargar_asignacion_io()
        if self.cycle_manager.errores_carga:
            logger.warning("Ciclos omitidos por JSON corrupto: %s",
                           ", ".join(self.cycle_manager.errores_carga))
            return secuencia.ARR_CICLO_CORRUPTO
        return None

    # ── R8 (tanda 8, D8-5.12): asignación de E/S ─────────────────────────────

    def cargar_asignacion_io(self, archivo=None, config_dir=None) -> None:
        """Aplica la asignación vigente (fábrica + data/asignacion_io.json) a
        los mapas de EstadoAutoclave, UNA vez, antes de construir SetOutput,
        puertas y ControlLoop. Fábrica inválida: fallo bloqueante del
        arranque. Archivo de la vigente ilegible o inválido: NO se usa la de
        fábrica en silencio (el puerto dañado volvería a usarse): alarma
        CONFIGURACION_INVALIDA y equipo bloqueado (construir_control), con la
        API disponible para que el ingeniero restaure la de fábrica."""
        from autoclave.core.runtime import asignacion_io as aio
        self.archivo_asignacion = archivo or aio.ArchivoAsignacion()
        self.motivo_asignacion = ""
        self.errores_asignacion = []
        self.asignacion_pendiente = []
        self.asignacion_modificada_en = ""
        self.verificacion_asignacion = {"estado": "sin_cambios", "funciones": {}}
        # SAF-01/SAF-02 (revisión R8): mientras quede una función reasignada sin
        # verificar por el ingeniero, no se inicia ningún ciclo, aunque la
        # alarma SEN-09 se resuelva con el reconocimiento de una FALLA
        if not getattr(self, "_bloqueo_asignacion_registrado", False):
            self.alarm_manager.condiciones_bloqueo.append(
                lambda: bool(getattr(self, "asignacion_pendiente", None)))
            self._bloqueo_asignacion_registrado = True
        try:
            self.asignacion_fabrica = aio.fabrica(config_dir)
        except aio.ErrorAsignacion as e:
            raise ErrorArranque(secuencia.CONFIGURACION_INVALIDA,
                                f"Asignación de E/S de fábrica inválida: {e}") from e
        try:
            asignacion, datos = aio.vigente(self.asignacion_fabrica, self.archivo_asignacion)
        except aio.ErrorAsignacion as e:
            self.motivo_asignacion = (f"Asignación de E/S inválida "
                                      f"({self.archivo_asignacion.ruta.name}): {e}")
            self.errores_asignacion = e.errores
            aio.aplicar_en_memoria(self.asignacion_fabrica)   # solo para construir; bloqueado
            self.alarm_manager.activar(CONFIGURACION_INVALIDA, motivo=self.motivo_asignacion)
            logger.critical("%s", self.motivo_asignacion)
            return
        aio.aplicar_en_memoria(asignacion)
        if datos["cambios"]:
            logger.warning("Asignación de E/S distinta de la de fábrica: %s",
                           ", ".join(f"{f}={p}" for f, p in sorted(datos["cambios"].items())))
        self.asignacion_pendiente = [f for f in datos["verificacion_pendiente"]
                                     if f in aio.funciones()]
        self.asignacion_modificada_en = str(datos.get("modificado_en") or "")
        if self.asignacion_pendiente:
            self.verificacion_asignacion = {"estado": "pendiente",
                                            "funciones": {f: "pendiente" for f in self.asignacion_pendiente}}
            self.alarma_asignacion_sin_verificar()

    # Salidas que aportan energía (vapor, aire comprimido): inhibidas mientras
    # haya una analógica reasignada sin verificar (SAF-02 de la re-revisión R8)
    _SALIDAS_ENERGIA = ("vapor_generador", "vapor_caldera", "vapor_chaqueta", "vapor_camara",
                        "aire_comprimido_chaqueta", "aire_comprimido_camara")
    _SALIDAS_VENTEO = ("descompresion_rapida", "descompresion_lenta", "descompresion_chaqueta",
                       "aire_admosferico_camara")

    def inhibir_salidas_sin_verificar(self) -> None:
        """SAF-02 (re-revisión R8): fuera de ciclo los lazos de PREPARACION y
        PREPARADO accionan salidas solos. Mientras queden funciones sin
        verificar, el control automático no enciende las salidas reasignadas
        sin verificar ni, si hay una analógica sin verificar, las que aportan
        energía a cámara o chaqueta. Abrir o cerrar sin verificar inhibe las
        dos de esa puerta. El venteo y el alivio no se inhiben nunca. El modo
        prueba sí puede encenderlas (para verificarlas).

        TMG-02 (4.ª vuelta): bajo el mismo lock que SEN-09 y leyendo los
        pendientes dentro de él, para que dos verificaciones simultáneas no
        dejen un conjunto viejo como último escrito."""
        with self.__dict__.setdefault("_lock_alarma_asignacion", threading.Lock()):
            self._inhibir_salidas_sin_verificar()

    def _inhibir_salidas_sin_verificar(self) -> None:
        from autoclave.core.runtime import asignacion_io as aio
        setdo = getattr(self, "setdo", None)
        if setdo is None:
            return
        pendientes = list(getattr(self, "asignacion_pendiente", []) or [])
        inhibidas = {aio.nombre_estado(aio.base(f)) for f in pendientes
                     if aio.funciones().get(f) == "DO"}
        if any(aio.funciones().get(f) == "AI" for f in pendientes):
            inhibidas |= set(self._SALIDAS_ENERGIA)
        # SAF-02 (3.ª vuelta): abrir o cerrar sin verificar detiene todo
        # movimiento automático de esa puerta (sin cierre sin reapertura)
        for n in ("1", "2"):
            if {f"abrir_puerta_{n}", f"cerrar_puerta_{n}"} & inhibidas:
                inhibidas |= {f"abrir_puerta_{n}", f"cerrar_puerta_{n}"}
        # SAF-01 (3.ª vuelta): el venteo y el alivio nunca se inhiben, aunque
        # estén pendientes (el puerto viejo puede estar dañado: sin ellos no
        # habría venteo automático ni estado seguro)
        inhibidas -= set(self._SALIDAS_VENTEO)
        setdo.inhibidas = frozenset(inhibidas)
        if inhibidas:
            logger.warning("Reasignación de E/S sin verificar: control automático sin %s",
                           ", ".join(sorted(inhibidas)))

    def alarma_asignacion_sin_verificar(self) -> None:
        """Activa (o despeja, si ya no queda ninguna) SEN-09 con las funciones
        reasignadas sin verificar. Bajo un lock propio y leyendo los
        pendientes dentro de él (TMG-12 de la re-revisión R8)."""
        with self.__dict__.setdefault("_lock_alarma_asignacion", threading.Lock()):
            self._alarma_asignacion_sin_verificar()

    def _alarma_asignacion_sin_verificar(self) -> None:
        from autoclave.core.runtime import asignacion_io as aio
        pendientes = list(getattr(self, "asignacion_pendiente", []) or [])
        if not pendientes:
            self.alarm_manager.resolver(SEN_09)
            return
        memoria = aio.en_memoria()
        partes = []
        for f in pendientes:
            tipo, nombre = aio.separar(f)
            tipo = tipo or aio.funciones().get(f, "")
            puerto = (memoria.get(tipo) or {}).get(nombre)
            partes.append(f"{f} ({aio.etiqueta(tipo, puerto)})" if puerto else f)
        texto = ", ".join(partes)
        inst = self.alarm_manager.obtener(SEN_09)
        activa = inst is not None and getattr(getattr(inst, "estado", None), "name", "") == "ACTIVA"
        if not activa or (getattr(inst, "valores", None) or {}).get("funciones") != texto:
            self.alarm_manager.activar(SEN_09, funciones=texto)

    def observar_entradas_reasignadas(self, datos: dict) -> None:
        """SAF-02 (revisión R8): una entrada digital reasignada solo se puede
        dar por verificada si se vio cambiar en su puerto nuevo (el operador
        acciona el paro, abre y cierra la puerta...). Guarda el primer valor
        visto y marca la función al ver otro distinto."""
        from autoclave.core.runtime import asignacion_io as aio
        if not isinstance(datos, dict) or not datos.get("connected"):
            return
        raw = datos.get("raw_di") or []
        vistos = self.__dict__.setdefault("_di_primer_valor", {})
        cambio = self.__dict__.setdefault("asignacion_di_cambio", set())
        memoria = aio.en_memoria()
        for f in list(getattr(self, "asignacion_pendiente", None) or []):
            if aio.funciones().get(f) != "DI" or f in cambio:
                continue
            puerto = memoria["DI"].get(aio.base(f))
            if not puerto or puerto > len(raw):
                continue
            valor = raw[puerto - 1]
            if f not in vistos:
                vistos[f] = valor
            elif valor != vistos[f]:
                cambio.add(f)
                logger.info("Reasignación de E/S: %s cambió de estado en su puerto nuevo", f)

    def iniciar_vigilancia_asignacion(self, cada_s: float = 0.5, alarma_cada: int = 10) -> None:
        """Mientras queden funciones sin verificar: observa los cambios de las
        entradas digitales reasignadas y vuelve a activar SEN-09 si se
        resolvió (p. ej. al reconocer una FALLA). El inicio de ciclo ya está
        bloqueado por la condición registrada en el AlarmManager; la alarma
        solo mantiene visible el motivo."""
        if not getattr(self, "asignacion_pendiente", None) or                 getattr(self, "_hilo_alarma_asignacion", None) is not None:
            return

        def vigilar():
            vuelta = 0
            while getattr(self, "asignacion_pendiente", None):
                try:
                    if self.units is not None:
                        self.observar_entradas_reasignadas(self.units.get_all())
                    if vuelta % alarma_cada == 0:
                        self.alarma_asignacion_sin_verificar()
                except Exception:
                    logger.exception("Vigilancia de la reasignación de E/S")
                vuelta += 1
                time.sleep(cada_s)
            try:
                self.alarma_asignacion_sin_verificar()     # la despeja (TMG-12)
            except Exception:
                logger.exception("Vigilancia de la reasignación de E/S")
        self._hilo_alarma_asignacion = threading.Thread(
            target=vigilar, name="VigilanciaReasignacionIO", daemon=True)
        self._hilo_alarma_asignacion.start()

    def iniciar_verificacion_asignacion(self, plazo_s: float = 60.0, pausa_s: float = 1.0,
                                        reloj=time.monotonic, dormir=time.sleep) -> None:
        """Tras reiniciar por una reasignación: comprueba en un hilo que la
        tarjeta envía el puerto nuevo de cada función (y, en las analógicas,
        una lectura válida), sin accionar nada, y lo registra en audit_log
        como "trama_presente" o "sin_respuesta". NO da la función por
        verificada (SAF-02/SEN-03 de la revisión R8: en DI/DO la trama siempre
        trae todos los puertos): la marca pendiente solo la quita el ingeniero
        (POST /io/assignment/verify). Plazo con time.monotonic()."""
        pendientes = list(getattr(self, "asignacion_pendiente", []) or [])
        if not pendientes or getattr(self, "_hilo_verificacion_io", None) is not None:
            return

        def verificar():
            from autoclave.core.runtime import asignacion_io as aio
            try:
                asignacion = aio.en_memoria()
                fin = reloj() + plazo_s
                resultado = {f: False for f in pendientes}
                conectado_desde = None
                while True:
                    datos = self.units.get_all() if self.units is not None else {}
                    if datos.get("connected"):
                        conectado_desde = conectado_desde if conectado_desde is not None else reloj()
                        # unas tramas después de conectar (AI/DI/DO cada 500 ms)
                        if reloj() - conectado_desde >= 2.0:
                            resultado = {f: aio.responde(f, asignacion, datos) for f in pendientes}
                            if all(resultado.values()):
                                break
                    else:
                        conectado_desde = None
                    if reloj() >= fin:
                        break
                    dormir(pausa_s)
                self._registrar_verificacion(resultado, asignacion)
            except Exception:
                logger.exception("Verificación de la reasignación de E/S")
                self.verificacion_asignacion = {"estado": "fallida",
                                                "funciones": {f: "sin_respuesta" for f in pendientes}}

        self.verificacion_asignacion = {"estado": "en_curso",
                                        "funciones": {f: "pendiente" for f in pendientes}}
        self._hilo_verificacion_io = threading.Thread(target=verificar, name="VerificacionReasignacionIO",
                                                      daemon=True)
        self._hilo_verificacion_io.start()

    def _registrar_verificacion(self, resultado: dict, asignacion: dict) -> None:
        from autoclave.core.runtime import asignacion_io as aio
        todas_ok = all(resultado.values())
        previas = (getattr(self, "verificacion_asignacion", None) or {}).get("funciones") or {}
        self.verificacion_asignacion = {
            "estado": "trama_presente" if todas_ok else "fallida",
            "funciones": {f: ("verificada" if previas.get(f) == "verificada"
                              else "trama_presente" if ok else "sin_respuesta")
                          for f, ok in resultado.items()}}
        for funcion, ok in sorted(resultado.items()):
            tipo, nombre = aio.separar(funcion)
            tipo = tipo or next((t for t in aio.TIPOS if nombre in asignacion.get(t, {})), "")
            puerto = (asignacion.get(tipo) or {}).get(nombre)
            try:
                self.db.registrar_auditoria(
                    "reasignacion_io_verificada", usuario="sistema", entidad=funcion,
                    valor_nuevo=aio.etiqueta(tipo, puerto) if puerto else None,
                    detalle={"resultado": "trama_presente" if ok else "sin_respuesta", "tipo": tipo,
                             "metodo": "automatico"})
            except Exception:
                logger.exception("No se pudo registrar la verificación de %s en audit_log", funcion)
        if todas_ok:
            logger.info("Reasignación de E/S: la tarjeta envía el puerto nuevo de %s; falta la "
                        "verificación del ingeniero", ", ".join(sorted(resultado)))
        else:
            logger.error("Reasignación de E/S: sin respuesta en %s",
                         ", ".join(f for f, ok in sorted(resultado.items()) if not ok))

    # ── 5. verificando_calibracion ───────────────────────────────────────────

    def verificar_calibracion(self) -> None:
        """Sin valores por defecto silenciosos (§4.5): load_config() aceptaría
        un YAML vacío con los valores de AppConfig; aquí es un fallo."""
        ruta = calibration_path()
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                datos = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            raise ErrorArranque(secuencia.ARR_CALIBRACION, f"{ruta}: {e}") from e
        if not datos:
            raise ErrorArranque(secuencia.ARR_CALIBRACION, f"{ruta}: archivo vacío")
        try:
            self.units = Units(ruta)
        except Exception as e:
            raise ErrorArranque(secuencia.ARR_CALIBRACION, f"{ruta}: {e}") from e

    # ── 6. abriendo_base_datos ───────────────────────────────────────────────

    def abrir_base_datos(self, intentos: int = secuencia.INTENTOS_BD) -> str | None:
        """Degradable: agotados los intentos, el backend sigue sin BD."""
        for intento in range(1, intentos + 1):
            try:
                self.db = DbManager()
                self.calibration_audit = SensorCalibrationAuditDB()
                self._numeracion_y_ciclos_interrumpidos()
                # O2a: valores vigentes de los parámetros del equipo (system_params)
                if self.config_manager is not None:
                    self.config_manager.vincular_bd(self.db)
                return None
            except BdBloqueadaError as e:
                logger.critical("%s", e)
                break
            except Exception as e:
                if es_base_corrupta(e):
                    # §7.7: se aparta (nunca se borra) y no se reintenta
                    try:
                        destino = apartar_base_corrupta(DB_DEFAULT)
                        logger.critical("Base de datos corrupta apartada en %s", destino)
                    except Exception:
                        logger.exception("No se pudo apartar la base de datos corrupta")
                    break
                logger.exception("Base de datos no disponible (intento %d de %d)", intento, intentos)
        # T8 (§7, D-03): el equipo opera sin base; los ciclos van al respaldo
        # JSONL y al ticket, con confirmación explícita en cada inicio
        self.db = BdNoDisponible()
        self.calibration_audit = BdNoDisponible()
        self.sin_base_de_datos = True
        self.contador_ciclos.sincronizar(None)
        self._marca_interrumpido = self.contador_ciclos.en_curso()
        self.alarm_manager.activar(OPERANDO_SIN_BD)
        return secuencia.ARR_SIN_BD

    # ── 7. conectando_modulos_es ─────────────────────────────────────────────

    def construir_control(self, al_cancelar_prueba=None) -> None:
        """Abre el serial, construye puertas, registro de ciclo y ControlLoop,
        y arranca el loop. `al_cancelar_prueba` se registra antes de start(),
        para no perder un paro que llegue en el primer tick."""
        self.serial = build_serial(self.units, al_conectar=self._al_conectar_tarjeta)
        self.setdo = SetOutput(self.serial, self.estado, profile=self.profile)
        self.inhibir_salidas_sin_verificar()     # R8: SAF-02 de la re-revisión

        self.doors = [
            create_door(
                config=self.config_manager,
                io={
                    "cfg":           cfg,
                    "estado":        self.estado,
                    "setdo":         self.setdo,
                    "alarm_manager": self.alarm_manager,
                }
            )
            for cfg in build_doors_cfg(self.profile)
        ]

        # Servicio de dominio (ÚNICO)
        self.servicio_puertas = ServicioPuertas(
            doors=self.doors,
            estado=self.estado,
            profile=self.profile,
            logger=logger,
            config = self.config_manager,
            programas=self.programas_para_seguridad,
            temp_max_ciclo=self.temp_max_tras_ciclo,
            estado_seguro_activo=self.estado_seguro_activo,
        )

        # Data logger (SQLite) + impresión en tiempo real
        self.realtime_printer = RealtimePrinter()
        self.cycle_logger = CycleLogger(
            db            = self.db,
            estado        = self.estado,
            config        = self.config_manager,
            profile       = self.profile,
            cycle_manager = self.cycle_manager,
            printer       = self.realtime_printer,
            contador      = self.contador_ciclos,
            respaldo      = self.respaldo_ciclos,
            sin_base_de_datos = self.sin_base_de_datos,
            # TMG-01 de T8: la base del ciclo se escribe fuera del hilo del lazo
            ejecutar_bd   = EscritorBD(),
            # S3d: el respaldo (con su fsync) en su propio hilo FIFO, sin límite
            ejecutar_respaldo = EscritorBD(maximo=0, nombre="CycleLoggerRespaldo"),
        )
        # S3c (tanda 2): una base que falla en caliente activa OPERANDO_SIN_BD
        self.cycle_logger.al_fallar_bd = self.bd_fallo_en_caliente
        # Historial persistente de alarmas (spec 2026-10-06 §6). El ciclo en
        # curso se lee al aparecer cada alarma.
        self.historial_alarmas = HistorialAlarmas(
            self.db, self.alarm_manager,
            ciclo_actual=lambda: self.cycle_logger.ciclo_id,
        )

        self.control_loop = ControlLoop(
            units=self.units,
            door_service=self.servicio_puertas,
            doors=self.doors,
            estado=self.estado,
            link=self.serial,
            set_do=self.setdo,
            alarm_manager=self.alarm_manager,
            cycle_manager=self.cycle_manager,
            config_manager=self.config_manager,
            cycle_logger=self.cycle_logger,
            cap=self.cap,
            realtime_printer=self.realtime_printer,
            profile=self.profile,
        )
        if al_cancelar_prueba is not None:
            self.control_loop.al_cancelar_modo_prueba(al_cancelar_prueba)
        # R8: asignación de E/S vigente ilegible o inválida: bloqueado hasta
        # restaurar la de fábrica (Opciones avanzadas) y reiniciar
        if getattr(self, "motivo_asignacion", ""):
            self.control_loop.bloquear_por_configuracion(self.motivo_asignacion)
        # Fin de ciclo §15: paro, confirmación y estado seguro en audit_log
        self.control_loop.al_evento_seguridad = self._auditar_evento_seguridad
        # T2-b (tanda 7): DESPEJAR de COM-02/03 exige el enlace de vuelta en "ok"
        self.alarm_manager.enlace_ok = self._enlace_confirmado_ok
        # E4 (D-08; SAF-01 de T6): se decide por el estado físico, no por la
        # base. En CADA arranque, con el primer dato vigente, si la cámara no
        # es segura el equipo entra en estado seguro con confirmación. El
        # programa: el del ciclo interrumpido, si no el del último ciclo
        # registrado y, si no, uno conservador (líquido, solo la lenta).
        self.control_loop.recuperar_ciclo_interrumpido(self._programa_para_arranque())
        self.control_loop.start()
        self.iniciar_verificacion_asignacion()   # R8: solo tras una reasignación
        self.iniciar_vigilancia_asignacion()
        self.iniciar_vigilancia_mantenimiento()
        self.iniciar_vigilancia_impresora()
        self.registrar_presentacion_tickets()

    def _al_conectar_tarjeta(self, tarjeta: dict) -> None:
        """Cada handshake completo con la tarjeta de E/S: registro en
        audit_log y comparación con el board_id del perfil (FW-D7). Una
        tarjeta distinta o sin registrar es solo advertencia en la versión
        1.0 (no bloquea). Corre en el hilo de supervisión del enlace."""
        emparejada = tarjeta_emparejada(getattr(self, "profile", None), tarjeta.get("id"))
        board_id = getattr(getattr(self, "profile", None), "board_id", None)
        if not emparejada:
            logger.warning(
                "Tarjeta de E/S %s no emparejada con el equipo (board_id del perfil: %s). "
                "Registrarla con tools/emparejar_tarjeta.py si es la correcta.",
                tarjeta.get("id"), board_id or "sin registrar")
        db = getattr(self, "db", None)
        if db is None:
            return
        try:
            db.registrar_auditoria(
                "tarjeta_conectada",
                usuario="sistema",
                entidad="tarjeta_es",
                valor_nuevo=dict(tarjeta),
                detalle={"emparejada": emparejada, "board_id": board_id},
            )
        except Exception:
            logger.exception("No se pudo registrar la conexión de la tarjeta en audit_log")

    def programa_para_sensores(self):
        """Programa del sensor Principal (tanda §1.1). Antes de construir el
        ControlLoop, el seleccionado; sin ninguno, None (= temp_camara)."""
        loop = getattr(self, "control_loop", None)
        if loop is not None:
            return loop.programa_para_sensores()
        cm = getattr(self, "cycle_manager", None)
        return getattr(cm, "selected_cycle", None)

    def _enlace_confirmado_ok(self) -> bool:
        """T2-b: el enlace con la tarjeta volvió a "ok" (3 tramas vigentes
        seguidas). Sin lazo de control, False (falla cerrada)."""
        return getattr(getattr(self, "control_loop", None), "enlace_confirmado_ok", False) is True

    def _auditar_evento_seguridad(self, evento: str, detalle: dict) -> None:
        """Lo llama el tick del ControlLoop: la escritura en SQLite va en un
        hilo propio para no detener el lazo (eventos poco frecuentes)."""
        def escribir():
            try:
                self.db.registrar_auditoria(evento, usuario="sistema", entidad="estado_seguro",
                                            detalle=detalle or None)
            except Exception:
                logger.exception("No se pudo registrar %s en audit_log", evento)
        threading.Thread(target=escribir, name="AuditoriaEstadoSeguro", daemon=True).start()

    @property
    def contador_ciclos(self) -> ContadorCiclos:
        """Contador persistente de ciclos (E4, §7.5): data/ciclo_contador.json."""
        if getattr(self, "_contador_ciclos", None) is None:
            self._contador_ciclos = ContadorCiclos(app_root() / "data" / "ciclo_contador.json")
        return self._contador_ciclos

    @property
    def mantenimiento(self):
        """Servicio de próximo mantenimiento (M1, tanda 3). Solo informa:
        nunca interviene en un ciclo."""
        with _LOCK_MANTENIMIENTO:     # una sola instancia (hilo de vigilancia y HTTP)
            if getattr(self, "_mantenimiento", None) is None:
                from autoclave.core.runtime.servicio_mantenimiento import ServicioMantenimiento
                self._mantenimiento = ServicioMantenimiento(
                    app_root() / "data" / "mantenimiento.json",
                    db=lambda: self.db,
                    instalado_en=lambda: getattr(self.profile, "created_at", None),
                    contador_ciclos=self.contador_ciclos,
                    alarm_manager=self.alarm_manager)
            return self._mantenimiento

    @property
    def config_impresora(self):
        """Bandera `habilitada` de la impresora (B5, tanda 4): data/impresora.json."""
        with _LOCK_MANTENIMIENTO:
            if getattr(self, "_config_impresora", None) is None:
                from autoclave.core.runtime.vigilancia_impresora import ConfigImpresora
                self._config_impresora = ConfigImpresora(app_root() / "data" / "impresora.json")
            return self._config_impresora

    @property
    def config_correo_equipo(self):
        """O2g (tanda 6): destinatarios e interruptor del correo, data/correo_equipo.json."""
        with _LOCK_MANTENIMIENTO:
            if getattr(self, "_config_correo_equipo", None) is None:
                from autoclave.core.runtime.config_correo_equipo import ConfigCorreoEquipo
                from autoclave.ui_qml.exportacion import config_correo
                self._config_correo_equipo = ConfigCorreoEquipo(
                    config_correo.RUTA_EQUIPO,
                    semilla=lambda: config_correo.cargar(contrasena=lambda r: None,
                                                         ruta_equipo=os.devnull).destinos)
            return self._config_correo_equipo

    @property
    def estado_red(self):
        """O2g (tanda 6): estado de red en solo lectura (cache de 10 s)."""
        with _LOCK_MANTENIMIENTO:
            if getattr(self, "_estado_red", None) is None:
                from autoclave.core.runtime.estado_red import EstadoRed
                self._estado_red = EstadoRed()
            return self._estado_red

    @property
    def config_idioma(self):
        """I1 (tanda 5): idioma de la interfaz y de las salidas, data/idioma.json."""
        with _LOCK_MANTENIMIENTO:
            if getattr(self, "_config_idioma", None) is None:
                from autoclave.core.runtime.config_idioma import ConfigIdioma
                self._config_idioma = ConfigIdioma(app_root() / "data" / "idioma.json")
            return self._config_idioma

    @property
    def config_unidades(self):
        """U1 (tanda 5): unidades de presentación, data/unidades.json."""
        with _LOCK_MANTENIMIENTO:
            if getattr(self, "_config_unidades", None) is None:
                from autoclave.core.runtime.unidades import ConfigUnidades
                self._config_unidades = ConfigUnidades(app_root() / "data" / "unidades.json")
            return self._config_unidades

    def registrar_presentacion_tickets(self) -> None:
        """I3 (tanda 5): el ticket usa el idioma y las unidades vigentes al
        generarlo. P_atm fuera de 50-110 kPa cuenta como ausente."""
        from autoclave.core.runtime.unidades import p_atm_valida
        from autoclave.services.domain.logging import ticket_formatter as tf

        def proveedor():
            unidades = self.config_unidades.leer()
            try:
                p_atm = p_atm_valida(self.config_manager.get("presion_admosferica"))
            except Exception:
                p_atm = None
            return tf.Presentacion(self.config_idioma.leer(), unidades["temperatura"],
                                   unidades["presion"], p_atm)
        tf.fijar_proveedor(proveedor)

    def iniciar_vigilancia_impresora(self) -> None:
        """B5 (tanda 4): verifica una vez, en un hilo con plazo de 5 s, que la
        impresora esté presente (solo si está habilitada) y avisa sin bloquear.
        Idempotente; un fallo se registra y no afecta nada más."""
        if getattr(self, "_vigilancia_impresora", None) is not None:
            return
        try:
            from autoclave.core.runtime.vigilancia_impresora import VigilanciaImpresora
            self._vigilancia_impresora = VigilanciaImpresora(self.config_impresora,
                                                             self.alarm_manager)
            self._vigilancia_impresora.iniciar()
        except Exception:
            logger.exception("No se pudo iniciar la verificación de la impresora")

    def aplicar_config_impresora(self) -> None:
        """P2 (tanda 5): la bandera cambió; el aviso se ajusta sin reiniciar."""
        vig = getattr(self, "_vigilancia_impresora", None)
        if vig is None:
            self.iniciar_vigilancia_impresora()
        else:
            vig.aplicar_configuracion()

    def iniciar_vigilancia_mantenimiento(self, cada_s: float = 600.0) -> None:
        """Evalúa el aviso de mantenimiento vencido al arrancar y cada 10 min
        (hilo daemon; un fallo se registra y no afecta nada más)."""
        if getattr(self, "_hilo_mantenimiento", None) is not None:
            return                       # idempotente
        self.mantenimiento               # instancia antes de lanzar el hilo
        try:
            self.mantenimiento.migrar_valores_provisionales()   # B3 (tanda 4)
        except Exception:
            logger.exception("Migración de intervalos de mantenimiento")

        def vigilar():
            while True:
                try:
                    self.mantenimiento.evaluar_alarma()
                except Exception:
                    logger.exception("Vigilancia de mantenimiento")
                time.sleep(cada_s)
        self._hilo_mantenimiento = threading.Thread(
            target=vigilar, name="VigilanciaMantenimiento", daemon=True)
        self._hilo_mantenimiento.start()

    @property
    def respaldo_ciclos(self) -> RespaldoCiclos:
        """Respaldo JSONL por ciclo (T8, §7.4): data/respaldo_ciclos/."""
        if getattr(self, "_respaldo_ciclos", None) is None:
            self._respaldo_ciclos = RespaldoCiclos(app_root() / "data" / "respaldo_ciclos",
                                                   al_fallar=self._respaldo_fallido)
        return self._respaldo_ciclos

    def bd_fallo_en_caliente(self, motivo: str) -> None:
        """S3c (tanda 2, T8 SAF-03): la base de datos falló con el equipo en
        marcha. Se pasa al modo sin base como si hubiera arrancado así: alarma
        no bloqueante OPERANDO_SIN_BD, el siguiente ciclo pide confirmación y
        lleva la leyenda "SIN OPERADOR / SIN BD", y calibración, parámetros y
        altas quedan bloqueados. El ciclo en curso NO se detiene: sigue en el
        respaldo JSONL y en el ticket. Idempotente; lo llama el hilo de
        escritura de la base."""
        with self._lock_sin_bd:
            if self.sin_base_de_datos:
                return
            self.sin_base_de_datos = True
        logger.critical("La base de datos falló en caliente (%s): se opera sin base", motivo)
        if getattr(self, "cycle_logger", None) is not None:
            self.cycle_logger.sin_base_de_datos = True
        # Como si hubiera arrancado sin base: los endpoints que usan context.db
        # (altas, historial, reportes...) responden 503 en vez de fallar al azar.
        # La referencia real se conserva para cerrarla al apagar; el logger y el
        # historial de alarmas mantienen la suya.
        self.db_real = self.db
        self.db = BdNoDisponible()
        self.calibration_audit = BdNoDisponible()
        try:
            self.alarm_manager.activar(OPERANDO_SIN_BD)
        except Exception:
            logger.exception("No se pudo activar OPERANDO_SIN_BD")

    def _respaldo_fallido(self, error: str) -> None:
        """SAF-01 de T8: alarma SIS-03 (aviso, despeje manual)."""
        try:
            self.alarm_manager.activar(SIS_03, error=error)
        except Exception:
            logger.exception("No se pudo activar la alarma de respaldo")

    def _reimportar_respaldos(self) -> None:
        """T8 (§7.4): ciclos del respaldo que no están en la base (ciclos sin
        base de datos o con la base caída a mitad de ciclo) se reimportan;
        idempotente por uuid."""
        try:
            r = reimportar(self.respaldo_ciclos, self.db, MOTIVO_INTERRUMPIDO)
        except Exception:
            logger.exception("No se pudieron reimportar los respaldos de ciclos")
            return
        for clave, evento in (("importados", "ciclo_reimportado"),
                              ("completados", "ciclo_completado_desde_respaldo")):
            for uuid_ciclo in r.get(clave, []):
                logger.warning("Ciclo %s: %s", uuid_ciclo, evento)
                try:
                    self.db.registrar_auditoria(evento, usuario="sistema",
                                                entidad=f"ciclo/{uuid_ciclo}")
                except Exception:
                    logger.exception("No se pudo auditar %s", evento)
        for nombre in r["errores"]:
            logger.error("Respaldo de ciclo %s no reimportado; se reintenta al arrancar", nombre)

    def _numeracion_y_ciclos_interrumpidos(self) -> None:
        """E4 (D-08, PF-17): sincroniza el contador con la base y cierra como
        INTERRUMPIDO todo ciclo sin fecha de fin. El último se recupera al
        construir el control: si la cámara no es segura, arranca en estado
        seguro con confirmación (nunca se reanuda el ciclo)."""
        try:
            self.contador_ciclos.sincronizar(self.db.max_numero_ciclo())
        except Exception:
            logger.exception("No se pudo sincronizar el contador de ciclos")
        # TMG-03 de T6: marca persistente, independiente de la base
        self._marca_interrumpido = self.contador_ciclos.en_curso()
        self._reimportar_respaldos()
        try:
            cerrados = self.db.cerrar_ciclos_interrumpidos(MOTIVO_INTERRUMPIDO)
        except Exception:
            logger.exception("No se pudieron cerrar los ciclos interrumpidos")
            return
        for fila in cerrados:
            logger.error("Ciclo #%s (id %s) interrumpido: cerrado al arrancar",
                         fila.get("numero_ciclo"), fila.get("id"))
            try:
                self.db.registrar_auditoria("ciclo_interrumpido", usuario="sistema",
                                            entidad=f"ciclo/{fila.get('id')}",
                                            detalle={"numero": fila.get("numero_ciclo"),
                                                     "programa": fila.get("tipo_ciclo")})
            except Exception:
                logger.exception("No se pudo auditar el ciclo interrumpido")
        self._ciclo_interrumpido = cerrados[-1] if cerrados else None

    def _programa_del_ciclo_interrumpido(self):
        """Reconstruye el programa con el que corría el ciclo interrumpido:
        la instantánea (v3) o, en filas anteriores, el programa cargado con
        la asignación de sensores registrada (v2)."""
        fila = getattr(self, "_ciclo_interrumpido", None)
        marca = getattr(self, "_marca_interrumpido", None)
        if not fila and marca:
            # Sin fila en la base (base caída o bloqueada): la marca del contador
            if marca.get("programa"):
                try:
                    return Cycle.desde_instantanea(marca["programa"])
                except Exception:
                    logger.exception("Instantánea de la marca de ciclo ilegible")
            return _programa_desconocido()
        if not fila:
            return None
        try:
            if fila.get("programa_json"):
                return Cycle.desde_instantanea(json.loads(fila["programa_json"]))
            base = self.cycle_manager.cycles.get(fila.get("tipo_ciclo"))
            if base is None:
                return None
            programa = base.copia()
            if fila.get("asignacion_sensores"):
                programa.sensores, _ = interpretar_asignacion(json.loads(fila["asignacion_sensores"]))
            return programa
        except Exception:
            logger.exception("No se pudo reconstruir el programa del ciclo interrumpido")
            return None

    def _programa_para_arranque(self):
        programa = self._programa_del_ciclo_interrumpido()
        if programa is None:
            try:
                recientes = self.db.get_ciclos_recientes(1)
                fila = dict(recientes[0]) if recientes else None
                if fila and fila.get("programa_json"):
                    programa = Cycle.desde_instantanea(json.loads(fila["programa_json"]))
            except Exception:
                logger.exception("No se pudo leer el último ciclo registrado")
        if programa is None:
            return _programa_desconocido()
        # SAF-05 de T6: sin tipo de carga registrado, se recupera como líquido
        if programa.get_param("globals", "tipo_carga") is None:
            programa.parameters.setdefault("globals", {})["tipo_carga"] = {"value": "liquido"}
        return programa

    def programas_para_seguridad(self) -> list:
        """Programas cuyos Principales deciden apertura y cámara segura
        (SAF-01 de T3). Antes de construir el ControlLoop, el seleccionado."""
        loop = getattr(self, "control_loop", None)
        if loop is not None:
            return loop.programas_para_seguridad()
        cm = getattr(self, "cycle_manager", None)
        seleccionado = getattr(cm, "selected_cycle", None)
        return [seleccionado] if seleccionado is not None else []

    def estado_seguro_activo(self) -> bool:
        loop = getattr(self, "control_loop", None)
        return bool(loop is not None and loop.estado_seguro.activo)

    def temp_max_tras_ciclo(self):
        loop = getattr(self, "control_loop", None)
        return loop.temp_max_tras_ciclo() if loop is not None else None

    def es_conectada(self) -> bool:
        return self.serial is not None and self.serial.is_connected()

    def _validar_configuracion(self) -> str | None:
        """Configuración inválida (valores fuera de rango): alarma
        CONFIGURACION_INVALIDA y devuelve el motivo. En el arranque por etapas
        es un fallo bloqueante de "cargando_configuracion": la secuencia se
        detiene antes de construir el control. Si el ControlLoop ya existe,
        además se bloquea (sin puertas ni máquina de estados, todo apagado)."""
        errores = errores_config_arranque(self.config_manager)
        if not errores:
            return None
        motivo = "; ".join(errores)
        self.alarm_manager.activar(CONFIGURACION_INVALIDA, motivo=motivo)
        control_loop = getattr(self, "control_loop", None)
        if control_loop is not None:
            control_loop.bloquear_por_configuracion(motivo)
        return motivo

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
from autoclave.state_machine.alarms.catalogo import CONFIGURACION_INVALIDA, OPERANDO_SIN_BD, SIS_03
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

import json
import logging
import threading

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
        if self.cycle_manager.errores_carga:
            logger.warning("Ciclos omitidos por JSON corrupto: %s",
                           ", ".join(self.cycle_manager.errores_carga))
            return secuencia.ARR_CICLO_CORRUPTO
        return None

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
        # Fin de ciclo §15: paro, confirmación y estado seguro en audit_log
        self.control_loop.al_evento_seguridad = self._auditar_evento_seguridad
        # E4 (D-08; SAF-01 de T6): se decide por el estado físico, no por la
        # base. En CADA arranque, con el primer dato vigente, si la cámara no
        # es segura el equipo entra en estado seguro con confirmación. El
        # programa: el del ciclo interrumpido, si no el del último ciclo
        # registrado y, si no, uno conservador (líquido, solo la lenta).
        self.control_loop.recuperar_ciclo_interrumpido(self._programa_para_arranque())
        self.control_loop.start()

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

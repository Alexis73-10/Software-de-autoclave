# autoclave/backend/context.py

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.services.domain.puertas.ser_puertas import ServicioPuertas
from autoclave.installation.bootstrap import get_installation_profile
from autoclave.installation.clock_guard import ClockTamperedError
from autoclave.installation.equipment import get_capabilities
from autoclave.installation.profile import entradas_no_monitoreadas, sondas_no_vigiladas
from autoclave.devices.factory.factory import build_doors_cfg, build_serial
from autoclave.devices.puertas.advanced_door import AdvancedDoor
from autoclave.devices.puertas.door_factory import create_door
from autoclave.devices.io.set_io import SetOutput
from autoclave.hal.measures.units import Units
from autoclave.services.domain.loop.control_loop import ControlLoop
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.state_machine.alarms.alarm_types import AlarmType
from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.core.managers.config_manager import ConfigManager
from autoclave.core.managers.validacion_config import errores_config_arranque
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.cycle_logger import CycleLogger
from autoclave.services.domain.logging.sensor_calibration_audit import SensorCalibrationAuditDB
from autoclave.devices.printer.realtime_printer import RealtimePrinter
from autoclave.backend.arranque import secuencia
from autoclave.backend.arranque.secuencia import ErrorArranque
from autoclave.backend.arranque.sin_bd import BdNoDisponible
from autoclave.utils.paths import calibration_path

import logging

import yaml

logger = logging.getLogger(__name__)


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
                return None
            except Exception:
                logger.exception("Base de datos no disponible (intento %d de %d)", intento, intentos)
        # PROVISIONAL hasta el modo sin BD (§7): sin registro no se inicia ciclo
        self.db = BdNoDisponible()
        self.calibration_audit = BdNoDisponible()
        self.sin_base_de_datos = True
        self.alarm_manager.report(Alarm(
            alarm_id="OPERANDO_SIN_BD",
            alarm_type=AlarmType.FALLA,
            source_state="ARRANQUE",
            description="Base de datos no disponible: el inicio de ciclo queda bloqueado",
            recoverable=False,
            blocks_operation=True,
        ))
        return secuencia.ARR_SIN_BD

    # ── 7. conectando_modulos_es ─────────────────────────────────────────────

    def construir_control(self, al_cancelar_prueba=None) -> None:
        """Abre el serial, construye puertas, registro de ciclo y ControlLoop,
        y arranca el loop. `al_cancelar_prueba` se registra antes de start(),
        para no perder un paro que llegue en el primer tick."""
        self.serial = build_serial(self.units)
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
            config = self.config_manager
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
        self.control_loop.start()

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
        self.alarm_manager.report(Alarm(
            alarm_id="CONFIGURACION_INVALIDA",
            alarm_type=AlarmType.FALLA,
            source_state="ARRANQUE",
            description=f"Configuración inválida: {motivo}",
            recoverable=False,
            blocks_operation=True,
        ))
        control_loop = getattr(self, "control_loop", None)
        if control_loop is not None:
            control_loop.bloquear_por_configuracion(motivo)
        return motivo

# autoclave/backend/context.py

from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.services.domain.puertas.ser_puertas import ServicioPuertas
from autoclave.installation.bootstrap import get_installation_profile
from autoclave.installation.equipment import get_capabilities
from autoclave.devices.factory.factory import build_hardware
from autoclave.devices.puertas.advanced_door import AdvancedDoor
from autoclave.devices.puertas.door_factory import create_door
from autoclave.devices.io.set_io import SetOutput
from autoclave.services.domain.loop.control_loop import ControlLoop
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.core.managers.config_manager import ConfigManager
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.cycle_logger import CycleLogger
from autoclave.services.domain.logging.sensor_calibration_audit import SensorCalibrationAuditDB
from autoclave.devices.printer.realtime_printer import RealtimePrinter
from autoclave.config.preferences import load_preferences, save_preferences
from autoclave.devices.audio.manifest import load_manifest, ManifestError
from autoclave.devices.audio.announcer import Announcer
from autoclave.services.domain.audio.announcer_observer import AnnouncerObserver
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType
from autoclave.utils.resources import resource_path

import logging

logger = logging.getLogger(__name__)


class BackendContext:
    def __init__(self):
        self.estado = EstadoAutoclave()
        self.alarm_manager = AlarmManager(self.estado)


        self.cycle_manager = CycleManager()
        self.config_manager = ConfigManager()
        self.cycle_manager.load_all_cycles()
        self.config_manager.load_config()
        logger.info(f"Ciclos cargados: {list(self.cycle_manager.cycles.keys())}")
        self.cycle_manager.set_default_cycle("bowe_dick")


        self.profile = get_installation_profile()
        if self.profile is None:
            raise RuntimeError("Backend sin InstallationProfile")
        cap = get_capabilities(self.profile.equipment_class)


        # Hardware real
        self.units, self.serial, doors_cfg = build_hardware(self.profile)

        self.setdo = SetOutput(self.serial, self.estado)

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
            for cfg in doors_cfg
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
        self.db               = DbManager()
        self.calibration_audit = SensorCalibrationAuditDB()
        self.realtime_printer = RealtimePrinter()
        self.cycle_logger = CycleLogger(
            db            = self.db,
            estado        = self.estado,
            config        = self.config_manager,
            profile       = self.profile,
            cycle_manager = self.cycle_manager,
            printer       = self.realtime_printer,
        )

        # Anuncios por voz — deshabilitado en caliente si el manifiesto no
        # carga (archivo faltante/corrupto); el equipo sigue operando (D-14).
        self.audio_preferences = load_preferences()
        try:
            eventos_audio = load_manifest(resource_path("autoclave/assets/audio/manifest.json"))
            self._audio_disponible = True
        except ManifestError as exc:
            logger.warning("Anuncios por voz deshabilitados: %s", exc)
            eventos_audio = {}
            self._audio_disponible = False

        def _reportar_audio_no_disponible():
            self._audio_disponible = False
            self.alarm_manager.report(Alarm(
                alarm_id="AUDIO_NO_DISPONIBLE",
                alarm_type=AlarmType.ALERTA,
                source_state="ANNOUNCER",
                description="Subsistema de anuncios por voz no disponible.",
                recoverable=True,
                blocks_operation=False,
            ))

        if not self._audio_disponible:
            _reportar_audio_no_disponible()

        self.announcer = Announcer(
            eventos=eventos_audio,
            get_volume=lambda: self.audio_preferences["audio"]["volume"],
            get_enabled=lambda: self.audio_preferences["audio"]["enabled"] and self._audio_disponible,
            on_fallo_persistente=_reportar_audio_no_disponible,
        )
        self.announcer.start()
        announcer_observer = AnnouncerObserver(self.announcer)

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
            cap=cap,
            realtime_printer=self.realtime_printer,
            announcer_observer=announcer_observer,
        )
        self.control_loop.start()
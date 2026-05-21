# autoclave/backend/context.py

from autoclave.core.status import EstadoAutoclave
from autoclave.services.domain.puertas.ser_puertas import ServicioPuertas
from autoclave.installation.bootstrap import get_installation_profile
from autoclave.devices.factory.factory import build_hardware
from autoclave.devices.puertas.advanced_door import AdvancedDoor
from autoclave.devices.puertas.door_factory import create_door
from autoclave.devices.io.set_io import SetOutput
from autoclave.services.domain.loop.control_loop import ControlLoop
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
from autoclave.core.cycle_manager import CycleManager
from autoclave.core.config_manager import ConfigManager
from autoclave.services.domain.logging.db_manager import DbManager
from autoclave.services.domain.logging.cycle_logger import CycleLogger

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


        # Hardware real
        self.units, self.serial, doors_cfg = build_hardware()

        self.setdo = SetOutput(self.serial, self.estado)

        self.doors = [
            create_door(
                config=self.config_manager,
                io={
                    "cfg": cfg,
                    "estado": self.estado,
                    "setdo": self.setdo,
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

        # Data logger (SQLite)
        self.db          = DbManager()
        self.cycle_logger = CycleLogger(
            db            = self.db,
            estado        = self.estado,
            config        = self.config_manager,
            profile       = self.profile,
            cycle_manager = self.cycle_manager,
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
        )
        self.control_loop.start()
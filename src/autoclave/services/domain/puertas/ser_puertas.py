#empezaremos con la logica de automatizacion de puertas
#este modulo se encargara de coordinar y decidir cuando actuar sobre las puertas
#Ejemplo de responsabilidades:
#- abrir las puertas cuando la UI lo solicite
#- registrar eventos de apertura/cierre
#- verificar el estado de las puertas
#- manejar errores relacionados con las puertas
# esto evita que la UI controle hadware directamente, mejorando la modularidad
#rol: coordinador y guardian de reglas
#- recibe solicitudes de apertura/cierre desde la UI
#- valida si la accion es permitida segun el estado actual
#- llama a la puerta
#- registra eventos y errores
#- notifica a la UI sobre el resultado de las acciones
#- maneja politicas (seguridad, permisos, secuencias)
#no controla hardware directamente, delega en el modulo de puertas
#vive en el nivel de servicio, no en el nivel de dispositivo

import logging
from autoclave.devices.puertas.advanced_door import DoorState
from .permissions import PERMISSIONS
from autoclave.state_machine.machine.parametros_gobales import ParametrosGlobales

logger = logging.getLogger(__name__)


class Rules:
    TEMP_MAX_APERTURA = 120.0        # °C


class ServicioPuertas:

    def __init__(self, doors, estado, profile, config, logger=logger, ):
        self.config = config
        self.doors = {d.name: d for d in doors}
        self.estado = estado
        self.profile = profile
        self.logger = logger
        self._last_states = {name: None for name in self.doors}

        # parámetros fijos de configuración (no cambian en runtime)
        self.temp_max  = self.config.get("temp_max_apertura")
        self.press_atm = self.config.get("presion_admosferica")
        self.rango_atm = self.config.get("rango_presion_atm")

    # ── lectura en vivo de sensores ──────────────────────────────────────────
    @property
    def pres(self):
        return self.estado.sensores_pres.get("pres_camara")

    @property
    def temp(self):
        return self.estado.sensores_temp.get("temp_camara")


    # ============================
    # API HACIA LA INTERFAZ
    # ============================

    def request_open(self, door_name):

        if door_name not in self.doors:
            self.logger.error(f"Puerta desconocida: {door_name}")
            return False
        
        if not self._can_open_physical(door_name):
            self.logger.warning(f"Apertura denegada: puerta {door_name}")
            return False

        self.doors[door_name].cmd_abrir()
        self.logger.info(f"Comando abrir enviado a puerta {door_name}")
        return True

    def request_close(self, door_name):
        if door_name not in self.doors:
            self.logger.error(f"Puerta desconocida: {door_name}")
            return False

        if not self._can_close_physical(door_name):
            self.logger.warning(f"Cierre denegado: puerta {door_name}")
            return False

        self.doors[door_name].cmd_cerrar()
        self.logger.info(f"Comando cerrar enviado a puerta {door_name}")
        return True

    def get_status(self, door_name=None):
        if door_name is None:
            return {
                name: self.estado.get_door_state(name).name
                for name in self.doors
            }
        return self.estado.get_door_state(door_name).name

    # ============================
    # REGLAS Y POLÍTICAS
    # ============================
    def can_open(self, door_name):
        if not self.can_open_from_context(door_name):
            self.logger.warning(
                f"Apertura no permitida desde puerta {self.profile.door_id}"
            )
            return False

        return self._can_open_physical(door_name)

    def can_close(self, door_name):
        if not self.can_close_from_context(door_name):
            self.logger.warning(
                f"Cierre no permitido desde puerta {self.profile.door_id}"
            )
            return False

        return self._can_close_physical(door_name)
    
    def can_open_from_context(self, door_name) -> bool:
    # ¿es mi puerta?
        if door_name != self.profile.door_id:
            return self.can("open_other_door")

        return self.can("open_own_door")


    def can_close_from_context(self, door_name) -> bool:
        # normalmente cerrar es menos restrictivo,
        # pero dejamos el hook por consistencia
        if door_name != self.profile.door_id:
            return self.can("open_other_door")

        return True


    def _can_open_physical(self, door_name):
        pres     = self.pres
        temp     = self.temp
        atm      = self.press_atm
        rango    = self.rango_atm
        temp_max = self.temp_max

        # si los parámetros de config no están disponibles, permitir (modo degradado)
        if atm is not None and rango is not None and pres is not None:
            if pres > atm + rango:
                self.logger.warning("No se puede abrir: sobrepresión en cámara (%.1f kPa)", pres)
                return False
            if pres < atm - rango:
                self.logger.warning("No se puede abrir: cámara en vacío (%.1f kPa)", pres)
                return False
        else:
            self.logger.debug("_can_open_physical: sensores de presión no disponibles, omitiendo verificación")

        if temp_max is not None and temp is not None:
            if temp > temp_max:
                self.logger.warning("No se puede abrir: temperatura alta (%.1f °C)", temp)
                return False
        else:
            self.logger.debug("_can_open_physical: sensor de temperatura no disponible, omitiendo verificación")

        for name in self.doors:
            if name != door_name:
                if self.estado.get_door_state(name) != DoorState.CERRADO:
                    self.logger.warning("No se puede abrir: otra puerta no cerrada")
                    return False

        return True

    def _can_close_physical(self, door_name):
        state = self.estado.get_door_state(door_name)

        if state in (DoorState.CERRADO, DoorState.CERRANDO):
            return False

        pres  = self.pres
        atm   = self.press_atm
        rango = self.rango_atm

        if atm is not None and rango is not None and pres is not None:
            if pres > atm + rango:
                self.logger.warning("No se puede cerrar: cámara presurizada (%.1f kPa)", pres)
                return False

        pres_empaque = self.estado.sensores_pres.get(f"pres_empaque_{door_name}")
        if pres_empaque is not None and atm is not None and rango is not None:
            if pres_empaque > atm + rango:
                self.logger.warning("No se puede cerrar: empaque presurizado")
                return False

        return True

    # ============================
    # OBSERVACIÓN DE ESTADOS
    # ============================

    def update(self):
        for name in self.doors:
            current = self.estado.get_door_state(name)
            last = self._last_states[name]

            if last is None:
                self._last_states[name] = current
                continue

            if current == last:
                continue

            self._on_state_change(name, last, current)
            self._last_states[name] = current

    def _on_state_change(self, door_name, prev, current):
        self.logger.info(
            f"Puerta {door_name}: {prev.name} → {current.name}"
        )

        handlers = {
            DoorState.ERROR: self._handle_error,
            DoorState.ABRIENDO: self._handle_opening,
            DoorState.ABIERTO: self._handle_opened,
            DoorState.CERRANDO: self._handle_closing,
            DoorState.CERRADO: self._handle_closed,
            DoorState.ATRAPADA: self._handle_jammed,
        }

        handler = handlers.get(current)
        if handler:
            handler(door_name)

    # ============================
    # HANDLERS
    # ============================

    def _handle_error(self, door_name):
        self.logger.error(f"ERROR en puerta {door_name}")

    def _handle_opening(self, door_name):
        self.logger.info(f"Puerta {door_name} abriéndose")

    def _handle_opened(self, door_name):
        self.logger.info(f"Puerta {door_name} abierta")

    def _handle_closing(self, door_name):
        self.logger.info(f"Puerta {door_name} cerrándose")

    def _handle_closed(self, door_name):
        self.logger.info(f"Puerta {door_name} cerrada")

    def _handle_jammed(self, door_name):
        self.logger.error(f"Puerta {door_name} ATRAPADA")

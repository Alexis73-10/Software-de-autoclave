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

# Condiciones físicas (planeacion_backend_autenticacion.md §5.3, T-13 y T-18):
# se aplican siempre, a la orden manual y a la apertura automática. Fallan
# CERRADAS: una lectura ausente o inválida (presión o temperatura de cámara,
# presión del empaque si la puerta lo usa) o un parámetro de configuración
# ausente rechaza la operación (antes se omitía la comprobación, OPC-16). La
# configuración se lee en vivo, no de copias tomadas al construir (OPC-11).
# request_open / request_close devuelven el resultado real de la orden: si la
# puerta la cancela (bloqueo mecánico) o no la acepta, es un rechazo.

import logging
import math

from autoclave.devices.puertas.advanced_door import AdvancedDoor, DoorState
from .permissions import PERMISSIONS
from autoclave.state_machine.machine.parametros_globales import ParametrosGlobales
from autoclave.core.runtime.sensores_ciclo import temp_seguridad
from autoclave.core.runtime import camara_segura
from autoclave.core.runtime.motivos import Motivo

logger = logging.getLogger(__name__)


# claves de global_params.json ("admosferica" es el nombre real de la clave)
_CLAVE_ATM = "presion_admosferica"
_CLAVE_RANGO = "rango_presion_atm"
_CLAVE_TEMP_MAX = "temp_max_apertura"
_MOTIVO_PARO = Motivo("paro", "Paro de emergencia activado")


def _numero(valor) -> float | None:
    """Lectura o parámetro válido como número finito; None si no lo es."""
    if isinstance(valor, bool):
        return None
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


class ServicioPuertas:

    def __init__(self, doors, estado, profile, config, logger=logger, programas=None,
                 temp_max_ciclo=None, estado_seguro_activo=None, presion_vigente=None):
        self.config = config
        # Callable -> lista de programas cuyos sensores Principales deciden la
        # temperatura de apertura (tanda §1.1; SAF-01 de T3: el seleccionado y,
        # hasta que la cámara sea segura, el del último ciclo). None = temp_camara.
        self._programas = programas
        self._temp_max_ciclo = temp_max_ciclo   # callable (SAF-04 de T4)
        # callable: protocolo de estado seguro en curso (SAF-03 de T5)
        self._estado_seguro_activo = estado_seguro_activo
        # S9 (tanda 9), revisión ★ pasada 2 R2-M3: callable -> bool, presión
        # de cámara al día (ControlLoop.presion_vigente: DI + AI + estado
        # publicado). Sin él, como antes; con él, falla cerrada.
        self._presion_vigente = presion_vigente
        self.doors = {d.name: d for d in doors}
        self.estado = estado
        self.profile = profile
        self.logger = logger
        self._last_states = {name: None for name in self.doors}

    # ── configuración en vivo (OPC-11) ───────────────────────────────────────
    @property
    def temp_max(self):
        return _numero(self.config.get(_CLAVE_TEMP_MAX))

    @property
    def press_atm(self):
        return _numero(self.config.get(_CLAVE_ATM))

    @property
    def rango_atm(self):
        return _numero(self.config.get(_CLAVE_RANGO))

    def _falta_config(self, *claves) -> str:
        faltan = [c for c in claves if _numero(self.config.get(c)) is None]
        return (Motivo("falta_config", f"Falta configuración: {', '.join(faltan)}",
                       claves=", ".join(faltan)) if faltan else "")

    def _paro_activo(self) -> bool:
        """Con el paro de emergencia activo no se mueve ninguna puerta, ni por
        orden manual ni por la apertura automática."""
        return bool(self.estado.get_flag("PARO_EMERGENCIA"))

    def _sensor_empaque(self, door_name) -> str | None:
        """Sensor de presión del empaque de la puerta, solo si lo tiene: las
        AdvancedDoor sin empaque (LOCKING, MOTORIZED...) no lo definen en `ai`."""
        door = self.doors[door_name]
        if not isinstance(door, AdvancedDoor):
            return None
        return (getattr(door, "ai", None) or {}).get("presion_empaque")

    def tiene_actuador(self, door_name) -> bool:
        """False para puertas sin actuador (SimpleDoor): la orden no mueve nada."""
        return getattr(self.doors.get(door_name), "tiene_actuador", True)

    # ── lectura en vivo de sensores ──────────────────────────────────────────
    @property
    def pres(self):
        return self.estado.sensores_pres.get("pres_camara")

    @property
    def temp(self):
        """Temperatura del sensor Principal (tanda §1.1). Lectura None = no
        seguro: _can_open_physical falla cerrada. Si el técnico asigna como
        Principal una sonda fría, la decisión puede ser optimista (riesgo
        registrado en el análisis de riesgos, sin advertencia en la UI)."""
        programas = None
        if self._programas is not None:
            try:
                programas = self._programas()
            except Exception:
                # SAF-08 de T3: sin saber qué sensor decide, no es seguro
                logger.exception("ServicioPuertas: no se pudo obtener el programa")
                return None
        return temp_seguridad(self.estado, programas, self.profile)


    # ============================
    # API HACIA LA INTERFAZ
    # ============================

    def request_open(self, door_name) -> tuple:
        """Retorna (True, "") si se envió el comando, (False, motivo) si se denegó."""
        if door_name not in self.doors:
            self.logger.error(f"Puerta desconocida: {door_name}")
            return False, Motivo("desconocida", "Puerta desconocida")

        ok, reason = self._can_open_physical(door_name)
        if not ok:
            self.logger.warning(f"Apertura denegada: puerta {door_name} — {reason}")
            return False, reason

        ok, reason = self._resultado(self.doors[door_name].cmd_abrir())
        if not ok:
            self.logger.warning(f"Apertura cancelada por la puerta {door_name} — {reason}")
            return False, reason
        self.logger.info(f"Comando abrir enviado a puerta {door_name}")
        return True, ""

    def request_close(self, door_name) -> tuple:
        """Retorna (True, "") si se envió el comando, (False, motivo) si se denegó."""
        if door_name not in self.doors:
            self.logger.error(f"Puerta desconocida: {door_name}")
            return False, Motivo("desconocida", "Puerta desconocida")

        ok, reason = self._can_close_physical(door_name)
        if not ok:
            self.logger.warning(f"Cierre denegado: puerta {door_name} — {reason}")
            return False, reason

        ok, reason = self._resultado(self.doors[door_name].cmd_cerrar())
        if not ok:
            self.logger.warning(f"Cierre no aceptado por la puerta {door_name} — {reason}")
            return False, reason
        self.logger.info(f"Comando cerrar enviado a puerta {door_name}")
        return True, ""

    @staticmethod
    def _resultado(retorno) -> tuple:
        """Resultado de cmd_abrir / cmd_cerrar: (ok, motivo). None = sin
        actuador o puerta que no informa: se considera aceptada."""
        if retorno is None:
            return True, ""
        if isinstance(retorno, tuple):
            return bool(retorno[0]), retorno[1] if len(retorno) > 1 else ""
        return bool(retorno), "" if retorno else Motivo("no_acepto", "La puerta no aceptó la orden")

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

    def can(self, permission: str) -> bool:
        """Consulta si el rol actual tiene el permiso indicado."""
        role_perms = PERMISSIONS.get(self.profile.role, {})
        return role_perms.get(permission, False)

    def can_open(self, door_name) -> tuple:
        if not self.can_open_from_context(door_name):
            msg = Motivo("no_permitido_origen", f"No permitido desde puerta {self.profile.door_id}",
                         puerta=self.profile.door_id)
            self.logger.warning("Apertura no permitida: %s", msg)
            return False, msg
        return self._can_open_physical(door_name)

    def can_close(self, door_name) -> tuple:
        if not self.can_close_from_context(door_name):
            msg = Motivo("no_permitido_origen", f"No permitido desde puerta {self.profile.door_id}",
                         puerta=self.profile.door_id)
            self.logger.warning("Cierre no permitido: %s", msg)
            return False, msg
        return self._can_close_physical(door_name)

    def can_open_from_context(self, door_name) -> bool:
        if door_name != f"Puerta {self.profile.door_id}":
            return self.can("open_other_door")
        return self.can("open_own_door")

    def can_close_from_context(self, door_name) -> bool:
        if door_name != f"Puerta {self.profile.door_id}":
            return self.can("open_other_door")
        return True


    def _can_open_physical(self, door_name) -> tuple:
        """Retorna (True, "") si se puede abrir, (False, motivo) si no.
        Falla cerrada: sin lectura válida o sin configuración, no abre."""
        if self._paro_activo():
            return False, _MOTIVO_PARO
        if self._estado_seguro_activo is not None:
            try:
                activo = self._estado_seguro_activo() is True
            except Exception:
                activo = True
            if activo:
                msg = Motivo("estado_seguro", "Protocolo de estado seguro en curso")
                self.logger.warning("No se puede abrir: %s", msg)
                return False, msg
        # Cámara segura (E2, fin de ciclo §5): misma condición que "NO ABRIR"
        # y el inicio de ciclo; falla cerrada sin lectura o sin configuración.
        programas = None
        if self._programas is not None:
            try:
                programas = self._programas()
            except Exception:
                msg = Motivo("sensor_temp_indeterminado", "No se pudo determinar el sensor de temperatura")
                self.logger.exception("No se puede abrir: %s", msg)
                return False, msg
        try:
            temp_max_ciclo = self._temp_max_ciclo() if self._temp_max_ciclo is not None else None
            vigentes = (True if self._presion_vigente is None
                        else self._presion_vigente() is True)
            segura, msg = camara_segura.evaluar(self.estado, self.config, programas,
                                                self.profile, datos_vigentes=vigentes,
                                                temp_max_ciclo=temp_max_ciclo)
        except Exception:
            # SAF-06 de T4: un error al evaluar no abre ni corta el tick
            msg = Motivo("error_evaluacion", "No se pudo evaluar la cámara segura")
            self.logger.exception("No se puede abrir: %s", msg)
            return False, msg
        if not segura:
            self.logger.warning("No se puede abrir: %s", msg)
            return False, msg

        for name in self.doors:
            if name != door_name:
                if self.estado.get_door_state(name) != DoorState.CERRADO:
                    msg = Motivo("otra_puerta_abierta", f"{name} no está cerrada", puerta=name)
                    self.logger.warning("No se puede abrir: %s", msg)
                    return False, msg

        return True, ""

    def _can_close_physical(self, door_name) -> tuple:
        """Retorna (True, "") si se puede cerrar, (False, motivo) si no.
        Intervienen el estado de la puerta, la presión de cámara y, solo si la
        puerta usa empaque (AdvancedDoor), la del empaque. Sin comprobación de
        vacío ni de temperatura (decisión 18). Falla cerrada."""
        if self._paro_activo():
            return False, _MOTIVO_PARO
        state = self.estado.get_door_state(door_name)

        if state in (DoorState.CERRADO, DoorState.CERRANDO):
            return False, Motivo("ya_cerrada", "La puerta ya está cerrada")
        if state == DoorState.DESCONOCIDO:
            # la posición segura es abierta (decisión 18)
            msg = Motivo("estado_desconocido", "Estado de la puerta desconocido")
            self.logger.warning("No se puede cerrar: %s", msg)
            return False, msg

        falta = self._falta_config(_CLAVE_ATM, _CLAVE_RANGO)
        if falta:
            self.logger.warning("No se puede cerrar: %s", falta)
            return False, falta
        limite = self.press_atm + self.rango_atm

        pres = _numero(self.pres)
        if pres is None:
            msg = Motivo("sin_presion_camara", "Sin lectura válida de presión de cámara")
            self.logger.warning("No se puede cerrar: %s", msg)
            return False, msg
        if pres > limite:
            msg = Motivo("camara_presurizada", f"Cámara presurizada ({pres:.0f} kPa)", pres=pres)
            self.logger.warning("No se puede cerrar: %s", msg)
            return False, msg

        sensor_empaque = self._sensor_empaque(door_name)
        if sensor_empaque:
            pres_empaque = _numero(self.estado.sensores_pres.get(sensor_empaque))
            if pres_empaque is None:
                msg = Motivo("sin_presion_empaque", "Sin lectura válida de presión del empaque")
                self.logger.warning("No se puede cerrar: %s", msg)
                return False, msg
            if pres_empaque > limite:
                msg = Motivo("empaque_presurizado", "Empaque presurizado")
                self.logger.warning("No se puede cerrar: %s", msg)
                return False, msg

        return True, ""

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

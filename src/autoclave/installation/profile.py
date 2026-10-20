import re
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from autoclave.installation.equipment import EquipmentClass
from autoclave.devices.puertas.door_type import DoorType


class Role(Enum):
    OPERATOR_FRONT = "operator_front"
    OPERATOR_BACK  = "operator_back"
    SERVICE        = "service"


# Entradas digitales de suministro que un equipo puede o no tener cableadas
# (E1-1, CR-FC-02). Una entrada sin cablear lee 0 y bloquearía el equipo.
SUPPLY_INPUT_KEYS = (
    "agua_bomba",
    "agua_generador",
    "aire_comprimido",
    "vapor_suministro",
    "suministro_electrico",
)


def supply_inputs_por_defecto() -> dict[str, bool]:
    """Todas cableadas: falla cerrada para perfiles sin el campo."""
    return {k: True for k in SUPPLY_INPUT_KEYS}


def normalizar_supply_inputs(valor) -> dict[str, bool]:
    """Completa con True las claves que falten (campo ausente = todas)."""
    resultado = supply_inputs_por_defecto()
    if isinstance(valor, dict):
        for k in SUPPLY_INPUT_KEYS:
            if valor.get(k) is False:
                resultado[k] = False
    return resultado


def entrada_requerida(profile, clave: str) -> bool:
    """True si el equipo tiene la entrada `clave` cableada y debe vigilarse.
    Sin perfil, o con un valor distinto de False, se considera requerida."""
    si = getattr(profile, "supply_inputs", None)
    if not isinstance(si, dict):
        return True
    return si.get(clave, True) is not False


def numero_puertas(profile) -> int:
    """Puertas declaradas en el perfil (E1-2). Sin perfil válido, 2 (como antes)."""
    n = getattr(profile, "door_count", None)
    return n if n in (1, 2) else 2


def revisa_empaque(profile) -> bool:
    """False solo para door_type=simple (sin sensor de empaque, E1-2). Los
    demás tipos y la falta de perfil conservan la revisión de siempre."""
    return getattr(profile, "door_type", None) != DoorType.SIMPLE


def sensores_empaque(profile) -> list[str]:
    """Sensores de empaque que se revisan: uno por puerta declarada, o
    ninguno si el tipo de puerta no tiene empaque."""
    if not revisa_empaque(profile):
        return []
    return [f"pres_empaque_{n}" for n in range(1, numero_puertas(profile) + 1)]


def entradas_no_monitoreadas(profile) -> list[str]:
    """Entradas declaradas "no aplica" en el perfil, en orden fijo."""
    return [k for k in SUPPLY_INPUT_KEYS if not entrada_requerida(profile, k)]


# Canales de temperatura que un equipo puede o no tener con sonda (adenda
# E0/E1, A-2). Mismos nombres que EstadoAutoclave.map_temp. temp_camara es la
# sonda de control: siempre instalada (la validación rechaza False).
TEMPERATURE_PROBE_KEYS = (
    "temp_camara",
    "temp_2_camara",
    "temp_ref",
    "temp_drenaje",
)
SONDA_OBLIGATORIA = "temp_camara"


def temperature_probes_por_defecto() -> dict[str, bool]:
    """Todas instaladas: falla cerrada para perfiles sin el campo."""
    return {k: True for k in TEMPERATURE_PROBE_KEYS}


def normalizar_temperature_probes(valor) -> dict[str, bool]:
    """Completa con True las claves que falten (campo ausente = todas)."""
    resultado = temperature_probes_por_defecto()
    if isinstance(valor, dict):
        for k in TEMPERATURE_PROBE_KEYS:
            if valor.get(k) is False and k != SONDA_OBLIGATORIA:
                resultado[k] = False
    return resultado


def sonda_instalada(profile, canal: str) -> bool:
    """True si el canal tiene sonda y debe vigilarse. Sin perfil, o con un
    valor distinto de False, se considera instalada."""
    if canal == SONDA_OBLIGATORIA:
        return True
    tp = getattr(profile, "temperature_probes", None)
    if not isinstance(tp, dict):
        return True
    return tp.get(canal, True) is not False


def sondas_no_vigiladas(profile) -> list[str]:
    """Canales declarados sin sonda en el perfil, en orden fijo."""
    return [k for k in TEMPERATURE_PROBE_KEYS if not sonda_instalada(profile, k)]


# FW-D7: ID único de la tarjeta de E/S (MAC de fábrica del ESP32, 12 dígitos
# hex en mayúscula) registrado por el ingeniero con tools/emparejar_tarjeta.py.
_RE_BOARD_ID = re.compile(r"^[0-9A-F]{12}$")


def board_id_valido(valor) -> bool:
    return isinstance(valor, str) and bool(_RE_BOARD_ID.match(valor))


def tarjeta_emparejada(profile, id_tarjeta) -> bool | None:
    """True si la tarjeta conectada es la registrada en el perfil; False si
    es otra o el perfil no tiene board_id (sin emparejar); None si no se
    conoce el ID de la tarjeta. En la versión 1.0 es solo una advertencia
    no bloqueante (FW-D7)."""
    if not id_tarjeta:
        return None
    return getattr(profile, "board_id", None) == id_tarjeta


# E1b (D-23): fuente de vapor del equipo. La salida de la fuente que el
# equipo no tiene no se enciende nunca; en mixto quedan las dos. Campo ausente
# = comportamiento previo (ambas disponibles) para perfiles anteriores a E1b.
# S1 (tanda 2, decisión 1 de Cristian, 2026-10-19): con generador interno no
# hay DO1 (vapor_generador) ni DO2 (vapor_caldera): el generador tiene sus
# propios controles y el software no los enciende ni los lee. Caldera externa
# y mixto conservan la asignación de E1b (abierta, por definir en campo).
VAPOR_SOURCES = ("generator", "boiler", "mixed")
_SALIDAS_VAPOR = {
    "generator": frozenset(),
    "boiler":    frozenset({"vapor_caldera"}),
    "mixed":     frozenset({"vapor_generador", "vapor_caldera"}),
}


def salidas_vapor_permitidas(profile) -> set[str]:
    """None (perfil anterior a E1b) = ambas; un valor desconocido = ninguna
    (falla cerrada: nunca se habilita una fuente por un valor mal escrito)."""
    fuente = getattr(profile, "vapor_source", None)
    if fuente is None:
        return set(_SALIDAS_VAPOR["mixed"])
    return set(_SALIDAS_VAPOR.get(fuente, frozenset()))


class ProfileValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Perfil de instalación inválido: {'; '.join(errors)}")


@dataclass
class InstallationProfile:
    machine_id:      str
    model_id:        str
    serial_number:   str
    equipment_class: EquipmentClass
    door_count:      int
    door_type:       DoorType
    cooling_level:   int
    door_id:         int
    role:            Role
    created_at:      datetime
    locked:          bool = True
    # E1-1: entrada -> True si está cableada. Falta el campo = todas True.
    supply_inputs:   dict = field(default_factory=supply_inputs_por_defecto)
    # A-2: canal de temperatura -> True si tiene sonda. Falta el campo = todas.
    temperature_probes: dict = field(default_factory=temperature_probes_por_defecto)
    # FW-D7: ID de la tarjeta de E/S emparejada. None = sin emparejar.
    board_id:        str | None = None
    # E1b: generator | boiler | mixed. None = perfil anterior a E1b.
    vapor_source:    str | None = None


_REQUIRED_TYPES: dict[str, type] = {
    "machine_id":      str,
    "model_id":        str,
    "serial_number":   str,
    "equipment_class": str,
    "door_count":      int,
    "door_type":       str,
    "cooling_level":   int,
    "door_id":         int,
    "role":            str,
    "created_at":      str,
    "locked":          bool,
}

_VALID_EQUIPMENT_CLASSES = {e.value for e in EquipmentClass}
_VALID_DOOR_TYPES        = {e.value for e in DoorType}


def validate_profile_data(data: dict) -> list[str]:
    from autoclave.installation.equipment import get_capabilities
    errors: list[str] = []

    for field, expected_type in _REQUIRED_TYPES.items():
        if field not in data:
            errors.append(f"campo faltante: '{field}'")
        elif not isinstance(data[field], expected_type):
            errors.append(
                f"tipo incorrecto en '{field}': "
                f"esperado {expected_type.__name__}, "
                f"recibido {type(data[field]).__name__}"
            )

    if "door_count" in data and isinstance(data["door_count"], int):
        if data["door_count"] not in {1, 2}:
            errors.append(
                f"valor inválido en 'door_count': '{data['door_count']}' no está en {{1, 2}}"
            )

    if "equipment_class" in data and isinstance(data["equipment_class"], str):
        if data["equipment_class"] not in _VALID_EQUIPMENT_CLASSES:
            errors.append(
                f"valor inválido en 'equipment_class': '{data['equipment_class']}' "
                f"no está en {_VALID_EQUIPMENT_CLASSES}"
            )

    if "door_type" in data and isinstance(data["door_type"], str):
        if data["door_type"] not in _VALID_DOOR_TYPES:
            errors.append(
                f"valor inválido en 'door_type': '{data['door_type']}' "
                f"no está en {_VALID_DOOR_TYPES}"
            )

    # supply_inputs es opcional; si está, solo claves conocidas y booleanas
    if "supply_inputs" in data:
        si = data["supply_inputs"]
        if not isinstance(si, dict):
            errors.append(
                f"tipo incorrecto en 'supply_inputs': esperado dict, "
                f"recibido {type(si).__name__}"
            )
        else:
            desconocidas = sorted(set(si) - set(SUPPLY_INPUT_KEYS))
            if desconocidas:
                errors.append(
                    f"claves desconocidas en 'supply_inputs': {desconocidas} "
                    f"(válidas: {list(SUPPLY_INPUT_KEYS)})"
                )
            no_bool = sorted(k for k, v in si.items() if not isinstance(v, bool))
            if no_bool:
                errors.append(f"valores no booleanos en 'supply_inputs': {no_bool}")

    # temperature_probes es opcional; mismo patrón, y temp_camara no puede faltar
    if "temperature_probes" in data:
        tp = data["temperature_probes"]
        if not isinstance(tp, dict):
            errors.append(
                f"tipo incorrecto en 'temperature_probes': esperado dict, "
                f"recibido {type(tp).__name__}"
            )
        else:
            desconocidas = sorted(set(tp) - set(TEMPERATURE_PROBE_KEYS))
            if desconocidas:
                errors.append(
                    f"claves desconocidas en 'temperature_probes': {desconocidas} "
                    f"(válidas: {list(TEMPERATURE_PROBE_KEYS)})"
                )
            no_bool = sorted(k for k, v in tp.items() if not isinstance(v, bool))
            if no_bool:
                errors.append(f"valores no booleanos en 'temperature_probes': {no_bool}")
            if tp.get(SONDA_OBLIGATORIA) is False:
                errors.append(
                    f"'temperature_probes.{SONDA_OBLIGATORIA}' no puede ser false: "
                    f"es la sonda de control del ciclo"
                )

    # board_id es opcional (FW-D7); si está, 12 dígitos hex en mayúscula
    if "board_id" in data and not board_id_valido(data["board_id"]):
        errors.append(
            f"valor inválido en 'board_id': {data['board_id']!r} "
            f"(se esperan 12 dígitos hexadecimales en mayúscula)"
        )

    # vapor_source es opcional (E1b); si está, uno de VAPOR_SOURCES
    if "vapor_source" in data and data["vapor_source"] not in VAPOR_SOURCES:
        errors.append(
            f"valor inválido en 'vapor_source': {data['vapor_source']!r} "
            f"(se espera uno de {list(VAPOR_SOURCES)})"
        )

    # Validaciones cruzadas (solo si equipment_class es válido)
    ec_value = data.get("equipment_class")
    if (ec_value in _VALID_EQUIPMENT_CLASSES
            and isinstance(data.get("door_count"), int)
            and isinstance(data.get("cooling_level"), int)):
        cap = get_capabilities(EquipmentClass(ec_value))
        if data["door_count"] > cap.door_count_max:
            errors.append(
                f"door_count {data['door_count']} excede el máximo "
                f"({cap.door_count_max}) para '{ec_value}'"
            )
        if data["cooling_level"] > cap.cooling_level_max:
            errors.append(
                f"cooling_level {data['cooling_level']} excede el máximo "
                f"({cap.cooling_level_max}) para '{ec_value}'"
            )

    return errors

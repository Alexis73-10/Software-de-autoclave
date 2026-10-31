from autoclave.core.runtime.asignacion_io import canal_do
from autoclave.hal.measures.units import Units
from autoclave.utils.paths import calibration_path
from autoclave.devices.puertas.door_type import DoorType

def _canales_do_puerta(n: int) -> dict:
    """Canales físicos de las salidas de la puerta `n` según la asignación de
    E/S en memoria (R8, D8-5.12). Con la de fábrica: puerta 1 = 20/22/9/11,
    puerta 2 = 21/23/10/12, como antes."""
    return {"abrir": canal_do(f"abrir_puerta_{n}"), "cerrar": canal_do(f"cerrar_puerta_{n}"),
            "desbloquear": canal_do(f"desbloqueo_puerta_{n}"),
            "bloquear": canal_do(f"bloqueo_puerta_{n}")}


def _build_door_cfg(n: int, door_type: DoorType) -> dict:
    do_ch = _canales_do_puerta(n)
    cfg = {
        "name": f"Puerta {n}",
        "type": door_type,
        "di": {
            "abierta": f"puerta_{n}_abierta",
            "cerrada": f"puerta_{n}_cerrada",
        },
    }

    has_motor  = door_type in (DoorType.MOTORIZED, DoorType.MOTORIZED_LOCKING, DoorType.ADVANCED)
    has_lock   = door_type in (DoorType.LOCKING, DoorType.MOTORIZED_LOCKING, DoorType.ADVANCED)
    has_sensor = door_type == DoorType.ADVANCED
    has_mech_lock_sensor = door_type in (DoorType.MOTORIZED, DoorType.MOTORIZED_LOCKING)

    if has_motor or has_lock:
        do = {}
        if has_motor:
            do["abrir"]  = do_ch["abrir"]
            do["cerrar"] = do_ch["cerrar"]
        if has_lock:
            do["desbloquear"] = do_ch["desbloquear"]
            do["bloquear"]    = do_ch["bloquear"]
        cfg["do"] = do

    if has_sensor:
        cfg["di"]["atrapamiento"] = f"atrapamiento_puerta_{n}"
        cfg["ai"] = {"presion_empaque": f"pres_empaque_{n}"}

    if has_mech_lock_sensor:
        cfg["di"]["bloqueo"] = f"bloqueo_puerta_{n}"

    return cfg


def build_modbus(units, al_conectar=None):
    """Enlace Modbus TCP con los módulos M31-U (tanda 19), ya iniciado.
    `al_conectar(modulo_es)` se registra antes de start() para no perder la
    primera conexión verificada (audit_log y emparejamiento, FW-D7)."""
    try:
        from autoclave.protocols.modbus_link import ModbusLink
    except ImportError as e:
        raise RuntimeError(
            "enlace de E/S: el enlace Modbus no está disponible en esta "
            f"compilación (autoclave.protocols.modbus_link: {e})") from e
    enlace = ModbusLink(on_update=lambda data: units.update_from_serial(data))
    enlace.al_conectar = al_conectar
    enlace.start()
    return enlace


def build_enlace(units, al_conectar=None):
    """Construye e inicia el enlace de E/S: ModbusLink (MOD-01; enlace único
    desde la tanda 20, T20-03, que retiró el serial y la selección por
    archivo). Cumple protocols.enlace.EnlaceES."""
    return build_modbus(units, al_conectar=al_conectar)


def build_doors_cfg(profile) -> list[dict]:
    return [_build_door_cfg(n + 1, profile.door_type) for n in range(profile.door_count)]


def build_hardware(profile):
    units = Units(calibration_path())
    enlace = build_enlace(units)
    return units, enlace, build_doors_cfg(profile)

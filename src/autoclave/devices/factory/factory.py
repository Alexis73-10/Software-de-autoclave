from autoclave.hal.units import Units
from autoclave.protocols.serial_link import SerialLink
from autoclave.utils.resources import resource_path
from autoclave.devices.puertas.door_type import DoorType

_DOOR_DO_CHANNELS = {
    1: {"abrir": 20, "cerrar": 22, "desbloquear": 9,  "bloquear": 11},
    2: {"abrir": 21, "cerrar": 23, "desbloquear": 10, "bloquear": 12},
}


def _build_door_cfg(n: int, door_type: DoorType) -> dict:
    do_ch = _DOOR_DO_CHANNELS[n]
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


def build_hardware(profile):
    units = Units(resource_path("autoclave/config/calibration.yaml"))
    serial = SerialLink(on_update=lambda data: units.update_from_serial(data))
    serial._scan_ports()
    serial.start()

    doors_cfg = [_build_door_cfg(n + 1, profile.door_type) for n in range(profile.door_count)]
    return units, serial, doors_cfg

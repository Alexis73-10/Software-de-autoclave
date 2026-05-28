from autoclave.hal.units import Units
from autoclave.protocols.serial_link import SerialLink
from autoclave.utils.resources import resource_path

_DOOR_TYPE_MAP = {"simple": 1, "advanced": 2}


def build_hardware(profile):
    units = Units(resource_path("autoclave/config/calibration.yaml"))

    serial = SerialLink(
        on_update=lambda data: units.update_from_serial(data)
    )
    serial._scan_ports()
    serial.start()

    door_type_int = _DOOR_TYPE_MAP[profile.door_type]

    all_doors_cfg = [
        {
            "name": "Puerta 1",
            "type": door_type_int,
            "di": {
                "abierta": "puerta_1_abierta",
                "cerrada": "puerta_1_cerrada",
                "atrapamiento": "atrapamiento_puerta_1",
            },
            "ai": {"presion_empaque": "pres_empaque_1"},
            "do": {"abrir": 20, "cerrar": 22, "desbloquear": 9, "bloquear": 11},
        },
        {
            "name": "Puerta 2",
            "type": door_type_int,
            "di": {
                "abierta": "puerta_2_abierta",
                "cerrada": "puerta_2_cerrada",
                "atrapamiento": "atrapamiento_puerta_2",
            },
            "ai": {"presion_empaque": "pres_empaque_2"},
            "do": {"abrir": 21, "cerrar": 23, "desbloquear": 10, "bloquear": 12},
        },
    ]

    return units, serial, all_doors_cfg[:profile.door_count]

from autoclave.hal.units import Units
from autoclave.protocols.serial_link import SerialLink


def build_hardware():
    units = Units("src/autoclave/config/calibration.yaml")

    serial = SerialLink(
        on_update=lambda data: units.update_from_serial(data)
    )
    serial._scan_ports()
    serial.start()

    doors_cfg = [
        {
            "name": "Puerta 1",
            "type": 2,  # Tipo de puerta (1 = simple, 2 = avanzada)
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
            "type": 2,  # Tipo de puerta (1 = simple, 2 = avanzada)
            "di": {
                "abierta": "puerta_2_abierta",
                "cerrada": "puerta_2_cerrada",
                "atrapamiento": "atrapamiento_puerta_2",
            },
            "ai": {"presion_empaque": "pres_empaque_2"},
            "do": {"abrir": 21, "cerrar": 23, "desbloquear": 10, "bloquear": 12},
        },
    ]

    return units, serial, doors_cfg

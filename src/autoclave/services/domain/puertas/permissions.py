# autoclave/services/domain/puertas/permissions.py

from autoclave.installation.profile import Role

PERMISSIONS = {
    Role.OPERATOR_FRONT: {
        "start_cycle": True,
        "open_own_door": True,
        "open_other_door": False,
    },
    Role.OPERATOR_BACK: {
        "start_cycle": False,
        "open_own_door": True,
        "open_other_door": False,
    },
    Role.SERVICE: {
        "start_cycle": True,
        "open_own_door": True,
        "open_other_door": True,
    },
}

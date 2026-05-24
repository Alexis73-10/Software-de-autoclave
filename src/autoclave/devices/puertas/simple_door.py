from autoclave.devices.puertas.base_puertas import Door
from autoclave.devices.puertas.enum_doors import DoorState


class SimpleDoor(Door):
    def __init__(self, name, di, estado):
        super().__init__(name)
        self.di = di
        self.estado = estado

    # ============================
    # LECTURA
    # ============================

    def puerta_cerrada(self):
        return self.estado.sensores_di.get(self.di["cerrada"])

    def is_closed(self):
        return self.puerta_cerrada()

    # ============================
    # ESTADO
    # ============================

    def get_state(self):
        return self.estado.get_door_state(self.name)

    def set_state(self, new_state):
        self.estado.update_door_state(self.name, new_state)

    def can_start_cycle(self):
        return self.puerta_cerrada()

    # ============================
    # ACCIONES (NO APLICAN)
    # ============================

    def lock(self):
        pass

    def unlock(self):
        pass

    def cmd_abrir(self):
        pass

    def cmd_cerrar(self):
        pass

    # ============================
    # LOOP
    # ============================

    def update(self):
        cerrada = self.puerta_cerrada()

        if cerrada is None:
            return  # sensor inválido

        if cerrada:
            self.set_state(DoorState.CERRADO)
        else:
            self.set_state(DoorState.ABIERTO)
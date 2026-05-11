class Door:
    def __init__(self, name):
        self.name = name
    def is_closed(self) -> bool:
        raise NotImplementedError

    def lock(self):
        pass

    def unlock(self):
        pass

    def can_start_cycle(self) -> bool:
        raise NotImplementedError

    def update(self):
        pass
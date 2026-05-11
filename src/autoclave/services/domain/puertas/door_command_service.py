class DoorCommandService:
    def __init__(self, backend_client, source_door: int):
        self.backend = backend_client
        self.source_door = source_door

    def open(self, door_name: str):
        return self.backend.post(
            f"/doors/{door_name}/open",
            {"source_door": self.source_door},
        )

    def close(self, door_name: str):
        return self.backend.post(
            f"/doors/{door_name}/close",
            {"source_door": self.source_door},
        )

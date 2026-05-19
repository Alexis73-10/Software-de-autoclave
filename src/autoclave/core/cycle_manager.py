
import json
import os
import logging
from autoclave.utils.resources import resource_path

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
class Cycle:
    def __init__(self, cycle_id: str, name: str, parameters: dict):
        self.id = cycle_id
        self.name = name
        self.parameters = parameters

    def get_param(self, *keys, default=None):
        data = self.parameters

        for key in keys:
            data = data.get(key, {})
        
        return data.get("value", default)


class CycleManager:
    def __init__(self):
        self.cycles = {}
        self.selected_cycle = None
    
    def load_all_cycles(self):
        self.cycles.clear()

        self._load_from_folder("cycles/factory", source="factory")
        self._load_from_folder("cycles/user", source="user")

    def _load_from_folder(self, folder_path, source):
        folder_path = os.path.join(BASE_DIR, folder_path)

        logger.info(f"📂 Buscando en: {folder_path}")

        if not os.path.exists(folder_path):
            print("❌ No existe la carpeta")
            return

        for file in os.listdir(folder_path):
            if file.endswith(".json"):
                full_path = os.path.join(folder_path, file)

                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                        cycle = Cycle(
                            cycle_id=data["cycle_id"],
                            name=data.get("display_name", data.get("cycle_name", data["cycle_id"])),
                            parameters=data.get("parameters", {})
                        )

                        cycle.source = source

                        # 🔥 aquí pasa la magia
                        self.cycles[cycle.id] = cycle

                except Exception as e:
                    print(f"⚠️ Error cargando {file}: {e}")

    def set_default_cycle(self, cycle_id: str):
        if cycle_id in self.cycles:
            self.selected_cycle = self.cycles[cycle_id]
            return

        raise Exception(f"Ciclo por defecto '{cycle_id}' no encontrado")
    
    def get_selected_cycle(self):
        if self.selected_cycle is None:
            raise Exception("No hay ciclo seleccionado")
        return self.selected_cycle
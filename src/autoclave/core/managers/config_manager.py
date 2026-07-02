import json
import os
from autoclave.utils.resources import resource_path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
class ConfigManager:
    def __init__(self):
        self.config = {}

    def load_config(self):
        path = resource_path("autoclave/config/global_params.json")

        with open(path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def get(self, *keys, default=None):
        data = self.config

        for key in keys:
            data = data.get(key, {})

        if isinstance(data, dict) and "value" in data:
            return data["value"]

        return data if data != {} else default

import json
import os
import logging
from autoclave.utils.resources import resource_path

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROLES_SENSOR_VALIDOS = {"principal", "referencia", "no_en_uso"}


class Cycle:
    def __init__(self, cycle_id: str, name: str, parameters: dict,
                 sensor_roles: dict | None = None,
                 display_slots: list | None = None):
        self.id = cycle_id
        self.name = name
        self.parameters = parameters
        self.sensor_roles = sensor_roles or {}
        self.display_slots = display_slots or [None, None, None]

    def get_param(self, *keys, default=None):
        data = self.parameters

        for key in keys:
            data = data.get(key, {})

        return data.get("value", default)

    def set_param(self, fase: str, path: list[str], value):
        """Actualiza el 'value' de un parámetro navegando fase + path, coercionando
        y validando contra el 'type'/'min'/'max' propio del JSON del ciclo.
        Devuelve el valor ya coercionado. No muta nada si la validación falla."""
        section = self.parameters.get(fase)
        if section is None:
            raise KeyError(f"El ciclo no tiene la sección '{fase}'")

        node = section
        for key in path[:-1]:
            if not isinstance(node, dict) or key not in node:
                raise KeyError(f"Ruta de parámetro inválida: {'.'.join(path)}")
            node = node[key]

        leaf_key = path[-1]
        if not isinstance(node, dict) or leaf_key not in node or "value" not in node[leaf_key]:
            raise KeyError(f"El parámetro '{'.'.join(path)}' no existe en '{fase}'")

        leaf = node[leaf_key]
        param_type = leaf.get("type", "int")

        if param_type == "bool":
            coerced = bool(value)
        elif param_type == "float":
            coerced = float(value)
        else:
            coerced = int(value)

        if param_type != "bool":
            pmin, pmax = leaf.get("min"), leaf.get("max")
            if pmin is not None and coerced < pmin:
                raise ValueError(f"'{leaf_key}' fuera de rango (mínimo {pmin})")
            if pmax is not None and coerced > pmax:
                raise ValueError(f"'{leaf_key}' fuera de rango (máximo {pmax})")

        leaf["value"] = coerced
        return coerced

    def get_principal_sensor(self) -> str:
        for sensor, rol in self.sensor_roles.items():
            if rol == "principal":
                return sensor
        return "temp_camara"

    def get_referencia_sensor(self) -> str | None:
        for sensor, rol in self.sensor_roles.items():
            if rol == "referencia":
                return sensor
        return None

    def set_sensor_roles(self, roles: dict) -> None:
        from autoclave.core.runtime.status import EstadoAutoclave
        sensores_validos = set(EstadoAutoclave.map_temp.keys())

        principales = 0
        referencias = 0
        for sensor, rol in roles.items():
            if sensor not in sensores_validos:
                raise ValueError(f"Sensor desconocido: '{sensor}'")
            if rol not in _ROLES_SENSOR_VALIDOS:
                raise ValueError(f"Rol inválido para '{sensor}': '{rol}'")
            if rol == "principal":
                principales += 1
            elif rol == "referencia":
                referencias += 1

        if principales > 1:
            raise ValueError("Solo puede haber un sensor 'principal'")
        if referencias > 1:
            raise ValueError("Solo puede haber un sensor 'referencia'")

        self.sensor_roles = dict(roles)

    def set_display_slots(self, slots: list) -> None:
        from autoclave.core.runtime.status import EstadoAutoclave

        if len(slots) != 3:
            raise ValueError("display_slots debe tener exactamente 3 elementos")

        sensores_validos = set(EstadoAutoclave.map_temp.keys()) | set(EstadoAutoclave.map_pres.keys())
        for slot in slots:
            if slot is not None and slot not in sensores_validos:
                raise ValueError(f"Sensor desconocido: '{slot}'")

        self.display_slots = list(slots)


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
                            parameters=data.get("parameters", {}),
                            sensor_roles=data.get("cycle_temperature_sensors", {}),
                            display_slots=data.get("cycle_display_slots", [None, None, None]),
                        )

                        cycle.source = source
                        cycle._path  = full_path

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
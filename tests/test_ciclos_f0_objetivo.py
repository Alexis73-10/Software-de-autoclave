# tests/test_ciclos_f0_objetivo.py
#
# Todos los perfiles de ciclo deben traer F0_objetivo en globals (plan
# docs/mis_plans/planeacion_f0.md sección 2): rango 0-60 min, defecto 12.
import glob
import json
import os

_CYCLES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "src", "autoclave", "cycles",
)


def _cycle_files():
    return sorted(
        glob.glob(os.path.join(_CYCLES_DIR, "factory", "*.json"))
        + glob.glob(os.path.join(_CYCLES_DIR, "user", "*.json"))
    )


def test_hay_archivos_de_ciclo_para_verificar():
    assert len(_cycle_files()) >= 5


def test_todos_los_ciclos_tienen_f0_objetivo_en_globals():
    for path in _cycle_files():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        globals_params = data["parameters"]["globals"]
        assert "F0_objetivo" in globals_params, f"Falta F0_objetivo en {path}"
        param = globals_params["F0_objetivo"]
        assert param["min"] == 0
        assert param["max"] == 60
        assert 0 <= param["value"] <= 60
        assert "F0" in globals_params  # ya existía, no se toca

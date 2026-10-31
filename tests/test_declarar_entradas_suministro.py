# tests/test_declarar_entradas_suministro.py
#
# E1-1: herramienta de instalación que declara supply_inputs en el perfil.

import importlib.util
import json
from pathlib import Path

import pytest

_RUTA = Path(__file__).resolve().parents[1] / "tools" / "declarar_entradas_suministro.py"
_spec = importlib.util.spec_from_file_location("declarar_entradas_suministro", _RUTA)
herramienta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(herramienta)

_PERFIL = {
    "machine_id": "ACV-2026-SN1", "model_id": "SPK", "serial_number": "SN1",
    "door_count": 2, "door_type": "simple", "equipment_type": "horizontal",
    "equipment_class": "piso_lab", "drying_type": "vacuum", "door_id": 1,
    "role": "operator_front", "created_at": "2026-05-25T05:49:47", "cooling_level": 3,
    "locked": True,
}


def _perfil(tmp_path):
    f = tmp_path / "installation_profile.json"
    f.write_text(json.dumps(_PERFIL), encoding="utf-8")
    return f


def test_solo_aire_comprimido(tmp_path):
    f = _perfil(tmp_path)
    # --si: sin pregunta interactiva (adenda A-6 agregó la confirmación)
    assert herramienta.main(["--perfil", str(f), "--cableadas", "aire_comprimido", "--si"]) == 0
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data["supply_inputs"] == {
        "agua_bomba": False, "agua_generador": False, "aire_comprimido": True,
        "vapor_suministro": False, "suministro_electrico": False,
    }
    # conserva los demás campos, incluidos los que la aplicación no lee
    assert data["drying_type"] == "vacuum" and data["locked"] is True
    assert list(tmp_path.glob("installation_profile.json.*.bak"))


def test_clave_desconocida_no_escribe(tmp_path):
    f = _perfil(tmp_path)
    assert herramienta.main(["--perfil", str(f), "--cableadas", "vapor"]) == 1
    assert "supply_inputs" not in json.loads(f.read_text(encoding="utf-8"))
    assert not list(tmp_path.glob("*.bak"))


def test_mostrar_sin_campo_todas_true(tmp_path, capsys):
    f = _perfil(tmp_path)
    assert herramienta.main(["--perfil", str(f), "--mostrar"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        k: True for k in ("agua_bomba", "agua_generador", "aire_comprimido",
                          "vapor_suministro", "suministro_electrico")}

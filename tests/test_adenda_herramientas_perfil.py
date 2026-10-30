# tests/test_adenda_herramientas_perfil.py
#
# Adenda E0/E1: herramientas del ingeniero sobre installation_profile.json.
#   A-6 (SAF-05)  declarar_entradas_suministro: lista vacía solo con flag
#                 explícito, confirmación y registro de auditoría
#   A-2           declarar_sondas_temperatura (mismo patrón)

import importlib.util
import json
from pathlib import Path

import pytest


def _cargar(nombre):
    ruta = Path(__file__).resolve().parents[1] / "tools" / f"{nombre}.py"
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


suministro = _cargar("declarar_entradas_suministro")
sondas = _cargar("declarar_sondas_temperatura")

_PERFIL = {
    "machine_id": "ACV-2026-SN1", "model_id": "SPK", "serial_number": "SN1",
    "door_count": 2, "door_type": "simple", "equipment_class": "piso_lab",
    "door_id": 1, "role": "operator_front", "created_at": "2026-05-25T05:49:47",
    "cooling_level": 3, "locked": True,
}


@pytest.fixture
def perfil(tmp_path):
    f = tmp_path / "installation_profile.json"
    f.write_text(json.dumps(_PERFIL), encoding="utf-8")
    return f


def _leer(f):
    return json.loads(f.read_text(encoding="utf-8"))


def _auditoria(f):
    log = f.with_name("installation_profile_cambios.log")
    if not log.exists():
        return []
    return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# A-6: declarar_entradas_suministro
# ---------------------------------------------------------------------------

def test_cableadas_vacio_sin_flag_se_rechaza(perfil):
    assert suministro.main(["--perfil", str(perfil), "--cableadas", "--si"]) == 1
    assert "supply_inputs" not in _leer(perfil)
    assert _auditoria(perfil) == []


def test_cableadas_vacio_con_flag_explicito(perfil):
    assert suministro.main(["--perfil", str(perfil), "--cableadas",
                            "--permitir-ninguna", "--si"]) == 0
    assert not any(_leer(perfil)["supply_inputs"].values())


def test_sin_confirmacion_no_escribe(perfil, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "no")
    assert suministro.main(["--perfil", str(perfil), "--cableadas", "aire_comprimido"]) == 1
    assert "supply_inputs" not in _leer(perfil)
    assert not list(perfil.parent.glob("*.bak"))


def test_confirmacion_interactiva_escribe(perfil, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "SI")
    assert suministro.main(["--perfil", str(perfil), "--cableadas", "aire_comprimido"]) == 0
    assert _leer(perfil)["supply_inputs"]["aire_comprimido"] is True


def test_sin_terminal_no_escribe(perfil, monkeypatch):
    def _eof(*_):
        raise EOFError
    monkeypatch.setattr("builtins.input", _eof)
    assert suministro.main(["--perfil", str(perfil), "--cableadas", "aire_comprimido"]) == 1
    assert "supply_inputs" not in _leer(perfil)


def test_cambio_queda_en_el_registro_de_auditoria(perfil):
    assert suministro.main(["--perfil", str(perfil), "--cableadas", "aire_comprimido",
                            "--si"]) == 0
    (reg,) = _auditoria(perfil)
    assert reg["campo"] == "supply_inputs"
    assert reg["herramienta"] == "declarar_entradas_suministro"
    assert reg["antes"] is None                       # el perfil no tenía el campo
    assert reg["despues"]["aire_comprimido"] is True
    assert reg["despues"]["agua_bomba"] is False
    assert reg["fecha"] and reg["usuario"]


def test_registro_se_acumula(perfil):
    suministro.main(["--perfil", str(perfil), "--cableadas", "aire_comprimido", "--si"])
    suministro.main(["--perfil", str(perfil), "--cableadas", "aire_comprimido",
                     "agua_bomba", "--si"])
    regs = _auditoria(perfil)
    assert len(regs) == 2
    assert regs[1]["antes"]["agua_bomba"] is False
    assert regs[1]["despues"]["agua_bomba"] is True


# ---------------------------------------------------------------------------
# A-2: declarar_sondas_temperatura
# ---------------------------------------------------------------------------

def test_sondas_declara_las_instaladas(perfil):
    # procedimiento de este equipo: las cuatro sondas cableadas
    assert sondas.main(["--perfil", str(perfil), "--instaladas", "temp_camara",
                        "temp_2_camara", "temp_ref", "temp_drenaje", "--si"]) == 0
    assert _leer(perfil)["temperature_probes"] == {
        "temp_camara": True, "temp_2_camara": True, "temp_ref": True, "temp_drenaje": True,
    }
    assert list(perfil.parent.glob("installation_profile.json.*.bak"))
    (reg,) = _auditoria(perfil)
    assert reg["campo"] == "temperature_probes"
    assert reg["herramienta"] == "declarar_sondas_temperatura"


def test_sondas_sin_temp_camara_se_rechaza(perfil):
    assert sondas.main(["--perfil", str(perfil), "--instaladas", "temp_ref", "--si"]) == 1
    assert "temperature_probes" not in _leer(perfil)
    assert _auditoria(perfil) == []


def test_sondas_clave_desconocida_se_rechaza(perfil):
    assert sondas.main(["--perfil", str(perfil), "--instaladas", "temp_camara",
                        "temp_chaqueta", "--si"]) == 1
    assert "temperature_probes" not in _leer(perfil)


def test_sondas_mostrar_sin_campo_todas(perfil, capsys):
    assert sondas.main(["--perfil", str(perfil), "--mostrar"]) == 0
    assert all(json.loads(capsys.readouterr().out).values())


def test_sondas_sin_confirmacion_no_escribe(perfil, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "")
    assert sondas.main(["--perfil", str(perfil), "--instaladas", "temp_camara"]) == 1
    assert "temperature_probes" not in _leer(perfil)

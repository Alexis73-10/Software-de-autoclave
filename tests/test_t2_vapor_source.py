"""T2 (E1b, tanda 2026-10-14): fuente de vapor en el perfil de instalación.

`vapor_source` = generator | boiler | mixed. La salida de vapor de la fuente
que el equipo no tiene no se enciende nunca (D-23, planeacion_menu_instalacion_ui
§4). Campo ausente = comportamiento previo (ambas salidas disponibles)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from autoclave.devices.io.set_io import SetOutput
from autoclave.installation import storage
from autoclave.installation.profile import (
    VAPOR_SOURCES, salidas_vapor_permitidas, validate_profile_data,
)

_VALIDO = {
    "machine_id": "ACV-2026-SN001", "model_id": "MX-500", "serial_number": "SN001",
    "equipment_class": "piso_lab", "door_count": 2, "door_type": "simple",
    "cooling_level": 2, "door_id": 1, "role": "operator_front",
    "created_at": "2026-01-01T00:00:00", "locked": True,
}


def test_valores_validos():
    assert VAPOR_SOURCES == ("generator", "boiler", "mixed")


@pytest.mark.parametrize("fuente", ["generator", "boiler", "mixed"])
def test_validacion_acepta_fuentes_conocidas(fuente):
    assert validate_profile_data({**_VALIDO, "vapor_source": fuente}) == []


@pytest.mark.parametrize("fuente", ["interno", "", None, 3, "GENERATOR"])
def test_validacion_rechaza_fuente_desconocida(fuente):
    errores = validate_profile_data({**_VALIDO, "vapor_source": fuente})
    assert any("vapor_source" in e for e in errores)


def test_campo_ausente_es_valido():
    assert validate_profile_data(_VALIDO) == []


@pytest.mark.parametrize("fuente,esperado", [
    ("generator", set()),          # S1 (tanda 2): sin DO1 ni DO2
    ("boiler", {"vapor_caldera"}),
    ("mixed", {"vapor_generador", "vapor_caldera"}),
    (None, {"vapor_generador", "vapor_caldera"}),
])
def test_salidas_permitidas_por_fuente(fuente, esperado):
    perfil = SimpleNamespace(vapor_source=fuente)
    assert salidas_vapor_permitidas(perfil) == esperado


def test_sin_perfil_ambas_salidas():
    assert salidas_vapor_permitidas(None) == {"vapor_generador", "vapor_caldera"}


def _setdo(fuente):
    io = MagicMock()
    estado = MagicMock()
    return SetOutput(io, estado, profile=SimpleNamespace(vapor_source=fuente)), io


def test_generador_no_enciende_la_caldera():
    setdo, io = _setdo("generator")
    setdo.vapor_caldera_on()
    io.set_output.assert_called_once_with(2, False)   # nunca ON: se fuerza OFF
    setdo.vapor_generador_on()
    io.set_output.assert_called_with(1, False)        # S1: tampoco DO1


def test_caldera_no_enciende_el_generador():
    setdo, io = _setdo("boiler")
    setdo.vapor_generador_on()
    io.set_output.assert_called_once_with(1, False)
    setdo.vapor_caldera_on()
    io.set_output.assert_called_with(2, True)


def test_set_output_generico_tambien_bloquea_la_fuente_ausente():
    # /io/test/output y cualquier otro llamador pasan por set_output(canal)
    setdo, io = _setdo("generator")
    setdo.set_output(2, True)
    io.set_output.assert_called_once_with(2, False)


def test_apagar_siempre_se_permite():
    setdo, io = _setdo("generator")
    setdo.vapor_caldera_off()
    io.set_output.assert_called_once_with(2, False)


def test_mixto_enciende_las_dos():
    setdo, io = _setdo("mixed")
    setdo.vapor_generador_on()
    setdo.vapor_caldera_on()
    assert [c.args for c in io.set_output.call_args_list] == [(1, True), (2, True)]


def test_storage_conserva_la_fuente(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "INSTALLATION_FILE", tmp_path / "perfil.json")
    (tmp_path / "perfil.json").write_text(
        __import__("json").dumps({**_VALIDO, "vapor_source": "generator", "locked": False}),
        encoding="utf-8")
    perfil = storage.load()
    assert perfil.vapor_source == "generator"
    storage.save(perfil)
    assert storage.load().vapor_source == "generator"


def test_storage_sin_fuente_no_escribe_el_campo(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(storage, "INSTALLATION_FILE", tmp_path / "perfil.json")
    (tmp_path / "perfil.json").write_text(json.dumps({**_VALIDO, "locked": False}), encoding="utf-8")
    perfil = storage.load()
    assert perfil.vapor_source is None
    storage.save(perfil)
    assert "vapor_source" not in json.loads((tmp_path / "perfil.json").read_text(encoding="utf-8"))


def test_valor_desconocido_falla_cerrado():
    assert salidas_vapor_permitidas(SimpleNamespace(vapor_source="interno")) == set()
    setdo, io = _setdo("interno")
    setdo.vapor_generador_on()
    setdo.vapor_caldera_on()
    assert [c.args for c in io.set_output.call_args_list] == [(1, False), (2, False)]


def test_salida_bloqueada():
    setdo, _ = _setdo("boiler")
    assert setdo.salida_bloqueada(1) is True
    assert setdo.salida_bloqueada(2) is False

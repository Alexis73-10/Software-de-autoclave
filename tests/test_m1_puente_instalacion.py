"""M1 (tanda 7): el puente del asistente calcula el modelo, ignora el que
manda la QML y no instala equipos de mesa (planeacion_asistente_modelo.md
§3, §4.7 y §6)."""

import json
import sys
from datetime import datetime

import pytest

from autoclave import i18n
from autoclave.installation import storage

pytest.importorskip("PySide6")
from autoclave.ui_qml.bridge import puente_instalacion as pi

AHORA = datetime(2026, 10, 22, 8, 0, 0)


def _datos(**cambios):
    d = {
        "serial_number": "ab-123", "equipment_class": "piso_lab",
        "door_count": 2, "door_type": "advanced", "door_id": 2, "cooling_level": 2,
        "vapor_source": "generator", "capacidad_litros": 45, "tipo_carga": "V",
        "supply_inputs": {}, "temperature_probes": {},
    }
    d.update(cambios)
    return d


def _ok(_s, _c):
    return True


@pytest.fixture
def perfil_tmp(monkeypatch, tmp_path):
    ruta = tmp_path / "installation_profile.json"
    monkeypatch.setattr(storage, "INSTALLATION_FILE", ruta)
    return ruta


def test_clases_solo_de_piso():
    assert [c["valor"] for c in pi.clases_disponibles()] == ["piso", "piso_lab"]


def test_el_puente_calcula_el_modelo():
    p = pi.construir_perfil(_datos(), "X", AHORA, validar_codigo=_ok)
    assert p.model_id == "SPK-SAT 45V2-LAB"
    assert p.capacidad_litros == 45 and p.tipo_carga == "V"


def test_ignora_el_model_id_que_manda_la_qml():
    p = pi.construir_perfil(_datos(model_id="MODELO ESPECIAL"), "X", AHORA, validar_codigo=_ok)
    assert p.model_id == "SPK-SAT 45V2-LAB"


def test_una_puerta_y_piso():
    p = pi.construir_perfil(_datos(equipment_class="piso", door_count=1, capacidad_litros=180,
                                   tipo_carga="H"), "X", AHORA, validar_codigo=_ok)
    assert p.model_id == "SPK-SAT 180H" and p.door_id == 1


def test_capacidad_entera_que_llega_como_float_desde_qml():
    p = pi.construir_perfil(_datos(capacidad_litros=45.0), "X", AHORA, validar_codigo=_ok)
    assert p.capacidad_litros == 45 and isinstance(p.capacidad_litros, int)


@pytest.mark.parametrize("clase", ["mesa_n", "mesa_b", "mesa_b_lab"])
def test_instalar_mesa_es_error_i18n(clase):
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_datos(equipment_class=clase, door_count=1, cooling_level=0),
                            "X", AHORA, validar_codigo=_ok)
    assert str(e.value) == i18n.t("instalacion.error_clase_fuera_alcance")


@pytest.mark.parametrize("litros", [19, 2001, 45.5, "45", True, None, 0])
def test_rechaza_capacidad(litros):
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_datos(capacidad_litros=litros), "X", AHORA, validar_codigo=_ok)
    assert str(e.value) == i18n.t("instalacion.error_capacidad")


@pytest.mark.parametrize("carga", ["v", "X", "", None])
def test_rechaza_tipo_de_carga(carga):
    with pytest.raises(ValueError) as e:
        pi.construir_perfil(_datos(tipo_carga=carga), "X", AHORA, validar_codigo=_ok)
    assert str(e.value) == i18n.t("instalacion.error_tipo_carga")


@pytest.mark.parametrize("puertas", [0, 3])
def test_rechaza_puertas(puertas):
    with pytest.raises(ValueError, match="puertas"):
        pi.construir_perfil(_datos(door_count=puertas), "X", AHORA, validar_codigo=_ok)


def test_el_perfil_escrito_es_valido_y_consistente(perfil_tmp):
    pi.escribir_perfil(pi.construir_perfil(_datos(), "X", validar_codigo=_ok))
    datos = json.loads(perfil_tmp.read_text(encoding="utf-8"))
    assert datos["model_id"] == "SPK-SAT 45V2-LAB"
    assert datos["capacidad_litros"] == 45 and datos["tipo_carga"] == "V"
    assert pi.requiere_instalacion() is False


def test_cargar_un_perfil_de_mesa_existente_no_abre_el_asistente(perfil_tmp, monkeypatch):
    """DECISIÓN SIN CONFIRMAR (spec §3): un perfil de mesa ya instalado se carga."""
    import autoclave.installation.clock_guard as cg
    perfil_tmp.write_text(json.dumps({
        "machine_id": "ACV-2026-M1", "model_id": "MESA-VIEJA", "serial_number": "M1",
        "equipment_class": "mesa_b", "door_count": 1, "door_type": "simple", "cooling_level": 0,
        "door_id": 1, "role": "operator_front", "created_at": "2026-01-01T00:00:00",
        "locked": True}), encoding="utf-8")
    monkeypatch.setattr(cg, "_today", lambda: datetime(2026, 1, 1).date())
    assert pi.requiere_instalacion() is False


def test_slot_vista_previa():
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    puente = pi.PuenteInstalacion(validar_codigo=_ok)
    assert puente.calcularModelo("piso_lab", 2000, "H", 2) == "SPK-SAT 2000H2-LAB"
    assert puente.calcularModelo("piso", 45, "V", 1) == "SPK-SAT 45V"
    assert puente.calcularModelo("piso", 0, "V", 1) == ""          # dato faltante
    assert puente.calcularModelo("piso", 45, "", 1) == ""
    assert puente.calcularModelo("", 45, "V", 1) == ""
    assert puente.calcularModelo("mesa_b", 45, "V", 1) == ""
    assert puente.calcularModelo("piso", 45.5, "V", 1) == ""


def test_puente_instalar_mesa_devuelve_error(perfil_tmp):
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    puente = pi.PuenteInstalacion(validar_codigo=_ok)
    assert puente.validarCodigo("ab-123", "X") is True
    r = puente.instalar(_datos(equipment_class="mesa_b", door_count=1, cooling_level=0))
    assert r == {"ok": False, "error": i18n.t("instalacion.error_clase_fuera_alcance")}
    assert not perfil_tmp.exists()
    r = puente.instalar(_datos(model_id="OTRO"))
    assert r["ok"] is True
    assert json.loads(perfil_tmp.read_text(encoding="utf-8"))["model_id"] == "SPK-SAT 45V2-LAB"

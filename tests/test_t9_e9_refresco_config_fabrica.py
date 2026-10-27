"""D9-13.1 (tanda 9, E9): al actualizar, el ejecutable refresca los archivos de
configuración DE FÁBRICA de la copia persistente (`config/instances/*.yaml` y
`config/global_params.json`), con respaldo previo con fecha, y NUNCA toca
`calibration_modbus.yaml` (antes `calibration.yaml`, T20-03), `correo.json`,
`active_instances.yaml`, `cycles/user`,
`cycles/defecto` ni nada fuera de `programa/` (perfil, BD, asignación de E/S).

D9-7: la entrega ya no trae `cycles/user`; en la primera instalación los
programas editables se siembran como copia de los de fábrica."""
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from autoclave.core.managers import cycle_manager as cm_mod
from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.utils import resources

SRC = Path(__file__).resolve().parents[1] / "src"
INSTANCIA = "instances/ACV-2026-001.yaml"


@pytest.fixture
def exe(tmp_path, monkeypatch):
    """Build congelado simulado con el contenido que empaqueta el .spec de la
    tanda 9: config completa y SOLO cycles/factory."""
    paquete = tmp_path / "meipass"
    shutil.copytree(SRC / "autoclave" / "cycles" / "factory", paquete / "autoclave" / "cycles" / "factory")
    shutil.copytree(SRC / "autoclave" / "config", paquete / "autoclave" / "config",
                    ignore=shutil.ignore_patterns("__pycache__", "*.py"))
    datos = tmp_path / "ProgramData"
    monkeypatch.setattr(sys, "_MEIPASS", str(paquete), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(resources, "raiz_datos_exe", lambda: str(datos))
    monkeypatch.setattr(resources, "_sembradas", set())
    monkeypatch.setattr(cm_mod, "resource_path", resources.resource_path)
    return paquete, datos


def _cfg(datos, rel=""):
    return datos / "programa" / "autoclave" / "config" / rel


def _ciclos(datos, *partes):
    return datos / "programa" / "autoclave" / "cycles" / Path(*partes)


def _respaldos(datos):
    raiz = datos / "programa" / resources.CARPETA_RESPALDOS
    return sorted(p for p in raiz.iterdir() if p.is_dir()) if raiz.exists() else []


def _nuevo_proceso(monkeypatch):
    monkeypatch.setattr(resources, "_sembradas", set())


def _sembrar_todo():
    resources.resource_path("autoclave/config/global_params.json")
    resources.resource_path("autoclave/cycles/factory")


# ── primera instalación ──────────────────────────────────────────────────────

def test_primera_instalacion_siembra_programas_de_usuario_desde_fabrica(exe):
    paquete, datos = exe
    cm = CycleManager()
    cm.load_all_cycles()
    fabrica = sorted(p.name for p in (paquete / "autoclave/cycles/factory").glob("*.json"))
    usuario = sorted(p.name for p in _ciclos(datos, "user").glob("*.json"))
    assert usuario == fabrica
    for nombre in fabrica:
        f = json.loads((paquete / "autoclave/cycles/factory" / nombre).read_text(encoding="utf-8"))
        u = json.loads(_ciclos(datos, "user", nombre).read_text(encoding="utf-8"))
        assert "nombre_clave" not in u          # un nombre cambiado en el hospital se mostraría
        f.pop("nombre_clave", None)
        assert u == f                            # mismos valores que fábrica: sin residuos del banco
    # los 4 programas son editables (de usuario)
    assert {c.source for c in cm.cycles.values()} == {"user"}
    assert len(cm.cycles) == len(fabrica)
    assert not _respaldos(datos)                 # primera vez: nada que respaldar


def test_primera_instalacion_conserva_el_nombre_en_cada_idioma(exe):
    cm = CycleManager()
    cm.load_all_cycles()
    for c in cm.cycles.values():
        assert cm.nombre_clave_de(c)             # cae a la clave del de fábrica


def test_no_se_vuelve_a_sembrar_si_ya_hay_carpeta_de_usuario(exe, monkeypatch):
    _, datos = exe
    CycleManager().load_all_cycles()
    u = _ciclos(datos, "user", "instrumental_134.json")
    d = json.loads(u.read_text(encoding="utf-8"))
    d["marca_hospital"] = 1
    u.write_text(json.dumps(d), encoding="utf-8")
    _ciclos(datos, "user", "liquidos.json").unlink()        # borrado en el hospital
    _nuevo_proceso(monkeypatch)
    CycleManager().load_all_cycles()
    assert json.loads(u.read_text(encoding="utf-8"))["marca_hospital"] == 1
    assert not _ciclos(datos, "user", "liquidos.json").exists()


# ── actualización (B → D) ────────────────────────────────────────────────────

def _instalacion_previa(exe, monkeypatch):
    """Primera ejecución y luego archivos «de la versión anterior» + datos del sitio."""
    paquete, datos = exe
    _sembrar_todo()
    _cfg(datos, INSTANCIA).write_text("io_enabled: {AI: [temp_camara]}\n# VIEJO\n", encoding="utf-8")
    _cfg(datos, "global_params.json").write_text('{"viejo": {"value": 1}}', encoding="utf-8")
    sitio = {
        "calibration_modbus.yaml": "# CALIBRACION-DEL-EQUIPO   (T20-03)\n",
        "correo.json": '{"remitente": "hospital@ejemplo.com"}',
        "active_instances.yaml": "active_instance: ACV-2026-001\n# SITIO\n",
    }
    for nombre, texto in sitio.items():
        _cfg(datos, nombre).write_text(texto, encoding="utf-8")
    shutil.rmtree(_ciclos(datos, "user"))            # el user/ de la B: solo un programa
    _ciclos(datos, "user").mkdir(parents=True)
    _ciclos(datos, "user", "bowe_dick.json").write_text('{"residuo": "modo 4"}', encoding="utf-8")
    _ciclos(datos, "defecto").mkdir(parents=True, exist_ok=True)
    _ciclos(datos, "defecto", "1.json").write_text('{"hospital": 1}', encoding="utf-8")
    fuera = datos / "data" / "asignacion_io.json"
    fuera.parent.mkdir(parents=True)
    fuera.write_text("{}", encoding="utf-8")
    perfil = datos / "installation_profile.json"
    perfil.write_text("{}", encoding="utf-8")
    _nuevo_proceso(monkeypatch)
    return paquete, datos, sitio


def test_actualizacion_refresca_instancias_y_global_params_con_respaldo(exe, monkeypatch):
    paquete, datos, _ = _instalacion_previa(exe, monkeypatch)
    _sembrar_todo()
    for rel in (INSTANCIA, "global_params.json"):
        assert _cfg(datos, rel).read_bytes() == (paquete / "autoclave/config" / rel).read_bytes(), rel
    respaldos = _respaldos(datos)
    assert len(respaldos) == 1
    assert respaldos[0].name[:4].isdigit()       # carpeta con fecha (AAAA-MM-DD_HHMMSS)
    viejo = respaldos[0] / "autoclave" / "config"
    assert "# VIEJO" in (viejo / INSTANCIA).read_text(encoding="utf-8")
    assert (viejo / "global_params.json").read_text(encoding="utf-8") == '{"viejo": {"value": 1}}'
    # el respaldo no queda donde se cargan las instancias
    assert sorted(p.name for p in _cfg(datos, "instances").iterdir()) == ["ACV-2026-001.yaml"]


def test_actualizacion_nunca_toca_datos_del_sitio(exe, monkeypatch):
    _, datos, sitio = _instalacion_previa(exe, monkeypatch)
    _sembrar_todo()
    CycleManager().load_all_cycles()
    for nombre, texto in sitio.items():
        assert _cfg(datos, nombre).read_text(encoding="utf-8") == texto, nombre
    assert _ciclos(datos, "user", "bowe_dick.json").read_text(encoding="utf-8") == '{"residuo": "modo 4"}'
    assert not _ciclos(datos, "user", "liquidos.json").exists()      # no se re-siembra
    assert _ciclos(datos, "defecto", "1.json").read_text(encoding="utf-8") == '{"hospital": 1}'
    assert (datos / "data" / "asignacion_io.json").read_text(encoding="utf-8") == "{}"
    assert (datos / "installation_profile.json").read_text(encoding="utf-8") == "{}"


def test_sin_cambios_no_hay_respaldo(exe, monkeypatch):
    _, datos = exe
    _sembrar_todo()
    _nuevo_proceso(monkeypatch)
    _sembrar_todo()
    assert not _respaldos(datos)


def test_segunda_actualizacion_conserva_el_primer_respaldo(exe, monkeypatch):
    paquete, datos, _ = _instalacion_previa(exe, monkeypatch)
    _sembrar_todo()
    _nuevo_proceso(monkeypatch)
    # otra versión más nueva
    (paquete / "autoclave/config" / INSTANCIA).write_text("io_enabled: {}\n# V3\n", encoding="utf-8")
    monkeypatch.setattr(resources, "_marca_tiempo", lambda: "2099-01-01_000000")
    _sembrar_todo()
    respaldos = _respaldos(datos)
    assert len(respaldos) == 2
    assert "# VIEJO" in (respaldos[0] / "autoclave/config" / INSTANCIA).read_text(encoding="utf-8")
    assert "# V3" in _cfg(datos, INSTANCIA).read_text(encoding="utf-8")


def test_fallo_al_respaldar_no_reemplaza(exe, monkeypatch):
    """Sin respaldo no se reemplaza: queda el archivo anterior (el programa
    sigue funcionando como antes de la actualización)."""
    _, datos, _ = _instalacion_previa(exe, monkeypatch)

    def _falla(*a, **k):
        raise OSError("disco lleno")
    monkeypatch.setattr(resources, "_respaldar", _falla)
    _sembrar_todo()
    assert "# VIEJO" in _cfg(datos, INSTANCIA).read_text(encoding="utf-8")


def test_calibracion_y_correo_nuevos_se_siembran_solo_si_faltan(exe):
    paquete, datos = exe
    _sembrar_todo()
    # T20-03: calibration_modbus.yaml (antes calibration.yaml del serial)
    for nombre in ("calibration_modbus.yaml", "correo.json", "active_instances.yaml"):
        assert _cfg(datos, nombre).read_bytes() == (paquete / "autoclave/config" / nombre).read_bytes()


def test_respaldo_por_ruta_relativa(tmp_path, monkeypatch):
    origen = tmp_path / "a.yaml"
    origen.write_text("x", encoding="utf-8")
    monkeypatch.setattr(resources, "_carpeta_persistente", lambda: str(tmp_path / "programa"))
    destino = resources._respaldar(str(origen), "autoclave/config/instances/a.yaml", "2026-10-23_220000")
    assert Path(destino) == (tmp_path / "programa" / resources.CARPETA_RESPALDOS / "2026-10-23_220000"
                             / "autoclave" / "config" / "instances" / "a.yaml")
    assert Path(destino).read_text(encoding="utf-8") == "x"
    assert os.path.exists(origen)

"""C2 (tanda 3, RB-04.5): con el ejecutable congelado, los programas de usuario
(cycles/user) viven en una carpeta persistente junto a los datos (no en el
directorio temporal del ejecutable), se siembran desde fábrica la primera vez,
se conservan en las actualizaciones y `factory` se refresca siempre (solo
lectura). Un archivo corrupto cae al programa de fábrica con aviso."""

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


@pytest.fixture
def exe(tmp_path, monkeypatch):
    """Simula un build congelado: paquete (MEIPASS) copiado, datos persistentes aparte."""
    paquete = tmp_path / "meipass"
    shutil.copytree(SRC / "autoclave" / "cycles", paquete / "autoclave" / "cycles")
    shutil.copytree(SRC / "autoclave" / "config", paquete / "autoclave" / "config",
                    ignore=shutil.ignore_patterns("instances", "models", "__pycache__"))
    datos = tmp_path / "ProgramData"
    monkeypatch.setattr(sys, "_MEIPASS", str(paquete), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(resources, "raiz_datos_exe", lambda: str(datos))
    monkeypatch.setattr(resources, "_sembradas", set())
    monkeypatch.setattr(cm_mod, "resource_path", resources.resource_path)
    return paquete, datos


def _n(ruta) -> str:
    return os.path.normcase(os.path.normpath(str(ruta)))


def _persistente(datos, *partes):
    return datos / "programa" / "autoclave" / "cycles" / Path(*partes)


def _reiniciar_proceso(monkeypatch):
    monkeypatch.setattr(resources, "_sembradas", set())    # un proceso nuevo (otro arranque)


def test_primera_ejecucion_siembra_fabrica_y_usuario_fuera_del_paquete(exe):
    paquete, datos = exe
    cm = CycleManager()
    cm.load_all_cycles()
    assert {c.id for c in cm.cycles.values()} >= {"134_instrumental", "liquidos"}
    for c in cm.cycles.values():
        assert _n(datos) in _n(c._path) and _n(paquete) not in _n(c._path)       # persistente, no temporal
    assert _persistente(datos, "user", "instrumental_134.json").exists()
    assert _persistente(datos, "factory", "instrumental_134.json").exists()


def test_la_edicion_del_tecnico_sobrevive_a_una_actualizacion(exe, monkeypatch):
    paquete, datos = exe
    CycleManager().load_all_cycles()                                  # primera ejecución
    usuario = _persistente(datos, "user", "instrumental_134.json")
    d = json.loads(usuario.read_text(encoding="utf-8"))
    d["marca_tecnico"] = "editado"
    usuario.write_text(json.dumps(d), encoding="utf-8")
    # actualización: el paquete nuevo trae otro user/ y un factory modificado
    (paquete / "autoclave" / "cycles" / "user" / "instrumental_134.json").write_text(
        json.dumps({**d, "marca_tecnico": "del_paquete_nuevo"}), encoding="utf-8")
    nuevo = {**json.loads((paquete / "autoclave/cycles/user/instrumental_121.json").read_text(encoding="utf-8")),
             "cycle_id": "nuevo_programa", "cycle_number": 9}
    (paquete / "autoclave/cycles/user/nuevo_programa.json").write_text(json.dumps(nuevo), encoding="utf-8")
    fabrica = paquete / "autoclave/cycles/factory/instrumental_134.json"
    f = json.loads(fabrica.read_text(encoding="utf-8"))
    f["marca_fabrica"] = "v2"
    fabrica.write_text(json.dumps(f), encoding="utf-8")

    _reiniciar_proceso(monkeypatch)
    CycleManager().load_all_cycles()
    assert json.loads(usuario.read_text(encoding="utf-8"))["marca_tecnico"] == "editado"   # conservado
    assert _persistente(datos, "user", "nuevo_programa.json").exists()                     # lo nuevo entra
    fab = json.loads(_persistente(datos, "factory", "instrumental_134.json").read_text(encoding="utf-8"))
    assert fab["marca_fabrica"] == "v2"                                                    # fábrica se refresca


def test_fabrica_se_restaura_si_alguien_la_toca(exe, monkeypatch):
    _, datos = exe
    CycleManager().load_all_cycles()
    ruta = _persistente(datos, "factory", "liquidos.json")
    original = ruta.read_text(encoding="utf-8")
    ruta.write_text("{ alterado", encoding="utf-8")
    _reiniciar_proceso(monkeypatch)
    CycleManager().load_all_cycles()
    assert ruta.read_text(encoding="utf-8") == original


def test_archivo_de_usuario_corrupto_cae_a_fabrica_con_aviso(exe, monkeypatch):
    _, datos = exe
    CycleManager().load_all_cycles()
    usuario = _persistente(datos, "user", "instrumental_134.json")
    usuario.write_text('{"cycle_id": "134_instrumental", "parameters": {', encoding="utf-8")  # truncado
    _reiniciar_proceso(monkeypatch)
    cm = CycleManager()
    cm.load_all_cycles()
    ciclo = cm.cycles["134_instrumental"]
    assert ciclo.source == "factory"                       # el de fábrica, íntegro
    assert _n(usuario) in [_n(e) for e in cm.errores_carga]   # el aviso (el arranque degrada con ARR_CICLO_CORRUPTO)
    assert not getattr(ciclo, "danado", None)


def test_usuario_con_valores_fuera_de_catalogo_no_es_ejecutable(exe, monkeypatch):
    _, datos = exe
    CycleManager().load_all_cycles()
    usuario = _persistente(datos, "user", "liquidos.json")
    d = json.loads(usuario.read_text(encoding="utf-8"))
    d["parameters"]["esterilizacion"]["temperatura_esterilizacion"]["value"] = 999
    usuario.write_text(json.dumps(d), encoding="utf-8")
    bak = usuario.with_name(usuario.name + ".bak")
    if bak.exists():
        bak.unlink()
    _reiniciar_proceso(monkeypatch)
    cm = CycleManager()
    cm.load_all_cycles()
    assert cm.cycles["liquidos"].danado            # nunca a un ciclo inválido: queda marcado
    assert _n(usuario) in [_n(e) for e in cm.errores_carga]


def test_el_directorio_persistente_no_es_el_del_paquete(exe):
    paquete, datos = exe
    ruta = resources.resource_path("autoclave/cycles/user")
    assert Path(ruta).is_relative_to(datos) and not Path(ruta).is_relative_to(paquete)
    # lo que no se escribe (imágenes) sigue saliendo del paquete
    assert Path(resources.resource_path("autoclave/images")).is_relative_to(paquete)

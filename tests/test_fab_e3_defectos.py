# tests/test_fab_e3_defectos.py
#
# Modo fábrica, Etapa 3: consolidar_defectos_programas (pieza del cierre de la
# Etapa 5). Carpeta temporal; nunca toca src/autoclave/cycles del repo.

import json
from types import SimpleNamespace

import pytest

from autoclave.core.runtime import fabrica_equipo as fe


def _prog(cid, numero, valor, danado=None):
    return SimpleNamespace(id=cid, name=f"Programa {cid}", number=numero, danado=danado or [],
                           parameters={"esterilizacion": {"tiempo_esterilizacion": {"value": valor}}})


def _cm(*programas):
    return SimpleNamespace(cycles={p.id: p for p in programas})


def _leer(carpeta, nombre):
    return json.loads((carpeta / nombre).read_text(encoding="utf-8"))


@pytest.fixture
def carpeta(tmp_path):
    c = tmp_path / "defecto"
    c.mkdir()
    # defecto viejo de un programa que ya no existe, otro del programa 2 con
    # otro nombre de archivo y un archivo que no es .json
    (c / "programa_9.json").write_text('{"cycle_id": "programa_9", "cycle_number": 9}', encoding="utf-8")
    (c / "viejo_2.json").write_text('{"cycle_id": "instrumental_121", "cycle_number": 2}', encoding="utf-8")
    (c / "notas.txt").write_text("x", encoding="utf-8")
    return c


def test_escribe_un_defecto_por_programa_con_numero_y_borra_los_demas(carpeta):
    cm = _cm(_prog("instrumental_134", 1, 4.0), _prog("instrumental_121", 2, 15.0),
             _prog("sin_numero", None, 1.0), _prog("programa_11", 11, 7.0))
    r = fe.consolidar_defectos_programas(cm, carpeta)
    assert r["escritos"] == ["instrumental_121.json", "instrumental_134.json", "programa_11.json"]
    assert r["borrados"] == ["programa_9.json", "viejo_2.json"]
    assert r["omitidos"] == []
    d = _leer(carpeta, "instrumental_134.json")
    assert d == {"cycle_id": "instrumental_134", "cycle_number": 1,
                 "display_name": "Programa instrumental_134",
                 "parameters": {"esterilizacion": {"tiempo_esterilizacion": {"value": 4.0}}}}
    assert _leer(carpeta, "programa_11.json")["cycle_number"] == 11
    assert sorted(p.name for p in carpeta.iterdir()) == [
        "instrumental_121.json", "instrumental_134.json", "notas.txt", "programa_11.json"]


def test_idempotente(carpeta):
    cm = _cm(_prog("instrumental_134", 1, 4.0), _prog("programa_11", 11, 7.0))
    fe.consolidar_defectos_programas(cm, carpeta)
    antes = {p.name: p.read_bytes() for p in carpeta.iterdir()}
    r = fe.consolidar_defectos_programas(cm, carpeta)
    assert r["borrados"] == []
    assert {p.name: p.read_bytes() for p in carpeta.iterdir()} == antes


def test_valores_vigentes_y_copia_independiente(carpeta):
    p = _prog("instrumental_134", 1, 4.0)
    fe.consolidar_defectos_programas(_cm(p), carpeta)
    p.parameters["esterilizacion"]["tiempo_esterilizacion"]["value"] = 9.0
    assert _leer(carpeta, "instrumental_134.json")["parameters"]["esterilizacion"][
        "tiempo_esterilizacion"]["value"] == 4.0
    fe.consolidar_defectos_programas(_cm(p), carpeta)
    assert _leer(carpeta, "instrumental_134.json")["parameters"]["esterilizacion"][
        "tiempo_esterilizacion"]["value"] == 9.0


def test_programa_danado_conserva_su_defecto(carpeta):
    (carpeta / "liquidos.json").write_text('{"cycle_id": "liquidos", "cycle_number": 3}', encoding="utf-8")
    r = fe.consolidar_defectos_programas(_cm(_prog("liquidos", 3, 1.0, danado=["x"])), carpeta)
    assert r["omitidos"] == ["liquidos"] and "liquidos.json" not in r["escritos"]
    assert _leer(carpeta, "liquidos.json") == {"cycle_id": "liquidos", "cycle_number": 3}


def test_crea_la_carpeta(tmp_path):
    destino = tmp_path / "no" / "existe"
    fe.consolidar_defectos_programas(_cm(_prog("a", 1, 1.0)), destino)
    assert (destino / "a.json").exists()


def test_fallo_de_escritura_no_cambia_nada_ni_deja_temporales(carpeta, monkeypatch):
    antes = {p.name: p.read_bytes() for p in carpeta.iterdir()}
    llamadas = {"n": 0}
    real = fe.os.fsync

    def fsync(fd):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise OSError("disco")
        real(fd)

    monkeypatch.setattr(fe.os, "fsync", fsync)
    with pytest.raises(OSError):
        fe.consolidar_defectos_programas(_cm(_prog("a", 1, 1.0), _prog("b", 2, 2.0)), carpeta)
    assert {p.name: p.read_bytes() for p in carpeta.iterdir()} == antes


def _cargar(raiz):
    from autoclave.core.managers.cycle_manager import CycleManager
    m = CycleManager()
    m.raiz = str(raiz)
    m.load_all_cycles()
    return m


def test_cycle_manager_real(tmp_path):
    """Con un CycleManager real sobre una copia temporal de cycles/: los
    defectos consolidados quedan como defecto de su número al recargar."""
    import shutil
    from pathlib import Path
    ciclos = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "cycles"
    shutil.copytree(ciclos / "factory", tmp_path / "cycles" / "factory")
    (tmp_path / "cycles" / "user").mkdir()
    for f in (ciclos / "user").glob("*.json"):
        shutil.copy2(f, tmp_path / "cycles" / "user" / f.name)
    cm = _cargar(tmp_path)
    carpeta = tmp_path / "cycles" / "defecto"
    r = fe.consolidar_defectos_programas(cm, carpeta)
    assert len(r["escritos"]) >= 5
    cm2 = _cargar(tmp_path)
    for nombre in r["escritos"]:
        d = _leer(carpeta, nombre)
        assert cm2.defecto(d["cycle_number"]).id == d["cycle_id"]
        assert cm2.defectos[d["cycle_number"]].parameters == cm.cycles[d["cycle_id"]].parameters

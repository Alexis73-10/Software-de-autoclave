"""PRI-05: la siembra al cargar de los programas de fábrica que faltan en
cycles/user (un equipo actualizado recibe Prion; ver utils/resources)."""
import json
import os
import shutil
import stat
from pathlib import Path

import pytest

from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.utils import resources

pytestmark = pytest.mark.req("PRI")

REPO = Path(__file__).resolve().parents[1] / "src" / "autoclave" / "cycles"
LEGADOS = ["bowe_dick.json", "instrumental_121.json", "instrumental_134.json",
           "liquidos.json", "textiles.json"]


@pytest.fixture
def raiz(tmp_path):
    """Equipo ya instalado: fábrica con los 6 programas, usuario con los 5
    anteriores. Devuelve la carpeta `cycles` (el CycleManager usa su padre)."""
    tmp_path = tmp_path / "cycles"
    tmp_path.mkdir()
    shutil.copytree(REPO / "factory", tmp_path / "factory")
    (tmp_path / "user").mkdir()
    for n in LEGADOS:
        shutil.copy(REPO / "user" / n, tmp_path / "user" / n)
    return tmp_path


def _cargar(raiz):
    cm = CycleManager()
    cm.raiz = str(raiz.parent)
    cm.load_all_cycles()
    return cm


def test_equipo_actualizado_recibe_prion_editable_y_sin_nombre_clave(raiz):
    cm = _cargar(raiz)
    destino = raiz / "user" / "prion.json"
    assert destino.exists()
    datos = json.loads(destino.read_text(encoding="utf-8"))
    assert "nombre_clave" not in datos
    c = cm.cycles["prion"]
    assert c.number == 6 and c.source == "user"
    assert cm.nombre_clave_de(c) == "ciclos_fabrica.prion.nombre"   # cae a la de fábrica
    assert sorted(x.number for x in cm.cycles.values()) == [1, 2, 3, 4, 5, 6]


def test_sale_en_seleccionables(raiz, monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from tests.helpers.backend_doble import cargar_servidor
    cm = _cargar(raiz)
    ctx = MagicMock()
    ctx.sin_base_de_datos = True
    ctx.cap = SimpleNamespace(has_liquids=True)
    ctx.cycle_manager = cm
    loop = MagicMock()
    loop.bloqueo_maquina.return_value = nullcontext()
    loop._motivo_no_cambiar_ciclo.return_value = None
    loop.cycle = SimpleNamespace(id="134_instrumental")
    ctx.control_loop = loop
    srv, _ = cargar_servidor(ctx)
    r = TestClient(srv.app).get("/programas/seleccionables")
    # sembrado DESHABILITADO: no se ofrece en Preciclo ni se puede iniciar
    assert [p["numero"] for p in r.json()["programas"]] == [1, 2, 3, 4, 5]
    assert cm.cycles["prion"].habilitado is False
    rs = TestClient(srv.app).post("/cycle/select", json={"cycle_id": "prion", "origen": "puerta_1"})
    assert rs.status_code == 409 and "programa_deshabilitado" in rs.text
    # un técnico lo habilita tras validar el proceso: ya sale y se puede elegir
    from autoclave.core.managers import gestion_programas as gp
    assert gp.fijar_habilitado(cm, 6, True, None) == (False, True)
    r = TestClient(srv.app).get("/programas/seleccionables")
    assert [p["numero"] for p in r.json()["programas"]] == [1, 2, 3, 4, 5, 6]
    assert next(p for p in r.json()["programas"] if p["numero"] == 6)["cycle_id"] == "prion"
    rs = TestClient(srv.app, raise_server_exceptions=False).post(
        "/cycle/select", json={"cycle_id": "prion", "origen": "puerta_1"})
    assert "programa_deshabilitado" not in rs.text


def test_no_pisa_un_prion_editado(raiz):
    editado = json.loads((REPO / "user" / "prion.json").read_text(encoding="utf-8"))
    editado["parameters"]["esterilizacion"]["tiempo_esterilizacion"]["value"] = 45
    (raiz / "user" / "prion.json").write_text(json.dumps(editado), encoding="utf-8")
    _cargar(raiz)
    de_disco = json.loads((raiz / "user" / "prion.json").read_text(encoding="utf-8"))
    assert de_disco["parameters"]["esterilizacion"]["tiempo_esterilizacion"]["value"] == 45


def test_no_pisa_otro_programa_con_el_mismo_numero(raiz):
    otro = json.loads((REPO / "user" / "textiles.json").read_text(encoding="utf-8"))
    otro["cycle_id"], otro["cycle_number"] = "mio", 6
    (raiz / "user" / "mio.json").write_text(json.dumps(otro), encoding="utf-8")
    _cargar(raiz)
    assert not (raiz / "user" / "prion.json").exists()


def test_idempotente_y_no_recrea_lo_borrado(raiz):
    assert resources.sembrar_faltantes_usuario(str(raiz)) == ["prion.json"]
    assert resources.sembrar_faltantes_usuario(str(raiz)) == []
    (raiz / "user" / "prion.json").unlink()          # el hospital lo borra
    assert resources.sembrar_faltantes_usuario(str(raiz)) == []
    assert not (raiz / "user" / "prion.json").exists()
    assert "prion" in (raiz / "user" / resources.MARCA_FABRICA_VISTOS).read_text().split()


def test_un_legado_borrado_no_se_recrea_sin_marca(raiz):
    (raiz / "user" / "textiles.json").unlink()
    resources.sembrar_faltantes_usuario(str(raiz))
    assert not (raiz / "user" / "textiles.json").exists()


def test_la_marca_no_se_toma_por_un_programa(raiz):
    cm = _cargar(raiz)
    assert cm.errores_carga == []
    assert (raiz / "user" / resources.MARCA_FABRICA_VISTOS).exists()


def test_sin_directorio_de_usuario_no_rompe_ni_lo_crea(raiz):
    shutil.rmtree(raiz / "user")
    assert resources.sembrar_faltantes_usuario(str(raiz)) == []
    assert not (raiz / "user").exists()
    cm = _cargar(raiz)
    assert sorted(c.number for c in cm.cycles.values()) == [1, 2, 3, 4, 5, 6]   # fábrica


def test_sin_fabrica_no_rompe(tmp_path):
    (tmp_path / "user").mkdir()
    assert resources.sembrar_faltantes_usuario(str(tmp_path)) == []


def test_usuario_no_escribible_no_rompe_y_reintenta(raiz, monkeypatch):
    def falla(*a, **k):
        raise PermissionError("solo lectura")
    monkeypatch.setattr(resources.os, "replace", falla)
    assert resources.sembrar_faltantes_usuario(str(raiz)) == []
    monkeypatch.undo()
    assert not (raiz / "user" / "prion.json").exists()
    assert not (raiz / "user" / resources.MARCA_FABRICA_VISTOS).exists()
    assert resources.sembrar_faltantes_usuario(str(raiz)) == ["prion.json"]   # reintenta


def test_programa_de_fabrica_ilegible_no_rompe(raiz):
    (raiz / "factory" / "roto.json").write_text("{no es json", encoding="utf-8")
    assert resources.sembrar_faltantes_usuario(str(raiz)) == ["prion.json"]


def test_equipo_nuevo_igual_que_antes(tmp_path, monkeypatch):
    """Primera instalación (sin cycles/user): la siembra inicial copia los 6 y
    la de faltantes no agrega ni cambia nada."""
    paquete, datos = tmp_path / "paquete", tmp_path / "datos"
    shutil.copytree(REPO / "factory", paquete / "autoclave" / "cycles" / "factory")
    monkeypatch.setattr(resources.sys, "_MEIPASS", str(paquete), raising=False)
    monkeypatch.setattr(resources, "_carpeta_persistente", lambda: str(datos))
    monkeypatch.setattr(resources, "_sembradas", set())
    resources._sembrar("autoclave/cycles")
    usuario = datos / "autoclave" / "cycles" / "user"
    assert sorted(p.name for p in usuario.glob("*.json")) == sorted(
        p.name for p in (REPO / "factory").glob("*.json"))
    assert "prion" in (usuario / resources.MARCA_FABRICA_VISTOS).read_text().split()
    assert resources.sembrar_faltantes_usuario(str(datos / "autoclave" / "cycles")) == []
    # y si el hospital borra Prion, no vuelve
    (usuario / "prion.json").unlink()
    assert resources.sembrar_faltantes_usuario(str(datos / "autoclave" / "cycles")) == []


# ── revisión de seguridad: ALTA-1, MEDIA-2, BAJA-5, BAJA-6 ────────────────

def _programa_usuario_con_6(raiz, nombre="mio"):
    otro = json.loads((REPO / "user" / "textiles.json").read_text(encoding="utf-8"))
    otro["cycle_id"], otro["cycle_number"] = nombre, 6
    (raiz / "user" / f"{nombre}.json").write_text(json.dumps(otro), encoding="utf-8")


def test_programa_del_hospital_con_el_6_conserva_numero_y_defecto(raiz):
    """ALTA-1: con Prion de fábrica (6) y un programa de usuario con el 6, el
    del hospital conserva número y defecto; el de fábrica cede."""
    _programa_usuario_con_6(raiz)
    (raiz / "defecto").mkdir()
    d = json.loads((raiz / "user" / "mio.json").read_text(encoding="utf-8"))
    d["display_name"] = "defecto del hospital"
    (raiz / "defecto" / "mio.json").write_text(json.dumps(d), encoding="utf-8")
    cm = _cargar(raiz)
    assert cm.cycles["mio"].number == 6 and cm.cycles["mio"].source == "user"
    assert cm.cycles["prion"].number is None
    assert cm.fabrica.get(6) is None
    assert cm.defecto(6).name == "defecto del hospital"
    assert not (raiz / "user" / "prion.json").exists()


def test_programa_del_hospital_con_el_6_sin_defecto_no_devuelve_prion(raiz):
    _programa_usuario_con_6(raiz)
    cm = _cargar(raiz)
    assert cm.cycles["mio"].number == 6
    assert cm.defecto(6) is None


def test_dos_programas_de_usuario_repetidos_siguen_perdiendo_el_numero(raiz):
    _programa_usuario_con_6(raiz, "a")
    _programa_usuario_con_6(raiz, "b")
    cm = _cargar(raiz)
    assert cm.cycles["a"].number is None and cm.cycles["b"].number is None
    assert cm.cycles["prion"].number is None      # sin número: no hay conflicto que ganar


def test_fabrica_sin_conflicto_conserva_su_numero_y_su_defecto(raiz):
    cm = _cargar(raiz)
    assert cm.fabrica[6].id == "prion" and cm.cycles["prion"].number == 6


def test_numero_usado_y_borrado_no_se_reutiliza(raiz):
    (raiz / "user" / "numeros_usados.json").write_text("[6]", encoding="utf-8")
    assert resources.sembrar_faltantes_usuario(str(raiz)) == []
    assert not (raiz / "user" / "prion.json").exists()


def test_numeros_usados_ilegible_no_siembra(raiz):
    (raiz / "user" / "numeros_usados.json").write_text("{roto", encoding="utf-8")
    assert resources.sembrar_faltantes_usuario(str(raiz)) == []


def test_json_de_usuario_ilegible_no_siembra_y_reintenta(raiz):
    (raiz / "user" / "roto.json").write_text("{no es json", encoding="utf-8")
    assert resources.sembrar_faltantes_usuario(str(raiz)) == []
    assert not (raiz / "user" / "prion.json").exists()
    assert not (raiz / "user" / resources.MARCA_FABRICA_VISTOS).exists()
    (raiz / "user" / "roto.json").unlink()
    assert resources.sembrar_faltantes_usuario(str(raiz)) == ["prion.json"]


def test_fsync_antes_de_reemplazar(raiz, monkeypatch):
    llamadas = []
    real = os.fsync
    monkeypatch.setattr(resources.os, "fsync", lambda fd: (llamadas.append(fd), real(fd))[1])
    assert resources.sembrar_faltantes_usuario(str(raiz)) == ["prion.json"]
    assert len(llamadas) == 2       # el programa sembrado y la marca


def test_se_siembra_deshabilitado_tal_cual_y_habilitado_no_se_pisa(raiz):
    assert resources.sembrar_faltantes_usuario(str(raiz)) == ["prion.json"]
    destino = raiz / "user" / "prion.json"
    assert json.loads(destino.read_text(encoding="utf-8"))["habilitado"] is False
    cm = _cargar(raiz)
    from autoclave.core.managers import gestion_programas as gp
    gp.fijar_habilitado(cm, 6, True, None)               # el técnico lo habilita
    assert json.loads(destino.read_text(encoding="utf-8"))["habilitado"] is True
    assert resources.sembrar_faltantes_usuario(str(raiz)) == []
    assert _cargar(raiz).cycles["prion"].habilitado is True


def test_equipo_nuevo_siembra_prion_deshabilitado(tmp_path, monkeypatch):
    paquete, datos = tmp_path / "paquete", tmp_path / "datos"
    shutil.copytree(REPO / "factory", paquete / "autoclave" / "cycles" / "factory")
    monkeypatch.setattr(resources.sys, "_MEIPASS", str(paquete), raising=False)
    monkeypatch.setattr(resources, "_carpeta_persistente", lambda: str(datos))
    monkeypatch.setattr(resources, "_sembradas", set())
    resources._sembrar("autoclave/cycles")
    d = json.loads((datos / "autoclave" / "cycles" / "user" / "prion.json").read_text(encoding="utf-8"))
    assert d["habilitado"] is False

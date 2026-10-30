"""Etapa VER: fuente única de versión (VER-01..05) y cálculos del script de
entrega (§2.3, D-VER-3). Instrucción: docs/mis_plans/instruccion_claude_code_versionado.md."""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from autoclave import _version as ver

RAIZ = Path(__file__).resolve().parents[1]


def _cargar(nombre: str):
    ruta = RAIZ / "tools" / "entrega" / f"{nombre}.py"
    sys.path.insert(0, str(ruta.parent))
    spec = importlib.util.spec_from_file_location(f"ver_{nombre}", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


ce = _cargar("compilar_entrega")
ic = _cargar("info_compilacion")


# ── D-VER-3: cálculo de N ────────────────────────────────────────────────────

@pytest.mark.req("VER-D3")
@pytest.mark.parametrize("etiquetas, n", [
    ([], 1),
    (["v1.0.0-alpha.9", "v1.0.0-alpha.10"], 11),            # orden numérico, no de texto
    (["v1.0.0-alpha.10", "v1.0.0-alpha.9", "v1.0.0-alpha.2"], 11),
    (["inst-2026-10-24-i", "archivo/tanda-3", "v1.0.0-beta.4", "v1.0.0-rc.1", "v1.0.0"], 1),
    (["inst-2026-10-24-i", "v1.0.0-alpha.3", "v1.0.0-beta.7"], 4),
    (["v1.0.0-alpha.3-bis", "xv1.0.0-alpha.8", "v2.0.0-alpha.5"], 1),
])
def test_calculo_de_n(etiquetas, n):
    assert ce.calcular_n(etiquetas) == n


# ── SemVer <-> PEP 440 y AppVerNum (§2.3) ───────────────────────────────────

@pytest.mark.parametrize("semver, pep440", [
    ("1.0.0-alpha.1", "1.0.0a1"), ("1.0.0-alpha.10", "1.0.0a10"), ("1.0.0-beta.2", "1.0.0b2"),
    ("1.0.0-rc.3", "1.0.0rc3"), ("1.0.0", "1.0.0"), ("1.0.0-alpha.0", "1.0.0a0"),
])
def test_semver_pep440_ida_y_vuelta(semver, pep440):
    assert ver.semver_a_pep440(semver) == pep440
    assert ver.pep440_a_semver(pep440) == semver


@pytest.mark.parametrize("malo", ["1.0", "1.0.0-alpha", "1.0.0-gamma.1", "v1.0.0-alpha.1", "", None])
def test_semver_fuera_del_esquema(malo):
    with pytest.raises(ValueError):
        ver.semver_a_pep440(malo)


@pytest.mark.parametrize("semver, num", [
    ("1.0.0-alpha.1", "1.0.0.1001"), ("1.0.0-beta.2", "1.0.0.2002"), ("1.0.0-rc.3", "1.0.0.3003"),
    ("1.0.0", "1.0.0.9000"), ("1.0.0-alpha.999", "1.0.0.1999"),
])
def test_app_ver_num(semver, num):
    assert ce.app_ver_num(semver) == num


def test_app_ver_num_supera_a_la_compilacion_i():
    # La I instalada es 1.0.0.9: alpha.1 debe ser mayor para que el Setup actualice
    assert int(ce.app_ver_num("1.0.0-alpha.1").split(".")[3]) > 9


@pytest.mark.parametrize("semver", ["1.0.0-alpha.1000", "1.0.0-alpha.0"])
def test_app_ver_num_rechaza_n_fuera_de_rango(semver):
    with pytest.raises(ValueError):
        ce.app_ver_num(semver)


def test_reescribir_version_solo_cambia_las_dos_lineas():
    texto = (RAIZ / "src" / "autoclave" / "_version.py").read_text(encoding="utf-8")
    # una versión que nunca es la vigente (con alpha.7 ya entregada, la prueba
    # comparaba el archivo consigo mismo: tanda 21)
    nuevo = ce.reescribir_version(texto, "1.0.0-alpha.999")
    assert '__version__ = "1.0.0a999"' in nuevo and 'VERSION_SEMVER = "1.0.0-alpha.999"' in nuevo
    distintas = [(a, b) for a, b in zip(texto.splitlines(), nuevo.splitlines()) if a != b]
    assert len(distintas) == 2 and len(texto.splitlines()) == len(nuevo.splitlines())
    with pytest.raises(ValueError):
        ce.reescribir_version("x = 1\n", "1.0.0-alpha.7")


# ── VER-01/02: fuente única coherente ────────────────────────────────────────

@pytest.mark.req("VER-01")
def test_version_coherente_en_las_dos_formas():
    assert ver.semver_a_pep440(ver.VERSION_SEMVER) == ver.__version__


@pytest.mark.req("VER-02")
def test_pyproject_toma_la_version_del_modulo():
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^dynamic = \["version"\]', texto, re.M)
    assert not re.search(r'^version\s*=\s*"', texto, re.M)
    assert 'version = {attr = "autoclave._version.__version__"}' in texto


@pytest.mark.req("VER-03")
def test_nadie_lee_la_version_de_los_metadatos():
    patron = re.compile(r"""version\(\s*["']autoclave["']\s*\)""")
    culpables = [p.relative_to(RAIZ).as_posix() for p in (RAIZ / "src").rglob("*.py")
                 if patron.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert culpables == []


@pytest.mark.req("VER-03")
def test_nadie_mas_escribe_la_version_a_mano():
    patron = re.compile(r"""^\s*(__version__|VERSION_SEMVER)\s*=""", re.M)
    sitios = [p.relative_to(RAIZ).as_posix() for p in (RAIZ / "src").rglob("*.py")
              if patron.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert sitios == ["src/autoclave/_version.py"]


# ── VER-04: formato mostrado ─────────────────────────────────────────────────

def _info(etiqueta="v1.0.0-alpha.3", sucio=False, commit="1a2b3c4"):
    return {"commit": commit, "etiqueta": etiqueta, "fecha_utc": "2026-10-25T10:00:00Z", "sucio": sucio}


@pytest.mark.req("VER-04")
def test_formato_entrega():
    assert ver.version_mostrada(_info(), "1.0.0-alpha.3") == "1.0.0-alpha.3"
    assert ver.version_completa(_info(), "1.0.0-alpha.3") == "1.0.0-alpha.3 (1a2b3c4)"


@pytest.mark.req("VER-04")
def test_formato_verificacion_nunca_parece_entrega():
    assert ver.version_mostrada(_info(etiqueta=None), "1.0.0-alpha.3") == "1.0.0-alpha.4.dev+g1a2b3c4"
    assert ver.version_completa(_info(etiqueta=None), "1.0.0-alpha.3") == "1.0.0-alpha.4.dev+g1a2b3c4"
    # etiqueta de entrega pero árbol sucio, o etiqueta de otra versión: verificación
    assert ver.version_mostrada(_info(sucio=True), "1.0.0-alpha.3") == "1.0.0-alpha.4.dev+g1a2b3c4.sucio"
    assert ver.version_mostrada(_info(etiqueta="v1.0.0-alpha.2"), "1.0.0-alpha.3") == \
        "1.0.0-alpha.4.dev+g1a2b3c4"
    # sin entregas todavía (alpha.0): la primera verificación apunta a alpha.1
    assert ver.version_mostrada(_info(etiqueta=None), "1.0.0-alpha.0") == "1.0.0-alpha.1.dev+g1a2b3c4"


@pytest.mark.req("VER-04")
def test_formato_desde_fuente():
    assert ver.version_mostrada(None, "1.0.0-alpha.3") == "1.0.0-alpha.3+fuente"
    assert ver.version_completa(None, "1.0.0-alpha.3") == "1.0.0-alpha.3+fuente"


def test_desde_fuente_ignora_un_build_info_que_haya_quedado(monkeypatch):
    # sys.frozen ausente (pruebas): aunque exista _build_info.py no cuenta
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert ver.version_mostrada().endswith("+fuente")


def test_congelado_lee_build_info(monkeypatch):
    import types
    falso = types.ModuleType("autoclave._build_info")
    falso.COMMIT, falso.ETIQUETA, falso.FECHA_UTC, falso.SUCIO = "abcdef1", f"v{ver.VERSION_SEMVER}", "x", False
    monkeypatch.setitem(sys.modules, "autoclave._build_info", falso)
    import autoclave
    monkeypatch.setattr(autoclave, "_build_info", falso, raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert ver.version_mostrada() == ver.VERSION_SEMVER
    assert ver.version_completa() == f"{ver.VERSION_SEMVER} (abcdef1)"


# ── VER-04: _build_info.py ───────────────────────────────────────────────────

def test_estado_arbol_clasifica():
    porcelana = (" M src/autoclave/x.py\nA  tools/y.py\n?? src/autoclave/nuevo.py\n"
                 "?? packaging/z.spec\n?? data/a.json\n?? docs/informes/b.md\n"
                 '?? "src/autoclave/images/icono autoclave.jpg"\n')
    cambiados, producto, otros = ic.estado_arbol(porcelana)
    assert cambiados == ["src/autoclave/x.py", "tools/y.py"]
    assert producto == ["src/autoclave/nuevo.py", "packaging/z.spec", "src/autoclave/images/icono autoclave.jpg"]
    assert otros == ["data/a.json", "docs/informes/b.md"]


def test_texto_build_info_se_puede_importar():
    d = {"commit": "1a2b3c4", "etiqueta": None, "fecha_utc": "2026-10-25T10:00:00Z", "sucio": True}
    espacio = {}
    exec(ic.texto_build_info(d), espacio)
    assert (espacio["COMMIT"], espacio["ETIQUETA"], espacio["SUCIO"]) == ("1a2b3c4", None, True)


def test_build_info_no_se_versiona():
    assert "/src/autoclave/_build_info.py" in (RAIZ / ".gitignore").read_text(encoding="utf-8")


@pytest.mark.parametrize("spec", ["Autoclave", "AutoclaveBackend", "AutoclaveSettings"])
def test_los_spec_del_autoclave_generan_build_info(spec):
    texto = (RAIZ / "packaging" / f"{spec}.spec").read_text(encoding="utf-8")
    assert "generar_build_info(RAIZ)" in texto and "'autoclave._build_info'" in texto


def test_el_generador_queda_fuera_del_esquema():
    assert "build_info" not in (RAIZ / "packaging" / "GeneradorCodigos.spec").read_text(encoding="utf-8")


# ── VER-05: dónde se ve ──────────────────────────────────────────────────────

@pytest.mark.req("VER-05")
def test_los_sitios_usan_la_version_completa(monkeypatch):
    from tests.helpers.backend_doble import cargar_servidor, modulo_backend
    cargar_servidor()
    respaldo = modulo_backend("rutas.respaldo")
    from autoclave.devices.printer import arranque_equipo
    from autoclave.services.domain.logging import cycle_logger
    from autoclave.ui_qml.bridge import info_equipo
    monkeypatch.setattr(ver, "version_completa", lambda: "1.0.0-alpha.5 (1a2b3c4)")
    assert respaldo._version_sw() == "1.0.0-alpha.5 (1a2b3c4)"
    assert arranque_equipo._version() == "1.0.0-alpha.5 (1a2b3c4)"
    assert cycle_logger._software_version() == "1.0.0-alpha.5 (1a2b3c4)"
    assert info_equipo.version_software() == "1.0.0-alpha.5 (1a2b3c4)"


@pytest.mark.req("VER-05")
def test_get_system_info_trae_la_version(monkeypatch):
    from tests.helpers.backend_doble import cargar_servidor, modulo_backend
    cargar_servidor()
    sistema = modulo_backend("rutas.sistema")
    monkeypatch.setattr(ver, "version_completa", lambda: "1.0.0-alpha.5 (1a2b3c4)")
    assert sistema.get_system_info()["software"]["version"] == "1.0.0-alpha.5 (1a2b3c4)"


def test_respaldo_compara_la_version_mayor():
    from autoclave.core.runtime import respaldo as rp
    assert rp.version_mayor("1.0.0-alpha.2.dev+g1a2b3c4") == rp.version_mayor("1.0.0-alpha.1 (abc)") == "1"


@pytest.mark.parametrize("valor, lineas", [
    ("1.0.0-alpha.1", ["Software: 1.0.0-alpha.1"]),
    ("1.0.0-alpha.1 (1a2b3c4)", ["Software:", "1.0.0-alpha.1 (1a2b3c4)"]),
    ("1.0.0-alpha.12.dev+g1a2b3c4.sucio", ["Software:", "1.0.0-alpha.12.dev", "+g1a2b3c4.sucio"]),
])
def test_ticket_de_ciclo_no_corta_la_version(valor, lineas):
    from autoclave.services.domain.logging.ticket_formatter import ANCHO_TICKET, lineas_version
    assert lineas_version("Software", valor) == lineas
    assert all(len(l) <= ANCHO_TICKET for l in lineas)


def test_ticket_de_arranque_no_corta_la_version():
    from autoclave.devices.printer import startup_ticket as st
    corta = st._lineas_software("Software", "1.0.0-alpha.1 (1a2b3c4)")
    assert corta == [f"{'Software':<16}v1.0.0-alpha.1 (1a2b3c4)"]
    larga = st._lineas_software("Software", "1.0.0-alpha.12.dev+g1a2b3c4.sucio")
    assert larga == ["Software", "  v1.0.0-alpha.12.dev+g1a2b3c4.sucio"]
    assert all(len(l) <= st._W for l in corta + larga)


def test_escribir_version_sin_arrancar_nada(tmp_path):
    from autoclave import exe_unico
    salida = tmp_path / "v.json"
    assert exe_unico.main(["--escribir-version", str(salida)]) == 0
    datos = json.loads(salida.read_text(encoding="utf-8"))
    assert datos["version_semver"] == ver.VERSION_SEMVER
    assert datos["mostrada"] == f"{ver.VERSION_SEMVER}+fuente" and datos["congelado"] is False

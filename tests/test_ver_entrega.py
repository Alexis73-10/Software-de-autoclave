"""Etapa VER §3: verificaciones previas (§2.1) con git simulado y secuencia de
entrega (§2.2) sobre un repositorio git temporal, con los pasos de compilación
sustituidos: un fallo en el paso 5 deja el árbol y las etiquetas como antes."""
import subprocess
from pathlib import Path

import pytest

from tests.test_ver_version import RAIZ, ce, ic


# ── §2.1 verificaciones previas con git simulado ─────────────────────────────

def _git_falso(rama="dev", porcelana="", local="a" * 40, remota="a" * 40):
    def git(*args):
        if args[:2] == ("rev-parse", "--abbrev-ref"):
            return rama + "\n"
        if args[0] == "status":
            return porcelana
        if args == ("rev-parse", "dev"):
            return local + "\n"
        if args == ("rev-parse", "origin/dev"):
            return remota + "\n"
        raise AssertionError(f"git inesperado: {args}")
    return git


def _suite(ok=True):
    llamadas = []
    def correr():
        llamadas.append(1)
        return ok, "7834 passed" if ok else "2 failed"
    return correr, llamadas


@pytest.mark.req("VER-D4")
def test_todo_bien_no_bloquea():
    correr, llamadas = _suite()
    p = ce.verificaciones_previas(_git_falso(), correr)
    assert p.errores == [] and p.avisos == [] and llamadas == [1]


@pytest.mark.req("VER-D4")
def test_rama_distinta_de_dev_bloquea():
    correr, llamadas = _suite()
    p = ce.verificaciones_previas(_git_falso(rama="tanda-16"), correr)
    assert any("tanda-16" in e for e in p.errores)
    assert llamadas == []          # sin correr la suite


@pytest.mark.req("VER-D4")
@pytest.mark.parametrize("porcelana", [" M src/autoclave/x.py\n", "M  README.md\n", "A  tools/y.py\n"])
def test_archivo_versionado_modificado_bloquea(porcelana):
    p = ce.verificaciones_previas(_git_falso(porcelana=porcelana), _suite()[0])
    assert any("modificados" in e for e in p.errores)


@pytest.mark.req("VER-D4")
@pytest.mark.parametrize("ruta", ["src/autoclave/config/calibration.yaml.bak", "packaging/x.spec",
                                  "tools/instalador/a.iss", "Hardware/placa.txt"])
def test_sin_versionar_en_el_producto_bloquea(ruta):
    p = ce.verificaciones_previas(_git_falso(porcelana=f"?? {ruta}\n"), _suite()[0])
    assert any(ruta in e for e in p.errores)


def test_sin_versionar_fuera_del_producto_solo_avisa():
    p = ce.verificaciones_previas(
        _git_falso(porcelana="?? data/correo_equipo.json\n?? docs/informes/x.md\n"), _suite()[0])
    assert p.errores == [] and any("data/correo_equipo.json" in a for a in p.avisos)


def test_suite_roja_bloquea():
    p = ce.verificaciones_previas(_git_falso(), _suite(ok=False)[0])
    assert any("suite" in e for e in p.errores)


def test_dev_distinto_de_origin_solo_avisa():
    p = ce.verificaciones_previas(_git_falso(remota="b" * 40), _suite()[0])
    assert p.errores == [] and any("origin/dev" in a for a in p.avisos)


def test_herramienta_ausente_bloquea():
    p = ce.verificaciones_previas(_git_falso(), _suite()[0], existe=lambda r: False,
                                  herramientas=[("ISCC.exe", "C:/no/ISCC.exe")])
    assert any("ISCC.exe" in e for e in p.errores)


# ── §2.2 secuencia y reversión con un repositorio temporal ───────────────────

def _git(raiz, *args):
    return ic.git(raiz, *args)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / "src" / "autoclave").mkdir(parents=True)
    (r / "docs" / "versiones").mkdir(parents=True)
    (r / "src" / "autoclave" / "_version.py").write_bytes(
        (RAIZ / "src" / "autoclave" / "_version.py").read_bytes())
    (r / "docs" / "versiones" / "HISTORIAL_VERSIONES.md").write_bytes(
        (RAIZ / "docs" / "versiones" / "HISTORIAL_VERSIONES.md").read_bytes())
    (r / ".gitignore").write_text("/src/autoclave/_build_info.py\n/data/\n", encoding="utf-8")
    _git(r, "init", "-q", "-b", "dev")
    _git(r, "config", "user.email", "prueba@example.com")
    _git(r, "config", "user.name", "Prueba")
    _git(r, "config", "core.autocrlf", "false")
    _git(r, "add", "-A")
    _git(r, "commit", "-q", "-m", "base")
    _git(r, "tag", "inst-2026-10-24-i")
    (r / "notas.txt").write_text("x", encoding="utf-8")
    _git(r, "add", "notas.txt")
    _git(r, "commit", "-q", "-m", "feat: algo nuevo")
    (r / "data").mkdir()
    (r / "data" / "local.json").write_text("{}", encoding="utf-8")   # ignorado, se conserva
    return r


def _foto(r: Path):
    return {"head": _git(r, "rev-parse", "HEAD").strip(),
            "etiquetas": _git(r, "tag", "--list").split(),
            "estado": _git(r, "status", "--porcelain", "--untracked-files=all", "--ignored"),
            "version": (r / "src" / "autoclave" / "_version.py").read_bytes(),
            "historial": (r / "docs" / "versiones" / "HISTORIAL_VERSIONES.md").read_bytes(),
            "build_info": ((r / ic.ARCHIVO).read_bytes() if (r / ic.ARCHIVO).exists() else None)}


def _bien(ctx):
    pass


def _escribe_build_info(ctx):
    (ctx.raiz / ic.ARCHIVO).write_text("COMMIT = 'x'\n", encoding="utf-8")


def _falla(ctx):
    raise ce.FalloPaso("simulado: el .exe no reporta la versión")


def _crea_carpeta(ctx):
    ctx.carpeta = ctx.raiz / "entrega" / f"{ctx.etiqueta}_{ctx.fecha}"
    ctx.carpeta.mkdir(parents=True)


def _entregar(r, pasos):
    return ce.entregar(r, "python", "ISCC.exe", pasos=pasos, git=lambda *a: _git(r, *a))


@pytest.mark.req("VER-09")
@pytest.mark.parametrize("build_info_previo", [None, b"COMMIT = 'viejo'\n"])
def test_fallo_en_el_paso_5_deja_todo_como_antes(repo, build_info_previo):
    if build_info_previo is not None:
        (repo / ic.ARCHIVO).write_bytes(build_info_previo)
    antes = _foto(repo)
    pasos = [("3 compilar", _escribe_build_info), ("4 neutra", _bien), ("5 versión del .exe", _falla),
             ("6 Inno Setup", _bien), ("7 carpeta", _bien)]
    assert _entregar(repo, pasos) == 1
    assert _foto(repo) == antes
    assert (repo / "data" / "local.json").exists()


def test_fallo_tras_crear_la_carpeta_la_aparta_sin_borrarla(repo):
    antes = _foto(repo)
    pasos = [("3", _bien), ("6", _crea_carpeta), ("7", _falla)]
    assert _entregar(repo, pasos) == 1
    assert _foto(repo)["head"] == antes["head"] and _foto(repo)["etiquetas"] == antes["etiquetas"]
    apartadas = list((repo / "entrega").iterdir())
    assert len(apartadas) == 1 and ".fallida-" in apartadas[0].name


def test_n_no_se_consume_tras_un_fallo(repo):
    _entregar(repo, [("5", _falla)])
    assert ce.calcular_n(_git(repo, "tag", "--list").split()) == 1


def test_entrega_completa_crea_commit_y_etiqueta_anotada(repo, capsys):
    base = _git(repo, "rev-parse", "HEAD").strip()
    assert _entregar(repo, [("3", _bien)]) == 0
    assert _git(repo, "log", "-1", "--format=%s").strip() == "chore(ver): 1.0.0-alpha.1"
    assert _git(repo, "rev-parse", "HEAD~1").strip() == base
    assert _git(repo, "cat-file", "-t", "v1.0.0-alpha.1").strip() == "tag"       # anotada
    assert _git(repo, "rev-list", "-n1", "v1.0.0-alpha.1").strip() == _git(repo, "rev-parse", "HEAD").strip()
    version = (repo / "src" / "autoclave" / "_version.py").read_text(encoding="utf-8")
    assert '__version__ = "1.0.0a1"' in version and 'VERSION_SEMVER = "1.0.0-alpha.1"' in version
    historial = (repo / "docs" / "versiones" / "HISTORIAL_VERSIONES.md").read_text(encoding="utf-8")
    assert "## 1.0.0-alpha.1" in historial and "1.0.0.1001" in historial
    assert "feat: algo nuevo" in historial and "inst-2026-10-24-i" in historial
    assert _git(repo, "status", "--porcelain").strip() == ""
    mensaje = _git(repo, "tag", "-l", "--format=%(contents)", "v1.0.0-alpha.1")
    assert "1.0.0-alpha.1" in mensaje and "AppVerNum: 1.0.0.1001" in mensaje
    assert "git push origin dev v1.0.0-alpha.1" in capsys.readouterr().out
    # la siguiente es alpha.2 y lista solo lo nuevo
    (repo / "otra.txt").write_text("y", encoding="utf-8")
    _git(repo, "add", "otra.txt")
    _git(repo, "commit", "-q", "-m", "fix: otra cosa")
    assert _entregar(repo, [("3", _bien)]) == 0
    historial = (repo / "docs" / "versiones" / "HISTORIAL_VERSIONES.md").read_text(encoding="utf-8")
    entrada2 = historial.split("## 1.0.0-alpha.2")[1].split("## 1.0.0-alpha.1")[0]
    assert "fix: otra cosa" in entrada2 and "feat: algo nuevo" not in entrada2
    assert historial.index("## 1.0.0-alpha.2") < historial.index("## 1.0.0-alpha.1")


def test_el_script_sale_con_2_sin_tocar_nada_si_bloquea(monkeypatch):
    monkeypatch.setattr(ce, "verificaciones_previas",
                        lambda *a, **k: ce.Previas(errores=["rama"], avisos=[]))
    llamado = []
    monkeypatch.setattr(ce, "entregar", lambda *a, **k: llamado.append(1))
    assert ce.main([]) == 2 and llamado == []


def test_historial_entrada_debajo_de_la_marca():
    texto = (RAIZ / "docs" / "versiones" / "HISTORIAL_VERSIONES.md").read_text(encoding="utf-8")
    assert "## " not in texto.split(ce.MARCA_ENTRADAS)[1]          # §5: sin entradas todavía
    uno = ce.agregar_al_historial(texto, "## 1.0.0-alpha.1 — x\n")
    dos = ce.agregar_al_historial(uno, "## 1.0.0-alpha.2 — y\n")
    assert dos.startswith(texto.split(ce.MARCA_ENTRADAS)[0])
    assert dos.index("## 1.0.0-alpha.2") < dos.index("## 1.0.0-alpha.1")
    with pytest.raises(ValueError):
        ce.agregar_al_historial("# sin marca\n", "## x\n")


def test_sumas_con_lf_para_sha256sum(tmp_path):
    ce._escribir_lf(tmp_path / "SHA256SUMS.txt", "abc *x.exe\ndef *y.zip\n")
    assert b"\r" not in (tmp_path / "SHA256SUMS.txt").read_bytes()


def test_entrada_y_mensaje_sin_commits_dicen_ninguno():
    assert "  - (ninguno)" in ce.entrada_historial("1.0.0-alpha.2", "2026-10-26", "1a2b3c4", "1.0.0.1002",
                                                   "v1.0.0-alpha.1", [])
    ctx = ce.Contexto(RAIZ, "1.0.0-alpha.2", "1.0.0.1002", "2026-10-26", "python", "iscc", commit="1" * 40)
    assert "- (ninguno)" in ce.mensaje_etiqueta(ctx, [])

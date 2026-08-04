import subprocess

import pytest

from autoclave.utils.git_autocommit import git_autocommit


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    _git("init", cwd=tmp_path)
    _git("config", "user.email", "test@example.com", cwd=tmp_path)
    _git("config", "user.name", "Test", cwd=tmp_path)

    tracked = tmp_path / "config.yaml"
    tracked.write_text("value: 1\n", encoding="utf-8")
    _git("add", str(tracked), cwd=tmp_path)
    _git("commit", "-m", "commit inicial", cwd=tmp_path)

    return tmp_path, tracked


def _log(cwd):
    result = subprocess.run(
        ["git", "log", "--format=%s"], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.splitlines()


def test_comitea_el_cambio_del_archivo(repo):
    repo_dir, tracked = repo
    tracked.write_text("value: 2\n", encoding="utf-8")

    ok = git_autocommit(tracked, "chore: actualizar config")

    assert ok is True
    log = _log(repo_dir)
    assert log[0] == "chore: actualizar config"


def test_no_arrastra_otros_archivos_con_cambios_sin_relacion(repo):
    repo_dir, tracked = repo
    otro = repo_dir / "otro.txt"
    otro.write_text("cambio sin relacion\n", encoding="utf-8")
    _git("add", str(otro), cwd=repo_dir)  # queda staged pero no debe comitearse

    tracked.write_text("value: 3\n", encoding="utf-8")
    git_autocommit(tracked, "chore: actualizar config")

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo_dir, check=True, capture_output=True, text=True
    ).stdout
    assert "otro.txt" in status  # sigue apareciendo: aun staged, no comiteado


def test_no_lanza_fuera_de_un_repo_git(tmp_path):
    archivo = tmp_path / "config.yaml"
    archivo.write_text("value: 1\n", encoding="utf-8")

    ok = git_autocommit(archivo, "chore: actualizar config")

    assert ok is False


def test_no_lanza_si_no_hay_cambios_que_comitear(repo):
    _repo_dir, tracked = repo

    ok = git_autocommit(tracked, "chore: sin cambios")

    assert ok is True

"""P1 (tanda 7): dónde guarda sus datos el ejecutable instalado (y el portátil)
y que la calibración y los parámetros sobreviven a un reinicio y a una
actualización del programa. Simula el build congelado en un subproceso
(sys.frozen, sys._MEIPASS, sys.executable) con ProgramFiles/ProgramData de
prueba: no toca las carpetas reales del PC."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

_GUION = r"""
import json, os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "src"))
meipass, exe, accion = sys.argv[2], sys.argv[3], sys.argv[4]
sys.frozen = True
sys._MEIPASS = meipass
sys.executable = exe
from autoclave.utils.paths import app_root, calibration_path
from autoclave.utils.resources import resource_path
from autoclave.installation import storage
from autoclave.services.domain.logging import db_manager
cal = calibration_path()
glob = resource_path("autoclave/config/global_params.json")
if accion == "marcar":
    with open(cal, "a", encoding="utf-8") as f:
        f.write("\n# MARCA-P1-CALIBRACION\n")
    with open(glob, "a", encoding="utf-8") as f:
        f.write(" ")   # editado por el usuario (JSON sigue válido)
print(json.dumps({
    "app_root": str(app_root()),
    "perfil": str(storage.INSTALLATION_FILE),
    "db": str(db_manager.DB_DEFAULT),
    "calibracion": str(cal),
    "global_params": str(glob),
    "marca": "MARCA-P1-CALIBRACION" in open(cal, encoding="utf-8").read(),
    "glob_editado": open(glob, encoding="utf-8").read().endswith(" "),
}))
"""


def _bundle(tmp_path: Path, nombre: str) -> Path:
    """Copia mínima del árbol _internal (lo que resource_path siembra)."""
    meipass = tmp_path / nombre
    for sub in ("config", "cycles"):
        shutil.copytree(RAIZ / "src" / "autoclave" / sub, meipass / "autoclave" / sub,
                        ignore=shutil.ignore_patterns("__pycache__"))
    return meipass


def _correr(tmp_path, meipass, exe, accion="leer"):
    # Windows rehace ProgramFiles de un proceso de 64 bits desde ProgramW6432
    propias = {"ProgramFiles": str(tmp_path / "PF"),
               "ProgramW6432": str(tmp_path / "PF"),
               "ProgramFiles(x86)": str(tmp_path / "PF86"),
               "ProgramData": str(tmp_path / "PD")}
    # en Windows os.environ trae las claves en mayúsculas: sin quitarlas, el
    # hijo recibiría las dos y podría ver las carpetas reales
    tapadas = {k.upper() for k in propias} | {"PYTHONPATH"}
    entorno = {k: v for k, v in os.environ.items() if k.upper() not in tapadas}
    entorno.update(propias)
    r = subprocess.run([sys.executable, "-c", _GUION, str(RAIZ), str(meipass), str(exe), accion],
                       capture_output=True, text=True, encoding="utf-8", env=entorno,
                       cwd=tmp_path, timeout=120)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_instalado_guarda_todo_en_programdata_y_sobrevive_reinicio_y_actualizacion(tmp_path):
    exe = tmp_path / "PF" / "Especifika" / "Autoclave" / "Autoclave.exe"
    datos = tmp_path / "PD" / "Especifika" / "Autoclave"
    a = _bundle(tmp_path, "meipass_a")

    r = _correr(tmp_path, a, exe, "marcar")
    assert Path(r["app_root"]) == datos
    assert Path(r["perfil"]) == datos / "installation_profile.json"
    assert Path(r["db"]) == datos / "data" / "autoclave.db"
    assert Path(r["calibracion"]) == datos / "data" / "calibration.yaml"
    assert Path(r["global_params"]) == datos / "programa" / "autoclave" / "config" / "global_params.json"

    # reinicio: mismo programa, se conserva lo guardado
    r = _correr(tmp_path, a, exe)
    assert r["marca"] and r["glob_editado"]

    # actualización: build nuevo con otra calibración de fábrica empaquetada
    b = _bundle(tmp_path, "meipass_b")
    (b / "autoclave" / "config" / "calibration.yaml").write_text("# build nuevo\n", encoding="utf-8")
    r = _correr(tmp_path, b, exe)
    assert r["marca"], "la actualización pisó la calibración del sitio"
    assert r["glob_editado"], "la actualización pisó global_params.json del sitio"
    # nada se escribió junto al ejecutable
    assert not (exe.parent / "data").exists()
    assert not (exe.parent / "installation_profile.json").exists()


def test_portable_guarda_junto_al_ejecutable(tmp_path):
    exe = tmp_path / "USB" / "Autoclave" / "Autoclave.exe"
    r = _correr(tmp_path, _bundle(tmp_path, "meipass"), exe)
    assert Path(r["app_root"]) == exe.parent
    assert Path(r["perfil"]) == exe.parent / "installation_profile.json"
    assert Path(r["calibracion"]) == exe.parent / "data" / "calibration.yaml"
    assert not (tmp_path / "PD").exists()

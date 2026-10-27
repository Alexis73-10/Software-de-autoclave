"""E9 (tanda 9, D9-13.1): ensayo de la actualización B -> D sobre una COPIA.

Igual que el ensayo B -> C de K8 (docs/informes/tanda8/K8_compilacion_c.md), pero
SIN el paso manual de reemplazar `instances\\*.yaml` y `global_params.json`: la D
los debe refrescar sola (utils/resources.py), con respaldo, sin tocar los datos
del sitio. Simula el ejecutable instalado (sys.frozen, sys._MEIPASS,
sys.executable bajo un ProgramFiles/ProgramData de prueba), como
tests/test_p1_rutas_build_congelado.py: no toca las carpetas reales del PC.

  1. con el código de la B y el `_internal` de la entrega B: siembra programa/,
     crea el perfil del equipo de pruebas, la BD (un usuario, un parámetro del
     equipo cambiado), marca la calibración del equipo y el correo del sitio;
  2. con el código de la D y un `_internal` de la D (programa reemplazado, datos
     sin tocar): comprueba perfil, BD migrada, calibración/correo/programas de
     usuario intactos, parámetros nuevos del equipo, canales de E/S (Cámara 2 y
     descompresion_lenta) y el respaldo con fecha de los archivos reemplazados.

Uso:
  python tools/ensayo_actualizacion_b_d.py <repo_B> <internal_B> <repo_D> <internal_D|--desde-src> <tmp>

`<repo_X>` es una carpeta con `src/` del código de esa versión (por ejemplo,
`git archive inst-2026-10-22-b src` extraído en una carpeta temporal).
`--desde-src` arma el `_internal` de la D desde `<repo_D>/src` con lo que
empaqueta Autoclave.spec (config con calibración y correo neutros, solo
cycles/factory); con la compilación D real, pasar su `_internal`.
`<tmp>` se borra y se recrea: debe ser una carpeta de prueba.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

FASE_B = r"""
import json, os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "src"))
sys.frozen = True; sys._MEIPASS = sys.argv[2]; sys.executable = sys.argv[3]
from datetime import datetime
from pathlib import Path
from autoclave.utils.paths import calibration_path
from autoclave.utils.resources import resource_path
from autoclave.installation import storage
from autoclave.installation.profile import (InstallationProfile, EquipmentClass, DoorType, Role)
from autoclave.services.domain.logging import db_manager
resource_path("autoclave/config/global_params.json"); resource_path("autoclave/cycles/factory")
cal = calibration_path()
with open(cal, "a", encoding="utf-8") as f:
    f.write("\n# MARCA-CALIBRACION-DEL-EQUIPO\n")
correo = Path(resource_path("autoclave/config/correo.json"))
datos = json.loads(correo.read_text(encoding="utf-8"))
datos["_marca_sitio"] = "CORREO-DEL-SITIO"
correo.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
p = InstallationProfile(
    machine_id="ACV-2026-001", model_id="SPK-SAT 100H2", serial_number="PRUEBA-001",
    equipment_class=EquipmentClass("piso"), door_count=2, door_type=DoorType.SIMPLE,
    cooling_level=0, door_id=1, role=Role.OPERATOR_FRONT, created_at=datetime(2026, 10, 22, 15, 0),
    supply_inputs={"agua_bomba": False, "agua_generador": False, "aire_comprimido": True,
                   "vapor_suministro": False, "suministro_electrico": False},
    temperature_probes={"temp_camara": True, "temp_2_camara": True, "temp_ref": True,
                        "temp_drenaje": True},
    vapor_source="generator", capacidad_litros=100, tipo_carga="H")
storage.save(p)
db = db_manager.DbManager(db_manager.DB_DEFAULT)
db.crear_usuario("Cristian Prueba", "cristian", "x" * 60, rol="ingeniero")
db.guardar_parametro_sistema("temp_max_apertura", 75, 80, 40, 100)
usuario = Path(resource_path("autoclave/cycles/user"))
print(json.dumps({"version_bd": db._conn.execute("PRAGMA user_version").fetchone()[0],
                  "calibracion": str(cal), "perfil": str(storage.INSTALLATION_FILE),
                  "programas_usuario": {x.name: x.read_text(encoding="utf-8")
                                        for x in sorted(usuario.glob("*.json"))}}))
"""

FASE_D = r"""
import json, os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "src"))
sys.frozen = True; sys._MEIPASS = sys.argv[2]; sys.executable = sys.argv[3]
import autoclave
from autoclave.utils.paths import calibration_path
from autoclave.utils.resources import resource_path, raiz_datos_exe, CARPETA_RESPALDOS
from autoclave.installation import storage
from autoclave.services.domain.logging import db_manager
from autoclave.core.managers.config_manager import ConfigManager
from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.core.runtime import io_names
from pathlib import Path
perfil = storage.load()
db = db_manager.DbManager(db_manager.DB_DEFAULT)
cm = ConfigManager(); cm.load_config(); cm.vincular_bd(db)
ciclos = CycleManager(); ciclos.load_all_cycles()
cal = calibration_path()
cfg_dir = Path(resource_path("autoclave/config"))
io = io_names.leer_io_enabled(cfg_dir, perfil)
usuarios = [r[0] for r in db._conn.execute("SELECT usuario FROM usuarios").fetchall()]
fab = Path(resource_path("autoclave/cycles/factory"))
usuario = Path(resource_path("autoclave/cycles/user"))
respaldos = Path(raiz_datos_exe()) / "programa" / CARPETA_RESPALDOS
print(json.dumps({
    "autoclave": autoclave.__file__,
    "serial": perfil.serial_number,
    "version_bd": db._conn.execute("PRAGMA user_version").fetchone()[0],
    "usuarios": usuarios,
    "temp_max_apertura": cm.config["temp_max_apertura"]["value"],
    "pausa_max_esterilizacion_s": (cm.config.get("pausa_max_esterilizacion_s") or {}).get("value"),
    "espera_sellado_sin_sonda_min": (cm.config.get("espera_sellado_sin_sonda_min") or {}).get("value"),
    "marca_calibracion": "MARCA-CALIBRACION-DEL-EQUIPO" in open(cal, encoding="utf-8").read(),
    "marca_correo": "CORREO-DEL-SITIO" in (cfg_dir / "correo.json").read_text(encoding="utf-8"),
    "io": io,
    "programas_fabrica": sorted(x.name for x in fab.glob("*.json")),
    "programas_usuario": {x.name: x.read_text(encoding="utf-8") for x in sorted(usuario.glob("*.json"))},
    "fuentes": sorted({c.source for c in ciclos.cycles.values()}),
    "respaldos": sorted(str(x.relative_to(respaldos)).replace("\\", "/")
                        for x in respaldos.rglob("*") if x.is_file()) if respaldos.exists() else [],
}))
"""


def armar_internal_d(repo_d: Path, destino: Path) -> Path:
    """Lo que Autoclave.spec empaqueta de config/ y cycles/ (D9-7, D8-3.18)."""
    src = repo_d / "src" / "autoclave"
    interno = destino / "autoclave"
    shutil.copytree(src / "config", interno / "config",
                    ignore=shutil.ignore_patterns("__pycache__", "*.py"))
    # Tanda 20 (T20-03): la plantilla serial ya no existe en el código actual;
    # solo se copia si la versión ensayada la trae.
    plantilla = src / "config" / "plantillas" / "calibration_neutra.yaml"
    if plantilla.exists():
        shutil.copy2(plantilla, interno / "config" / "calibration.yaml")
    shutil.copy2(src / "config" / "plantillas" / "correo_neutro.json",
                 interno / "config" / "correo.json")
    shutil.copytree(src / "cycles" / "factory", interno / "cycles" / "factory")
    return destino


def correr(guion, repo, meipass, exe, tmp):
    propias = {"ProgramFiles": str(tmp / "PF"), "ProgramW6432": str(tmp / "PF"),
               "ProgramFiles(x86)": str(tmp / "PF86"), "ProgramData": str(tmp / "PD")}
    tapadas = {k.upper() for k in propias} | {"PYTHONPATH"}
    entorno = {k: v for k, v in os.environ.items() if k.upper() not in tapadas}
    entorno.update(propias)
    r = subprocess.run([sys.executable, "-c", guion, str(repo), str(meipass), str(exe)],
                       capture_output=True, text=True, encoding="utf-8", env=entorno,
                       cwd=tmp, timeout=300)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise SystemExit(f"falló la fase con {repo}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def main(argv) -> int:
    if len(argv) != 6:
        print(__doc__)
        return 2
    repo_b, int_b, repo_d, int_d, tmp = argv[1], argv[2], argv[3], argv[4], argv[5]
    repo_b, int_b, repo_d, tmp = map(Path, (repo_b, int_b, repo_d, tmp))
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    int_d = armar_internal_d(repo_d, tmp / "internal_d") if int_d == "--desde-src" else Path(int_d)
    exe = tmp / "PF" / "Especifika" / "Autoclave" / "Autoclave.exe"
    b = correr(FASE_B, repo_b, int_b, exe, tmp)
    print("B:", json.dumps({k: v for k, v in b.items() if k != "programas_usuario"}, ensure_ascii=False))
    print("B programas de usuario:", sorted(b["programas_usuario"]))
    d = correr(FASE_D, repo_d, int_d, exe, tmp)
    print("D:", json.dumps({k: v for k, v in d.items() if k != "programas_usuario"}, ensure_ascii=False))
    errores = []
    if d["serial"] != "PRUEBA-001": errores.append("perfil perdido")
    if "cristian" not in d["usuarios"]: errores.append("usuario perdido")
    if d["temp_max_apertura"] != 75: errores.append("parámetro del equipo perdido")
    if not d["marca_calibracion"]: errores.append("calibración del equipo reemplazada")
    if not d["marca_correo"]: errores.append("correo del sitio reemplazado")
    if d["version_bd"] < b["version_bd"]: errores.append("BD no migrada")
    if d["programas_usuario"] != b["programas_usuario"]: errores.append("programas de usuario alterados")
    if d["pausa_max_esterilizacion_s"] is None or d["espera_sellado_sin_sonda_min"] is None:
        errores.append("parámetros nuevos del equipo ausentes (global_params.json no refrescado)")
    if "temp_2_camara" not in d["io"]["AI"]: errores.append("Cámara 2 (temp_2_camara) ausente en E/S")
    if "descompresion_lenta" not in d["io"]["DO"]: errores.append("descompresion_lenta ausente en E/S")
    esperados = {"autoclave/config/global_params.json", "autoclave/config/instances/ACV-2026-001.yaml"}
    vistos = {r.split("/", 1)[1] for r in d["respaldos"]}
    if not esperados <= vistos: errores.append(f"faltan respaldos: {sorted(esperados - vistos)}")
    if vistos - esperados: errores.append(f"respaldos de más (¿se tocó algo del sitio?): {sorted(vistos - esperados)}")
    print("ERRORES:" if errores else "OK: sin errores", errores)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

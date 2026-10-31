"""K11 (tanda 11): ensayo de la actualización F -> G sobre una COPIA.

Igual que el ensayo B -> D de E9 (tools/ensayo_actualizacion_b_d.py, que se
reutiliza), con las comprobaciones propias de la G:
  - U11 (D11-6): la BD pasa a v11; `admin`/`ingeniero` (semilla) quedan como
    `Admin`/`Ingeniero` con la marca `cuenta_sistema`, el mismo hash de
    contraseña y el mismo `debe_cambiar_clave`, una fila `usuario_renombrado`
    por cuenta, la auditoría anterior intacta, y el inicio de sesión los
    encuentra con `admin`, `ADMIN` y `Admin`;
  - E11 (D11-2): `aire_comprimido_chaqueta` ya no aparece en las E/S y el
    YAML de instancia refrescado se respalda (cambió de la F a la G).

Uso:
  python tools/ensayo_actualizacion_f_g.py <repo_F> <internal_F> <repo_G> <internal_G|--desde-src> <tmp>
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensayo_actualizacion_b_d as base  # noqa: E402

FASE_F = base.FASE_B.replace(
    'print(json.dumps({"version_bd"',
    'semillas = {r[0]: {"hash": r[1], "debe": r[2]} for r in db._conn.execute(\n'
    '    "SELECT usuario, hash_pw, debe_cambiar_clave FROM usuarios WHERE creado_por=\'semilla\'")}\n'
    'n_audit = db._conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]\n'
    'print(json.dumps({"semillas": semillas, "n_audit": n_audit, "version_bd"')
assert FASE_F != base.FASE_B

FASE_G = base.FASE_D.replace(
    'print(json.dumps({\n',
    'filas = db._conn.execute("SELECT usuario, nombre, hash_pw, debe_cambiar_clave, cuenta_sistema "\n'
    '                         "FROM usuarios WHERE creado_por=\'semilla\'").fetchall()\n'
    'semillas = {r[0]: {"nombre": r[1], "hash": r[2], "debe": r[3], "marca": r[4]} for r in filas}\n'
    'renombres = [r[0] for r in db._conn.execute(\n'
    '    "SELECT valor_nuevo FROM audit_log WHERE evento=\'usuario_renombrado\'").fetchall()]\n'
    'n_audit = db._conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]\n'
    'login = {u: (db.get_usuario_by_username(u) or {}).get("usuario") for u in ("admin", "ADMIN", "Admin", "ingeniero", "INGENIERO")}\n'
    'print(json.dumps({"semillas": semillas, "renombres": renombres, "n_audit": n_audit, "login": login,\n')
assert FASE_G != base.FASE_D


def main(argv) -> int:
    if len(argv) != 6:
        print(__doc__)
        return 2
    repo_f, int_f, repo_g, int_g, tmp = argv[1], argv[2], argv[3], argv[4], argv[5]
    repo_f, int_f, repo_g, tmp = map(Path, (repo_f, int_f, repo_g, tmp))
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    int_g = base.armar_internal_d(repo_g, tmp / "internal_g") if int_g == "--desde-src" else Path(int_g)
    exe = tmp / "PF" / "Especifika" / "Autoclave" / "Autoclave.exe"
    f = base.correr(FASE_F, repo_f, int_f, exe, tmp)
    print("F:", json.dumps({k: v for k, v in f.items() if k not in ("programas_usuario", "semillas")},
                           ensure_ascii=False))
    print("F semillas:", sorted(f["semillas"]))
    g = base.correr(FASE_G, repo_g, int_g, exe, tmp)
    print("G:", json.dumps({k: v for k, v in g.items()
                            if k not in ("programas_usuario", "semillas", "io")}, ensure_ascii=False))
    print("G semillas:", json.dumps({u: {k: v for k, v in d.items() if k != "hash"}
                                     for u, d in g["semillas"].items()}, ensure_ascii=False))
    errores = []
    if g["serial"] != "PRUEBA-001": errores.append("perfil perdido")
    if "cristian" not in g["usuarios"]: errores.append("usuario perdido")
    if g["temp_max_apertura"] != 75: errores.append("parámetro del equipo perdido")
    if not g["marca_calibracion"]: errores.append("calibración del equipo reemplazada")
    if not g["marca_correo"]: errores.append("correo del sitio reemplazado")
    if g["version_bd"] != 11: errores.append(f"BD no migrada a v11 ({g['version_bd']})")
    if g["programas_usuario"] != f["programas_usuario"]: errores.append("programas de usuario alterados")
    for viejo, nuevo in (("admin", "Admin"), ("ingeniero", "Ingeniero")):
        antes, despues = f["semillas"].get(viejo), g["semillas"].get(nuevo)
        if antes is None: errores.append(f"la F no tenía la semilla {viejo}"); continue
        if despues is None: errores.append(f"{viejo} no se renombró a {nuevo}"); continue
        if despues["nombre"] != nuevo: errores.append(f"nombre mostrado de {nuevo}: {despues['nombre']}")
        if despues["hash"] != antes["hash"]: errores.append(f"contraseña de {nuevo} alterada")
        if despues["debe"] != antes["debe"]: errores.append(f"debe_cambiar_clave de {nuevo} alterado")
        if despues["marca"] != 1: errores.append(f"{nuevo} sin marca cuenta_sistema")
    if len(g["renombres"]) != 2: errores.append(f"filas usuario_renombrado: {len(g['renombres'])}")
    if g["n_audit"] < f["n_audit"] + 2: errores.append("auditoría anterior alterada")
    if g["login"] != {"admin": "Admin", "ADMIN": "Admin", "Admin": "Admin",
                      "ingeniero": "Ingeniero", "INGENIERO": "Ingeniero"}:
        errores.append(f"inicio de sesión sin distinguir mayúsculas: {g['login']}")
    if "aire_comprimido_chaqueta" in g["io"]["DO"]: errores.append("aire_comprimido_chaqueta sigue en E/S")
    if "aire_comprimido_camara" not in g["io"]["DO"]: errores.append("aire_comprimido_camara ausente en E/S")
    if "temp_2_camara" not in g["io"]["AI"]: errores.append("Cámara 2 (temp_2_camara) ausente en E/S")
    vistos = {r.split("/", 1)[1] for r in g["respaldos"]}
    esperado = "autoclave/config/instances/ACV-2026-001.yaml"
    if esperado not in vistos: errores.append(f"falta el respaldo de {esperado}")
    print("Respaldos:", sorted(vistos))
    print("ERRORES:" if errores else "OK: sin errores", errores)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

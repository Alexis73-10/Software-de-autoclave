"""K12 (tanda 12): ensayo de la actualización G -> H sobre una COPIA.

Reutiliza el ensayo B -> D de E9 (tools/ensayo_actualizacion_b_d.py). La fase G
siembra el equipo con el código de la G y además copia los programas de usuario
de la G (`cycles/user/*.json`, con el Bowie & Dick en `presion_add` 99, como en
el equipo de pruebas). La fase H, con el código y el `_internal` de la H:
  - carga los programas (ninguno dañado);
  - J12 (C-04.4): `bowe_dick` de usuario migra `presion_add_calentamiento`
    99 -> 9, con una fila `param_ciclo_cambio` de auditoría (anterior/nuevo,
    origen "migración tanda 12"), el aviso SIS-06 activo y el archivo
    reescrito con su `.bak`;
  - J12 (C-05.9): la chaqueta 350/25 de los programas de usuario se conserva;
  - J12 (C-05.3, C-13.4): claves nuevas presentes tras la carga.
Las llamadas de arranque son las reales de BackendContext
(`_avisar_migraciones_correctivas`, `auditar_migraciones_correctivas`), sobre
un objeto mínimo con el CycleManager, la BD y un AlarmManager reales.

Uso:
  python tools/ensayo_actualizacion_g_h.py <repo_G> <internal_G> <repo_H> <internal_H|--desde-src> <tmp>
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensayo_actualizacion_b_d as base  # noqa: E402

FASE_G = base.FASE_B.replace(
    'usuario = Path(resource_path("autoclave/cycles/user"))\n',
    'usuario = Path(resource_path("autoclave/cycles/user"))\n'
    'import shutil as _sh\n'
    'usuario.mkdir(parents=True, exist_ok=True)\n'
    'for _x in sorted((Path(sys.argv[1]) / "src" / "autoclave" / "cycles" / "user").glob("*.json")):\n'
    '    _sh.copy2(_x, usuario / _x.name)\n')
assert FASE_G != base.FASE_B

_EXTRA_H = '''
from types import SimpleNamespace
from autoclave.backend.context import BackendContext
from autoclave.state_machine.alarms.alarm_manager import AlarmManager
am = AlarmManager()
ns = SimpleNamespace(cycle_manager=ciclos, db=db, alarm_manager=am)
BackendContext._avisar_migraciones_correctivas(ns)
BackendContext.auditar_migraciones_correctivas(ns)
avisos = sorted(str(k) for k in am._instancias)
aud = [dict(zip(("entidad", "valor_anterior", "valor_nuevo", "detalle"), r)) for r in db._conn.execute(
    "SELECT entidad, valor_anterior, valor_nuevo, detalle FROM audit_log WHERE evento='param_ciclo_cambio'")]
migr = [{"programa": c.id, **m} for c, m in ciclos.migraciones_correctivas()]
danados = {c.id: c.danado for c in ciclos.cycles.values() if getattr(c, "danado", None)}
def _p(cid, sec, nom):
    c = ciclos.cycles.get(cid)
    return None if c is None else c.get_param(sec, nom)
claves = {cid: {"presion_add_calentamiento": _p(cid, "calentamiento", "presion_add_calentamiento"),
                "presion_chaqueta": _p(cid, "globals", "presion_chaqueta"),
                "rango_presion_chaqueta": _p(cid, "globals", "rango_presion_chaqueta"),
                "delta_temp_chaqueta": _p(cid, "globals", "delta_temp_chaqueta"),
                "margen_flujo_chaqueta": _p(cid, "globals", "margen_flujo_chaqueta"),
                "timeout_excursion_referencia": _p(cid, "esterilizacion", "timeout_excursion_referencia"),
                "brecha_segura_temperatura": _p(cid, "esterilizacion", "brecha_segura_temperatura"),
                "source": ciclos.cycles[cid].source}
          for cid in sorted(ciclos.cycles)}
bak = sorted(x.name for x in usuario.glob("*.bak"))
print(json.dumps({"avisos": avisos, "auditoria": aud, "migraciones": migr, "danados": danados,
                  "claves": claves, "bak": bak,
'''
FASE_H = base.FASE_D.replace('print(json.dumps({\n', _EXTRA_H.lstrip("\n"))
assert FASE_H != base.FASE_D


def main(argv) -> int:
    if len(argv) != 6:
        print(__doc__)
        return 2
    repo_g, int_g, repo_h, int_h, tmp = argv[1], argv[2], argv[3], argv[4], argv[5]
    repo_g, int_g, repo_h, tmp = map(Path, (repo_g, int_g, repo_h, tmp))
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    int_h = base.armar_internal_d(repo_h, tmp / "internal_h") if int_h == "--desde-src" else Path(int_h)
    exe = tmp / "PF" / "Especifika" / "Autoclave" / "Autoclave.exe"
    g = base.correr(FASE_G, repo_g, int_g, exe, tmp)
    print("G:", json.dumps({k: v for k, v in g.items() if k != "programas_usuario"}, ensure_ascii=False))
    print("G programas de usuario:", sorted(g["programas_usuario"]))
    h = base.correr(FASE_H, repo_h, int_h, exe, tmp)
    print("H:", json.dumps({k: h[k] for k in ("serial", "version_bd", "usuarios", "temp_max_apertura",
                                               "marca_calibracion", "marca_correo", "programas_fabrica",
                                               "fuentes", "respaldos")}, ensure_ascii=False))
    print("H migraciones:", json.dumps(h["migraciones"], ensure_ascii=False))
    print("H auditoría:", json.dumps(h["auditoria"], ensure_ascii=False))
    print("H avisos:", h["avisos"], "| .bak:", h["bak"], "| dañados:", h["danados"])
    for cid, d in h["claves"].items():
        print(f"H {cid}:", json.dumps(d, ensure_ascii=False))
    errores = []
    if h["serial"] != "PRUEBA-001": errores.append("perfil perdido")
    if "cristian" not in h["usuarios"]: errores.append("usuario perdido")
    if h["temp_max_apertura"] != 75: errores.append("parámetro del equipo perdido")
    if not h["marca_calibracion"]: errores.append("calibración del equipo reemplazada")
    if not h["marca_correo"]: errores.append("correo del sitio reemplazado")
    if h["version_bd"] < g["version_bd"]: errores.append("BD no migrada")
    if "user" not in h["fuentes"]: errores.append("no cargó ningún programa de usuario")
    if h["danados"]: errores.append(f"programas dañados: {h['danados']}")
    usuario = {cid: d for cid, d in h["claves"].items() if d["source"] == "user"}
    if not usuario: errores.append("sin programas de usuario cargados")
    bd = next((d for cid, d in usuario.items() if "bowe" in cid), {})
    if bd.get("presion_add_calentamiento") != 9: errores.append(f"B&D no migró a 9: {bd}")
    if not any("bowe" in m["programa"] and m["parametro"] == "presion_add_calentamiento"
               and m["anterior"] == 99 and m["nuevo"] == 9 for m in h["migraciones"]):
        errores.append("sin migración correctiva 99 -> 9 del B&D")
    filas = [a for a in h["auditoria"] if "bowe" in a["entidad"]
             and "presion_add_calentamiento" in a["entidad"]]
    if not filas: errores.append("sin fila de auditoría de la migración")
    elif "migraci" not in (filas[0]["detalle"] or ""): errores.append("auditoría sin origen de migración")
    if not any("SIS-06" in a for a in h["avisos"]): errores.append("sin aviso SIS-06")
    if not any("bowe" in b for b in h["bak"]): errores.append("B&D reescrito sin .bak")
    for cid, d in usuario.items():
        if "bowe" in cid or "134" in cid:
            if (d.get("presion_chaqueta"), d.get("rango_presion_chaqueta")) != (350, 25):
                errores.append(f"chaqueta 350/25 de {cid} alterada: {d}")
    for cid, d in h["claves"].items():
        for k in ("delta_temp_chaqueta", "margen_flujo_chaqueta", "timeout_excursion_referencia"):
            if d.get(k) is None: errores.append(f"{cid}: falta {k}")
    print("ERRORES:" if errores else "OK: sin errores", errores)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

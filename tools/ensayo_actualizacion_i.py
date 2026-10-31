"""K13 (tanda 13): ensayo de las actualizaciones H -> I y G -> I sobre COPIAS.

Reutiliza el ensayo G -> H de K12 (tools/ensayo_actualizacion_g_h.py):
  - G -> I: la fase G siembra el equipo con el código de la G y sus programas
    de usuario (B&D en `presion_add` 99); la fase I, con el código y el
    `_internal` de la I, debe hacer lo mismo que hacía la H (migración 99 -> 9
    con auditoría, SIS-06 y `.bak`).
  - H -> I: G -> H (como en el equipo de pruebas) y después la fase I; la
    migración ya ocurrió en la H, así que en la I no debe repetirse.
En los dos casos la fase I comprueba además (VAP-01, IAPWS-IF97):
  - los programas de usuario cargan y ninguno queda dañado;
  - la consigna mostrada a 134 °C (gráfica del PDF, `consignas.py`) es 304.2 kPa;
  - la consigna de chaqueta del Instrumental 134 de usuario (134 °C / 9) es 328.2 kPa.

Uso:
  python tools/ensayo_actualizacion_i.py g <repo_G> <internal_G> <repo_I> <internal_I|--desde-src> <tmp>
  python tools/ensayo_actualizacion_i.py h <repo_G> <internal_G> <repo_H> <internal_H> <repo_I> <internal_I|--desde-src> <tmp>
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensayo_actualizacion_b_d as base  # noqa: E402
import ensayo_actualizacion_g_h as gh  # noqa: E402

_EXTRA_I = '''
from autoclave.ui_qml.domain.consignas import consigna_esterilizacion
from autoclave.core.managers import catalogo_parametros as _cp
_c134 = consigna_esterilizacion(134.0, [{"clave": "esterilizacion", "inicioMin": 0.0}], 1.0)
consigna_134 = None if _c134 is None else round(_c134["pres"], 2)
chaqueta = {cid: (None if (_v := _cp.consigna_chaqueta_programa(c.parameters)) is None else round(_v, 2))
            for cid, c in sorted(ciclos.cycles.items())}
'''
FASE_I = gh.FASE_H.replace('print(json.dumps({"avisos"', _EXTRA_I.lstrip("\n") + 'print(json.dumps({"avisos"')
FASE_I = FASE_I.replace('"claves": claves, "bak": bak,',
                        '"claves": claves, "bak": bak, "consigna_134": consigna_134, "chaqueta": chaqueta,')
assert FASE_I.count("consigna_134") == 3 and '"chaqueta": chaqueta' in FASE_I


def _mostrar(nombre, r):
    print(f"{nombre}:", json.dumps({k: r[k] for k in ("serial", "version_bd", "usuarios", "temp_max_apertura",
                                                       "marca_calibracion", "marca_correo", "programas_fabrica",
                                                       "fuentes", "respaldos")}, ensure_ascii=False))
    print(f"{nombre} migraciones:", json.dumps(r["migraciones"], ensure_ascii=False))
    print(f"{nombre} auditoría:", json.dumps(r["auditoria"], ensure_ascii=False))
    print(f"{nombre} avisos:", r["avisos"], "| .bak:", r["bak"], "| dañados:", r["danados"])
    for cid, d in r["claves"].items():
        print(f"{nombre} {cid}:", json.dumps(d, ensure_ascii=False))


def _comunes(i, previo) -> list[str]:
    errores = []
    if i["serial"] != "PRUEBA-001": errores.append("perfil perdido")
    if "cristian" not in i["usuarios"]: errores.append("usuario perdido")
    if i["temp_max_apertura"] != 75: errores.append("parámetro del equipo perdido")
    if not i["marca_calibracion"]: errores.append("calibración del equipo reemplazada")
    if not i["marca_correo"]: errores.append("correo del sitio reemplazado")
    if i["version_bd"] < previo["version_bd"]: errores.append("BD no migrada")
    if i["danados"]: errores.append(f"programas dañados: {i['danados']}")
    usuario = {cid: d for cid, d in i["claves"].items() if d["source"] == "user"}
    if not usuario: errores.append("sin programas de usuario cargados")
    bd = next((d for cid, d in usuario.items() if "bowe" in cid), {})
    if bd.get("presion_add_calentamiento") != 9: errores.append(f"B&D no quedó en 9: {bd}")
    for cid, d in usuario.items():
        if "bowe" in cid or "134" in cid:
            if (d.get("presion_chaqueta"), d.get("rango_presion_chaqueta")) != (350, 25):
                errores.append(f"chaqueta 350/25 de {cid} alterada: {d}")
    if i["consigna_134"] is None or abs(i["consigna_134"] - 304.2) > 0.05:
        errores.append(f"consigna mostrada a 134 °C: {i['consigna_134']} (esperado 304.2)")
    c134 = next((v for cid, v in i["chaqueta"].items()
                 if "134" in cid and i["claves"][cid]["source"] == "user"), None)
    if c134 is None or abs(c134 - 328.2) > 0.05:
        errores.append(f"consigna de chaqueta del Instrumental 134: {c134} (esperado 328.2)")
    return errores


def main(argv) -> int:
    if len(argv) < 2 or (argv[1], len(argv)) not in (("g", 7), ("h", 9)):
        print(__doc__)
        return 2
    modo = argv[1]
    if modo == "g":
        repo_g, int_g, repo_i, int_i, tmp = argv[2:]
        repo_h = int_h = None
    else:
        repo_g, int_g, repo_h, int_h, repo_i, int_i, tmp = argv[2:]
    tmp = Path(tmp)
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    int_i = base.armar_internal_d(Path(repo_i), tmp / "internal_i") if int_i == "--desde-src" else Path(int_i)
    exe = tmp / "PF" / "Especifika" / "Autoclave" / "Autoclave.exe"
    g = base.correr(gh.FASE_G, Path(repo_g), Path(int_g), exe, tmp)
    print("G:", json.dumps({k: v for k, v in g.items() if k != "programas_usuario"}, ensure_ascii=False))
    previo = g
    if modo == "h":
        h = base.correr(gh.FASE_H, Path(repo_h), Path(int_h), exe, tmp)
        _mostrar("H", h)
        previo = h
    i = base.correr(FASE_I, Path(repo_i), int_i, exe, tmp)
    _mostrar("I", i)
    print("I consigna mostrada a 134 °C:", i["consigna_134"], "| consignas de chaqueta:", i["chaqueta"])
    errores = _comunes(i, previo)
    migr_bd = [m for m in i["migraciones"] if "bowe" in m["programa"]
               and m["parametro"] == "presion_add_calentamiento"]
    if modo == "g":
        if not any(m["anterior"] == 99 and m["nuevo"] == 9 for m in migr_bd):
            errores.append("sin migración correctiva 99 -> 9 del B&D")
        filas = [a for a in i["auditoria"] if "bowe" in a["entidad"]
                 and "presion_add_calentamiento" in a["entidad"]]
        if not filas: errores.append("sin fila de auditoría de la migración")
        if not any("SIS-06" in a for a in i["avisos"]): errores.append("sin aviso SIS-06")
        if not any("bowe" in b for b in i["bak"]): errores.append("B&D reescrito sin .bak")
    else:
        if migr_bd: errores.append(f"la I repitió la migración del B&D: {migr_bd}")
    print("ERRORES:" if errores else "OK: sin errores", errores)
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

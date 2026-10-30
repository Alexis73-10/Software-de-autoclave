# tools/registro_pruebas/exportar.py
#
# Salida al PC de la app de registro de pruebas (F1, tanda 3):
#   (a) registro.json  completo, con versiones y hashes;
#   (b) registro.html  imprimible con el formato diligenciado (cabecera, cada
#       prueba con resultado, valores, fotos (miniaturas) y firmas incrustadas,
#       resumen por bloque, anomalías y hash final);
#   (c) resultados.csv de resultados.
#
# Uso como script (copia JSON, CSV y HTML SIN las fotos grandes ni la base a
# docs/informes/pruebas_banco/<AAAA-MM-DD>/<usuario>/; no agrega nada a git):
#   python tools/registro_pruebas/exportar.py --registro 1 [--usuario ana] [--destino ruta]

import argparse
import base64
import csv
import html
import io
import json
import os
import sys
from datetime import date
from pathlib import Path

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)

import almacen as almacen_mod  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
MINIATURA_MAX_BYTES = 120_000
ETIQUETA = {"aprobada": "APROBADA", "fallada": "FALLADA", "no_aplica": "NO APLICA", None: "SIN RESULTADO"}


def exportar_json(estado: dict, verificacion: dict) -> str:
    salida = {"registro": {k: v for k, v in estado.items() if k != "snapshot"},
              "definiciones": estado["snapshot"], "verificacion": verificacion}
    return json.dumps(salida, ensure_ascii=False, indent=2)


def _celda(texto) -> str:
    """REG-10: una celda que empiece con = + - @ se ejecutaría como fórmula en Excel."""
    texto = str(texto)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


def exportar_csv(estado: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["registro", "ejecutor", "bloque", "prueba", "titulo", "resultado", "valores",
                "observaciones", "version", "hora_servidor", "firmada", "fotos"])
    fotos = {}
    for e in estado["evidencias"]:
        if e["tipo"] == "foto":
            fotos[e["prueba_id"]] = fotos.get(e["prueba_id"], 0) + 1
    for p in estado["snapshot"]["pruebas"]:
        r = estado["pruebas"].get(p["id"], {})
        valores = "; ".join(f"{k}={v}" for k, v in (r.get("valores") or {}).items())
        w.writerow([estado["id"], estado["usuario"], p["bloque"], p["id"], p["titulo"],
                    r.get("resultado") or "", _celda(valores),
                    _celda((r.get("observaciones") or "").replace("\n", " ")),
                    r.get("version", ""), r.get("ts_servidor", ""), "si" if r.get("firma_id") else "no",
                    fotos.get(p["id"], 0)])
    return buf.getvalue()


def _imagen_incrustada(datos: Path, archivo: str, mime: str) -> str:
    ruta = datos / archivo
    try:
        contenido = ruta.read_bytes()
    except OSError:
        return "<em>(archivo no disponible)</em>"
    if len(contenido) > MINIATURA_MAX_BYTES and mime == "image/jpeg":
        contenido = _reducir(contenido)
    b64 = base64.b64encode(contenido).decode("ascii")
    return f'<img src="data:{mime};base64,{b64}" alt="">'


def _reducir(jpeg: bytes) -> bytes:
    """Miniatura para el HTML (si hay Pillow; si no, se deja la foto tal cual)."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(jpeg))
        img.thumbnail((360, 360))
        out = io.BytesIO()
        img.convert("RGB").save(out, "JPEG", quality=70)
        return out.getvalue()
    except Exception:
        return jpeg


def exportar_html(estado: dict, verificacion: dict, datos: Path) -> str:
    e = html.escape
    cab = estado["cabecera"]
    snap = estado["snapshot"]
    filas_cab = "".join(f"<tr><th>{e(k)}</th><td>{e(str(v))}</td></tr>" for k, v in cab.items() if v != "")
    por_bloque = {}
    for p in snap["pruebas"]:
        por_bloque.setdefault(p["bloque"], []).append(p)
    nombres = {b[0]: b[1] for b in snap["bloques"]}
    ev_por_prueba = {}
    for ev in estado["evidencias"]:
        ev_por_prueba.setdefault((ev["prueba_id"], ev["tipo"]), []).append(ev)
    archivos = {}
    for v in estado["versiones"]:
        if v["tipo"] in ("foto", "firma"):
            archivos[v["datos"]["evidencia_id"]] = v["datos"]["archivo"]
    resumen, cuerpo = [], []
    for bloque, pruebas in por_bloque.items():
        cuenta = {"aprobada": 0, "fallada": 0, "no_aplica": 0, None: 0}
        for p in pruebas:
            cuenta[(estado["pruebas"].get(p["id"]) or {}).get("resultado")] += 1
        resumen.append(f"<tr><td>{e(bloque)} — {e(nombres.get(bloque, ''))}</td><td>{cuenta['aprobada']}</td>"
                       f"<td>{cuenta['fallada']}</td><td>{cuenta['no_aplica']}</td><td>{cuenta[None]}</td></tr>")
        cuerpo.append(f"<h2>Bloque {e(bloque)} — {e(nombres.get(bloque, ''))}</h2>")
        for p in pruebas:
            r = estado["pruebas"].get(p["id"], {})
            pasos = "".join(
                f"<li>{'☑' if (i < len(r.get('pasos', [])) and r['pasos'][i]) else '☐'} {e(paso)}</li>"
                for i, paso in enumerate(p["pasos"]))
            valores = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in (r.get("valores") or {}).items())
            fotos = "".join(_imagen_incrustada(datos, archivos[ev["id"]], "image/jpeg")
                            for ev in ev_por_prueba.get((p["id"], "foto"), []) if ev["id"] in archivos)
            firma = ""
            if r.get("firma_id"):
                for ev in ev_por_prueba.get((p["id"], "firma"), []):
                    if ev["cliente_id"] == r["firma_id"] and ev["id"] in archivos:
                        firma = (_imagen_incrustada(datos, archivos[ev["id"]], "image/png")
                                 + f"<div class='nota'>Firmó {e(r.get('usuario', ''))} · {e(r.get('ts_servidor', ''))}</div>")
            clase = {"aprobada": "ok", "fallada": "mal"}.get(r.get("resultado"), "")
            cuerpo.append(
                f"<section class='prueba'><h3>{e(p['id'])} — {e(p['titulo'])} "
                f"<span class='res {clase}'>{ETIQUETA[r.get('resultado')]}</span></h3>"
                f"<p><b>Objetivo:</b> {e(p['objetivo'])}</p><p><b>Precondiciones:</b> {e(p['pre'])}</p>"
                f"<ol>{pasos}</ol><p><b>Esperado:</b> {e(p['esperado'])}</p><p><b>Criterio:</b> {e(p['criterio'])}</p>"
                f"{'<table>' + valores + '</table>' if valores else ''}"
                f"<p><b>Observaciones:</b> {e(r.get('observaciones') or '—')}</p>"
                f"<div class='fotos'>{fotos}</div><div class='firma'>{firma}</div></section>")
    anomalias = "".join(
        f"<tr><td>{e(a_id)}</td><td>{e(a.get('prueba_id', ''))}</td><td>{e(a['descripcion'])}</td>"
        f"<td>{e(a['gravedad'])}</td><td>{e(a.get('accion', ''))}</td><td>{e(a.get('responsable', ''))}</td>"
        f"<td>{e(a['estado'])}</td><td>{e(a.get('reensayo', ''))}</td></tr>"
        for a_id, a in sorted(estado["anomalias"].items())) or "<tr><td colspan='8'>Sin anomalías</td></tr>"
    cierre = estado["cierre"]
    firma_final = ""
    if cierre:
        for ev in estado["evidencias"]:
            if ev["tipo"] == "firma" and ev["cliente_id"] == cierre["firma_id"] and ev["id"] in archivos:
                firma_final = (_imagen_incrustada(datos, archivos[ev["id"]], "image/png")
                               + f"<div class='nota'>Cierre firmado por {e(cierre['usuario'])} · {e(cierre['ts_servidor'])}</div>")
    estado_cadena = "ÍNTEGRA" if verificacion["ok"] else "ALTERADA: " + e("; ".join(verificacion["errores"]))
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<title>Registro de pruebas de banco #{estado['id']}</title>
<style>body{{font-family:sans-serif;max-width:900px;margin:20px auto;padding:0 16px;color:#222}}
table{{border-collapse:collapse;margin:6px 0}}th{{text-align:left;padding:2px 10px 2px 0;color:#555}}
td,th{{vertical-align:top}}.res{{font-size:.8rem;padding:2px 8px;border-radius:10px;background:#eee}}
.res.ok{{background:#d4efdf}}.res.mal{{background:#f5b7b1}}.prueba{{border-top:1px solid #ccc;padding:8px 0;page-break-inside:avoid}}
.fotos img{{max-width:180px;margin:4px;border:1px solid #ccc}}.firma img{{max-height:80px}}.nota{{font-size:.75rem;color:#666}}
.hash{{font-family:monospace;font-size:.75rem;word-break:break-all}}
table.res2 td,table.res2 th{{border:1px solid #ccc;padding:3px 8px}}</style></head><body>
<h1>Registro de pruebas de banco #{estado['id']}</h1>
<p>Ejecutor: <b>{e(estado['usuario'])}</b> · Creado: {e(estado['creado'])} · Estado: <b>{e(estado['estado'])}</b>
{' · Cerrado: ' + e(estado['cerrado_en']) if estado['cerrado_en'] else ''}</p>
<h2>Cabecera</h2><table>{filas_cab}</table>
<h2>Resumen por bloque</h2><table class="res2"><tr><th>Bloque</th><th>Aprobadas</th><th>Falladas</th><th>No aplica</th><th>Sin resultado</th></tr>{''.join(resumen)}</table>
{''.join(cuerpo)}
<h2>Anomalías</h2><table class="res2"><tr><th>ID</th><th>Prueba</th><th>Descripción</th><th>Gravedad</th><th>Acción</th><th>Responsable</th><th>Estado</th><th>Reensayo</th></tr>{anomalias}</table>
<h2>Cierre</h2><div class="firma">{firma_final or '<em>Registro sin cerrar</em>'}</div>
<p>Definiciones: versión <span class="hash">{e(estado['snapshot_hash'])}</span></p>
<p>Cadena de versiones: <b>{estado_cadena}</b> ({verificacion['versiones']} versiones)</p>
<p>Hash final: <span class="hash">{e(verificacion['ultimo_hash'])}</span></p>
</body></html>"""


def exportar_todo(almacen, registro_id: int, destino: Path | None = None, usuario_carpeta: str | None = None
                  ) -> dict:
    """Escribe los tres archivos. Con `destino` None: carpeta `exportaciones\\R<id>\\`
    de la carpeta de datos."""
    estado = almacen.estado_registro(registro_id)
    verificacion = almacen.verificar(registro_id)
    carpeta = Path(destino) if destino else almacen.datos / "exportaciones" / f"R{registro_id}"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "registro.json").write_text(exportar_json(estado, verificacion), encoding="utf-8")
    (carpeta / "resultados.csv").write_text(exportar_csv(estado), encoding="utf-8-sig", newline="")
    (carpeta / "registro.html").write_text(exportar_html(estado, verificacion, almacen.datos), encoding="utf-8")
    return {"carpeta": str(carpeta), "archivos": ["registro.json", "resultados.csv", "registro.html"],
            "cadena_integra": verificacion["ok"]}


def main(argv=None) -> int:
    import datos_registro
    ap = argparse.ArgumentParser(description="Copia un registro a docs/informes/pruebas_banco/")
    ap.add_argument("--registro", type=int, required=True)
    ap.add_argument("--destino", help="carpeta (por defecto docs/informes/pruebas_banco/<fecha>/<usuario>/)")
    ap.add_argument("--datos", help="carpeta de datos (por defecto la de la app)")
    a = ap.parse_args(argv)
    alm = almacen_mod.Almacen(Path(a.datos) if a.datos else datos_registro.carpeta_datos())
    estado = alm.estado_registro(a.registro)
    destino = Path(a.destino) if a.destino else (
        RAIZ / "docs" / "informes" / "pruebas_banco" / date.today().isoformat() / estado["usuario"])
    r = exportar_todo(alm, a.registro, destino)
    print(f"Exportado a {r['carpeta']} (cadena {'íntegra' if r['cadena_integra'] else 'ALTERADA'}).")
    print("Se copiaron registro.json, resultados.csv y registro.html SIN las fotos ni la base. "
          "No se agregó nada a git.")
    return 0 if r["cadena_integra"] else 1


if __name__ == "__main__":
    sys.exit(main())

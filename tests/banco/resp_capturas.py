# tests/banco/resp_capturas.py
#
# Tanda responsive (10-nov): captura los escenarios de tests/banco/hor_capturas.py
# (y sus hor_escenarios_*.py) a varios tamaños de pantalla y escalas de Windows,
# y revisa en cada uno, además de lo que ya revisa hor_capturas (textos
# recortados, encogidos, fuera de su cuadro, ítems fuera de la ventana):
#
#   - "tactiles": zonas táctiles visibles y habilitadas (MouseArea, botones de
#     Qt Quick Controls y TapHandler) cuyo lado menor, en px FÍSICOS, queda
#     bajo el mínimo (--tactil, 44 por defecto);
#   - "lienzo": rectángulo del lienzo en la ventana (franjas sobrantes);
#   - "fuente_min": la letra visible más chica en px físicos.
#
# No es una prueba automática. La escala se simula con QT_SCREEN_SCALE_FACTORS
# (sin tocar el entorno del equipo: solo el del subproceso): el tamaño de la
# ventana se da en px físicos y la ventana se abre con su tamaño lógico
# (físico / escala), igual que la ve app.py en pantalla completa.
#
#   python tests/banco/resp_capturas.py --tamanos 1920x1080 1024x600 --escalas 1 1.5
#          [--temas claro oscuro] [--escenarios a b] [--destino DIR] [--paralelo 4]
#          [--raiz <árbol>] [--idioma es]
#   python tests/banco/resp_capturas.py --analizar DIR      (tabla de defectos nuevos)
#
# Deja DIR/<WxH>@<escala>/hor_<tema>_<escenario>.png y resumen_<tema>.json.

import argparse
import json
import os
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ_PROPIA = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_PROPIA))
from tests.banco import hor_capturas  # noqa: E402

DESTINO = RAIZ_PROPIA / "docs" / "informes" / "responsive" / "capturas"

# Tamaños de la tabla del prompt (px físicos) y sus giros
TAMANOS = ["1024x600", "1280x720", "1366x768", "1440x900", "1600x900", "1920x1080",
           "1920x1200", "2560x1440", "1280x1024", "1024x768", "2560x1080",
           "600x1024", "720x1280", "768x1366", "900x1440", "1080x1920", "1200x1920",
           "1440x2560", "768x1024"]

TACTIL_JS = r"""
    // Zonas táctiles (tanda responsive): MouseArea, AbstractButton y TapHandler
    // visibles y habilitados; lado menor en px físicos bajo `minimo`.
    function zonasTactiles(raiz, W, H, dpr, minimo) {
        const malos = []
        let total = 0
        function nombre(it) {
            let p = it, n = ""
            for (let k = 0; p && k < 6 && !n; ++k, p = p.parent) n = p.objectName || ""
            let t = ""
            function txt(q, d) {
                if (t || !q || d > 3) return
                if (typeof q.text === "string" && q.text.trim() !== "") { t = q.text.slice(0, 30); return }
                const hs = q.children || []
                for (let i = 0; i < hs.length && !t; ++i) txt(hs[i], d + 1)
            }
            txt(it.parent && it.width < 4 ? it.parent : it, 0)
            if (!t && it.parent) txt(it.parent, 0)
            return n + "|" + t
        }
        function revisar(it, recorte, extra) {
            const p = it.mapToItem(null, 0, 0)
            const w = it.width, h = it.height
            if (w >= W - 4 && h >= H - 4) return          // velos a pantalla completa
            if (p.x + w < 0 || p.y + h < 0 || p.x > W || p.y > H) return
            if (recorte && (p.x >= recorte.x + recorte.w || p.x + w <= recorte.x
                            || p.y >= recorte.y + recorte.h || p.y + h <= recorte.y)) return
            total += 1
            const lado = (Math.min(w, h) + 2 * (extra || 0)) * dpr
            if (lado < minimo - 0.5)
                malos.push({obj: nombre(it), lado_fisico: Math.round(lado * 10) / 10,
                            x: Math.round(p.x), y: Math.round(p.y), w: Math.round(w), h: Math.round(h)})
        }
        function rec(it, recorte) {
            const hijos = it.children || []
            for (let i = 0; i < hijos.length; ++i) {
                const h = hijos[i]
                if (!h.visible || h.opacity === 0 || h.enabled === false) continue
                const esArea = h.pressAndHoldInterval !== undefined && h.drag !== undefined
                const esBoton = h.checkable !== undefined && h.autoExclusive !== undefined
                if ((esArea || esBoton) && h.width > 0 && h.height > 0) revisar(h, recorte)
                const recursos = h.resources || []
                for (let k = 0; k < recursos.length; ++k) {
                    const r = recursos[k]
                    if (r && r.gesturePolicy !== undefined && r.enabled !== false && h.width > 0)
                        revisar(h, recorte, r.margin || 0)
                }
                let nr = recorte
                if (h.clip) {
                    const q = h.mapToItem(null, 0, 0)
                    nr = {x: q.x, y: q.y, w: h.width, h: h.height}
                }
                rec(h, nr)
            }
        }
        rec(raiz, null)
        return JSON.stringify({total: total, malos: malos.slice(0, 80)})
    }
    function fuenteMinima(raiz) {
        let menor = 9999, cual = ""
        function rec(it) {
            const hijos = it.children || []
            for (let i = 0; i < hijos.length; ++i) {
                const h = hijos[i]
                if (!h.visible || h.opacity === 0) continue
                if (h.fontInfo !== undefined && typeof h.text === "string" && h.text.trim() !== ""
                        && h.width > 0 && h.fontInfo.pixelSize < menor) {
                    menor = h.fontInfo.pixelSize; cual = h.text.slice(0, 30)
                }
                rec(h)
            }
        }
        rec(raiz)
        return JSON.stringify({px: menor, texto: cual})
    }
"""

EXTRA_PY = r'''
        try:
            dpr = float(win.devicePixelRatio())
        except Exception:
            dpr = 1.0
        tactiles, lienzo_r, fmin = {}, None, {}
        if rev is not None:
            tactiles = json.loads(QMetaObject.invokeMethod(rev, "zonasTactiles", Q_RETURN_ARG("QVariant"),
                                  Q_ARG("QVariant", win.contentItem()), Q_ARG("QVariant", W),
                                  Q_ARG("QVariant", H), Q_ARG("QVariant", dpr),
                                  Q_ARG("QVariant", cfg.get("tactil", 44))))
            f = json.loads(QMetaObject.invokeMethod(rev, "fuenteMinima", Q_RETURN_ARG("QVariant"),
                                                    Q_ARG("QVariant", win.contentItem())))
            fmin = {"px_logico": f["px"], "px_fisico": round(f["px"] * dpr, 1), "texto": f["texto"]}
        for o in por_nombre(win, "lienzo"):
            pp = o.mapToScene(QPointF(0, 0))
            lienzo_r = [round(pp.x(), 1), round(pp.y(), 1), round(o.width(), 1), round(o.height(), 1)]
        sin_cubrir = None
        try:
            from PIL import Image as _Im
            import numpy as _np
            _a = _np.asarray(_Im.open(archivo).convert("RGB")).astype(_np.int16)
            _m = (_a[:, :, 0] >= 250) & (_a[:, :, 1] <= 5) & (_a[:, :, 2] >= 250)
            sin_cubrir = {"px": int(_m.sum()), "fraccion": round(float(_m.mean()), 6),
                          "bordes": {"arriba": int(_m[0].sum()), "abajo": int(_m[-1].sum()),
                                     "izquierda": int(_m[:, 0].sum()), "derecha": int(_m[:, -1].sum())}}
        except Exception as _e:
            sin_cubrir = {"error": repr(_e)}
        try:
            esc = engine.singletonInstance("Tema", "Escala")
            escala_v = {"factor": esc.property("factor"), "altoLienzo": esc.property("altoLienzo"),
                        "horizontal": esc.property("horizontal")}
        except Exception:
            escala_v = {}
'''


AREA_FIJA_PY = r'''
import re as _re
_FIJAS = _re.compile(r"\s*(Login|CambioClave|NuevoUsuario|PantallaPreciclo|Reposo)\s*\{")
def _area_fija(cuerpo):
    m = _FIJAS.match(cuerpo)
    if not m:
        return cuerpo
    prof, i, en_cad = 0, m.end() - 1, None
    while i < len(cuerpo):
        c = cuerpo[i]
        if en_cad:
            if c == en_cad and cuerpo[i - 1] != "\\":
                en_cad = None
        elif c in "'\"":
            en_cad = c
        elif c == "{":
            prof += 1
        elif c == "}":
            prof -= 1
            if prof == 0:
                break
        i += 1
    return "AreaFija { anchors.fill: parent\n" + cuerpo[:i + 1] + "\n}" + cuerpo[i + 1:]
'''


def guion(raiz: Path) -> str:
    """Guion de hor_capturas con la regla de proyección del árbol `raiz` (si
    ya existe Escala.factorPara) y las revisiones de esta tanda."""
    s = hor_capturas._SCRIPT
    escala = (raiz / "src" / "autoclave" / "ui_qml" / "qml" / "Tema" / "Escala.qml").read_text(encoding="utf-8")
    if "function factorPara" in escala:
        viejo_f = ('Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / '
                   'Escala.anchoDiseno, ventana.height / Escala.altoDiseno) }')
        viejo_a = ('Binding { target: Escala; property: "altoLienzo"; value: Math.max(Escala.altoDiseno, '
                   'ventana.height / Escala.factor) }')
        assert viejo_f in s and viejo_a in s
        s = s.replace(viejo_f, 'Binding { target: Escala; property: "factor"; value: '
                               'Escala.factorPara(ventana.width, ventana.height) }')
        s = s.replace(viejo_a, 'Binding { target: Escala; property: "altoLienzo"; value: '
                               'Escala.altoLienzoPara(ventana.width, ventana.height) }')
        if "function anchoLienzoPara" in escala:
            s = s.replace('            width: Escala.px(Escala.anchoDiseno); height: Escala.px(Escala.altoLienzo)',
                          '            width: Escala.px(Escala.anchoLienzo); height: Escala.px(Escala.altoLienzo)', 1)
            s = s.replace('Binding { target: Escala; property: "factor";',
                          'Binding { target: Escala; property: "anchoLienzo"; value: '
                          'Escala.anchoLienzoPara(ventana.width, ventana.height) }\n'
                          '            Binding { target: Escala; property: "factor";', 1)
        if "property real dpr" in escala:
            s = s.replace('Binding { target: Escala; property: "factor";',
                          'property real _dprResp: Screen.devicePixelRatio\n'
                          '            Binding { target: Escala; property: "dpr"; value: ventana._dprResp }\n'
                          '            Binding { target: Escala; property: "factor";', 1)
    # Como en Main.qml: las pantallas de alto fijo van dentro de AreaFija (el
    # guion de la tanda horizontal las ponía directo en el lienzo, que solo
    # da lo mismo cuando el lienzo mide exactamente el de diseño)
    marca_env = '    """ % (W, H, BIND_HZ, extra, cuerpo)\n'
    assert marca_env in s
    s = s.replace(marca_env, '    """ % (W, H, BIND_HZ, extra, _area_fija(cuerpo))\n', 1)
    s = s.replace("def envolver(cuerpo, extra=\"\"):", AREA_FIJA_PY + "\ndef envolver(cuerpo, extra=\"\"):", 1)
    s = s.replace("function fueraDelLienzo(raiz, W, H) {", TACTIL_JS + "\nfunction fueraDelLienzo(raiz, W, H) {", 1)
    # Criterio «sin barras»: la ventana se pinta de un color centinela (magenta
    # puro, que ningún tema usa); todo px de ese color en la captura es ventana
    # sin cubrir por la pantalla
    s = s.replace("    win.show()\n", "    win.show()\n    from PySide6.QtGui import QColor as _QC\n"
                  "    win.setColor(_QC(255, 0, 255))\n", 1)
    marca = '    print("captura", nombre, len(problemas), "problemas", len(fuera), "fuera")\n'
    assert marca in s
    s = s.replace(marca, textwrap.indent(textwrap.dedent(EXTRA_PY), "    ") + marca, 1)
    s = s.replace('    return {"problemas": problemas, "fuera": fuera,',
                  '    return {"problemas": problemas, "fuera": fuera, "tactiles": tactiles,\n'
                  '            "lienzo": lienzo_r, "fuente_min": fmin, "escala": escala_v, "dpr": dpr,\n'
                  '            "sin_cubrir": sin_cubrir,', 1)
    return s


def correr(raiz: Path, destino: Path, tamano: str, escala: float, tema: str, escenarios, idioma: str,
           plataforma: str, tactil: float) -> dict:
    fw, fh = (int(x) for x in tamano.split("x"))
    lw, lh = round(fw / escala), round(fh / escala)
    carpeta = destino / f"{tamano}@{escala:g}"
    carpeta.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "QT_QPA_PLATFORM": plataforma,
           "PYTHONPATH": str(raiz / "src") + os.pathsep + str(RAIZ_PROPIA)}
    for k in ("QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS", "QT_ENABLE_HIGHDPI_SCALING"):
        env.pop(k, None)
    if escala == 1:
        env["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    else:
        env["QT_ENABLE_HIGHDPI_SCALING"] = "1"
        env["QT_SCREEN_SCALE_FACTORS"] = f"{escala:g}"
        env["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"
    cfg = {"tema": tema, "destino": str(carpeta), "ancho": lw, "alto": lh, "escenarios": escenarios,
           "idioma": idioma, "banco": str(RAIZ_PROPIA / "tests" / "banco"), "tactil": tactil}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", guion(raiz), json.dumps(cfg)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=raiz, timeout=3600)
    resumen = {}
    for linea in p.stdout.splitlines():
        if linea.startswith("RESUMEN="):
            resumen = json.loads(linea[len("RESUMEN="):])
    if p.returncode != 0 or not resumen:
        print(tamano, escala, tema, "ERROR", p.stderr[-2000:], file=sys.stderr)
    sufijo = "" if escenarios is None else "_parcial"
    (carpeta / f"resumen_{tema}{sufijo}.json").write_text(
        json.dumps({"tamano_fisico": [fw, fh], "escala": escala, "logico": [lw, lh], "resultado": resumen},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("hecho", tamano, escala, tema, len(resumen), "escenarios", flush=True)
    return resumen


# ── Análisis: defectos que aparecen en un tamaño y no en el de diseño ──────

def _firma(p: dict) -> str:
    return f'{p.get("tipo")}|{p.get("texto", p.get("obj", ""))}'


def analizar(destino: Path, tema: str = "claro") -> dict:
    """Por tamaño y escenario, los problemas de texto y de «fuera» que no tiene
    el mismo escenario en el tamaño de diseño de su orientación (1920x1200 o
    1200x1920 a 100 %), las zonas táctiles bajo el mínimo y la letra mínima."""
    datos = {}
    for f in sorted(destino.glob(f"*@*/resumen_{tema}.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        datos[f.parent.name] = d
    base = {"h": datos.get("1920x1200@1", {}).get("resultado", {}),
            "v": datos.get("1200x1920@1", {}).get("resultado", {})}
    tabla = {}
    for clave, d in datos.items():
        fw, fh = d["tamano_fisico"]
        ref = base["h" if fw >= fh else "v"]
        fila = {"escala": d["escala"], "logico": d["logico"], "escenarios": {}}
        for esc, r in d["resultado"].items():
            if not isinstance(r, dict) or "error" in r:
                fila["escenarios"][esc] = {"error": (r or {}).get("error", "sin datos")}
                continue
            b = ref.get(esc) or {}
            conocidos = {_firma(p) for p in b.get("problemas", [])} | {_firma(p) for p in b.get("fuera", [])}
            nuevos = [p for p in r.get("problemas", []) + r.get("fuera", []) if _firma(p) not in conocidos]
            t = r.get("tactiles") or {}
            fila["escenarios"][esc] = {
                "nuevos": nuevos[:20], "n_nuevos": len(nuevos),
                "tactiles_bajo_minimo": len(t.get("malos", [])), "tactiles_total": t.get("total"),
                "tactiles": t.get("malos", [])[:30],
                "fuente_min": r.get("fuente_min"), "lienzo": r.get("lienzo"), "escala_qml": r.get("escala"),
                "sin_cubrir": r.get("sin_cubrir"),
            }
        tabla[clave] = fila
    salida = destino / f"analisis_{tema}.json"
    salida.write_text(json.dumps(tabla, ensure_ascii=False, indent=1), encoding="utf-8")
    for clave, fila in tabla.items():
        n = sum(e.get("n_nuevos", 0) for e in fila["escenarios"].values())
        t = sum(e.get("tactiles_bajo_minimo", 0) for e in fila["escenarios"].values())
        errores = [k for k, e in fila["escenarios"].items() if "error" in e]
        fmin = min((e["fuente_min"]["px_fisico"] for e in fila["escenarios"].values()
                    if e.get("fuente_min")), default=None)
        sc = [k for k, e in fila["escenarios"].items() if (e.get("sin_cubrir") or {}).get("px")]
        print(f"{clave:16s} nuevos={n:4d} tactiles<min={t:4d} letra_min_fisica={fmin} sin_cubrir={sc} errores={errores}")
    return tabla


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tamanos", nargs="+", default=TAMANOS)
    ap.add_argument("--escalas", nargs="+", type=float, default=[1.0])
    ap.add_argument("--temas", nargs="+", default=["claro"])
    ap.add_argument("--escenarios", nargs="*", default=None)
    ap.add_argument("--destino", default=str(DESTINO))
    ap.add_argument("--idioma", default="es")
    ap.add_argument("--plataforma", default="windows")
    ap.add_argument("--raiz", default=str(RAIZ_PROPIA))
    ap.add_argument("--paralelo", type=int, default=4)
    ap.add_argument("--tactil", type=float, default=44.0)
    ap.add_argument("--analizar", default=None, help="carpeta ya capturada: solo analiza")
    a = ap.parse_args()
    if a.analizar:
        for tema in a.temas:
            analizar(Path(a.analizar), tema)
        return 0
    destino = Path(a.destino)
    trabajos = [(t, e, tema) for t in a.tamanos for e in a.escalas for tema in a.temas]
    with ThreadPoolExecutor(max_workers=max(1, a.paralelo)) as ex:
        list(ex.map(lambda x: correr(Path(a.raiz), destino, x[0], x[1], x[2], a.escenarios, a.idioma,
                                     a.plataforma, a.tactil), trabajos))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

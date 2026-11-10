# tests/banco/resp_geometria_igual.py
#
# Tanda responsive (10-nov): segunda evidencia de que 1200x1920 y 1920x1200
# quedaron iguales a dev, sin depender de la fase de las animaciones. Para cada
# escenario de tests/banco/hor_capturas.py vuelca la geometría de TODOS los
# ítems visibles (clase, objectName, x, y, ancho, alto en coordenadas de la
# ventana, con 2 decimales, texto y tamaño de letra) con el árbol de dev y con
# este, y compara las listas. No es una prueba automática.
#
#   python tests/banco/resp_geometria_igual.py --dev <worktree de dev> [--tamanos ...] [--escenarios ...]
#
# Deja docs/informes/responsive/geometria_igual_<WxH>.json.

import argparse
import json
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from tests.banco import hor_capturas  # noqa: E402

VOLCADO_JS = r"""
function volcarGeometria(raiz) {
    const r = []
    // ítems dentro de componentes con animación continua (pulso y destellos
    // del deslizador, vapor y burbujas de los círculos de fase): su posición
    // depende del instante de la captura; se marcan y no se comparan
    const ANIMADOS = ["DeslizadorInicio", "CirculoFaseLiquido"]
    function rec(it, ruta, anim) {
        const hijos = it.children || []
        for (let i = 0; i < hijos.length; ++i) {
            const h = hijos[i]
            if (!h.visible || h.opacity === 0) continue
            const p = h.mapToItem(null, 0, 0)
            const clase = String(h).split("(")[0].split("_QML")[0]
            const a = anim || ANIMADOS.indexOf(clase) >= 0
            r.push([(a ? "A" : "") + ruta + "/" + i, clase, h.objectName || "", Math.round(p.x * 100) / 100, Math.round(p.y * 100) / 100,
                    Math.round(h.width * 100) / 100, Math.round(h.height * 100) / 100,
                    typeof h.text === "string" ? h.text.slice(0, 40) : "",
                    h.font !== undefined && h.font ? h.font.pixelSize : 0])
            rec(h, ruta + "/" + i, a)
        }
    }
    rec(raiz, "", false)
    return JSON.stringify(r)
}
"""

EXTRA = textwrap.indent(textwrap.dedent(r'''
    geometria = []
    if rev is not None:
        geometria = json.loads(QMetaObject.invokeMethod(rev, "volcarGeometria", Q_RETURN_ARG("QVariant"),
                                                        Q_ARG("QVariant", win.contentItem())))
'''), "    ")


def guion() -> str:
    s = hor_capturas._SCRIPT
    s = s.replace("function fueraDelLienzo(raiz, W, H) {", VOLCADO_JS + "\nfunction fueraDelLienzo(raiz, W, H) {", 1)
    marca = '    print("captura", nombre, len(problemas), "problemas", len(fuera), "fuera")\n'
    assert marca in s
    s = s.replace(marca, EXTRA + marca, 1)
    s = s.replace('    return {"problemas": problemas, "fuera": fuera,',
                  '    return {"geometria": geometria, "problemas": problemas, "fuera": fuera,', 1)
    return s


def volcar(raiz: Path, tamano: str, escenarios, destino: Path) -> dict:
    import os
    w, h = (int(x) for x in tamano.split("x"))
    destino.mkdir(parents=True, exist_ok=True)
    cfg = {"tema": "claro", "destino": str(destino), "ancho": w, "alto": h, "escenarios": escenarios,
           "idioma": "es", "banco": str(RAIZ / "tests" / "banco")}
    env = {**os.environ, "QT_ENABLE_HIGHDPI_SCALING": "0", "QT_QPA_PLATFORM": "windows",
           "PYTHONPATH": str(raiz / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", guion(), json.dumps(cfg)], capture_output=True,
                       text=True, encoding="utf-8", env=env, cwd=raiz, timeout=3600)
    for linea in p.stdout.splitlines():
        if linea.startswith("RESUMEN="):
            return json.loads(linea[len("RESUMEN="):])
    print(p.stderr[-2000:], file=sys.stderr)
    return {}


def main() -> int:
    import tempfile
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", required=True)
    ap.add_argument("--tamanos", nargs="+", default=["1200x1920", "1920x1200"])
    ap.add_argument("--escenarios", nargs="*", default=None)
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="resp_geom_"))
    trabajos = ([(Path(a.dev), t, "dev") for t in a.tamanos] + [(Path(a.dev), t, "dev2") for t in a.tamanos]
                + [(RAIZ, t, "rama") for t in a.tamanos])
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(lambda x: volcar(x[0], x[1], a.escenarios, tmp / f"{x[1]}_{x[2]}"), trabajos))
    datos = {(t, q): r for (_, t, q), r in zip(trabajos, res)}
    malos_total = 0
    for t in a.tamanos:
        dev, dev2, rama = datos[(t, "dev")], datos[(t, "dev2")], datos[(t, "rama")]
        salida = {}
        for esc in sorted(dev):
            gd = [tuple(x) for x in (dev[esc] or {}).get("geometria", [])]
            gr = [tuple(x) for x in (rama.get(esc) or {}).get("geometria", [])]
            # el texto del reloj cambia de minuto: no cuenta
            # sin la ruta en el árbol y sin los Item contenedores anónimos: la rama
            # agrega contenedores (bloque de ciclo centrado) que a estos tamaños
            # miden lo mismo que la pantalla y no dibujan nada; lo que se compara
            # es dónde queda y qué tamaño tiene cada cosa que se ve
            def sin_hora(g):
                return sorted(x[1:7] + (("HH:MM" if len(x[7]) == 5 and x[7][2:3] == ":" else x[7]),) + x[8:]
                              for x in g if not (x[1] == "QQuickItem" and not x[2]) and not x[0].startswith("A"))
            # lo que se mueve solo (cambia entre dos corridas de dev: pulso del
            # deslizador, vapor de las fases...) se identifica por clase, nombre
            # y tamaño y no se compara
            g2 = sin_hora([tuple(x) for x in (dev2.get(esc) or {}).get("geometria", [])])
            from collections import Counter
            a1, a2 = Counter(sin_hora(gd)), Counter(g2)
            moviles = {(x[0], x[1], x[4], x[5]) for x in ((a1 - a2) + (a2 - a1))}
            gd2 = [x for x in sin_hora(gd) if (x[0], x[1], x[4], x[5]) not in moviles]
            gr2 = [x for x in sin_hora(gr) if (x[0], x[1], x[4], x[5]) not in moviles]
            if gd2 == gr2:
                salida[esc] = {"igual": True, "items": len(gd2), "moviles_excluidos": len(moviles)}
            else:
                dif = [(x, y) for x, y in zip(gd2, gr2) if x != y][:8]
                salida[esc] = {"igual": False, "items": [len(gd2), len(gr2)], "diferencias": dif}
        distintos = [e for e, r in salida.items() if not r["igual"]]
        malos_total += len(distintos)
        (RAIZ / "docs" / "informes" / "responsive" / f"geometria_igual_{t}.json").write_text(
            json.dumps({"tamano": t, "escenarios": len(salida), "distintos": distintos, "resultado": salida},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        print(t, "escenarios", len(salida), "DISTINTOS:", distintos or "ninguno")
    return 1 if malos_total else 0


if __name__ == "__main__":
    raise SystemExit(main())

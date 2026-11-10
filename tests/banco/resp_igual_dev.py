# tests/banco/resp_igual_dev.py
#
# Tanda responsive (10-nov): demuestra que 1200x1920 y 1920x1200 al 100 %
# quedaron IDÉNTICOS a dev. Captura todos los escenarios de
# tests/banco/hor_capturas.py (y hor_escenarios_*.py) con el árbol de dev
# (--dev, un worktree de dev) y con este árbol, y los compara píxel a píxel con
# la misma función de tests/banco/hor_vertical_igual.py (ignora solo la franja
# del reloj, y < 190). Con --dev-contra-dev captura dev dos veces para saber
# qué escenarios cambian solos entre corridas (animación o reloj): esos se
# informan aparte y no cuentan como diferencia. No es una prueba automática.
#
#   python tests/banco/resp_igual_dev.py --dev <worktree de dev> [--tamanos 1200x1920 1920x1200]
#          [--temas claro] [--escenarios a b]
#
# Deja docs/informes/responsive/igual_dev_<WxH>_<tema>.json.

import argparse
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from tests.banco.hor_vertical_igual import comparar  # noqa: E402

SALIDA = RAIZ / "docs" / "informes" / "responsive"


def capturar(raiz: Path, destino: Path, tamano: str, tema: str, escenarios) -> None:
    cmd = [sys.executable, str(RAIZ / "tests" / "banco" / "hor_capturas.py"), "--temas", tema,
           "--tamano", tamano, "--destino", str(destino), "--raiz", str(raiz)]
    if escenarios:
        cmd += ["--escenarios", *escenarios]
    subprocess.run(cmd, check=False, capture_output=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", required=True)
    ap.add_argument("--tamanos", nargs="+", default=["1200x1920", "1920x1200"])
    ap.add_argument("--temas", nargs="+", default=["claro"])
    ap.add_argument("--escenarios", nargs="*", default=None)
    ap.add_argument("--sin-dev-contra-dev", action="store_true")
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="resp_igual_"))
    trabajos = []
    for t in a.tamanos:
        for tema in a.temas:
            trabajos.append((Path(a.dev), tmp / f"{t}_{tema}" / "dev", t, tema))
            trabajos.append((RAIZ, tmp / f"{t}_{tema}" / "rama", t, tema))
            if not a.sin_dev_contra_dev:
                trabajos.append((Path(a.dev), tmp / f"{t}_{tema}" / "dev2", t, tema))
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(lambda x: capturar(x[0], x[1], x[2], x[3], a.escenarios), trabajos))
    total_malos = 0
    for t in a.tamanos:
        for tema in a.temas:
            base = tmp / f"{t}_{tema}"
            resumen, animados = {}, []
            for f in sorted((base / "dev").glob(f"hor_{tema}_*.png")):
                nombre = f.stem[len(f"hor_{tema}_"):]
                g = base / "rama" / f.name
                resumen[nombre] = comparar(f, g) if g.exists() else {"igual": False, "motivo": "sin captura"}
                h = base / "dev2" / f.name
                if h.exists() and not comparar(f, h)["igual"]:
                    animados.append(nombre)
                    resumen[nombre]["dev_contra_dev_distinto"] = True
            # Una diferencia cuya caja queda DENTRO de una zona que cambia sola
            # entre dos corridas de dev en algún escenario de este tamaño (p. ej.
            # el pulso del deslizador INICIAR, que es el mismo en todas las
            # variantes de Preciclo) se marca como «en zona animada»
            cajas_anim = [r.get("caja") for n, r in resumen.items() if n in animados and r.get("caja")]
            cajas_anim += [comparar(base / "dev" / f"hor_{tema}_{n}.png", base / "dev2" / f"hor_{tema}_{n}.png").get("caja")
                           for n in animados if (base / "dev2" / f"hor_{tema}_{n}.png").exists()]
            cajas_anim = [c for c in cajas_anim if c]

            def _dentro(c):
                return any(c[0] >= a[0] - 4 and c[1] >= a[1] - 4 and c[2] <= a[2] + 4 and c[3] <= a[3] + 4
                           for a in cajas_anim)
            por_region = [n for n, r in resumen.items()
                          if not r["igual"] and n not in animados and r.get("caja") and _dentro(r["caja"])]
            for n in por_region:
                resumen[n]["en_zona_animada"] = True
            # se informan aparte pero SIGUEN contando como distintos: la zona es
            # amplia (la gráfica animada cubre casi toda la pantalla) y puede
            # ocultar un cambio real; la geometría (resp_geometria_igual.py) decide
            distintos = [n for n, r in resumen.items() if not r["igual"] and n not in animados]
            total_malos += len(distintos)
            SALIDA.mkdir(parents=True, exist_ok=True)
            (SALIDA / f"igual_dev_{t}_{tema}.json").write_text(json.dumps(
                {"tamano": t, "tema": tema, "carpeta": str(base), "escenarios": len(resumen),
                 "identicos": sum(1 for r in resumen.values() if r["igual"]),
                 "animados_dev_contra_dev": animados, "en_zona_animada": por_region, "distintos_reales": distintos,
                 "resultado": resumen}, ensure_ascii=False, indent=1), encoding="utf-8")
            print(t, tema, "escenarios", len(resumen), "idénticos",
                  sum(1 for r in resumen.values() if r["igual"]), "animados", animados, "en zona animada", por_region,
                  "DISTINTOS:", distintos or "ninguno")
    return 1 if total_malos else 0


if __name__ == "__main__":
    raise SystemExit(main())

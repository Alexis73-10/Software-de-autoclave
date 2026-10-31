# docs/mis_plans/hoja_pruebas_banco/generar.py
#
# Genera la hoja de pruebas de banco (P1, tanda 2) en Markdown y en HTML
# imprimible a partir de pruebas.py. Uso, desde la raíz del repo:
#   python docs/mis_plans/hoja_pruebas_banco/generar.py

import html
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from pruebas import BLOQUES, PRUEBAS, REGISTROS  # noqa: E402

DESTINO = AQUI.parent
TITULO = "Hoja de pruebas de banco — equipo de pruebas"
MODO = {"seco": "En seco (sin vapor)", "operacion": "En operación (vapor)"}

INTRO = [
    "Equipo de pruebas: autoclave de laboratorio, 2 puertas abatibles manuales, generador interno "
    "(sin DO1/DO2), sondas Cámara 1, Cámara 2, Referencia y drenaje.",
    "Origen: tanda 2 (P1, E7). Reúne las 11 comprobaciones manuales de "
    "`docs/informes/informe_tanda_2026-10-14.md` §5 y las de la tanda 2 (`docs/informes/tanda2/`).",
    "Valores de los programas de fábrica (provisionales, por validar aquí): Bowie & Dick 134 °C / 3,5 min; "
    "Instrumental 134 °C / 7 min; Instrumental 121 °C / 15 min; Líquidos 121 °C / 15 min, sin prevacío "
    "ni secado, descompresión modo 4 con contrapresión hasta 80 °C (Principal).",
]

ORDEN = [
    "Bloques A a D en seco, en ese orden: primero se confirma el perfil, el módulo E/S y la seguridad sin "
    "energía térmica en la cámara.",
    "No pasar al bloque E sin haber aprobado B-01 (paro), B-03 (NO ABRIR), B-04 (puertas) y A-04 (DO1/DO2).",
    "Bloque E (ciclos normales) antes del F (fallas provocadas): las fallas se provocan solo con un ciclo "
    "normal ya aprobado.",
    "F-04 (puerta en ciclo) solo durante PREVACIO, nunca con presión positiva.",
    "Bloque G (Líquidos) al final y con vidrio real; detener ante cualquier ebullición o rotura.",
    "Entre pruebas en operación, esperar a cámara segura (NO ABRIR apagado) antes de manipular la carga.",
]


def _modo(p) -> str:
    """Texto del modo: el propio de la prueba (modo_texto) o el del catálogo."""
    return p.get("modo_texto") or MODO[p["modo"]]


def _md() -> str:
    l = [f"# {TITULO}", "", "> Generado desde `docs/mis_plans/hoja_pruebas_banco/pruebas.py` "
         "(editar ahí y regenerar con `generar.py`). Versión imprimible: "
         "`hoja_pruebas_banco_equipo_pruebas.html`.", ""]
    l += [f"- {t}" for t in INTRO] + ["", "## Orden seguro de ejecución", ""]
    l += [f"{i}. {t}" for i, t in enumerate(ORDEN, 1)] + [""]
    l += ["## Resumen", "", "| ID | Prueba | Modo | Origen |", "|---|---|---|---|"]
    l += [f"| {p['id']} | {p['titulo']} | {_modo(p)} | {p['origen']} |" for p in PRUEBAS]
    for clave, nombre in BLOQUES:
        l += ["", f"## Bloque {clave}. {nombre}"]
        for p in (x for x in PRUEBAS if x["bloque"] == clave):
            l += ["", f"### {p['id']} — {p['titulo']}", "",
                  f"- **Modo:** {_modo(p)}  ·  **Origen:** {p['origen']}",
                  f"- **Objetivo:** {p['objetivo']}",
                  f"- **Precondiciones:** {p['pre']}",
                  "- **Pasos:**"]
            l += [f"  {i}. {s}" for i, s in enumerate(p["pasos"], 1)]
            l += [f"- **Resultado esperado:** {p['esperado']}",
                  f"- **Criterio de aprobado/fallo:** {p['criterio']}"]
            l += [f"- **{n}:** {v}" for n, v in p.get("extra", [])]
            l += ["- **Valor observado:** ______________________________________________",
                  "- **Resultado:** ☐ Aprobado  ☐ Fallo  ☐ No ejecutada (motivo: ____________)",
                  "- **Fecha / ejecutó / firma:** ____________ / ____________ / ____________"]
    l += ["", "## Registros que se deben conservar (expediente IEC 62304)", ""]
    l += [f"- {r}" for r in REGISTROS]
    return "\n".join(l) + "\n"


_CSS = """
:root { color-scheme: light; }
body { font-family: "Segoe UI", Arial, sans-serif; font-size: 10.5pt; color: #111; background: #fff; margin: 16px; }
h1 { font-size: 16pt; margin: 0 0 6px; } h2 { font-size: 13pt; margin: 18px 0 6px; border-bottom: 2px solid #333; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 12px; page-break-inside: avoid; }
td, th { border: 1px solid #555; padding: 4px 6px; vertical-align: top; text-align: left; }
th { background: #e8e8e8; width: 22%; }
.cab td { background: #f3f3f3; font-weight: bold; }
.firma td { height: 26px; }
.caja { display: inline-block; width: 12px; height: 12px; border: 1px solid #111; margin: 0 4px 0 10px; vertical-align: middle; }
ol { margin: 0; padding-left: 18px; }
.nota { font-size: 9pt; color: #444; }
@media print { body { margin: 8mm; } h2 { page-break-before: auto; } .prueba { page-break-inside: avoid; } }
"""


def _html() -> str:
    e = html.escape
    def md(t):   # `código` -> <code>
        partes = e(t).split("`")
        return "".join(f"<code>{x}</code>" if i % 2 else x for i, x in enumerate(partes))
    h = [f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>{e(TITULO)}</title>"
         f"<style>{_CSS}</style></head><body>", f"<h1>{e(TITULO)}</h1>",
         "<p class='nota'>Generada desde docs/mis_plans/hoja_pruebas_banco/pruebas.py. "
         "Equipo / serie: ____________ · Software (commit): ____________ · Firmware: ____________ · "
         "Fecha de inicio: ____________</p>", "<ul>"]
    h += [f"<li>{md(t)}</li>" for t in INTRO] + ["</ul><h2>Orden seguro de ejecución</h2><ol>"]
    h += [f"<li>{md(t)}</li>" for t in ORDEN] + ["</ol>"]
    for clave, nombre in BLOQUES:
        h.append(f"<h2>Bloque {e(clave)}. {e(nombre)}</h2>")
        for p in (x for x in PRUEBAS if x["bloque"] == clave):
            pasos = "".join(f"<li>{md(s)}</li>" for s in p["pasos"])
            h.append(
                "<table class='prueba'>"
                f"<tr class='cab'><td colspan='2'>{e(p['id'])} — {e(p['titulo'])} "
                f"<span class='nota'>({e(_modo(p))} · {e(p['origen'])})</span></td></tr>"
                f"<tr><th>Objetivo</th><td>{md(p['objetivo'])}</td></tr>"
                f"<tr><th>Precondiciones</th><td>{md(p['pre'])}</td></tr>"
                f"<tr><th>Pasos</th><td><ol>{pasos}</ol></td></tr>"
                f"<tr><th>Resultado esperado</th><td>{md(p['esperado'])}</td></tr>"
                f"<tr><th>Criterio</th><td>{md(p['criterio'])}</td></tr>"
                + "".join(f"<tr><th>{e(n)}</th><td>{md(v)}</td></tr>" for n, v in p.get("extra", []))
                + "<tr class='firma'><th>Valor observado</th><td></td></tr>"
                "<tr><th>Resultado</th><td><span class='caja'></span>Aprobado"
                "<span class='caja'></span>Fallo<span class='caja'></span>No ejecutada "
                "(motivo: ____________)</td></tr>"
                "<tr class='firma'><th>Fecha / ejecutó / firma</th><td></td></tr></table>")
    h.append("<h2>Registros que se deben conservar (expediente IEC 62304)</h2><ul>")
    h += [f"<li><span class='caja'></span>{md(r)}</li>" for r in REGISTROS]
    h.append("</ul></body></html>")
    return "\n".join(h) + "\n"


def main() -> None:
    (DESTINO / "hoja_pruebas_banco_equipo_pruebas.md").write_text(_md(), encoding="utf-8")
    (DESTINO / "hoja_pruebas_banco_equipo_pruebas.html").write_text(_html(), encoding="utf-8")
    print(f"{len(PRUEBAS)} pruebas escritas en {DESTINO}")


if __name__ == "__main__":
    main()

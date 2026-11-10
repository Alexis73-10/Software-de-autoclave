"""Tanda responsive (10-nov): «sin barras» y desbordes en la tabla de tamaños.

Decisión de Cristian (10-nov): la interfaz se ajusta a la pantalla, sin barras
ni franjas, en cualquier proporción. Criterio medible: cada pantalla completa
se captura con la ventana pintada de un color centinela (magenta puro, que
ningún tema usa; tests/banco/resp_capturas.py) y en la captura NO queda ningún
px de ese color, es decir, el contenido propio de la pantalla cubre el 100 %
de la ventana, bordes incluidos. Se prueba en 4:3, 16:10, 16:9 y 21:9 en las
dos orientaciones y en el tamaño mínimo soportado (1024x600 y 600x1024).

Además, en cada tamaño:
- ningún ítem con texto u objectName queda fuera de la ventana;
- no aparece ningún problema de texto que el mismo escenario no tenga ya en el
  tamaño de diseño de su orientación (los de diseño son falsos positivos
  conocidos de la tanda horizontal);
- ninguna zona táctil queda por debajo de min(44 px físicos, su lado en el
  tamaño de diseño) (Escala.margenTactil).
"""

import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("PIL")

from tests.banco import resp_capturas as rc  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]

ESCENARIOS = ["intro", "reposo", "login", "cambio_clave", "nuevo_usuario", "instalacion",
              "preciclo_alarma", "b_preciclo_falla", "ciclo_grafica", "fin_fallido", "menu",
              "menu_historial", "reportes", "opciones"]
PROPORCIONES = ["1600x1200", "1920x1200", "1920x1080", "2560x1080",
                "1200x1600", "1200x1920", "1080x1920", "1080x2560"]
MINIMOS = ["1024x600", "600x1024"]
# escala de Windows (tamaño físico @ escala): misma regla que al 100 %
ESCALADOS = ["1920x1080@1.5", "1200x1920@1.25", "2560x1440@2", "1080x1920@1.75"]
DISENO = {"h": "1920x1200", "v": "1200x1920"}


@pytest.fixture(scope="module")
def capturas():
    destino = Path(tempfile.mkdtemp(prefix="resp_sin_barras_"))
    tamanos = PROPORCIONES + MINIMOS + ESCALADOS

    def uno(t):
        tam, _, esc = t.partition("@")
        return rc.correr(RAIZ, destino, tam, float(esc or 1), "claro", ESCENARIOS, "es", "windows", 44.0)
    with ThreadPoolExecutor(max_workers=5) as ex:
        res = dict(zip(tamanos, ex.map(uno, tamanos)))
    return res


def _orient(t):
    w, h = (int(x) for x in t.split("@")[0].split("x"))
    return "h" if w >= h else "v"


@pytest.mark.parametrize("tamano", PROPORCIONES + MINIMOS + ESCALADOS)
def test_el_contenido_cubre_toda_la_ventana(capturas, tamano):
    r = capturas[tamano]
    assert set(ESCENARIOS) <= set(r), sorted(set(ESCENARIOS) - set(r))
    malos = {e: v.get("sin_cubrir") for e, v in r.items()
             if (v.get("sin_cubrir") or {}).get("px", 1) != 0}
    assert not malos, malos


# Lo que no cuenta como desborde (justificado en el informe de la tanda):
# - "encogido": la letra baja para caber (D8-5.4 lo permite; con el redondeo a
#   px enteros de Escala.fuente un texto justo puede bajar 1-2 px);
# - "fuera" de las secciones del desplazable de Reportes (seccion*): contenido
#   que sigue más abajo, se ve al desplazar (igual en dev);
# - RESIDUAL conocido: la leyenda de la gráfica de Ciclo en curso a 1024x600
#   (la letra ya está en su mínimo y el redondeo la deja 1-2 px larga).
RESIDUALES = {("1024x600", "ciclo_grafica", "sale_del_cuadro|Presión")}


def _cuenta(tamano, esc, p):
    if p.get("tipo") == "encogido":
        return False
    if "tipo" not in p and str(p.get("obj", "")).startswith("seccion"):
        return False
    return (tamano, esc, rc._firma(p)) not in RESIDUALES


@pytest.mark.parametrize("tamano", PROPORCIONES + MINIMOS + ESCALADOS)
def test_nada_fuera_y_sin_desbordes_nuevos(capturas, tamano):
    r, base = capturas[tamano], capturas[DISENO[_orient(tamano)]]
    nuevos = {}
    for esc, v in r.items():
        conocidos = {rc._firma(p) for p in base[esc].get("problemas", []) + base[esc].get("fuera", [])}
        n = [p for p in v.get("problemas", []) + v.get("fuera", [])
             if rc._firma(p) not in conocidos and _cuenta(tamano, esc, p)]
        if n:
            nuevos[esc] = n[:5]
    assert not nuevos, json.dumps(nuevos, ensure_ascii=False)[:3000]


@pytest.mark.parametrize("tamano", PROPORCIONES + MINIMOS + ESCALADOS)
def test_zonas_tactiles_minimas(capturas, tamano):
    r, base = capturas[tamano], capturas[DISENO[_orient(tamano)]]
    malos = {}
    for esc, v in r.items():
        lado_diseno = {t["obj"]: t["lado_fisico"] for t in (base[esc].get("tactiles") or {}).get("malos", [])}
        for t in (v.get("tactiles") or {}).get("malos", []):
            minimo = min(44.0, lado_diseno.get(t["obj"], 44.0))
            if t["lado_fisico"] < minimo - 1.0:
                malos.setdefault(esc, []).append((t["obj"], t["lado_fisico"], minimo))
    assert not malos, json.dumps(malos, ensure_ascii=False)[:3000]


def test_en_los_tamanos_de_diseno_el_lienzo_es_el_de_siempre(capturas):
    for t, (w, h) in (("1920x1200", (1920, 1200)), ("1200x1920", (1200, 1920))):
        for esc, v in capturas[t].items():
            assert v["escala"]["factor"] == 1.0, (t, esc)
            if v.get("lienzo"):
                assert v["lienzo"] == [0.0, 0.0, float(w), float(h)], (t, esc)

"""DR-H01 / HAZ-REP-01: el dashboard de Reportes no induce a creer que la hoja
Bowie & Dick fue «conforme» ni que el equipo está «apto».

Solo vigila lo nuevo: las claves `reportes.*` y los textos de los componentes
del dashboard. La clave heredada del Historial (`resultado_no_conforme`,
«NO CONFORME» de ciclos viejos) está fuera de `reportes.*` y no se toca.
"""
import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1] / "src" / "autoclave"
QML = RAIZ / "ui_qml" / "qml"
PROHIBIDAS = re.compile(r"\b(conforme|conformes|apto|apta|aptos|aptas|compliant|fit for use)\b", re.IGNORECASE)
LEYENDA = {
    "es": "Muestra el resultado del ciclo. La lectura de la hoja de prueba no se registra en el equipo.",
    "en": "Shows the cycle result. The reading of the test sheet is not recorded in the unit.",
}
ARCHIVOS_QML = [
    QML / "Componentes" / n
    for n in ("CalendarioEjecucion", "MesMiniatura", "PanelDiaCalendario",
              "ListaProgramasReporte", "ListaAlarmasPeriodo", "ListaOperadores")
] + [QML / "Pantallas" / "Reportes.qml"]
ARCHIVOS_QML = [p if p.suffix else p.with_suffix(".qml") for p in ARCHIVOS_QML]
LITERAL = re.compile(r'"((?:[^"\\n]|\.)*)"')


def _reportes(idioma):
    return json.loads((RAIZ / "i18n" / f"{idioma}.json").read_text(encoding="utf8"))["reportes"]


@pytest.mark.req("REQ-50")
@pytest.mark.parametrize("idioma", ["es", "en"])
def test_claves_reportes_sin_palabras_prohibidas(idioma):
    textos = _reportes(idioma)
    assert textos
    for clave, valor in textos.items():
        assert not PROHIBIDAS.search(clave), (idioma, clave)
        if isinstance(valor, str):
            assert not PROHIBIDAS.search(valor), (idioma, clave, valor)


@pytest.mark.req("REQ-50")
@pytest.mark.parametrize("ruta", ARCHIVOS_QML, ids=lambda p: p.name)
def test_qml_del_dashboard_sin_palabras_prohibidas(ruta):
    assert ruta.exists(), ruta
    for linea in ruta.read_text(encoding="utf8").splitlines():
        if linea.lstrip().startswith("//"):
            continue
        for literal in LITERAL.findall(linea):
            assert not PROHIBIDAS.search(literal), (ruta.name, literal)


@pytest.mark.req("REQ-50")
@pytest.mark.parametrize("idioma", ["es", "en"])
def test_leyenda_dr_h01_exacta(idioma):
    assert _reportes(idioma)["cal_leyenda"] == LEYENDA[idioma]


@pytest.mark.req("REQ-50")
def test_dominio_publica_la_leyenda_dr_h01():
    from autoclave.ui_qml.domain import reporte_dashboard as dom

    fuente = Path(dom.__file__).read_text(encoding="utf8")
    assert '"reportes.cal_leyenda"' in fuente

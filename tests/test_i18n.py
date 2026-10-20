# tests/test_i18n.py
#
# Catálogo de idiomas (F1 de planeacion_i18n.md):
#   - paridad es/en: mismas claves, estructura, placeholders y sin textos vacíos;
#   - toda clave citada de forma literal en QML o Python existe;
#   - familias de claves dinámicas ("prefijo." + algo): cada sufijo posible,
#     enumerado desde el código, existe; y no aparece ninguna familia nueva
#     sin enumerar;
#   - respaldo (R-05): falta en en -> español + aviso; falta en ambos -> la
#     clave + aviso; nunca "";
#   - binding QML: I18n.t(clave, I18n.lang) se re-evalúa al cambiar el idioma.

import ast
import json
import logging
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from autoclave import i18n

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "autoclave"
QML = SRC / "ui_qml" / "qml"
CATALOGOS = {idioma: json.loads((SRC / "i18n" / f"{idioma}.json").read_text(encoding="utf-8"))
             for idioma in i18n.IDIOMAS}
ES = CATALOGOS["es"]
SECCIONES = set(ES)

# Python dentro del alcance de D-02 que arma o entrega claves de texto
PY_ALCANCE = sorted(
    [p for p in (SRC / "ui_qml").rglob("*.py")]
    + [SRC / "ui_pyside" / "views" / "nuevo_usuario" / "puente.py",
       SRC / "ui_pyside" / "views" / "nuevo_usuario" / "vista.py",
       SRC / "ui_pyside" / "services" / "roles.py",
       SRC / "ui_pyside" / "services" / "validacion_usuario.py"])
QML_ARCHIVOS = sorted(QML.rglob("*.qml"))


def _hojas(nodo, ruta=""):
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            yield from _hojas(v, f"{ruta}.{k}" if ruta else k)
    elif isinstance(nodo, list):
        for i, v in enumerate(nodo):
            yield from _hojas(v, f"{ruta}[{i}]")
    else:
        yield ruta, nodo


def _forma(nodo):
    """Estructura comparable: objetos por clave, listas por longitud, textos
    por su conjunto de placeholders."""
    if isinstance(nodo, dict):
        return {k: _forma(v) for k, v in nodo.items()}
    if isinstance(nodo, list):
        return [_forma(v) for v in nodo]
    if isinstance(nodo, str):
        return ("texto", tuple(sorted(re.findall(r"\{(\w+)\}", nodo))))
    return (type(nodo).__name__,)


def _es_texto(clave: str, cat: dict) -> bool:
    nodo = cat
    for parte in clave.split("."):
        if not isinstance(nodo, dict) or parte not in nodo:
            return False
        nodo = nodo[parte]
    return isinstance(nodo, str)


# ── Paridad ──────────────────────────────────────────────────────────────

def test_paridad_estructura_y_placeholders():
    assert _forma(CATALOGOS["en"]) == _forma(ES)


@pytest.mark.parametrize("idioma", i18n.IDIOMAS)
def test_ningun_texto_vacio(idioma):
    vacios = [r for r, v in _hojas(CATALOGOS[idioma]) if not isinstance(v, str) or not v.strip()]
    assert vacios == []


# ── Claves citadas de forma literal ──────────────────────────────────────

_LITERAL_QML = re.compile(r'"((?:%s)\.[A-Za-z0-9_.]*)"' % "|".join(sorted(SECCIONES)))


def _literales_qml():
    for ruta in QML_ARCHIVOS:
        for m in _LITERAL_QML.finditer(ruta.read_text(encoding="utf-8")):
            yield ruta.relative_to(QML).as_posix(), m.group(1)


def _literales_py():
    for ruta in PY_ALCANCE:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                if re.fullmatch(r"(?:%s)\.[A-Za-z0-9_.]*" % "|".join(SECCIONES), nodo.value):
                    yield ruta.relative_to(SRC).as_posix(), nodo.value


def _es_prefijo(clave: str) -> bool:
    """Prefijo de una familia dinámica, o nombre de archivo ("usuarios.svg")."""
    return clave.endswith((".", "_")) or re.search(r"\.(svg|png|jpg|qml|json|otf)$", clave) is not None


def test_claves_literales_qml_existen_en_ambos_idiomas():
    faltan = [(f, c, idioma) for f, c in _literales_qml() if not _es_prefijo(c)
              for idioma, cat in CATALOGOS.items()
              if not _es_texto(c, cat) and c not in ("fecha.meses",)]
    assert faltan == []


def test_claves_literales_python_existen_en_ambos_idiomas():
    faltan = [(f, c, idioma) for f, c in _literales_py() if not _es_prefijo(c)
              for idioma, cat in CATALOGOS.items() if not _es_texto(c, cat)]
    assert faltan == []


def test_hay_claves_literales_en_qml_y_python():
    # que la búsqueda no quede vacía en silencio
    assert len({c for _, c in _literales_qml()}) > 150
    assert len({c for _, c in _literales_py()}) > 40


# ── Familias de claves dinámicas ─────────────────────────────────────────

def _qml(rel):
    return (QML / rel).read_text(encoding="utf-8")


def _lista_qml(rel, propiedad):
    m = re.search(r"property var %s: \[([^\]]*)\]" % propiedad, _qml(rel))
    assert m, (rel, propiedad)
    return re.findall(r'"(\w+)"', m.group(1))


def _segundos_qml(rel, patron):
    """Segundo elemento de cada par de un model: [["a", "clave"], ...]."""
    m = re.search(patron, _qml(rel))
    assert m, (rel, patron)
    return re.findall(r'\[\s*"\w+",\s*"(\w+)"\s*\]', m.group(0))


def _sufijos_menu():
    columnas = re.search(r'model: \[("col_\w+"(?:, "col_\w+")*)\]', _qml("Componentes/ListaCiclos.qml"))
    filtros = _segundos_qml("Componentes/SelectorPeriodo.qml", r"model: \[\[.*\]\]")
    return re.findall(r'"(\w+)"', columnas.group(1)) + filtros


def _sufijos_reportes():
    from autoclave.ui_qml.domain.reporte_resumen import CLAVES
    pestanas = _segundos_qml("Pantallas/MenuPrincipal.qml", r'model: \[\["resumen".*\]\]')
    return list(CLAVES) + pestanas


def _sufijos_instalacion_pasos():
    m = re.search(r"readonly property var pasos: \{(.*?)\n    \}", _qml("Pantallas/Instalacion.qml"), re.S)
    return re.findall(r'"(\w+)"', m.group(1))


def _sufijos_instalacion():
    filas = re.search(r"readonly property var filasResumen: \[(.*?)\]\.filter", _qml("Pantallas/Instalacion.qml"), re.S)
    return ([f"sum_{k}" for k in _lista_qml("Pantallas/Instalacion.qml", "clavesSuministro")]
            + [f"sonda_{k}" for k in _lista_qml("Pantallas/Instalacion.qml", "clavesSonda")]
            + re.findall(r'clave: "(\w+)"', filas.group(1)))


def _sufijos_equipo():
    from autoclave.ui_qml.bridge import info_equipo
    filas = re.findall(r'_fila\("(\w+)"', (SRC / "ui_qml" / "bridge" / "info_equipo.py").read_text(encoding="utf-8"))
    return filas + list(info_equipo._TEXTO_EMPAREJAMIENTO.values()) + ["no_disponible"]


def _sufijos_estados():
    from autoclave.core.runtime.progreso_ciclo import _FASE_BACKEND_A_UI, resultado
    from autoclave.ui_qml.bridge.ui_bridge import estado_equipo
    maquina = {estado_equipo(m, listo) for m in ("CICLO", "FALLA", "PREPARADO", "PREPARACION", "")
               for listo in (True, False)}
    fases = list(_FASE_BACKEND_A_UI) + ["COMPLETADO", "CANCELADO", "FALLO_X", "EMERGENCIA"]
    return sorted(maquina | {r for r in map(resultado, fases) if r})


def _sufijos_resultado_menu():
    from autoclave.ui_qml.domain.resumen_sistema import _CLAVE_POR_RESULTADO
    return [v.lower() for v in _CLAVE_POR_RESULTADO.values()]


def _sufijos_campos(rel, campo):
    m = re.search(r"readonly property var campos: \[(.*?)\n    \]", _qml(rel), re.S)
    return re.findall(r'%s: "(\w+)"' % campo, m.group(1))


def _sufijos_arranque():
    from autoclave.ui_qml.bridge.progreso_arranque import ETAPAS_EJEMPLO
    return [clave for clave, _ in ETAPAS_EJEMPLO]


def _sufijos_teclado():
    return re.findall(r'claveMensajeRango: "(\w+)"', _qml("Tema/TecladoProvisional.qml"))


def _sufijos_secciones():
    from autoclave.ui_qml.domain.permisos_opciones import SECCIONES as SECC
    return [s.clave for s in SECC]


def _sufijos_impresora():
    from autoclave.devices.printer import win32_printer
    estados = set(re.findall(r'return "(\w+)"', Path(win32_printer.__file__).read_text(encoding="utf-8")))
    return sorted((estados - {"lista"}) | {"error"})


def _sufijos_validacion():
    from autoclave.ui_pyside.services import validacion_usuario as v
    return [getattr(v, n) for n in dir(v) if n.startswith("COD_") and getattr(v, n) != v.COD_EXISTE]


def _parametros_de_perfiles():
    import glob, json as _j
    salida = set()
    def rec(n, ruta):
        if isinstance(n, dict) and "value" in n and not isinstance(n["value"], dict):
            salida.add(".".join(ruta)); return
        if isinstance(n, dict):
            for k, v in n.items():
                rec(v, ruta + [k])
    for f in glob.glob(str(RAIZ / "src" / "autoclave" / "cycles" / "*" / "*.json")):
        for sec, v in _j.load(open(f, encoding="utf-8"))["parameters"].items():
            rec(v, [sec])
    return sorted(salida)


FAMILIAS = {
    "menu.": _sufijos_menu,
    "reportes.": _sufijos_reportes,
    "instalacion.": _sufijos_instalacion,
    "instalacion.clase_": lambda: [c.value for c in __import__(
        "autoclave.installation.equipment", fromlist=["EquipmentClass"]).EquipmentClass],
    "instalacion.puerta_": lambda: _lista_qml("Pantallas/Instalacion.qml", "clavesTipoPuerta"),
    "instalacion.puerta_pc_": lambda: ["1", "2"],
    "instalacion.vapor_": lambda: _lista_qml("Pantallas/Instalacion.qml", "clavesVapor"),
    "instalacion.paso_": _sufijos_instalacion_pasos,
    "instalacion.sum_": lambda: _lista_qml("Pantallas/Instalacion.qml", "clavesSuministro"),
    "instalacion.sonda_": lambda: _lista_qml("Pantallas/Instalacion.qml", "clavesSonda"),
    "equipo.": _sufijos_equipo,
    "fases.": lambda: list(__import__("autoclave.core.runtime.progreso_ciclo",
                                      fromlist=["FASES_UI"]).FASES_UI),
    "arranque.": _sufijos_arranque,
    "estados.": _sufijos_estados,
    "teclado.": _sufijos_teclado,
    "formulario.": lambda: _sufijos_campos("Pantallas/Login.qml", "clave"),
    "sesion.": lambda: _sufijos_campos("Pantallas/CambioClave.qml", "etiqueta"),
    "menu.resultado_": _sufijos_resultado_menu,
    "opciones.secciones.": _sufijos_secciones,
    # M1 (tanda 3): tipos de mantenimiento
    "opciones.mant_tipo_": lambda: list(__import__(
        "autoclave.core.runtime.servicio_mantenimiento", fromlist=["TIPOS"]).TIPOS),
    # T12: secciones de un programa (GET /programas) y valores de enumerados
    "opciones.secciones_programa.": lambda: list(__import__(
        "autoclave.backend.server", fromlist=["_SECCIONES_PROGRAMA"])._SECCIONES_PROGRAMA),
    "opciones.valor_": lambda: list(__import__(
        "autoclave.core.managers.catalogo_parametros", fromlist=["TIPOS_CARGA"]).TIPOS_CARGA),
    # Descripción de cada parámetro de los perfiles de ciclo (tarjeta de ajuste)
    "parametros_desc.": lambda: _parametros_de_perfiles(),
    # Descompresión: nombre y qué hace cada modo (0 a 5) en Parámetros del ciclo
    "descompresion_modos.": lambda: [f"{n}.{c}" for n in range(6) for c in ("nombre", "desc")],
    "exportacion.impresora_": _sufijos_impresora,
    "validacion.": _sufijos_validacion,
}

def _prefijos_en_codigo():
    patron = re.compile(r'"((?:%s)\.[A-Za-z0-9_.]*)"\s*\+' % "|".join(SECCIONES))
    for ruta in QML_ARCHIVOS:
        for m in patron.finditer(ruta.read_text(encoding="utf-8")):
            yield m.group(1)
    for ruta in PY_ALCANCE:
        texto = ruta.read_text(encoding="utf-8")
        for m in patron.finditer(texto):
            yield m.group(1)
        for m in re.finditer(r'f"((?:%s)\.)\{' % "|".join(SECCIONES), texto):
            yield m.group(1)


def test_toda_familia_dinamica_esta_enumerada():
    sin_enumerar = sorted(set(_prefijos_en_codigo()) - set(FAMILIAS))
    assert sin_enumerar == []


@pytest.mark.parametrize("prefijo", sorted(FAMILIAS))
def test_familia_dinamica_tiene_todos_sus_textos(prefijo):
    sufijos = FAMILIAS[prefijo]()
    assert sufijos, prefijo
    faltan = [(prefijo + s, idioma) for s in sufijos for idioma, cat in CATALOGOS.items()
              if not _es_texto(prefijo + s, cat)]
    assert faltan == []


def test_descripciones_opcionales_de_puerta():
    # Instalacion.qml pide "puerta_<tipo>_desc" con existe(); hoy solo existe la de "simple"
    con_desc = [t for t in _lista_qml("Pantallas/Instalacion.qml", "clavesTipoPuerta")
                if _es_texto(f"instalacion.puerta_{t}_desc", ES)]
    assert con_desc == ["simple"]


# ── Respaldo (R-05) ──────────────────────────────────────────────────────

@pytest.fixture
def catalogos_de_prueba(monkeypatch):
    monkeypatch.setattr(i18n, "_catalogos", {
        "es": {"a": {"solo_es": "Hola {n}", "ambos": "Sí"}},
        "en": {"a": {"ambos": "Yes"}},
    })
    monkeypatch.setattr(i18n, "_avisadas", set())
    yield


def test_falta_en_ingles_devuelve_espanol_y_avisa_una_vez(catalogos_de_prueba, caplog):
    with caplog.at_level(logging.WARNING, logger="autoclave.i18n"):
        assert i18n.t("a.solo_es", "en", n=2) == "Hola 2"
        assert i18n.t("a.solo_es", "en", n=3) == "Hola 3"
    avisos = [r for r in caplog.records if "a.solo_es" in r.getMessage()]
    assert len(avisos) == 1


def test_falta_en_ambos_devuelve_la_clave_y_avisa_una_vez(catalogos_de_prueba, caplog):
    with caplog.at_level(logging.WARNING, logger="autoclave.i18n"):
        assert i18n.t("a.no_existe", "en") == "a.no_existe"
        assert i18n.t("a.no_existe", "en") == "a.no_existe"
        assert i18n.t("a.no_existe", "es") == "a.no_existe"
    avisos = [r.getMessage() for r in caplog.records if "a.no_existe" in r.getMessage()]
    assert len(avisos) == 2          # una por idioma pedido


def test_nunca_devuelve_vacio(catalogos_de_prueba):
    for clave in ("", "a", "a.", "a.ambos.x", "zz.zz"):
        for idioma in i18n.IDIOMAS:
            assert i18n.t(clave, idioma) != "" or clave == ""
    assert i18n.t("", "es") == ""    # sin clave no hay nada que mostrar


def test_existe_y_valor(catalogos_de_prueba):
    assert i18n.existe("a.solo_es", "en")
    assert not i18n.existe("a.no_existe", "es")
    assert i18n.valor("a.no_existe", "es") is None
    assert i18n.valor("a", "en") == {"ambos": "Yes"}


def test_idioma_vigente_y_oyentes(monkeypatch):
    monkeypatch.setattr(i18n, "_idioma", "es")
    monkeypatch.setattr(i18n, "_oyentes", [])
    vistos = []
    i18n.al_cambiar_idioma(vistos.append)
    i18n.fijar_idioma("en")
    i18n.fijar_idioma("en")          # sin cambio: no avisa
    assert i18n.idioma() == "en"
    assert i18n.t("menu.titulo") == CATALOGOS["en"]["menu"]["titulo"]
    assert vistos == ["en"]
    with pytest.raises(ValueError):
        i18n.fijar_idioma("fr")


def test_catalogo_es_una_copia():
    c = i18n.catalogo("es")
    c["menu"]["titulo"] = "otro"
    assert i18n.t("menu.titulo", "es") == ES["menu"]["titulo"]


def test_cargar_falla_si_falta_un_catalogo(monkeypatch, tmp_path):
    monkeypatch.setattr(i18n, "ruta_catalogo", lambda idioma: str(tmp_path / f"{idioma}.json"))
    with pytest.raises(FileNotFoundError):
        i18n.cargar()


def test_parametros_como_javascript():
    from autoclave.ui_qml.bridge.i18n_qml import como_texto_js
    assert [como_texto_js(v) for v in (5.0, 2.5, 3, True, None, "x")] == \
        ["5", "2.5", "3", "true", "null", "x"]


# ── Binding QML ──────────────────────────────────────────────────────────

_SCRIPT_BINDING = textwrap.dedent(r"""
    import json
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave import i18n
    from autoclave.ui_qml.bridge import i18n_qml  # noqa: F401

    app = QGuiApplication([])
    motor = QQmlEngine()
    avisos = []
    motor.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(motor)
    comp.setData(b'''
    import QtQuick
    import Autoclave.I18n
    Item {
        property string titulo: I18n.t("menu.titulo", I18n.lang)
        property string conParametro: I18n.t("exportacion.impreso", I18n.lang, { n: 4 })
        property var meses: I18n.valor("fecha.meses", I18n.lang)
        property string idioma: I18n.lang
    }''', QUrl())
    o = comp.create()
    if o is None:
        print(json.dumps({"errores": [e.toString() for e in comp.errors()]})); raise SystemExit
    leer = lambda: [o.property("titulo"), o.property("conParametro"),
                    list(o.property("meses"))[0], o.property("idioma")]
    salida = [leer()]
    i18n.fijar_idioma("en"); app.processEvents(); salida.append(leer())
    i18n.fijar_idioma("es"); app.processEvents(); salida.append(leer())
    print(json.dumps({"lecturas": salida, "avisos": avisos}, ensure_ascii=False))
""")


def test_binding_qml_se_reevalua_al_cambiar_idioma():
    pytest.importorskip("PySide6")
    entorno = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8",
                   PYTHONPATH=str(RAIZ / "src"))
    r = subprocess.run([sys.executable, "-c", _SCRIPT_BINDING], capture_output=True, text=True,
                       encoding="utf-8", cwd=RAIZ, env=entorno, timeout=120)
    assert r.returncode == 0, r.stderr
    datos = json.loads(r.stdout.strip().splitlines()[-1])
    assert "errores" not in datos, datos
    es, en = CATALOGOS["es"], CATALOGOS["en"]
    esperado_es = [es["menu"]["titulo"], es["exportacion"]["impreso"].replace("{n}", "4"),
                   es["fecha"]["meses"][0], "es"]
    esperado_en = [en["menu"]["titulo"], en["exportacion"]["impreso"].replace("{n}", "4"),
                   en["fecha"]["meses"][0], "en"]
    assert datos["lecturas"] == [esperado_es, esperado_en, esperado_es]
    assert datos["avisos"] == []

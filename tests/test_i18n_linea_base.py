# tests/test_i18n_linea_base.py
#
# Línea base del comportamiento de textos en español (F1 de planeacion_i18n.md).
#
# REFERENCIA_QML y _tx_referencia son copias literales de las funciones que
# existían antes de F1 (tx/txRuta de Login.qml, CambioClave.qml y NuevoUsuario.qml;
# tx(clave) de ResumenPeriodo.qml; _tx de IntroArranque.qml; nombre() de
# BarraFases.qml; nombreSeccion() de Opciones.qml; ti() de Instalacion.qml; y
# AccionesCiclos._tx en Python). Se conservan aquí congeladas para comprobar
# que el catálogo nuevo (autoclave.i18n y el singleton QML I18n) da EXACTAMENTE
# el mismo texto en español para toda clave existente.
#
# Diferencia aceptada (R-05): con una clave inexistente las funciones viejas
# devolvían "" (QML) o la clave corta (Python); el catálogo nuevo devuelve la
# clave completa y avisa en el log.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

RAIZ = Path(__file__).resolve().parents[1]
ES_JSON = RAIZ / "src" / "autoclave" / "i18n" / "es.json"


def _es() -> dict:
    return json.loads(ES_JSON.read_text(encoding="utf-8"))


def _tx_referencia(textos, seccion, clave, **valores):
    # Copia literal de AccionesCiclos._tx antes de F1
    texto = (textos.get(seccion) or {}).get(clave, clave)
    return texto.format(**valores) if valores else texto


def _hojas(d, prefijo=""):
    """(clave, texto) de cada texto del catálogo, recorriendo objetos."""
    for k, v in d.items():
        ruta = f"{prefijo}{k}"
        if isinstance(v, dict):
            yield from _hojas(v, ruta + ".")
        elif isinstance(v, str):
            yield ruta, v


def _muestras(texto: str) -> list:
    """Juegos de parámetros para los placeholders de un texto: entero, real y texto."""
    import re
    nombres = re.findall(r"\{(\w+)\}", texto)
    if not nombres:
        return [{}]
    return [{n: 3 for n in nombres}, {n: 2.5 for n in nombres}, {n: "x" for n in nombres}]


# ── Python ────────────────────────────────────────────────────────────────

def test_python_resuelve_clave_y_placeholders():
    es = _es()
    assert _tx_referencia(es, "menu", "titulo") == es["menu"]["titulo"]
    assert _tx_referencia(es, "exportacion", "impreso", n=3) == es["exportacion"]["impreso"].replace("{n}", "3")
    assert _tx_referencia(es, "exportacion", "no_existe") == "no_existe"


def test_python_i18n_igual_a_referencia_en_espanol():
    from autoclave import i18n
    es = _es()
    for seccion, contenido in es.items():
        if not isinstance(contenido, dict):
            continue
        for clave, texto in contenido.items():
            if not isinstance(texto, str):
                continue
            for p in _muestras(texto):
                esperado = _tx_referencia(es, seccion, clave, **p)
                assert i18n.t(f"{seccion}.{clave}", "es", **p) == esperado, (seccion, clave, p)


def test_python_i18n_listas_y_objetos():
    from autoclave import i18n
    es = _es()
    assert i18n.valor("fecha.meses", "es") == es["fecha"]["meses"]
    assert i18n.valor("sensores", "es") == es["sensores"]
    assert i18n.valor("fases", "es") == es["fases"]
    assert i18n.t("opciones.secciones.usuarios", "es") == es["opciones"]["secciones"]["usuarios"]


# ── QML ───────────────────────────────────────────────────────────────────

REFERENCIA_QML = r"""
import QtQuick
import Autoclave.I18n

Item {
    property var textosJson: ({})

    // tx/txRuta de Login.qml, CambioClave.qml y NuevoUsuario.qml (las demás
    // copias de tx(seccion, clave) eran idénticas)
    function tx(seccion, clave) {
        const s = textosJson ? textosJson[seccion] : undefined
        return (s && s[clave] !== undefined) ? s[clave] : ""
    }
    function txRuta(ruta, valores) {
        const i = ruta.indexOf(".")
        let texto = i > 0 ? tx(ruta.slice(0, i), ruta.slice(i + 1)) : ""
        for (const k in (valores || {}))
            texto = texto.replace("{" + k + "}", valores[k])
        return texto
    }
    // ResumenPeriodo.qml
    function txReportes(clave) {
        const s = textosJson ? textosJson["reportes"] : undefined
        return (s && s[clave] !== undefined) ? s[clave] : ""
    }
    // IntroArranque.qml
    function txArranque(clave) {
        const sec = textosJson ? textosJson["arranque"] : undefined
        return sec && typeof sec[clave] === "string" ? sec[clave] : ""
    }
    // BarraFases.qml / GraficaCiclo.qml
    function nombreFase(clave) {
        const f = textosJson ? textosJson.fases : undefined
        return (f && f[clave] !== undefined) ? f[clave] : ""
    }
    // Opciones.qml
    function nombreSeccion(clave) {
        const s = textosJson?.opciones?.secciones
        return ((s && s[clave] !== undefined) ? s[clave] : clave).replace(/\n/g, " ")
    }

    // Catálogo nuevo
    function nuevo(clave, valores) { return I18n.t(clave, "es", valores) }
    function nuevoValor(clave) { return I18n.valor(clave, "es") }
}
"""

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    import autoclave.ui_qml.bridge.i18n_qml  # noqa: F401  registra Autoclave.I18n

    qml, es_json, casos_json = sys.argv[1], sys.argv[2], sys.argv[3]
    app = QGuiApplication([])
    motor = QQmlEngine()
    avisos = []
    motor.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    comp = QQmlComponent(motor)
    comp.setData(open(qml, encoding="utf-8").read().encode("utf-8"), QUrl())
    raiz = comp.createWithInitialProperties({"textosJson": json.load(open(es_json, encoding="utf-8"))})
    if raiz is None:
        print(json.dumps({"errores": [e.toString() for e in comp.errors()]}))
        sys.exit(0)

    from PySide6.QtCore import QMetaObject, Q_RETURN_ARG, Q_ARG

    def llamar(funcion, *args):
        tipos = [Q_ARG("QVariant", a) for a in args]
        return QMetaObject.invokeMethod(raiz, funcion, Q_RETURN_ARG("QVariant"), *tipos)

    salida = []
    for c in json.load(open(casos_json, encoding="utf-8")):
        salida.append([c, llamar(c["f"], *c["a"])])
    print(json.dumps({"resultados": salida, "avisos": avisos}, ensure_ascii=False))
""")


def _correr_qml(tmp_path, casos):
    qml = tmp_path / "referencia.qml"
    qml.write_text(REFERENCIA_QML, encoding="utf-8")
    script = tmp_path / "script.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    archivo_casos = tmp_path / "casos.json"
    archivo_casos.write_text(json.dumps(casos, ensure_ascii=False), encoding="utf-8")
    entorno = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8",
                   PYTHONPATH=str(RAIZ / "src"))
    r = subprocess.run([sys.executable, str(script), str(qml), str(ES_JSON), str(archivo_casos)],
                       capture_output=True, text=True, encoding="utf-8", cwd=RAIZ, env=entorno,
                       timeout=120)
    assert r.returncode == 0, r.stderr
    datos = json.loads(r.stdout.strip().splitlines()[-1])
    assert "errores" not in datos, datos
    return datos


def test_qml_referencia_fija_el_comportamiento_actual(tmp_path):
    es = _es()
    casos = [
        {"f": "tx", "a": ["menu", "titulo"]},
        {"f": "tx", "a": ["menu", "no_existe"]},
        {"f": "txRuta", "a": ["exportacion.impreso", {"n": 3}]},
        {"f": "txRuta", "a": ["exportacion.impreso", {"n": 2.5}]},
        {"f": "txRuta", "a": ["sin_punto", None]},
        {"f": "tx", "a": ["fecha", "meses"]},
        {"f": "txReportes", "a": ["total"]},
        {"f": "nombreFase", "a": ["NO_EXISTE"]},
        {"f": "nombreSeccion", "a": ["no_existe"]},
    ]
    r = [v for _, v in _correr_qml(tmp_path, casos)["resultados"]]
    assert r[0] == es["menu"]["titulo"]
    assert r[1] == ""
    assert r[2] == es["exportacion"]["impreso"].replace("{n}", "3")
    assert r[3] == es["exportacion"]["impreso"].replace("{n}", "2.5")
    assert r[4] == ""
    assert r[5] == es["fecha"]["meses"]
    assert r[6] == es["reportes"]["total"]
    assert r[7] == ""
    assert r[8] == "no_existe"


def test_qml_i18n_igual_a_referencia_para_toda_clave(tmp_path):
    """Toda clave de es.json: I18n.t(clave, "es", params) == txRuta/tx de antes,
    con parámetros enteros, reales y de texto."""
    es = _es()
    casos = []
    for clave, texto in _hojas(es):
        for p in _muestras(texto):
            casos.append({"f": "txRuta", "a": [clave, p], "clave": clave})
            casos.append({"f": "nuevo", "a": [clave, p], "clave": clave})
    for seccion in ("fecha.meses", "fases", "sensores", "arranque", "opciones.secciones"):
        casos.append({"f": "nuevoValor", "a": [seccion]})
    datos = _correr_qml(tmp_path, casos)
    res = datos["resultados"]
    pares = [(res[i], res[i + 1]) for i in range(0, len(res) - 5, 2)]
    for (caso_ref, ref), (_, nuevo) in pares:
        clave = caso_ref["clave"]
        if clave.startswith("alarmas.") and clave.endswith(".plantilla"):
            # I1 (tanda 5): plantilla en formato de Python ({pres:.0f}) que
            # renderiza el backend (core/runtime/alarmas_i18n.py), no I18n.t
            continue
        if clave.startswith("opciones.secciones_programa."):
            # T12: tercer nivel nuevo, sin referencia vieja; contra el catálogo
            ref = es["opciones"]["secciones_programa"][clave.split(".")[2]]
        elif clave.startswith("opciones.secciones."):
            # txRuta parte en el primer punto: no resolvía el tercer nivel;
            # Opciones lo leía directo del objeto.
            ref = es["opciones"]["secciones"][clave.split(".")[2]]
        elif clave.startswith(("bitacora.ev.", "bitacora.tipo.")):
            # O2e (tanda 6): tercer nivel nuevo, sin referencia vieja
            ref = es["bitacora"][clave.split(".")[1]][clave.split(".")[2]]
            if caso_ref["a"][1]:
                ref = ref.format(**{k: caso_ref["a"][1].get(k, "{%s}" % k)
                                    for k in ("entidad", "anterior", "nuevo", "evento")})
        elif clave.startswith("bitacora.categoria."):
            # BIT-05 (tanda 17): tercer nivel nuevo, sin referencia vieja
            ref = es["bitacora"]["categoria"][clave.split(".")[2]]
        elif clave.startswith(("opciones.equipo_grupos.", "opciones.equipo_grupos_desc.")):
            # O2a (tanda 6): tercer nivel nuevo, sin referencia vieja
            ref = es["opciones"][clave.split(".")[1]][clave.split(".")[2]]
        elif clave.startswith("io.") and clave.count(".") == 2:
            # Entradas / Salidas (planeacion_opciones_entradas_salidas.md §9):
            # io.di|do|ai|ui.<clave>, tres niveles sin referencia vieja.
            _, grupo, campo = clave.split(".")
            ref = es["io"][grupo][campo]
            parametros = caso_ref["a"][1]
            if parametros:
                ref = ref.format(**parametros)
        elif clave.startswith(("motivos_fase.", "ticket_ciclo.", "abrev.")):
            # X9 (tanda 9, D9-13.4): catálogo nuevo, sin referencia vieja; 2 o 3
            # niveles, con placeholders "{nombre}"
            # U10b (tanda 10, D10-1.2): también la sección abrev.<ruta completa>
            # (3 o más niveles), que txRuta de referencia no resuelve
            ref = es
            for parte in clave.split("."):
                ref = ref[parte]
            for k, v in (caso_ref["a"][1] or {}).items():
                ref = ref.replace("{%s}" % k, str(v))
        elif clave.startswith(("parametros_desc.", "parametros.", "descompresion_modos.", "ciclos_fabrica.")):
            # V8b (tanda 8): también parametros.<sección>.<clave> (nombre visible)
            # Descripciones de parámetros y modos de descompresión (Opciones):
            # catálogo nuevo, sin referencia vieja; 3 o 4 niveles. I4 (tanda 6):
            # también ciclos_fabrica.<cycle_id>.nombre.
            ref = es
            for parte in clave.split("."):
                ref = ref[parte]
        elif clave.startswith("alarmas."):
            # Bloque nuevo (tanda 2026-10-14, P1 de E6): tres niveles, sin
            # referencia vieja. Se compara contra el catálogo.
            _, ident, campo = clave.split(".")
            ref = es["alarmas"][ident][campo]
        assert nuevo == ref, (caso_ref, ref, nuevo)
    valores = [v for _, v in res[-5:]]
    assert valores[0] == es["fecha"]["meses"]
    assert valores[1] == es["fases"]
    assert valores[2] == es["sensores"]
    assert valores[3] == es["arranque"]
    assert valores[4] == es["opciones"]["secciones"]
    assert datos["avisos"] == []

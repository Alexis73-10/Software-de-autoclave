# tests/test_teclado_alfanumerico_qml.py
#
# Carga real de la pantalla de prueba del teclado alfanumérico
# (qml/Pruebas/PruebaTecladoAlfanumerico.qml) a 1200x1920 (Escala.factor = 1):
# distribución del diseñador con PROV-03 y la capa ?123, medidas (TEC-D11 y provisionales),
# etiquetas que caben sin recortar, comportamiento por toques simulados y
# cero avisos del motor QML. En subproceso para tener un QGuiApplication
# propio (otras pruebas crean QCoreApplication).

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("PySide6")

_SCRIPT = textwrap.dedent(r"""
    import json
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui_qml.controllers.teclado_alfanumerico_controller import TecladoAlfanumericoController
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes, cargar_textos

    app = QGuiApplication([])
    _cargar_fuentes()
    engine = QQmlApplicationEngine()
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"textosJson": cargar_textos()})
    engine.load(QUrl.fromLocalFile(f"{QML_DIR}/Pruebas/PruebaTecladoAlfanumerico.qml"))
    w = engine.rootObjects()[0]
    w.setWidth(1200); w.setHeight(1920); w.show()
    QTest.qWait(200)

    def visuales(item):
        for h in item.childItems():
            yield h
            yield from visuales(h)

    def teclas():
        return [o for o in visuales(w.contentItem())
                if o.metaObject().className().startswith("Tecla_QML")]

    teclado = w.findChild(QObject, "tecladoAlfanumerico")
    ctrl = teclado.findChildren(TecladoAlfanumericoController)[0]
    resultado = w.findChild(QObject, "resultado")
    # letras por su carácter en minúscula; acciones por objectName
    letras = {o.property("texto").lower(): o for o in teclas() if o.objectName() == ""}
    acciones = {o.objectName(): o for o in teclas() if o.objectName()}

    def geo(o):
        r = o.mapRectToScene(o.boundingRect())
        return [round(r.x(), 1), round(r.y(), 1), round(r.width(), 1), round(r.height(), 1)]

    def tocar(o, esperar=20):
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, o.mapToScene(o.boundingRect().center()).toPoint())
        QTest.qWait(esperar)

    def etiqueta_recortada(o):
        return any(h.property("truncated") for h in o.childItems() if h.property("truncated") is not None)

    r = {"geo": {**{k: geo(o) for k, o in letras.items()}, **{k: geo(o) for k, o in acciones.items()}}}
    r["recortadas"] = [o.objectName() or o.property("texto") for o in teclas() if etiqueta_recortada(o)]
    r["etiquetas_al_abrir"] = "".join(letras[c].property("texto") for c in "qñ")
    r["aa_marcada_al_abrir"] = acciones["teclaAa"].property("verPresionada")

    for c in "hola":
        tocar(letras[c])
    r["hola"] = ctrl.property("texto")
    r["etiquetas_tras_letra"] = "".join(letras[c].property("texto") for c in "qñ")
    QTest.qWait(150)
    r["aa_marcada_tras_letra"] = acciones["teclaAa"].property("verPresionada")

    tocar(acciones["teclaEspacio"])
    tocar(acciones["teclaAa"]); tocar(letras["ñ"])
    r["con_enie"] = ctrl.property("texto")

    r["etiqueta_capa_en_letras"] = acciones["teclaCapa"].property("texto")
    tocar(acciones["teclaCapa"])
    r["capa_numeros"] = ctrl.property("capa")
    r["etiqueta_capa_en_numeros"] = acciones["teclaCapa"].property("texto")
    # posiciones de las letras -> contenido de la capa ?123
    r["etiquetas_numeros"] = {c: letras[c].property("texto") for c in "qpaz"}
    r["visibles_numeros"] = {c: letras[c].property("visible") for c in "zx"}
    r["geo_numeros"] = {c: geo(letras[c]) for c in "qz"}
    tocar(letras["q"]); tocar(letras["a"]); tocar(letras["z"])
    r["texto_en_numeros"] = ctrl.property("texto")
    tocar(acciones["teclaCapa"])
    r["capa_vuelta"] = ctrl.property("capa")
    r["visible_x_en_letras"] = letras["x"].property("visible")

    for _ in range(3):
        tocar(acciones["teclaBorrar"])
    r["tras_borrar_simbolos"] = ctrl.property("texto")
    tocar(acciones["teclaBorrar"])
    r["tras_borrar"] = ctrl.property("texto")
    tocar(acciones["teclaConfirmar"], esperar=50)
    r["entregado"] = resultado.property("text")

    # al reabrir vacío; 35 toques: no pasa de 30
    for _ in range(35):
        tocar(letras["a"], esperar=0)
    QTest.qWait(50)
    r["largo"] = len(ctrl.property("texto"))
    tocar(acciones["teclaCancelar"], esperar=50)
    r["tras_cancelar"] = resultado.property("text")
    tocar(acciones["teclaConfirmar"], esperar=50)
    r["entregado_vacio"] = resultado.property("text")
    r["avisos"] = avisos
    print(json.dumps(r, ensure_ascii=False))
""")


@pytest.fixture(scope="module")
def salida():
    r = subprocess.run([sys.executable, "-c", _SCRIPT], capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"},
                       timeout=90)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_sin_avisos_del_motor_qml(salida):
    assert salida["avisos"] == []


def test_distribucion_del_disenador(salida):
    g = salida["geo"]
    filas = ["qwertyuiop", "asdfghjklñ", "zxcvbnm"]
    for i, fila in enumerate(filas):
        assert len({g[c][1] for c in fila}) == 1, fila
        xs = [g[c][0] for c in fila]
        assert xs == sorted(xs), fila
        for a, b in zip(fila, fila[1:]):
            assert g[b][0] - (g[a][0] + 96) == 14, (a, b)   # separación horizontal
    assert g["a"][0] - g["q"][0] == 22                       # fila 2 desplazada
    assert g["a"][1] - (g["q"][1] + 120) == 14               # separación vertical
    # fila 3: Aa al inicio, BORRAR tras la M
    assert g["teclaAa"][1] == g["z"][1] and g["teclaAa"][0] == g["q"][0]
    assert g["teclaBorrar"][1] == g["z"][1] and g["teclaBorrar"][0] > g["m"][0]
    # fila 4 (PROV-03): ?123 | CANCELAR | espacio | CONFIRMAR
    orden = ["teclaCapa", "teclaCancelar", "teclaEspacio", "teclaConfirmar"]
    assert len({g[k][1] for k in orden}) == 1
    for a, b in zip(orden, orden[1:]):
        assert g[b][0] - (g[a][0] + g[a][2]) == 14, (a, b)
    assert g["teclaCapa"][0] == g["q"][0]
    fin_fila1 = g["p"][0] + g["p"][2]
    assert g["teclaConfirmar"][0] + g["teclaConfirmar"][2] == fin_fila1
    assert g["teclaBorrar"][0] + g["teclaBorrar"][2] == fin_fila1


def test_medidas(salida):
    g = salida["geo"]
    for c in "qwertyuiopasdfghjklñzxcvbnm":
        assert g[c][2:] == [96.0, 120.0], c
    assert g["teclaAa"][2:] == [96.0, 120.0]
    assert g["teclaBorrar"][2:] == [206.0, 120.0]
    assert g["teclaCapa"][2:] == [110.0, 120.0]
    assert g["teclaCancelar"][2:] == [190.0, 120.0]
    assert g["teclaEspacio"][2:] == [524.0, 120.0]
    assert g["teclaConfirmar"][2:] == [220.0, 120.0]


def test_cabe_en_el_lienzo_y_bajo_el_45_por_ciento(salida):
    g = salida["geo"]
    assert min(v[0] for v in g.values()) >= 0
    assert max(v[0] + v[2] for v in g.values()) <= 1200
    alto_rejilla = g["teclaConfirmar"][1] + g["teclaConfirmar"][3] - g["q"][1]
    assert alto_rejilla < 0.45 * 1920


def test_ninguna_etiqueta_recortada(salida):
    assert salida["recortadas"] == []


def test_aa_y_etiquetas(salida):
    assert salida["etiquetas_al_abrir"] == "QÑ"           # Aa armada al abrir vacío
    assert salida["aa_marcada_al_abrir"] is True          # PROV-02
    assert salida["hola"] == "Hola"                       # solo la primera en mayúscula
    assert salida["etiquetas_tras_letra"] == "qñ"
    assert salida["aa_marcada_tras_letra"] is False
    assert salida["con_enie"] == "Hola Ñ"


def test_capa_numeros_y_simbolos(salida):
    assert salida["etiqueta_capa_en_letras"] == "?123"
    assert salida["capa_numeros"] == "numeros"
    assert salida["etiqueta_capa_en_numeros"] == "ABC"
    assert salida["etiquetas_numeros"] == {"q": "1", "p": "0", "a": "@", "z": "¿"}
    assert salida["visibles_numeros"] == {"z": True, "x": True}    # fila 3 completa
    g = salida["geo"]
    assert salida["geo_numeros"]["q"] == g["q"]                    # misma retícula
    assert salida["geo_numeros"]["z"] == g["z"]
    assert salida["texto_en_numeros"] == "Hola Ñ1@¿"               # conserva el texto
    assert salida["capa_vuelta"] == "letras"
    assert salida["visible_x_en_letras"] is True


def test_borrar_confirmar_longitud_y_cancelar(salida):
    assert salida["tras_borrar_simbolos"] == "Hola Ñ"
    assert salida["tras_borrar"] == "Hola "
    assert salida["entregado"] == "«Hola »"
    assert salida["largo"] == 30
    assert salida["tras_cancelar"].startswith("Cancelado")
    assert salida["entregado_vacio"] == "«»"

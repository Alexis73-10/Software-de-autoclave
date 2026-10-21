# tests/test_b1_barra_preciclo_ciclo_qml.py
#
# B1 (tanda 6, decisión 1.7): Preciclo y Ciclo en curso usan la misma
# BarraInferiorMenu flotante de Opciones, FUERA de la tarjeta (panel principal)
# y por debajo de ella, conservando sus funciones de hoy en las tres celdas:
#   Preciclo: equipo (izquierda), versión (centro), iniciar sesión (derecha).
#   Ciclo en curso: equipo (izquierda), iniciar sesión (centro), CANCELAR (derecha).
# Ningún contenido de la pantalla queda tapado por la barra.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

_RAIZ = Path(__file__).resolve().parents[1]

# (pantalla, barra, tarjeta, [(botón, señal de la pantalla o "dialogo:<objectName>")])
CASOS = [
    ("PantallaPreciclo", "barraInferiorPreciclo", "tarjetaPreciclo",
     [("botonEquipoPreciclo", "equipoPulsado"), ("avatarPreciclo", "avatarPulsado")]),
    ("PantallaCicloEnCurso", "barraInferiorCicloEnCurso", "tarjetaCicloEnCurso",
     [("botonEquipoCiclo", "equipoPulsado"), ("avatarCiclo", "avatarPulsado"),
      ("botonCancelarCiclo", "dialogo:dialogoCancelarCiclo")]),
]

_SCRIPT = textwrap.dedent(r"""
    import json, sys
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes

    PANTALLA, BARRA, TARJETA = sys.argv[1], sys.argv[2], sys.argv[3]
    BOTONES = json.loads(sys.argv[4])
    QML = '''
    import QtQuick
    import Tema
    import "Pantallas"
    import "Componentes"
    Window {
        width: 1200; height: 1920; visible: true
        Binding { target: Escala; property: "factor"; value: 1 }
        %s { objectName: "pantalla"; anchors.fill: parent; datosVigentes: true }
    }
    ''' % PANTALLA
    ruta = f"{QML_DIR}/_prueba_b1_barra.qml"
    open(ruta, "w", encoding="utf-8").write(QML)
    try:
        qapp = QGuiApplication([])
        _cargar_fuentes()
        engine = QQmlApplicationEngine()
        avisos = []
        engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
        engine.addImportPath(QML_DIR)
        engine.load(QUrl.fromLocalFile(ruta))
    finally:
        import os; os.remove(ruta)
    w = engine.rootObjects()[0]
    w.show()
    QTest.qWait(300)
    pantalla = w.findChild(QObject, "pantalla")

    def caja(o):
        p = o.mapToScene(o.boundingRect().topLeft())
        return [p.x(), p.y(), o.width(), o.height()]

    def es_descendiente(o, ancestro):
        while o is not None:
            if o == ancestro:
                return True
            o = o.parentItem()
        return False

    barra = w.findChild(QObject, BARRA)
    tarjeta = w.findChild(QObject, TARJETA)
    r = {"avisos": avisos, "hay_barra": barra is not None, "hay_tarjeta": tarjeta is not None}
    if barra is not None and tarjeta is not None:
        r["barra"] = caja(barra)
        r["tarjeta"] = caja(tarjeta)
        r["barra_en_tarjeta"] = es_descendiente(barra, tarjeta)
        r["padre_barra_es_pantalla"] = barra.parentItem() == pantalla
        # contenido visible fuera de la barra que la cruce por arriba (tapado):
        # se ignoran capas de pantalla completa, áreas táctiles y el margen de
        # desenfoque de las sombras (QQuickShaderEffect de MultiEffect)
        by = r["barra"][1]
        tapados = []
        def recorrer(it):
            for h in it.childItems():
                if h == barra or not h.isVisible():
                    continue
                x, y, ww, hh = caja(h)
                if hh < 1500 and ww > 0 and hh > 0 and y < by - 1 and y + hh > by + 1 \
                        and h.metaObject().className() not in ("QQuickMouseArea", "QQuickShaderEffect") and not h.metaObject().className().startswith("QGfx"):
                    tapados.append([h.objectName(), h.metaObject().className(), x, y, ww, hh])
                recorrer(h)
        recorrer(pantalla)
        r["tapados"] = tapados
        # borde inferior del contenido visible ajeno a la barra (sin sombras ni capas)
        def bajar(it):
            for h in it.childItems():
                if h == barra or h == tarjeta or not h.isVisible():
                    continue
                x, y, ww, hh = caja(h)
                if hh < 1500 and ww > 0 and hh > 0 and y < by and                         h.metaObject().className() not in ("QQuickMouseArea", "QQuickShaderEffect") and not h.metaObject().className().startswith("QGfx"):
                    yield (y + hh, h.objectName(), h.metaObject().className(), y)
                yield from bajar(h)
        r["contenido_mas_bajo"] = max(bajar(pantalla), default=(0,))
        senales, fuera = [], []
        for nombre, senal in BOTONES:
            b = barra.findChild(QObject, nombre)
            if b is None:
                senales.append(None); continue
            if not es_descendiente(b, barra):
                fuera.append(nombre)
            punto = b.mapToScene(b.boundingRect().center()).toPoint()
            if senal.startswith("dialogo:"):
                QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, punto)
                QTest.qWait(50)
                d = w.findChild(QObject, senal.split(":", 1)[1])
                senales.append(senal if d is not None and d.isVisible() else None)
                continue
            got = []
            getattr(pantalla, senal).connect(lambda s=senal: got.append(s))
            QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, punto)
            QTest.qWait(50)
            senales.append(got[0] if got else None)
            # cierra los paneles que pudo abrir el toque
            for o in w.findChildren(QObject):
                if o.metaObject().className().startswith(("PanelEquipo", "PanelModal")):
                    o.setProperty("visible", False)
            QTest.qWait(50)
        r["senales"] = senales
        r["fuera"] = fuera
    print("RESULTADO=" + json.dumps(r))
""")


def _correr(pantalla, barra, tarjeta, botones):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(_RAIZ / "src") + os.pathsep + str(_RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, pantalla, barra, tarjeta,
                        json.dumps(botones)], capture_output=True, text=True, env=env, cwd=_RAIZ,
                       timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout + p.stderr
    return json.loads(linea[len("RESULTADO="):])


@pytest.fixture(scope="module", params=CASOS, ids=[c[0] for c in CASOS])
def resultado(request):
    return request.param, _correr(*request.param)


def test_carga_sin_avisos_y_con_barra(resultado):
    _, r = resultado
    assert r["avisos"] == []
    assert r["hay_barra"] and r["hay_tarjeta"]


def test_la_barra_no_es_hija_de_la_tarjeta_y_queda_debajo(resultado):
    _, r = resultado
    bx, by, bw, bh = r["barra"]
    tx, ty, tw, th = r["tarjeta"]
    assert not r["barra_en_tarjeta"]
    assert r["padre_barra_es_pantalla"]
    assert by >= ty + th
    assert by + bh <= 1920 and 0 <= bx and bx + bw <= 1200
    # misma colocación que Opciones: x = 34, 171 px del borde inferior (lienzo 1196)
    assert bx == pytest.approx(34 * 1200 / 1196, abs=1)
    assert by == pytest.approx(1920 - 171 * 1200 / 1196, abs=1)
    assert bw == pytest.approx(1128 * 1200 / 1196, abs=1)


def test_cada_boton_esta_en_la_barra_y_emite_su_senal(resultado):
    caso, r = resultado
    assert r["fuera"] == []
    assert r["senales"] == [s for _, s in caso[3]]


def test_ningun_contenido_queda_tapado(resultado):
    _, r = resultado
    assert r["tapados"] == []


def test_el_contenido_de_la_tarjeta_cabe_dentro_de_ella(resultado):
    # el panel principal llega por debajo de su contenido más bajo
    _, r = resultado
    tx, ty, tw, th = r["tarjeta"]
    assert r["contenido_mas_bajo"][0] <= ty + th + 0.5, r["contenido_mas_bajo"]

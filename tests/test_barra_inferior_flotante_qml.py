# tests/test_barra_inferior_flotante_qml.py
#
# Barra inferior flotante en Login, Cambio de clave y Nuevo usuario
# (docs/mis_plans/instruccion_claude_code_barra_inferior_flotante.md, T1 a T4):
# la misma BarraInferiorMenu de Opciones, FUERA de la tarjeta de contenido y por
# debajo de ella; Atrás e Inicio emiten su señal; la tarjeta ya no lleva `pie`.
# Se carga cada pantalla real a 1200x1920 en subproceso (QGuiApplication propio).

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

_RAIZ = Path(__file__).resolve().parents[1]
_PANTALLAS = _RAIZ / "src" / "autoclave" / "ui_qml" / "qml" / "Pantallas"

# (archivo, tipo QML, objectName de la barra)
CASOS = [
    ("Login", "barraInferiorLogin"),
    ("CambioClave", "barraInferiorCambioClave"),
    ("NuevoUsuario", "barraInferiorNuevoUsuario"),
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

    PANTALLA, BARRA = sys.argv[1], sys.argv[2]
    QML = '''
    import QtQuick
    import Tema
    import "Pantallas"
    import "Componentes"
    Window {
        width: 1200; height: 1920; visible: true
        Binding { target: Escala; property: "factor"; value: 1 }
        %s { objectName: "pantalla"; anchors.fill: parent }
    }
    ''' % PANTALLA
    ruta = f"{QML_DIR}/_prueba_barra_flotante.qml"
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

    def caja(o):
        p = o.mapToScene(o.boundingRect().topLeft())
        return [p.x(), p.y(), o.width(), o.height()]
    barra = w.findChild(QObject, BARRA)
    tarjetas = [o for o in w.findChildren(QObject)
                if o.metaObject().className().startswith("TarjetaContenido_QML")]
    r = {"avisos": avisos, "hay_barra": barra is not None, "tarjetas": len(tarjetas),
         "ventana_alto": w.height(), "ventana_ancho": w.width()}
    if barra is not None and tarjetas:
        r["barra"] = caja(barra)
        r["tarjeta"] = caja(tarjetas[0])
        r["padre_barra"] = barra.parent().metaObject().className()
        senales = []
        barra.atrasPulsado.connect(lambda: senales.append("atras"))
        barra.inicioPulsado.connect(lambda: senales.append("inicio"))
        for nombre in ("botonAtras", "botonInicio"):
            b = barra.findChild(QObject, nombre)
            QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier,
                             b.mapToScene(b.boundingRect().center()).toPoint())
            QTest.qWait(50)
        r["senales"] = senales
    print("RESULTADO=" + json.dumps(r))
""")


def _correr(pantalla, barra):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(_RAIZ / "src") + os.pathsep + str(_RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, pantalla, barra], capture_output=True,
                       text=True, env=env, cwd=_RAIZ, timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout + p.stderr
    return json.loads(linea[len("RESULTADO="):])


@pytest.fixture(scope="module", params=CASOS, ids=[c[0] for c in CASOS])
def resultado(request):
    return request.param[0], _correr(*request.param)


def test_carga_sin_avisos_y_con_barra(resultado):
    _, r = resultado
    assert r["avisos"] == []
    assert r["hay_barra"] and r["tarjetas"] >= 1


def test_la_barra_queda_fuera_y_debajo_de_la_tarjeta(resultado):
    _, r = resultado
    bx, by, bw, bh = r["barra"]
    tx, ty, tw, th = r["tarjeta"]
    assert by >= ty + th                                 # por debajo, sin solaparse
    assert r["padre_barra"] != "TarjetaContenido_QMLTYPE"
    assert not r["padre_barra"].startswith(("TarjetaContenido", "QQuickItem"))  # hija de la pantalla
    assert by + bh <= r["ventana_alto"]
    assert 0 <= bx and bx + bw <= r["ventana_ancho"]
    # 171 px del borde inferior (lienzo 1196); D8-5.2 (tanda 8): mismo x y
    # ancho que la tarjeta de encima
    assert by == pytest.approx(1920 - 171 * 1200 / 1196, abs=1)
    assert bx == pytest.approx(tx, abs=0.5)
    assert bw == pytest.approx(tw, abs=0.5)


def test_atras_e_inicio_emiten_su_senal(resultado):
    _, r = resultado
    assert r["senales"] == ["atras", "inicio"]


@pytest.mark.parametrize("pantalla", [c[0] for c in CASOS])
def test_la_tarjeta_no_conserva_pie(pantalla):
    texto = (_PANTALLAS / f"{pantalla}.qml").read_text(encoding="utf-8")
    assert re.search(r"^\s*pie\s*:", texto, re.M) is None
    assert "BarraInferior {" not in texto            # la barra de 4 iconos ya no se usa

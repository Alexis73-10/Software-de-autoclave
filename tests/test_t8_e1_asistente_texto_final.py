"""D8-3.22 (tanda 8, E1): el resultado del asistente de instalación dice
"Instalación completada" con el botón Continuar, en lugar de "Reinicie el
software". Se carga InstalacionVentana.qml offscreen en un subproceso, en es y
en, se fuerza el paso final y se pulsa Continuar: la ventana sale con el
código 3 (CODIGO_INSTALACION_TERMINADA), que el lanzador toma como "seguir con
el arranque normal" (exe_unico.py).

REI-01 (tanda 18, decisiones_tanda_18.md) cambia por decisión de Cristian lo
que D8-3.22 fijaba: el botón pasa a «Reiniciar ahora» con una cuenta
regresiva de 10 s y el lanzador reinicia el PC al recibir el código 3; las
aserciones del botón y del texto se actualizaron (el código 3 sigue igual)."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

_RAIZ = Path(__file__).resolve().parents[1]

_SCRIPT = textwrap.dedent(r'''
    import json, sys
    from PySide6.QtCore import QObject, QUrl, QMetaObject, QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from autoclave import i18n
    import autoclave.ui_qml.bridge.i18n_qml as i18n_qml
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller, teclado_numerico_controller  # noqa: F401
    from autoclave.ui_qml.bridge.puente_instalacion import PuenteInstalacion
    from autoclave.ui_qml.app import QML_DIR

    i18n.cargar()
    i18n.fijar_idioma(sys.argv[1])
    i18n_qml.instancia._consultar = lambda: None
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(QML_DIR)
    engine.exit.connect(app.exit)   # QQmlApplicationEngine (app.py) lo hace solo
    avisos = []
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    puente = PuenteInstalacion(validar_codigo=lambda s, c: False)
    comp = QQmlComponent(engine, QUrl.fromLocalFile(QML_DIR + "/InstalacionVentana.qml"))
    ventana = comp.createWithInitialProperties({"puenteInstalacion": puente})
    assert ventana is not None, comp.errorString()
    a = ventana.findChild(QObject, "asistenteInstalacion")
    a.setProperty("terminado", True)

    def obj(nombre):
        return a.findChild(QObject, nombre)

    obs = {
        "titulo": obj("tituloInstalacion").property("text"),
        "texto": obj("textoListo").property("text"),
        "texto_visible": bool(obj("pasoListo").property("visible")),
        "boton": obj("botonContinuar").property("texto"),
        "boton_visible": bool(obj("botonContinuar").property("visible")),
        "siguiente_visible": bool(obj("botonSiguiente").property("visible")),
    }
    QTimer.singleShot(0, lambda: QMetaObject.invokeMethod(obj("botonContinuar"), "pulsado"))
    QTimer.singleShot(5000, lambda: app.exit(99))
    obs["codigo_salida"] = app.exec()
    obs["avisos"] = avisos[:10]
    print("RESULTADO=" + json.dumps(obs, ensure_ascii=False))
''')


def _cargar(idioma):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(_RAIZ / "src") + os.pathsep + str(_RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, idioma],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=_RAIZ,
                       timeout=120)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


# REI-01: antes "Continuar"/"Continue" y ningún "reinici"/"restart" en el texto
@pytest.mark.parametrize("idioma, titulo, boton", [
    ("es", "INSTALACIÓN COMPLETADA", "Reiniciar ahora"),
    ("en", "INSTALLATION COMPLETE", "Restart now"),
])
def test_resultado_dice_instalacion_completada_con_reiniciar_ahora(idioma, titulo, boton):
    r = _cargar(idioma)
    assert r["avisos"] == []
    assert r["titulo"] == titulo
    assert r["texto_visible"] and r["boton_visible"] and not r["siguiente_visible"]
    assert r["boton"] == boton
    assert r["codigo_salida"] == 3             # el lanzador reinicia el PC (REI-01)


def test_catalogo_sin_reiniciar_en_el_resultado():
    # REI-01: el aviso de reinicio va en su propia clave (instalacion.reinicio_cuenta);
    # el texto y el título del resultado siguen sin hablar de reiniciar
    for idioma, prohibido in (("es", "reinici"), ("en", "restart")):
        cat = json.loads((_RAIZ / f"src/autoclave/i18n/{idioma}.json").read_text(encoding="utf-8"))
        assert prohibido not in cat["instalacion"]["listo_texto"].lower()
        assert prohibido not in cat["instalacion"]["listo_titulo"].lower()

# tests/banco/llf_capturas_barra_fases.py
#
# Llenado de fases (planeacion_llenado_fases.md §8.2, paso 4a): capturas de la
# barra de fases con líquido, a 1024 px de ancho (1024 x 1638) y en la base
# 1200 x 1920, en docs/informes/llenado_fases/capturas/. No es una prueba
# automática: Cristian las revisa a ojo. Usa la plataforma real (no offscreen)
# para ver el antialias y las animaciones.
#
#   set PYTHONPATH=<raíz del worktree>\src     (si hay otro checkout instalado)
#   python tests/banco/llf_capturas_barra_fases.py          genera las capturas
#   python tests/banco/llf_capturas_barra_fases.py --demo   abre el MODO
#                                                           DEMOSTRACION animado
#                                                           (Pruebas/PruebaCicloEnCurso.qml)
#
# El script fija PYTHONPATH al `src` de este árbol para que se importe el
# código de este checkout y no el de otro instalado en modo editable.

import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "docs" / "informes" / "llenado_fases" / "capturas"

_COMUN = textwrap.dedent(r'''
    import os, sys
    from PySide6.QtCore import QObject, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave import i18n
    raiz = sys.argv[1]
    assert os.path.normcase(QML_DIR).startswith(os.path.normcase(raiz)), (QML_DIR, raiz)
    i18n.fijar_idioma("es")
    qapp = QGuiApplication([])
    _cargar_fuentes()
''')

_SCRIPT_DEMO = _COMUN + textwrap.dedent(r'''
    engine = QQmlApplicationEngine()
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"demostracion": True})
    engine.load(QUrl.fromLocalFile(QML_DIR + "/Pruebas/PruebaCicloEnCurso.qml"))
    w = engine.rootObjects()[0]
    w.setWidth(800); w.setHeight(1280)
    sys.exit(qapp.exec())
''')

_SCRIPT = _COMUN + textwrap.dedent(r'''
    destino = sys.argv[2]
    CL = ["precalentamiento", "vacio", "calentamiento", "esterilizacion", "descompresion", "secado"]

    def F(spec):
        out = []
        for i, t in enumerate(spec):
            e = t[0]
            est = {"c": "completada", "p": "pendiente", "f": "fallida", "i": "interrumpida"}.get(e, "activa")
            fr = (float(t[2:]) if len(t) > 2 else None) if e == "a" else (1.0 if e == "c" else 0.0 if e == "p" else None)
            out.append({"fase": CL[i], "estado": est, "fraccion": fr})
        return out

    # (nombre, [(spec, datosVigentes, espera_ms)], espera final antes de capturar)
    ESC = [
        ("01_pendiente", [(["p"] * 6, True, 600)]),
        ("02_activa_010", [(["a:0.1", "p", "p", "p", "p", "p"], True, 1500)]),
        ("03_activa_045", [(["c", "a:0.45", "p", "p", "p", "p"], True, 1500)]),
        ("04_activa_090", [(["c", "c", "a:0.9", "p", "p", "p"], True, 1500)]),
        ("05_completada_y_activa", [(["c", "c", "c", "a:0.6", "p", "p"], True, 1500)]),
        ("06_sin_referencia", [(["c", "c", "a", "p", "p", "p"], True, 1500)]),
        ("07_fallida", [(["c", "c", "c", "a:0.4", "p", "p"], True, 600),
                        (["c", "c", "c", "f", "p", "p"], True, 900)]),
        ("08_interrumpida", [(["c", "c", "a:0.6", "p", "p", "p"], True, 600),
                             (["c", "c", "i", "p", "p", "p"], True, 900)]),
        ("09_todas_completadas", [(["c"] * 6, True, 800)]),
        ("10_sin_datos_vigentes", [(["c", "c", "c", "a:0.5", "p", "p"], False, 1500)]),
        # secuencia de cambio de fase, capturas cada paso
        ("11a_antes_del_cambio", [(["c", "a:0.85", "p", "p", "p", "p"], True, 1500)]),
        ("11b_cierre_y_conector", [(["c", "a:0.85", "p", "p", "p", "p"], True, 1500),
                                   (["c", "c", "a:0.1", "p", "p", "p"], True, 650)]),
        ("11c_chorro_nivel_bajo", [(["c", "a:0.85", "p", "p", "p", "p"], True, 1500),
                                   (["c", "c", "a:0.1", "p", "p", "p"], True, 1900)]),
        ("11d_chorro_nivel_medio", [(["c", "a:0.85", "p", "p", "p", "p"], True, 1500),
                                    (["c", "c", "a:0.1", "p", "p", "p"], True, 1900),
                                    (["c", "c", "a:0.35", "p", "p", "p"], True, 1600)]),
        ("11e_sin_chorro_sobre_mitad", [(["c", "a:0.85", "p", "p", "p", "p"], True, 1500),
                                        (["c", "c", "a:0.1", "p", "p", "p"], True, 1900),
                                        (["c", "c", "a:0.6", "p", "p", "p"], True, 1600)]),
        ("12a_recalculo_antes", [(["c", "c", "a:0.9", "p", "p", "p"], True, 1500)]),
        ("12b_recalculo_despues", [(["c", "c", "a:0.9", "p", "p", "p"], True, 1500),
                                   (["c", "c", "a:0.75", "p", "p", "p"], True, 1800)]),
    ]
    TAMANOS = [(1024, 1638, "1024"), (1200, 1920, "1200")]

    for (ancho, alto, etiqueta) in TAMANOS:
        engine = QQmlApplicationEngine()
        engine.warnings.connect(lambda ws: [print('AVISO QML:', x.toString(), file=sys.stderr) for x in ws])
        engine.addImportPath(QML_DIR)
        engine.setInitialProperties({})
        engine.load(QUrl.fromLocalFile(QML_DIR + "/Pruebas/PruebaCicloEnCurso.qml"))
        w = engine.rootObjects()[0]
        w.setFlags(w.flags() | Qt.FramelessWindowHint)
        w.setGeometry(0, 0, ancho, alto)
        w.show()
        QTest.qWait(600)
        todos = w.findChildren(QObject)
        pantalla = [o for o in todos if o.metaObject().className().startswith("PantallaCicloEnCurso_QML")][0]
        barra = [o for o in todos if o.metaObject().className().startswith("BarraFases_QML")][0]
        for nombre, pasos in ESC:
            pantalla.setProperty("fases", [])
            QTest.qWait(100)
            # primer paso: primera carga, sin animación
            for k, (spec, vig, espera) in enumerate(pasos):
                pantalla.setProperty("datosVigentes", vig)
                pantalla.setProperty("fases", F(spec))
                QTest.qWait(espera)
            img = w.grabWindow()
            img.save(os.path.join(destino, f"{nombre}_{etiqueta}.png"))
            # recorte de la barra (para revisarla a gran tamaño)
            esc = barra.property("escala")
            p = barra.mapToScene(barra.boundingRect().topLeft())
            recorte = img.copy(0, int(p.y() + 420 * esc), ancho, int(160 * esc))
            recorte.save(os.path.join(destino, f"{nombre}_{etiqueta}_barra.png"))
            print("captura", nombre, etiqueta)
        w.close()
        engine.deleteLater()
        QTest.qWait(50)
''')


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    demo = "--demo" in sys.argv
    env = {**os.environ,
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ),
           "QT_ENABLE_HIGHDPI_SCALING": "0"}
    env.pop("QT_QPA_PLATFORM", None)   # plataforma real
    script = _SCRIPT_DEMO if demo else _SCRIPT
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", script, str(RAIZ), str(DESTINO)],
                       capture_output=not demo, text=True, encoding="utf-8", env=env, cwd=RAIZ,
                       timeout=None if demo else 900)
    if not demo:
        print(p.stdout)
        if p.returncode != 0:
            print(p.stderr, file=sys.stderr)
    return p.returncode


if __name__ == "__main__":
    raise SystemExit(main())

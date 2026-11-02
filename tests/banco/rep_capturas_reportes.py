# tests/banco/rep_capturas_reportes.py
#
# Capturas de la pantalla Reportes (etapa E de planeacion_dashboard_reportes.md)
# con el arnés qml/Pruebas/PruebaReportes.qml y datos de ejemplo
# (tests/helpers/reportes_ejemplo.py: ~124 ciclos de octubre de 2026, no son
# lecturas reales), en español e inglés y a 1200x1920 (5:8) y 1080x1920 (9:16):
#
#   mes          Mes (octubre) recorrido de arriba a abajo
#   anio         Año (12 meses) y la tarjeta del calendario
#   dia_previo   día con fallo previo (8 de octubre) en el panel del día
#   dia_falto    día «faltó» (14 de octubre)
#   selector     selector de programa abierto
#   alarmas      «Ver todas» de las alarmas del periodo (lista completa paginada)
#   correo       destino de correo sin sesión (solo los guardados)
#
# Por defecto usa la plataforma real de Windows (ventana sin marco en 0,0 con
# QT_ENABLE_HIGHDPI_SCALING=0, como AJ-01), que dibuja bien los Shape recortados
# por el Flickable; con offscreen aparecen figuras fuera del recorte al
# desplazar (`--plataforma offscreen` solo para ejecutarlo sin pantalla).
#
# Uso (no es una prueba de pytest):
#
#     PYTHONPATH=<repo>\src python tests/banco/rep_capturas_reportes.py [--solo 1200x1920] [--idiomas es en]
#
# Guarda en docs/informes/dashboard_reportes/capturas/rep_<idioma>_<tamaño>_<escenario>[_<n>].png

import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "src"))
DESTINO = RAIZ / "docs" / "informes" / "dashboard_reportes" / "capturas"
TAMANOS = {"1200x1920": (1200, 1920), "1080x1920": (1080, 1920)}

_SCRIPT = textwrap.dedent(r'''
    import json, os, sys, tempfile
    from pathlib import Path
    from PySide6.QtCore import QObject, QPointF, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge import i18n_qml
    from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
    from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial
    from autoclave.ui_qml.bridge.reporte_dashboard import ReporteDashboard
    from autoclave.ui_qml import historial_ejemplo as ejemplo
    from tests.helpers.reportes_ejemplo import ClienteReportes, HOY

    cfg = json.loads(sys.argv[1])
    i18n.cargar()
    i18n.fijar_idioma(cfg["idioma"])
    i18n_qml.instancia._consultar = lambda: None
    qapp = QGuiApplication([])
    _cargar_fuentes()
    destino = Path(cfg["destino"])
    destino.mkdir(parents=True, exist_ok=True)
    pref = f"rep_{cfg['idioma']}_{cfg['tamano']}"

    def config_con_destinos():
        c = ejemplo.config_correo_ejemplo()
        c.destinos = [{"nombre": "Mantenimiento", "correo": "mantenimiento@example.com"},
                      {"nombre": "Calidad", "correo": "calidad@example.com"}]
        return c

    with ClienteReportes(Path(tempfile.mkdtemp())) as cli:
        rd = ReporteDashboard(cli, ejecutar=lambda t: t(), hoy=lambda: HOY)
        hist = CiclosHistorial(cli, ejecutar=lambda t: t(), hoy=lambda: HOY)
        acc = AccionesCiclos(cli, cargar_config=config_con_destinos, enviar=ejemplo.enviar_ejemplo,
                             ejecutar=lambda t: t())
        eng = QQmlApplicationEngine()
        avisos = []
        eng.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
        eng.addImportPath(QML_DIR)
        eng.setInitialProperties({"reporteDashboard": rd, "acciones": acc, "historial": hist})
        eng.load(QUrl.fromLocalFile(QML_DIR + "/Pruebas/PruebaReportes.qml"))
        v = eng.rootObjects()[0]
        v.setFlags(Qt.FramelessWindowHint | Qt.Window)
        v.setGeometry(0, 0, cfg["ancho"], cfg["alto"])
        v.show()
        QTest.qWait(1200)

        def buscar(nombre, it=None):
            it = it or v.contentItem()
            for h in it.childItems():
                if h.objectName() == nombre:
                    return h
                e = buscar(nombre, h)
                if e is not None:
                    return e
            return None

        flick = buscar("contenidoReportes")

        def ir_a(nombre, margen=20):
            o = buscar(nombre)
            y = o.mapToItem(flick.property("contentItem"), QPointF(0, 0)).y()
            tope = max(0, flick.property("contentHeight") - flick.height())
            flick.setProperty("contentY", max(0, min(tope, y - margen)))
            QTest.qWait(250)

        def foto(nombre):
            QTest.qWait(250)
            v.grabWindow().save(str(destino / f"{pref}_{nombre}.png"))

        def tocar(o):
            c = o.mapToScene(o.boundingRect().center()).toPoint()
            QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, c)
            QTest.qWait(300)

        def recorrido(nombre):
            tope = max(0, flick.property("contentHeight") - flick.height())
            paso = flick.height() - 80
            y, k = 0, 1
            while True:
                flick.setProperty("contentY", min(y, tope))
                foto(f"{nombre}_{k}")
                if y >= tope:
                    break
                y += paso
                k += 1
            flick.setProperty("contentY", 0)

        esc = cfg["escenarios"]
        if "mes" in esc:
            recorrido("mes")
        if "dia_previo" in esc:
            rd.elegirDia("2026-10-08"); QTest.qWait(300)
            ir_a("seccionCalendario"); foto("dia_previo")
            ir_a("panelDiaCalendario", margen=300); foto("dia_previo_panel")
        if "dia_falto" in esc:
            rd.elegirDia("2026-10-14"); QTest.qWait(300)
            ir_a("panelDiaCalendario", margen=300); foto("dia_falto")
        if "selector" in esc:
            ir_a("seccionCalendario")
            sel = buscar("selectorProgramaCalendario")
            sel.abrir() if hasattr(sel, "abrir") else sel.setProperty("abierto", True)
            QTest.qWait(400)
            foto("selector")
            sel.setProperty("abierto", False)
            QTest.qWait(200)
        if "anio" in esc:
            rd.cambiarPeriodo("anio"); QTest.qWait(500)
            flick.setProperty("contentY", 0); foto("anio_1")
            ir_a("seccionCalendario"); foto("anio_calendario")
            rd.cambiarPeriodo("mes"); QTest.qWait(300)
        if "alarmas" in esc:
            ir_a("seccionAlarmas")
            lista = buscar("listaAlarmasPeriodo")
            lista.abrirTodas()
            QTest.qWait(300)
            foto("alarmas_todas")
            lista.cerrarTodas()
            QTest.qWait(200)
        if "correo" in esc:
            v.setProperty("sesionActiva", False); QTest.qWait(200)
            ir_a("seccionAcciones")
            tocar(buscar("botonEnviarResumen"))
            foto("correo_sin_sesion")
        print("RESULTADO=" + json.dumps({"avisos": [a for a in avisos if "Binding loop" not in a][:30]},
                                        ensure_ascii=False))
''')


def correr(idioma: str, tamano: str, escenarios, plataforma: str) -> list:
    ancho, alto = TAMANOS[tamano]
    cfg = {"idioma": idioma, "tamano": tamano, "ancho": ancho, "alto": alto,
           "escenarios": list(escenarios), "destino": str(DESTINO)}
    env = {**os.environ, "QT_QPA_PLATFORM": plataforma, "QT_ENABLE_HIGHDPI_SCALING": "0",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=600)
    linea = next((x for x in p.stdout.splitlines() if x.startswith("RESULTADO=")), None)
    if not linea:
        raise SystemExit("rep_capturas_reportes\n" + p.stdout[-2000:] + p.stderr[-3000:])
    return json.loads(linea[len("RESULTADO="):])["avisos"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--idiomas", nargs="*", default=["es", "en"])
    ap.add_argument("--solo", nargs="*", default=list(TAMANOS))
    ap.add_argument("--escenarios", nargs="*",
                    default=["mes", "anio", "dia_previo", "dia_falto", "selector", "alarmas", "correo"])
    ap.add_argument("--plataforma", default="windows", choices=["windows", "offscreen"])
    a = ap.parse_args()
    malos = 0
    for tam in a.solo:
        for idioma in a.idiomas:
            avisos = correr(idioma, tam, a.escenarios, a.plataforma)
            print(idioma, tam, "avisos QML:", avisos)
            malos += len(avisos)
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())

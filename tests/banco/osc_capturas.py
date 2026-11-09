# tests/banco/osc_capturas.py
#
# Modo oscuro, paso 7: capturas de las pantallas principales en tema claro y
# oscuro, a 1080x1920 y 1024x1638, offscreen (MultiEffect no se dibuja; igual
# en todas las corridas, así que el diff claro contra dev es comparable).
# No es una prueba automática.
#
#   python tests/banco/osc_capturas.py [--temas claro oscuro] [--destino DIR]
#
# Para el diff contra dev: correr este mismo archivo con OSC_RAIZ apuntando a un
# worktree de dev (ahí no existe Colores.oscuro: solo se admite --temas claro).

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ_PROPIA = Path(__file__).resolve().parents[2]
RAIZ = Path(os.environ.get("OSC_RAIZ", RAIZ_PROPIA))
DESTINO = RAIZ_PROPIA / "docs" / "informes" / "modo_oscuro" / "capturas"
TAMANOS = [(1080, 1920), (1024, 1638)]

_SCRIPT = textwrap.dedent(r'''
    import json, os, sys
    from PySide6.QtCore import QObject, QUrl, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem, QQuickWindow
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.bridge import i18n_qml
    from autoclave.cliente.session_manager import SessionManager

    cfg = json.loads(sys.argv[1])
    tema, destino, prefijo = cfg["tema"], cfg["destino"], cfg["prefijo"]
    i18n.cargar(); i18n.fijar_idioma("es")
    i18n_qml.instancia._consultar = lambda: None

    class Sesion:
        sinConexion = False
        def enviar(self, metodo, ruta, cuerpo=None):
            if ruta.startswith("/theme"):
                return sesion_backend.Resultado("ok", {"tema": tema}, 200)
            return sesion_backend.Resultado("ok", {}, 200)
        def __getattr__(self, n):
            return lambda *a, **k: sesion_backend.Resultado("ok", {}, 200)
    sesion_backend.ventana = lambda: Sesion()
    SessionManager.login({"usuario": "ingeniero", "nombre": "Ingeniero", "rol": "ingeniero",
                          "debe_cambiar_clave": False}, token="t")

    qapp = QGuiApplication([])
    _cargar_fuentes()

    PUENTE_PRECICLO = """
    QtObject {
        id: puenteP
        property bool connected: true
        property string estadoModuloEs: "ok"
        property string cicloActivo: "04"
        property string programa: "BOWIE & DICK"
        property string tempEsterilizacion: "134.0"
        property string tiempoEsterilizacion: "3.5"
        property string tiempoSecado: "15"
        property string tempCamara: "098.2"
        property string tempReferencia: "096.4"
        property string presionCamara: "084.1"
        property string estadoEquipo: %(estado)s
        property string machineState: "PREPARACION"
        property int door: 1
        property string doorState: "CERRADO"
        property bool doorOpen: false
        property bool puertaConActuador: false
        property bool listoParaCiclo: %(listo)s
        property ListModel alarms: ListModel {
            Component.onCompleted: { %(alarmas)s }
        }
    }
    """
    ALARMA = ('append({ id: "CHAQUETA_FRIA", level: "FALLA", description: "Chaqueta fria",'
              ' source_state: "PREPARACION", priority: "media" })')

    def envolver(w, h, cuerpo, extra=""):
        return """
        import QtQuick
        import Tema
        import "Pantallas"
        import "Componentes"
        Window {
            id: ventana
            width: %d; height: %d; visible: true
            color: Colores.fondoMarinoOscuro
            Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / Escala.anchoDiseno, ventana.height / Escala.altoDiseno) }
            Binding { target: Escala; property: "altoLienzo"; value: Math.max(Escala.altoDiseno, ventana.height / Escala.factor) }
            %s
            Item {
                id: lienzo
                width: Escala.px(Escala.anchoDiseno); height: Escala.px(Escala.altoLienzo)
                anchors.centerIn: parent; clip: true
                %s
            }
        }
        """ % (w, h, extra, cuerpo)

    ESCENARIOS = {}
    # (nombre) -> ("qml", cuerpo, extra, accion)  |  ("arnes", archivo, props, accion)
    ESCENARIOS["reposo"] = ("qml", "Reposo { anchors.fill: parent }", "", None)
    ESCENARIOS["login"] = ("qml", "Login { anchors.fill: parent; teclado: tec }", "", None)
    ESCENARIOS["login_teclado"] = ("qml", "Login { anchors.fill: parent; teclado: tec }\n"
        "PanelTeclado { id: tec; objectName: 'tec' }", "", "teclado")
    ESCENARIOS["menu"] = ("arnes", "PruebaMenuPrincipal.qml", {}, None)
    ESCENARIOS["preciclo_preparado"] = ("qml", "PantallaPreciclo { anchors.fill: parent; puente: puenteP }",
        PUENTE_PRECICLO % {"estado": '"listo"', "listo": "true", "alarmas": ""}, None)
    ESCENARIOS["preciclo_alarma"] = ("qml", "PantallaPreciclo { anchors.fill: parent; puente: puenteP }",
        PUENTE_PRECICLO % {"estado": '"no_preparado"', "listo": "false", "alarmas": ALARMA}, None)
    ESCENARIOS["opciones_tema"] = ("qml", "OpcionesParametrosEquipo { objectName: 'opeq'; anchors.fill: parent }", "", "maquina")

    # arneses de t21 (PruebaFinDeCiclo): ciclo en curso con grafica, fin fallido, modal
    from autoclave.ui_qml.domain import fin_de_ciclo
    ALARMAS = [{"codigo": "PRE-01", "nivel": "AVISO", "titulo": "Presión de chaqueta baja", "descripcion": "",
                "valores": {"pres": 268, "minimo": 280, "objetivo": 300, "rango": 20},
                "aparecida": "2026-10-28T13:02:15", "resuelta": "2026-10-28T13:04:40"}]
    FALLO = {"tipo": "fallo", "codigo": "CIC-12", "valores": {"tsat": 136.4, "dt": 2.3, "temp": 134.1},
             "motivo": "", "fase": "esterilizacion", "hora_fin": "2026-10-28T13:21:07",
             "cancelado_por": None, "observaciones": []}
    def fases(fin_fase, estado_fin):
        orden = ["precalentamiento", "vacio", "calentamiento", "esterilizacion", "descompresion", "secado"]
        salida, antes = [], True
        for f in orden:
            if f == fin_fase:
                salida.append({"fase": f, "estado": estado_fin}); antes = False
            else:
                salida.append({"fase": f, "estado": "completada" if antes else "pendiente"})
        return salida
    _t = fin_de_ciclo.normalizar_terminacion(FALLO, "fallo")
    _fin = fin_de_ciclo.armar(_t, fin_de_ciclo.normalizar_alarmas(ALARMAS), "es")
    ESCENARIOS["ciclo_grafica"] = ("arnes", "PruebaFinDeCiclo.qml",
        {"resultado": "", "fin": {}, "fases": fases("esterilizacion", "activa")}, None)
    ESCENARIOS["fin_fallido"] = ("arnes", "PruebaFinDeCiclo.qml",
        {"resultado": "fallo", "fin": _fin, "fases": fases("esterilizacion", "fallida")}, None)

    def ejecutar(nombre):
        tipo, a, b, accion = ESCENARIOS[nombre]
        w, h = cfg["ancho"], cfg["alto"]
        engine = QQmlApplicationEngine()
        engine.addImportPath(QML_DIR)
        ruta_tmp = None
        if tipo == "qml":
            ruta_tmp = f"{QML_DIR}/_osc_{os.getpid()}.qml"
            fuente = envolver(w, h, a, b)
            if "tec" in a and "id: tec" not in a:
                fuente = fuente.replace("Login {", "PanelTeclado { id: tec }\n Login {", 1)
            open(ruta_tmp, "w", encoding="utf-8").write(fuente)
            url = ruta_tmp
        else:
            url = f"{QML_DIR}/Pruebas/{a}"
            if b: engine.setInitialProperties(b)
        engine.load(QUrl.fromLocalFile(url))
        if ruta_tmp: os.remove(ruta_tmp)
        win = engine.rootObjects()[0]
        if tema == "oscuro":
            engine.singletonInstance("Tema", "Colores").setProperty("oscuro", True)
        win.setFlags(win.flags() | Qt.FramelessWindowHint)
        win.setGeometry(0, 0, w, h)
        win.show()
        QTest.qWait(600)
        if accion and accion.startswith("obj:"):
            for o in win.findChildren(QObject):
                if o.objectName() == accion[4:]:
                    o.setProperty("visible", True)
            QTest.qWait(500)
        if accion == "maquina":
            from PySide6.QtCore import QPointF
            for o in win.findChildren(QObject):
                if o.objectName() == "tarjeta_maquina":
                    c = o.mapToScene(QPointF(o.width() / 2, o.height() / 2)).toPoint()
                    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, c)
            QTest.qWait(900)
        if accion == "teclado":
            for o in win.findChildren(QObject):
                if o.objectName() == "tec":
                    from PySide6.QtCore import QMetaObject, Q_ARG
                    QMetaObject.invokeMethod(o, "abrirAlfanumerico", Q_ARG("QVariant", "Usuario"),
                        Q_ARG("QVariant", ""), Q_ARG("QVariant", 30), Q_ARG("QVariant", False),
                        Q_ARG("QVariant", None), Q_ARG("QVariant", None))
            QTest.qWait(800)
        QTest.qWait(400)
        win.grabWindow().save(os.path.join(destino, f"{prefijo}_{tema}_{w}_{nombre}.png"))
        print("captura", nombre)
        win.close(); engine.deleteLater(); QTest.qWait(50)

    for n in cfg["escenarios"]:
        try:
            ejecutar(n)
        except Exception as e:
            print("FALLO", n, repr(e))
''')


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--temas", nargs="+", default=["claro", "oscuro"])
    ap.add_argument("--destino", default=str(DESTINO))
    ap.add_argument("--prefijo", default="osc")
    ap.add_argument("--escenarios", nargs="*", default=None)
    a = ap.parse_args()
    Path(a.destino).mkdir(parents=True, exist_ok=True)
    esc = a.escenarios or ["reposo", "login", "login_teclado", "menu", "preciclo_preparado",
                           "preciclo_alarma", "opciones_tema", "ciclo_grafica", "fin_fallido"]
    env = {**os.environ, "QT_ENABLE_HIGHDPI_SCALING": "0",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    for tema in a.temas:
        for ancho, alto in TAMANOS:
            cfg = {"tema": tema, "destino": a.destino, "prefijo": a.prefijo, "ancho": ancho,
                   "alto": alto, "escenarios": esc, "t21": ""}
            p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg)],
                               capture_output=True, text=True, encoding="utf-8", env=env,
                               cwd=RAIZ, timeout=600)
            print(p.stdout)
            if p.returncode != 0:
                print(p.stderr[-3000:], file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

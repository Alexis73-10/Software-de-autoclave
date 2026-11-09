# tests/banco/hor_capturas.py
#
# Tanda horizontal (9-nov): capturas de todas las pantallas QML en el lienzo
# horizontal fijo 1920x1200 (8:5), en tema claro y oscuro, offscreen (sin
# backend: sesión HTTP doble que responde 200 {}). Además de la captura, cada
# escenario pasa la revisión genérica de textos de
# tests/helpers/textos_caben_qml.py (recortado, encogido, sale del cuadro...)
# y la de «fuera del lienzo» (ítems visibles cuyo borde pasa de 1920x1200, en
# coordenadas de la ventana, sin contar los recortados por un clip). No es una
# prueba automática.
#
#   python tests/banco/hor_capturas.py [--temas claro oscuro] [--escenarios a b]
#                                      [--destino DIR] [--tamano 1920x1200]
#
# Deja hor_<tema>_<escenario>.png en docs/informes/horizontal/capturas/ y
# resumen_<tema>.json con los problemas de cada escenario.

import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ_PROPIA = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_PROPIA))
DESTINO = RAIZ_PROPIA / "docs" / "informes" / "horizontal" / "capturas"

_SCRIPT = textwrap.dedent(r'''
    import json, os, sys, tempfile
    from pathlib import Path
    from PySide6.QtCore import QObject, QUrl, Qt, QPointF, QMetaObject, Q_ARG, Q_RETURN_ARG
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
    from PySide6.QtQuick import QQuickItem, QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_qml.bridge import i18n_qml
    from autoclave.cliente.session_manager import SessionManager
    from tests.helpers.textos_caben_qml import FUNCION_REVISAR

    cfg = json.loads(sys.argv[1])
    tema, destino = cfg["tema"], cfg["destino"]
    W, H = cfg["ancho"], cfg["alto"]
    i18n.cargar(); i18n.fijar_idioma(cfg.get("idioma", "es"))
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
        objectName: "puente"
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
        property bool puertaConActuador: %(actuador)s
        property bool listoParaCiclo: %(listo)s
        property bool inicioCicloVisible: true
        property ListModel alarms: ListModel {
            Component.onCompleted: { %(alarmas)s }
        }
    }
    """
    ALARMA = ('append({ id: "CHAQUETA_FRIA", level: "FALLA", description: "Chaqueta fria",'
              ' source_state: "PREPARACION", priority: "media" });'
              'append({ id: "SUMINISTRO", level: "ALERTA", description: "Revise el suministro de agua",'
              ' source_state: "PREPARACION", priority: "baja" })')
    PUENTE_SIMPLE = """
    QtObject { id: puenteFalso; objectName: "puente"; property string machineState: "PREPARADO"
               property bool connected: true }
    """

    # En vertical no se toca Escala.horizontal (así el mismo guion corre contra
    # un árbol de dev, donde no existe, para comparar el vertical: --raiz)
    BIND_HZ = ('Binding { target: Escala; property: "horizontal"; '
               'value: Escala.esHorizontal(ventana.width, ventana.height) }') if W >= H else ""

    def envolver(cuerpo, extra=""):
        return """
        import QtQuick
        import Tema
        import "Pantallas"
        import "Componentes"
        Window {
            id: ventana
            width: %d; height: %d; visible: true
            color: Colores.fondoMarinoOscuro
            %s
            Binding { target: Escala; property: "factor"; value: Math.min(ventana.width / Escala.anchoDiseno, ventana.height / Escala.altoDiseno) }
            Binding { target: Escala; property: "altoLienzo"; value: Math.max(Escala.altoDiseno, ventana.height / Escala.factor) }
            %s
            Item {
                id: lienzo
                objectName: "lienzo"
                width: Escala.px(Escala.anchoDiseno); height: Escala.px(Escala.altoLienzo)
                anchors.centerIn: parent; clip: true
                %s
            }
        }
        """ % (W, H, BIND_HZ, extra, cuerpo)

    # nombre -> dict(tipo="qml"|"arnes", cuerpo/archivo, extra, props, accion)
    E = {}
    def qml(nombre, cuerpo, extra=PUENTE_SIMPLE, accion=None):
        E[nombre] = {"tipo": "qml", "cuerpo": cuerpo, "extra": extra, "accion": accion}
    def arnes(nombre, archivo, props=None, accion=None, py=None):
        E[nombre] = {"tipo": "arnes", "archivo": archivo, "props": props or {}, "accion": accion,
                     "py": py}

    # intro y arranque
    qml("intro", "IntroArranque { anchors.fill: parent }")
    qml("reposo", "Reposo { anchors.fill: parent }")
    # sesión
    qml("login", "Login { anchors.fill: parent; teclado: tec }\nPanelTeclado { id: tec; objectName: 'tec' }")
    qml("login_teclado", "Login { anchors.fill: parent; teclado: tec }\nPanelTeclado { id: tec; objectName: 'tec' }",
        accion="teclado_alfa")
    qml("login_teclado_num", "Login { anchors.fill: parent; teclado: tec }\nPanelTeclado { id: tec; objectName: 'tec' }",
        accion="teclado_num")
    qml("cambio_clave", "CambioClave { anchors.fill: parent; teclado: tec }\nPanelTeclado { id: tec; objectName: 'tec' }")
    qml("nuevo_usuario", "NuevoUsuario { anchors.fill: parent; teclado: tec }\nPanelTeclado { id: tec; objectName: 'tec' }")
    # asistente
    arnes("instalacion", "PruebaInstalacion.qml")
    # preciclo
    qml("preciclo_preparado", "PantallaPreciclo { anchors.fill: parent; puente: puenteP }",
        PUENTE_PRECICLO % {"estado": '"listo"', "listo": "true", "alarmas": "", "actuador": "false"})
    qml("preciclo_alarma", "PantallaPreciclo { anchors.fill: parent; puente: puenteP }",
        PUENTE_PRECICLO % {"estado": '"no_preparado"', "listo": "false", "alarmas": ALARMA, "actuador": "true"})
    # ciclo en curso (arnés T21)
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
    arnes("ciclo_grafica", "PruebaFinDeCiclo.qml",
          {"resultado": "", "fin": {}, "fases": fases("esterilizacion", "activa")})
    arnes("ciclo_completo", "PruebaFinDeCiclo.qml",
          {"resultado": "completado", "fin": {}, "fases": fases("secado", "completada")})
    arnes("fin_fallido", "PruebaFinDeCiclo.qml",
          {"resultado": "fallo", "fin": _fin, "fases": fases("esterilizacion", "fallida")})
    arnes("ciclo_demo", "PruebaCicloEnCurso.qml", {"automatico": False})
    arnes("ciclo_zoom", "PruebaCicloEnCurso.qml", {"automatico": False}, accion="obj_click:botonPantallaCompleta")
    # menú principal y ventanas flotantes
    def _menu_py():
        from autoclave.ui_qml import historial_ejemplo as ejemplo
        from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
        from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial
        backend = ejemplo.BackendEjemplo()
        return {"historial": CiclosHistorial(backend),
                "acciones": AccionesCiclos(backend, cargar_config=ejemplo.config_correo_ejemplo,
                                           enviar=ejemplo.enviar_ejemplo)}
    arnes("menu", "PruebaMenuPrincipal.qml", py="menu")
    for v in ("ultimo_ciclo", "mantenimiento", "ciclos_hoy", "historial"):
        arnes("menu_" + v, "PruebaMenuPrincipal.qml", {"ventanaInicial": v}, py="menu")
    arnes("menu_historial_detalle", "PruebaMenuPrincipal.qml", {"ventanaInicial": "historial"},
          py="menu", accion="historial_detalle")
    # reportes
    arnes("reportes", "PruebaReportes.qml", py="reportes")
    arnes("reportes_abajo", "PruebaReportes.qml", py="reportes", accion="flick_fin:contenidoReportes")
    # opciones (cada sección sola)
    qml("opciones", "Opciones { anchors.fill: parent; puente: puenteFalso }")
    for s in ["OpcionesParametrosCiclo", "OpcionesParametrosEquipo", "OpcionesUsuarios",
              "OpcionesFechaHora", "OpcionesInfoSistema", "OpcionesBitacora", "OpcionesCalibracionAtm",
              "OpcionesCalibracionSensor", "OpcionesConectividad", "OpcionesRespaldo",
              "OpcionesEntradasSalidas", "OpcionesMantenimiento", "OpcionesAvanzadas",
              "OpcionesManejoCiclos", "OpcionesReasignacion"]:
        qml(s, s + " { objectName: 'seccion'; anchors.fill: parent }")
    qml("opciones_equipo_maquina", "OpcionesParametrosEquipo { objectName: 'opeq'; anchors.fill: parent }",
        accion="click:tarjeta_maquina")
    # teclados
    arnes("teclado_alfa", "PruebaTecladoAlfanumerico.qml")
    arnes("teclado_num", "PruebaTecladoNumerico.qml")

    REVISOR = None

    def todos(win):
        return win.findChildren(QObject)

    def por_nombre(win, n):
        return [o for o in todos(win) if o.objectName() == n]

    FUERA = r"""
    function fueraDelLienzo(raiz, W, H) {
        const malos = []
        function rec(it, recorte) {
            const hijos = it.children || []
            for (let i = 0; i < hijos.length; ++i) {
                const h = hijos[i]
                if (!h.visible || h.opacity === 0 || h.width <= 0 || h.height <= 0) continue
                const p = h.mapToItem(null, 0, 0)
                const r = recorte
                const dentro = !r || (p.x < r.x + r.w && p.x + h.width > r.x && p.y < r.y + r.h && p.y + h.height > r.y)
                if (dentro && (p.x + h.width > W + 2 || p.y + h.height > H + 2 || p.x < -2 || p.y < -2)) {
                    const n = (h.objectName || "") + "|" + (h.text !== undefined ? String(h.text).slice(0, 30) : "")
                    if (h.text !== undefined || h.objectName)
                        malos.push({obj: n, x: Math.round(p.x), y: Math.round(p.y),
                                    w: Math.round(h.width), h: Math.round(h.height)})
                }
                const nr = h.clip ? {x: p.x, y: p.y, w: h.width, h: h.height} : recorte
                rec(h, nr)
            }
        }
        rec(raiz, null)
        return JSON.stringify(malos.slice(0, 40))
    }
    """

    def ejecutar(nombre):
        global REVISOR
        e = E[nombre]
        engine = QQmlApplicationEngine()
        avisos = []
        engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
        engine.addImportPath(QML_DIR)
        ruta_tmp = None
        props = dict(e.get("props") or {})
        guardar = []
        if e.get("py") == "menu":
            props.update(_menu_py())
        if e.get("py") == "reportes":
            from autoclave.ui_qml import historial_ejemplo as ejemplo
            from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
            from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial
            from autoclave.ui_qml.bridge.reporte_dashboard import ReporteDashboard
            from tests.helpers.reportes_ejemplo import ClienteReportes, HOY
            cli = ClienteReportes(Path(tempfile.mkdtemp())).__enter__()
            guardar.append(cli)
            props.update({"reporteDashboard": ReporteDashboard(cli, ejecutar=lambda t: t(), hoy=lambda: HOY),
                          "historial": CiclosHistorial(cli, ejecutar=lambda t: t(), hoy=lambda: HOY),
                          "acciones": AccionesCiclos(cli, cargar_config=ejemplo.config_correo_ejemplo,
                                                     enviar=ejemplo.enviar_ejemplo, ejecutar=lambda t: t())})
        if e["tipo"] == "qml":
            ruta_tmp = f"{QML_DIR}/_hor_{os.getpid()}.qml"
            open(ruta_tmp, "w", encoding="utf-8").write(envolver(e["cuerpo"], e["extra"]))
            url = ruta_tmp
        else:
            url = f"{QML_DIR}/Pruebas/{e['archivo']}"
        guardar.extend(props.values())
        if props:
            engine.setInitialProperties(props)
        engine.load(QUrl.fromLocalFile(url))
        if ruta_tmp:
            os.remove(ruta_tmp)
        if not engine.rootObjects():
            print("FALLO", nombre, "no cargó", avisos[:5]); return None
        win = engine.rootObjects()[0]
        if tema == "oscuro":
            engine.singletonInstance("Tema", "Colores").setProperty("oscuro", True)
        win.setFlags(win.flags() | Qt.FramelessWindowHint)
        win.setGeometry(0, 0, W, H)
        win.setProperty("width", W); win.setProperty("height", H)
        win.show()
        QTest.qWait(700)
        acc = e.get("accion") or ""
        def tocar(o):
            c = o.mapToScene(QPointF(o.width() / 2, o.height() / 2)).toPoint()
            QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, c)
        if acc.startswith("click:"):
            for o in por_nombre(win, acc[6:]):
                tocar(o); break
            QTest.qWait(900)
        if acc.startswith("obj_click:"):
            for o in por_nombre(win, acc[10:]):
                tocar(o); break
            QTest.qWait(900)
        if acc.startswith("flick_fin:"):
            for o in por_nombre(win, acc[10:]):
                o.setProperty("contentY", max(0, o.property("contentHeight") - o.property("height")))
            QTest.qWait(500)
        if acc in ("teclado_alfa", "teclado_num"):
            for o in por_nombre(win, "tec"):
                if acc == "teclado_alfa":
                    QMetaObject.invokeMethod(o, "abrirAlfanumerico", Q_ARG("QVariant", "Usuario"),
                        Q_ARG("QVariant", ""), Q_ARG("QVariant", 30), Q_ARG("QVariant", False),
                        Q_ARG("QVariant", None), Q_ARG("QVariant", None))
                else:
                    QMetaObject.invokeMethod(o, "abrirNumerico", Q_ARG("QVariant", "Valor"),
                        Q_ARG("QVariant", "°C"), Q_ARG("QVariant", "12"), Q_ARG("QVariant", 0),
                        Q_ARG("QVariant", 100), Q_ARG("QVariant", 1), Q_ARG("QVariant", None),
                        Q_ARG("QVariant", None))
            QTest.qWait(900)
        if acc == "historial_detalle":
            QTest.qWait(600)
            filas = [o for o in todos(win) if o.objectName().startswith("resultado_")]
            if filas:
                tocar(filas[0]); QTest.qWait(900)
        QTest.qWait(400)
        archivo = os.path.join(destino, f"hor_{tema}_{nombre}.png")
        win.grabWindow().save(archivo)
        comp = QQmlComponent(engine)
        comp.setData(("import QtQuick\nQtObject {\n" + FUNCION_REVISAR + FUERA + "\n}\n").encode("utf-8"),
                     QUrl.fromLocalFile(QML_DIR + "/_revisor_hor.qml"))
        rev = comp.create()
        problemas, fuera = [], []
        if rev is not None:
            r = json.loads(QMetaObject.invokeMethod(rev, "revisarDesde", Q_RETURN_ARG("QVariant"),
                                                    Q_ARG("QVariant", win.contentItem())))
            problemas = r["problemas"]
            fuera = json.loads(QMetaObject.invokeMethod(rev, "fueraDelLienzo", Q_RETURN_ARG("QVariant"),
                                                        Q_ARG("QVariant", win.contentItem()),
                                                        Q_ARG("QVariant", W), Q_ARG("QVariant", H)))
        print("captura", nombre, len(problemas), "problemas", len(fuera), "fuera")
        win.close(); engine.deleteLater(); QTest.qWait(50)
        return {"problemas": problemas, "fuera": fuera,
                "avisos": [a for a in avisos if "Binding loop" not in a][:10]}

    resumen = {}
    for n in cfg["escenarios"] or list(E):
        if n not in E:
            print("DESCONOCIDO", n); continue
        try:
            resumen[n] = ejecutar(n)
        except Exception as ex:
            print("FALLO", n, repr(ex)); resumen[n] = {"error": repr(ex)}
    print("RESUMEN=" + json.dumps(resumen, ensure_ascii=False))
''')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--temas", nargs="+", default=["claro", "oscuro"])
    ap.add_argument("--destino", default=str(DESTINO))
    ap.add_argument("--escenarios", nargs="*", default=None)
    ap.add_argument("--tamano", default="1920x1200")
    ap.add_argument("--idioma", default="es")
    # windows (defecto): ventana sin marco en 0,0; dibuja los íconos (MultiEffect),
    # que offscreen no dibuja
    ap.add_argument("--plataforma", default="windows")
    # árbol de fuentes a capturar (p. ej. un worktree de dev para el vertical)
    ap.add_argument("--raiz", default=str(RAIZ_PROPIA))
    a = ap.parse_args()
    ancho, alto = (int(x) for x in a.tamano.split("x"))
    Path(a.destino).mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "QT_ENABLE_HIGHDPI_SCALING": "0", "QT_QPA_PLATFORM": a.plataforma,
           "PYTHONPATH": str(Path(a.raiz) / "src") + os.pathsep + str(RAIZ_PROPIA)}
    for tema in a.temas:
        cfg = {"tema": tema, "destino": a.destino, "ancho": ancho, "alto": alto,
               "escenarios": a.escenarios, "idioma": a.idioma}
        p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg)],
                           capture_output=True, text=True, encoding="utf-8", env=env,
                           cwd=a.raiz, timeout=1800)
        resumen = {}
        for linea in p.stdout.splitlines():
            if linea.startswith("RESUMEN="):
                resumen = json.loads(linea[len("RESUMEN="):])
            else:
                print(linea)
        if p.returncode != 0:
            print(p.stderr[-3000:], file=sys.stderr)
        sufijo = "" if a.escenarios is None else "_parcial"
        (Path(a.destino) / f"resumen_{tema}{sufijo}.json").write_text(
            json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# tests/textos_caben_qml.py
#
# U10a (tanda 10, D10-1.5): revisión GENÉRICA de que los textos visibles caben
# en su cuadro. No es una prueba (pytest no recoge este módulo): la usan
# tests/test_u10a_textos_caben_qml.py y el script de capturas de U10a, y está
# pensada para que U10b la extienda a todas las pantallas agregando casos.
#
# Cómo funciona: cada caso carga una pantalla QML sola, offscreen, en un
# subproceso, con un puente falso (QtObject con las propiedades que se pasen) y
# en el idioma pedido. Luego recorre TODOS los Text visibles y aplica, sin
# conocer la pantalla:
#
#   1. "abreviatura_no_cabe": un TextoAjustable (Componentes/TextoAjustable.qml)
#      con `desborda` = true, es decir, ni el texto abreviado cabe en su
#      `anchoDisponible` (D10-1.1). También se informa cada TextoAjustable en
#      `ajustables` (completo, abreviado, mostrado, anchos) para el informe.
#   2. "desborda_su_caja": un Text sin ajuste de línea, sin elide y sin
#      reducción de fuente cuyo `implicitWidth` supera su propio `width`.
#   3. "sale_del_cuadro": la tinta del texto (contentWidth, según su
#      alineación) se sale por la izquierda o la derecha del Rectangle visible
#      más pequeño que contiene su punto de inicio (el cuadro que lo contiene,
#      aunque en el QML sea hermano y no padre, como en las tarjetas de Preciclo).
#   4. "cruza_divisor": la tinta del texto cruza una línea vertical visible
#      (Rectangle de 4 px o menos de ancho), como los divisores de columna.
#   U10b agrega:
#   5. "recortado": Qt lo recortó (`truncated`: elide o maximumLineCount).
#   6. "encogido": de una línea con `fontSizeMode` distinto de FixedSize y su
#      texto a su tamaño de letra (`implicitWidth`) no cabe en su `width`: Qt
#      lo achica (lo visto en CIC-10 de la tarjeta de alarmas, tanda 9).
#   7. "desborda_alto": con ajuste de línea, sus líneas (`contentHeight`) no
#      caben en el alto que tiene.
#
# Para U10b: agregar casos (pantalla, puente, pasos) en la prueba y, si una
# pantalla necesita datos para mostrar sus textos largos, darlos en `puente`.
# `revisar()` devuelve también `avisos` del motor QML.

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# Resoluciones de las pantallas del equipo: la del banco I4/CAP9 (1024 px de
# ancho, la pantalla real más angosta) y el lienzo de diseño 1200x1920.
RESOLUCIONES = ((1024, 1638), (1200, 1920))

# Función JS de la revisión (la usan el envoltorio de una pantalla sola y, en
# U10b, revisar_main sobre Main.qml completo). Recibe el ítem raíz a recorrer.
FUNCION_REVISAR = r'''
// Los enums (Text.NoWrap...) se leen aquí, en JS, como enteros.
function revisarDesde(raizRevision) {
    const textos = [], cajas = [], lineas = [], ajustables = [], problemas = []
    // U10b: cada ítem lleva el «contexto de recorte» (clip) más cercano; un
    // texto solo se compara con cuadros y divisores de su mismo contexto (las
    // filas de una lista recortada no se mezclan con la barra que tapa su
    // parte oculta).
    let contextos = 0
    function caja(it, ctx) {
        const p = it.mapToItem(null, 0, 0)
        return {x: p.x, y: p.y, w: it.width, h: it.height, ctx: ctx}
    }
    function rec(it, ctx) {
        const hijos = it.children || []
        for (let i = 0; i < hijos.length; ++i) {
            const h = hijos[i]
            if (!h.visible || h.opacity === 0) continue
            const ctxH = h.clip ? ++contextos : ctx
            const esTexto = h.truncated !== undefined && h.elide !== undefined
                            && typeof h.text === "string"
            if (esTexto) {
                if (h.text.trim() !== "") textos.push({t: h, ctx: ctxH})
            } else if (h.radius !== undefined && h.border !== undefined
                       && h.color !== undefined && h.width > 0 && h.height > 0) {
                const visible = h.color.a > 0 || h.border.width > 0
                if (visible) {
                    if (h.width <= 4 && h.height >= 10) lineas.push(caja(h, ctxH))
                    else if (h.width > 4 && h.height > 4) cajas.push(caja(h, ctxH))
                }
            }
            rec(h, ctxH)
        }
    }
    rec(raizRevision, 0)
    for (const tc of textos) {
        const t = tc.t
        const b = caja(t)
        const fijo = t.wrapMode === Text.NoWrap && t.elide === Text.ElideNone
                     && t.fontSizeMode === Text.FixedSize
        const cw = fijo ? t.implicitWidth : Math.min(t.contentWidth, t.width)
        const factor = (t.horizontalAlignment & Qt.AlignHCenter) ? 0.5
                     : (t.horizontalAlignment & Qt.AlignRight) ? 1 : 0
        const izq = b.x + (b.w - cw) * factor
        const der = izq + cw
        const yc = b.y + b.h / 2
        const desc = {texto: t.text, obj: t.objectName, x: Math.round(izq),
                      ancho: Math.round(cw)}
        if (t.anchoDisponible !== undefined && t.desborda !== undefined) {
            ajustables.push({completo: t.textoCompleto, abreviado: t.textoAbreviado,
                             mostrado: t.text, usaAbreviado: t.usaAbreviado,
                             anchoDisponible: Math.round(t.anchoDisponible * 10) / 10,
                             anchoCompleto: Math.round(t.anchoCompleto * 10) / 10,
                             implicito: Math.round(t.implicitWidth * 10) / 10})
            if (t.desborda || t.implicitWidth > t.anchoDisponible + 0.5)
                problemas.push(Object.assign({tipo: "abreviatura_no_cabe",
                                              disponible: Math.round(t.anchoDisponible)}, desc))
        }
        if (fijo && t.width > 0 && t.implicitWidth > t.width + 1)
            problemas.push(Object.assign({tipo: "desborda_su_caja",
                                          caja: Math.round(t.width)}, desc))
        // U10b: recortado por Qt (elide o maximumLineCount)
        if (t.truncated)
            problemas.push(Object.assign({tipo: "recortado"}, desc))
        // U10b: achicado por fontSizeMode para caber (el texto completo
        // a su tamaño de letra no cabe en su caja)
        if (t.fontSizeMode !== Text.FixedSize && t.width > 0
                && t.wrapMode === Text.NoWrap && t.implicitWidth > t.width + 1)
            problemas.push(Object.assign({tipo: "encogido",
                                          caja: Math.round(t.width),
                                          natural: Math.round(t.implicitWidth)}, desc))
        // U10b: con ajuste de línea, las líneas no caben en el alto fijado
        if (t.wrapMode !== Text.NoWrap && t.height > 0
                && t.contentHeight > t.height + 2)
            problemas.push(Object.assign({tipo: "desborda_alto",
                                          alto: Math.round(t.height),
                                          contenido: Math.round(t.contentHeight)}, desc))
        let menor = null
        for (const c of cajas) {
            if (c.ctx === tc.ctx && izq + 0.5 >= c.x && izq < c.x + c.w && yc >= c.y && yc <= c.y + c.h
                    && (!menor || c.w * c.h < menor.w * menor.h))
                menor = c
        }
        if (menor && (der > menor.x + menor.w + 1 || izq < menor.x - 1))
            problemas.push(Object.assign({tipo: "sale_del_cuadro",
                                          cuadro: [Math.round(menor.x), Math.round(menor.w)]}, desc))
        for (const l of lineas) {
            const lx = l.x + l.w / 2
            if (l.ctx === tc.ctx && lx > izq + 1 && lx < der - 1 && b.y < l.y + l.h && b.y + b.h > l.y) {
                problemas.push(Object.assign({tipo: "cruza_divisor", divisor: Math.round(lx)}, desc))
                break
            }
        }
    }
    return JSON.stringify({problemas: problemas, ajustables: ajustables,
                           vistos: textos.map(tc => tc.t.text)})
}
'''

_SCRIPT = textwrap.dedent(r'''
    import json, os, sys
    from PySide6.QtCore import QObject, QUrl, QMetaObject, Q_RETURN_ARG
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow  # noqa: F401  (grabWindow en la raíz)
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge import i18n_qml

    cfg = json.loads(sys.argv[1])
    i18n.cargar()
    i18n.fijar_idioma(cfg["idioma"])
    i18n_qml.instancia._consultar = lambda: None        # sin backend: no cambia el idioma

    # U10b: doble de la sesión HTTP (como tests/i4_truncado_banco.py) para las
    # pantallas que consultan al servicio al cargarse (Opciones y sus secciones).
    if cfg.get("sesion"):
        from autoclave.ui_qml import sesion_backend
        from autoclave.cliente.session_manager import SessionManager

        class Sesion:
            sinConexion = False
            def enviar(self, metodo, ruta, cuerpo=None):
                return sesion_backend.Resultado("ok", {}, 200)
            def __getattr__(self, n):
                return lambda *a, **k: sesion_backend.Resultado("ok", {}, 200)

        sesion_backend.ventana = lambda: Sesion()
        SessionManager.login({"usuario": "ingeniero", "nombre": "Ingeniero", "rol": cfg["sesion"],
                              "debe_cambiar_clave": False}, token="t")

    def _qml_valor(v):
        return json.dumps(v, ensure_ascii=False)

    def _tipo(v):
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, (int, float)):
            return "real"
        if isinstance(v, str):
            return "string"
        return "var"

    props = "\n".join(f"property {_tipo(v)} {k}: {_qml_valor(v)}"
                      for k, v in (cfg.get("puente") or {}).items())
    usa_puente = cfg.get("puente") is not None
    QML = """
    import QtQuick
    import Tema
    import "Pantallas"
    Window {
        id: ventana
        width: %d; height: %d; visible: true
        Binding { target: Escala; property: "factor"; value: %f }
        QtObject { id: puenteFalso; objectName: "puente"
            %s
        }
        %s { id: pantalla; objectName: "pantalla"; anchors.fill: parent %s }

        // U10b: la revisión vive en FUNCION_REVISAR (la comparte revisar_main)
        %s
        function revisar() { return revisarDesde(contentItem) }
    }
    """ % (cfg["ancho"], cfg["alto"], cfg["ancho"] / 1200.0, props, cfg["pantalla"],
           "; puente: puenteFalso" if usa_puente else "", cfg["funcion"])
    ruta = f"{QML_DIR}/_prueba_textos_caben_{os.getpid()}.qml"
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
        os.remove(ruta)
    assert engine.rootObjects(), avisos
    w = engine.rootObjects()[0]
    w.show()
    QTest.qWait(500)
    pasos = []
    for paso in cfg.get("pasos") or [{}]:
        puente = w.findChild(QObject, "puente")
        for k, v in (paso.get("puente") or {}).items():
            puente.setProperty(k, v)
        QTest.qWait(250)
        r = json.loads(QMetaObject.invokeMethod(w, "revisar", Q_RETURN_ARG("QVariant")))
        if paso.get("captura"):
            w.grabWindow().save(paso["captura"])
        pasos.append(r)
    print("RESULTADO=" + json.dumps({"pasos": pasos, "avisos": avisos[:30]}, ensure_ascii=False))
''')


def revisar(pantalla: str, idioma: str, ancho: int = 1024, alto: int = 1638,
            puente: dict | None = None, pasos: list | None = None,
            sesion: str | None = None) -> dict:
    """Carga `pantalla` y revisa sus textos en cada paso.

    `puente`: propiedades iniciales del puente falso (None = la pantalla sin puente).
    `pasos`: lista de {"puente": {prop: valor}, "captura": ruta_png}; cada paso
    cambia esas propiedades, revisa y (si se pide) guarda una captura.
    `sesion`: rol (p. ej. "ingeniero") para iniciar sesión con un doble de la
    sesión HTTP que responde 200 {} (U10b; None = sin doble, como en U10a).
    Devuelve {"pasos": [{"problemas", "ajustables", "vistos"}...], "avisos"}.
    """
    cfg = {"pantalla": pantalla, "idioma": idioma, "ancho": ancho, "alto": alto,
           "puente": puente, "pasos": pasos, "sesion": sesion, "funcion": FUNCION_REVISAR}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ,
                       timeout=180)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, pantalla + "\n" + p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


# ── U10b: Main.qml completo, con UiBridge sobre un backend simulado ─────────
#
# Para los textos que solo aparecen con datos del servicio (tarjeta de alarmas
# de Preciclo, panel de la campana): mismo andamiaje que la parte «preciclo»
# de tests/cap9_capturas_banco.py (UiBridge real sobre un UIServiceBackend
# simulado, alarmas armadas con el catálogo real igual que server._alarma_dto).
#
# Cada paso de `pasos` es un dict con, opcionalmente:
#   "alarmas": [[codigo, {valores}], ...]   alarmas activas (DTO de /status)
#   "campos": {clave: valor}                 campos de /status (estado_seguro...)
#   "pres_camara": valor | None              lectura de presión de cámara
#   "campana": True | False                  abre / cierra el panel de la campana
#   "captura": ruta_png
# El primer paso toca Reposo para pasar a Preciclo.

_SCRIPT_MAIN = textwrap.dedent(r'''
    import json, os, sys
    from unittest.mock import MagicMock
    from PySide6.QtCore import QMetaObject, QObject, QUrl, Q_ARG, Q_RETURN_ARG
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.core.runtime import alarmas_i18n
    from autoclave.state_machine.alarms.catalogo import CATALOGO
    from autoclave.cliente.ui_service_backend import UIServiceBackend
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge import i18n_qml
    from autoclave.ui_qml.bridge.ui_bridge import UiBridge
    from autoclave.ui_qml.controllers import teclado_alfanumerico_controller  # noqa: F401
    from autoclave.ui_qml import sesion_backend
    from autoclave.ui_pyside.views.nuevo_usuario.puente import NuevoUsuarioBridge

    cfg = json.loads(sys.argv[1])
    i18n.cargar()
    i18n.fijar_idioma(cfg["idioma"])
    i18n_qml.instancia._consultar = lambda: None

    def transporte(metodo, ruta, cuerpo, token, plazo):
        return 200, {"ok": True}

    qapp = QGuiApplication([])
    _cargar_fuentes()
    sesion = sesion_backend.SesionVentana(transporte=transporte, ejecutar=lambda t: t(),
                                          cierre_s=0.8, intervalo_ms=50)
    sesion_backend.instalar(sesion)
    puente_nu = NuevoUsuarioBridge(sesion=sesion)

    def alarma(codigo, valores):
        d = CATALOGO[codigo]
        return {"id": codigo, "level": d.nivel.nombre_compat,
                "description": d.renderizar(valores), "source_state": "PREPARACION",
                "textos": alarmas_i18n.por_idioma(d, valores)}

    flags = {"LISTO_PARA_CICLO": False, "PARO_EMERGENCIA": False, "PARO_REAL": False}
    campos = {"estado_tarjeta": "ok", "no_abrir": False, "estado_seguro": {}}
    alarmas = []
    pres = {"pres_camara": 101.3}
    ui = MagicMock(spec=UIServiceBackend)
    ui.connected = True
    ui.get_estado_global.return_value = "PREPARACION"
    ui.get_estado_puerta.return_value = "CERRADO"
    ui.get_alarmas.side_effect = lambda: list(alarmas)
    ui.get_estado_flag.side_effect = lambda f: flags.get(f, False)
    ui.get_campo.side_effect = lambda k, d=None: campos.get(k, d)
    ui.get_cycle.return_value = {"name": "Instrumental 134", "number": 2}
    ui.get_sensores_temp.return_value = {"temp_camara": 62.4}
    ui.get_sensores_pres.side_effect = lambda: dict(pres)
    puente = UiBridge(ui, door=1, iniciar=False)
    puente.refrescar()

    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties({"puente": puente, "sesion": sesion, "puenteNuevoUsuario": puente_nu})
    engine.load(QUrl.fromLocalFile(QML_DIR + "/Main.qml"))
    ventana = engine.rootObjects()[0]
    ventana.setProperty("width", cfg["ancho"])
    ventana.setProperty("height", cfg["alto"])
    ventana.show()

    revisor_c = QQmlComponent(engine)
    revisor_c.setData(("import QtQuick\nQtObject {\n" + cfg["funcion"] + "\n}\n").encode("utf-8"),
                      QUrl.fromLocalFile(QML_DIR + "/_revisor_textos.qml"))
    revisor = revisor_c.create()
    assert revisor is not None, revisor_c.errorString()

    def buscar(tipo):
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith(tipo + "_QML")]

    QTest.qWait(700)
    QMetaObject.invokeMethod(buscar("Reposo")[0], "tocado")
    QTest.qWait(700)
    pasos = []
    for paso in cfg["pasos"]:
        if "alarmas" in paso:
            alarmas[:] = [alarma(c, v) for c, v in paso["alarmas"]]
        if "campos" in paso:
            campos.update(paso["campos"])
        if "pres_camara" in paso:
            pres["pres_camara"] = paso["pres_camara"]
        puente.refrescar()
        QTest.qWait(400)
        raiz_revision = ventana.contentItem()
        if "campana" in paso:
            # el panel abierto tapa la pantalla: se revisa solo el panel, con
            # sus tres grupos desplegados
            for pre in buscar("PantallaPreciclo"):
                if not pre.property("visible"):
                    continue
                for panel in pre.findChildren(QObject):
                    if panel.metaObject().className().startswith("PanelNotificaciones_QML"):
                        QMetaObject.invokeMethod(panel, "abrir" if paso["campana"] else "cerrar")
                        for nombre in ("grupoEmergencia", "grupoAlarmas", "grupoAvisos"):
                            g = panel.findChild(QObject, nombre)
                            if g is not None:
                                g.setProperty("expandido", bool(paso["campana"]))
                        if paso["campana"]:
                            raiz_revision = panel
            QTest.qWait(600)
        r = json.loads(QMetaObject.invokeMethod(revisor, "revisarDesde", Q_RETURN_ARG("QVariant"),
                                                Q_ARG("QVariant", raiz_revision)))
        r["filas_alarma"] = [f["description"] for f in puente.alarms.filas()]
        if paso.get("captura"):
            QTest.qWait(200)
            ventana.grabWindow().save(paso["captura"])
        pasos.append(r)
    print("RESULTADO=" + json.dumps({"pasos": pasos,
                                     "avisos": [a for a in avisos if "Binding loop" not in a][:30]},
                                    ensure_ascii=False))
''')


def revisar_main(idioma: str, ancho: int = 1024, alto: int = 1638, pasos: list | None = None) -> dict:
    """Main.qml completo en Preciclo, con alarmas reales del catálogo (ver arriba)."""
    cfg = {"idioma": idioma, "ancho": ancho, "alto": alto, "pasos": pasos or [{}],
           "funcion": FUNCION_REVISAR}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT_MAIN, json.dumps(cfg, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ,
                       timeout=240)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, "Main\n" + p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])


# ── U10b: Menú Principal con datos de ejemplo y sus ventanas flotantes ─────
#
# Arnés del Menú (qml/Pruebas/PruebaMenuPrincipal.qml) con los datos de
# ejemplo de ui_qml/historial_ejemplo.py (los mismos de
# `prueba_menu_principal.py --pantalla`): resumen, Ciclos hoy, Historial,
# Reportes, último ciclo, mantenimiento, panel del equipo y campana. Cada
# elemento de `ventanas` se abre, se revisa SOLO esa ventana (tapa al menú) y
# se cierra; "" revisa el menú sin ventanas.

_SCRIPT_MENU = textwrap.dedent(r'''
    import json, os, sys
    from PySide6.QtCore import QMetaObject, QObject, QUrl, Q_ARG, Q_RETURN_ARG
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
    from PySide6.QtQuick import QQuickWindow  # noqa: F401
    from PySide6.QtTest import QTest
    from autoclave import i18n
    from autoclave.ui_qml import app as _app  # noqa: F401
    from autoclave.ui_qml.app import QML_DIR, _cargar_fuentes
    from autoclave.ui_qml.bridge import i18n_qml
    from autoclave.ui_qml import historial_ejemplo as ejemplo
    from autoclave.ui_qml.bridge.acciones_ciclos import AccionesCiclos
    from autoclave.ui_qml.bridge.ciclos_historial import CiclosHistorial
    from autoclave.ui_qml.bridge.reporte_resumen import ReporteResumen

    cfg = json.loads(sys.argv[1])
    i18n.cargar()
    i18n.fijar_idioma(cfg["idioma"])
    i18n_qml.instancia._consultar = lambda: None

    qapp = QGuiApplication([])
    _cargar_fuentes()
    from datetime import date
    hoy = lambda: date(2026, 10, 22)      # día con 3 ciclos de ejemplo (uno con fallo)
    backend = ejemplo.BackendEjemplo(sin_conexion=False, hoy=hoy)
    historial = CiclosHistorial(backend, ejecutar=lambda t: t(), hoy=hoy)
    props = {"historial": historial,
             "acciones": AccionesCiclos(backend, cargar_config=ejemplo.config_correo_ejemplo,
                                        enviar=ejemplo.enviar_ejemplo, ejecutar=lambda t: t()),
             "reporte": ReporteResumen(backend, ejecutar=lambda t: t(), hoy=hoy)}
    avisos = []
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: avisos.extend(w.toString() for w in ws))
    engine.addImportPath(QML_DIR)
    engine.setInitialProperties(props)
    engine.load(QUrl.fromLocalFile(QML_DIR + "/Pruebas/PruebaMenuPrincipal.qml"))
    ventana = engine.rootObjects()[0]
    ventana.setProperty("width", cfg["ancho"])
    ventana.setProperty("height", cfg["alto"])
    ventana.show()
    revisor_c = QQmlComponent(engine)
    revisor_c.setData(("import QtQuick\nQtObject {\n" + cfg["funcion"] + "\n}\n").encode("utf-8"),
                      QUrl.fromLocalFile(QML_DIR + "/_revisor_textos.qml"))
    revisor = revisor_c.create()
    assert revisor is not None, revisor_c.errorString()
    QTest.qWait(800)

    def buscar_tipo(tipo):
        return [o for o in ventana.findChildren(QObject)
                if o.metaObject().className().startswith(tipo + "_QML")]

    pasos = []
    for nombre in cfg["ventanas"]:
        raiz_revision = ventana.contentItem()
        abierta = None
        if nombre:
            # "<ventana>:detalle" abre además el detalle del último ciclo listado;
            # "ventanaReportes:consolidado", la pestaña Consolidado
            base, _, detalle = nombre.partition(":")
            abierta = ventana.findChild(QObject, base)
            QMetaObject.invokeMethod(abierta, "abrir")
            QTest.qWait(900)
            if detalle == "consolidado":     # pestaña Consolidado de Reportes
                abierta.setProperty("pestana", "consolidado")
                QTest.qWait(600)
            elif detalle:
                ciclos = historial.property("ciclos") or []
                if ciclos:
                    abierta.setProperty("seleccion", ciclos[-1])
                    historial.cargarGrafica(ciclos[-1]["id"])
                    QTest.qWait(600)
            raiz_revision = abierta
        r = json.loads(QMetaObject.invokeMethod(revisor, "revisarDesde", Q_RETURN_ARG("QVariant"),
                                                Q_ARG("QVariant", raiz_revision)))
        r["ventana"] = nombre
        if cfg.get("capturas"):
            ventana.grabWindow().save(os.path.join(cfg["capturas"],
                                                   f"{cfg['prefijo']}_{cfg['idioma']}_menu_{(nombre or 'base').replace(':', '_')}.png"))
        if abierta is not None:
            QMetaObject.invokeMethod(abierta, "cerrar")
            QTest.qWait(300)
        pasos.append(r)
    print("RESULTADO=" + json.dumps({"pasos": pasos,
                                     "avisos": [a for a in avisos if "Binding loop" not in a][:30]},
                                    ensure_ascii=False))
''')

VENTANAS_MENU = ("", "ventanaUltimoCiclo", "ventanaMantenimiento", "ventanaCiclosHoy",
                 "ventanaCiclosHoy:detalle", "ventanaHistorial", "ventanaHistorial:detalle",
                 "ventanaReportes", "ventanaReportes:consolidado", "panelEquipoMenu",
                 "panelNotificacionesMenu")


def revisar_menu(idioma: str, ancho: int = 1024, alto: int = 1638, ventanas=VENTANAS_MENU,
                 capturas: str | None = None, prefijo: str = "U10b") -> dict:
    """Menú Principal con datos de ejemplo; revisa el menú y cada ventana flotante."""
    cfg = {"idioma": idioma, "ancho": ancho, "alto": alto, "ventanas": list(ventanas),
           "funcion": FUNCION_REVISAR, "capturas": capturas, "prefijo": prefijo}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT_MENU, json.dumps(cfg, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ,
                       timeout=240)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, "Menu\n" + p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])

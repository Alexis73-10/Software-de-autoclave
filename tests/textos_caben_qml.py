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

        // Los enums (Text.NoWrap...) se leen aquí, en JS, como enteros.
        function revisar() {
            const textos = [], cajas = [], lineas = [], ajustables = [], problemas = []
            function caja(it) {
                const p = it.mapToItem(null, 0, 0)
                return {x: p.x, y: p.y, w: it.width, h: it.height}
            }
            function rec(it) {
                const hijos = it.children || []
                for (let i = 0; i < hijos.length; ++i) {
                    const h = hijos[i]
                    if (!h.visible || h.opacity === 0) continue
                    const esTexto = h.truncated !== undefined && h.elide !== undefined
                                    && typeof h.text === "string"
                    if (esTexto) {
                        if (h.text.trim() !== "") textos.push(h)
                    } else if (h.radius !== undefined && h.border !== undefined
                               && h.color !== undefined && h.width > 0 && h.height > 0) {
                        const visible = h.color.a > 0 || h.border.width > 0
                        if (visible) {
                            if (h.width <= 4 && h.height >= 10) lineas.push(caja(h))
                            else if (h.width > 4 && h.height > 4) cajas.push(caja(h))
                        }
                    }
                    rec(h)
                }
            }
            rec(contentItem)
            for (const t of textos) {
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
                let menor = null
                for (const c of cajas) {
                    if (izq + 0.5 >= c.x && izq < c.x + c.w && yc >= c.y && yc <= c.y + c.h
                            && (!menor || c.w * c.h < menor.w * menor.h))
                        menor = c
                }
                if (menor && (der > menor.x + menor.w + 1 || izq < menor.x - 1))
                    problemas.push(Object.assign({tipo: "sale_del_cuadro",
                                                  cuadro: [Math.round(menor.x), Math.round(menor.w)]}, desc))
                for (const l of lineas) {
                    const lx = l.x + l.w / 2
                    if (lx > izq + 1 && lx < der - 1 && b.y < l.y + l.h && b.y + b.h > l.y) {
                        problemas.push(Object.assign({tipo: "cruza_divisor", divisor: Math.round(lx)}, desc))
                        break
                    }
                }
            }
            return JSON.stringify({problemas: problemas, ajustables: ajustables,
                                   vistos: textos.map(t => t.text)})
        }
    }
    """ % (cfg["ancho"], cfg["alto"], cfg["ancho"] / 1200.0, props, cfg["pantalla"],
           "; puente: puenteFalso" if usa_puente else "")
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
            puente: dict | None = None, pasos: list | None = None) -> dict:
    """Carga `pantalla` y revisa sus textos en cada paso.

    `puente`: propiedades iniciales del puente falso (None = la pantalla sin puente).
    `pasos`: lista de {"puente": {prop: valor}, "captura": ruta_png}; cada paso
    cambia esas propiedades, revisa y (si se pide) guarda una captura.
    Devuelve {"pasos": [{"problemas", "ajustables", "vistos"}...], "avisos"}.
    """
    cfg = {"pantalla": pantalla, "idioma": idioma, "ancho": ancho, "alto": alto,
           "puente": puente, "pasos": pasos}
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
           "PYTHONPATH": str(RAIZ / "src") + os.pathsep + str(RAIZ)}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _SCRIPT, json.dumps(cfg, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ,
                       timeout=180)
    linea = next((l for l in p.stdout.splitlines() if l.startswith("RESULTADO=")), None)
    assert linea, pantalla + "\n" + p.stdout[-2000:] + p.stderr[-3000:]
    return json.loads(linea[len("RESULTADO="):])

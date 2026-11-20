# tests/helpers/solapes_qml.py
#
# Revisión visual (RV, etapa A): detector automático de elementos que se
# solapan. No es una prueba (pytest no recoge este módulo): lo usan
# tests/banco/hor_capturas.py (y por él resumen_<tema>.json) y
# tests/test_rv_solapes_qml.py.
#
# FUNCION_SOLAPES define en JS `solapesDesde(raiz, W, H, animados)`, que
# recorre los ítems visibles (visible y opacidad efectiva > 0, dentro de la
# ventana) en orden de pintado (preorden, hermanos por z) y reporta el tipo
# «solape»: dos elementos con contenido cuyos rectángulos visibles, en
# coordenadas de la ventana, se intersectan más de UMBRAL px en ambos ejes.
#
# Contenido:
#   - Text con texto no vacío (rectángulo = tinta, contentWidth x
#     contentHeight según su alineación, acotada a su caja, sin el
#     interlineado: cada línea cuenta como su tamaño de letra);
#   - Image con fuente (rectángulo pintado, paintedWidth x paintedHeight
#     centrado) e IconoColor (Item con `source` y `color`, sin `radius`);
#   - controles: ítems con `pressed` (MouseArea, botones) habilitados, con
#     objectName o MouseArea; un control que cubre más de la mitad de la
#     ventana es un fondo que captura toques y no cuenta.
# Los Rectangle no son contenido (un texto sobre su propio fondo no cuenta).
#
# No es solape:
#   - un par en el que uno es ancestro del otro, o en el que uno está dentro de
#     la «unidad» del otro (la unidad de un control es su padre: el texto de un
#     botón y su MouseArea hermana; la fila de una lista y su botón);
#   - lo que queda fuera de su clip (cada rectángulo se recorta con el clip de
#     sus ancestros antes de intersectar);
#   - lo que está dentro de un componente animado (`animados`, nombres de tipo
#     QML: DeslizadorInicio, CirculoFaseLiquido), cuya posición depende del
#     instante;
#   - dos controles entre sí (zonas táctiles invisibles, ampliadas a propósito);
#   - una insignia (`insignias`: InsigniaCampana) sobre un ícono;
#   - una imagen de fondo (más de la mitad de la ventana);
#   - lo que queda debajo de una capa que lo cubre a propósito (modal, panel,
#     teclado): un Rectangle opaco (alfa >= 0,3) de al menos COBERTURA_MIN del
#     área de la ventana, pintado después del elemento y que no es su
#     ancestro, que contiene el centro de su rectángulo visible. Cuenta solo la
#     capa superior. Un rectángulo pequeño (un botón) no tapa: así un texto
#     debajo de un botón sigue saliendo como solape con la etiqueta del botón.
#
# Cada problema: {tipo: "solape", a: {...}, b: {...}, area} con clase,
# objectName, texto (40 caracteres) y rectángulo [x, y, w, h] de cada elemento.

UMBRAL = 4
COBERTURA_MIN = 0.15
ANIMADOS = ("DeslizadorInicio", "CirculoFaseLiquido")
# superposiciones de diseño sobre un ícono (la insignia sobre la campana)
INSIGNIAS = ("InsigniaCampana",)

FUNCION_SOLAPES = r'''
function solapesDesde(raiz, W, H, animados, insignias) {
    const UMBRAL = %(umbral)s, COBERTURA = %(cobertura)s
    const anim = animados || []
    const insig = insignias || []
    const elementos = [], capas = []
    let orden = 0
    function clase(it) { return String(it).split("(")[0].split("_QML")[0] }
    function inter(a, b) {
        if (!a || !b) return null
        const x = Math.max(a.x, b.x), y = Math.max(a.y, b.y)
        const x2 = Math.min(a.x + a.w, b.x + b.w), y2 = Math.min(a.y + a.h, b.y + b.h)
        return (x2 > x && y2 > y) ? {x: x, y: y, w: x2 - x, h: y2 - y} : null
    }
    function rectDe(it) { const p = it.mapToItem(null, 0, 0); return {x: p.x, y: p.y, w: it.width, h: it.height} }
    function esTexto(h) { return h.truncated !== undefined && h.elide !== undefined && typeof h.text === "string" }
    function esImagen(h) {
        if (h.source === undefined || h.radius !== undefined) return false
        const s = String(h.source)
        if (s === "" ) return false
        return h.fillMode !== undefined || h.color !== undefined
    }
    function esRect(h) { return h.radius !== undefined && h.border !== undefined && h.color !== undefined }
    function esControl(h) {
        if (h.pressed === undefined || h.enabled === false) return false
        const ma = h.acceptedButtons !== undefined
        return ma || (h.objectName || "") !== ""
    }
    function rectTexto(h, b) {
        const cw = Math.min(h.contentWidth, h.width > 0 ? h.width : h.contentWidth)
        let ch = h.height > 0 ? Math.min(h.contentHeight, h.height) : h.contentHeight
        // interlineado: la tinta ocupa ~el tamaño de letra de cada línea, no
        // la altura de línea completa (la hora grande sobre la fecha)
        const px = h.font && h.font.pixelSize > 0 ? h.font.pixelSize
                 : (h.font && h.font.pointSize > 0 ? h.font.pointSize * 4 / 3 : 0)
        const nl = Math.max(1, h.lineCount || 1)
        const recorte = px > 0 ? Math.max(0, (ch / nl - px) / 2) : 0
        const fx = (h.horizontalAlignment & Qt.AlignHCenter) ? 0.5 : (h.horizontalAlignment & Qt.AlignRight) ? 1 : 0
        const fy = (h.verticalAlignment & Qt.AlignVCenter) ? 0.5 : (h.verticalAlignment & Qt.AlignBottom) ? 1 : 0
        return {x: b.x + (b.w - cw) * fx, y: b.y + (h.height > 0 ? (b.h - ch) * fy : 0) + recorte,
                w: cw, h: Math.max(1, ch - 2 * recorte)}
    }
    function rectImagen(h, b) {
        if (h.paintedWidth !== undefined && h.paintedWidth > 0) {
            const pw = Math.min(h.paintedWidth, b.w), ph = Math.min(h.paintedHeight, b.h)
            return {x: b.x + (b.w - pw) / 2, y: b.y + (b.h - ph) / 2, w: pw, h: ph}
        }
        return b
    }
    const ventana = {x: 0, y: 0, w: W, h: H}
    // recorre en orden de pintado; `ancestros` es la cadena de ítems hasta el
    // padre; `recorte` el clip acumulado; `enAnim` si está dentro de un animado
    function rec(it, ancestros, recorte, opac, enAnim, enInsig) {
        const hijos = (it.children || []).slice()
        hijos.sort(function (a, b) { return (a.z || 0) - (b.z || 0) })
        for (let i = 0; i < hijos.length; ++i) {
            const h = hijos[i]
            const op = opac * (h.opacity === undefined ? 1 : h.opacity)
            if (!h.visible || op <= 0.01) continue
            const b = rectDe(h)
            const a = enAnim || anim.indexOf(clase(h)) >= 0
            const ins = enInsig || insig.indexOf(clase(h)) >= 0
            const cad = ancestros.concat([h])
            const idx = orden++
            if (!a && h.width > 0 && h.height > 0) {
                let r = null, tipo = ""
                if (esTexto(h) && h.text.trim() !== "") { r = rectTexto(h, b); tipo = "texto" }
                else if (esImagen(h)) {
                    // una imagen de fondo (más de la mitad de la ventana) no cuenta
                    const ri = rectImagen(h, b)
                    if (ri.w * ri.h <= 0.5 * W * H) { r = ri; tipo = "imagen" }
                }
                else if (esControl(h)) {
                    if (b.w * b.h <= 0.5 * W * H) { r = b; tipo = "control" }
                }
                if (r) {
                    const vis = inter(inter(r, recorte || ventana), ventana)
                    if (vis)
                        elementos.push({it: h, cad: cad, orden: idx, vis: vis, tipo: tipo, insignia: ins,
                                        unidad: tipo === "control" ? (h.parent || h) : h,
                                        clase: clase(h), obj: h.objectName || "",
                                        texto: typeof h.text === "string" ? h.text.slice(0, 40) : ""})
                }
                if (esRect(h) && h.color.a >= 0.3 && b.w * b.h >= COBERTURA * W * H) {
                    const vr = inter(b, recorte || ventana)
                    if (vr) capas.push({it: h, orden: idx, vis: vr})
                }
            }
            // un IconoColor no se recorre por dentro (su Image es la máscara)
            if (esImagen(h) && h.fillMode === undefined) continue
            const nr = h.clip ? inter(b, recorte || ventana) : recorte
            if (h.clip && !nr) continue
            rec(h, cad, nr, op, a, ins)
        }
    }
    rec(raiz, [raiz], null, 1, false, false)
    function cubierto(e) {
        const cx = e.vis.x + e.vis.w / 2, cy = e.vis.y + e.vis.h / 2
        for (const c of capas) {
            if (c.orden <= e.orden) continue
            if (e.cad.indexOf(c.it) >= 0) continue
            if (cx >= c.vis.x && cx <= c.vis.x + c.vis.w && cy >= c.vis.y && cy <= c.vis.y + c.vis.h)
                return true
        }
        return false
    }
    const vivos = elementos.filter(function (e) { return !cubierto(e) })
    function contiene(e, x) { return x.cad.indexOf(e) >= 0 }
    const malos = []
    function desc(e) {
        return {clase: e.clase, obj: e.obj, texto: e.texto, tipo: e.tipo,
                rect: [Math.round(e.vis.x), Math.round(e.vis.y), Math.round(e.vis.w), Math.round(e.vis.h)]}
    }
    for (let i = 0; i < vivos.length; ++i) {
        for (let j = i + 1; j < vivos.length; ++j) {
            const p = vivos[i], q = vivos[j]
            if (contiene(p.it, q) || contiene(q.it, p)) continue
            if (contiene(p.unidad, q) || contiene(q.unidad, p)) continue
            if ((p.insignia && q.tipo === "imagen") || (q.insignia && p.tipo === "imagen")) continue
            // dos zonas táctiles (invisibles, a veces ampliadas con márgenes negativos
            // por Escala.margenTactil) no son un solape visual
            if (p.tipo === "control" && q.tipo === "control") continue
            const s = inter(p.vis, q.vis)
            if (!s || s.w <= UMBRAL || s.h <= UMBRAL) continue
            malos.push({tipo: "solape", a: desc(p), b: desc(q), area: Math.round(s.w * s.h),
                        zona: [Math.round(s.x), Math.round(s.y), Math.round(s.w), Math.round(s.h)]})
            if (malos.length >= 80) return JSON.stringify(malos)
        }
    }
    return JSON.stringify(malos)
}
''' % {"umbral": UMBRAL, "cobertura": COBERTURA_MIN}


# Ejecutor para las pruebas: carga `qml` (un Window completo) offscreen en un
# subproceso y devuelve la lista de solapes.
_GUION = r'''
import json, sys
from PySide6.QtCore import QUrl, QMetaObject, Q_ARG, Q_RETURN_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtTest import QTest
from PySide6.QtQuick import QQuickWindow  # noqa: F401
sys.path.insert(0, sys.argv[3])
from tests.helpers.solapes_qml import FUNCION_SOLAPES, ANIMADOS, INSIGNIAS
app = QGuiApplication([])
eng = QQmlApplicationEngine()
eng.loadData(sys.argv[1].encode("utf-8"), QUrl.fromLocalFile(sys.argv[2] + "/_rv.qml"))
win = eng.rootObjects()[0]
win.show(); QTest.qWait(200)
comp = QQmlComponent(eng)
comp.setData(("import QtQuick\nQtObject {\n" + FUNCION_SOLAPES + "\n}\n").encode("utf-8"),
             QUrl.fromLocalFile(sys.argv[2] + "/_rv_rev.qml"))
rev = comp.create()
r = QMetaObject.invokeMethod(rev, "solapesDesde", Q_RETURN_ARG("QVariant"),
                             Q_ARG("QVariant", win.contentItem()), Q_ARG("QVariant", win.width()),
                             Q_ARG("QVariant", win.height()), Q_ARG("QVariant", list(ANIMADOS)),
                             Q_ARG("QVariant", list(INSIGNIAS)))
print("SOLAPES=" + r)
'''


def revisar_qml(qml: str, carpeta: str) -> list:
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path
    raiz = str(Path(__file__).resolve().parents[2])
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", _GUION, qml, carpeta, raiz],
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    for linea in p.stdout.splitlines():
        if linea.startswith("SOLAPES="):
            return json.loads(linea[len("SOLAPES="):])
    raise RuntimeError(p.stderr[-2000:])

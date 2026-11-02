import QtQuick
import QtQuick.Shapes
import Tema

// Grafica de ciclos por intervalo del dashboard de reportes (REP-05). Solo dibujo.
// `serie` = presentable()['serie']: {vacia, puntos:[{x, y_total, y_completados, con_fallo,
// total, completados, fallos, etiqueta, rotulo}], eje_y:{max, paso, marcas:[{valor, y}]},
// eje_x:[{x, texto}], color_total, color_completados, color_fallo} (x e y en 0..1; los
// colores son CLAVES de Tema/Colores). Curva de area (total) y linea (completados)
// suavizadas (Catmull-Rom -> Bezier con puntos de control acotados al area).
// Al tocar un punto/intervalo se muestra una burbuja con rotulo, total y fallos que se cierra a los 5 s.
// Los rotulos de la burbuja (`rotuloTotal`, `rotuloFallos`) y `textoVacio` llegan como propiedades.
// Medidas en px del mockup escaladas con `escala` (convencion m(), D-18).
Item {
    id: raiz
    objectName: "graficaArea"

    property real escala: 1
    property var serie: ({ vacia: true, puntos: [], eje_y: { max: 4, paso: 1, marcas: [] }, eje_x: [] })
    property string rotuloTotal: ""
    property string rotuloFallos: ""
    property string textoVacio: ""
    // tiempo que la burbuja permanece abierta
    property int duracionBurbujaMs: 5000
    // indice del punto elegido (-1 = ninguno)
    property int seleccion: -1

    signal puntoElegido(int indice)

    readonly property var _s: (serie && typeof serie === "object") ? serie : ({})
    readonly property var puntos: secuencia(_s.puntos)
    readonly property var marcasY: _s.eje_y ? secuencia(_s.eje_y.marcas) : []
    readonly property var marcasX: secuencia(_s.eje_x)
    readonly property bool vacia: _s.vacia !== false || puntos.length === 0
    readonly property color colorTotal: colorTema(_s.color_total ?? "accionPrimario")
    readonly property color colorCompletados: colorTema(_s.color_completados ?? "menuVerde")
    readonly property color colorFallo: colorTema(_s.color_fallo ?? "peligroTexto")

    readonly property real izq: m(56)
    readonly property real der: m(16)
    readonly property real arriba: m(16)
    readonly property real abajoMargen: m(40)
    readonly property real ancho: Math.max(1, width - izq - der)
    readonly property real alto: Math.max(1, height - arriba - abajoMargen)

    // listas que llegan de Python pueden ser secuencias de QVariant, no Array de JS
    function secuencia(v) {
        if (v === undefined || v === null || typeof v === "string" || typeof v.length !== "number") return []
        return Array.prototype.slice.call(v)
    }
    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    function colorTema(clave) {
        var c = Colores[clave]
        return c === undefined ? Colores.textoSecundario : c
    }
    function _n(v) { return (typeof v === "number" && isFinite(v)) ? Math.max(0, Math.min(1, v)) : 0 }
    function px(p) { return _n(p.x) * ancho }
    function py(frac) { return alto - _n(frac) * alto }

    // Catmull-Rom -> Bezier cubica (tension 1/6). Controles acotados a [0, alto]
    // en y y entre las x del tramo, para que la curva no salga del area.
    function curva(pts, arriba_, abajo_) {
        if (pts.length === 0) return ""
        var s = "M " + pts[0].x + " " + pts[0].y
        for (var i = 0; i < pts.length - 1; i++) {
            var p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)]
            var c1x = Math.min(p2.x, Math.max(p1.x, p1.x + (p2.x - p0.x) / 6))
            var c1y = Math.min(abajo_, Math.max(arriba_, p1.y + (p2.y - p0.y) / 6))
            var c2x = Math.min(p2.x, Math.max(p1.x, p2.x - (p3.x - p1.x) / 6))
            var c2y = Math.min(abajo_, Math.max(arriba_, p2.y - (p3.y - p1.y) / 6))
            s += " C " + c1x + " " + c1y + " " + c2x + " " + c2y + " " + p2.x + " " + p2.y
        }
        return s
    }
    function lista(clave) {
        var out = []
        for (var i = 0; i < puntos.length; i++)
            out.push({ x: px(puntos[i]), y: py(puntos[i][clave]) })
        return out
    }
    function indiceCercano(xLocal) {
        var mejor = -1, d = 1e9
        for (var i = 0; i < puntos.length; i++) {
            var dd = Math.abs(px(puntos[i]) - xLocal)
            if (dd < d) { d = dd; mejor = i }
        }
        return mejor
    }
    function cerrarBurbuja() { seleccion = -1 }

    onSerieChanged: seleccion = -1

    implicitWidth: m(640)
    implicitHeight: m(320)

    readonly property var ptsTotal: lista("y_total")
    readonly property var ptsComp: lista("y_completados")
    readonly property string trazoTotal: curva(ptsTotal, 0, alto)
    readonly property string trazoComp: curva(ptsComp, 0, alto)

    Timer {
        id: cierre
        objectName: "graficaAreaCierre"
        interval: raiz.duracionBurbujaMs
        running: raiz.seleccion >= 0
        repeat: false
        onTriggered: raiz.cerrarBurbuja()
    }

    // cuadricula y marcas del eje y
    Repeater {
        model: raiz.marcasY
        Item {
            id: marca
            required property var modelData
            width: raiz.width
            y: raiz.arriba + raiz.py(modelData.y)
            Rectangle {
                x: raiz.izq; width: raiz.ancho; height: 1
                color: Colores.bordeDivisor
            }
            Text {
                x: 0; width: raiz.izq - raiz.m(10)
                y: -height / 2
                horizontalAlignment: Text.AlignRight
                text: String(marca.modelData.valor ?? "")
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(16)
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: Escala.fuenteMinima
                wrapMode: Text.NoWrap
            }
        }
    }

    // etiquetas del eje x
    Repeater {
        model: raiz.marcasX
        Text {
            id: etiquetaX
            required property var modelData
            readonly property real cx: raiz.izq + raiz._n(modelData.x) * raiz.ancho
            width: raiz.m(72)
            x: Math.max(0, Math.min(raiz.width - width, cx - width / 2))
            y: raiz.arriba + raiz.alto + raiz.m(10)
            horizontalAlignment: Text.AlignHCenter
            text: String(modelData.texto ?? "")
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: raiz.fuente(16)
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: Escala.fuenteMinima
            wrapMode: Text.NoWrap
        }
    }

    // curvas
    Item {
        id: lienzo
        objectName: "graficaAreaLienzo"
        x: raiz.izq; y: raiz.arriba
        width: raiz.ancho; height: raiz.alto
        visible: !raiz.vacia

        Shape {
            anchors.fill: parent
            ShapePath {
                fillColor: Qt.alpha(raiz.colorTotal, 0.16)
                strokeWidth: -1
                PathSvg {
                    path: raiz.ptsTotal.length >= 2
                          ? raiz.trazoTotal + " L " + raiz.ptsTotal[raiz.ptsTotal.length - 1].x + " " + raiz.alto
                            + " L " + raiz.ptsTotal[0].x + " " + raiz.alto + " Z"
                          : ""
                }
            }
            ShapePath {
                objectName: "graficaAreaLineaTotal"
                strokeColor: raiz.colorTotal
                strokeWidth: Math.max(1, raiz.m(3))
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: raiz.ptsTotal.length >= 2 ? raiz.trazoTotal : "" }
            }
            ShapePath {
                objectName: "graficaAreaLineaCompletados"
                strokeColor: raiz.colorCompletados
                strokeWidth: Math.max(1, raiz.m(3))
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: raiz.ptsComp.length >= 2 ? raiz.trazoComp : "" }
            }
        }

        // punto rojo en cada intervalo con fallos
        Repeater {
            model: raiz.vacia ? [] : raiz.puntos
            Rectangle {
                id: punto
                required property var modelData
                required property int index
                objectName: "graficaAreaPuntoFallo_" + index
                visible: modelData.con_fallo === true
                width: raiz.m(14); height: width; radius: width / 2
                x: raiz.px(modelData) - width / 2
                y: raiz.py(modelData.y_total) - height / 2
                color: raiz.colorFallo
                border.width: Math.max(1, Math.round(raiz.m(2)))
                border.color: Colores.fondoTarjeta
            }
        }

        // marca del punto elegido
        Rectangle {
            id: guia
            objectName: "graficaAreaGuia"
            visible: raiz.seleccion >= 0 && raiz.seleccion < raiz.puntos.length
            width: Math.max(1, raiz.m(2)); height: raiz.alto
            x: visible ? raiz.px(raiz.puntos[raiz.seleccion]) - width / 2 : 0
            color: Colores.bordeCampo
        }
    }

    // estado vacio
    Text {
        objectName: "graficaAreaVacia"
        visible: raiz.vacia
        x: raiz.izq; y: raiz.arriba
        width: raiz.ancho; height: raiz.alto
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: raiz.textoVacio
        color: Colores.textoGuia
        font.family: Tipografia.familia
        font.pixelSize: raiz.fuente(22)
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: Escala.fuenteMinima
        wrapMode: Text.NoWrap
    }

    // toque: punto/intervalo mas cercano en x (zona completa, mayor que 64 px de alto)
    MouseArea {
        id: toque
        objectName: "graficaAreaToque"
        x: raiz.izq; y: raiz.arriba
        width: raiz.ancho; height: raiz.alto
        enabled: !raiz.vacia
        onClicked: (mouse) => {
            var i = raiz.indiceCercano(mouse.x)
            if (i < 0) return
            raiz.seleccion = i
            cierre.restart()
            raiz.puntoElegido(i)
        }
    }

    // burbuja
    Rectangle {
        id: burbuja
        objectName: "graficaAreaBurbuja"
        readonly property var p: (raiz.seleccion >= 0 && raiz.seleccion < raiz.puntos.length) ? raiz.puntos[raiz.seleccion] : null
        visible: p !== null
        width: Math.min(raiz.m(240), raiz.width)
        height: contenidoBurbuja.implicitHeight + raiz.m(24)
        radius: raiz.m(12)
        color: Colores.fondoTarjeta
        border.width: Math.max(1, Math.round(raiz.m(1)))
        border.color: Colores.bordeCampo
        x: p === null ? 0 : Math.max(0, Math.min(raiz.width - width, raiz.izq + raiz.px(p) - width / 2))
        y: p === null ? 0 : Math.max(0, raiz.arriba + raiz.py(p.y_total) - height - raiz.m(14))

        Column {
            id: contenidoBurbuja
            x: raiz.m(14); y: raiz.m(12)
            width: parent.width - raiz.m(28)
            spacing: raiz.m(4)
            Text {
                objectName: "graficaAreaBurbujaRotulo"
                width: parent.width
                text: burbuja.p ? String(burbuja.p.rotulo ?? "") : ""
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(20)
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: Escala.fuenteMinima
                wrapMode: Text.NoWrap
            }
            Text {
                objectName: "graficaAreaBurbujaTotal"
                width: parent.width
                text: burbuja.p ? (raiz.rotuloTotal + " " + String(burbuja.p.total ?? 0)) : ""
                color: raiz.colorTotal
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(18)
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: Escala.fuenteMinima
                wrapMode: Text.NoWrap
            }
            Text {
                objectName: "graficaAreaBurbujaFallos"
                width: parent.width
                text: burbuja.p ? (raiz.rotuloFallos + " " + String(burbuja.p.fallos ?? 0)) : ""
                color: raiz.colorFallo
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(18)
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: Escala.fuenteMinima
                wrapMode: Text.NoWrap
            }
        }
    }
}

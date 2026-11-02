import QtQuick
import QtQuick.Shapes
import Tema

// Tarjeta de indicador del dashboard de reportes (REP-03). Solo dibujo.
// `dato` = un elemento de presentable()['indicadores']: {clave, titulo, valor, pie,
// comparacion:{disponible, texto, flecha(arriba|abajo|igual|ninguna), color, sin_datos,
// texto_sin_datos}, mini:[{x, y}]} con x e y en 0..1. `color` de la comparacion es una
// CLAVE de Tema/Colores (si no existe usa el respaldo del tema).
// Medidas en px del mockup escaladas con `escala` (convencion m(), D-18).
Rectangle {
    id: raiz
    objectName: "tarjetaIndicador"

    property real escala: 1
    property var dato: ({})

    readonly property var _d: (dato && typeof dato === "object") ? dato : ({})
    readonly property var _c: (_d.comparacion && typeof _d.comparacion === "object") ? _d.comparacion : ({})
    readonly property var _mini: secuencia(_d.mini)
    readonly property bool sinDatos: _c.sin_datos === true || _c.disponible === false
    readonly property string flecha: sinDatos ? "ninguna" : String(_c.flecha ?? "ninguna")
    readonly property color colorComparacion: colorTema(_c.color ?? "textoSecundario")
    readonly property bool hayMini: _mini.length >= 2

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
    // Catmull-Rom -> Bezier cubica (tension 1/6); los puntos de control quedan
    // acotados a [arriba, abajo] y entre las x de cada tramo, sin sobrepaso.
    function curva(pts, arriba, abajo) {
        if (pts.length === 0) return ""
        var s = "M " + pts[0].x + " " + pts[0].y
        for (var i = 0; i < pts.length - 1; i++) {
            var p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)]
            var c1x = Math.min(p2.x, Math.max(p1.x, p1.x + (p2.x - p0.x) / 6))
            var c1y = Math.min(abajo, Math.max(arriba, p1.y + (p2.y - p0.y) / 6))
            var c2x = Math.min(p2.x, Math.max(p1.x, p2.x - (p3.x - p1.x) / 6))
            var c2y = Math.min(abajo, Math.max(arriba, p2.y - (p3.y - p1.y) / 6))
            s += " C " + c1x + " " + c1y + " " + c2x + " " + c2y + " " + p2.x + " " + p2.y
        }
        return s
    }
    function puntosMini(ancho, alto) {
        var out = []
        for (var i = 0; i < _mini.length; i++) {
            var p = _mini[i]
            var x = (typeof p.x === "number" && isFinite(p.x)) ? p.x : i / Math.max(1, _mini.length - 1)
            var y = (typeof p.y === "number" && isFinite(p.y)) ? p.y : 0
            out.push({ x: Math.max(0, Math.min(1, x)) * ancho, y: alto - Math.max(0, Math.min(1, y)) * alto })
        }
        return out
    }

    implicitWidth: m(300)
    implicitHeight: m(190)
    radius: m(16)
    color: Colores.fondoTarjeta
    border.width: Math.max(1, Math.round(m(1)))
    border.color: Colores.bordeDivisor

    Text {
        id: titulo
        objectName: "indicadorTitulo"
        x: raiz.m(18); y: raiz.m(14)
        width: raiz.width - raiz.m(36)
        text: String(raiz._d.titulo ?? "")
        color: Colores.textoSecundario
        font.family: Tipografia.familia
        font.pixelSize: raiz.fuente(20)
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: Escala.fuenteMinima
        wrapMode: Text.NoWrap
    }

    Text {
        id: valor
        objectName: "indicadorValor"
        anchors.top: titulo.bottom
        anchors.topMargin: raiz.m(4)
        x: raiz.m(18)
        width: raiz.width - raiz.m(36) - (raiz.hayMini ? raiz.m(110) : 0)
        text: String(raiz._d.valor ?? "")
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(52)
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: Escala.fuenteMinima
        wrapMode: Text.NoWrap
    }

    Row {
        id: comparacion
        objectName: "indicadorComparacion"
        anchors.top: valor.bottom
        anchors.topMargin: raiz.m(2)
        x: raiz.m(18)
        spacing: raiz.m(8)
        height: raiz.m(28)

        Shape {
            id: flechaForma
            objectName: "indicadorFlecha"
            visible: raiz.flecha === "arriba" || raiz.flecha === "abajo"
            width: raiz.m(16); height: raiz.m(14)
            anchors.verticalCenter: parent.verticalCenter
            ShapePath {
                fillColor: raiz.colorComparacion
                strokeWidth: -1
                PathPolyline {
                    path: raiz.flecha === "abajo"
                          ? [Qt.point(0, 0), Qt.point(flechaForma.width, 0), Qt.point(flechaForma.width / 2, flechaForma.height), Qt.point(0, 0)]
                          : [Qt.point(0, flechaForma.height), Qt.point(flechaForma.width, flechaForma.height), Qt.point(flechaForma.width / 2, 0), Qt.point(0, flechaForma.height)]
                }
            }
        }
        Rectangle {
            objectName: "indicadorIgual"
            visible: raiz.flecha === "igual"
            width: raiz.m(16); height: raiz.m(4); radius: height / 2
            anchors.verticalCenter: parent.verticalCenter
            color: raiz.colorComparacion
        }
        Text {
            id: textoComparacion
            objectName: "indicadorTextoComparacion"
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, raiz.width - raiz.m(36) - (raiz.hayMini ? raiz.m(110) : 0) - raiz.m(24))
            text: raiz.sinDatos ? String(raiz._c.texto_sin_datos ?? "") : String(raiz._c.texto ?? "")
            color: raiz.sinDatos ? Colores.textoGuia : raiz.colorComparacion
            font.family: Tipografia.familia
            font.weight: raiz.sinDatos ? Tipografia.pesoRegular : Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(raiz.sinDatos ? 16 : 20)
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: Escala.fuenteMinima
            wrapMode: Text.NoWrap
        }
    }

    Text {
        objectName: "indicadorPie"
        visible: text !== ""
        anchors.left: parent.left
        anchors.leftMargin: raiz.m(18)
        anchors.right: parent.right
        anchors.rightMargin: raiz.m(18)
        anchors.bottom: parent.bottom
        anchors.bottomMargin: raiz.m(12)
        text: String(raiz._d.pie ?? "")
        color: Colores.textoSecundario
        font.family: Tipografia.familia
        font.pixelSize: raiz.fuente(17)
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: Escala.fuenteMinima
        wrapMode: Text.NoWrap
    }

    // minigrafica suavizada: area tenue + linea, abajo a la derecha
    Item {
        id: mini
        objectName: "indicadorMini"
        visible: raiz.hayMini
        width: raiz.m(100); height: raiz.m(44)
        anchors.right: parent.right
        anchors.rightMargin: raiz.m(18)
        anchors.top: parent.top
        anchors.topMargin: raiz.m(70)
        readonly property var pts: raiz.puntosMini(width, height)
        readonly property string trazo: raiz.curva(pts, 0, height)

        Shape {
            anchors.fill: parent
            ShapePath {
                fillColor: Qt.alpha(Colores.accionPrimario, 0.12)
                strokeWidth: -1
                PathSvg {
                    path: mini.pts.length >= 2
                          ? mini.trazo + " L " + mini.pts[mini.pts.length - 1].x + " " + mini.height + " L " + mini.pts[0].x + " " + mini.height + " Z"
                          : ""
                }
            }
            ShapePath {
                strokeColor: Colores.accionPrimario
                strokeWidth: Math.max(1, raiz.m(2.5))
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: mini.pts.length >= 2 ? mini.trazo : "" }
            }
        }
    }
}

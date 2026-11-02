import QtQuick
import QtQuick.Shapes
import Tema

// Anillo de progreso generico (reportes: mantenimiento REP-09 y similares).
// Solo dibujo: `fraccion` (0..1), `colorClave` (nombre de una propiedad de Tema/Colores;
// si no existe usa el color de respaldo del tema), `texto` central y `titulo` bajo el anillo.
// Medidas en px del mockup escaladas con `escala` (convencion m(), D-18).
Item {
    id: raiz
    objectName: "anilloProgreso"

    property real escala: 1
    property real fraccion: 0
    property string colorClave: "accionPrimario"
    property string texto: ""
    property string titulo: ""
    // diametro del anillo y grosor del trazo, en px del mockup
    property real diametro: 150
    property real grosor: 16

    readonly property real fraccionAcotada: (isFinite(fraccion) ? Math.max(0, Math.min(1, fraccion)) : 0)
    readonly property color colorAnillo: colorTema(colorClave)

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    function colorTema(clave) {
        var c = Colores[clave]
        return c === undefined ? Colores.textoSecundario : c
    }

    implicitWidth: m(diametro)
    implicitHeight: m(diametro) + (titulo !== "" ? m(52) : 0)

    Item {
        id: zona
        objectName: "anilloZona"
        width: raiz.m(raiz.diametro)
        height: width
        anchors.horizontalCenter: parent.horizontalCenter

        Shape {
            anchors.fill: parent
            ShapePath {
                strokeColor: Colores.bordeDivisor
                strokeWidth: raiz.m(raiz.grosor)
                fillColor: "transparent"
                capStyle: ShapePath.FlatCap
                PathAngleArc {
                    centerX: zona.width / 2; centerY: zona.height / 2
                    radiusX: (zona.width - raiz.m(raiz.grosor)) / 2
                    radiusY: radiusX
                    startAngle: -90; sweepAngle: 359.99
                }
            }
            ShapePath {
                objectName: "anilloArco"
                strokeColor: raiz.colorAnillo
                strokeWidth: raiz.fraccionAcotada > 0 ? raiz.m(raiz.grosor) : 0
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathAngleArc {
                    centerX: zona.width / 2; centerY: zona.height / 2
                    radiusX: (zona.width - raiz.m(raiz.grosor)) / 2
                    radiusY: radiusX
                    startAngle: -90
                    sweepAngle: Math.min(359.99, 360 * raiz.fraccionAcotada)
                }
            }
        }

        Text {
            objectName: "anilloTexto"
            anchors.centerIn: parent
            width: parent.width - raiz.m(raiz.grosor) * 2 - raiz.m(12)
            horizontalAlignment: Text.AlignHCenter
            text: raiz.texto
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(32)
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: Escala.fuenteMinima
            wrapMode: Text.NoWrap
        }
    }

    Text {
        objectName: "anilloTitulo"
        visible: raiz.titulo !== ""
        anchors.top: zona.bottom
        anchors.topMargin: raiz.m(10)
        anchors.horizontalCenter: parent.horizontalCenter
        width: raiz.width
        horizontalAlignment: Text.AlignHCenter
        text: raiz.titulo
        color: Colores.textoSecundario
        font.family: Tipografia.familia
        font.pixelSize: raiz.fuente(22)
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: Escala.fuenteMinima
        wrapMode: Text.NoWrap
    }
}

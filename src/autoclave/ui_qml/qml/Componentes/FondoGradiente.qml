import QtQuick
import QtQuick.Shapes

// Modo oscuro: gradiente radial elíptico, como el CSS
// `radial-gradient(radioX radioY at centroX centroY, color0, color1 posicion1, color2)`
// (fracciones del ancho y del alto). Lo usan FondoApp, Reposo e IntroArranque en
// lugar de fondo-arranque.png (paleta_modo_oscuro.md §1). Los colores los pasa
// quien lo usa, siempre desde Colores.
Item {
    id: raiz
    property real centroX: 0.5
    property real centroY: 0.5
    property real radioX: 0.5
    property real radioY: 0.5
    property color color0
    property color color1
    property real posicion1: 0.5
    property color color2
    clip: true

    // la elipse se dibuja como círculo en un sistema estirado en vertical por 1/k
    readonly property real _rx: Math.max(1, width * radioX)
    readonly property real _k: Math.max(0.001, height * radioY / _rx)
    readonly property real _altoCirculo: height / _k

    // fuera del radio, el último color (como `pad` del CSS)
    Rectangle { anchors.fill: parent; color: raiz.color2 }

    Shape {
        width: raiz.width
        height: raiz._altoCirculo
        preferredRendererType: Shape.CurveRenderer
        transform: Scale { yScale: raiz._k }
        ShapePath {
            strokeWidth: 0
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: raiz.width * raiz.centroX
                centerY: raiz._altoCirculo * raiz.centroY
                centerRadius: raiz._rx
                focalX: centerX; focalY: centerY
                GradientStop { position: 0.0; color: raiz.color0 }
                GradientStop { position: raiz.posicion1; color: raiz.color1 }
                GradientStop { position: 1.0; color: raiz.color2 }
            }
            startX: 0; startY: 0
            PathLine { x: raiz.width; y: 0 }
            PathLine { x: raiz.width; y: raiz._altoCirculo }
            PathLine { x: 0; y: raiz._altoCirculo }
            PathLine { x: 0; y: 0 }
        }
    }
}

import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import Tema

// Deslizador de INICIAR CICLO: traducción a QML del interruptor "holográfico" de
// Uiverse.io (reglobby), con paleta de verdes. Mismos elementos que el original:
// pista con brillo exterior, reflejo, franja superior y línea de puntos en
// movimiento; manija con núcleo, centro que pulsa, barrido, partículas y brillo
// interior; tres anillos que giran (aparecen al deslizar); indicador que parpadea;
// textos de cada estado y las líneas de interfaz bajo la pista.
//
// Comportamiento: el ciclo solo arranca si la manija llega al extremo derecho
// (completado()); si se suelta antes, o al terminar, vuelve sola al inicio.
//
// Medidas: todo el dibujo está en "u" = alto / 60, la unidad del original (alto 60),
// así que escala con el alto que le dé la pantalla. Paleta: verdeReposo (estado
// "apagado" del original, azul) y verdeListo (estado "encendido") se mezclan según
// el avance, para que el color cambie con el arrastre.
Item {
    id: desl

    property string texto: ""             // texto de reposo (en el original, "apagado")
    property string textoCompletado: ""   // texto que aparece al deslizar (en el original, "encendido")
    property alias contenidoCirculo: iconoManija.data
    signal completado()

    readonly property real u: height / 60
    readonly property real margen: 3 * u
    readonly property real diametro: 54 * u
    readonly property real maxX: width - margen - diametro
    readonly property real progreso: maxX > margen
        ? Math.max(0, Math.min(1, (manija.x - margen) / (maxX - margen))) : 0
    // mientras vuelve al inicio (o se acaba de emitir) no acepta otro arrastre
    property bool _bloqueado: false
    // sin movimiento en las pruebas con plataforma "offscreen" ni cuando está oculto
    readonly property bool animar: visible && !Movimiento.instantaneo

    // ---- paleta de verdes (reposo → listo) ----
    readonly property color verdeReposo: "#28be5f"
    readonly property color verdeListo: "#6effa0"
    readonly property color brilloReposo: "#9be8b4"
    readonly property color brilloListo: "#c8ffd8"
    readonly property color acento: mezcla(verdeReposo, verdeListo, progreso)
    readonly property color brillo: mezcla(brilloReposo, brilloListo, progreso)

    function mezcla(a, b, t) {
        a = Qt.color(a); b = Qt.color(b)
        return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t,
                       a.b + (b.b - a.b) * t, a.a + (b.a - a.a) * t)
    }
    function ac(alfa) { return Qt.rgba(acento.r, acento.g, acento.b, alfa) }
    function br(alfa) { return Qt.rgba(brillo.r, brillo.g, brillo.b, alfa) }

    opacity: enabled ? 1.0 : 0.4

    function _alInicio() { regreso.restart() }
    onEnabledChanged: if (!enabled) _alInicio()
    onVisibleChanged: if (!visible) { regreso.stop(); manija.x = margen; _bloqueado = false }
    onWidthChanged: if (!arrastre.active && !regreso.running) manija.x = margen

    // ======================= piezas reutilizables =======================

    // círculo/elipse con degradado radial (centro → borde)
    component DiscoRadial: Shape {
        id: dr
        property color centro: "white"
        property color borde: "transparent"
        property real corte: 1.0          // posición del borde dentro del radio
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeWidth: 0
            fillGradient: RadialGradient {
                centerX: dr.width / 2; centerY: dr.height / 2
                centerRadius: dr.width / 2
                focalX: centerX; focalY: centerY
                GradientStop { position: 0.0; color: dr.centro }
                GradientStop { position: dr.corte; color: dr.borde }
                GradientStop { position: 1.0; color: dr.borde }
            }
            PathAngleArc {
                centerX: dr.width / 2; centerY: dr.height / 2
                radiusX: dr.width / 2; radiusY: dr.height / 2
                startAngle: 0; sweepAngle: 360
            }
        }
    }

    // "radial-gradient(ellipse at center, ...)": círculo comprimido en vertical
    component ElipseRadial: Item {
        id: er
        property color centro: "white"
        property color borde: "transparent"
        property real corte: 0.99
        DiscoRadial {
            width: er.width; height: er.width
            y: (er.height - er.width) / 2
            centro: er.centro; borde: er.borde; corte: er.corte
            transform: Scale { origin.x: er.width / 2; origin.y: er.width / 2; yScale: er.height / er.width }
        }
    }

    // sombra interior ("box-shadow: inset 0 0 Npx color"): un anillo difuminado y
    // recortado a la forma
    component SombraInterior: Item {
        id: si
        property real radio: height / 2
        property color color: "#000000"
        property real grosor: 8
        property real desenfoque: 0.6
        Item {
            anchors.fill: parent
            layer.enabled: true
            layer.effect: MultiEffect {
                blurEnabled: true; blurMax: 32; blur: si.desenfoque
                maskEnabled: true; maskSource: mascaraSombra
            }
            Rectangle {
                anchors.fill: parent
                radius: si.radio
                color: "transparent"
                border.width: si.grosor
                border.color: si.color
            }
        }
        Item {
            id: mascaraSombra
            anchors.fill: parent
            visible: false
            layer.enabled: true
            Rectangle { anchors.fill: parent; radius: si.radio }
        }
    }

    // recorta su contenido a la forma de la pista (el original usa overflow: hidden)
    component Recorte: Item {
        id: rc
        default property alias contenido: cont.data
        Item {
            id: cont
            anchors.fill: parent
            layer.enabled: true
            layer.effect: MultiEffect { maskEnabled: true; maskSource: mascaraRecorte }
        }
        Item {
            id: mascaraRecorte
            anchors.fill: parent
            visible: false
            layer.enabled: true
            Rectangle { anchors.fill: parent; radius: height / 2 }
        }
    }

    // anillo con dos arcos (dos "bordes" de color distinto) que gira
    component Anillo: Shape {
        id: an
        property real diam: 50 * desl.u
        property real angulo: -135      // inicio del arco principal (grados, 0 = derecha)
        property real alfa1: 0.5
        property real alfa2: 0.3
        property int duracion: 3000
        property bool inverso: false
        width: diam; height: diam
        preferredRendererType: Shape.CurveRenderer
        readonly property real grosor: 2 * desl.u
        ShapePath {
            strokeWidth: an.grosor; strokeColor: desl.ac(an.alfa1); fillColor: "transparent"
            capStyle: ShapePath.FlatCap
            PathAngleArc {
                centerX: an.diam / 2; centerY: an.diam / 2
                radiusX: (an.diam - an.grosor) / 2; radiusY: (an.diam - an.grosor) / 2
                startAngle: an.angulo; sweepAngle: 90
            }
        }
        ShapePath {
            strokeWidth: an.grosor; strokeColor: desl.ac(an.alfa2); fillColor: "transparent"
            capStyle: ShapePath.FlatCap
            PathAngleArc {
                centerX: an.diam / 2; centerY: an.diam / 2
                radiusX: (an.diam - an.grosor) / 2; radiusY: (an.diam - an.grosor) / 2
                startAngle: an.angulo + 90; sweepAngle: 90
            }
        }
        NumberAnimation on rotation {
            running: desl.animar && an.visible
            from: 0; to: an.inverso ? -360 : 360
            duration: an.duracion; loops: Animation.Infinite
        }
    }

    // ======================= resplandor exterior (holo-glow) =======================
    ElipseRadial {
        x: 0; y: 0; width: desl.width; height: desl.height
        centro: desl.ac(0.2); borde: "transparent"; corte: 0.99
        opacity: 0.5
        layer.enabled: true
        layer.effect: MultiEffect {
            blurEnabled: true; blurMax: 32; blur: 0.5
            paddingRect: Qt.rect(20 * desl.u, 20 * desl.u, 20 * desl.u, 20 * desl.u)
        }
    }

    // ======================= pista (toggle-track) =======================
    Rectangle {
        id: pista
        anchors.fill: parent
        radius: height / 2
        color: desl.mezcla("#052a17", "#063a1f", desl.progreso)
        border.width: Math.max(1, desl.u)
        border.color: desl.ac(0.3)
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: desl.ac(1)
            shadowOpacity: 0.4
            shadowBlur: 0.6
            paddingRect: Qt.rect(24 * desl.u, 24 * desl.u, 24 * desl.u, 24 * desl.u)
        }
    }

    // sombra interior de la pista (inset 0 0 10px negro .8)
    SombraInterior {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.8)
        grosor: 10 * desl.u
        desenfoque: 0.55
    }

    Recorte {
        anchors.fill: parent
        // ::before — degradado radial y lineal de fondo
        ElipseRadial {
            anchors.fill: parent
            centro: desl.ac(0.1); borde: "transparent"; corte: 0.99
            opacity: 0.6
        }
        Rectangle {
            anchors.fill: parent
            radius: height / 2
            opacity: 0.6
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: desl.mezcla(Qt.rgba(0.04, 0.35, 0.18, 0.1), Qt.rgba(0, 0.47, 0.24, 0.1), desl.progreso) }
                GradientStop { position: 1.0; color: desl.mezcla(Qt.rgba(0.01, 0.18, 0.09, 0.2), Qt.rgba(0, 0.24, 0.12, 0.2), desl.progreso) }
            }
        }

        // ::after — franja de luz en el borde superior
        Rectangle {
            x: 2 * desl.u; y: 2 * desl.u
            width: desl.width - 4 * desl.u; height: 10 * desl.u
            topLeftRadius: 10 * desl.u; topRightRadius: 10 * desl.u
            opacity: 0.7
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: desl.ac(0.3) }
                GradientStop { position: 1.0; color: desl.mezcla(Qt.rgba(0.1, 0.7, 0.4, 0.1), Qt.rgba(0.1, 0.8, 0.5, 0.1), desl.progreso) }
            }
        }

        // línea de puntos que se desplaza por el centro (track-lines)
        Item {
            x: 0; width: desl.width
            height: Math.max(1, desl.u)
            anchors.verticalCenter: parent.verticalCenter
            clip: true
            Item {
                id: carril
                property real fase: 0
                height: parent.height
                width: desl.width + 30 * desl.u
                x: desl.progreso > 0.5 ? -fase * 15 * desl.u : (fase - 1) * 15 * desl.u
                Repeater {
                    model: Math.ceil(carril.width / (15 * desl.u)) + 1
                    Rectangle {
                        x: index * 15 * desl.u
                        width: 5 * desl.u; height: carril.height
                        color: desl.ac(0.3)
                    }
                }
                NumberAnimation on fase {
                    running: desl.animar
                    from: 0; to: 1; duration: 2000; loops: Animation.Infinite
                }
            }
        }
    }

    // ======================= textos e indicadores (toggle-data) =======================
    // estado de reposo: texto a la derecha + indicador que parpadea
    Text {
        objectName: "textoDeslizadorInicio"
        x: desl.margen + desl.diametro + 12 * desl.u
        width: desl.width - x - 32 * desl.u
        anchors.verticalCenter: parent.verticalCenter
        horizontalAlignment: Text.AlignRight
        text: desl.texto
        color: desl.ac(0.85)
        opacity: 1.0 - desl.progreso
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoMedium
        font.pixelSize: Math.max(1, Math.round(12 * desl.u))
        font.letterSpacing: desl.u
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: Math.min(font.pixelSize, Escala.fuenteMinima)
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true; shadowColor: desl.ac(1); shadowOpacity: 0.5; shadowBlur: 0.35
            paddingRect: Qt.rect(8 * desl.u, 8 * desl.u, 8 * desl.u, 8 * desl.u)
        }
    }
    Item {
        id: puntoReposo
        width: 10 * desl.u; height: width
        x: desl.width - 15 * desl.u - width
        anchors.verticalCenter: parent.verticalCenter
        opacity: (1.0 - desl.progreso) * parpadeo
        scale: 0.9 + 0.2 * (parpadeo - 0.5) / 0.5
        property real parpadeo: 0.5
        DiscoRadial {
            anchors.centerIn: parent
            width: 26 * desl.u; height: width
            centro: desl.ac(0.5); borde: "transparent"
        }
        DiscoRadial {
            anchors.fill: parent
            centro: desl.ac(0.8); borde: desl.ac(0.4)
        }
        SequentialAnimation on parpadeo {
            running: desl.animar
            loops: Animation.Infinite
            NumberAnimation { from: 0.5; to: 1.0; duration: 1000; easing.type: Easing.InOutQuad }
            NumberAnimation { from: 1.0; to: 0.5; duration: 1000; easing.type: Easing.InOutQuad }
        }
    }

    // estado listo: texto a la izquierda + indicador (aparecen al deslizar)
    Text {
        x: 15 * desl.u
        width: desl.width - x - desl.margen - desl.diametro - 12 * desl.u
        anchors.verticalCenter: parent.verticalCenter
        horizontalAlignment: Text.AlignLeft
        text: desl.textoCompletado
        color: desl.ac(0.85)
        opacity: desl.progreso
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoMedium
        font.pixelSize: Math.max(1, Math.round(12 * desl.u))
        font.letterSpacing: desl.u
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: Math.min(font.pixelSize, Escala.fuenteMinima)
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true; shadowColor: desl.ac(1); shadowOpacity: 0.5; shadowBlur: 0.35
            paddingRect: Qt.rect(8 * desl.u, 8 * desl.u, 8 * desl.u, 8 * desl.u)
        }
    }
    Item {
        width: 10 * desl.u; height: width
        x: 15 * desl.u
        anchors.verticalCenter: parent.verticalCenter
        opacity: desl.progreso * puntoReposo.parpadeo
        scale: puntoReposo.scale
        DiscoRadial {
            anchors.centerIn: parent
            width: 26 * desl.u; height: width
            centro: desl.ac(0.5); borde: "transparent"
        }
        DiscoRadial {
            anchors.fill: parent
            centro: desl.ac(0.8); borde: desl.ac(0.4)
        }
    }

    // ======================= reflejo (toggle-reflection) =======================
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeWidth: 0
            fillGradient: LinearGradient {
                // 135deg: de arriba-izquierda a abajo-derecha, sobre el largo del degradado CSS
                readonly property real mitad: (desl.width + desl.height) * 0.7071 / 2
                x1: desl.width / 2 - mitad * 0.7071; y1: desl.height / 2 - mitad * 0.7071
                x2: desl.width / 2 + mitad * 0.7071; y2: desl.height / 2 + mitad * 0.7071
                GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.1) }
                GradientStop { position: 0.4; color: Qt.rgba(1, 1, 1, 0) }
                GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0) }
            }
            PathRectangle {
                x: 0; y: 0; width: desl.width; height: desl.height
                radius: desl.height / 2
            }
        }
    }

    // ======================= anillos de energía (siguen a la manija) =======================
    Item {
        id: anillos
        x: manija.x; y: manija.y
        width: desl.diametro; height: desl.diametro
        opacity: desl.progreso
        visible: opacity > 0
        Anillo { anchors.centerIn: parent; diam: 50 * desl.u; angulo: -135; duracion: 3000 }
        Anillo { anchors.centerIn: parent; diam: 40 * desl.u; angulo: 45; duracion: 2000; inverso: true }
        Anillo { anchors.centerIn: parent; diam: 30 * desl.u; angulo: 135; duracion: 1500 }
    }

    // ======================= manija (toggle-thumb) =======================
    Item {
        id: manija
        objectName: "manijaDeslizadorInicio"
        x: desl.margen; y: desl.margen
        width: desl.diametro; height: desl.diametro

        // sombra exterior (0 2px 15px negro .5)
        DiscoRadial {
            x: -8 * desl.u; y: -8 * desl.u + 2 * desl.u
            width: parent.width + 16 * desl.u; height: width
            centro: Qt.rgba(0, 0, 0, 0.5); borde: "transparent"; corte: 0.98
            // el degradado arranca en el borde de la manija: se ve solo hacia afuera
            opacity: 0.55
        }
        // fondo
        DiscoRadial {
            anchors.fill: parent
            centro: desl.mezcla(Qt.rgba(0.02, 0.25, 0.13, 0.9), Qt.rgba(0.04, 0.35, 0.16, 0.9), desl.progreso)
            borde: desl.mezcla(Qt.rgba(0, 0.13, 0.07, 0.8), Qt.rgba(0, 0.2, 0.08, 0.8), desl.progreso)
        }

        // contenido recortado al círculo: núcleo, centro que pulsa, barrido y partículas
        Item {
            id: interior
            anchors.fill: parent
            layer.enabled: true
            layer.effect: MultiEffect {
                maskEnabled: true; maskSource: mascaraManija
            }
            // thumb-core
            DiscoRadial {
                anchors.centerIn: parent
                width: 40 * desl.u; height: width
                opacity: 0.9
                centro: desl.ac(0.6)
                borde: desl.mezcla(Qt.rgba(0, 0.2, 0.1, 0.2), Qt.rgba(0, 0.24, 0.1, 0.2), desl.progreso)
            }
            // thumb-inner
            DiscoRadial {
                id: nucleoCentral
                anchors.centerIn: parent
                width: 25 * desl.u; height: width
                property real pulso: 0
                opacity: 0.5 + 0.3 * pulso
                scale: 0.9 + 0.2 * pulso
                centro: Qt.rgba(1, 1, 1, 0.8)
                borde: desl.br(0.5)
                SequentialAnimation on pulso {
                    running: desl.animar
                    loops: Animation.Infinite
                    NumberAnimation { from: 0; to: 1; duration: 2000; easing.type: Easing.InOutQuad }
                    NumberAnimation { from: 1; to: 0; duration: 2000; easing.type: Easing.InOutQuad }
                }
            }
            // thumb-scan
            Rectangle {
                id: barrido
                width: parent.width; height: 5 * desl.u
                y: -5 * desl.u
                opacity: 0
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0) }
                    GradientStop { position: 0.2; color: desl.ac(0.5) }
                    GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.8) }
                    GradientStop { position: 0.8; color: desl.ac(0.5) }
                    GradientStop { position: 1.0; color: Qt.rgba(0, 0, 0, 0) }
                }
                ParallelAnimation {
                    running: desl.animar
                    loops: Animation.Infinite
                    NumberAnimation { target: barrido; property: "y"; from: -5 * desl.u; to: 54 * desl.u; duration: 2000 }
                    SequentialAnimation {
                        NumberAnimation { target: barrido; property: "opacity"; from: 0; to: 0.7; duration: 400 }
                        PauseAnimation { duration: 1200 }
                        NumberAnimation { target: barrido; property: "opacity"; from: 0.7; to: 0; duration: 400 }
                    }
                }
            }
            // thumb-particles
            Repeater {
                model: [
                    { arriba: 0.70, izq: 0.30, retardo: 200 },
                    { arriba: 0.60, izq: 0.60, retardo: 600 },
                    { arriba: 0.50, izq: 0.40, retardo: 1000 },
                    { arriba: 0.40, izq: 0.70, retardo: 1400 },
                    { arriba: 0.80, izq: 0.50, retardo: 1800 }
                ]
                Rectangle {
                    id: particula
                    readonly property real base: modelData.arriba * desl.diametro
                    x: modelData.izq * desl.diametro
                    y: base
                    width: 3 * desl.u; height: width; radius: width / 2
                    color: desl.br(0.8)
                    opacity: 0
                    SequentialAnimation {
                        running: desl.animar
                        PauseAnimation { duration: modelData.retardo }
                        ParallelAnimation {
                            loops: Animation.Infinite
                            NumberAnimation { target: particula; property: "y"; from: particula.base; to: particula.base - 30 * desl.u; duration: 3000; easing.type: Easing.OutQuad }
                            NumberAnimation { target: particula; property: "scale"; from: 1; to: 0; duration: 3000; easing.type: Easing.OutQuad }
                            SequentialAnimation {
                                NumberAnimation { target: particula; property: "opacity"; from: 0; to: 0.8; duration: 600 }
                                NumberAnimation { target: particula; property: "opacity"; from: 0.8; to: 0; duration: 2400 }
                            }
                        }
                    }
                }
            }
        }
        Item {
            id: mascaraManija
            anchors.fill: parent
            visible: false
            layer.enabled: true
            Rectangle { anchors.fill: parent; radius: width / 2 }
        }

        // brillo interior (inset 0 0 15px acento .5) y borde
        SombraInterior {
            anchors.fill: parent
            color: desl.ac(0.5)
            grosor: 12 * desl.u
            desenfoque: 0.5
        }
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: "transparent"
            border.width: Math.max(1, desl.u)
            border.color: desl.ac(0.6)
        }

        // ícono propio de la pantalla (triángulo "play")
        Item { id: iconoManija; anchors.fill: parent }

        DragHandler {
            id: arrastre
            enabled: !desl._bloqueado
            target: manija
            xAxis.minimum: desl.margen
            xAxis.maximum: desl.maxX
            yAxis.enabled: false
            onActiveChanged: {
                if (active)
                    return
                // solo cuenta el recorrido completo (con 1 px de holgura de redondeo)
                if (manija.x >= desl.maxX - 1) {
                    desl._bloqueado = true
                    desl.completado()
                }
                desl._alInicio()
            }
        }
        NumberAnimation {
            id: regreso
            target: manija
            property: "x"
            to: desl.margen
            duration: 250
            easing.type: Easing.OutCubic
            onStopped: desl._bloqueado = false
        }
    }

    // ======================= líneas de interfaz bajo la pista =======================
    Repeater {
        // [x desde la izquierda o -1, x desde la derecha, ancho, alto, bottom] en px del original
        model: [
            { izq: 20, der: -1, w: 15, h: 1, bottom: -5 },
            { izq: 35, der: -1, w: 1, h: 8, bottom: -12 },
            { izq: 35, der: -1, w: 25, h: 1, bottom: -12 },
            { izq: -1, der: 20, w: 15, h: 1, bottom: -5 },
            { izq: -1, der: 35, w: 1, h: 8, bottom: -12 },
            { izq: -1, der: 10, w: 25, h: 1, bottom: -12 }
        ]
        Rectangle {
            width: Math.max(1, modelData.w * desl.u); height: Math.max(1, modelData.h * desl.u)
            x: modelData.izq >= 0 ? modelData.izq * desl.u
                                  : desl.width - modelData.der * desl.u - width
            y: desl.height - modelData.bottom * desl.u - height
            color: desl.ac(0.3)
        }
    }
}

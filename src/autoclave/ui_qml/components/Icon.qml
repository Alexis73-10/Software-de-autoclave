// ui_qml/components/Icon.qml
//
// Icono monocromo con tinte en tiempo de ejecución (§7.3 del plan de
// interfaz dual-pantalla). El renderizador SVG de Qt (SVG Tiny 1.2) no
// resuelve currentColor ni variables CSS (hallazgo UI-06), así que los SVG
// de origen traen un color fijo cualquiera y este componente lo recolorea
// vía MultiEffect.colorization. Contrato de entrega de los SVG: §7.3 del
// plan (viewBox 0 0 24 24, sin width/height, trazo expandido a trayectoria,
// monocromo puro, nombre icon-{nombre-kebab}-24.svg).

import QtQuick
import QtQuick.Effects

Item {
    id: root

    property string iconsDir: "icons/"
    property string name: ""
    property color color: "black"
    property int size: 24

    readonly property url source: name ? iconsDir + "icon-" + name + "-24.svg" : ""

    implicitWidth: size
    implicitHeight: size
    width: size
    height: size

    Image {
        id: img
        source: root.source
        sourceSize: Qt.size(root.size, root.size)
        anchors.fill: parent
        visible: false
        smooth: true
        fillMode: Image.PreserveAspectFit
    }

    MultiEffect {
        anchors.fill: parent
        source: img
        colorization: 1.0
        colorizationColor: root.color
    }
}

import QtQuick
import QtQuick.Effects

// Icono SVG pintado de un color exacto: el SVG se usa como máscara (alfa) de un
// rectángulo del color pedido. colorization de MultiEffect da un tono aproximado
// (#009535 sale #009E38); con máscara el color es idéntico al token.
// MultiEffect no se dibuja con QT_QPA_PLATFORM=offscreen (backend de software):
// en pruebas offscreen el icono queda invisible; las capturas usan la plataforma real.
Item {
    id: raiz
    property url source
    property color color: "black"

    Image {
        id: forma
        anchors.fill: parent
        source: raiz.source
        sourceSize.width: width
        sourceSize.height: height
        visible: false
        layer.enabled: true
    }
    Rectangle {
        id: relleno
        anchors.fill: parent
        color: raiz.color
        visible: false
        layer.enabled: true
    }
    MultiEffect {
        anchors.fill: parent
        source: relleno
        maskEnabled: true
        maskSource: forma
        // umbral 0.5 con dispersión completa: conserva el antialias del borde
        maskThresholdMin: 0.5
        maskSpreadAtMin: 1.0
    }
}

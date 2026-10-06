import QtQuick
import Tema

// Botón de texto en píldora de las ventanas del Menú Principal (Historial,
// Reportes): primario azul o secundario gris, atenuado si no está habilitado.
// Medidas en px del mockup escaladas con `escala` (convención m(), D-18).
// DISEÑO PROVISIONAL: sin diseño del diseñador.
Item {
    id: raiz

    property real escala: 1
    property string texto: ""
    property bool primario: false
    property bool habilitado: true

    signal pulsado()

    function m(v) { return v * escala }

    width: Math.max(m(220), textoBoton.implicitWidth + m(56))
    height: m(64)
    opacity: habilitado ? 1 : 0.4

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: raiz.primario ? Colores.accionPrimario : Colores.fondoSutil
        border.width: raiz.primario ? 0 : raiz.m(2)
        border.color: Colores.bordeDivisor
        opacity: zona.pressed ? 0.8 : 1
    }
    Text {
        id: textoBoton
        anchors.centerIn: parent
        text: raiz.texto
        color: raiz.primario ? "white" : Colores.textoPrimario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
        font.pixelSize: Math.max(1, Math.round(raiz.m(22)))
    }
    MouseArea {
        id: zona
        anchors.fill: parent
        enabled: raiz.habilitado
        onClicked: raiz.pulsado()
    }
}

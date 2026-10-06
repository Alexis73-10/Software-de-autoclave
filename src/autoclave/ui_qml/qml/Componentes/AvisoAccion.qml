import QtQuick
import Tema

// Aviso de una acción de impresión o correo (Historial y Reportes): mientras
// trabaja ("Imprimiendo…"), o su resultado en verde (éxito) o rojo (error).
// Tocarlo lo cierra, salvo mientras trabaja. Invisible si no hay texto.
// Medidas en px del mockup escaladas con `escala` (convención m(), D-18).
// DISEÑO PROVISIONAL: sin diseño del diseñador.
Rectangle {
    id: raiz

    property real escala: 1
    property string texto: ""
    property bool trabajando: false
    property bool error: false

    signal cerrado()

    function m(v) { return v * escala }

    visible: texto !== ""
    width: Math.min(parent ? parent.width : 0, textoAviso.implicitWidth + m(64))
    height: textoAviso.height + m(32)
    radius: m(20)
    color: error ? Colores.peligroFondo : Colores.fondoTarjeta
    border.width: m(2)
    border.color: error ? Colores.peligroTexto : Colores.bordeDivisor

    Text {
        id: textoAviso
        objectName: "textoAvisoAccion"
        anchors.centerIn: parent
        width: Math.min(implicitWidth, (raiz.parent ? raiz.parent.width : 0) - raiz.m(64))
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        text: raiz.texto
        color: raiz.error ? Colores.peligroTexto
             : raiz.trabajando ? Colores.textoPrimario : Colores.menuVerdeTexto
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
        font.pixelSize: Math.max(1, Math.round(raiz.m(24)))
    }
    MouseArea {
        anchors.fill: parent
        enabled: !raiz.trabajando
        onClicked: raiz.cerrado()
    }
}

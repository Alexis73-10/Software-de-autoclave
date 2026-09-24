import QtQuick
import Tema

// Barra de navegación inferior: solo la fila de iconos, sin fondo propio.
// La dimensiona quien la usa (normalmente el slot "pie" de TarjetaContenido).
// Recibe una lista de botones: [{icono: "casa", activo: true, accion: function(){...}}, ...]
// Activo e inactivo se ven igual por ahora: la diferencia visual la define
// el diseñador en las pantallas que faltan.
Item {
    id: raiz
    property var botones: []
    property string version: ""   // ej. "V: 1.0" — dejar vacío si no aplica

    // Ruta de assets: ajustar si la ubicación final de los SVG cambia
    property string carpetaIconos: "../../assets/iconos/mono/"

    Row {
        anchors.centerIn: parent
        spacing: Escala.px(64)

        Repeater {
            model: raiz.botones
            delegate: Rectangle {
                width: Escala.px(68); height: Escala.px(68)
                radius: Escala.px(12)
                color: "transparent"

                Image {
                    anchors.centerIn: parent
                    width: Escala.px(48); height: Escala.px(48)
                    source: raiz.carpetaIconos + modelData.icono + ".svg"
                    sourceSize.width: width
                    sourceSize.height: height
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: if (modelData.accion) modelData.accion()
                }
            }
        }
    }

    Text {
        visible: raiz.version.length > 0
        text: raiz.version
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Escala.px(16)
        color: Colores.textoGuia
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(16)   // meta_version de estilos_de_texto.csv
        font.weight: Tipografia.pesoMedium
    }
}

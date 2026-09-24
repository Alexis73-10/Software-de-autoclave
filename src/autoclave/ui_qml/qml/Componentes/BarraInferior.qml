import QtQuick
import Tema

// Barra inferior de navegación (1080x168). Recibe una lista de botones:
// [{icono: "casa", activo: true, accion: function(){...}}, ...]
Rectangle {
    id: raiz
    property var botones: []

    width: Escala.px(Escala.anchoDiseno)
    height: Escala.px(168)
    color: Colores.fondoTarjeta

    // Ruta de assets: ajustar si la ubicación final de los SVG cambia.
    // Botón activo usa la variante color/, inactivo la mono/.
    property string carpetaIconos: "../../assets/iconos/"

    Row {
        anchors.centerIn: parent
        spacing: Escala.px(64)

        Repeater {
            model: raiz.botones
            delegate: Rectangle {
                width: Escala.px(68); height: Escala.px(68)
                radius: Escala.px(12)
                color: modelData.activo ? Colores.accionPrimario : "transparent"

                Image {
                    anchors.centerIn: parent
                    width: Escala.px(28); height: Escala.px(28)
                    source: raiz.carpetaIconos + (modelData.activo ? "color/" : "mono/") +
                            modelData.icono + ".svg"
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
}

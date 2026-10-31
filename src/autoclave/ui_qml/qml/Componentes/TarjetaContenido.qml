import QtQuick
import QtQuick.Layouts
import Tema

// Tarjeta blanca flotante para el área de contenido debajo de la barra
// superior. La dimensiona quien la usa. radio_contenedor=28 de
// 06_MEDIDAS/medidas.csv (NO el radius-lg=14 de tokens.css — inconsistencia
// entre los dos archivos del diseñador, confirmar con él cuál es correcto).
// Dos slots: "contenido" (se estira) y "pie" (alto fijo abajo, ej. BarraInferior).
Rectangle {
    default property alias contenido: zonaContenido.children
    property alias pie: zonaPie.children

    radius: Escala.px(28)
    color: Colores.fondoTarjeta

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            id: zonaContenido
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1   // en un Layout, height no fija el alto
            color: "#E6E6E6"   // borde_divisor de tokens.css
            visible: zonaPie.children.length > 0
        }

        Item {
            id: zonaPie
            Layout.fillWidth: true
            Layout.preferredHeight: Escala.px(168)
        }
    }
}

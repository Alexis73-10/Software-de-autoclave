import QtQuick
import Tema

// Selector de segmentos de ancho igual (número de puertas, nivel de
// enfriamiento). `opciones`: [{valor, etiqueta, habilitada}]. `valor` es el
// elegido (-1 = ninguno). Solo avisa (`elegido`); la pantalla guarda el valor.
Item {
    id: raiz

    property var opciones: []
    property int valor: -1
    property bool habilitado: true

    signal elegido(int valor)

    height: Escala.px(88)
    opacity: habilitado ? 1 : 0.4

    Row {
        anchors.fill: parent
        Repeater {
            model: raiz.opciones
            delegate: Rectangle {
                id: segmento
                required property var modelData
                required property int index
                readonly property bool activo: modelData.valor === raiz.valor
                readonly property bool libre: raiz.habilitado && modelData.habilitada !== false
                width: raiz.width / raiz.opciones.length
                height: raiz.height
                radius: Escala.px(8)
                color: activo ? Colores.accionPrimario : Colores.fondoTarjeta
                border.width: activo ? 0 : Escala.px(1)
                border.color: Colores.bordeCampo
                opacity: libre ? 1 : 0.4
                // separación visual entre segmentos sin perder el área táctil
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: Escala.px(4)
                    radius: Escala.px(6)
                    color: "transparent"
                    border.width: 0
                    // T21 (FC-10): si la etiqueta no cabe en el segmento, la letra
                    // baja (HorizontalFit) hasta Escala.fuenteMinima; nunca se recorta
                    Text {
                        anchors.centerIn: parent
                        width: Math.min(implicitWidth, parent.width - Escala.px(16))
                        fontSizeMode: Text.HorizontalFit
                        minimumPixelSize: Escala.fuenteMinima
                        text: segmento.modelData.etiqueta
                        color: segmento.activo ? "white" : Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                        font.weight: segmento.activo ? Tipografia.pesoBold : Tipografia.pesoSemiBold
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: segmento.libre
                    onClicked: raiz.elegido(segmento.modelData.valor)
                }
            }
        }
    }
}

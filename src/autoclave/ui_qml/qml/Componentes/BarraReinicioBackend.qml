import QtQuick
import Tema
import Autoclave.I18n

// Tanda 26 (ARQ-D5): el backend se reinició con esta pantalla abierta
// (reasignación de E/S, caída relanzada por el lanzador). Mientras el arranque
// del backend nuevo no termina, esta capa cubre la pantalla con la barra de
// etapas reales (sin la animación de la intro) y no deja pasar toques: el
// control sigue retenido con todo apagado. Solo dibuja; el estado lo da
// `progreso` (bridge/progreso_arranque.py: fraccion, proceso).
Rectangle {
    id: raiz
    property QtObject progreso: null

    color: Colores.fondoMarinoOscuro

    // Ningún toque pasa a la pantalla de debajo
    MouseArea { anchors.fill: parent }

    Column {
        anchors.centerIn: parent
        width: parent.width * 0.8
        spacing: Escala.px(28)

        Text {
            objectName: "tituloReinicioBackend"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: I18n.t("arranque.reinicio_titulo", I18n.lang)
            color: Colores.textoSobreAccion
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(38)
        }

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: I18n.t("arranque.reinicio_detalle", I18n.lang)
            color: Colores.textoSobreAccion
            opacity: 0.85
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(28)
        }

        // Riel y relleno, como la barra de la intro
        Item {
            width: parent.width
            height: Escala.px(14)
            Rectangle {
                anchors.fill: parent
                radius: height / 2
                color: Colores.textoSobreAccion
                opacity: 0.25
            }
            Rectangle {
                objectName: "rellenoReinicioBackend"
                width: parent.width * Math.max(0, Math.min(1, raiz.progreso?.fraccion ?? 0))
                height: parent.height
                radius: height / 2
                color: Colores.textoSobreAccion
                opacity: 0.9
                Behavior on width { NumberAnimation { duration: 250; easing.type: Easing.OutQuad } }
            }
        }

        Text {
            objectName: "procesoReinicioBackend"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
            readonly property string clave: "arranque." + (raiz.progreso?.proceso ?? "")
            text: I18n.existe(clave, I18n.lang) ? I18n.t(clave, I18n.lang) : ""
            color: Colores.textoSobreAccion
            opacity: 0.9
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoMedium
            font.pixelSize: Escala.fuente(30)
        }
    }
}

import QtQuick
import Tema

// Ventana flotante genérica de SOLO VISUALIZACIÓN (D-21), superpuesta dentro de
// la misma pantalla: fondo atenuado (tocarlo cierra), tarjeta blanca redondeada
// con título y botón de cierre arriba a la derecha, y el contenido debajo.
// DISEÑO PROVISIONAL: el mockup v3 no la tiene; la valida el diseñador.
// Medidas en px del mockup escaladas con `escala` (convención m(), D-18).
// No reutiliza PanelModal.qml: ese usa Escala.px y un botón CERRAR fijo abajo
// que le quita alto a la gráfica de Último ciclo.
Item {
    id: raiz

    property real escala: 1
    property string titulo: ""
    // Alto deseado de la tarjeta en px del mockup; se limita al alto disponible
    property real altoTarjeta: 1200
    // Zona de contenido, debajo del título y su línea (ancho y alto en px reales)
    default property alias contenido: zona.data
    readonly property real anchoContenido: zona.width
    readonly property real altoContenido: zona.height
    readonly property bool abierta: visible

    signal mostrada()
    signal cerrada()

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    function abrir() {
        if (visible) return
        visible = true
        mostrada()
    }
    function cerrar() {
        if (!visible) return
        visible = false
        cerrada()
    }

    anchors.fill: parent
    visible: false
    z: 100

    Rectangle {
        objectName: "fondoVentana"
        anchors.fill: parent
        color: "#99000000"
        MouseArea { anchors.fill: parent; onClicked: raiz.cerrar() }
    }

    Rectangle {
        id: tarjeta
        objectName: "tarjetaVentana"
        x: raiz.m(34)
        width: parent.width - 2 * x
        height: Math.min(raiz.m(raiz.altoTarjeta), parent.height - raiz.m(160))
        anchors.verticalCenter: parent.verticalCenter
        radius: raiz.m(26)
        color: Colores.fondoTarjeta
        MouseArea { anchors.fill: parent }   // no dejar pasar el toque al fondo

        Text {
            id: textoTitulo
            x: raiz.m(48)
            width: botonCerrar.x - x - raiz.m(24)
            y: raiz.m(78) - baselineOffset
            elide: Text.ElideRight
            text: raiz.titulo
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(32)
        }

        // Botón de cierre: aro gris con una X dibujada (no hay icono de cerrar en assets)
        Item {
            id: botonCerrar
            objectName: "botonCerrarVentana"
            width: raiz.m(88); height: width
            x: tarjeta.width - width - raiz.m(28)
            y: raiz.m(24)
            Rectangle {
                anchors.centerIn: parent
                width: raiz.m(64); height: width; radius: width / 2
                color: Colores.fondoSutil
                border.width: raiz.m(2); border.color: Colores.bordeDivisor
            }
            Repeater {
                model: [45, -45]
                Rectangle {
                    required property int modelData
                    anchors.centerIn: parent
                    width: raiz.m(30); height: raiz.m(4); radius: height / 2
                    rotation: modelData
                    color: Colores.textoPrimario
                }
            }
            MouseArea { anchors.fill: parent; onClicked: raiz.cerrar() }
        }

        Rectangle {
            id: linea
            x: raiz.m(48); y: raiz.m(124)
            width: tarjeta.width - 2 * x; height: raiz.m(2)
            color: Colores.bordeDivisor
        }

        Item {
            id: zona
            objectName: "zonaVentana"
            x: raiz.m(48)
            width: tarjeta.width - 2 * x
            anchors.top: linea.bottom
            anchors.topMargin: raiz.m(24)
            anchors.bottom: parent.bottom
            anchors.bottomMargin: raiz.m(36)
            clip: true
        }
    }
}

import QtQuick
import Tema

// PROVISIONAL (sin diseño): cuadro de notificaciones del software que abre la
// campana. Arriba, los avisos de seguridad (paro, estado seguro, NO ABRIR,
// modo prueba; U1 de la tanda 2, antes franja superior de E5); debajo, la
// categoría "Alertas y avisos": al tocarla se despliega/pliega el listado de
// alarmas activas (mismo modelo que la pantalla de ciclo).
PanelModal {
    id: raiz
    altoTarjeta: Escala.px(1400)

    property var alarmas: null            // AlarmListModel de UiBridge
    property QtObject puente: null        // UiBridge: avisos de seguridad
    property QtObject comandosSistema: null   // "Confirmar y llevar a estado seguro"
    property string rotuloAlertas: ""
    property string textoSinAlarmas: ""
    property bool expandido: false
    readonly property int conteo: alarmas?.count ?? 0

    // Para la insignia de la campana de la pantalla que contiene el panel
    readonly property int conteoTotal: conteo + seguridad.conteo
    readonly property bool urgente: seguridad.urgente
    readonly property bool parpadeo: seguridad.confirmar
    readonly property bool avisoEnCurso: seguridad.enCurso

    onVisibleChanged: if (!visible) expandido = false

    // El paro y la confirmación pendiente abren el panel solos (al aparecer y
    // al crear la pantalla con ellos ya activos) y no dejan cerrarlo mientras
    // duren: deben verse sin tocar la campana (revisión U1: SAF-01/TMG-01).
    // Encima de los demás modales de la pantalla (SAF-02).
    z: 200
    bloqueado: seguridad.urgente
    onBloqueadoChanged: if (bloqueado) abrir()
    Component.onCompleted: if (bloqueado) abrir()

    Column {
        id: columna
        width: parent.width
        spacing: 0

        SeccionEstadoSeguro {
            id: seguridad
            objectName: "seccionEstadoSeguro"
            width: parent.width
            puente: raiz.puente
            comandos: raiz.comandosSistema
            bottomPadding: seguridad.conteo > 0 ? Escala.px(24) : 0
        }

        // Encabezado de la categoría: toca para desplegar/plegar
        Item {
            width: parent.width
            height: Escala.px(96)

            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: raiz.rotuloAlertas
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(28)
            }
            Rectangle {
                anchors.right: chevron.left
                anchors.rightMargin: Escala.px(20)
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(height, conteoTexto.implicitWidth + Escala.px(20))
                height: Escala.px(40); radius: height / 2
                color: raiz.conteo > 0 ? Colores.accionPrimario : Colores.bordeCampo
                Text {
                    id: conteoTexto
                    anchors.centerIn: parent
                    text: raiz.conteo
                    color: "white"
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(22)
                }
            }
            Image {
                id: chevron
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: Escala.px(40); height: width
                source: "../../assets/iconos/color/" + (raiz.expandido ? "chevron_arriba" : "chevron_abajo") + ".svg"
                sourceSize.width: width
                sourceSize.height: height
            }
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width; height: Escala.px(2)
                color: "#E6E6E6"
            }
            MouseArea { anchors.fill: parent; onClicked: raiz.expandido = !raiz.expandido }
        }

        Text {
            visible: raiz.expandido && raiz.conteo === 0
            topPadding: Escala.px(24)
            text: raiz.textoSinAlarmas
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(24)
        }
    }

    ListView {
        visible: raiz.expandido
        y: columna.y + seguridad.height + Escala.px(96)
        width: parent.width
        height: parent.height - y
        clip: true
        model: raiz.alarmas
        delegate: FilaAlarma {
            required property var model
            width: ListView.view.width
            idAlarma: model.id
            descripcion: model.description
            prioridad: model.priority
        }
    }
}

import QtQuick
import Tema
import Autoclave.I18n

// PROVISIONAL (sin diseño): cuadro de notificaciones del software que abre la
// campana. U4 (tanda 2, D3): agrupado por nivel del catálogo, cada grupo con
// cabecera y contador: "Emergencia / Fallas" (sin conexión, tarjeta
// desconectada o sin datos, paro, estado seguro con su botón de confirmar y
// las alarmas EMERGENCIA), "Alarmas" (NO ABRIR y las FALLA) y "Avisos" (modo
// prueba y las ALERTA). Las filas de seguridad salen de SeccionEstadoSeguro.
// U4: ya no se abre solo ni queda bloqueado (antes, corrección SAF-01 de U1):
// el paro y el estado seguro se ven sin abrirlo en la tarjeta de alarmas de
// Preciclo (y de Ciclo en curso) y en la insignia roja de la campana.
PanelModal {
    id: raiz
    altoTarjeta: Escala.px(1400)

    property var alarmas: null            // AlarmListModel de UiBridge
    property QtObject puente: null        // UiBridge: avisos de seguridad
    property QtObject comandosSistema: null   // "Confirmar y llevar a estado seguro"
    property string rotuloAlertas: ""     // sin uso desde U4 (grupos por nivel)
    property string textoSinAlarmas: ""
    readonly property int conteo: alarmas?.count ?? 0

    // Para la insignia de la campana de la pantalla que contiene el panel
    readonly property int conteoTotal: conteo + seguridad.conteoTotal
    readonly property bool urgente: seguridad.urgente
    readonly property bool parpadeo: seguridad.parpadeo
    readonly property bool avisoEnCurso: seguridad.enCurso

    // Encima de los demás modales de la pantalla (SAF-02 de U1)
    z: 200

    onVisibleChanged: if (!visible) { grupoAlarmas.expandido = false; grupoAvisos.expandido = false }

    // Nivel del catálogo (nombre de /status) → grupo. Desconocido: el más
    // llamativo (como UiBridge.prioridad_de).
    function grupoDe(nivel) {
        if (nivel === "FALLA") return "alarma"
        if (nivel === "ALERTA" || nivel === "INFORMATIVO") return "aviso"
        return "emergencia"
    }

    // Solo para los estados agregados (insignia, conteo total)
    SeccionEstadoSeguro {
        id: seguridad
        visible: false
        puente: raiz.puente
        comandos: raiz.comandosSistema
    }

    component Grupo: Column {
        id: g
        property string seccion: ""
        property string titulo: ""
        property bool expandido: false
        property int conteoAlarmas: 0
        readonly property int conteo: filas.conteo + conteoAlarmas

        function recontar() {
            let n = 0
            for (let i = 0; i < repetidor.count; i++) {
                const fila = repetidor.itemAt(i)
                if (fila && fila.enGrupo)
                    n++
            }
            conteoAlarmas = n
        }

        width: parent ? parent.width : 0

        // Cabecera: toca para desplegar/plegar
        Item {
            objectName: "cabecera_" + g.seccion
            property int conteo: g.conteo
            width: g.width
            height: Escala.px(96)

            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: g.titulo
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
                color: g.conteo === 0 ? Colores.bordeCampo
                     : g.seccion === "emergencia" ? Colores.alarmaAlta
                     : Colores.accionPrimario
                Text {
                    id: conteoTexto
                    anchors.centerIn: parent
                    text: g.conteo
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
                source: "../../assets/iconos/color/" + (g.expandido ? "chevron_arriba" : "chevron_abajo") + ".svg"
                sourceSize.width: width
                sourceSize.height: height
            }
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width; height: Escala.px(2)
                color: "#E6E6E6"
            }
            MouseArea { anchors.fill: parent; onClicked: g.expandido = !g.expandido }
        }

        SeccionEstadoSeguro {
            id: filas
            objectName: "seguridad_" + g.seccion
            visible: g.expandido && conteo > 0
            width: g.width
            grupo: g.seccion
            puente: raiz.puente
            comandos: raiz.comandosSistema
            topPadding: Escala.px(16)
        }

        Repeater {
            id: repetidor
            model: raiz.alarmas
            onItemAdded: Qt.callLater(g.recontar)
            onItemRemoved: Qt.callLater(g.recontar)
            delegate: FilaAlarma {
                required property var model
                readonly property bool enGrupo: raiz.grupoDe(model.level ?? "") === g.seccion
                visible: g.expandido && enGrupo
                width: g.width
                idAlarma: model.id
                descripcion: model.description
                prioridad: model.priority
            }
        }
    }

    Flickable {
        anchors.fill: parent
        contentHeight: columna.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: columna
            width: parent.width
            spacing: 0

            Grupo {
                id: grupoEmergencia
                objectName: "grupoEmergencia"
                seccion: "emergencia"
                titulo: I18n.t("notificaciones.grupo_emergencia", I18n.lang)
                expandido: true
            }
            Grupo {
                id: grupoAlarmas
                objectName: "grupoAlarmas"
                seccion: "alarma"
                titulo: I18n.t("notificaciones.grupo_alarmas", I18n.lang)
            }
            Grupo {
                id: grupoAvisos
                objectName: "grupoAvisos"
                seccion: "aviso"
                titulo: I18n.t("notificaciones.grupo_avisos", I18n.lang)
            }

            Text {
                objectName: "textoSinNotificaciones"
                visible: raiz.conteoTotal === 0
                topPadding: Escala.px(24)
                text: raiz.textoSinAlarmas
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(24)
            }
        }
    }
}

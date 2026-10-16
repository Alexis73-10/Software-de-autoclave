pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// PROVISIONAL (sin diseño): avisos de seguridad sobre todas las pantallas
// (E5, tanda 2026-10-14; fin de ciclo §5 y §15; I18N-28).
// - Paro activo: "PARO DE EMERGENCIA — NO ABRIR".
// - Cámara no segura: "NO ABRIR" con el motivo (en cualquier estado).
// - Paro liberado con el estado seguro pendiente: botón "Confirmar y llevar a
//   estado seguro" (cualquier operador, sin rol).
// - Estado seguro en curso: aviso informativo.
// - Modo prueba: "MODO PRUEBA ACTIVO — los ciclos no son válidos...".
// Sin conexión, el puente ya entrega noAbrir = true (falla cerrada).
Column {
    id: raiz
    property QtObject puente: null
    property QtObject comandos: null    // ComandosSistema

    readonly property bool paro: puente?.paroActivo ?? false
    readonly property bool noAbrir: puente?.noAbrir ?? true
    readonly property bool confirmar: (puente?.estadoSeguroRequiereConfirmacion ?? false) && !paro
    readonly property bool enCurso: (puente?.estadoSeguroActivo ?? false) && !confirmar && !paro
    readonly property bool modoPrueba: puente?.modoPrueba ?? false

    spacing: 0

    component Franja: Rectangle {
        id: franja
        property string texto: ""
        property string detalle: ""
        property color fondo: "#C62828"
        width: raiz.width
        height: columna.implicitHeight + Escala.px(20)
        color: fondo
        Column {
            id: columna
            anchors.centerIn: parent
            width: parent.width - Escala.px(32)
            spacing: Escala.px(4)
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: franja.texto
                color: "white"
                wrapMode: Text.WordWrap
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(26)
            }
            Text {
                width: parent.width
                visible: franja.detalle.length > 0
                horizontalAlignment: Text.AlignHCenter
                text: franja.detalle
                color: "white"
                wrapMode: Text.WordWrap
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(18)
            }
        }
    }

    Franja {
        objectName: "avisoParo"
        visible: raiz.paro
        texto: I18n.t("sistema.paro_no_abrir", I18n.lang)
    }
    Franja {
        objectName: "avisoNoAbrir"
        visible: raiz.noAbrir && !raiz.paro
        texto: I18n.t("sistema.no_abrir", I18n.lang)
        detalle: raiz.puente?.noAbrirMotivo ?? ""
    }
    Rectangle {
        objectName: "avisoConfirmarEstadoSeguro"
        visible: raiz.confirmar
        width: raiz.width
        height: Escala.px(150)
        color: "#E65100"
        Column {
            anchors.centerIn: parent
            spacing: Escala.px(10)
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                width: raiz.width - Escala.px(32)
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: I18n.t("sistema.paro_liberado", I18n.lang)
                color: "white"
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(18)
            }
            Rectangle {
                objectName: "botonConfirmarEstadoSeguro"
                anchors.horizontalCenter: parent.horizontalCenter
                width: textoBoton.implicitWidth + Escala.px(48)
                height: Escala.px(64)
                radius: Escala.px(32)
                color: "white"
                opacity: (raiz.comandos?.ocupado ?? false) ? 0.5 : 1.0
                Text {
                    id: textoBoton
                    anchors.centerIn: parent
                    text: I18n.t("sistema.confirmar_estado_seguro", I18n.lang)
                    color: "#E65100"
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(22)
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: raiz.comandos?.confirmarEstadoSeguro()
                }
            }
        }
    }
    Franja {
        objectName: "avisoEstadoSeguro"
        visible: raiz.enCurso
        fondo: "#455A64"
        texto: I18n.t("sistema.estado_seguro_en_curso", I18n.lang)
    }
    Franja {
        objectName: "avisoModoPrueba"
        visible: raiz.modoPrueba
        fondo: "#F9A825"
        texto: I18n.t("sistema.modo_prueba", I18n.lang)
    }
}

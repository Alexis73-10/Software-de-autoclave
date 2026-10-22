pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Información del sistema (O2d, tanda 6; mockup 8). Solo lectura,
// en grupos de clave–valor: Equipo, Software y tarjeta, Uso y mantenimiento,
// Configuración vigente (con chips de impresora y red).
Item {
    id: raiz
    objectName: "opcionesInfoSistema"
    readonly property bool cambiosPendientes: false

    InfoSistemaController {
        id: control
        objectName: "infoSistemaController"
    }
    readonly property alias controlador: control
    Component.onCompleted: control.cargar()

    Flickable {
        anchors.fill: parent
        contentHeight: columna.height
        clip: true
        Column {
            id: columna
            width: parent.width
            spacing: Escala.px(10)

            Text {
                objectName: "errorInfoSistema"
                visible: control.mensaje !== ""
                width: parent.width
                wrapMode: Text.WordWrap
                text: control.mensaje !== "" ? I18n.t(control.mensaje, I18n.lang) : ""
                color: Colores.peligroTexto
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(22)
            }

            Repeater {
                model: control.grupos
                delegate: Column {
                    id: grupo
                    required property var modelData
                    objectName: "grupoInfo_" + modelData.grupo
                    width: columna.width
                    spacing: 0
                    Text {
                        topPadding: Escala.px(18)
                        bottomPadding: Escala.px(6)
                        text: I18n.t("info_sistema.grupo_" + grupo.modelData.grupo, I18n.lang).toUpperCase()
                        color: Colores.accionPrimarioTexto
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: Escala.fuente(24)
                        font.letterSpacing: Escala.px(1.5)
                    }
                    Repeater {
                        model: grupo.modelData.filas
                        delegate: Item {
                            id: fila
                            required property var modelData
                            objectName: "infoFila_" + modelData.clave
                            readonly property string texto: modelData.valorClave !== ""
                                                            ? I18n.t(modelData.valorClave, I18n.lang)
                                                            : (modelData.valor !== "" ? modelData.valor : "—")
                            width: grupo.width
                            height: Escala.px(84)
                            Text {
                                anchors.left: parent.left; anchors.leftMargin: Escala.px(12)
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width * 0.5
                                elide: Text.ElideRight
                                text: I18n.t("info_sistema.rotulo_" + fila.modelData.clave, I18n.lang)
                                color: Colores.textoSecundario
                                font.family: Tipografia.familia
                                font.pixelSize: Escala.fuente(25)
                            }
                            Rectangle {
                                visible: fila.modelData.chip !== ""
                                anchors.right: parent.right; anchors.rightMargin: Escala.px(12)
                                anchors.verticalCenter: parent.verticalCenter
                                width: textoChip.implicitWidth + Escala.px(28); height: Escala.px(46)
                                radius: height / 2
                                color: fila.modelData.chip === "ok" ? Colores.accionFondoTenue : Colores.advertenciaFondo
                                Text {
                                    id: textoChip
                                    anchors.centerIn: parent
                                    text: fila.texto
                                    color: fila.modelData.chip === "ok" ? Colores.menuVerdeTexto : Colores.advertenciaTexto
                                    font.family: Tipografia.familia
                                    font.weight: Tipografia.pesoSemiBold
                                    font.pixelSize: Escala.fuente(21)
                                }
                            }
                            Text {
                                visible: fila.modelData.chip === ""
                                anchors.right: parent.right; anchors.rightMargin: Escala.px(12)
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width * 0.47
                                horizontalAlignment: Text.AlignRight
                                elide: Text.ElideLeft
                                text: fila.texto
                                color: fila.modelData.valorClave === "menu.vencido" ? Colores.peligroTexto
                                                                                   : Colores.textoPrimario
                                font.family: Tipografia.familia
                                font.weight: Tipografia.pesoBold
                                font.pixelSize: Escala.fuente(27)
                            }
                            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Colores.bordeDivisor }
                        }
                    }
                }
            }
        }
    }
}

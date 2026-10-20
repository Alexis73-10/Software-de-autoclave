pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Mantenimiento (M1, tanda 3). PROVISIONAL (sin diseño final):
// próximo vencimiento ("VENCIDO" si pasó), último mantenimiento, ciclos
// restantes y "Registrar mantenimiento realizado" con el tipo. Solo informa:
// un mantenimiento vencido nunca impide un ciclo. Los intervalos se configuran
// por PUT /maintenance/config (defecto PROVISIONAL: 180 días, sin límite de
// ciclos); su pantalla de edición queda en Parámetros del sistema (PySide).
Item {
    id: raiz
    objectName: "opcionesMantenimiento"

    property bool edicionPermitida: false      // estado y rol (OpcionesController)
    property string tipoElegido: "preventivo"

    MantenimientoController {
        id: control
        objectName: "mantenimientoController"
    }
    readonly property alias controlador: control
    Component.onCompleted: control.cargar()

    component Dato: Item {
        id: dato
        property string rotulo: ""
        property string valor: ""
        property color tinta: Colores.textoPrimario
        width: parent ? parent.width : 0
        height: Escala.px(92)
        Text {
            anchors.left: parent.left; anchors.leftMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.55
            elide: Text.ElideRight
            text: dato.rotulo
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(26)
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.4
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideLeft
            text: dato.valor
            color: dato.tinta
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(30)
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Colores.bordeDivisor }
    }

    Rectangle {
        id: bandaError
        objectName: "errorMantenimiento"
        visible: control.mensaje !== ""
        anchors.top: parent.top
        width: parent.width
        height: visible ? Escala.px(72) : 0
        radius: Escala.px(12)
        color: Colores.peligroFondo
        Text {
            anchors.fill: parent; anchors.margins: Escala.px(16)
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap
            text: control.mensaje !== "" ? I18n.t(control.mensaje, I18n.lang) : ""
            color: Colores.peligroTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }
        MouseArea { anchors.fill: parent; onClicked: control.limpiarMensaje() }
    }

    Column {
        anchors.top: bandaError.bottom; anchors.topMargin: Escala.px(8)
        width: parent.width
        spacing: Escala.px(6)

        Dato {
            objectName: "datoProximoVencimiento"
            rotulo: I18n.t("menu.proximo_vencimiento", I18n.lang)
            valor: control.vencido ? I18n.t("menu.vencido", I18n.lang) : control.proximo
            tinta: control.vencido ? Colores.peligroTexto : Colores.textoPrimario
        }
        Dato {
            objectName: "datoUltimoMantenimiento"
            rotulo: I18n.t("menu.ultimo_mantenimiento", I18n.lang)
            valor: control.ultimo
        }
        Dato {
            objectName: "datoCiclosRestantes"
            rotulo: I18n.t("menu.ciclos_restantes", I18n.lang)
            valor: control.ciclosRestantes
        }
        Text {
            objectName: "notaMantenimientoSinDato"
            visible: control.estado === "sin_dato"
            width: parent.width
            wrapMode: Text.WordWrap
            text: I18n.t("opciones.mant_sin_dato", I18n.lang)
            color: Colores.advertenciaTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }

        Text {
            width: parent.width
            topPadding: Escala.px(24)
            text: I18n.t("opciones.mant_tipo", I18n.lang)
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(24)
        }
        Flow {
            width: parent.width
            spacing: Escala.px(10)
            Repeater {
                model: control.tipos
                delegate: Rectangle {
                    id: chip
                    required property string modelData
                    readonly property bool activo: modelData === raiz.tipoElegido
                    objectName: "tipo_" + modelData
                    width: textoChip.implicitWidth + Escala.px(48)
                    height: Escala.px(80)
                    radius: Escala.px(40)
                    color: activo ? Colores.accionPrimario : Colores.fondoSutil
                    Text {
                        id: textoChip
                        anchors.centerIn: parent
                        text: I18n.t("opciones.mant_tipo_" + chip.modelData, I18n.lang)
                        color: chip.activo ? "white" : Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: Escala.fuente(24)
                    }
                    MouseArea { anchors.fill: parent; onClicked: raiz.tipoElegido = chip.modelData }
                }
            }
        }
        Rectangle {
            objectName: "botonRegistrarMantenimiento"
            readonly property bool habilitado: raiz.edicionPermitida
            width: parent.width; height: Escala.px(96)
            radius: Escala.px(12)
            color: Colores.accionPrimario
            opacity: habilitado ? 1.0 : 0.4
            Text {
                anchors.centerIn: parent
                text: I18n.t("opciones.mant_registrar", I18n.lang)
                color: "white"
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(28)
            }
            MouseArea {
                anchors.fill: parent
                enabled: parent.habilitado
                onClicked: confirmar.abrir()
            }
        }
    }

    DialogoConfirmacion {
        id: confirmar
        objectName: "confirmarMantenimiento"
        mensaje: I18n.t("opciones.mant_confirmar", I18n.lang,
                        { tipo: I18n.t("opciones.mant_tipo_" + raiz.tipoElegido, I18n.lang) })
        textoConfirmar: I18n.t("opciones.mant_registrar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        onConfirmado: { cerrar(); control.registrar(raiz.tipoElegido) }
    }
}

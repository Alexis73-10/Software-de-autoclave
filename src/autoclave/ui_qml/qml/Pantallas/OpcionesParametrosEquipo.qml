pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Parámetros del equipo (P2, tanda 5). Diseño PROVISIONAL (sin
// diseño final). Interruptor "Impresora habilitada" (data/impresora.json):
// técnico e ingeniero, con auditoría en el backend. Deshabilitada, el equipo
// no avisa por impresora desconectada; nunca bloquea un ciclo. Unidades
// (U1): temperatura °C/°F y presión kPa/bar/mbar (absolutas) o psi
// (psig, inHg de vacío); solo fuera de ciclo. Solo cambia lo que se muestra.
Item {
    id: raiz
    objectName: "opcionesParametrosEquipo"

    property bool edicionPermitida: false      // estado y rol (OpcionesController)
    property QtObject teclado: null            // PanelTeclado de la ventana

    ParametrosEquipoController {
        id: control
        objectName: "parametrosEquipoController"
    }
    readonly property alias controlador: control

    // Fila de opciones excluyentes (chips)
    component FilaOpciones: Column {
        id: fila
        property string rotulo: ""
        property var opciones: []
        property string elegida: ""
        signal elegir(string v)
        width: parent ? parent.width : 0
        spacing: Escala.px(8)
        Text {
            text: fila.rotulo
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(26)
        }
        Flow {
            width: parent.width
            spacing: Escala.px(10)
            Repeater {
                model: fila.opciones
                delegate: Rectangle {
                    id: chip
                    required property var modelData
                    readonly property bool activa: modelData.v === fila.elegida
                    objectName: fila.objectName + "_" + modelData.v
                    width: textoChip.implicitWidth + Escala.px(48)
                    height: Escala.px(72)
                    radius: Escala.px(36)
                    color: activa ? Colores.accionPrimario : Colores.fondoSutil
                    opacity: raiz.edicionPermitida && fila.elegida !== "" ? 1.0 : 0.5
                    Text {
                        id: textoChip
                        anchors.centerIn: parent
                        text: chip.modelData.t
                        color: chip.activa ? "white" : Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: Escala.fuente(24)
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: raiz.edicionPermitida && fila.elegida !== "" && !chip.activa
                        onClicked: fila.elegir(chip.modelData.v)
                    }
                }
            }
        }
    }
    Component.onCompleted: control.cargar()

    Rectangle {
        id: bandaError
        objectName: "errorParametrosEquipo"
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
        id: columna
        objectName: "columnaParametrosEquipo"
        anchors.top: bandaError.bottom; anchors.topMargin: Escala.px(8)
        width: parent.width
        spacing: Escala.px(6)

        // Fila con interruptor
        Rectangle {
            id: filaImpresora
            objectName: "filaImpresoraHabilitada"
            readonly property bool habilitado: raiz.edicionPermitida && control.impresoraConocida
            width: parent.width
            height: Escala.px(110)
            radius: Escala.px(12)
            color: Colores.fondoSutil
            opacity: habilitado ? 1.0 : 0.5
            Column {
                anchors.left: parent.left; anchors.leftMargin: Escala.px(16)
                anchors.right: estadoImpresora.left; anchors.rightMargin: Escala.px(16)
                anchors.verticalCenter: parent.verticalCenter
                Text {
                    width: parent.width
                    elide: Text.ElideRight
                    text: I18n.t("opciones.equipo_impresora", I18n.lang)
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(28)
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: I18n.t("opciones.equipo_impresora_ayuda", I18n.lang)
                    color: Colores.textoGuia
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(20)
                }
            }
            Rectangle {
                id: interruptor
                objectName: "interruptorImpresora"
                readonly property bool encendido: control.impresoraHabilitada
                anchors.right: parent.right; anchors.rightMargin: Escala.px(16)
                anchors.verticalCenter: parent.verticalCenter
                width: Escala.px(112); height: Escala.px(60)
                radius: height / 2
                color: encendido ? Colores.accionPrimario : Colores.bordeDivisor
                Rectangle {
                    width: parent.height - Escala.px(12); height: width
                    radius: width / 2
                    y: Escala.px(6)
                    x: interruptor.encendido ? parent.width - width - Escala.px(6) : Escala.px(6)
                    color: "white"
                }
            }
            Text {
                id: estadoImpresora
                objectName: "estadoImpresora"
                anchors.right: interruptor.left; anchors.rightMargin: Escala.px(16)
                anchors.verticalCenter: parent.verticalCenter
                text: !control.impresoraConocida ? "—"
                      : I18n.t(control.impresoraHabilitada ? "opciones.equipo_si" : "opciones.equipo_no",
                               I18n.lang)
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(24)
            }
            MouseArea {
                anchors.fill: parent
                enabled: filaImpresora.habilitado
                onClicked: control.fijarImpresora(!control.impresoraHabilitada)
            }
        }

        // ── Unidades (U1, tanda 5) ─────────────────────────────────────
        Text {
            width: parent.width
            topPadding: Escala.px(24)
            text: I18n.t("opciones.equipo_unidades", I18n.lang)
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(24)
        }
        FilaOpciones {
            objectName: "unidadTemperatura"
            rotulo: I18n.t("opciones.equipo_unidad_temperatura", I18n.lang)
            opciones: [{ v: "C", t: "°C" }, { v: "F", t: "°F" }]
            elegida: control.unidadTemperatura
            onElegir: (v) => control.fijarUnidades(v, control.unidadPresion)
        }
        FilaOpciones {
            objectName: "unidadPresion"
            rotulo: I18n.t("opciones.equipo_unidad_presion", I18n.lang)
            opciones: [{ v: "kPa", t: "kPa" }, { v: "bar", t: "bar" }, { v: "mbar", t: "mbar" },
                       { v: "psi", t: "psig / inHg" }]
            elegida: control.unidadPresion
            onElegir: (v) => control.fijarUnidades(control.unidadTemperatura, v)
        }
        Text {
            width: parent.width
            wrapMode: Text.WordWrap
            text: I18n.t("opciones.equipo_unidades_ayuda", I18n.lang)
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(20)
        }
    }
}

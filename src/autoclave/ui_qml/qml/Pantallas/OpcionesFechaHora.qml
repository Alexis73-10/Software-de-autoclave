pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Fecha y hora (O2c, tanda 6). SOLO LECTURA (decisión 1.10): hora
// grande, fecha, zona horaria y aviso si el reloj es anterior a la
// instalación (M1-01). Sin campos de edición ni botón Aplicar: el reloj se
// ajusta en Windows (soporte).
Item {
    id: raiz
    objectName: "opcionesFechaHora"
    readonly property bool cambiosPendientes: false

    FechaHoraController {
        id: control
        objectName: "fechaHoraController"
    }
    readonly property alias controlador: control
    Component.onCompleted: control.cargar()

    readonly property var _locale: Qt.locale(I18n.lang === "en" ? "en_US" : "es_CO")

    Column {
        width: parent.width
        spacing: Escala.px(18)

        Rectangle {
            objectName: "avisoRelojAnterior"
            visible: control.relojAnterior
            width: parent.width; height: visible ? textoAviso.implicitHeight + Escala.px(36) : 0
            radius: Escala.px(12)
            color: Colores.peligroFondo
            Text {
                id: textoAviso
                x: Escala.px(18); width: parent.width - 2 * x
                anchors.verticalCenter: parent.verticalCenter
                wrapMode: Text.WordWrap
                text: I18n.t("fecha_hora.reloj_anterior", I18n.lang, { fecha: control.instalacion.substring(0, 10) })
                color: Colores.peligroTexto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(24)
            }
        }

        Item { width: 1; height: Escala.px(40) }

        Text {
            objectName: "horaGrande"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: control.hora
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(150)
        }
        Text {
            objectName: "fechaLarga"
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: control.fechaIso === "" ? "—"
                  : Qt.formatDate(new Date(control.fechaIso + "T12:00:00"), raiz._locale, "dddd d MMMM yyyy")
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(40)
        }

        Item { width: 1; height: Escala.px(40) }

        Repeater {
            model: [
                { clave: "zona", valor: control.zona },
                { clave: "fecha_iso", valor: control.fechaIso },
                { clave: "instalacion", valor: control.instalacion !== "" ? control.instalacion.substring(0, 10) : "—" },
                { clave: "fuente", valor: I18n.t("fecha_hora.fuente_pc", I18n.lang) }
            ]
            delegate: Item {
                id: fila
                required property var modelData
                objectName: "datoFecha_" + modelData.clave
                width: parent ? parent.width : 0
                height: Escala.px(92)
                Text {
                    anchors.left: parent.left; anchors.leftMargin: Escala.px(12)
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width * 0.45
                    elide: Text.ElideRight
                    text: I18n.t("fecha_hora.rotulo_" + fila.modelData.clave, I18n.lang)
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(26)
                }
                Text {
                    anchors.right: parent.right; anchors.rightMargin: Escala.px(12)
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width * 0.53
                    horizontalAlignment: Text.AlignRight
                    elide: Text.ElideLeft
                    text: fila.modelData.valor || "—"
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(28)
                }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Colores.bordeDivisor }
            }
        }

        Text {
            objectName: "explicacionSoloLectura"
            width: parent.width
            topPadding: Escala.px(24)
            wrapMode: Text.WordWrap
            text: I18n.t("fecha_hora.explicacion", I18n.lang)
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }
        Text {
            objectName: "errorFechaHora"
            visible: control.mensaje !== ""
            width: parent.width
            wrapMode: Text.WordWrap
            text: control.mensaje !== "" ? I18n.t(control.mensaje, I18n.lang) : ""
            color: Colores.peligroTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }
    }
}

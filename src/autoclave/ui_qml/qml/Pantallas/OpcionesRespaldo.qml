pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Respaldo (O2h, tanda 6; mockup 12 de docs/mockups/tanda6/APROBADO.md).
// Estado de la USB, casillas de qué exportar y "Exportar a USB"; lista de
// respaldos de la USB con chip Válido / Rechazado (otro número de serie,
// versión, dañado) y "Restaurar seleccionado" con confirmación. Técnico e
// ingeniero, solo fuera de ciclo (`edicionPermitida` y el backend, 409).
Item {
    id: raiz
    objectName: "opcionesRespaldo"

    property bool edicionPermitida: false

    RespaldoController {
        id: control
        objectName: "respaldoController"
    }
    readonly property alias controlador: control
    Component.onCompleted: control.cargar()

    readonly property bool hayUsb: control.unidad !== ""

    function textoMotivo(m) {
        return I18n.existe("respaldo.motivo_" + m, I18n.lang) ? I18n.t("respaldo.motivo_" + m, I18n.lang)
                                                              : I18n.t("respaldo.motivo_invalido", I18n.lang)
    }

    component Boton: Rectangle {
        id: boton
        property string texto: ""
        property bool habilitado: true
        signal pulsado()
        height: Escala.px(92)
        radius: Escala.px(12)
        color: Colores.accionPrimario
        opacity: habilitado ? 1.0 : 0.4
        Text {
            anchors.centerIn: parent
            text: boton.texto
            color: "white"
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(27)
        }
        MouseArea { anchors.fill: parent; enabled: boton.habilitado; onClicked: boton.pulsado() }
    }

    Flickable {
        anchors.fill: parent
        contentHeight: columna.height + Escala.px(40)
        clip: true
        interactive: contentHeight > height

        Column {
            id: columna
            width: parent.width
            spacing: Escala.px(8)

            Rectangle {
                objectName: "mensajeRespaldo"
                visible: control.mensaje !== ""
                width: parent.width
                height: visible ? textoMensaje.implicitHeight + Escala.px(28) : 0
                radius: Escala.px(12)
                readonly property bool exito: control.mensaje === "respaldo.exportado"
                                              || control.mensaje.indexOf("respaldo.restaurado") === 0
                color: exito ? Colores.accionFondoTenue : Colores.peligroFondo
                Text {
                    id: textoMensaje
                    x: Escala.px(14); width: parent.width - Escala.px(28); anchors.verticalCenter: parent.verticalCenter
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                    text: control.mensaje !== "" ? I18n.t(control.mensaje, I18n.lang) : ""
                    color: parent.exito ? Colores.accionPrimarioTexto : Colores.peligroTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                }
                MouseArea { anchors.fill: parent; onClicked: control.limpiarMensaje() }
            }

            // ── USB ───────────────────────────────────────────────────
            Rectangle {
                objectName: "estadoUsb"
                width: parent.width
                height: Escala.px(100)
                radius: Escala.px(14)
                color: raiz.hayUsb ? Colores.accionFondoTenue : Colores.advertenciaFondo
                Text {
                    anchors.left: parent.left; anchors.leftMargin: Escala.px(20)
                    anchors.right: botonActualizar.left
                    anchors.verticalCenter: parent.verticalCenter
                    wrapMode: Text.WordWrap
                    text: raiz.hayUsb ? I18n.t("respaldo.usb_detectada", I18n.lang,
                                               { unidad: control.unidad, libre: control.libre })
                                      : I18n.t("respaldo.usb_no_detectada", I18n.lang)
                    color: raiz.hayUsb ? Colores.accionPrimarioTexto : Colores.advertenciaTexto
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(25)
                }
                Rectangle {
                    id: botonActualizar
                    objectName: "botonActualizarUsb"
                    anchors.right: parent.right; anchors.rightMargin: Escala.px(14)
                    anchors.verticalCenter: parent.verticalCenter
                    width: Escala.px(200); height: Escala.px(68); radius: Escala.px(10)
                    color: Colores.fondoTarjeta
                    border.color: Colores.bordeCampo
                    Text {
                        anchors.centerIn: parent
                        text: I18n.t("respaldo.actualizar", I18n.lang)
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(22)
                    }
                    MouseArea { anchors.fill: parent; onClicked: control.cargar() }
                }
            }

            // ── exportar ──────────────────────────────────────────────
            Text {
                width: parent.width
                topPadding: Escala.px(16)
                text: I18n.t("respaldo.exportar_titulo", I18n.lang)
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(30)
            }
            Repeater {
                model: control.listaPartes
                delegate: FilaInterruptor {
                    required property string modelData
                    objectName: "parte_" + modelData
                    width: columna.width
                    etiqueta: I18n.t("respaldo.parte_" + modelData, I18n.lang)
                    marcado: control.partes[modelData] === true
                    bloqueado: !raiz.edicionPermitida
                    onAlternado: control.fijarParte(modelData, !(control.partes[modelData] === true))
                }
            }
            Boton {
                objectName: "botonExportar"
                width: parent.width
                texto: I18n.t("respaldo.exportar", I18n.lang)
                habilitado: raiz.edicionPermitida && raiz.hayUsb
                onPulsado: control.exportar()
            }

            // ── restaurar ─────────────────────────────────────────────
            Text {
                width: parent.width
                topPadding: Escala.px(20)
                text: I18n.t("respaldo.restaurar_titulo", I18n.lang)
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(30)
            }
            Text {
                visible: control.respaldos.length === 0
                width: parent.width
                text: I18n.t("respaldo.sin_respaldos", I18n.lang)
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(22)
            }
            Repeater {
                model: control.respaldos
                delegate: Rectangle {
                    id: fila
                    required property var modelData
                    readonly property bool elegida: control.seleccion === modelData.archivo
                    objectName: "respaldo_" + modelData.archivo
                    width: columna.width
                    height: Escala.px(104)
                    radius: Escala.px(12)
                    color: elegida ? Colores.accionFondoTenue : Colores.fondoSutil
                    border.color: elegida ? Colores.accionPrimario : "transparent"
                    border.width: 2
                    Column {
                        anchors.left: parent.left; anchors.leftMargin: Escala.px(16)
                        anchors.right: chip.left; anchors.rightMargin: Escala.px(12)
                        anchors.verticalCenter: parent.verticalCenter
                        Text {
                            width: parent.width
                            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                            text: fila.modelData.archivo
                            color: Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoSemiBold
                            font.pixelSize: Escala.fuente(22)
                        }
                        Text {
                            width: parent.width
                            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                            text: fila.modelData.valido
                                  ? I18n.t("respaldo.detalle", I18n.lang,
                                           { serie: fila.modelData.serie, fecha: String(fila.modelData.fecha).replace("T", " ") })
                                  : raiz.textoMotivo(fila.modelData.motivo)
                                    + (fila.modelData.serie ? " (" + fila.modelData.serie + ")" : "")
                            color: fila.modelData.valido ? Colores.textoSecundario : Colores.peligroTexto
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(20)
                        }
                    }
                    Rectangle {
                        id: chip
                        anchors.right: parent.right; anchors.rightMargin: Escala.px(14)
                        anchors.verticalCenter: parent.verticalCenter
                        width: textoChip.implicitWidth + Escala.px(32); height: Escala.px(52)
                        radius: height / 2
                        color: fila.modelData.valido ? Colores.menuVerde : Colores.peligroFondo
                        Text {
                            id: textoChip
                            anchors.centerIn: parent
                            text: fila.modelData.valido ? I18n.t("respaldo.valido", I18n.lang)
                                                        : I18n.t("respaldo.rechazado", I18n.lang)
                            color: fila.modelData.valido ? "white" : Colores.peligroTexto
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoSemiBold
                            font.pixelSize: Escala.fuente(20)
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: fila.modelData.valido
                        onClicked: control.seleccionar(fila.modelData.archivo)
                    }
                }
            }
            Boton {
                objectName: "botonRestaurar"
                width: parent.width
                texto: I18n.t("respaldo.restaurar", I18n.lang)
                habilitado: raiz.edicionPermitida && control.seleccion !== ""
                onPulsado: dialogoRestaurar.abrir()
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("respaldo.nota", I18n.lang)
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(20)
            }
        }
    }

    DialogoConfirmacion {
        id: dialogoRestaurar
        objectName: "dialogoRestaurar"
        mensaje: I18n.t("respaldo.confirmar", I18n.lang, { archivo: control.seleccion })
        textoConfirmar: I18n.t("respaldo.restaurar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: Colores.peligroTexto
        onConfirmado: { cerrar(); control.restaurar() }
    }
}

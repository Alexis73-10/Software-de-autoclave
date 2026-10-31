pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Conectividad (O2g, tanda 6; mockup 11 de docs/mockups/tanda6/
// APROBADO.md). Red en solo lectura (Wi-Fi y señal, IP, Ethernet) con la nota
// "para cambiar la red se requiere soporte". Correo de ciclos: interruptor de
// envío, destinatarios con quitar, "+ Agregar destinatario" y "Enviar correo de
// prueba". La contraseña del servidor nunca se muestra (solo si está
// configurada). Admin e ingeniero editan; el técnico lo ve en solo lectura,
// con el motivo (decisión 1.9). El backend es la autoridad (403/409).
Item {
    id: raiz
    objectName: "opcionesConectividad"

    property QtObject teclado: null
    property string rol: ""
    property string estadoMaquina: ""

    ConectividadController {
        id: control
        objectName: "conectividadController"
        rol: raiz.rol
        estadoMaquina: raiz.estadoMaquina
    }
    readonly property alias controlador: control
    Component.onCompleted: control.cargar()

    readonly property bool editable: control.puedeEditar
    property string _nombreNuevo: ""

    function agregarDestinatario() {
        if (!raiz.editable || raiz.teclado === null)
            return
        // Modo acción (TEC-ACC-04): el correo se pide al Confirmar el nombre y
        // se agrega al Confirmar el correo; Cancelar en cualquier paso no envía
        raiz.teclado.abrirAlfanumericoAccion(I18n.t("conectividad.nombre_destinatario", I18n.lang), "", 40, false,
            function (nombre) {
                raiz._nombreNuevo = nombre
                Qt.callLater(function () {
                    raiz.teclado.abrirAlfanumericoAccion(I18n.t("conectividad.correo_destinatario", I18n.lang),
                        "", 254, false, function (correo) { control.agregar(raiz._nombreNuevo, correo) })
                })
            })
    }

    component Titulo: Text {
        width: parent ? parent.width : 0
        topPadding: Escala.px(16)
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: Escala.fuente(30)
    }
    component Dato: Item {
        id: dato
        property string rotulo: ""
        property string valor: ""
        width: parent ? parent.width : 0
        height: Escala.px(72)
        Text {
            anchors.left: parent.left; anchors.leftMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.45
            // D8-5.4: sin recorte; dos líneas o letra menor dentro de la fila
            height: parent.height; verticalAlignment: Text.AlignVCenter
            wrapMode: Text.Wrap
            fontSizeMode: Text.Fit; minimumPixelSize: Escala.fuenteMinima
            text: dato.rotulo
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(25)
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.53
            horizontalAlignment: Text.AlignRight
            // D8-5.4: sin recorte; dos líneas o letra menor dentro de la fila
            height: parent.height; verticalAlignment: Text.AlignVCenter
            wrapMode: Text.Wrap
            fontSizeMode: Text.Fit; minimumPixelSize: Escala.fuenteMinima
            text: dato.valor
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(26)
        }
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Colores.bordeDivisor }
    }
    component Boton: Rectangle {
        id: boton
        property string texto: ""
        property bool habilitado: true
        signal pulsado()
        height: Escala.px(88)
        radius: Escala.px(12)
        color: Colores.accionPrimario
        opacity: habilitado ? 1.0 : 0.4
        Text {
            anchors.centerIn: parent
            text: boton.texto
            color: "white"
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(26)
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
            spacing: Escala.px(6)

            Rectangle {
                objectName: "mensajeConectividad"
                visible: control.mensaje !== ""
                width: parent.width
                height: visible ? textoMensaje.implicitHeight + Escala.px(28) : 0
                radius: Escala.px(12)
                color: control.mensaje === "conectividad.prueba_enviada" ? Colores.accionFondoTenue
                                                                         : Colores.peligroFondo
                Text {
                    id: textoMensaje
                    x: Escala.px(14); width: parent.width - Escala.px(28); anchors.verticalCenter: parent.verticalCenter
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                    text: control.mensaje !== "" ? I18n.t(control.mensaje, I18n.lang) : ""
                    color: control.mensaje === "conectividad.prueba_enviada" ? Colores.accionPrimarioTexto
                                                                             : Colores.peligroTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                }
                MouseArea { anchors.fill: parent; onClicked: control.limpiarMensaje() }
            }

            // ── red (solo lectura) ────────────────────────────────────
            Titulo { text: I18n.t("conectividad.red", I18n.lang) }
            Dato {
                objectName: "datoWifi"
                rotulo: I18n.t("conectividad.wifi", I18n.lang)
                valor: control.wifiSsid !== ""
                       ? control.wifiSsid + (control.wifiSenal >= 0
                                             ? " · " + I18n.t("conectividad.senal", I18n.lang, { n: control.wifiSenal })
                                             : "")
                       : I18n.t("conectividad.sin_wifi", I18n.lang)
            }
            Repeater {
                model: control.adaptadores
                delegate: Dato {
                    required property var modelData
                    objectName: "adaptador_" + modelData.nombre
                    rotulo: modelData.nombre
                    valor: modelData.conectado
                           ? (modelData.ipv4 || I18n.t("conectividad.sin_ip", I18n.lang))
                           : I18n.t("conectividad.desconectado", I18n.lang)
                }
            }
            Text {
                objectName: "notaRedSoporte"
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("conectividad.nota_soporte", I18n.lang)
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(21)
            }

            // ── correo de ciclos ──────────────────────────────────────
            Titulo { text: I18n.t("conectividad.correo", I18n.lang) }
            Rectangle {
                objectName: "avisoSoloLecturaCorreo"
                visible: !raiz.editable
                width: parent.width
                height: visible ? textoAviso.implicitHeight + Escala.px(24) : 0
                radius: Escala.px(12)
                color: Colores.advertenciaFondo
                Text {
                    id: textoAviso
                    x: Escala.px(12); width: parent.width - Escala.px(24); anchors.verticalCenter: parent.verticalCenter
                    wrapMode: Text.WordWrap
                    text: control.motivoEdicion === "ciclo" ? I18n.t("conectividad.motivo_ciclo", I18n.lang)
                                                            : I18n.t("conectividad.motivo_rol", I18n.lang)
                    color: Colores.advertenciaTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(21)
                }
            }
            FilaInterruptor {
                objectName: "interruptorEnvioCorreo"
                width: parent.width
                etiqueta: I18n.t("conectividad.envio", I18n.lang)
                detalle: I18n.t("conectividad.envio_detalle", I18n.lang)
                marcado: control.envioActivo
                bloqueado: !raiz.editable
                onAlternado: control.fijarEnvio(!control.envioActivo)
            }
            Dato {
                rotulo: I18n.t("conectividad.remitente", I18n.lang)
                valor: control.remitente !== "" ? control.remitente : "—"
            }
            Dato {
                rotulo: I18n.t("conectividad.servidor", I18n.lang)
                valor: control.servidor !== "" ? control.servidor : "—"
            }
            Dato {
                objectName: "datoContrasena"
                rotulo: I18n.t("conectividad.contrasena", I18n.lang)
                valor: control.contrasenaConfigurada ? I18n.t("conectividad.configurada", I18n.lang)
                                                     : I18n.t("conectividad.no_configurada", I18n.lang)
            }
            Text {
                width: parent.width
                topPadding: Escala.px(12)
                text: I18n.t("conectividad.destinatarios", I18n.lang,
                             { n: control.destinatarios.length, max: control.maxDestinatarios })
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(24)
            }
            Repeater {
                model: control.destinatarios
                delegate: Rectangle {
                    id: filaDest
                    required property var modelData
                    required property int index
                    objectName: "destinatario_" + index
                    width: columna.width
                    height: Escala.px(88)
                    radius: Escala.px(12)
                    color: Colores.fondoSutil
                    Column {
                        anchors.left: parent.left; anchors.leftMargin: Escala.px(16)
                        anchors.right: quitar.left
                        anchors.verticalCenter: parent.verticalCenter
                        Text {
                            width: parent.width
                            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                            text: filaDest.modelData.nombre
                            color: Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoSemiBold
                            font.pixelSize: Escala.fuente(24)
                        }
                        Text {
                            width: parent.width
                            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                            text: filaDest.modelData.correo
                            color: Colores.textoSecundario
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(22)
                        }
                    }
                    Rectangle {
                        id: quitar
                        objectName: "quitarDestinatario_" + filaDest.index
                        anchors.right: parent.right; anchors.rightMargin: Escala.px(12)
                        anchors.verticalCenter: parent.verticalCenter
                        width: Escala.px(140); height: Escala.px(64)
                        radius: Escala.px(10)
                        color: Colores.peligroFondo
                        opacity: raiz.editable ? 1.0 : 0.4
                        Text {
                            anchors.centerIn: parent
                            text: I18n.t("conectividad.quitar", I18n.lang)
                            color: Colores.peligroTexto
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoSemiBold
                            font.pixelSize: Escala.fuente(22)
                        }
                        MouseArea {
                            anchors.fill: parent
                            enabled: raiz.editable
                            onClicked: control.quitar(filaDest.index)
                        }
                    }
                }
            }
            Text {
                visible: control.destinatarios.length === 0
                width: parent.width
                text: I18n.t("conectividad.sin_destinatarios", I18n.lang)
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(22)
            }
            Row {
                width: parent.width
                spacing: Escala.px(16)
                topPadding: Escala.px(8)
                Boton {
                    objectName: "botonAgregarDestinatario"
                    width: (parent.width - parent.spacing) / 2
                    texto: I18n.t("conectividad.agregar", I18n.lang)
                    habilitado: raiz.editable && raiz.teclado !== null
                                && control.destinatarios.length < control.maxDestinatarios
                    onPulsado: raiz.agregarDestinatario()
                }
                Boton {
                    objectName: "botonCorreoPrueba"
                    width: (parent.width - parent.spacing) / 2
                    texto: I18n.t("conectividad.prueba", I18n.lang)
                    habilitado: raiz.editable && control.envioActivo && control.destinatarios.length > 0
                    onPulsado: control.enviarPrueba()
                }
            }
        }
    }
}

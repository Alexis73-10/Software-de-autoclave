pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Opciones avanzadas › Cierre de fabricación (modo fábrica,
// Etapa 5; §6 de planeacion_modo_fabrica.md). Solo la carga Opciones
// avanzadas con el equipo en FÁBRICA (UiBridge.modoFabrica) y sesión de
// ingeniero; el backend es la autoridad (409 solo_modo_fabrica, 403).
// Muestra lo que se borra y lo que queda, la USB, las precondiciones y, al
// iniciar, el avance por etapa y el resultado (ruta del ZIP; hash en
// pequeño) antes de que el software se reinicie. Iniciar: confirmación modal
// y luego la contraseña con `abrirAlfanumericoAccion` (TEC-ACC: el callback
// envía al backend). Textos sin recorte (D8-5.4). DISEÑO PROVISIONAL sin mockup.
Item {
    id: raiz
    objectName: "opcionesCierreFabrica"

    property QtObject teclado: null

    CierreFabricaController {
        id: control
        objectName: "cierreFabricaController"
    }
    readonly property alias controlador: control
    Component.onCompleted: control.cargar()

    function pedirClave() {
        raiz.teclado?.abrirAlfanumericoAccion(
            I18n.t("cierre_fabrica.clave_titulo", I18n.lang), "", 64, true,
            function (texto) { control.iniciar(texto) })
    }

    component Titulo: Text {
        width: parent ? parent.width : 0
        wrapMode: Text.WordWrap
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: Escala.fuente(26)
    }
    component Parrafo: Text {
        width: parent ? parent.width : 0
        wrapMode: Text.WordWrap
        color: Colores.textoSecundario
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(22)
    }

    Rectangle {
        anchors.fill: parent
        color: Colores.fondoTarjeta
    }

    Flickable {
        id: desplazable
        objectName: "listaCierreFabrica"
        anchors.fill: parent
        contentHeight: columna.height + Escala.px(40)
        clip: true
        interactive: contentHeight > height

        Column {
            id: columna
            width: parent.width
            spacing: Escala.px(14)

            Parrafo {
                objectName: "explicacionCierreFabrica"
                text: I18n.t("cierre_fabrica.explicacion", I18n.lang)
                color: Colores.textoPrimario
            }

            Rectangle {
                objectName: "mensajeCierreFabrica"
                visible: control.mensaje !== ""
                width: parent.width
                height: visible ? textoMensaje.implicitHeight + Escala.px(28) : 0
                radius: Escala.px(12)
                color: Colores.peligroFondo
                Text {
                    id: textoMensaje
                    x: Escala.px(14); width: parent.width - Escala.px(28)
                    anchors.verticalCenter: parent.verticalCenter
                    wrapMode: Text.WordWrap
                    text: control.mensaje !== "" ? I18n.t(control.mensaje, I18n.lang) : ""
                    color: Colores.peligroTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                }
                MouseArea { anchors.fill: parent; onClicked: control.limpiarMensaje() }
            }

            // ── avance y resultado ────────────────────────────────────
            Rectangle {
                objectName: "avanceCierreFabrica"
                visible: control.enCurso || control.terminado
                width: parent.width
                height: visible ? avance.height + Escala.px(32) : 0
                radius: Escala.px(14)
                color: Colores.accionFondoTenue
                Column {
                    id: avance
                    x: Escala.px(16); y: Escala.px(16)
                    width: parent.width - Escala.px(32)
                    spacing: Escala.px(10)
                    Text {
                        objectName: "etapaCierreFabrica"
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: control.etapa !== "" && I18n.existe("cierre_fabrica.etapa_" + control.etapa, I18n.lang)
                              ? I18n.t("cierre_fabrica.etapa_" + control.etapa, I18n.lang) : ""
                        color: Colores.accionPrimarioTexto
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: Escala.fuente(24)
                    }
                    Rectangle {
                        width: parent.width
                        height: Escala.px(14)
                        radius: height / 2
                        color: Colores.bordeCampo
                        Rectangle {
                            objectName: "barraCierreFabrica"
                            width: parent.width * Math.max(0, Math.min(1, control.progreso))
                            height: parent.height
                            radius: parent.radius
                            color: Colores.progresoInicio
                        }
                    }
                    Text {
                        objectName: "paqueteCierreFabrica"
                        visible: control.terminado
                        width: parent.width
                        wrapMode: Text.WrapAnywhere
                        text: I18n.t("cierre_fabrica.resultado_paquete", I18n.lang, { ruta: control.rutaPaquete })
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(22)
                    }
                    Text {
                        objectName: "hashCierreFabrica"
                        visible: control.terminado
                        width: parent.width
                        wrapMode: Text.WrapAnywhere
                        text: I18n.t("cierre_fabrica.resultado_hash", I18n.lang, { hash: control.hashPaquete })
                        color: Colores.textoGuia
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(19)
                    }
                    Text {
                        visible: control.terminado
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: I18n.t("cierre_fabrica.resultado_reinicio", I18n.lang)
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: Escala.fuente(22)
                    }
                }
            }

            // ── qué se borra y qué queda ──────────────────────────────
            Titulo { text: I18n.t("cierre_fabrica.se_borra", I18n.lang) }
            Repeater {
                model: control.conteos
                delegate: Parrafo {
                    required property var modelData
                    objectName: "conteoCierre_" + modelData.clave
                    text: "• " + I18n.t(modelData.clave, I18n.lang, { n: modelData.n })
                }
            }
            Parrafo { text: I18n.t("cierre_fabrica.borra_extra", I18n.lang) }
            Titulo { text: I18n.t("cierre_fabrica.se_conserva", I18n.lang) }
            Parrafo { text: I18n.t("cierre_fabrica.queda_texto", I18n.lang) }

            // ── USB ───────────────────────────────────────────────────
            Rectangle {
                objectName: "usbCierreFabrica"
                readonly property bool hayUsb: control.unidad !== ""
                width: parent.width
                height: Math.max(Escala.px(100), textoUsb.implicitHeight + Escala.px(28))
                radius: Escala.px(14)
                color: hayUsb ? Colores.accionFondoTenue : Colores.advertenciaFondo
                Text {
                    id: textoUsb
                    anchors.left: parent.left; anchors.leftMargin: Escala.px(20)
                    anchors.right: botonActualizar.left; anchors.rightMargin: Escala.px(12)
                    anchors.verticalCenter: parent.verticalCenter
                    wrapMode: Text.WordWrap
                    text: parent.hayUsb ? I18n.t("cierre_fabrica.usb_detectada", I18n.lang,
                                                 { unidad: control.unidad, libre: control.libre,
                                                   requerido: control.requerido })
                                        : I18n.t("cierre_fabrica.usb_no_detectada", I18n.lang)
                    color: parent.hayUsb ? Colores.accionPrimarioTexto : Colores.advertenciaTexto
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(23)
                }
                Rectangle {
                    id: botonActualizar
                    objectName: "botonActualizarCierreFabrica"
                    anchors.right: parent.right; anchors.rightMargin: Escala.px(14)
                    anchors.verticalCenter: parent.verticalCenter
                    width: Escala.px(200); height: Escala.px(72)
                    radius: Escala.px(10)
                    color: Colores.fondoTarjeta
                    border.width: Escala.px(1); border.color: Colores.bordeCampo
                    opacity: control.enCurso ? 0.4 : 1.0
                    Text {
                        anchors.fill: parent; anchors.margins: Escala.px(6)
                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                        fontSizeMode: Text.HorizontalFit
                        minimumPixelSize: Escala.fuenteMinima
                        text: I18n.t("cierre_fabrica.actualizar", I18n.lang)
                        color: Colores.accionPrimarioTexto
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: Escala.fuente(22)
                    }
                    MouseArea { anchors.fill: parent; enabled: !control.enCurso; onClicked: control.cargar() }
                }
            }

            // ── precondiciones ────────────────────────────────────────
            Column {
                objectName: "precondicionesCierreFabrica"
                visible: control.cargado && !control.precondicionesOk && !control.enCurso && !control.terminado
                width: parent.width
                spacing: Escala.px(6)
                Titulo { text: I18n.t("cierre_fabrica.precondiciones", I18n.lang) }
                Repeater {
                    model: control.motivos
                    delegate: Parrafo {
                        required property var modelData
                        color: Colores.peligroTexto
                        text: "• " + (I18n.existe(modelData.clave, I18n.lang)
                                      ? I18n.t(modelData.clave, I18n.lang, { detalle: modelData.detalle })
                                      : modelData.detalle)
                    }
                }
            }

            Rectangle {
                id: botonIniciar
                objectName: "botonIniciarCierreFabrica"
                visible: !control.terminado
                readonly property bool habilitado: control.puedeIniciar && raiz.teclado !== null
                width: parent.width
                height: Math.max(Escala.px(96), textoIniciar.implicitHeight + Escala.px(24))
                radius: Escala.px(12)
                color: Colores.peligroTexto
                opacity: habilitado ? 1.0 : 0.4
                Text {
                    id: textoIniciar
                    anchors.fill: parent; anchors.margins: Escala.px(12)
                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                    text: I18n.t("cierre_fabrica.iniciar", I18n.lang)
                    color: Colores.textoSobreAccion
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(26)
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: botonIniciar.habilitado
                    onClicked: modalConfirmar.abrir()
                }
            }
        }
    }

    ModalConfirmacion {
        id: modalConfirmar
        objectName: "modalConfirmarCierreFabrica"
        titulo: I18n.t("cierre_fabrica.confirmar_titulo", I18n.lang)
        cuerpo: I18n.t("cierre_fabrica.confirmar_cuerpo", I18n.lang)
        nota: I18n.t("cierre_fabrica.confirmar_nota", I18n.lang)
        textoVolver: I18n.t("acciones.cancelar", I18n.lang)
        textoAccion: I18n.t("cierre_fabrica.confirmar_accion", I18n.lang)
        colorAccion: Colores.peligroTexto
        onAceptado: raiz.pedirClave()
    }
}

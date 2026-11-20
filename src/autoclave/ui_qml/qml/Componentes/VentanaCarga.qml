import QtQuick
import Tema
import Autoclave.I18n

// Registro de la carga con lector (RCB-01, RCB-02, RCB-09.2; 19-nov). Ventana
// «Carga del ciclo» de Preciclo, solo en la pantalla de carga. Solo dibuja: la
// lógica y los textos son de bridge/registro_carga_qml.py (`registro`).
//
// Captura del lector (RCB-01.2, HAZ-RCB-03): el lector USB escribe como un
// teclado y termina cada lectura con Enter. Mientras la ventana está abierta,
// el campo invisible `capturaLector` conserva el foco (lo recupera si otro
// control se lo quita) y cada Enter entrega su texto a `registro.leer`. Fuera
// de esta ventana no existe ese campo: el software no interpreta lecturas.
// La entrada manual usa el teclado en pantalla en modo acción (regla de la
// tanda 22: el callback ejecuta una acción, `abrirAlfanumericoAccion`).
// Mockup aprobado: docs/diseno/mockups/registro_carga/rcb_2_ventana_carga.png.
Item {
    id: raiz
    anchors.fill: parent

    property real escala: 1
    property QtObject registro: null
    property QtObject teclado: null
    property bool requerida: false        // el programa exige la carga (subtítulo)
    readonly property bool abierta: ventana.abierta

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    function abrir() {
        registro?.actualizarCatalogo()
        ventana.abrir()
    }
    function cerrar() { ventana.cerrar() }

    // Lectura completa del lector (o de una prueba): la entrega y limpia el campo
    function _entregarLectura() {
        const texto = capturaLector.text
        capturaLector.text = ""
        if (texto.length > 0)
            raiz.registro?.leer(texto)
    }
    function _recuperarFoco() {
        if (ventana.abierta && !vaciarModal.abierto && !(raiz.teclado?.abierto ?? false))
            capturaLector.forceActiveFocus()
    }

    component BotonVentana: Rectangle {
        id: b
        property string texto: ""
        property bool primario: false
        property bool habilitado: true
        signal pulsado()
        radius: raiz.m(14)
        color: primario ? Colores.puertaCerradaBorde : Colores.puertaCerradaFondo
        border.width: raiz.m(2)
        border.color: primario ? Colores.puertaCerradaBorde : Colores.bordeCampo
        opacity: habilitado ? 1 : 0.4
        Text {
            anchors.fill: parent
            anchors.margins: raiz.m(10)
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap
            text: b.texto
            color: b.primario ? Colores.textoSobreAccion : Colores.puertaCerradaTexto
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(26)
            fontSizeMode: Text.Fit
            minimumPixelSize: Math.min(raiz.fuente(26), Escala.fuenteMinima)
        }
        MouseArea {
            anchors.fill: parent
            enabled: b.habilitado
            onClicked: b.pulsado()
        }
    }

    VentanaFlotante {
        id: ventana
        objectName: "ventanaCarga"
        anchors.fill: parent
        escala: raiz.escala
        altoTarjeta: 1700
        titulo: I18n.t("registro_carga.ventana_titulo", I18n.lang)
        onMostrada: {
            capturaLector.text = ""
            raiz._recuperarFoco()
        }
        onCerrada: {
            capturaLector.text = ""
            capturaLector.focus = false
            raiz.teclado?.cerrar()
        }

        // Campo invisible de captura del lector (solo existe con la ventana abierta)
        TextInput {
            id: capturaLector
            objectName: "capturaLector"
            width: 1; height: 1
            opacity: 0
            enabled: ventana.abierta
            maximumLength: 128
            onAccepted: raiz._entregarLectura()
            onActiveFocusChanged: if (!activeFocus) Qt.callLater(raiz._recuperarFoco)
        }
        // al cerrarse el teclado en pantalla, el foco vuelve a la captura
        Connections {
            target: raiz.teclado
            function onAbiertoChanged() { if (!(raiz.teclado?.abierto ?? false)) Qt.callLater(raiz._recuperarFoco) }
        }

        Column {
            id: columna
            width: ventana.anchoContenido
            spacing: raiz.m(18)

            Text {
                objectName: "subtituloCarga"
                width: parent.width
                wrapMode: Text.WordWrap
                visible: raiz.requerida
                text: I18n.t("registro_carga.requerida_inicio", I18n.lang)
                color: Colores.advertenciaTexto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(22)
            }

            // Pasos: 1 · lote y 2 · elementos
            Row {
                width: parent.width
                spacing: raiz.m(18)
                readonly property real anchoPaso: (width - spacing) / 2
                Rectangle {
                    objectName: "pasoLote"
                    width: parent.anchoPaso
                    height: raiz.m(118)
                    radius: raiz.m(16)
                    color: Colores.fondoElevado
                    border.width: raiz.m(3)
                    border.color: (raiz.registro?.paso ?? "lote") === "lote" ? Colores.puertaCerradaBorde
                                                                           : Colores.estadoEjecucion
                    Text {
                        id: textoPasoLote
                        x: raiz.m(20); y: raiz.m(14)
                        width: parent.width - x - (botonCambiarLote.visible ? botonCambiarLote.width + raiz.m(16) : 0) - raiz.m(12)
                        wrapMode: Text.WordWrap
                        text: (raiz.registro?.lote ?? "") !== ""
                              ? I18n.t("registro_carga.lote", I18n.lang)
                              : I18n.t("registro_carga.paso_lote", I18n.lang)
                        color: Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: raiz.fuente(20)
                    }
                    Text {
                        objectName: "textoLote"
                        anchors.top: textoPasoLote.bottom
                        anchors.topMargin: raiz.m(4)
                        x: raiz.m(20)
                        width: textoPasoLote.width
                        text: (raiz.registro?.lote ?? "") !== "" ? raiz.registro.lote
                                                               : I18n.t("registro_carga.sin_lote", I18n.lang)
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: raiz.fuente(30)
                        fontSizeMode: Text.HorizontalFit
                        minimumPixelSize: Escala.fuenteMinima
                    }
                    BotonVentana {
                        id: botonCambiarLote
                        objectName: "botonCambiarLote"
                        visible: (raiz.registro?.lote ?? "") !== ""
                        anchors.right: parent.right
                        anchors.rightMargin: raiz.m(16)
                        anchors.verticalCenter: parent.verticalCenter
                        width: raiz.m(170); height: raiz.m(72)
                        texto: I18n.t("registro_carga.cambiar_lote", I18n.lang)
                        onPulsado: { raiz.registro?.cambiarLote(); raiz._recuperarFoco() }
                    }
                }
                Rectangle {
                    objectName: "pasoElementos"
                    width: parent.anchoPaso
                    height: raiz.m(118)
                    radius: raiz.m(16)
                    color: (raiz.registro?.paso ?? "lote") === "elementos" ? Colores.puertaCerradaFondo
                                                                          : Colores.fondoSutil
                    border.width: raiz.m(3)
                    border.color: (raiz.registro?.paso ?? "lote") === "elementos" ? Colores.puertaCerradaBorde
                                                                                  : Colores.bordeDivisor
                    Text {
                        anchors.fill: parent
                        anchors.margins: raiz.m(18)
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap
                        text: I18n.t("registro_carga.paso_elementos", I18n.lang)
                        color: (raiz.registro?.paso ?? "lote") === "elementos" ? Colores.puertaCerradaTexto
                                                                              : Colores.textoGuia
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: raiz.fuente(26)
                        fontSizeMode: Text.Fit
                        minimumPixelSize: Escala.fuenteMinima
                    }
                }
            }

            // Aviso de la última lectura (aceptada o rechazada)
            Rectangle {
                objectName: "avisoCarga"
                width: parent.width
                height: visible ? textoAviso.implicitHeight + raiz.m(24) : 0
                visible: (raiz.registro?.aviso ?? "") !== ""
                radius: raiz.m(10)
                color: (raiz.registro?.avisoTipo ?? "") === "error" ? Colores.peligroFondo : Colores.exitoFondo
                Text {
                    id: textoAviso
                    objectName: "textoAvisoCarga"
                    x: raiz.m(20); width: parent.width - raiz.m(40)
                    anchors.verticalCenter: parent.verticalCenter
                    wrapMode: Text.WordWrap
                    text: raiz.registro?.aviso ?? ""
                    color: (raiz.registro?.avisoTipo ?? "") === "error" ? Colores.peligroTexto : Colores.menuVerdeTexto
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(24)
                }
            }

            // Encabezado de la lista y totales
            Item {
                width: parent.width
                height: raiz.m(40)
                Text {
                    x: raiz.m(16)
                    anchors.verticalCenter: parent.verticalCenter
                    text: I18n.t("registro_carga.col_cantidad", I18n.lang)
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(20)
                }
                Text {
                    x: raiz.m(128)
                    anchors.verticalCenter: parent.verticalCenter
                    text: I18n.t("registro_carga.col_elemento", I18n.lang)
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(20)
                }
                Text {
                    objectName: "totalesCarga"
                    anchors.right: parent.right
                    anchors.rightMargin: raiz.m(16)
                    anchors.verticalCenter: parent.verticalCenter
                    text: I18n.t("registro_carga.total", I18n.lang,
                                 { codigos: raiz.registro?.totalCodigos ?? 0,
                                   unidades: raiz.registro?.totalUnidades ?? 0 })
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(20)
                }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Colores.bordeDivisor }
            }
        }

        ListView {
            id: lista
            objectName: "listaCarga"
            anchors.top: columna.bottom
            anchors.bottom: filaBotones.top
            anchors.bottomMargin: raiz.m(18)
            width: ventana.anchoContenido
            clip: true
            model: raiz.registro?.filas ?? []
            onCountChanged: positionViewAtEnd()
            delegate: Rectangle {
                id: fila
                required property var modelData
                objectName: "filaCarga_" + modelData.codigo
                width: ListView.view.width
                height: Math.max(raiz.m(104), columnaNombre.implicitHeight + raiz.m(24))
                color: modelData.ultimo ? Colores.exitoFondo : Colores.fondoElevado
                Text {
                    x: raiz.m(16); width: raiz.m(96)
                    anchors.verticalCenter: parent.verticalCenter
                    horizontalAlignment: Text.AlignHCenter
                    text: String(fila.modelData.cantidad)
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(40)
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: Escala.fuenteMinima
                }
                Column {
                    id: columnaNombre
                    x: raiz.m(128)
                    width: parent.width - x - botonMenosUno.width - raiz.m(36)
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: raiz.m(4)
                    Text {
                        width: parent.width
                        wrapMode: Text.Wrap
                        text: fila.modelData.enCatalogo ? fila.modelData.nombre : fila.modelData.codigo
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: raiz.fuente(28)
                    }
                    Flow {
                        width: parent.width
                        spacing: raiz.m(12)
                        Text {
                            text: fila.modelData.codigo
                            color: Colores.textoSecundario
                            font.family: Tipografia.familia
                            font.pixelSize: raiz.fuente(20)
                        }
                        Rectangle {
                            visible: fila.modelData.manual
                            width: textoManual.implicitWidth + raiz.m(20); height: textoManual.implicitHeight + raiz.m(6)
                            radius: height / 2
                            color: Colores.puertaCerradaFondo
                            Text {
                                id: textoManual
                                anchors.centerIn: parent
                                text: I18n.t("registro_carga.manual", I18n.lang)
                                color: Colores.puertaCerradaTexto
                                font.family: Tipografia.familia
                                font.weight: Tipografia.pesoSemiBold
                                font.pixelSize: raiz.fuente(18)
                            }
                        }
                        Rectangle {
                            visible: !fila.modelData.enCatalogo
                            width: textoSinCatalogo.implicitWidth + raiz.m(20); height: textoSinCatalogo.implicitHeight + raiz.m(6)
                            radius: height / 2
                            color: Colores.advertenciaFondo
                            Text {
                                id: textoSinCatalogo
                                anchors.centerIn: parent
                                text: I18n.t("registro_carga.sin_catalogo", I18n.lang)
                                color: Colores.advertenciaTexto
                                font.family: Tipografia.familia
                                font.weight: Tipografia.pesoSemiBold
                                font.pixelSize: raiz.fuente(18)
                            }
                        }
                    }
                }
                BotonVentana {
                    id: botonMenosUno
                    objectName: "botonMenosUno_" + fila.modelData.codigo
                    anchors.right: parent.right
                    anchors.rightMargin: raiz.m(20)
                    anchors.verticalCenter: parent.verticalCenter
                    width: raiz.m(96); height: raiz.m(68)
                    texto: I18n.t("registro_carga.quitar_uno", I18n.lang)
                    onPulsado: { raiz.registro?.quitarUno(fila.modelData.codigo); raiz._recuperarFoco() }
                }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Colores.bordeDivisor }
            }
            Text {
                objectName: "listaCargaVacia"
                visible: lista.count === 0
                anchors.centerIn: parent
                width: parent.width - raiz.m(40)
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: I18n.t("registro_carga.lista_vacia", I18n.lang)
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(24)
            }
        }

        // Escribir código · Vaciar · Listo
        Row {
            id: filaBotones
            anchors.bottom: parent.bottom
            width: ventana.anchoContenido
            spacing: raiz.m(18)
            readonly property real anchoBoton: (width - 2 * spacing) / 3
            BotonVentana {
                objectName: "botonEscribirCodigo"
                width: filaBotones.anchoBoton; height: raiz.m(96)
                texto: I18n.t("registro_carga.escribir", I18n.lang)
                onPulsado: raiz.teclado?.abrirAlfanumericoAccion(
                               I18n.t("registro_carga.escribir_titulo", I18n.lang), "", 64, false,
                               function (texto) {
                                   raiz.registro?.leerManual(texto)
                                   Qt.callLater(raiz._recuperarFoco)
                               })
            }
            BotonVentana {
                objectName: "botonVaciarCarga"
                width: filaBotones.anchoBoton; height: raiz.m(96)
                habilitado: !(raiz.registro?.vacio ?? true)
                texto: I18n.t("registro_carga.vaciar", I18n.lang)
                onPulsado: vaciarModal.abrir()
            }
            BotonVentana {
                objectName: "botonListoCarga"
                width: filaBotones.anchoBoton; height: raiz.m(96)
                primario: true
                texto: I18n.t("registro_carga.listo", I18n.lang)
                onPulsado: ventana.cerrar()
            }
        }
    }

    // «Vaciar» con confirmación (RCB-02.3)
    ModalConfirmacion {
        id: vaciarModal
        objectName: "modalVaciarCarga"
        titulo: I18n.t("registro_carga.vaciar_titulo", I18n.lang)
        cuerpo: I18n.t("registro_carga.vaciar_texto", I18n.lang)
        textoVolver: I18n.t("registro_carga.cancelar", I18n.lang)
        textoAccion: I18n.t("registro_carga.vaciar", I18n.lang)
        colorAccion: Colores.peligroTexto
        onAceptado: { raiz.registro?.vaciar(); Qt.callLater(raiz._recuperarFoco) }
        onCancelado: Qt.callLater(raiz._recuperarFoco)
    }
}

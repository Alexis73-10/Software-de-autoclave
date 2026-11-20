pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Catálogo de carga (RCB-08.1/08.2/08.3, registro de la carga con
// lector; docs/mis_plans/planeacion_registro_carga.md §9; mockup
// docs/diseno/mockups/registro_carga/rcb_3_catalogo.png). Ingeniero y admin.
// Lista con búsqueda (teclado en pantalla, filtro local en el controlador),
// «+ Alta», «Importar CSV» y, por fila, «Editar» (nombre y baja/reactivación).
// Toda la lógica y los mensajes salen de CatalogoCargaController; aquí solo se
// dibuja. El backend es la autoridad (rol, validación, bitácora).
//
// Lector de código de barras (USB HID en modo teclado, con Enter): SOLO
// mientras el diálogo de alta está abierto y el teclado en pantalla cerrado,
// un TextInput invisible (`capturaLector`) conserva el foco y cada Enter
// entrega lo leído como código. Fuera de ese diálogo no hay captura.
Item {
    id: raiz
    objectName: "opcionesCatalogoCarga"

    property QtObject teclado: null
    property bool edicionPermitida: false
    readonly property bool cambiosPendientes: false
    // texto de búsqueda (lo asigna el teclado en vivo; el controlador filtra)
    property string busqueda: ""

    CatalogoCargaController {
        id: control
        objectName: "catalogoCargaController"
        filtro: raiz.busqueda
    }
    readonly property alias controlador: control
    Component.onCompleted: control.cargar()

    readonly property bool tecladoAbierto: raiz.teclado !== null && raiz.teclado.abierto === true

    function texto(clave, args) { return clave !== "" ? I18n.t(clave, I18n.lang, args || {}) : "" }
    function textoMensaje() {
        if (control.mensaje === "")
            return ""
        const args = control.mensajeArgs
        if (control.mensajeMotivo !== "")
            args.motivo = I18n.t(control.mensajeMotivo, I18n.lang)
        return I18n.t(control.mensaje, I18n.lang, args)
    }

    // ── componentes locales ───────────────────────────────────────────
    component Boton: Rectangle {
        id: boton
        property string texto: ""
        property bool habilitado: true
        property bool secundario: false
        property color colorFondo: secundario ? Colores.accionFondoTenue : Colores.accionPrimario
        signal pulsado()
        height: Escala.px(88)
        radius: Escala.px(12)
        color: colorFondo
        border.width: secundario ? Escala.px(2) : 0
        border.color: Colores.accionPrimario
        opacity: habilitado ? 1.0 : 0.4
        Text {
            anchors.centerIn: parent
            width: parent.width - Escala.px(16)
            horizontalAlignment: Text.AlignHCenter
            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
            text: boton.texto
            color: boton.secundario ? Colores.accionPrimarioTexto : Colores.textoSobreAccion
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(26)
        }
        MouseArea { anchors.fill: parent; anchors.margins: -Escala.margenTactil(Math.min(parent.width, parent.height)); enabled: boton.habilitado; onClicked: boton.pulsado() }
    }

    component Chip: Rectangle {
        id: chip
        property bool activo: true
        width: textoChip.implicitWidth + Escala.px(28)
        height: Escala.px(44)
        radius: height / 2
        color: activo ? Colores.accionFondoTenue : Colores.fondoSutil
        Text {
            id: textoChip
            anchors.centerIn: parent
            text: I18n.t(chip.activo ? "registro_carga.estado_activo" : "registro_carga.estado_baja", I18n.lang)
            color: chip.activo ? Colores.menuVerdeTexto : Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(20)
        }
    }

    component Banda: Rectangle {
        id: banda
        visible: control.mensaje !== ""
        height: visible ? textoBanda.implicitHeight + Escala.px(28) : 0
        radius: Escala.px(12)
        color: control.mensajeExito ? Colores.accionFondoTenue : Colores.peligroFondo
        Text {
            id: textoBanda
            x: Escala.px(14); width: parent.width - Escala.px(28)
            anchors.verticalCenter: parent.verticalCenter
            wrapMode: Text.WordWrap
            text: raiz.textoMensaje()
            color: control.mensajeExito ? Colores.accionPrimarioTexto : Colores.peligroTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }
        MouseArea { anchors.fill: parent; onClicked: control.limpiarMensaje() }
    }

    // Ventana modal sobre la sección (mismo estilo que elegirRol de Usuarios)
    component Ventana: Item {
        id: ventana
        default property alias contenido: columnaVentana.data
        signal fondoPulsado()
        anchors.fill: parent
        visible: false
        z: 100
        Rectangle {
            anchors.fill: parent
            color: Colores.velo
            MouseArea { anchors.fill: parent; onClicked: ventana.fondoPulsado() }
        }
        Rectangle {
            id: panelVentana
            width: Escala.horizontal ? Math.min(parent.width - Escala.px(80), Escala.px(1300))
                                     : parent.width - Escala.px(40)
            height: Math.min(columnaVentana.implicitHeight + Escala.px(80), parent.height - Escala.px(40))
            anchors.horizontalCenter: parent.horizontalCenter
            y: Escala.px(20)
            radius: Escala.px(28)
            color: Colores.fondoTarjeta
            MouseArea { anchors.fill: parent }   // no dejar pasar el toque al fondo
            Flickable {
                anchors.fill: parent
                anchors.margins: Escala.px(40)
                contentHeight: columnaVentana.implicitHeight
                clip: true
                interactive: contentHeight > height
                Column {
                    id: columnaVentana
                    width: parent.width
                    spacing: Escala.px(16)
                }
            }
        }
    }

    // ── encabezado: búsqueda, alta e importación ─────────────────────
    Column {
        id: cabecera
        width: parent.width
        spacing: Escala.px(12)

        Row {
            width: parent.width
            spacing: Escala.px(16)
            Rectangle {
                id: campoBusqueda
                objectName: "campoBusquedaCatalogo"
                width: parent.width - botonAlta.width - botonImportar.width - 2 * parent.spacing
                height: Escala.px(88)
                radius: Escala.px(12)
                color: Colores.fondoCampo
                border.width: Escala.px(2)
                border.color: Colores.bordeCampo
                IconoColor {
                    id: iconoLupa
                    x: Escala.px(20); anchors.verticalCenter: parent.verticalCenter
                    width: Escala.px(32); height: width
                    source: "../../assets/iconos/color/lupa.svg"
                    color: Colores.iconoCampo
                }
                Text {
                    anchors.left: iconoLupa.right; anchors.leftMargin: Escala.px(12)
                    anchors.right: parent.right; anchors.rightMargin: Escala.px(16)
                    anchors.verticalCenter: parent.verticalCenter
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                    text: raiz.busqueda !== "" ? raiz.busqueda : I18n.t("registro_carga.catalogo_buscar_titulo", I18n.lang)
                    color: raiz.busqueda !== "" ? Colores.textoPrimario : Colores.textoGuia
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(26)
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: raiz.teclado !== null
                    // en vivo: solo asigna la propiedad (regla del teclado, tanda 22)
                    onClicked: raiz.teclado.abrirAlfanumerico(I18n.t("registro_carga.catalogo_buscar_titulo", I18n.lang),
                                                              raiz.busqueda, 64, false, (t) => { raiz.busqueda = t })
                }
            }
            Boton {
                id: botonAlta
                objectName: "botonAltaCatalogo"
                width: Escala.px(220)
                texto: "+ " + I18n.t("registro_carga.alta", I18n.lang)
                habilitado: raiz.edicionPermitida && !control.enviando
                onPulsado: dialogoAlta.abrir()
            }
            Boton {
                id: botonImportar
                objectName: "botonImportarCatalogo"
                width: Escala.px(250)
                secundario: true
                texto: I18n.t("registro_carga.importar", I18n.lang)
                habilitado: raiz.edicionPermitida && !control.enviando
                onPulsado: dialogoImportar.abrir()
            }
        }

        Text {
            objectName: "resumenCatalogo"
            width: parent.width
            wrapMode: Text.WordWrap
            text: I18n.t("registro_carga.catalogo_resumen", I18n.lang,
                         { total: control.total, activos: control.activos, baja: control.deBaja })
                  + " · " + I18n.t("registro_carga.catalogo_roles", I18n.lang)
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(20)
        }

        Banda {
            objectName: "mensajeCatalogo"
            width: parent.width
        }

        Text {
            visible: control.cargando
            width: parent.width
            text: I18n.t("opciones.cargando", I18n.lang)
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(20)
        }

        // títulos de columna
        Item {
            width: parent.width
            height: Escala.px(48)
            Text {
                x: Escala.px(24); width: raiz._anchoCodigo - Escala.px(24)
                anchors.verticalCenter: parent.verticalCenter
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                text: I18n.t("registro_carga.col_codigo", I18n.lang)
                font.capitalization: Font.AllUppercase
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(20)
            }
            Text {
                x: raiz._anchoCodigo + Escala.px(24); width: raiz._anchoNombre
                anchors.verticalCenter: parent.verticalCenter
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                text: I18n.t("registro_carga.col_nombre", I18n.lang)
                font.capitalization: Font.AllUppercase
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(20)
            }
            Text {
                x: parent.width - raiz._anchoAcciones; width: raiz._anchoChip
                anchors.verticalCenter: parent.verticalCenter
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                text: I18n.t("registro_carga.col_estado", I18n.lang)
                font.capitalization: Font.AllUppercase
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(20)
            }
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width; height: Escala.px(2)
                color: Colores.bordeDivisor
            }
        }
    }

    // medidas de las columnas (px de diseño, como las demás de Opciones)
    readonly property real _anchoCodigo: Escala.px(240)
    readonly property real _anchoChip: Escala.px(150)
    readonly property real _anchoBotonEditar: Escala.px(140)
    readonly property real _anchoAcciones: _anchoChip + _anchoBotonEditar + Escala.px(48)
    readonly property real _anchoNombre: width - _anchoCodigo - _anchoAcciones - Escala.px(48)

    // ── lista ─────────────────────────────────────────────────────────
    ListView {
        id: lista
        objectName: "listaCatalogo"
        anchors.top: cabecera.bottom
        anchors.bottom: nota.top
        anchors.bottomMargin: Escala.px(16)
        width: parent.width
        clip: true
        model: control.elementos
        boundsBehavior: Flickable.StopAtBounds
        delegate: Item {
            id: fila
            required property var modelData
            objectName: "filaCatalogo_" + modelData.codigo
            width: lista.width
            height: Math.max(Escala.px(100), textoNombre.implicitHeight + Escala.px(32))
            Text {
                x: Escala.px(24); width: raiz._anchoCodigo - Escala.px(24)
                anchors.verticalCenter: parent.verticalCenter
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                text: fila.modelData.codigo
                color: fila.modelData.activo ? Colores.textoPrimario : Colores.textoGuia
                font.family: Tipografia.familiaMono
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(24)
            }
            Text {
                id: textoNombre
                x: raiz._anchoCodigo + Escala.px(24); width: raiz._anchoNombre
                anchors.verticalCenter: parent.verticalCenter
                wrapMode: Text.Wrap
                text: fila.modelData.nombre
                color: fila.modelData.activo ? Colores.textoPrimario : Colores.textoGuia
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(26)
            }
            Chip {
                x: parent.width - raiz._anchoAcciones
                anchors.verticalCenter: parent.verticalCenter
                activo: fila.modelData.activo
            }
            Boton {
                objectName: "editar_" + fila.modelData.codigo
                anchors.right: parent.right; anchors.rightMargin: Escala.px(24)
                anchors.verticalCenter: parent.verticalCenter
                width: raiz._anchoBotonEditar; height: Escala.px(68)
                secundario: true
                texto: I18n.t("registro_carga.editar_boton", I18n.lang)
                habilitado: raiz.edicionPermitida && !control.enviando
                onPulsado: dialogoEditar.abrir(fila.modelData.id)
            }
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width; height: Escala.px(1)
                color: Colores.bordeDivisor
            }
        }
        Text {
            objectName: "catalogoVacio"
            visible: control.claveVacio !== "" && !control.cargando
            anchors.centerIn: parent
            width: parent.width - Escala.px(80)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: raiz.texto(control.claveVacio)
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(26)
        }
    }

    // ── nota inferior del mockup ──────────────────────────────────────
    Rectangle {
        id: nota
        objectName: "notaCatalogo"
        anchors.bottom: parent.bottom
        width: parent.width
        height: textoNota.implicitHeight + Escala.px(48)
        radius: Escala.px(16)
        color: Colores.fondoTarjeta
        border.width: Escala.px(2)
        border.color: Colores.bordeCampo
        Text {
            id: textoNota
            x: Escala.px(28); width: parent.width - Escala.px(56)
            anchors.verticalCenter: parent.verticalCenter
            wrapMode: Text.WordWrap
            textFormat: Text.StyledText
            text: "<b>" + I18n.t("registro_carga.nota_alta_titulo", I18n.lang) + "</b> "
                  + I18n.t("registro_carga.nota_alta", I18n.lang) + "<br><b>"
                  + I18n.t("registro_carga.nota_importar_titulo", I18n.lang) + "</b> "
                  + I18n.t("registro_carga.nota_importar", I18n.lang)
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }
    }

    // ══════════════════════ diálogo de alta ══════════════════════
    Ventana {
        id: dialogoAlta
        objectName: "dialogoAlta"
        property string codigo: ""
        property string nombre: ""
        property string aviso: ""
        // esperando el código del lector: abierto y sin el teclado en pantalla
        readonly property bool capturando: visible && !raiz.tecladoAbierto

        function abrir() {
            codigo = ""; nombre = ""; aviso = ""
            capturaLector.text = ""
            visible = true
            capturaLector.forceActiveFocus()
        }
        function cerrar() {
            visible = false
            capturaLector.text = ""
            if (raiz.teclado && raiz.teclado.abierto)
                raiz.teclado.cerrar()
        }
        // una lectura (Enter del lector) o lo escrito con el teclado
        function recibirCodigo(t) {
            const clave = control.validarCodigo(t)
            if (clave !== "") {
                aviso = clave
                return
            }
            codigo = control.normalizarCodigo(t)
            aviso = ""
        }
        onFondoPulsado: cerrar()
        onCapturandoChanged: if (capturando) capturaLector.forceActiveFocus()

        Connections {
            target: control
            function onAltaResuelta(aceptada, mensaje) {
                if (!dialogoAlta.visible)
                    return
                if (aceptada)
                    dialogoAlta.cerrar()
                else
                    dialogoAlta.aviso = mensaje
            }
        }

        // Captura del lector: invisible, con el foco solo mientras se espera
        TextInput {
            id: capturaLector
            objectName: "capturaLector"
            width: 1; height: 1
            opacity: 0
            enabled: dialogoAlta.capturando
            maximumLength: 256
            inputMethodHints: Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase | Qt.ImhPreferLatin
            onAccepted: {
                const leido = text
                text = ""
                dialogoAlta.recibirCodigo(leido)
            }
            onActiveFocusChanged: if (!activeFocus && dialogoAlta.capturando) Qt.callLater(capturaLector.forceActiveFocus)
        }

        Text {
            width: parent.width
            wrapMode: Text.WordWrap
            text: I18n.t("registro_carga.alta_titulo", I18n.lang)
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(32)
        }
        Text {
            width: parent.width
            wrapMode: Text.WordWrap
            text: I18n.t("registro_carga.alta_leer", I18n.lang)
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(24)
        }
        // código
        Text {
            width: parent.width
            text: I18n.t("registro_carga.codigo_titulo", I18n.lang)
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(22)
        }
        Rectangle {
            width: parent.width
            height: Escala.px(80)
            radius: Escala.px(12)
            color: Colores.fondoCampo
            border.width: Escala.px(2)
            border.color: dialogoAlta.capturando ? Colores.accionPrimario : Colores.bordeCampo
            Text {
                objectName: "codigoAlta"
                x: Escala.px(20); width: parent.width - Escala.px(40)
                anchors.verticalCenter: parent.verticalCenter
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                text: dialogoAlta.codigo !== "" ? dialogoAlta.codigo : I18n.t("registro_carga.sin_codigo", I18n.lang)
                color: dialogoAlta.codigo !== "" ? Colores.textoPrimario : Colores.textoGuia
                font.family: dialogoAlta.codigo !== "" ? Tipografia.familiaMono : Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(28)
            }
        }
        Boton {
            objectName: "botonEscribirCodigo"
            width: parent.width
            secundario: true
            texto: I18n.t("registro_carga.escribir", I18n.lang)
            habilitado: raiz.teclado !== null
            // modo acción: valida y normaliza al confirmar (TEC-ACC)
            onPulsado: raiz.teclado.abrirAlfanumericoAccion(I18n.t("registro_carga.escribir_titulo", I18n.lang),
                                                            dialogoAlta.codigo, control.largoCodigo, false,
                                                            (t) => dialogoAlta.recibirCodigo(t))
        }
        // nombre
        Text {
            width: parent.width
            text: I18n.t("registro_carga.nombre_titulo", I18n.lang)
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(22)
        }
        Rectangle {
            objectName: "campoNombreAlta"
            width: parent.width
            height: Math.max(Escala.px(80), textoNombreAlta.implicitHeight + Escala.px(24))
            radius: Escala.px(12)
            color: Colores.fondoCampo
            border.width: Escala.px(2)
            border.color: Colores.bordeCampo
            Text {
                id: textoNombreAlta
                x: Escala.px(20); width: parent.width - Escala.px(40)
                anchors.verticalCenter: parent.verticalCenter
                wrapMode: Text.Wrap
                text: dialogoAlta.nombre !== "" ? dialogoAlta.nombre : I18n.t("registro_carga.sin_nombre", I18n.lang)
                color: dialogoAlta.nombre !== "" ? Colores.textoPrimario : Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(26)
            }
            MouseArea {
                anchors.fill: parent
                enabled: raiz.teclado !== null
                // en vivo: solo asigna la propiedad
                onClicked: raiz.teclado.abrirAlfanumerico(I18n.t("registro_carga.nombre_titulo", I18n.lang),
                                                          dialogoAlta.nombre, control.largoNombre, false,
                                                          (t) => { dialogoAlta.nombre = t })
            }
        }
        Text {
            objectName: "avisoAlta"
            visible: dialogoAlta.aviso !== ""
            width: parent.width
            wrapMode: Text.WordWrap
            text: raiz.texto(dialogoAlta.aviso)
            color: Colores.peligroTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }
        Row {
            width: parent.width
            spacing: Escala.px(24)
            Boton {
                objectName: "cancelarAlta"
                width: (parent.width - parent.spacing) / 2
                secundario: true
                texto: I18n.t("registro_carga.cancelar", I18n.lang)
                onPulsado: dialogoAlta.cerrar()
            }
            Boton {
                objectName: "guardarAlta"
                width: (parent.width - parent.spacing) / 2
                texto: control.enviando ? I18n.t("opciones.guardando", I18n.lang)
                                        : I18n.t("registro_carga.guardar", I18n.lang)
                habilitado: raiz.edicionPermitida && !control.enviando && dialogoAlta.codigo !== ""
                            && control.validarNombre(dialogoAlta.nombre) === ""
                onPulsado: {
                    if (raiz.teclado && raiz.teclado.abierto)
                        raiz.teclado.cerrar()
                    control.alta(dialogoAlta.codigo, dialogoAlta.nombre)
                }
            }
        }
    }

    // ══════════════════════ diálogo de edición ══════════════════════
    Ventana {
        id: dialogoEditar
        objectName: "dialogoEditar"
        property int idElemento: 0
        readonly property var fila: control.total >= 0 && idElemento > 0 ? control.elemento(idElemento) : ({})
        function abrir(id) { idElemento = id; visible = true }
        function cerrar() { visible = false; idElemento = 0 }
        onFondoPulsado: cerrar()

        Connections {
            target: control
            function onEdicionResuelta(id, aceptada, mensaje) {
                if (aceptada && id === dialogoEditar.idElemento)
                    dialogoEditar.cerrar()
            }
        }

        Text {
            objectName: "codigoEditar"
            width: parent.width
            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
            text: dialogoEditar.fila.codigo ?? ""
            color: Colores.textoPrimario
            font.family: Tipografia.familiaMono
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(30)
        }
        Text {
            width: parent.width
            wrapMode: Text.Wrap
            text: dialogoEditar.fila.nombre ?? ""
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(28)
        }
        Chip { activo: dialogoEditar.fila.activo === true }
        Banda { width: parent.width }
        Boton {
            objectName: "botonEditarNombre"
            width: parent.width
            texto: I18n.t("registro_carga.editar", I18n.lang)
            habilitado: raiz.edicionPermitida && !control.enviando && raiz.teclado !== null
            // modo acción: envía al confirmar (TEC-ACC)
            onPulsado: raiz.teclado.abrirAlfanumericoAccion(I18n.t("registro_carga.nombre_titulo", I18n.lang),
                                                            dialogoEditar.fila.nombre ?? "", control.largoNombre, false,
                                                            (t) => control.editarNombre(dialogoEditar.idElemento, t))
        }
        Boton {
            objectName: "botonBajaReactivar"
            width: parent.width
            colorFondo: dialogoEditar.fila.activo === true ? Colores.peligroTexto : Colores.accionPrimario
            texto: I18n.t(dialogoEditar.fila.activo === true ? "registro_carga.baja" : "registro_carga.reactivar", I18n.lang)
            habilitado: raiz.edicionPermitida && !control.enviando
            onPulsado: control.fijarActivo(dialogoEditar.idElemento, dialogoEditar.fila.activo !== true)
        }
        Boton {
            objectName: "cerrarEditar"
            width: parent.width
            secundario: true
            texto: I18n.t("registro_carga.cerrar", I18n.lang)
            onPulsado: dialogoEditar.cerrar()
        }
    }

    // ══════════════════════ diálogo de importación ══════════════════════
    Ventana {
        id: dialogoImportar
        objectName: "dialogoImportar"
        function abrir() {
            control.cancelarImportacion()
            control.limpiarMensaje()
            visible = true
            control.cargarUsb()
        }
        function cerrar() {
            visible = false
            control.cancelarImportacion()
        }
        onFondoPulsado: if (!control.enviando) cerrar()

        Connections {
            target: control
            function onImportacionResuelta(aplicada, mensaje) {
                if (aplicada && dialogoImportar.visible)
                    dialogoImportar.visible = false
            }
        }

        Text {
            width: parent.width
            wrapMode: Text.WordWrap
            text: I18n.t("registro_carga.importar_titulo", I18n.lang)
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(32)
        }
        Text {
            width: parent.width
            wrapMode: Text.WordWrap
            text: I18n.t("registro_carga.importar_formato", I18n.lang)
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }
        Banda { width: parent.width }
        Text {
            visible: control.cargandoUsb || control.enviando
            width: parent.width
            text: I18n.t("registro_carga.procesando", I18n.lang)
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }

        // 1) elegir el archivo
        Column {
            visible: !control.hayVistaPrevia
            width: parent.width
            spacing: Escala.px(10)
            Text {
                objectName: "importarSinUsb"
                visible: control.archivosUsb.length === 0 && !control.cargandoUsb
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("registro_carga.importar_sin_usb", I18n.lang)
                color: Colores.advertenciaTexto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(24)
            }
            Text {
                visible: control.archivosUsb.length > 0
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("registro_carga.importar_elegir", I18n.lang)
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(22)
            }
            Repeater {
                model: control.archivosUsb
                delegate: Rectangle {
                    id: filaArchivo
                    required property var modelData
                    objectName: "csv_" + modelData.archivo
                    width: parent.width
                    height: Escala.px(88)
                    radius: Escala.px(12)
                    color: Colores.fondoSutil
                    Text {
                        x: Escala.px(18); width: parent.width - Escala.px(36)
                        anchors.verticalCenter: parent.verticalCenter
                        fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                        text: filaArchivo.modelData.unidad + "  " + filaArchivo.modelData.archivo
                              + (filaArchivo.modelData.tamano !== "" ? "  (" + filaArchivo.modelData.tamano + ")" : "")
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: Escala.fuente(24)
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: !control.enviando
                        onClicked: control.verVistaPrevia(filaArchivo.modelData.unidad, filaArchivo.modelData.archivo)
                    }
                }
            }
            Row {
                width: parent.width
                spacing: Escala.px(24)
                Boton {
                    objectName: "actualizarUsbCatalogo"
                    width: (parent.width - parent.spacing) / 2
                    secundario: true
                    texto: I18n.t("registro_carga.actualizar_usb", I18n.lang)
                    habilitado: !control.cargandoUsb
                    onPulsado: control.cargarUsb()
                }
                Boton {
                    objectName: "cerrarImportar"
                    width: (parent.width - parent.spacing) / 2
                    secundario: true
                    texto: I18n.t("registro_carga.cerrar", I18n.lang)
                    habilitado: !control.enviando
                    onPulsado: dialogoImportar.cerrar()
                }
            }
        }

        // 2) vista previa y aplicar
        Column {
            objectName: "vistaPreviaCatalogo"
            visible: control.hayVistaPrevia
            width: parent.width
            spacing: Escala.px(8)
            Text {
                width: parent.width
                wrapMode: Text.Wrap
                text: I18n.t("registro_carga.vista_previa", I18n.lang, { archivo: control.vistaPrevia.archivo })
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(26)
            }
            Repeater {
                model: [["registro_carga.vista_altas", control.vistaPrevia.altas],
                        ["registro_carga.vista_cambios", control.vistaPrevia.cambios],
                        ["registro_carga.vista_reactivados", control.vistaPrevia.reactivados],
                        ["registro_carga.vista_sin_cambio", control.vistaPrevia.sinCambio],
                        ["registro_carga.vista_rechazadas", control.vistaPrevia.rechazadas]]
                delegate: Text {
                    required property var modelData
                    required property int index
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: I18n.t(modelData[0], I18n.lang, { n: modelData[1] })
                    color: index === 4 && modelData[1] > 0 ? Colores.peligroTexto : Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(24)
                }
            }
            Repeater {
                model: control.lineasRechazadas
                delegate: Text {
                    required property var modelData
                    width: parent.width
                    wrapMode: Text.Wrap
                    text: I18n.t("registro_carga.vista_linea", I18n.lang,
                                 { linea: modelData.linea, motivo: I18n.t(modelData.motivo, I18n.lang) })
                          + (modelData.texto !== "" ? "  " + modelData.texto : "")
                    color: Colores.peligroTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(20)
                }
            }
            Row {
                width: parent.width
                spacing: Escala.px(24)
                topPadding: Escala.px(8)
                Boton {
                    objectName: "cancelarImportacion"
                    width: (parent.width - parent.spacing) / 2
                    secundario: true
                    texto: I18n.t("registro_carga.cancelar", I18n.lang)
                    habilitado: !control.enviando
                    onPulsado: control.cancelarImportacion()
                }
                Boton {
                    objectName: "aplicarImportacion"
                    width: (parent.width - parent.spacing) / 2
                    texto: control.enviando ? I18n.t("registro_carga.procesando", I18n.lang)
                                            : I18n.t("registro_carga.aplicar", I18n.lang)
                    habilitado: raiz.edicionPermitida && control.aplicable && !control.enviando
                    onPulsado: control.aplicarImportacion()
                }
            }
        }
    }
}

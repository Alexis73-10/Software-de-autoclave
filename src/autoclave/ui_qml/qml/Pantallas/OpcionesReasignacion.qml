pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES > Opciones avanzadas = reasignación de entradas y salidas (R8,
// tanda 8, D8-5.12; planeacion_opciones.md v4 R-03 y OPC-03). DISEÑO
// PROVISIONAL sin mockup aprobado: sigue el estilo de Entradas / Salidas
// (tarjetas, banda de mensaje, botones) y la barra flotante de OPCIONES.
//
// Tabla: función, puerto actual, puerto nuevo, tipo (DI/DO/AI) y si es crítica.
// Tocar una fila abre la lista de puertos de su tipo (libres y ocupados).
// Aplicar: alerta de criticidad -> nombre escrito de cada función reforzada
// (interlock de puerta, paro de emergencia, finales de carrera) -> "Se
// reiniciará el control" -> contraseña. El backend es la autoridad: la UI solo
// refleja y muestra el motivo de un rechazo.
// Tras el reinicio, cada función reasignada queda sin verificar (alarma SEN-09,
// no se inician ciclos) hasta que el ingeniero la verifica aquí, con la prueba
// que exige el backend (revisión R8: cambio observado en una entrada, salida
// accionada en modo prueba, analógica calibrada después de reasignar).
Item {
    id: raiz
    objectName: "opcionesReasignacion"

    property QtObject teclado: null            // PanelTeclado de la ventana
    readonly property alias controlador: control
    readonly property bool cambiosPendientes: control.cantidadCambios > 0
    property string funcionEnEleccion: ""

    Rectangle {
        anchors.fill: parent
        color: Colores.fondoTarjeta
    }

    ReasignacionController {
        id: control
        objectName: "reasignacionController"
    }
    Component.onCompleted: control.cargar()

    // Mientras el control se reinicia (o se verifica), se vuelve a consultar
    Timer {
        interval: 2000
        repeat: true
        running: raiz.visible && (control.reiniciando || raiz._verificando)
        onTriggered: control.cargar()
    }
    readonly property bool _verificando: control.cantidadSinVerificar > 0

    function nombre(clave) { return clave ? I18n.t(clave, I18n.lang) : "" }

    // ------------------------------------------------------------ componentes
    component Boton: Rectangle {
        id: boton
        property string texto: ""
        property color relleno: Colores.accionPrimario
        property bool habilitado: true
        signal pulsado()
        radius: Escala.px(10)
        color: relleno
        opacity: habilitado ? 1.0 : 0.4
        Text {
            anchors.centerIn: parent
            width: parent.width - Escala.px(16)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: boton.texto
            color: "white"
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(21)
        }
        MouseArea {
            anchors.fill: parent
            enabled: boton.habilitado
            onClicked: boton.pulsado()
        }
    }

    component Celda: Text {
        property real fraccion: 0.2
        width: (parent ? parent.width : 0) * fraccion
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        wrapMode: Text.Wrap   // D8-5.4: sin recorte; la fila (76 px) admite dos líneas
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(21)
    }

    // ---------------------------------------------------------------- cabecera
    Column {
        id: cabecera
        width: parent.width
        spacing: Escala.px(10)

        Text {
            width: parent.width
            text: I18n.t("reasignacion.subtitulo", I18n.lang)
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(28)
        }
        Text {
            width: parent.width
            wrapMode: Text.WordWrap
            text: I18n.t("reasignacion.aviso", I18n.lang)
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(19)
        }

        // Motivos y avisos (banda como la de Entradas / Salidas)
        Repeater {
            model: [
                { visible: control.bloqueado, texto: "reasignacion.bloqueo", peligro: true },
                { visible: control.cargado && !control.editable && control.motivo !== "",
                  texto: control.motivo, peligro: false },
                { visible: control.reinicioPendiente && !control.reiniciando,
                  texto: "reasignacion.reinicio_pendiente", peligro: false },
                { visible: control.cantidadSinVerificar > 0,
                  texto: "reasignacion.sin_verificar_aviso", peligro: true },
                { visible: control.mensaje !== "", texto: control.mensaje,
                  peligro: control.mensaje.indexOf(".err_") >= 0 }
            ]
            delegate: Rectangle {
                id: banda
                required property var modelData
                required property int index
                objectName: "bandaReasignacion_" + index
                visible: modelData.visible
                width: cabecera.width
                height: visible ? textoBanda.implicitHeight + Escala.px(28) : 0
                radius: Escala.px(12)
                color: modelData.peligro ? Colores.peligroFondo : Colores.advertenciaFondo
                Text {
                    id: textoBanda
                    anchors.left: parent.left; anchors.right: parent.right
                    anchors.margins: Escala.px(14)
                    anchors.verticalCenter: parent.verticalCenter
                    wrapMode: Text.WordWrap
                    text: banda.modelData.texto ? I18n.t(banda.modelData.texto, I18n.lang) : ""
                    color: banda.modelData.peligro ? Colores.peligroTexto : Colores.advertenciaTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(20)
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: banda.index === 4
                    onClicked: control.limpiarMensaje()
                }
            }
        }

        // Verificación tras el último reinicio
        Column {
            objectName: "verificacionReasignacion"
            visible: control.verificacion.length > 0
            width: parent.width
            spacing: Escala.px(4)
            Text {
                text: I18n.t("reasignacion.verif_titulo", I18n.lang)
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(21)
            }
            Repeater {
                model: control.verificacion
                delegate: Item {
                    id: itemVerif
                    required property var modelData
                    objectName: "verif_" + modelData.funcion
                    width: parent ? parent.width : 0
                    height: Math.max(columnaVerif.implicitHeight, botonVerif.visible ? botonVerif.height : 0)
                            + Escala.px(6)
                    Column {
                        id: columnaVerif
                        anchors.left: parent.left
                        anchors.right: botonVerif.visible ? botonVerif.left : parent.right
                        anchors.rightMargin: Escala.px(12)
                        Text {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: I18n.t(itemVerif.modelData.estado === "verificada" ? "reasignacion.verif_verificada"
                                         : itemVerif.modelData.estado === "trama_presente" ? "reasignacion.verif_trama_presente"
                                         : itemVerif.modelData.estado === "sin_respuesta" ? "reasignacion.verif_sin_respuesta"
                                         : "reasignacion.verif_pendiente", I18n.lang,
                                         { funcion: raiz.nombre(itemVerif.modelData.i18n),
                                           puerto: itemVerif.modelData.puerto })
                            color: itemVerif.modelData.estado === "sin_respuesta" ? Colores.peligroTexto
                                   : itemVerif.modelData.estado === "verificada" ? Colores.menuVerdeTexto
                                   : Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(19)
                        }
                        Text {
                            width: parent.width
                            visible: itemVerif.modelData.pendiente && itemVerif.modelData.falta !== ""
                            wrapMode: Text.WordWrap
                            text: itemVerif.modelData.falta ? I18n.t(itemVerif.modelData.falta, I18n.lang) : ""
                            color: Colores.advertenciaTexto
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(17)
                        }
                    }
                    Boton {
                        id: botonVerif
                        objectName: "botonVerificar_" + itemVerif.modelData.funcion
                        visible: itemVerif.modelData.pendiente
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        width: Escala.px(220); height: Escala.px(60)
                        relleno: Colores.accionPrimario
                        habilitado: control.editable && itemVerif.modelData.falta === ""
                        texto: I18n.t("reasignacion.verificar", I18n.lang)
                        onPulsado: raiz.iniciarVerificacion(itemVerif.modelData)
                    }
                }
            }
        }

        // Conflictos que la pantalla ya ve (el backend vuelve a validar)
        Repeater {
            model: control.conflictos
            delegate: Text {
                required property var modelData
                objectName: "conflictoReasignacion"
                width: cabecera.width
                wrapMode: Text.WordWrap
                text: I18n.t("reasignacion.conflicto", I18n.lang,
                             { funcion: raiz.nombre(modelData.i18n), otra: raiz.nombre(modelData.i18nOtra),
                               puerto: modelData.etiqueta })
                color: Colores.peligroTexto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(20)
            }
        }

        // Encabezado de la tabla
        Row {
            id: encabezadoTabla
            width: parent.width
            height: Escala.px(44)
            leftPadding: Escala.px(16)
            readonly property real util: width - Escala.px(32)
            Repeater {
                model: [
                    { clave: "reasignacion.col_funcion", f: 0.38 },
                    { clave: "reasignacion.col_actual",  f: 0.17 },
                    { clave: "reasignacion.col_nuevo",   f: 0.19 },
                    { clave: "reasignacion.col_tipo",    f: 0.11 },
                    { clave: "reasignacion.col_critica", f: 0.15 }
                ]
                delegate: Text {
                    required property var modelData
                    width: encabezadoTabla.util * modelData.f
                    height: encabezadoTabla.height
                    verticalAlignment: Text.AlignVCenter
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima   // D8-5.4
                    text: I18n.t(modelData.clave, I18n.lang)
                    color: Colores.textoGuia
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(19)
                }
            }
        }
    }

    // ------------------------------------------------------------------ tabla
    Flickable {
        id: tabla
        objectName: "tablaReasignacion"
        anchors.top: cabecera.bottom; anchors.topMargin: Escala.px(6)
        anchors.bottom: acciones.top; anchors.bottomMargin: Escala.px(12)
        width: parent.width
        contentHeight: columnaFilas.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Column {
            id: columnaFilas
            width: parent.width
            spacing: Escala.px(8)
            // P1 (tanda 7): modelo entero y datos por índice; recargar no recrea las filas
            Repeater {
                model: control.filas.length
                delegate: Rectangle {
                    id: fila
                    required property int index
                    readonly property var dato: control.filas[index] || ({})
                    readonly property string nuevo: control.pendientes[dato.funcion] || ""
                    objectName: "filaReasignacion_" + dato.funcion
                    width: columnaFilas.width
                    height: Escala.px(76)
                    radius: Escala.px(12)
                    color: nuevo !== "" ? Colores.advertenciaFondo : Colores.fondoTarjeta
                    border.width: Escala.px(1)
                    border.color: nuevo !== "" ? Colores.advertencia : Colores.bordeDivisor
                    Row {
                        id: celdas
                        anchors.fill: parent
                        anchors.leftMargin: Escala.px(16); anchors.rightMargin: Escala.px(16)
                        Celda {
                            fraccion: 0.38
                            text: raiz.nombre(fila.dato.i18n)
                                  + (fila.dato.habilitada === false
                                     ? " · " + I18n.t("reasignacion.sin_uso", I18n.lang) : "")
                            color: fila.dato.habilitada === false ? Colores.textoSecundario : Colores.textoPrimario
                            font.weight: Tipografia.pesoSemiBold
                        }
                        Celda {
                            fraccion: 0.17
                            text: fila.dato.id_actual || ""
                            font.features: { "tnum": 1 }
                        }
                        Celda {
                            objectName: "puertoNuevo_" + fila.dato.funcion
                            fraccion: 0.19
                            text: fila.nuevo !== "" ? fila.nuevo
                                  : (fila.dato.puerto_guardado !== fila.dato.puerto_actual
                                     ? I18n.t("reasignacion.col_nuevo", I18n.lang) + ": "
                                       + (fila.dato.tipo + " " + String(fila.dato.puerto_guardado).padStart(2, "0"))
                                     : I18n.t("reasignacion.sin_cambio", I18n.lang))
                            color: fila.nuevo !== "" ? Colores.advertenciaTexto : Colores.textoGuia
                            font.weight: fila.nuevo !== "" ? Tipografia.pesoBold : Tipografia.pesoRegular
                        }
                        Celda { fraccion: 0.11; text: fila.dato.tipo || "" }
                        Celda {
                            fraccion: 0.15
                            text: fila.dato.critica ? I18n.t("reasignacion.si", I18n.lang)
                                                    : I18n.t("reasignacion.no", I18n.lang)
                            color: fila.dato.critica ? Colores.peligroTexto : Colores.textoSecundario
                            font.weight: fila.dato.critica ? Tipografia.pesoBold : Tipografia.pesoRegular
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: control.editable
                        onClicked: raiz.abrirSelector(fila.dato.funcion)
                    }
                }
            }
        }
    }

    // ---------------------------------------------------------------- acciones
    Row {
        id: acciones
        anchors.bottom: parent.bottom
        width: parent.width
        height: Escala.px(84)
        spacing: Escala.px(12)
        readonly property real ancho: (width - 2 * spacing) / 3
        Boton {
            objectName: "botonDescartarReasignacion"
            width: acciones.ancho; height: parent.height
            relleno: Colores.textoSecundario
            habilitado: control.cantidadCambios > 0
            texto: I18n.t("reasignacion.descartar", I18n.lang)
            onPulsado: control.descartar()
        }
        Boton {
            objectName: "botonRestaurarFabrica"
            width: acciones.ancho; height: parent.height
            relleno: Colores.menuNaranja
            habilitado: control.editable && (control.hayCambiosGuardados || control.bloqueado
                                             || control.reinicioPendiente)
            texto: I18n.t("reasignacion.restaurar_fabrica", I18n.lang)
            onPulsado: dialogoFabrica.abrir()
        }
        Boton {
            objectName: "botonAplicarReasignacion"
            width: acciones.ancho; height: parent.height
            relleno: Colores.peligroTexto
            habilitado: control.editable && control.cantidadCambios > 0 && control.conflictos.length === 0
            texto: I18n.t("reasignacion.aplicar", I18n.lang)
            onPulsado: raiz.iniciarAplicar()
        }
    }

    // ------------------------------------------------------- selector de puerto
    property var puertosEnEleccion: []
    function abrirSelector(funcion) {
        funcionEnEleccion = funcion
        puertosEnEleccion = control.puertosPara(funcion)
        selector.visible = true
    }
    Item {
        id: selector
        objectName: "selectorPuerto"
        anchors.fill: parent
        visible: false
        z: 50
        Rectangle {
            anchors.fill: parent
            color: "#99000000"
            MouseArea { anchors.fill: parent; onClicked: selector.visible = false }
        }
        Rectangle {
            width: parent.width - Escala.px(40)
            height: Math.min(parent.height - Escala.px(40), columnaSelector.implicitHeight + Escala.px(48))
            anchors.centerIn: parent
            radius: Escala.px(20)
            color: Colores.fondoTarjeta
            MouseArea { anchors.fill: parent }
            Flickable {
                anchors.fill: parent
                anchors.margins: Escala.px(24)
                contentHeight: columnaSelector.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                clip: true
                Column {
                    id: columnaSelector
                    width: parent.width
                    spacing: Escala.px(14)
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: I18n.t("reasignacion.elegir_puerto", I18n.lang, {
                            funcion: raiz.nombre((control.filas.find(f => f.funcion === raiz.funcionEnEleccion) || {}).i18n) })
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: Escala.fuente(26)
                    }
                    Flow {
                        width: parent.width
                        spacing: Escala.px(10)
                        Repeater {
                            model: raiz.puertosEnEleccion
                            delegate: Rectangle {
                                id: chip
                                required property var modelData
                                objectName: "puerto_" + modelData.etiqueta.replace(" ", "_")
                                width: (columnaSelector.width - 3 * Escala.px(10)) / 4
                                height: Escala.px(96)
                                radius: Escala.px(12)
                                color: modelData.actual ? Colores.accionPrimario
                                       : modelData.ocupadoPor !== "" ? Colores.fondoSutil : Colores.fondoTarjeta
                                border.width: Escala.px(2)
                                border.color: modelData.fabrica ? Colores.menuVerde : Colores.bordeDivisor
                                Column {
                                    anchors.centerIn: parent
                                    width: parent.width - Escala.px(10)
                                    Text {
                                        width: parent.width
                                        horizontalAlignment: Text.AlignHCenter
                                        text: chip.modelData.etiqueta
                                        color: chip.modelData.actual ? "white" : Colores.textoPrimario
                                        font.family: Tipografia.familia
                                        font.weight: Tipografia.pesoBold
                                        font.pixelSize: Escala.fuente(22)
                                    }
                                    Text {
                                        width: parent.width
                                        horizontalAlignment: Text.AlignHCenter
                                        wrapMode: Text.Wrap   // D8-5.4: sin recorte; el botón (96 px) admite dos líneas
                                        text: chip.modelData.actual ? I18n.t("reasignacion.puerto_es_actual", I18n.lang)
                                              : chip.modelData.ocupadoPor !== ""
                                                ? raiz.nombre(chip.modelData.ocupadoPor)
                                                : chip.modelData.fabrica ? I18n.t("reasignacion.puerto_de_fabrica", I18n.lang)
                                                : I18n.t("reasignacion.puerto_libre", I18n.lang)
                                        color: chip.modelData.actual ? "white"
                                               : chip.modelData.ocupadoPor !== "" ? Colores.advertenciaTexto
                                               : Colores.textoGuia
                                        font.family: Tipografia.familia
                                        font.pixelSize: Escala.fuente(15)
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        control.elegirPuerto(raiz.funcionEnEleccion, chip.modelData.puerto)
                                        selector.visible = false
                                    }
                                }
                            }
                        }
                    }
                    Boton {
                        width: parent.width; height: Escala.px(72)
                        relleno: Colores.textoSecundario
                        texto: I18n.t("reasignacion.cerrar", I18n.lang)
                        onPulsado: selector.visible = false
                    }
                }
            }
        }
    }

    // --------------------------------------------------------- confirmaciones
    // 1) Alerta de criticidad
    function iniciarAplicar() {
        if (control.cantidadCambios === 0 || control.conflictos.length > 0)
            return
        dialogoAlerta.abrir()
    }
    function _textoAlerta() {
        let t = I18n.t("reasignacion.alerta_titulo", I18n.lang) + "\n\n"
              + I18n.t("reasignacion.alerta_texto", I18n.lang, { n: control.cantidadCambios })
        if (control.criticasPendientes.length > 0)
            t += "\n\n" + I18n.t("reasignacion.alerta_criticas", I18n.lang,
                                 { lista: control.criticasPendientes.map(c => raiz.nombre(c)).join(", ") })
        if (control.hayAnalogicas)
            t += "\n\n" + I18n.t("reasignacion.alerta_analogicas", I18n.lang)
        return t
    }
    DialogoConfirmacion {
        id: dialogoAlerta
        objectName: "dialogoAlertaReasignacion"
        mensaje: raiz._textoAlerta()
        textoConfirmar: I18n.t("reasignacion.continuar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: Colores.advertencia
        onConfirmado: { cerrar(); raiz._pasoReforzada(0) }
    }

    // 2) Confirmación reforzada: escribir el nombre de cada función de seguridad
    property int _indiceReforzada: 0
    function _pasoReforzada(i) {
        const lista = control.reforzadasPendientes
        if (i >= lista.length) {
            dialogoReinicio.abrir()
            return
        }
        _indiceReforzada = i
        dialogoReforzada.abrir()
    }
    DialogoConfirmacion {
        id: dialogoReforzada
        objectName: "dialogoReforzadaReasignacion"
        readonly property var actual: control.reforzadasPendientes[raiz._indiceReforzada] || ({})
        mensaje: I18n.t("reasignacion.reforzada_titulo", I18n.lang) + "\n\n"
                 + I18n.t("reasignacion.reforzada_texto", I18n.lang, { funcion: raiz.nombre(actual.i18n) })
        textoConfirmar: I18n.t("reasignacion.escribir_nombre", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: Colores.peligroTexto
        onConfirmado: {
            cerrar()
            const funcion = actual.funcion
            const i = raiz._indiceReforzada
            if (!raiz.teclado) return
            // Modo acción (TEC-ACC-04): avanza solo al Confirmar el nombre
            raiz.teclado.abrirAlfanumericoAccion(raiz.nombre(actual.i18n), "", 60, false, function (texto) {
                control.fijarNombre(funcion, texto)
                Qt.callLater(() => raiz._pasoReforzada(i + 1))
            })
        }
    }

    // 3) "Se reiniciará el control" y 4) contraseña
    DialogoConfirmacion {
        id: dialogoReinicio
        objectName: "dialogoReinicioReasignacion"
        mensaje: I18n.t("reasignacion.reinicio_titulo", I18n.lang) + "\n\n"
                 + I18n.t("reasignacion.reinicio_texto", I18n.lang)
        textoConfirmar: I18n.t("reasignacion.confirmar_reinicio", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: Colores.peligroTexto
        onConfirmado: { cerrar(); raiz._pedirClave(clave => control.aplicar(clave)) }
    }
    DialogoConfirmacion {
        id: dialogoFabrica
        objectName: "dialogoFabricaReasignacion"
        mensaje: I18n.t("reasignacion.restaurar_fabrica", I18n.lang) + "\n\n"
                 + I18n.t("reasignacion.restaurar_texto", I18n.lang) + "\n\n"
                 + I18n.t("reasignacion.reinicio_titulo", I18n.lang) + "\n"
                 + I18n.t("reasignacion.reinicio_texto", I18n.lang)
        textoConfirmar: I18n.t("reasignacion.confirmar_reinicio", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: Colores.peligroTexto
        onConfirmado: { cerrar(); raiz._pedirClave(clave => control.restaurarFabrica(clave)) }
    }
    // 5) Verificar una función reasignada: instrucciones de la prueba por tipo,
    // nombre escrito si es de seguridad y contraseña
    property var _enVerificacion: ({})
    function iniciarVerificacion(dato) {
        _enVerificacion = dato
        dialogoVerificar.abrir()
    }
    DialogoConfirmacion {
        id: dialogoVerificar
        objectName: "dialogoVerificarReasignacion"
        mensaje: I18n.t("reasignacion.verificar_titulo", I18n.lang,
                        { funcion: raiz.nombre(raiz._enVerificacion.i18n || ""),
                          puerto: raiz._enVerificacion.puerto || "" }) + "\n\n"
                 + I18n.t(raiz._enVerificacion.tipo === "DI" ? "reasignacion.verificar_texto_di"
                          : raiz._enVerificacion.tipo === "DO" ? "reasignacion.verificar_texto_do"
                          : "reasignacion.verificar_texto_ai", I18n.lang)
        textoConfirmar: I18n.t("reasignacion.verificar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: Colores.peligroTexto
        onConfirmado: {
            cerrar()
            const dato = raiz._enVerificacion
            if (!raiz.teclado) return
            const conClave = function (nombreEscrito) {
                raiz._pedirClave(clave => control.verificar(dato.funcion, clave, nombreEscrito))
            }
            if (dato.reforzada)
                raiz.teclado.abrirAlfanumericoAccion(raiz.nombre(dato.i18n), "", 60, false,
                                                     texto => Qt.callLater(() => conClave(texto)))
            else
                conClave("")
        }
    }

    // Modo acción (TEC-ACC-04, PRB-T22-01): la contraseña se envía una sola
    // vez al Confirmar; en vivo, cada tecla era un intento fallido
    function _pedirClave(alConfirmar) {
        if (!raiz.teclado) return
        raiz.teclado.abrirAlfanumericoAccion(I18n.t("reasignacion.clave_titulo", I18n.lang, { usuario: control.usuario }),
                                             "", 64, true, alConfirmar)
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n
import Autoclave.Unidades

// OPCIONES > Entradas / Salidas (planeacion_opciones_entradas_salidas.md).
// Una sola zona de contenido con selector de 4 segmentos (D-ES-01): Entradas,
// Salidas, Temperatura y Presion. La calibracion es una vista de detalle con
// flecha de regreso al segmento de origen. Lectura en vivo cada 1 s mientras la
// seccion esta visible (D-ES-12). La interfaz solo refleja: el backend decide
// (D-ES-07, D-ES-15, D-ES-16).
Item {
    id: raiz
    objectName: "opcionesEntradasSalidas"

    property QtObject teclado: null            // PanelTeclado de la ventana
    property string segmento: "entradas"       // entradas | salidas | temperatura | presion
    property string sensorEnCalibracion: ""
    property string segmentoOrigen: ""
    property double ultimaActividad: Date.now()
    readonly property alias controlador: control
    // true cuando la pantalla debe cerrar el modo prueba al abandonarla
    readonly property bool enCalibracion: sensorEnCalibracion !== ""

    // X1 (tanda 6): fondo opaco; ninguna pantalla debajo se ve a traves de esta
    Rectangle {
        objectName: "fondoOpacoES"
        anchors.fill: parent
        color: Colores.fondoTarjeta
    }

    EntradasSalidasController {
        id: control
        objectName: "entradasSalidasController"
    }

    // Cierra el modo prueba (D-ES-08): al abandonar la seccion, cambiar de
    // segmento o por inactividad. Lo llama tambien Opciones al salir.
    // FASE 6: el controlador decide si hay algo que cerrar (modo prueba activo,
    // entrada en vuelo o sin confirmar). Al destruirse la pantalla la salida se
    // lanza igual y se quita el gancho de cierre de sesion (abandonar).
    function cerrarModoPrueba(causa, destruyendo) {
        if (destruyendo === true) control.abandonar(causa)
        else control.salirModoPrueba(causa)
    }
    function marcarActividad() { ultimaActividad = Date.now() }
    // Corte de 5 min por inactividad de la interfaz: solo aplica si no hay
    // salidas ON. Estado desconocido (sin lista, o sin ninguna salida confirmada
    // ON, p. ej. todas null por enlace caído): el corte aplica (falla cerrada).
    property int plazoInactividadMs: 5 * 60 * 1000
    function hayAlgunaSalidaOn(salidas) {
        var lista = salidas || []
        for (var i = 0; i < lista.length; i++)
            if (lista[i] && lista[i].encendida === true) return true
        return false
    }
    // FASE 6: texto de un boton mientras su operacion va en vuelo
    function textoOperacion(clave, normal) {
        var enCurso = control.operacionEnCurso     // dependencia del enlace
        var e = control.estadoDe(clave)
        if (enCurso && e === "enviando") return I18n.t("operacion.procesando", I18n.lang)
        if (enCurso && e === "verificando") return I18n.t("operacion.verificando", I18n.lang)
        return normal
    }
    // FASE 6: sensor pedido; la calibracion se abre solo con la lectura confirmada
    property string calibracionPedidaTipo: ""
    property string calibracionPedidaSensor: ""
    Connections {
        target: control
        function onOperacionResuelta(clave, estado, mensaje) {
            if (clave !== "cal_cargar") return
            // C1 (revision FASE 6): una confirmacion tardia es de un pedido
            // anterior: no abre nada ni toca el pedido en curso
            if (mensaje === "operacion.confirmada_tarde") return
            // y solo se abre si la calibracion cargada es la del sensor pedido
            if (estado === "confirmada" && raiz.calibracionPedidaSensor !== ""
                    && control.calibracionEs(raiz.calibracionPedidaTipo, raiz.calibracionPedidaSensor)) {
                raiz.segmentoOrigen = raiz.calibracionPedidaTipo
                raiz.sensorEnCalibracion = raiz.calibracionPedidaSensor
            }
            raiz.calibracionPedidaTipo = ""
            raiz.calibracionPedidaSensor = ""
        }
    }

    onSegmentoChanged: {
        if (segmento !== "salidas") cerrarModoPrueba("abandono de la sección")
    }
    Component.onCompleted: { control.cargarCanales(); control.actualizar() }
    Component.onDestruction: cerrarModoPrueba("abandono de la sección", true)
    // P1: otra pantalla encima (Menú principal, ciclo, falla) la oculta en la
    // pila: el modo prueba no sigue sin su ventana a la vista
    onVisibleChanged: if (!visible) cerrarModoPrueba("abandono de la sección")

    // Lectura en vivo: solo corre con la seccion visible (D-ES-12)
    Timer {
        id: sondeo
        interval: 1000
        repeat: true
        running: raiz.visible
        onTriggered: {
            control.actualizar()
            if (control.salidasHabilitadas && Date.now() - raiz.ultimaActividad > raiz.plazoInactividadMs) {
                if (raiz.hayAlgunaSalidaOn(control.salidas)) raiz.marcarActividad()   // se rearma
                else control.salirModoPrueba("inactividad de la interfaz")
            }
        }
    }
    // Keepalive del modo prueba cada 30 s (P-ES-4); FASE 6: detenido mientras
    // una orden de modo prueba va en vuelo o quedo sin confirmar
    Timer {
        interval: 30000
        repeat: true
        running: raiz.visible && control.salidasHabilitadas
        onTriggered: control.keepalive()
    }

    // ------------------------------------------------------------ componentes
    component Chip: Rectangle {
        property string texto: ""
        property color tinta: Colores.textoSecundario
        width: etiqueta.implicitWidth + Escala.px(32)
        height: Escala.px(48)
        radius: Escala.px(24)
        color: Colores.fondoSutil
        Text {
            id: etiqueta
            anchors.centerIn: parent
            text: parent.texto
            color: parent.tinta
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(20)
        }
    }

    component TarjetaCanal: Rectangle {
        id: tarjeta
        property string nombre: ""
        property string idFisico: ""
        default property alias contenido: zona.data
        width: (parent ? parent.width : 0)
        height: Escala.px(132)
        radius: Escala.px(14)
        color: Colores.fondoTarjeta
        border.width: Escala.px(1)
        border.color: Colores.bordeDivisor
        Column {
            anchors.left: parent.left; anchors.leftMargin: Escala.px(20)
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.52
            spacing: Escala.px(4)
            Text {
                width: parent.width
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                text: tarjeta.nombre
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(26)
            }
            Text {
                text: tarjeta.idFisico
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(20)
            }
        }
        Item {
            id: zona
            anchors.right: parent.right; anchors.rightMargin: Escala.px(20)
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.4
            height: parent.height - Escala.px(24)
        }
    }

    component Boton: Rectangle {
        id: boton
        property string texto: ""
        property color relleno: Colores.accionPrimario
        property bool habilitado: true
        signal pulsado()
        signal presionado()
        signal soltado()
        radius: Escala.px(10)
        color: relleno
        opacity: habilitado ? 1.0 : 0.4
        Text {
            anchors.centerIn: parent
            text: boton.texto
            color: Colores.textoSobreAccion
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(22)
        }
        MouseArea {
            id: area
            anchors.fill: parent
            enabled: boton.habilitado
            onClicked: boton.pulsado()
            onPressed: boton.presionado()
            onReleased: boton.soltado()
            onCanceled: boton.soltado()
        }
    }

    component TarjetaSensor: Rectangle {
        id: tarjetaSensor
        // P1 (tanda 7): datos por índice; el Repeater no recrea la tarjeta en
        // cada refresco (el toque de Calibrar no se pierde)
        required property int index
        property var modelData: ({})
        property string tipo: ""
        objectName: "sensor_" + modelData.name
        width: parent ? parent.width : 0
        height: Escala.px(190)
        radius: Escala.px(14)
        color: Colores.fondoTarjeta
        border.width: Escala.px(1); border.color: Colores.bordeDivisor
        Column {
            anchors.left: parent.left; anchors.leftMargin: Escala.px(24)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Escala.px(4)
            Text {
                text: raiz.nombreCanal(tarjetaSensor.modelData.i18n)
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(26)
            }
            Text {
                text: tarjetaSensor.modelData.id + " · " + I18n.t("io.ui.adc", I18n.lang) + " "
                      + (tarjetaSensor.modelData.adc == null ? "—" : tarjetaSensor.modelData.adc)
                color: tarjetaSensor.modelData.valido ? Colores.textoGuia : Colores.advertenciaTexto
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(20)
            }
            Text {
                visible: !tarjetaSensor.modelData.valido
                // U4 / P1 (tanda 7): sin enlace no es el cableado del sensor
                text: control.enlace ? I18n.t("io.ui.sin_lectura", I18n.lang)
                                     : I18n.t("io.ui.enlace_perdido", I18n.lang)
                color: Colores.advertenciaTexto
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(20)
            }
        }
        Text {
            objectName: "valorSensor_" + tarjetaSensor.modelData.name
            anchors.right: botonCalibrar.left; anchors.rightMargin: Escala.px(24)
            anchors.verticalCenter: parent.verticalCenter
            text: tarjetaSensor.modelData.valido
                  ? tarjetaSensor.modelData.valor.toFixed(1)
                        + (tarjetaSensor.tipo === "temperatura" ? " °C" : " kPa")
                  : "---"
            color: tarjetaSensor.modelData.valido ? Colores.textoPrimario : Colores.advertencia
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(54)
            font.features: { "tnum": 1 }
        }
        Boton {
            id: botonCalibrar
            objectName: "botonCalibrar_" + tarjetaSensor.modelData.name
            anchors.right: parent.right; anchors.rightMargin: Escala.px(20)
            anchors.verticalCenter: parent.verticalCenter
            width: Escala.px(170); height: Escala.px(72)
            habilitado: control.puedeCalibrar && tarjetaSensor.modelData.valido
                        && !control.operacionEnCurso
            texto: raiz.calibracionPedidaSensor === tarjetaSensor.modelData.name
                   ? raiz.textoOperacion("cal_cargar", I18n.t("io.ui.calibrar", I18n.lang))
                   : I18n.t("io.ui.calibrar", I18n.lang)
            // FASE 6: se abre en onOperacionResuelta("cal_cargar", "confirmada")
            onPulsado: {
                raiz.calibracionPedidaTipo = tarjetaSensor.tipo
                raiz.calibracionPedidaSensor = tarjetaSensor.modelData.name
                if (!control.cargarCalibracion(tarjetaSensor.tipo, tarjetaSensor.modelData.name)) {
                    raiz.calibracionPedidaTipo = ""
                    raiz.calibracionPedidaSensor = ""
                }
            }
        }
    }


    function nombreCanal(clave) { return I18n.t(clave, I18n.lang) }
    // Tanda 17 (MPR-01): nombre de una salida por su clave (o la clave tal cual)
    function nombreSalida(nombre) {
        const s = (control.salidas || []).find(c => c.name === nombre)
        return s ? raiz.nombreCanal(s.i18n) : String(nombre)
    }

    // ---------------------------------------------------------------- cabecera
    Rectangle {
        id: banda
        objectName: "bandaMensajeES"
        visible: control.mensaje !== ""
        anchors.top: selector.bottom; anchors.topMargin: Escala.px(10)
        width: parent.width
        height: visible ? Escala.px(84) : 0
        radius: Escala.px(12)
        color: Colores.peligroFondo
        z: 5
        Text {
            anchors.fill: parent; anchors.margins: Escala.px(14)
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap
            text: (control.mensaje !== "" ? I18n.t(control.mensaje, I18n.lang) : "")
                  + (control.detalle !== "" ? " " + control.detalle : "")
            color: Colores.peligroTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(21)
        }
        MouseArea { anchors.fill: parent; onClicked: control.limpiarMensaje() }
    }

    SelectorSegmentos {
        id: selector
        objectName: "selectorSegmentosES"
        visible: !raiz.enCalibracion
        anchors.top: parent.top
        width: parent.width
        opciones: [
            { valor: 0, etiqueta: I18n.t("io.ui.seg_entradas", I18n.lang) },
            { valor: 1, etiqueta: I18n.t("io.ui.seg_salidas", I18n.lang) },
            { valor: 2, etiqueta: I18n.t("io.ui.seg_temperatura", I18n.lang) },
            { valor: 3, etiqueta: I18n.t("io.ui.seg_presion", I18n.lang) }
        ]
        valor: ["entradas", "salidas", "temperatura", "presion"].indexOf(raiz.segmento)
        onElegido: (v) => raiz.segmento = ["entradas", "salidas", "temperatura", "presion"][v]
    }

    // ------------------------------------------------------- zona de contenido
    Item {
        id: zonaContenido
        visible: !raiz.enCalibracion
        anchors.top: banda.visible ? banda.bottom : selector.bottom
        anchors.topMargin: Escala.px(14)
        anchors.bottom: pie.top; anchors.bottomMargin: Escala.px(8)
        width: parent.width
        clip: true

        // ---- Entradas / Salidas (X1, tanda 6): una pagina por segmento, cada
        // una con su propio Repeater sobre un modelo fijo. Antes compartian un
        // solo Flow con dos Repeater cuyo modelo alternaba entre la lista y [];
        // ahora una pagina oculta no puede dibujar tarjetas en la otra.
        Flickable {
            id: paginaEntradas
            objectName: "paginaEntradas"
            anchors.fill: parent
            visible: raiz.segmento === "entradas"
            contentHeight: cuadriculaEntradas.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            Flow {
                id: cuadriculaEntradas
                width: parent.width
                spacing: Escala.px(12)
                readonly property real ancho: (width - spacing) / 2

                Repeater {
                    model: control.entradas
                    delegate: TarjetaCanal {
                        id: tarjetaEntrada
                        required property var modelData
                        objectName: "entrada_" + modelData.name
                        width: cuadriculaEntradas.ancho
                        nombre: raiz.nombreCanal(modelData.i18n)
                        idFisico: modelData.id
                        Row {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: Escala.px(8)
                            Rectangle {
                                width: Escala.px(18); height: width; radius: width / 2
                                anchors.verticalCenter: parent.verticalCenter
                                color: tarjetaEntrada.modelData.activo === true ? Colores.menuVerde : "transparent"
                                border.width: Escala.px(2)
                                border.color: tarjetaEntrada.modelData.activo === true ? Colores.menuVerde : Colores.textoGuia
                            }
                            Text {
                                objectName: "estadoEntrada_" + tarjetaEntrada.modelData.name
                                text: tarjetaEntrada.modelData.activo === null
                                      ? I18n.t("io.ui.sin_datos", I18n.lang)
                                      : tarjetaEntrada.modelData.activo
                                        ? I18n.t("io.ui.activo", I18n.lang) : I18n.t("io.ui.inactivo", I18n.lang)
                                color: tarjetaEntrada.modelData.activo === true ? Colores.menuVerdeTexto : Colores.textoSecundario
                                font.family: Tipografia.familia
                                font.weight: Tipografia.pesoBold
                                font.pixelSize: Escala.fuente(22)
                            }
                            // D9-5 (tanda 9): de una entrada NC el estado de arriba
                            // es el interpretado; aquí, en pequeño, el nivel crudo
                            Text {
                                objectName: "nivelCrudo_" + tarjetaEntrada.modelData.name
                                visible: tarjetaEntrada.modelData.nc === true
                                         && tarjetaEntrada.modelData.nivel !== null
                                         && tarjetaEntrada.modelData.nivel !== undefined
                                anchors.verticalCenter: parent.verticalCenter
                                text: visible ? I18n.t("io.ui.nivel_crudo", I18n.lang,
                                                       { nivel: tarjetaEntrada.modelData.nivel ? "1" : "0" })
                                              : ""
                                color: Colores.textoGuia
                                font.family: Tipografia.familia
                                font.pixelSize: Escala.fuente(16)
                            }
                        }
                    }
                }
            }
        }

        Flickable {
            id: paginaSalidas
            objectName: "paginaSalidas"
            anchors.fill: parent
            visible: raiz.segmento === "salidas"
            contentHeight: cabeceraSalidas.height + cuadriculaSalidas.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            Column {
                id: cabeceraSalidas
                width: parent.width
                spacing: Escala.px(10)
                height: implicitHeight + Escala.px(10)

                Rectangle {
                    objectName: "bannerModoPrueba"
                    visible: control.modoPrueba
                    width: parent.width
                    height: Escala.px(110)
                    radius: Escala.px(12)
                    color: Colores.advertenciaFondo
                    border.width: Escala.px(2); border.color: Colores.advertencia
                    Column {
                        anchors.left: parent.left; anchors.leftMargin: Escala.px(20)
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width * 0.42
                        Text {
                            text: I18n.t("io.ui.banner_prueba", I18n.lang)
                            color: Colores.advertenciaTexto
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoBold
                            font.pixelSize: Escala.fuente(26)
                        }
                        Text {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: I18n.t("io.ui.banner_regla", I18n.lang)
                            color: Colores.advertenciaTexto
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(18)
                        }
                    }
                    // Tanda 17 (MPR-01): presión de cámara en la unidad vigente,
                    // refrescada con el estado (1 s); «—» sin lectura
                    Column {
                        objectName: "presionModoPrueba"
                        anchors.left: parent.left; anchors.leftMargin: parent.width * 0.42 + Escala.px(36)
                        anchors.right: parent.right; anchors.rightMargin: Escala.px(310)
                        anchors.verticalCenter: parent.verticalCenter
                        Text {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: I18n.t("io.ui.presion_camara", I18n.lang)
                            color: Colores.advertenciaTexto
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(18)
                        }
                        Text {
                            objectName: "valorPresionModoPrueba"
                            width: parent.width
                            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                            text: Unidades.pres(control.presionCamara, Unidades.version)
                            color: Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoBold
                            font.pixelSize: Escala.fuente(34)
                        }
                    }
                    Boton {
                        objectName: "botonSalirModoPrueba"
                        anchors.right: parent.right; anchors.rightMargin: Escala.px(20)
                        anchors.verticalCenter: parent.verticalCenter
                        width: Escala.px(270); height: Escala.px(70)
                        relleno: Colores.peligroTexto
                        // FASE 6: sin una orden de modo prueba en vuelo (tambien
                        // tras una salida sin confirmar, para reintentar)
                        habilitado: !control.operacionEnCurso || control.estadoDe("modo_prueba") === "inactiva"
                        texto: raiz.textoOperacion("modo_prueba", I18n.t("io.ui.salir_prueba", I18n.lang))
                        onPulsado: control.salirModoPrueba("salida solicitada")
                    }
                }
                // Tanda 17 (MPR-01 / ESG-02): salidas que el modo prueba apagó por
                // sus protecciones (puerta abierta, cámara presurizada)
                Repeater {
                    model: control.modoPrueba ? control.avisosCorte : []
                    delegate: Rectangle {
                        id: avisoCorte
                        required property var modelData
                        required property int index
                        objectName: "avisoCorte_" + index
                        width: cabeceraSalidas.width
                        height: textoCorte.implicitHeight + Escala.px(24)
                        radius: Escala.px(10)
                        color: Colores.peligroFondo
                        Text {
                            id: textoCorte
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.margins: Escala.px(16)
                            anchors.verticalCenter: parent.verticalCenter
                            wrapMode: Text.WordWrap
                            textFormat: Text.PlainText
                            text: (avisoCorte.modelData.clave ? I18n.t(avisoCorte.modelData.clave, I18n.lang)
                                                              : avisoCorte.modelData.texto)
                                  + (avisoCorte.modelData.salida ? " (" + raiz.nombreSalida(avisoCorte.modelData.salida) + ")" : "")
                            color: Colores.peligroTexto
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoSemiBold
                            font.pixelSize: Escala.fuente(20)
                        }
                    }
                }
                Boton {
                    objectName: "botonHabilitarModoPrueba"
                    visible: !control.modoPrueba
                    width: parent.width; height: Escala.px(84)
                    habilitado: control.puedeProbar
                                && (!control.operacionEnCurso || control.estadoDe("modo_prueba") === "inactiva")
                    texto: raiz.textoOperacion("modo_prueba", I18n.t("io.ui.habilitar_prueba", I18n.lang))
                    onPulsado: dialogoPrueba.abrir()
                }
                Text {
                    visible: !control.modoPrueba && !control.puedeProbar
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: I18n.t("io.ui.sin_permiso_prueba", I18n.lang)
                    color: Colores.textoGuia
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(18)
                }
            }

            Flow {
                id: cuadriculaSalidas
                anchors.top: cabeceraSalidas.bottom
                width: parent.width
                spacing: Escala.px(12)
                readonly property real ancho: (width - spacing) / 2

                // P1 (tanda 7): modelo entero (cantidad) y datos por índice. Con la
                // lista como modelo, el refresco de 1 s recreaba todas las tarjetas:
                // la pulsación sostenida perdía su renovación y un toque se perdía
                Repeater {
                    model: control.salidas.length
                    delegate: TarjetaCanal {
                        id: tarjetaSalida
                        required property int index
                        readonly property var modelData: control.salidas[index] || ({})
                        objectName: "salida_" + modelData.name
                        width: cuadriculaSalidas.ancho
                        nombre: raiz.nombreCanal(modelData.i18n)
                        idFisico: modelData.id + (modelData.bloqueada ? " · " + I18n.t("io.ui.bloqueada", I18n.lang) : "")
                        // FASE 6: solo con el modo prueba confirmado y sin orden de
                        // modo prueba en vuelo ni sin confirmar
                        readonly property bool libre: control.salidasHabilitadas && !modelData.bloqueada
                        // M1 (revision FASE 6): el APAGADO de una sostenida encendida
                        // se ofrece siempre con modo prueba o con dudas (salida o
                        // entrada sin confirmar); encender sigue exigiendo `libre`
                        // SMP (tanda 26): `apagar` lo arma el controlador (estado
                        // ordenado si hay orden pendiente; si no, el leído)
                        readonly property bool puedeApagar: !modelData.momentanea
                                                            && modelData.apagar === true
                                                            && (control.modoPrueba || control.pruebaSinConfirmar)
                        // P1 (tanda 7, SAF-01): salida momentánea fijada al pulsar; la
                        // renovación y el apagado usan ese nombre aunque cambien los datos
                        property string pulsada: ""
                        function soltarMomentanea() {
                            renovacion.stop()
                            if (pulsada === "") return
                            var nombre = pulsada
                            pulsada = ""
                            control.accionar(nombre, false, true)
                        }
                        // FASE 6: al deshabilitarse (salida del modo prueba en curso,
                        // orden sin confirmar) se deja de renovar y se suelta la
                        // momentánea con su OFF síncrono (apagar siempre sale)
                        onLibreChanged: if (!libre) soltarMomentanea()
                        Component.onDestruction: if (pulsada !== "" && control) control.accionar(pulsada, false, true)
                        Column {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: Escala.px(6)
                            Text {
                                anchors.right: parent.right
                                text: tarjetaSalida.modelData.encendida === null
                                      ? I18n.t("io.ui.sin_datos", I18n.lang)
                                      : tarjetaSalida.modelData.encendida
                                        ? I18n.t("io.ui.on", I18n.lang) : I18n.t("io.ui.off", I18n.lang)
                                color: tarjetaSalida.modelData.encendida === true ? Colores.menuVerdeTexto : Colores.textoSecundario
                                font.family: Tipografia.familia
                                font.weight: Tipografia.pesoBold
                                font.pixelSize: Escala.fuente(22)
                            }
                            // SMP (tanda 26): marca de orden enviada sin reflejo en /status
                            Text {
                                objectName: "pendienteSalida_" + tarjetaSalida.modelData.name
                                anchors.right: parent.right
                                width: Escala.px(190)
                                visible: tarjetaSalida.modelData.pendiente === true
                                text: I18n.t("io.ui.orden_pendiente", I18n.lang)
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignRight
                                color: Colores.textoGuia
                                font.family: Tipografia.familia
                                font.pixelSize: Escala.fuente(15)
                            }
                            Boton {
                                objectName: "botonSalida_" + tarjetaSalida.modelData.name
                                width: Escala.px(190); height: Escala.px(56)
                                habilitado: tarjetaSalida.libre || tarjetaSalida.puedeApagar
                                relleno: tarjetaSalida.modelData.momentanea ? Colores.menuNaranja
                                         : (tarjetaSalida.modelData.apagar === true ? Colores.peligroTexto : Colores.accionPrimario)
                                texto: I18n.t(tarjetaSalida.modelData.claveBoton || "io.ui.activar", I18n.lang)
                                // sostenida: un toque envía el inverso de lo ordenado (o
                                // de lo leído); momentanea: ON mientras dura la pulsacion
                                onPulsado: {
                                    raiz.marcarActividad()
                                    if (!tarjetaSalida.modelData.momentanea)
                                        control.alternar(tarjetaSalida.modelData.name)
                                }
                                onPresionado: {
                                    raiz.marcarActividad()
                                    if (tarjetaSalida.modelData.momentanea) {
                                        tarjetaSalida.pulsada = tarjetaSalida.modelData.name
                                        // rechazada (no dueño, paro, sin modo prueba): no se renueva
                                        if (control.accionar(tarjetaSalida.pulsada, true, true))
                                            renovacion.start()
                                        else
                                            tarjetaSalida.pulsada = ""
                                    }
                                }
                                onSoltado: tarjetaSalida.soltarMomentanea()
                                // P-ES-3: reenvia ON cada 500 ms mientras se mantiene pulsado
                                Timer {
                                    id: renovacion
                                    interval: 500
                                    repeat: true
                                    onTriggered: {
                                        if (tarjetaSalida.pulsada === "" || !control.salidasHabilitadas
                                                || !control.accionar(tarjetaSalida.pulsada, true, true)) {
                                            stop()
                                            tarjetaSalida.pulsada = ""
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ---- Temperatura / Presion (X1): una pagina por segmento, modelo fijo
        Flickable {
            objectName: "paginaTemperatura"
            anchors.fill: parent
            visible: raiz.segmento === "temperatura"
            contentHeight: columnaTemperatura.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true
            Column {
                id: columnaTemperatura
                width: parent.width
                spacing: Escala.px(12)
                Repeater {
                    model: control.temperatura.length
                    delegate: TarjetaSensor {
                        tipo: "temperatura"
                        modelData: control.temperatura[index] || ({})
                    }
                }
            }
        }
        Flickable {
            objectName: "paginaPresion"
            anchors.fill: parent
            visible: raiz.segmento === "presion"
            contentHeight: columnaPresion.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true
            Column {
                id: columnaPresion
                width: parent.width
                spacing: Escala.px(12)
                Repeater {
                    model: control.presion.length
                    delegate: TarjetaSensor {
                        tipo: "presion"
                        modelData: control.presion[index] || ({})
                    }
                }
            }
        }
    }

    // pie: enlace y periodo de actualizacion
    Text {
        id: pie
        objectName: "pieEnlaceES"
        visible: !raiz.enCalibracion
        anchors.bottom: parent.bottom
        width: parent.width
        height: Escala.px(34)
        verticalAlignment: Text.AlignVCenter
        text: control.enlace ? I18n.t("io.ui.enlace_ok", I18n.lang) : I18n.t("io.ui.enlace_perdido", I18n.lang)
        color: control.enlace ? Colores.textoGuia : Colores.advertenciaTexto
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(18)
    }

    // ---- Calibracion de un sensor (vista de detalle)
    Loader {
        id: cargadorCalibracion
        objectName: "cargadorCalibracion"
        active: raiz.enCalibracion
        anchors.fill: parent
        sourceComponent: OpcionesCalibracionSensor {
            controlador: control
            teclado: raiz.teclado
            segmento: raiz.segmentoOrigen
            sensor: raiz.sensorEnCalibracion
            nombreSensor: {
                var lista = raiz.segmentoOrigen === "temperatura" ? control.temperatura : control.presion
                for (var i = 0; i < lista.length; i++)
                    if (lista[i].name === raiz.sensorEnCalibracion) return raiz.nombreCanal(lista[i].i18n)
                return raiz.sensorEnCalibracion
            }
            onVolver: raiz.sensorEnCalibracion = ""
        }
    }

    // Advertencia previa al modo prueba (D-ES-15): sin esta no se entra
    DialogoConfirmacion {
        id: dialogoPrueba
        objectName: "dialogoModoPrueba"
        mensaje: I18n.t("io.ui.dialogo_titulo", I18n.lang) + "\n\n" + I18n.t("io.ui.dialogo_texto", I18n.lang)
        textoConfirmar: I18n.t("io.ui.continuar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: Colores.advertencia
        onConfirmado: { cerrar(); raiz.marcarActividad(); control.entrarModoPrueba() }
    }

    // Atras desde la barra inferior: sube un nivel (Calibracion -> segmento)
    function subirNivel() {
        if (raiz.enCalibracion) { raiz.sensorEnCalibracion = ""; return true }
        return false
    }
}

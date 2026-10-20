pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

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

    EntradasSalidasController {
        id: control
        objectName: "entradasSalidasController"
    }

    // Cierra el modo prueba (D-ES-08): al abandonar la seccion, cambiar de
    // segmento o por inactividad. Lo llama tambien Opciones al salir.
    function cerrarModoPrueba(causa) {
        if (control.modoPrueba) control.salirModoPrueba(causa)
    }
    function marcarActividad() { ultimaActividad = Date.now() }

    onSegmentoChanged: {
        if (segmento !== "salidas") cerrarModoPrueba("abandono de la sección")
    }
    Component.onCompleted: { control.cargarCanales(); control.actualizar() }
    Component.onDestruction: cerrarModoPrueba("abandono de la sección")

    // Lectura en vivo: solo corre con la seccion visible (D-ES-12)
    Timer {
        id: sondeo
        interval: 1000
        repeat: true
        running: raiz.visible
        onTriggered: {
            control.actualizar()
            if (control.modoPrueba && Date.now() - raiz.ultimaActividad > 5 * 60 * 1000)
                control.salirModoPrueba("inactividad de la interfaz")
        }
    }
    // Keepalive del modo prueba cada 30 s (P-ES-4)
    Timer {
        interval: 30000
        repeat: true
        running: raiz.visible && control.modoPrueba
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
                elide: Text.ElideRight
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
            color: "white"
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

    function nombreCanal(clave) { return I18n.t(clave, I18n.lang) }

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

        // ---- Entradas / Salidas: cuadricula de 2 columnas
        Flickable {
            anchors.fill: parent
            visible: raiz.segmento === "entradas" || raiz.segmento === "salidas"
            contentHeight: cuadricula.implicitHeight + (cabeceraSalidas.visible ? cabeceraSalidas.height : 0)
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: cabeceraSalidas
                visible: raiz.segmento === "salidas"
                width: parent.width
                spacing: Escala.px(10)
                height: visible ? implicitHeight + Escala.px(10) : 0

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
                        width: parent.width * 0.62
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
                    Boton {
                        objectName: "botonSalirModoPrueba"
                        anchors.right: parent.right; anchors.rightMargin: Escala.px(20)
                        anchors.verticalCenter: parent.verticalCenter
                        width: Escala.px(270); height: Escala.px(70)
                        relleno: Colores.peligroTexto
                        texto: I18n.t("io.ui.salir_prueba", I18n.lang)
                        onPulsado: control.salirModoPrueba("salida solicitada")
                    }
                }
                Boton {
                    objectName: "botonHabilitarModoPrueba"
                    visible: !control.modoPrueba
                    width: parent.width; height: Escala.px(84)
                    habilitado: control.puedeProbar
                    texto: I18n.t("io.ui.habilitar_prueba", I18n.lang)
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
                id: cuadricula
                anchors.top: cabeceraSalidas.bottom
                width: parent.width
                spacing: Escala.px(12)
                readonly property real ancho: (width - spacing) / 2

                Repeater {
                    model: raiz.segmento === "entradas" ? control.entradas : []
                    delegate: TarjetaCanal {
                        id: tarjetaEntrada
                        required property var modelData
                        objectName: "entrada_" + modelData.name
                        width: cuadricula.ancho
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
                        }
                    }
                }

                Repeater {
                    model: raiz.segmento === "salidas" ? control.salidas : []
                    delegate: TarjetaCanal {
                        id: tarjetaSalida
                        required property var modelData
                        objectName: "salida_" + modelData.name
                        width: cuadricula.ancho
                        nombre: raiz.nombreCanal(modelData.i18n)
                        idFisico: modelData.id + (modelData.bloqueada ? " · " + I18n.t("io.ui.bloqueada", I18n.lang) : "")
                        readonly property bool libre: control.modoPrueba && !modelData.bloqueada
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
                            Boton {
                                objectName: "botonSalida_" + tarjetaSalida.modelData.name
                                width: Escala.px(190); height: Escala.px(56)
                                habilitado: tarjetaSalida.libre
                                relleno: tarjetaSalida.modelData.momentanea ? Colores.menuNaranja
                                         : (tarjetaSalida.modelData.encendida === true ? Colores.peligroTexto : Colores.accionPrimario)
                                texto: tarjetaSalida.modelData.momentanea
                                       ? I18n.t("io.ui.mantener", I18n.lang)
                                       : (tarjetaSalida.modelData.encendida === true
                                          ? I18n.t("io.ui.apagar", I18n.lang) : I18n.t("io.ui.activar", I18n.lang))
                                // sostenida: un toque alterna; momentanea: ON mientras dura la pulsacion
                                onPulsado: {
                                    raiz.marcarActividad()
                                    if (!tarjetaSalida.modelData.momentanea)
                                        control.accionar(tarjetaSalida.modelData.name,
                                                         tarjetaSalida.modelData.encendida !== true, false)
                                }
                                onPresionado: {
                                    raiz.marcarActividad()
                                    if (tarjetaSalida.modelData.momentanea) {
                                        control.accionar(tarjetaSalida.modelData.name, true, true)
                                        renovacion.start()
                                    }
                                }
                                onSoltado: {
                                    if (tarjetaSalida.modelData.momentanea) {
                                        renovacion.stop()
                                        control.accionar(tarjetaSalida.modelData.name, false, true)
                                    }
                                }
                                // P-ES-3: reenvia ON cada 500 ms mientras se mantiene pulsado
                                Timer {
                                    id: renovacion
                                    interval: 500
                                    repeat: true
                                    onTriggered: control.accionar(tarjetaSalida.modelData.name, true, true)
                                }
                            }
                        }
                    }
                }
            }
        }

        // ---- Temperatura / Presion: una tarjeta por sensor
        Flickable {
            anchors.fill: parent
            visible: raiz.segmento === "temperatura" || raiz.segmento === "presion"
            contentHeight: columnaSensores.implicitHeight
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: columnaSensores
                width: parent.width
                spacing: Escala.px(12)
                Repeater {
                    model: raiz.segmento === "temperatura" ? control.temperatura
                           : raiz.segmento === "presion" ? control.presion : []
                    delegate: Rectangle {
                        id: tarjetaSensor
                        required property var modelData
                        objectName: "sensor_" + modelData.name
                        width: columnaSensores.width
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
                                      + (tarjetaSensor.modelData.adc === null ? "—" : tarjetaSensor.modelData.adc)
                                color: tarjetaSensor.modelData.valido ? Colores.textoGuia : Colores.advertenciaTexto
                                font.family: Tipografia.familia
                                font.pixelSize: Escala.fuente(20)
                            }
                            Text {
                                visible: !tarjetaSensor.modelData.valido
                                text: I18n.t("io.ui.sin_lectura", I18n.lang)
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
                                        + (raiz.segmento === "temperatura" ? " °C" : " kPa")
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
                            texto: I18n.t("io.ui.calibrar", I18n.lang)
                            onPulsado: {
                                if (control.cargarCalibracion(raiz.segmento, tarjetaSensor.modelData.name)) {
                                    raiz.segmentoOrigen = raiz.segmento
                                    raiz.sensorEnCalibracion = tarjetaSensor.modelData.name
                                }
                            }
                        }
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

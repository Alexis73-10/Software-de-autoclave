pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// Reportes › panel del día del calendario de ejecución (REP-07, DR-D05).
// Solo dibujo: `panel` es ReporteDashboard.panelDia (fecha, titulo, estado,
// estado_rotulo, explicacion y los campos de forma/color) y `ciclos` las filas
// de ReporteDashboard.ciclosDia, con la forma del Historial (id, numero, fecha,
// hora, programa, resultado, resultado_detalle, operador, no_conforme). Los
// intentos llegan ya en orden de inicio. Tocar un intento emite cicloElegido
// con la fila: la pantalla abre DetalleCiclo como el Historial.
//
// Sin día elegido (`panel.fecha` vacío): `textoToque` (calendario.texto_toque_dia).
// DR-H01: ningún texto propio dice «conforme» ni «apto»; un ciclo guardado como
// NO CONFORME se rotula «Sin éxito» (DR-D13).
// Medidas con m() (convención D-18); los textos largos bajan la letra, sin elide.
Item {
    id: raiz

    property real escala: 1
    property var panel: ({})
    property var ciclos: []
    property bool cargando: false
    property string error: ""
    property string textoToque: raiz.tx("reportes.cal_toque_dia")
    // Texto y color del resultado a partir de su clave (la pantalla puede cambiarlos)
    property var textoResultado: function (clave) {
        return clave ? I18n.t("menu.resultado_" + String(clave).toLowerCase(), I18n.lang) : "—"
    }
    property var colorResultado: function (clave) {
        return clave === "COMPLETADO" ? Colores.menuVerdeTexto
             : clave === "FALLO" ? Colores.peligroTexto
             : clave === "CANCELADO" ? Colores.advertenciaTexto
             : Colores.textoPrimario
    }

    readonly property bool hayDia: raiz.panel ? String(raiz.panel.fecha || "") !== "" : false
    readonly property var intentos: raiz.ciclos ? raiz.ciclos : []

    signal cicloElegido(var ciclo)

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    function tx(clave) { return I18n.t(clave, I18n.lang) }

    Rectangle {
        anchors.fill: parent
        radius: raiz.m(20)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2)
        border.color: Colores.bordeDivisor
    }

    // sin día elegido
    Text {
        objectName: "textoToqueDia"
        visible: !raiz.hayDia
        anchors.centerIn: parent
        width: parent.width - raiz.m(48)
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: raiz.textoToque
        color: Colores.textoSecundario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
        font.pixelSize: raiz.fuente(26)
    }

    Flickable {
        id: desplazable
        objectName: "desplazablePanelDia"
        visible: raiz.hayDia
        anchors.fill: parent
        anchors.margins: raiz.m(24)
        contentWidth: width
        contentHeight: contenido.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: contenido
            width: desplazable.width
            spacing: raiz.m(14)

            Text {
                objectName: "fechaPanelDia"
                width: parent.width
                text: raiz.panel.titulo || ""
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(30)
            }
            Row {
                width: parent.width
                spacing: raiz.m(14)
                MesMiniatura.Celda {
                    objectName: "marcaEstadoDia"
                    anchors.verticalCenter: parent.verticalCenter
                    datos: raiz.panel
                    diametro: raiz.m(44)
                    escalaCelda: raiz.escala
                    mostrarDia: false
                }
                Text {
                    objectName: "estadoPanelDia"
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - raiz.m(58)
                    text: raiz.panel.estado_rotulo || ""
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(26)
                }
            }
            Text {
                objectName: "explicacionPanelDia"
                width: parent.width
                wrapMode: Text.WordWrap
                text: raiz.panel.explicacion || ""
                visible: text !== ""
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(22)
            }
            Rectangle { width: parent.width; height: raiz.m(2); color: Colores.bordeDivisor }

            Text {
                objectName: "cargandoPanelDia"
                visible: raiz.cargando
                width: parent.width
                text: raiz.tx("reportes.cal_cargando")
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(22)
            }
            Text {
                objectName: "errorPanelDia"
                visible: !raiz.cargando && raiz.error !== ""
                width: parent.width
                wrapMode: Text.WordWrap
                text: raiz.error
                color: Colores.peligroTexto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(22)
            }
            Text {
                objectName: "sinIntentosPanelDia"
                visible: !raiz.cargando && raiz.error === "" && raiz.intentos.length === 0
                width: parent.width
                wrapMode: Text.WordWrap
                text: raiz.tx("reportes.cal_sin_intentos")
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(22)
            }

            Repeater {
                model: raiz.cargando || raiz.error !== "" ? [] : raiz.intentos
                Item {
                    id: fila
                    required property var modelData
                    required property int index
                    objectName: "intento_" + index
                    width: contenido.width
                    height: raiz.m(104)
                    readonly property bool sinExito: modelData.no_conforme === true
                    readonly property string resultado: sinExito
                        ? raiz.tx("reportes.estado_sin_exito")
                        : raiz.textoResultado(modelData.resultado)
                    readonly property color colorRes: sinExito ? Colores.peligroTexto
                                                              : raiz.colorResultado(modelData.resultado)

                    Rectangle {
                        anchors.fill: parent
                        color: Colores.textoPrimario
                        opacity: zona.pressed ? 0.06 : 0
                    }
                    Column {
                        x: 0
                        anchors.verticalCenter: parent.verticalCenter
                        width: (parent.width - raiz.m(48)) * 0.46
                        Text {
                            width: parent.width
                            text: String(fila.modelData.numero) + " · " + String(fila.modelData.hora)
                            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                            color: Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoBold
                            font.pixelSize: raiz.fuente(26)
                        }
                        Text {
                            width: parent.width
                            text: String(fila.modelData.operador || "—")
                            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                            color: Colores.textoSecundario
                            font.family: Tipografia.familia
                            font.pixelSize: raiz.fuente(20)
                        }
                    }
                    Column {
                        x: (parent.width - raiz.m(48)) * 0.46 + raiz.m(12)
                        anchors.verticalCenter: parent.verticalCenter
                        width: (parent.width - raiz.m(48)) * 0.54 - raiz.m(12)
                        Text {
                            objectName: "resultadoIntento_" + fila.index
                            width: parent.width
                            horizontalAlignment: Text.AlignRight
                            text: fila.resultado
                            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                            color: fila.colorRes
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoBold
                            font.pixelSize: raiz.fuente(24)
                        }
                        Text {
                            width: parent.width
                            horizontalAlignment: Text.AlignRight
                            visible: text !== ""
                            text: String(fila.modelData.resultado_detalle || "")
                            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                            color: Colores.textoSecundario
                            font.family: Tipografia.familia
                            font.pixelSize: raiz.fuente(20)
                        }
                    }
                    // chevron_derecha.svg (como ListaCiclos): tinta [12.8, 4.3, 35.2, 43.8]
                    Image {
                        readonly property real _k: raiz.m(22) / (43.8 - 4.3)
                        width: 48 * _k; height: width
                        x: parent.width - raiz.m(8) - 35.2 * _k
                        anchors.verticalCenter: parent.verticalCenter
                        source: "../../assets/iconos/mono/chevron_derecha.svg"
                        sourceSize.width: width
                        sourceSize.height: height
                    }
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width; height: raiz.m(1)
                        color: Colores.bordeDivisor
                    }
                    MouseArea {
                        id: zona
                        anchors.fill: parent
                        onClicked: raiz.cicloElegido(fila.modelData)
                    }
                }
            }
        }
    }
}

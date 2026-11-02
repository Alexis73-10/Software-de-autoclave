pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// Reportes › calendario de ejecución por programa (REP-07, DR-D03..D07).
// Solo dibujo: recibe `calendario` (ui_qml/domain/reporte_dashboard.py,
// presentable()["calendario"]) y no decide nada. Cabecera con título y selector
// de programa (SelectorPrograma: número y nombre, 01 primero), fila de conteo
// por estado, vista de mes (cuadrícula lunes a domingo, círculos >= 64 px) o de
// año (12 MesMiniatura) y la leyenda fija bajo el calendario.
//
// DR-H01: la leyenda es `calendario.leyenda` tal como llega (no se reescribe);
// ningún texto propio dice «conforme» ni «apto».
// Forma además de color (relleno, relleno con punto, sólido, borde grueso, gris,
// punteado, azul, deshabilitado) según los campos de cada celda.
// Textos propios (claves de catálogo, sin literales): reportes.cal_titulo y
// reportes.cal_ver_anio. Medidas con m() (convención D-18).
Item {
    id: raiz

    property real escala: 1
    property var calendario: ({})
    property string diaElegido: ""
    // la pantalla lo pone en true en la vista de mes abierta desde el año (DR-D07)
    property bool puedeVerAnio: false

    // El día tocado sale por diaTocado(fecha): `diaElegido` ya es una propiedad
    // (la pantalla la actualiza al recibir la señal), así que no puede ser señal.
    signal diaTocado(string fecha)
    signal mesElegido(int mes)
    signal programaElegido(int numero)
    signal verAnioPedido()

    readonly property var cal: raiz.calendario ? raiz.calendario : ({})
    readonly property bool vistaAnio: raiz.cal.vista === "anio"
    readonly property bool sinProgramas: raiz.cal.sin_programas === true
    readonly property var conteo: raiz.cal.conteo ? raiz.cal.conteo : []
    readonly property var leyendaEstados: raiz.cal.leyenda_estados ? raiz.cal.leyenda_estados : []

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    function tx(clave) { return I18n.t(clave, I18n.lang) }

    implicitHeight: columna.implicitHeight

    Column {
        id: columna
        width: parent.width
        spacing: raiz.m(16)

        // ------------------------------------------------------ cabecera
        Item {
            id: cabecera
            width: parent.width
            height: Math.max(selector.implicitHeight, raiz.m(88))
            readonly property real anchoSelector: Math.min(raiz.m(520), width * 0.5)
            readonly property real anchoVerAnio: raiz.puedeVerAnio && !raiz.vistaAnio ? raiz.m(200) : 0
            Column {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(0, cabecera.width - cabecera.anchoSelector - cabecera.anchoVerAnio - raiz.m(32))
                Text {
                    objectName: "tituloCalendario"
                    width: parent.width
                    text: raiz.tx("reportes.cal_titulo")
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(30)
                }
                Text {
                    objectName: "periodoCalendario"
                    width: parent.width
                    text: raiz.cal.titulo || ""
                    visible: text !== ""
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(24)
                }
            }
            Rectangle {
                id: botonAnio
                objectName: "botonVerAnio"
                visible: raiz.puedeVerAnio && !raiz.vistaAnio
                anchors.right: selector.left
                anchors.rightMargin: raiz.m(16)
                anchors.verticalCenter: parent.verticalCenter
                width: cabecera.anchoVerAnio; height: raiz.m(72)
                radius: height / 2
                color: zonaAnio.pressed ? Colores.accionFondoTenue : Colores.fondoTarjeta
                border.width: raiz.m(2)
                border.color: Colores.accionPrimario
                Text {
                    anchors.centerIn: parent
                    width: parent.width - raiz.m(24)
                    horizontalAlignment: Text.AlignHCenter
                    text: raiz.tx("reportes.cal_ver_anio")
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                    color: Colores.accionPrimarioTexto
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(24)
                }
                MouseArea { id: zonaAnio; anchors.fill: parent; onClicked: raiz.verAnioPedido() }
            }
            SelectorPrograma {
                id: selector
                objectName: "selectorProgramaCalendario"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: cabecera.anchoSelector
                programas: raiz.cal.programas ? raiz.cal.programas : []
                numero: typeof raiz.cal.programa === "number" ? raiz.cal.programa : 0
                onProgramaElegido: (n) => raiz.programaElegido(n)
            }
        }

        // ------------------------------------------------------ sin programas
        Text {
            objectName: "textoSinProgramas"
            visible: raiz.sinProgramas
            width: parent.width
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            topPadding: raiz.m(40); bottomPadding: raiz.m(40)
            text: raiz.cal.texto_sin_programas || ""
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(26)
        }

        // ------------------------------------------------------ conteo por estado
        Flow {
            objectName: "conteoEstados"
            visible: !raiz.sinProgramas
            width: parent.width
            spacing: raiz.m(8)
            Repeater {
                model: raiz.sinProgramas ? [] : raiz.conteo
                Row {
                    id: chip
                    required property var modelData
                    spacing: raiz.m(8)
                    height: raiz.m(48)
                    objectName: "conteo_" + modelData.estado
                    MesMiniatura.Celda {
                        anchors.verticalCenter: parent.verticalCenter
                        datos: chip.modelData
                        diametro: raiz.m(32)
                        escalaCelda: raiz.escala
                        mostrarDia: false
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: String(chip.modelData.cantidad)
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: raiz.fuente(24)
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: chip.modelData.rotulo
                        color: Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.pixelSize: raiz.fuente(20)
                        rightPadding: raiz.m(16)
                    }
                }
            }
        }

        // ------------------------------------------------------ vista de mes
        MesMiniatura {
            id: vistaMes
            objectName: "vistaMes"
            visible: !raiz.sinProgramas && !raiz.vistaAnio
            width: parent.width
            height: visible ? implicitHeight : 0
            escala: raiz.escala
            compacto: false
            mes: ({ semanas: raiz.cal.semanas ? raiz.cal.semanas : [] })
            diasSemana: raiz.cal.dias_semana ? raiz.cal.dias_semana : []
            diaElegido: raiz.diaElegido
            onDiaTocado: (fecha) => raiz.diaTocado(fecha)
        }

        // ------------------------------------------------------ vista de año
        Grid {
            id: vistaAnio
            objectName: "vistaAnio"
            visible: !raiz.sinProgramas && raiz.vistaAnio
            width: parent.width
            columns: 3
            spacing: raiz.m(14)
            readonly property real ancho: Math.floor((width - spacing * (columns - 1)) / columns)
            Repeater {
                model: raiz.vistaAnio && raiz.cal.meses ? raiz.cal.meses : []
                MesMiniatura {
                    id: mini
                    required property var modelData
                    objectName: "mes_" + modelData.mes
                    width: vistaAnio.ancho
                    height: implicitHeight
                    escala: raiz.escala
                    compacto: true
                    mes: mini.modelData
                    onTocado: raiz.mesElegido(mini.modelData.mes)
                }
            }
        }

        // ------------------------------------------------------ leyenda
        Flow {
            objectName: "leyendaEstados"
            visible: !raiz.sinProgramas
            width: parent.width
            spacing: raiz.m(8)
            Repeater {
                model: raiz.sinProgramas ? [] : raiz.leyendaEstados
                Row {
                    id: item
                    required property var modelData
                    spacing: raiz.m(6)
                    height: raiz.m(36)
                    MesMiniatura.Celda {
                        anchors.verticalCenter: parent.verticalCenter
                        datos: item.modelData
                        diametro: raiz.m(22)
                        escalaCelda: raiz.escala
                        mostrarDia: false
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: item.modelData.rotulo
                        color: Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.pixelSize: raiz.fuente(18)
                        rightPadding: raiz.m(14)
                    }
                }
            }
        }
        // DR-H01: texto fijo que llega del dominio, sin reescribir
        Text {
            objectName: "leyendaCalendario"
            width: parent.width
            wrapMode: Text.WordWrap
            text: raiz.cal.leyenda || ""
            visible: text !== ""
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(20)
        }
    }
}

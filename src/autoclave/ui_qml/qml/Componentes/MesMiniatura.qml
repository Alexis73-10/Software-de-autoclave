import QtQuick
import QtQuick.Shapes
import Tema
import Autoclave.I18n

// Reportes › calendario de ejecución (REP-07, DR-D07): cuadrícula de un mes.
// Solo dibujo: recibe el dict de mes del dominio (ui_qml/domain/reporte_dashboard.py,
// `calendario()["meses"][i]` o `{semanas: calendario["semanas"]}`) y lo pinta.
//
// Dos modos:
//   compacto (miniatura de la vista de año): nombre, mini cuadrícula y resumen;
//     toda la tarjeta es táctil y emite tocado() si el mes está habilitado.
//   completo (vista de mes): solo la cuadrícula lunes a domingo con encabezado
//     de días; cada círculo (>= 64 px) es táctil y emite diaTocado(fecha).
// La forma del día no depende solo del color (DR-D04 / REP-07): relleno,
// relleno con punto, sólido, borde grueso, gris, punteado, azul, deshabilitado.
// Colores solo por clave de Tema/Colores.qml (con respaldo si la clave no existe).
// `MesMiniatura.Celda` (círculo de un día) también lo usan CalendarioEjecucion
// (conteo y leyenda) y PanelDiaCalendario (estado del día).
// Medidas en px del mockup escaladas con `escala` (convención m(), D-18).
Item {
    id: raiz

    property real escala: 1
    // {mes, anio, nombre, nombre_corto, habilitado, resumen, semanas: [[celda x7]]}
    property var mes: ({})
    property var diasSemana: []             // encabezado del modo completo ("Lun"...)
    property bool compacto: true
    property string diaElegido: ""          // AAAA-MM-DD resaltado (modo completo)
    readonly property bool habilitado: raiz.mes ? raiz.mes.habilitado !== false : false
    // lado mínimo de la celda en el modo completo (zona táctil >= 64 px)
    property real ladoMinimoCelda: 64

    signal tocado()
    signal diaTocado(string fecha)

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    readonly property var celdas: {
        const out = []
        const sem = (raiz.mes && raiz.mes.semanas) ? raiz.mes.semanas : []
        for (let i = 0; i < sem.length; i++)
            for (let j = 0; j < sem[i].length; j++)
                out.push(sem[i][j])
        return out
    }
    readonly property int filas: Math.ceil(celdas.length / 7)

    // Círculo de un día. `datos`: forma, relleno, borde, punto, grosor, punteado, dia.
    component Celda: Item {
        id: celda
        property var datos: ({})
        property real diametro: 64
        property real escalaCelda: 1
        property bool mostrarDia: true
        property bool elegida: false
        property bool atenuada: false
        readonly property bool vacia: celda.datos ? celda.datos.vacia === true : true
        readonly property string forma: (celda.datos && celda.datos.forma) || ""
        readonly property bool punteado: celda.datos ? celda.datos.punteado === true : false
        readonly property bool conRelleno: celda.forma === "relleno" || celda.forma === "relleno_punto"
            || celda.forma === "solido" || celda.forma === "gris" || celda.forma === "azul"
            || celda.forma === "borde_grueso"
        readonly property bool oscuro: celda.forma === "solido" || celda.forma === "azul"
        width: diametro; height: diametro
        visible: !celda.vacia
        opacity: celda.forma === "deshabilitado" ? 0.4 : (celda.atenuada ? 0.55 : 1)

        // clave de tema -> color; respaldo si la clave aún no existe (p. ej. exitoFondo)
        function colorTema(clave, respaldo) {
            if (!clave) return "transparent"
            const c = Colores[clave]
            return c !== undefined ? c : respaldo
        }

        Rectangle {
            anchors.centerIn: parent
            width: celda.diametro + celda.escalaCelda * 10; height: width
            radius: width / 2
            color: "transparent"
            visible: celda.elegida
            border.width: Math.max(2, celda.escalaCelda * 4)
            border.color: Colores.accionPrimario
        }
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            visible: !celda.punteado
            color: celda.conRelleno ? celda.colorTema(celda.datos.relleno, Colores.deslizadorPista) : "transparent"
            border.width: Math.max(1, ((celda.datos && celda.datos.grosor) || 1) * celda.escalaCelda * 2)
            border.color: celda.colorTema(celda.datos ? celda.datos.borde : "", Colores.bordeCampo)
        }
        // día sin operación: borde punteado (forma, no solo color)
        Loader {
            anchors.fill: parent
            active: celda.punteado
            sourceComponent: Shape {
                ShapePath {
                    fillColor: "transparent"
                    strokeColor: celda.colorTema(celda.datos.borde, Colores.bordeCampo)
                    strokeWidth: Math.max(1, celda.escalaCelda * 2)
                    strokeStyle: ShapePath.DashLine
                    dashPattern: [3, 3]
                    PathAngleArc {
                        centerX: celda.diametro / 2; centerY: celda.diametro / 2
                        radiusX: celda.diametro / 2 - celda.escalaCelda * 2
                        radiusY: radiusX
                        startAngle: 0; sweepAngle: 360
                    }
                }
            }
        }
        // punto del «éxito tras un fallo previo»
        Rectangle {
            visible: celda.forma === "relleno_punto"
            width: celda.diametro * 0.28; height: width; radius: width / 2
            x: celda.diametro - width * 1.1; y: celda.diametro * 0.02
            color: celda.colorTema(celda.datos ? celda.datos.punto : "", Colores.peligroTexto)
            border.width: Math.max(1, celda.escalaCelda); border.color: Colores.fondoTarjeta
        }
        Text {
            visible: celda.mostrarDia
            anchors.centerIn: parent
            width: parent.width - celda.escalaCelda * 6
            horizontalAlignment: Text.AlignHCenter
            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
            text: celda.datos && celda.datos.dia !== undefined ? String(celda.datos.dia) : ""
            color: celda.oscuro ? Colores.fondoTarjeta : Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Math.max(1, Math.round(celda.diametro * 0.38))
        }
    }

    // ------------------------------------------------------------ compacto
    Rectangle {
        id: tarjeta
        objectName: "tarjetaMes"
        visible: raiz.compacto
        anchors.fill: parent
        radius: raiz.m(16)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2)
        border.color: raiz.habilitado ? Colores.bordeCampo : Colores.bordeDivisor
        opacity: raiz.habilitado ? 1 : 0.45

        Column {
            anchors.fill: parent
            anchors.margins: raiz.m(14)
            spacing: raiz.m(8)
            Text {
                width: parent.width
                text: (raiz.mes && raiz.mes.nombre) || ""
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(26)
            }
            Grid {
                id: minis
                columns: 7
                readonly property real lado: Math.floor(parent.width / 7)
                Repeater {
                    model: raiz.compacto ? raiz.celdas : []
                    Item {
                        id: huecoMini
                        required property var modelData
                        width: minis.lado; height: minis.lado
                        Loader {
                            anchors.centerIn: parent
                            active: !huecoMini.modelData.vacia
                            sourceComponent: Celda {
                                datos: huecoMini.modelData
                                diametro: Math.max(2, minis.lado - raiz.m(6))
                                escalaCelda: raiz.escala
                                mostrarDia: false
                            }
                        }
                    }
                }
            }
            Text {
                width: parent.width
                text: (raiz.mes && raiz.mes.resumen) || ""
                wrapMode: Text.WordWrap
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(20)
            }
        }
        MouseArea {
            anchors.fill: parent
            enabled: raiz.habilitado
            onClicked: raiz.tocado()
        }
    }

    // ------------------------------------------------------------ completo
    Column {
        visible: !raiz.compacto
        width: parent.width
        spacing: 0
        Row {
            width: parent.width
            Repeater {
                model: raiz.compacto ? [] : raiz.diasSemana
                Text {
                    required property var modelData
                    width: parent.width / 7
                    height: raiz.m(44)
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                    text: String(modelData)
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(20)
                }
            }
        }
        Grid {
            id: cuadricula
            objectName: "cuadriculaMes"
            columns: 7
            width: parent.width
            readonly property real lado: Math.max(raiz.m(raiz.ladoMinimoCelda), Math.floor(width / 7))
            Repeater {
                model: raiz.compacto ? [] : raiz.celdas
                Item {
                    id: hueco
                    required property var modelData
                    width: cuadricula.lado; height: cuadricula.lado
                    objectName: modelData.vacia ? "" : "dia_" + modelData.fecha
                    readonly property bool tocable: !modelData.vacia && modelData.tocable !== false
                    Loader {
                        anchors.centerIn: parent
                        active: !hueco.modelData.vacia
                        sourceComponent: Celda {
                            datos: hueco.modelData
                            diametro: Math.max(raiz.m(raiz.ladoMinimoCelda) - raiz.m(12), cuadricula.lado - raiz.m(14))
                            escalaCelda: raiz.escala
                            elegida: hueco.modelData.fecha === raiz.diaElegido
                            atenuada: hueco.modelData.en_periodo === false
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: hueco.tocable
                        onClicked: raiz.diaTocado(hueco.modelData.fecha)
                    }
                }
            }
        }
    }

    implicitHeight: raiz.compacto
        ? raiz.m(28) + raiz.m(40) + raiz.m(16) + minis.lado * raiz.filas + raiz.m(64)
        : raiz.m(44) + cuadricula.lado * raiz.filas
}

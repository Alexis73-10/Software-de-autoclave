import QtQuick
import QtQuick.Shapes
import Tema

// Dona de resultados del periodo (reportes REP-04). Solo dibujo.
// `dona` = presentable()['dona']: {vacia, total, centro, texto_vacio, color_vacio,
// porciones:[{clave, rotulo, cantidad, porcentaje, fraccion, inicio, color}]}.
// Los colores llegan como CLAVES de Tema/Colores; una clave desconocida usa el respaldo del tema.
// Medidas en px del mockup escaladas con `escala` (convencion m(), D-18).
Item {
    id: raiz
    objectName: "graficaDona"

    property real escala: 1
    property var dona: ({ vacia: true, total: 0, centro: "", texto_vacio: "", color_vacio: "bordeCampo", porciones: [] })
    property real diametro: 220
    property real grosor: 34

    readonly property var _d: (dona && typeof dona === "object") ? dona : ({})
    readonly property bool vacia: _d.vacia !== false
    readonly property var porciones: secuencia(_d.porciones)

    // listas que llegan de Python pueden ser secuencias de QVariant, no Array de JS
    function secuencia(v) {
        if (v === undefined || v === null || typeof v === "string" || typeof v.length !== "number") return []
        return Array.prototype.slice.call(v)
    }
    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    function colorTema(clave) {
        var c = Colores[clave]
        return c === undefined ? Colores.textoSecundario : c
    }
    function _num(v) { return (typeof v === "number" && isFinite(v)) ? v : 0 }

    implicitWidth: m(diametro) + m(24) + m(280)
    implicitHeight: Math.max(m(diametro), leyenda.implicitHeight)

    Item {
        id: zona
        objectName: "donaZona"
        width: raiz.m(raiz.diametro); height: width
        anchors.verticalCenter: parent.verticalCenter

        Shape {
            anchors.fill: parent
            ShapePath {
                objectName: "donaFondo"
                strokeColor: raiz.vacia ? raiz.colorTema(raiz._d.color_vacio ?? "bordeCampo") : Colores.bordeDivisor
                strokeWidth: raiz.m(raiz.grosor)
                fillColor: "transparent"
                capStyle: ShapePath.FlatCap
                PathAngleArc {
                    centerX: zona.width / 2; centerY: zona.height / 2
                    radiusX: (zona.width - raiz.m(raiz.grosor)) / 2; radiusY: radiusX
                    startAngle: -90; sweepAngle: 359.99
                }
            }
        }
        Repeater {
            model: raiz.vacia ? [] : raiz.porciones
            Shape {
                id: porcion
                required property var modelData
                required property int index
                objectName: "donaPorcion_" + index
                anchors.fill: zona
                visible: raiz._num(modelData.fraccion) > 0
                ShapePath {
                    strokeColor: raiz.colorTema(porcion.modelData.color)
                    strokeWidth: raiz.m(raiz.grosor)
                    fillColor: "transparent"
                    capStyle: ShapePath.FlatCap
                    PathAngleArc {
                        centerX: zona.width / 2; centerY: zona.height / 2
                        radiusX: (zona.width - raiz.m(raiz.grosor)) / 2; radiusY: radiusX
                        startAngle: -90 + 360 * raiz._num(porcion.modelData.inicio)
                        sweepAngle: Math.min(359.99, 360 * raiz._num(porcion.modelData.fraccion))
                    }
                }
            }
        }
        Text {
            objectName: "donaCentro"
            anchors.centerIn: parent
            width: parent.width - raiz.m(raiz.grosor) * 2 - raiz.m(16)
            horizontalAlignment: Text.AlignHCenter
            text: raiz.vacia ? (raiz._d.texto_vacio ?? "") : (raiz._d.centro ?? "")
            color: raiz.vacia ? Colores.textoGuia : Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(raiz.vacia ? 20 : 44)
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: Escala.fuenteMinima
            wrapMode: Text.NoWrap
        }
    }

    Column {
        id: leyenda
        objectName: "donaLeyenda"
        anchors.left: zona.right
        anchors.leftMargin: raiz.m(24)
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: raiz.m(12)
        Repeater {
            model: raiz.porciones
            Item {
                id: fila
                required property var modelData
                required property int index
                objectName: "donaLeyendaFila_" + index
                width: leyenda.width
                height: raiz.m(36)
                Rectangle {
                    id: punto
                    width: raiz.m(16); height: width; radius: width / 2
                    anchors.verticalCenter: parent.verticalCenter
                    color: raiz.colorTema(fila.modelData.color)
                }
                Text {
                    id: pct
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: raiz.m(70)
                    horizontalAlignment: Text.AlignRight
                    text: raiz.vacia ? "" : String(fila.modelData.porcentaje ?? "")
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: raiz.fuente(20)
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: Escala.fuenteMinima
                    wrapMode: Text.NoWrap
                }
                Text {
                    id: cant
                    anchors.right: pct.left
                    anchors.rightMargin: raiz.m(8)
                    anchors.verticalCenter: parent.verticalCenter
                    width: raiz.m(56)
                    horizontalAlignment: Text.AlignRight
                    text: String(fila.modelData.cantidad ?? 0)
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(22)
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: Escala.fuenteMinima
                    wrapMode: Text.NoWrap
                }
                Text {
                    anchors.left: punto.right
                    anchors.leftMargin: raiz.m(12)
                    anchors.right: cant.left
                    anchors.rightMargin: raiz.m(8)
                    anchors.verticalCenter: parent.verticalCenter
                    text: String(fila.modelData.rotulo ?? "")
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.pixelSize: raiz.fuente(22)
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: Escala.fuenteMinima
                    wrapMode: Text.NoWrap
                }
            }
        }
    }
}

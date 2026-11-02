pragma ComponentBehavior: Bound
import QtQuick
import Tema

// Reportes › Por programa (REP-06). Solo dibujo: `programas` es
// presentable()["programas"] ({numero, nombre, detalle, total, exito_pct,
// ancho 0..1, color: clave de Tema/Colores}) ya ordenado por cantidad. Barra
// verde con éxito >= 95 % y naranja por debajo (umbral visual, lo decide el
// dominio). Sin programas: `textoVacio`. Los textos largos bajan la letra, sin
// elide. Medidas en px del mockup escaladas con `escala` (convención m(), D-18).
Item {
    id: raiz
    objectName: "listaProgramasReporte"

    property real escala: 1
    property var programas: []
    property string textoVacio: ""

    readonly property var filas: secuencia(programas)
    readonly property real altoFila: m(104)

    function secuencia(v) {
        if (v === undefined || v === null || typeof v === "string" || typeof v.length !== "number") return []
        return Array.prototype.slice.call(v)
    }
    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    function colorTema(clave) {
        var c = Colores[clave]
        return c === undefined ? Colores.menuNaranja : c
    }

    implicitHeight: filas.length === 0 ? m(96) : filas.length * altoFila

    Text {
        objectName: "textoVacioProgramas"
        visible: raiz.filas.length === 0
        anchors.centerIn: parent
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: raiz.textoVacio
        color: Colores.textoGuia
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
        font.pixelSize: raiz.fuente(24)
    }

    Column {
        width: parent.width
        Repeater {
            model: raiz.filas
            Item {
                id: fila
                required property var modelData
                required property int index
                objectName: "filaPrograma_" + index
                width: raiz.width
                height: raiz.altoFila

                Rectangle {
                    x: 0; y: raiz.m(14)
                    width: raiz.m(64); height: raiz.m(48); radius: raiz.m(12)
                    color: Colores.accionFondoTenue
                    Text {
                        anchors.centerIn: parent
                        width: parent.width - raiz.m(8)
                        horizontalAlignment: Text.AlignHCenter
                        fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                        text: String(fila.modelData.numero ?? "")
                        color: Colores.accionPrimarioTexto
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: raiz.fuente(24)
                    }
                }
                Text {
                    x: raiz.m(80); y: raiz.m(10)
                    width: parent.width - x - raiz.m(190)
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                    text: String(fila.modelData.nombre ?? "")
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(26)
                }
                Text {
                    x: raiz.m(80); y: raiz.m(46)
                    width: parent.width - x - raiz.m(190)
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                    text: String(fila.modelData.detalle ?? "")
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: raiz.fuente(20)
                }
                Text {
                    objectName: "porcentajePrograma"
                    anchors.right: parent.right
                    y: raiz.m(8)
                    width: raiz.m(170)
                    horizontalAlignment: Text.AlignRight
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                    text: (fila.modelData.exito_pct ?? 0) + "%  ·  " + (fila.modelData.total ?? 0)
                    color: raiz.colorTema(fila.modelData.color)
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(26)
                }
                Rectangle {
                    x: raiz.m(80); y: raiz.m(80)
                    width: parent.width - x; height: raiz.m(10); radius: height / 2
                    color: Colores.fondoSutil
                    Rectangle {
                        objectName: "barraPrograma"
                        width: parent.width * Math.max(0, Math.min(1, fila.modelData.ancho ?? 0))
                        height: parent.height; radius: height / 2
                        color: raiz.colorTema(fila.modelData.color)
                    }
                }
            }
        }
    }
}

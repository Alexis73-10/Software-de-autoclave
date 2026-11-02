pragma ComponentBehavior: Bound
import QtQuick
import Tema

// Reportes › Por operador (REP-11). Solo dibujo: `operadores` es
// presentable()["operadores"] ({filas: [{nombre, iniciales, sin_operador,
// cantidad, fraccion 0..1}], otros: null | {texto, cantidad}, vacia,
// texto_vacio}). Iniciales en círculo, cantidad y barra relativa al mayor
// (máximo 5 filas y el resto como «Otros», lo arma el dominio). Sin elide: el
// nombre baja la letra. Medidas con m() (convención D-18).
Item {
    id: raiz
    objectName: "listaOperadores"

    property real escala: 1
    property var operadores: ({})

    readonly property var _o: (operadores && typeof operadores === "object") ? operadores : ({})
    readonly property var filas: secuencia(_o.filas)
    readonly property var otros: (_o.otros && typeof _o.otros === "object") ? _o.otros : null
    readonly property bool vacia: filas.length === 0
    readonly property real altoFila: m(84)

    function secuencia(v) {
        if (v === undefined || v === null || typeof v === "string" || typeof v.length !== "number") return []
        return Array.prototype.slice.call(v)
    }
    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    implicitHeight: vacia ? m(96) : (filas.length + (otros ? 1 : 0)) * altoFila

    Text {
        objectName: "textoVacioOperadores"
        visible: raiz.vacia
        anchors.centerIn: parent
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: String(raiz._o.texto_vacio ?? "")
        color: Colores.textoGuia
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
        font.pixelSize: raiz.fuente(24)
    }

    Column {
        visible: !raiz.vacia
        width: parent.width
        Repeater {
            model: raiz.filas
            Item {
                id: fila
                required property var modelData
                required property int index
                objectName: "filaOperador_" + index
                width: raiz.width
                height: raiz.altoFila
                Rectangle {
                    x: 0; y: raiz.m(10)
                    width: raiz.m(56); height: width; radius: width / 2
                    color: fila.modelData.sin_operador === true ? Colores.fondoSutil : Colores.accionFondoTenue
                    border.width: raiz.m(2)
                    border.color: fila.modelData.sin_operador === true ? Colores.bordeCampo : Colores.accionPrimario
                    Text {
                        anchors.centerIn: parent
                        width: parent.width - raiz.m(6)
                        horizontalAlignment: Text.AlignHCenter
                        fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                        text: String(fila.modelData.iniciales ?? "")
                        color: Colores.accionPrimarioTexto
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: raiz.fuente(22)
                    }
                }
                Text {
                    x: raiz.m(72); y: raiz.m(6)
                    width: parent.width - x - raiz.m(70)
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                    text: String(fila.modelData.nombre ?? "")
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(24)
                }
                Text {
                    anchors.right: parent.right
                    y: raiz.m(6)
                    width: raiz.m(64)
                    horizontalAlignment: Text.AlignRight
                    text: String(fila.modelData.cantidad ?? 0)
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoBold
                    font.pixelSize: raiz.fuente(26)
                }
                Rectangle {
                    x: raiz.m(72); y: raiz.m(50)
                    width: parent.width - x; height: raiz.m(10); radius: height / 2
                    color: Colores.fondoSutil
                    Rectangle {
                        width: parent.width * Math.max(0, Math.min(1, fila.modelData.fraccion ?? 0))
                        height: parent.height; radius: height / 2
                        color: Colores.accionPrimario
                    }
                }
            }
        }
        Item {
            visible: raiz.otros !== null
            objectName: "filaOtrosOperadores"
            width: raiz.width
            height: raiz.otros ? raiz.altoFila : 0
            Text {
                x: raiz.m(72)
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - x - raiz.m(70)
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                text: raiz.otros ? String(raiz.otros.texto ?? "") : ""
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(24)
            }
            Text {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: raiz.m(64)
                horizontalAlignment: Text.AlignRight
                text: raiz.otros ? String(raiz.otros.cantidad ?? 0) : ""
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(26)
            }
        }
    }
}

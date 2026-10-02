pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Effects
import Tema

// Barra de fases de la pantalla de ciclo en curso
// (planeacion_pantalla_ciclo_en_curso.md §5.3). Ocupa el ancho de la pantalla;
// geometría en px absolutos del mockup (escala = px reales por px del mockup):
// círculos de 85 px con centro en y = 480, entre x = 128 y x = 1068, nombre
// debajo (línea base 550). Las fases que no aplican no llegan en `fases`, y la
// distribución horizontal se recalcula con las que quedan.
Item {
    id: raiz

    property real escala: 1.0
    property var textosJson: ({})
    // [{fase: "vacio", estado: "completada" | "activa" | "pendiente"}], en orden
    property var fases: []

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    function nombre(clave) {
        const f = textosJson ? textosJson.fases : undefined
        return (f && f[clave] !== undefined) ? f[clave] : ""
    }
    // TODO-DISEÑO (plan 14.8): "completada" no tiene diseño; apariencia
    // provisional igual a la activa, pero se mantiene como estado separado.
    function resaltada(estado) { return estado === "activa" || estado === "completada" }

    readonly property real xPrimera: 128
    readonly property real xUltima: 1068
    readonly property real diametro: 85
    function centroX(i) {
        return fases.length > 1
            ? xPrimera + i * (xUltima - xPrimera) / (fases.length - 1)
            : (xPrimera + xUltima) / 2
    }

    readonly property QtObject paleta: QtObject {
        readonly property color pendiente: "#CCCCCC"
        readonly property color activaInicio: "#0B7A80"   // izquierda del círculo activo
        readonly property color activaFin: "#003A9C"      // derecha
        readonly property color conectorInicio: "#003B9B"
        readonly property color conectorFin: "#07BDFF"
        readonly property color etiqueta: "#3C3C3C"
    }

    readonly property string iconosColor: "../../assets/iconos/color/"

    // conectores (debajo de los círculos)
    Repeater {
        model: Math.max(0, raiz.fases.length - 1)
        delegate: Rectangle {
            id: conector
            required property int index
            readonly property bool azul: raiz.resaltada(raiz.fases[conector.index].estado)
            x: raiz.m(raiz.centroX(conector.index) + raiz.diametro / 2 - 1)
            y: raiz.m(477)
            width: raiz.m(raiz.centroX(conector.index + 1) - raiz.centroX(conector.index) - raiz.diametro + 2)
            height: raiz.m(7)
            color: raiz.paleta.pendiente
            gradient: conector.azul ? degradadoConector : null
            Gradient {
                id: degradadoConector
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: raiz.paleta.conectorInicio }
                GradientStop { position: 1.0; color: raiz.paleta.conectorFin }
            }
        }
    }

    Repeater {
        model: raiz.fases
        delegate: Item {
            id: fase
            required property var modelData
            required property int index
            readonly property real cx: raiz.centroX(fase.index)
            anchors.fill: parent

            Rectangle {
                x: raiz.m(fase.cx - raiz.diametro / 2); y: raiz.m(480 - raiz.diametro / 2)
                width: raiz.m(raiz.diametro); height: width; radius: width / 2
                color: raiz.paleta.pendiente
                gradient: raiz.resaltada(fase.modelData.estado) ? degradadoActiva : null
                Gradient {
                    id: degradadoActiva
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: raiz.paleta.activaInicio }
                    GradientStop { position: 1.0; color: raiz.paleta.activaFin }
                }
                Image {
                    anchors.centerIn: parent
                    width: raiz.m(48); height: width   // tinta ≈ 40 px
                    source: raiz.iconosColor + "fase_" + fase.modelData.fase + ".svg"
                    sourceSize.width: width; sourceSize.height: height
                }
            }
            Text {
                x: raiz.m(fase.cx) - width / 2
                y: raiz.m(550) - baselineOffset
                text: raiz.nombre(fase.modelData.fase)
                color: raiz.paleta.etiqueta
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(13.5)
            }
        }
    }
}

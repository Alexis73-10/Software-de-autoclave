pragma ComponentBehavior: Bound
import QtQuick
import Tema

// Selector de periodo de calendario del Historial y de Reportes: filtros
// Diario / Semanal / Mensual y, debajo, el periodo entre flechas (anterior /
// siguiente; la siguiente se apaga en el periodo actual). Solo presentación: el
// periodo lo lleva el puente (domain/navegador_periodo.py).
// Medidas en px del mockup escaladas con `escala` (convención m(), D-18).
// DISEÑO PROVISIONAL: sin diseño del diseñador.
Column {
    id: raiz

    property real escala: 1
    property var textosJson: ({})
    property string periodo: "dia"      // filtro marcado
    property string rotulo: ""          // "Octubre 2026"
    property bool esActual: true

    signal elegido(string periodo)
    signal movido(int pasos)

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    function tx(seccion, clave) {
        const s = textosJson ? textosJson[seccion] : undefined
        return (s && s[clave] !== undefined) ? s[clave] : ""
    }

    spacing: m(20)

    Row {
        spacing: raiz.m(16)
        Repeater {
            model: [["dia", "filtro_diario"], ["semana", "filtro_semanal"], ["mes", "filtro_mensual"]]
            Rectangle {
                id: filtro
                required property var modelData
                readonly property bool marcado: raiz.periodo === modelData[0]
                objectName: "filtro_" + modelData[0]
                width: raiz.m(200); height: raiz.m(60)
                radius: height / 2
                color: marcado ? Colores.accionPrimario : Colores.fondoSutil
                border.width: marcado ? 0 : raiz.m(2)
                border.color: Colores.bordeDivisor
                Text {
                    anchors.centerIn: parent
                    text: raiz.tx("menu", filtro.modelData[1])
                    color: filtro.marcado ? "white" : Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(22)
                }
                MouseArea { anchors.fill: parent; onClicked: raiz.elegido(filtro.modelData[0]) }
            }
        }
    }

    component Flecha: Item {
        id: flecha
        property bool atras: true
        property bool habilitada: true
        signal pulsada()
        width: raiz.m(96); height: parent.height
        opacity: habilitada ? 1 : 0.25
        Rectangle {
            anchors.centerIn: parent
            width: raiz.m(72); height: width; radius: width / 2
            color: Colores.fondoSutil
            border.width: raiz.m(2); border.color: Colores.bordeDivisor
        }
        // tinta de chevron_derecha.svg = [12.8, 4.3, 35.2, 43.8]
        Image {
            readonly property real _k: raiz.m(26) / (43.8 - 4.3)
            width: 48 * _k; height: width
            anchors.centerIn: parent
            rotation: flecha.atras ? 180 : 0
            source: "../../assets/iconos/mono/chevron_derecha.svg"
            sourceSize.width: width
            sourceSize.height: height
        }
        MouseArea { anchors.fill: parent; enabled: flecha.habilitada; onClicked: flecha.pulsada() }
    }

    Item {
        width: raiz.width
        height: raiz.m(72)
        Flecha {
            objectName: "flechaAnterior"
            onPulsada: raiz.movido(-1)
        }
        Text {
            objectName: "rotuloPeriodo"
            anchors.centerIn: parent
            width: parent.width - raiz.m(220)
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            text: raiz.rotulo
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(28)
        }
        Flecha {
            objectName: "flechaSiguiente"
            anchors.right: parent.right
            atras: false
            habilitada: !raiz.esActual
            onPulsada: raiz.movido(1)
        }
    }
}

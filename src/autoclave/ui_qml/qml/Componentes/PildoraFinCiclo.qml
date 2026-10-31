import QtQuick
import Tema
import Autoclave.I18n

// FC-05 / FC-07 (tanda 21, planeacion_fin_de_ciclo.md): píldora junto a
// «Tiempos» en la cabecera de la gráfica de un ciclo terminado.
//   tipo "alarmas"       → roja: «Alarmas (N) · SS s» (SS = segundos del regreso automático)
//   tipo "observaciones" → ámbar: «Observaciones (N)», sin cuenta
// Cualquier otro tipo se dibuja como "alarmas" (falla cerrada). El ancho sigue
// al texto (nunca se recorta): quien la usa ancla su borde derecho antes de
// «Tiempos» (x + width). Tocarla emite pulsada() (volver al panel / abrirlo).
//
// Geometría en px del mockup escalados por m() (`escala`, como GraficaCiclo).
Rectangle {
    id: raiz

    property real escala: 1.0
    property string tipo: "alarmas"
    property int cantidad: 0
    // segundos que faltan para el regreso automático (solo en la roja); < 0 = sin dato
    property int segundos: 0

    signal pulsada()

    readonly property bool esObservaciones: tipo === "observaciones"
    readonly property string texto: esObservaciones
        ? I18n.t("ciclo.pildora_observaciones", I18n.lang, { n: cantidad })
        : I18n.t("ciclo.pildora_alarmas", I18n.lang,
                 { n: cantidad, s: segundos < 0 ? "--" : (segundos < 10 ? "0" + segundos : "" + segundos) })

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    implicitWidth: fila.implicitWidth + m(48)
    implicitHeight: m(58)
    width: implicitWidth
    height: implicitHeight
    radius: height / 2
    color: esObservaciones ? Colores.advertenciaFondo : Colores.peligroFondo
    border.width: m(2)
    border.color: esObservaciones ? Colores.advertencia : Colores.peligroTexto

    Row {
        id: fila
        anchors.centerIn: parent
        spacing: raiz.m(12)
        Rectangle {
            objectName: "puntoPildora"
            anchors.verticalCenter: parent.verticalCenter
            width: raiz.m(14); height: width; radius: width / 2
            color: raiz.esObservaciones ? Colores.advertenciaTexto : Colores.peligroTexto
        }
        Text {
            objectName: "textoPildora"
            anchors.verticalCenter: parent.verticalCenter
            text: raiz.texto
            color: raiz.esObservaciones ? Colores.advertenciaTexto : Colores.peligroTexto
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(22)
            font.features: { "tnum": 1 }   // la cuenta no hace bailar el ancho
        }
    }

    MouseArea { anchors.fill: parent; onClicked: raiz.pulsada() }
}

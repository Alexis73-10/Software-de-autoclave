import QtQuick
import Tema

// Contenido de la tarjeta "Último ciclo" del Resumen del Sistema (§5): fecha y
// hora en negrita 19; "Programa:" y "Resultado:" en regular 17 con el valor en
// negrita. Solo presentación: la pantalla le pasa los textos ya formateados y
// los colores. Va dentro de TarjetaResumen (slot `contenido`, que ocupa toda la
// tarjeta). Líneas base medidas en el v3, relativas a la tarjeta: 231, 280 y 303.
Item {
    id: raiz

    property real escala: 1
    property string fecha: ""
    property string hora: ""
    property string rotuloPrograma: ""
    property string programa: ""
    property string rotuloResultado: ""
    property string resultado: ""
    property color colorPrograma: Colores.menuNaranjaTexto
    property color colorResultado: Colores.menuVerdeTexto

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    anchors.fill: parent

    Text {
        objectName: "fechaUltimoCiclo"
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(implicitWidth, parent.width - raiz.m(16))
        y: raiz.m(231) - baselineOffset
        horizontalAlignment: Text.AlignHCenter
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: raiz.fuente(12)
        // sin ciclo o sin conexión llegan "—" ambos: se muestra uno solo
        text: raiz.fecha === raiz.hora ? raiz.fecha : raiz.fecha + "  " + raiz.hora
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(19)
    }

    component Linea: Row {
        id: linea
        property string rotulo: ""
        property string valor: ""
        property color colorValor: Colores.textoPrimario
        property real bl: 0
        anchors.horizontalCenter: parent.horizontalCenter
        y: raiz.m(bl) - rotuloTexto.baselineOffset
        spacing: raiz.m(6)
        Text {
            id: rotuloTexto
            text: linea.rotulo
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoRegular
            font.pixelSize: raiz.fuente(17)
        }
        Text {
            // no desborda la tarjeta: lo que no cabe se elide
            width: Math.min(implicitWidth, raiz.width - raiz.m(16) - rotuloTexto.width - linea.spacing)
            fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
            text: linea.valor
            color: linea.colorValor
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(17)
        }
    }

    Linea { bl: 280; rotulo: raiz.rotuloPrograma; valor: raiz.programa; colorValor: raiz.colorPrograma }
    Linea { bl: 303; rotulo: raiz.rotuloResultado; valor: raiz.resultado; colorValor: raiz.colorResultado }
}

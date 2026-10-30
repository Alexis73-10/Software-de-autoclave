import QtQuick
import Tema

// Tarjeta de acción del Menú Principal (planeacion_menu_principal_ui_qml.md §5).
// Genérica: sin datos ni lógica de negocio; la pantalla le pasa textos y estado.
//
// Medidas en px del mockup v3 (docs/mockups/menu_principal_v3.png), relativas a
// la esquina de la tarjeta, escaladas con `escala` (px reales por px del mockup;
// convención m() de PantallaPreciclo.qml, D-18). Quien la usa pasa escala = ancho / 1196.
// Medido sobre el v3 (informe de Fase 3): aro de 117 con trazo de 4 centrado en
// (84, 82); título y descripción alineados por línea base desde abajo (última
// línea de la descripción a 32 del borde inferior, interlineado 28; última línea
// del título 41 por encima de la primera de la descripción, interlineado 33);
// flecha de 15 x 24 a 30 del borde derecho y centrada a 62.5 del borde inferior.
// Presionado y deshabilitado sin diseño (pendiente del diseñador): atenuación
// ligera y opacidad 0.4, como los botones de PantallaPreciclo.qml.
Item {
    id: raiz

    property real escala: 1
    property string titulo: ""          // admite "\n" (p. ej. TIEMPO ADICIONAL / DE SECADO)
    property string descripcion: ""     // admite "\n" (los cortes del mockup son explícitos)
    property url icono
    property real tamIcono: 80           // caja del SVG (48 x 48 de viewBox) en px del mockup
    property bool iconoTenido: true      // false = colores propios del SVG (variante color/)
    // El SVG trae su propio aro (círculo de diámetro 40 en el viewBox de 48): no se
    // dibuja otro y el icono se escala para que ese aro mida diametroAro.
    property bool iconoIncluyeAro: false
    property color colorAcento: Colores.textoPrimario
    property color colorTitulo: Colores.textoPrimario
    property bool aroAcento: false       // aro de 4 del color de acento; false = aro gris fino
    property bool conBorde: false        // borde de acento de 4 (Iniciar sesión)
    property real diametroAro: 117
    property real tamTitulo: 28.75       // fila 1: 28.75 / fila 2: 25
    property real tamDescripcion: 24     // fila 1: 24 / fila 2: 21
    property string valor: ""            // valor destacado arriba a la derecha; "" = sin valor
    property bool flechaVisible: true
    // false = tarjeta informativa (secado): no responde al toque ni se ve presionada
    property bool interactiva: true
    // Estado presionado visible; la galería lo fuerza para mostrarlo sin tocar
    property bool presionada: zona.pressed

    signal pulsada()

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    readonly property real _alto: height / escala      // alto en px del mockup
    readonly property real _ancho: width / escala
    readonly property string _iconos: "../../assets/iconos/mono/"

    opacity: enabled ? 1.0 : 0.4

    Rectangle {
        anchors.fill: parent
        radius: raiz.m(26)
        color: Colores.fondoTarjeta
        border.width: raiz.conBorde ? raiz.m(4) : 0
        border.color: raiz.colorAcento
    }

    Rectangle {
        id: aro
        objectName: "aroTarjeta"
        x: raiz.m(84 - raiz.diametroAro / 2); y: raiz.m(82 - raiz.diametroAro / 2)
        width: raiz.m(raiz.diametroAro); height: width
        radius: width / 2
        color: "transparent"
        border.width: raiz.iconoIncluyeAro ? 0 : (raiz.aroAcento ? raiz.m(4) : raiz.m(2))
        border.color: raiz.aroAcento ? raiz.colorAcento : Colores.bordeDivisor

        readonly property real _tam: raiz.iconoIncluyeAro ? width * 48 / 40 : raiz.m(raiz.tamIcono)
        IconoColor {
            visible: raiz.iconoTenido
            anchors.centerIn: parent
            width: aro._tam; height: width
            source: raiz.icono
            color: raiz.colorAcento
        }
        Image {
            visible: !raiz.iconoTenido
            anchors.centerIn: parent
            width: aro._tam; height: width
            source: raiz.icono
            sourceSize.width: width
            sourceSize.height: height
        }
    }

    Text {
        id: textoValor
        objectName: "valorTarjeta"
        visible: raiz.valor !== ""
        x: parent.width - raiz.m(35) - width
        y: raiz.m(101) - baselineOffset
        // no invade el aro: se reduce hasta caber
        width: Math.min(implicitWidth, parent.width - aro.x - aro.width - raiz.m(35 + 16))
        horizontalAlignment: Text.AlignRight
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: raiz.fuente(20)
        text: raiz.valor
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(46)
    }

    readonly property real _xTexto: 29
    readonly property real _anchoTexto: _ancho - _xTexto - (flechaVisible ? 30 + 15 + 16 : 29)

    // Línea base de la primera línea de la descripción (px del mockup desde arriba)
    readonly property real _blDescripcion:
        textoDescripcion.text === "" ? _alto - 32
                                     : _alto - 32 - 28 * (textoDescripcion.lineCount - 1)

    Text {
        id: textoTitulo
        objectName: "tituloTarjeta"
        x: raiz.m(raiz._xTexto)
        width: raiz.m(raiz._anchoTexto)
        // última línea del título 41 por encima de la primera de la descripción
        y: raiz.m((textoDescripcion.text === "" ? raiz._blDescripcion : raiz._blDescripcion - 41)
                  - 33 * (lineCount - 1)) - baselineOffset
        text: raiz.titulo
        wrapMode: Text.WordWrap
        lineHeightMode: Text.FixedHeight
        lineHeight: raiz.m(33)
        color: raiz.colorTitulo
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(raiz.tamTitulo)
    }

    Text {
        id: textoDescripcion
        objectName: "descripcionTarjeta"
        visible: text !== ""
        x: raiz.m(raiz._xTexto)
        width: raiz.m(raiz._anchoTexto)
        y: raiz.m(raiz._blDescripcion) - baselineOffset
        text: raiz.descripcion
        wrapMode: Text.WordWrap
        lineHeightMode: Text.FixedHeight
        lineHeight: raiz.m(28)
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoRegular
        font.pixelSize: raiz.fuente(raiz.tamDescripcion)
    }

    // Flecha: tinta de chevron_derecha.svg = [12.8, 4.3, 35.2, 43.8] en el viewBox de 48;
    // la caja se escala para que la tinta mida 24 de alto como en el v3.
    Image {
        id: flecha
        visible: raiz.flechaVisible
        readonly property real _k: raiz.m(24) / (43.8 - 4.3)
        width: 48 * _k; height: width
        x: parent.width - raiz.m(30) - 35.2 * _k
        y: parent.height - raiz.m(62.5) - (4.3 + 43.8) / 2 * _k
        source: raiz._iconos + "chevron_derecha.svg"
        sourceSize.width: width
        sourceSize.height: height
    }

    // Atenuación ligera mientras se presiona (PROVISIONAL)
    Rectangle {
        anchors.fill: parent
        radius: raiz.m(26)
        color: "#000000"
        opacity: raiz.interactiva && raiz.presionada ? 0.08 : 0.0
    }

    MouseArea {
        id: zona
        anchors.fill: parent
        enabled: raiz.interactiva
        onClicked: raiz.pulsada()
    }
}

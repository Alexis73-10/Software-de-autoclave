import QtQuick
import Tema

// Tarjeta del Resumen del Sistema (planeacion_menu_principal_ui_qml.md §5).
// Genérica, sin datos: aro con icono centrado arriba, rótulo, valor y subrótulo.
// Para Último ciclo, `contenido` reemplaza a valor y subrótulo (ocupa toda la
// tarjeta, con las mismas coordenadas que ella).
// Es un botón (D-20): emite `pulsada`, con estado presionado y deshabilitado,
// sin flecha. Presionado y deshabilitado sin diseño (pendiente del diseñador):
// misma convención que TarjetaMenu.
// Medidas del v3 en px del mockup relativas a la tarjeta, escaladas con `escala`
// (convención m(), D-18): aro de 106 con trazo de 5 centrado a 79 del borde
// superior; rótulo en negrita 20, alineado por abajo (última línea con línea base
// en 186, interlineado 27); valor en negrita 46 con línea base en 258; subrótulo
// regular 19 con línea base en 303.
Item {
    id: raiz

    property real escala: 1
    property url icono                  // SVG mono; se pinta de colorAcento
    property real tamIcono: 76          // caja del SVG en px del mockup (si no incluye aro)
    // El SVG ya trae su aro (círculo de diámetro 40 en el viewBox de 48, p. ej.
    // reproducir.svg): no se dibuja otro y el icono se agranda para que su aro
    // mida lo mismo que el dibujado (106), así no queda un aro doble.
    property bool iconoIncluyeAro: false
    property color colorAcento: Colores.textoPrimario
    property string rotulo: ""          // admite "\n" (PRÓXIMO / MANTENIMIENTO)
    property string valor: ""
    property string subrotulo: ""
    // Contenido propio; si tiene hijos, valor y subrótulo no se muestran
    default property alias contenido: zonaPropia.data
    // false = tarjeta informativa (Ciclos totales): aspecto normal, sin respuesta al toque
    property bool interactiva: true
    // Estado presionado visible; la galería lo fuerza para mostrarlo sin tocar
    property bool presionada: zona.pressed

    signal pulsada()

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    readonly property bool _contenidoPropio: zonaPropia.children.length > 0

    opacity: enabled ? 1.0 : 0.4

    Rectangle {
        anchors.fill: parent
        radius: raiz.m(24)
        color: Colores.fondoTarjeta
    }

    Rectangle {
        id: aro
        objectName: "aroResumen"
        anchors.horizontalCenter: parent.horizontalCenter
        y: raiz.m(79 - 53)
        width: raiz.m(106); height: width
        radius: width / 2
        color: "transparent"
        border.width: raiz.iconoIncluyeAro ? 0 : raiz.m(5)
        border.color: raiz.colorAcento

        IconoColor {
            anchors.centerIn: parent
            width: raiz.iconoIncluyeAro ? parent.width * 48 / 40 : raiz.m(raiz.tamIcono)
            height: width
            source: raiz.icono
            color: raiz.colorAcento
        }
    }

    Text {
        id: textoRotulo
        objectName: "rotuloResumen"
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - raiz.m(16)
        // alineado por abajo: la última línea siempre en 186
        y: raiz.m(186 - 27 * (lineCount - 1)) - baselineOffset
        horizontalAlignment: Text.AlignHCenter
        text: raiz.rotulo
        wrapMode: Text.WordWrap
        maximumLineCount: 2
        lineHeightMode: Text.FixedHeight
        lineHeight: raiz.m(27)
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(20)
    }

    // Valor: se reduce para caber en el ancho sin recortar (mínimo 20 de mockup)
    Text {
        id: textoValor
        objectName: "valorResumen"
        visible: !raiz._contenidoPropio
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - raiz.m(24)
        y: raiz.m(258) - baselineOffset
        horizontalAlignment: Text.AlignHCenter
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: raiz.fuente(20)
        text: raiz.valor
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(46)
    }

    Text {
        visible: !raiz._contenidoPropio && text !== ""
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - raiz.m(16)
        y: raiz.m(303) - baselineOffset
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: raiz.subrotulo
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoRegular
        font.pixelSize: raiz.fuente(19)
    }

    Item {
        id: zonaPropia
        anchors.fill: parent
    }

    // Atenuación ligera mientras se presiona (PROVISIONAL)
    Rectangle {
        anchors.fill: parent
        radius: raiz.m(24)
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

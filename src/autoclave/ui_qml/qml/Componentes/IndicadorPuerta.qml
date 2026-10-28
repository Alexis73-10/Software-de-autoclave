import QtQuick
import QtQuick.Effects
import Tema
import Autoclave.I18n

// FC-11 (tanda 21, docs/mis_plans/planeacion_fin_de_ciclo.md): indicador del
// estado de una puerta SIN actuador en la pantalla de preciclo. Ocupa la caja
// del BotonAccion de puerta (41, 1615, 298, 110 del mockup) y escala con su
// propio ancho (s = width / 298). Mockups: docs/diseno/mockups/fin_de_ciclo/
// preciclo_02..04_*.png.
//
// SOLO MUESTRA: sin MouseArea ni ningún manejador de toque y sin señales; nunca
// envía comandos. No lee UiBridge: quien lo usa le pasa los datos.
//
// Falla cerrada (decisión de la P3, sin confirmar):
//   - «PUERTA CERRADA» solo con datosVigentes y estadoPuerta === "CERRADO"
//     exacto (nombre de DoorState.CERRADO tal como lo publica /status y lo
//     entrega UiBridge.doorState).
//   - «PUERTA —» (gris, sin ícono) si no hay datos vigentes (sin conexión con el
//     backend) o el estado llega vacío/nulo.
//   - «PUERTA ABIERTA» en cualquier otro caso con dato: ABIERTO, ABRIENDO,
//     CERRANDO, ATRAPADA, ERROR, DESCONOCIDO (el backend no la confirma cerrada)
//     y cualquier texto no reconocido.
Item {
    id: raiz

    // ── entradas ──
    property string estadoPuerta: ""      // UiBridge.doorState ("CERRADO", "ABIERTO", ...)
    property bool datosVigentes: false    // UiBridge.connected
    property int numeroPuerta: 1          // 1 o 2: elige close_door_N / open_door_N

    // ── derivadas (solo lectura; las usan las pruebas) ──
    readonly property bool sinDatos: !datosVigentes || estadoPuerta === ""
    readonly property bool cerrada: !sinDatos && estadoPuerta === "CERRADO"
    readonly property string modo: sinDatos ? "sin_datos" : (cerrada ? "cerrada" : "abierta")

    readonly property color colorFondo: modo === "cerrada" ? "#EAF1F8"
                                      : modo === "abierta" ? Colores.advertenciaFondo
                                      : Colores.fondoSutil
    readonly property color colorBorde: modo === "cerrada" ? Colores.fondoBarraSuperior
                                      : modo === "abierta" ? Colores.advertencia
                                      : Colores.bordeCampo
    readonly property color colorTexto: modo === "cerrada" ? Colores.fondoBarraSuperior
                                      : modo === "abierta" ? Colores.advertenciaTexto
                                      : Colores.textoGuia

    readonly property string texto: modo === "cerrada" ? I18n.t("ciclo.puerta_cerrada_estado", I18n.lang)
                                  : modo === "abierta" ? I18n.t("ciclo.puerta_abierta_estado", I18n.lang)
                                  : I18n.t("ciclo.puerta_sin_datos_estado", I18n.lang)

    // escala respecto a la caja del mockup (298 x 110)
    readonly property real s: width / 298
    function m(v) { return v * s }

    implicitWidth: 298; implicitHeight: 110

    Rectangle {
        objectName: "fondoIndicadorPuerta"
        anchors.fill: parent
        radius: raiz.m(14)
        color: raiz.colorFondo
        // alias legible desde las pruebas (border es un grupo sin conversor en Python)
        readonly property color colorBordeAplicado: border.color
        border.color: raiz.colorBorde
        border.width: Math.max(1, raiz.m(2))
    }

    // Ícono del estado: el PNG de puerta (mismo recorte que el BotonAccion de
    // PantallaPreciclo), llevado a blanco con brightness y teñido con
    // colorization al color del texto. MultiEffect no se dibuja con
    // QT_QPA_PLATFORM=offscreen; las pruebas solo miran la fuente y la visibilidad.
    Item {
        id: icono
        objectName: "iconoPuerta"
        visible: raiz.modo !== "sin_datos"
        // centro del círculo del BotonAccion: circuloX 64 + 42 - caja 41 = 65
        x: raiz.m(65) - width / 2
        anchors.verticalCenter: parent.verticalCenter
        height: raiz.m(42); width: height * 607 / 992

        Image {
            id: imgPuerta
            objectName: "imagenPuerta"
            anchors.fill: parent
            source: raiz.modo === "sin_datos" ? ""
                    : Qt.resolvedUrl("../../../images/" + (raiz.cerrada ? "close_door_" : "open_door_")
                                     + (raiz.numeroPuerta === 2 ? 2 : 1) + ".png")
            // caja de tinta de cada PNG (1920x1080), la misma de PantallaPreciclo
            sourceClipRect: raiz.numeroPuerta === 2
                ? (raiz.cerrada ? Qt.rect(653, 37, 603, 962) : Qt.rect(647, 22, 615, 992))
                : (raiz.cerrada ? Qt.rect(670, 37, 598, 962) : Qt.rect(665, 22, 607, 992))
            fillMode: Image.PreserveAspectFit
            visible: false
        }
        MultiEffect {
            anchors.fill: imgPuerta
            source: imgPuerta
            brightness: 1.0
            colorization: 1.0
            colorizationColor: raiz.colorTexto
        }
    }

    // Texto Bold 22, dos líneas como máximo, sin elide ni maximumLineCount
    // (D8-5.4). Con ícono empieza en x 131 (textoX 172 - caja 41); sin ícono va
    // centrado en la caja. Si no cupiera en dos líneas, Fit reduce la fuente.
    Text {
        id: etiqueta
        objectName: "textoIndicadorPuerta"
        readonly property real izquierda: raiz.modo === "sin_datos" ? raiz.m(12) : raiz.m(131)
        x: izquierda
        width: raiz.width - izquierda - raiz.m(12)
        anchors.verticalCenter: parent.verticalCenter
        height: raiz.height - raiz.m(16)
        text: raiz.texto
        color: raiz.colorTexto
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: Math.max(1, Math.round(raiz.m(22)))
        fontSizeMode: Text.Fit
        minimumPixelSize: Math.max(1, Math.round(raiz.m(14)))
        wrapMode: Text.WordWrap
        elide: Text.ElideNone
        horizontalAlignment: raiz.modo === "sin_datos" ? Text.AlignHCenter : Text.AlignLeft
        verticalAlignment: Text.AlignVCenter
        lineHeight: 1.0
    }
}

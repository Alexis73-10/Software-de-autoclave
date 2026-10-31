import QtQuick
import Tema

// Elemento compartido (container transform): un rectángulo "fantasma" viaja
// del rectángulo de la tarjeta de origen al del `destino` (ventana, panel o
// vista que se abre), cambiando de color y de radio, mientras el contenido del
// destino aparece (`opacidadContenido`) y el fondo se atenúa (`opacidadFondo`).
// Al cerrar hace el camino inverso hacia la tarjeta si sigue en pantalla; si no,
// el fantasma se encoge sobre el propio destino.
//
// Va dentro del mismo Item que el destino (o de un ancestro que lo contenga) y
// se rellena a sí mismo con `anchors.fill: parent` por quien lo usa. Origen y
// destino pueden estar en ramas distintas del árbol: las coordenadas se pasan
// por la escena. Sin `origen` (apertura sin tarjeta) solo hay fundido.
//
// No toca la lógica de quien lo usa: el estado "abierto" lo sigue llevando la
// ventana; este componente solo dibuja el viaje (`progreso` 0..1).
Item {
    id: raiz

    property Item origen: null          // tarjeta tocada (se captura al abrir)
    property Item destino: null         // lo que ocupa el sitio final
    property color colorOrigen: Colores.fondoTarjeta
    property color colorDestino: Colores.fondoTarjeta
    property real radioOrigen: Escala.px(26)
    property real radioDestino: Escala.px(24)
    property int duracion: Movimiento.compartidoMs

    property real progreso: 0
    readonly property bool animando: anim.running
    readonly property bool enCurso: progreso > 0
    readonly property real opacidadFondo: progreso
    // el contenido aparece en la segunda mitad del viaje y se va en la primera
    readonly property real opacidadContenido: Math.max(0, Math.min(1, (progreso - 0.45) / 0.55))

    signal abierto()
    signal cerrado()

    property rect _ro: Qt.rect(0, 0, 0, 0)     // rectángulo del origen, en este Item
    property bool _hayOrigen: false

    function _capturarOrigen(tarjeta) {
        if (tarjeta && tarjeta.visible && tarjeta.width > 0 && tarjeta.height > 0) {
            const p = tarjeta.mapToItem(raiz, 0, 0)
            _ro = Qt.rect(p.x, p.y, tarjeta.width, tarjeta.height)
            _hayOrigen = true
            return true
        }
        return false
    }

    function abrir(tarjeta) {
        origen = tarjeta ?? null
        anim.stop()
        if (Movimiento.instantaneo) {
            _hayOrigen = false
            progreso = 1
            abierto()
            return
        }
        if (!_capturarOrigen(origen))
            _hayOrigen = false
        if (progreso <= 0)
            progreso = 0.0001
        anim.to = 1
        anim.start()
    }

    function cerrar() {
        anim.stop()
        if (Movimiento.instantaneo || progreso <= 0) {
            progreso = 0
            _alTerminar()
            return
        }
        _capturarOrigen(origen)      // la tarjeta pudo moverse (lista desplazada)
        anim.to = 0
        anim.start()
    }

    function _alTerminar() {
        if (progreso >= 1)
            abierto()
        else if (progreso <= 0) {
            origen = null
            cerrado()
        }
    }

    NumberAnimation {
        id: anim
        target: raiz
        property: "progreso"
        duration: raiz.duracion
        easing.type: Easing.InOutCubic
        onFinished: raiz._alTerminar()
    }

    Rectangle {
        id: fantasma
        visible: raiz.progreso > 0 && raiz.progreso < 1 && raiz.destino !== null
        z: 0
        readonly property real t: raiz.progreso
        readonly property point pd: raiz.destino ? raiz.destino.mapToItem(raiz, 0, 0) : Qt.point(0, 0)
        readonly property real wd: raiz.destino ? raiz.destino.width : 0
        readonly property real hd: raiz.destino ? raiz.destino.height : 0
        // sin tarjeta de origen: nace pequeño y centrado sobre el destino
        readonly property real xo: raiz._hayOrigen ? raiz._ro.x : pd.x + wd * 0.04
        readonly property real yo: raiz._hayOrigen ? raiz._ro.y : pd.y + hd * 0.04
        readonly property real wo: raiz._hayOrigen ? raiz._ro.width : wd * 0.92
        readonly property real ho: raiz._hayOrigen ? raiz._ro.height : hd * 0.92
        x: xo + (pd.x - xo) * t
        y: yo + (pd.y - yo) * t
        width: wo + (wd - wo) * t
        height: ho + (hd - ho) * t
        radius: raiz.radioOrigen + (raiz.radioDestino - raiz.radioOrigen) * t
        color: Qt.rgba(raiz.colorOrigen.r + (raiz.colorDestino.r - raiz.colorOrigen.r) * t,
                       raiz.colorOrigen.g + (raiz.colorDestino.g - raiz.colorOrigen.g) * t,
                       raiz.colorOrigen.b + (raiz.colorDestino.b - raiz.colorOrigen.b) * t,
                       1)
        border.width: 0
    }
}

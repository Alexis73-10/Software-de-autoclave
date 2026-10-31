import QtQuick

// Conector entre dos círculos de la barra de fases (llenado de fases, contrato
// A-3). Pista gris con un relleno azul que crece de izquierda a derecha. Solo
// se llena cuando la fase de la izquierda pasa a "completada" (`lleno`).
// BarraFases decide el modo con aplicar(modo, lleno):
//   "fijar" sin animación, "salto" corto, "cierre" espera cierreMs y llena en
//   conectorMs.
Item {
    id: raiz

    property real escala: 1.0
    property bool lleno: false
    property QtObject tiempos: null
    property bool instantaneo: false

    property real _p: 0.0
    // 0..1; lo lee el chorro del círculo siguiente
    readonly property real progreso: _p

    readonly property int _cierreMs: tiempos ? tiempos.cierreMs : 300
    readonly property int _conectorMs: tiempos ? tiempos.conectorMs : 600
    readonly property int _saltoMs: tiempos ? tiempos.saltoMs : 400

    function _terminar() {
        if (animCierre.running) animCierre.complete()
        if (animSalto.running) animSalto.complete()
    }

    function aplicar(modo, nuevoLleno) {
        _terminar()
        lleno = nuevoLleno
        const objetivo = nuevoLleno ? 1.0 : 0.0
        if (modo === "fijar" || instantaneo) {
            _p = objetivo
        } else if (modo === "cierre" && nuevoLleno) {
            _p = 0.0
            animCierre.restart()
        } else {
            animSalto.to = objetivo
            animSalto.restart()
        }
    }

    SequentialAnimation {
        id: animCierre
        PauseAnimation { duration: raiz._cierreMs }
        NumberAnimation { target: raiz; property: "_p"; to: 1.0
                          duration: raiz._conectorMs; easing.type: Easing.InOutQuad }
    }
    NumberAnimation {
        id: animSalto
        target: raiz; property: "_p"
        duration: raiz._saltoMs; easing.type: Easing.OutQuad
    }

    Rectangle {
        anchors.fill: parent
        color: "#CCCCCC"
    }
    Rectangle {
        objectName: "rellenoConector"
        width: raiz.width * raiz._p
        height: parent.height
        clip: true
        visible: width > 0
        Rectangle {
            width: raiz.width; height: raiz.height
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "#003B9B" }
                GradientStop { position: 1.0; color: "#07BDFF" }
            }
        }
    }
}

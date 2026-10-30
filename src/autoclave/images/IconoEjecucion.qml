import QtQuick 2.15

// Indicador de "en ejecución": engranaje + anillo de flechas en contra-rotación.
// Usar RotationAnimator (no RotationAnimation): corre en el hilo de render
// y no se congela si el hilo de UI está ocupado.
Item {
    id: root
    property bool running: false      // enlazar al estado del ciclo (True = en ejecución)
    property int size: 48

    width: size
    height: size

    Image {                           // anillo de flechas: sentido horario (coincide con las puntas)
        id: flechas
        anchors.fill: parent
        source: "flechas.svg"
        sourceSize: Qt.size(root.size * 2, root.size * 2)   // rasteriza a 2x: bordes nítidos
        smooth: true
        antialiasing: true
        RotationAnimator on rotation {
            running: root.running
            from: 0; to: 360
            duration: 6000
            loops: Animation.Infinite
        }
    }

    Image {                           // engranaje: antihorario, más rápido que el anillo
        id: engranaje
        anchors.fill: parent
        source: "engranaje.svg"
        sourceSize: Qt.size(root.size * 2, root.size * 2)
        smooth: true
        antialiasing: true
        RotationAnimator on rotation {
            running: root.running
            from: 0; to: -360
            duration: 4000
            loops: Animation.Infinite
        }
    }
}

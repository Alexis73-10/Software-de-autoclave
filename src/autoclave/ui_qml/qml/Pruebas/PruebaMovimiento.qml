import QtQuick
import QtQuick.Window
import Tema
import "../Componentes"

// Arnés de tests/test_movimiento_ui_qml.py: una tarjeta que abre una ventana
// flotante (elemento compartido) y dos secciones que se funden (crossfade).
// Fuerza Movimiento.instantaneo = false para ejercitar las animaciones.
Window {
    id: ventanaPrueba
    width: 1200; height: 1920
    visible: true
    Component.onCompleted: Movimiento.instantaneo = false

    property bool primera: true

    Item {
        anchors.fill: parent

        TarjetaMenu {
            objectName: "tarjetaPrueba"
            escala: 1
            x: 60; y: 100; width: 700; height: 320
            titulo: "Tarjeta"
            descripcion: "abre la ventana"
            onPulsada: ventana.abrir()
        }
        VentanaFlotante {
            id: ventana
            objectName: "ventanaPrueba"
            escala: 1
            altoTarjeta: 800
            titulo: "Ventana"
            Text { text: "contenido" }
        }
        CargadorSeccion {
            objectName: "seccionA"
            seleccionada: ventanaPrueba.primera
            x: 0; y: 600; width: 300; height: 100
            sourceComponent: Rectangle { color: "red" }
        }
        CargadorSeccion {
            objectName: "seccionB"
            seleccionada: !ventanaPrueba.primera
            x: 400; y: 600; width: 300; height: 100
            sourceComponent: Rectangle { color: "blue" }
        }
    }
}

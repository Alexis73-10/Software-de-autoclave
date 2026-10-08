pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "Pantallas"
import "Componentes"

// Host de la pantalla Nuevo Usuario dentro de la UI PySide (QQuickWidget de
// ui_pyside/views/nuevo_usuario/vista.py; alojamiento (a) de G0 en
// planeacion_nuevo_usuario.md). Hace lo mismo que Main.qml para una sola
// pantalla: fija la Escala del lienzo 1200x1920 y pone el PanelTeclado sobre
// ella. `puente` y `textosJson` los inyecta la vista (setInitialProperties).
Item {
    id: host

    property QtObject puente: null
    property var textosJson: ({})

    // La vista los llama al ocultarse / mostrarse
    function limpiar() { pantalla.limpiar() }

    Rectangle {
        anchors.fill: parent
        color: Colores.fondoMarinoOscuro   // franjas si la ventana no es 5:8
    }

    Binding {
        target: Escala
        property: "factor"
        value: Math.min(host.width / Escala.anchoDiseno, host.height / Escala.altoDiseno)
    }

    Item {
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoDiseno)
        anchors.centerIn: parent
        clip: true

        NuevoUsuario {
            id: pantalla
            anchors.fill: parent
            teclado: panelTeclado
            puente: host.puente
            textosJson: host.textosJson
        }

        PanelTeclado {
            id: panelTeclado
            objectName: "panelTeclado"
            textosJson: host.textosJson
        }
    }
}

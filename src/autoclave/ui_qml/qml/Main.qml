import QtQuick
import Tema
import "Pantallas"

Window {
    id: ventana
    width: 600; height: 960   // 5:8, igual que el lienzo de Escala
    visibility: Window.Windowed   // producción: Window.FullScreen
    visible: true
    color: Colores.fondoMarinoOscuro

    Binding {
        target: Escala
        property: "factor"
        value: Math.min(ventana.width / Escala.anchoDiseno,
                        ventana.height / Escala.altoDiseno)
    }

    // Navegación provisional de 2 estados — el patrón definitivo (StackView vs.
    // navegación plana) sigue sin decidirse; esto se reemplaza sin tocar pantallas.
    property string pantallaActual: "arranque"

    Item {
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoDiseno)
        anchors.centerIn: parent
        clip: true

        Loader {
            anchors.fill: parent
            sourceComponent: ventana.pantallaActual === "arranque"
                             ? arranqueComp : loginComp
        }
    }

    Component {
        id: arranqueComp
        Arranque { onTocado: ventana.pantallaActual = "login" }
    }
    Component { id: loginComp; Login {} }
}

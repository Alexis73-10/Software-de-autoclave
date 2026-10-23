pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n
import "Pantallas"

// W10 (tanda 10, D10-4.1): ventana de la pantalla 2 mientras la pantalla 1
// está en el asistente de instalación (sin perfil). La abre ui_qml/app.py en
// lugar de Main.qml para la puerta 2. Es el Reposo (logo y reloj) con el aviso
// «Instalación en curso en la pantalla 1»; no responde al toque ni usa el
// backend. Al terminar la instalación, el lanzador la cierra y abre la
// pantalla 2 con el flujo normal (D10-4.2). Mismo escalado que Main.qml.
Window {
    id: ventana
    width: 600; height: 960
    visible: true
    color: Colores.fondoMarinoOscuro

    Binding {
        target: Escala
        property: "factor"
        value: Math.min(ventana.width / Escala.anchoDiseno, ventana.height / Escala.altoDiseno)
    }

    Item {
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoDiseno)
        anchors.centerIn: parent
        clip: true

        Reposo {
            objectName: "reposoInstalacion"
            anchors.fill: parent
            tactil: false
            aviso: I18n.t("instalacion.aviso_pantalla2", I18n.lang)
        }
    }
}

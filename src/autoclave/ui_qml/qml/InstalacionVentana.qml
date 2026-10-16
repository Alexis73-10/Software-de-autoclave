pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "Pantallas"
import "Componentes"

// Ventana del asistente de instalación (tanda 2026-10-14 T9, ARR-02 / MIG-07).
// La abre ui_qml/app.py en lugar de Main.qml cuando falta el perfil de
// instalación o es inválido, solo en la ventana principal (puerta 1). El
// puente es el real (bridge/puente_instalacion.py): escribe
// installation_profile.json. Al terminar, el botón del resultado cierra la
// aplicación con el código 3 (CODIGO_INSTALACION_TERMINADA): el lanzador no la
// relanza (TMG-02 de T9) y el texto pide reiniciar el software (el backend
// arrancó sin perfil y debe reiniciarse). Mismo escalado que Main.qml.
Window {
    id: ventana
    width: 600; height: 960
    visible: true
    color: Colores.fondoMarinoOscuro

    property QtObject puenteInstalacion: null

    Binding {
        target: Escala
        property: "factor"
        value: Math.min(ventana.width / Escala.anchoDiseno, ventana.height / Escala.altoDiseno)
    }

    Item {
        id: lienzo
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoDiseno)
        anchors.centerIn: parent
        clip: true

        Instalacion {
            objectName: "asistenteInstalacion"
            anchors.fill: parent
            puente: ventana.puenteInstalacion
            teclado: panelTeclado
            onInstalacionCompletada: Qt.exit(3)
        }
        PanelTeclado {
            id: panelTeclado
        }
    }
}

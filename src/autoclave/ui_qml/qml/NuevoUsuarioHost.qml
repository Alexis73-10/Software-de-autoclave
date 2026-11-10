pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Apariencia
import "Pantallas"
import "Componentes"

// Host de la pantalla Nuevo Usuario dentro de la UI PySide (QQuickWidget de
// ui_pyside/views/nuevo_usuario/vista.py; alojamiento (a) de G0 en
// planeacion_nuevo_usuario.md). Hace lo mismo que Main.qml para una sola
// pantalla: fija la Escala del lienzo 1200x1920 y pone el PanelTeclado sobre
// ella. `puente` lo inyecta la vista (setInitialProperties); textos: singleton I18n.
Item {
    id: host
    // Modo oscuro: el tema vigente (Apariencia) enlazado a Colores; ninguna
    // pantalla pregunta por el tema, solo leen Colores.*
    Binding { target: Colores; property: "oscuro"; value: Apariencia.oscuro }
    // Orientación del lienzo (tanda horizontal): la del tamaño real de esta
    // ventana, que app.py pone en pantalla completa en el monitor elegido
    Binding { target: Escala; property: "horizontal"; value: Escala.esHorizontal(host.width, host.height) }

    property QtObject puente: null

    // La vista los llama al ocultarse / mostrarse
    function limpiar() { pantalla.limpiar() }

    Rectangle {
        anchors.fill: parent
        color: Colores.fondoMarinoOscuro   // franjas si la ventana no es 5:8
    }

    // Proyección del lienzo (tanda responsive): la regla vive en Escala; el
    // tamaño es el del QQuickWidget que la aloja (pantalla de alto fijo).
    readonly property real dprPantalla: Screen.devicePixelRatio
    Binding { target: Escala; property: "dpr"; value: host.dprPantalla }
    Binding {
        target: Escala
        property: "factor"
        value: Escala.factorPara(host.width, host.height)
    }
    Binding { target: Escala; property: "anchoLienzo"; value: Escala.anchoLienzoPara(host.width, host.height) }
    Binding { target: Escala; property: "altoLienzo"; value: Escala.altoLienzoPara(host.width, host.height) }

    // el lienzo mide lo mismo que el widget (sin franjas)
    Item {
        width: Escala.px(Escala.anchoLienzo)
        height: Escala.px(Escala.altoLienzo)
        anchors.centerIn: parent
        clip: true

        NuevoUsuario {
            id: pantalla
            anchors.fill: parent
            teclado: panelTeclado
            puente: host.puente
        }

        PanelTeclado {
            id: panelTeclado
            objectName: "panelTeclado"
        }
    }
}

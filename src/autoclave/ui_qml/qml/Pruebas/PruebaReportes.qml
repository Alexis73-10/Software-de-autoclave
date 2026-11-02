pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Pantallas"
import "../Componentes"

// PRUEBA (etapa E de planeacion_dashboard_reportes.md): arnés de la pantalla
// Reportes. NO es parte de la navegación de producción (Main.qml la apila
// desde el Menú Principal). Lo usan tests/banco/rep_capturas_reportes.py y
// tests/test_rep_pantalla_reportes_qml.py con un cliente de ejemplo
// (tests/helpers/reportes_ejemplo.py: datos ficticios, no son lecturas reales).
// Mismo escalado que Main.qml. Las señales solo se registran en consola.
Window {
    id: ventana
    width: 600; height: 960
    visible: true
    color: Colores.fondoMarinoOscuro

    property QtObject reporteDashboard: null
    property QtObject acciones: null
    property QtObject historial: null
    // REP-13: sin sesión el correo solo ofrece los destinatarios guardados
    property bool sesionActiva: true
    property int inicios: 0
    property int salidas: 0

    Binding {
        target: Escala
        property: "factor"
        value: Math.min(ventana.width / Escala.anchoDiseno, ventana.height / Escala.altoDiseno)
    }
    Binding {
        target: Escala
        property: "altoLienzo"
        value: Math.max(Escala.altoDiseno, ventana.height / Escala.factor)
    }

    Item {
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoLienzo)
        anchors.centerIn: parent
        clip: true

        Reportes {
            id: pantalla
            objectName: "pantallaReportes"
            anchors.fill: parent
            reporteDashboard: ventana.reporteDashboard
            acciones: ventana.acciones
            historial: ventana.historial
            teclado: panelTeclado
            sesionActiva: ventana.sesionActiva
            onInicioPulsado: { ventana.inicios += 1; console.log("Reportes: inicio") }
            onSalirPulsado: { ventana.salidas += 1; console.log("Reportes: salir") }
        }
        PanelTeclado {
            id: panelTeclado
            objectName: "panelTeclado"
        }
    }
}

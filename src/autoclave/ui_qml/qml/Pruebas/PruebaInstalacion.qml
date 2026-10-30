pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Pantallas"
import "../Componentes"

// PRUEBA (planeacion_menu_instalacion_ui.md): arnés del asistente de instalación.
// NO es parte de la navegación de producción: lo abre ui_qml/prueba_instalacion.py.
// No escribe ningún perfil ni toca el backend: el puente es de EJEMPLO
// (capacidades por clase copiadas de installation/equipment.py; acepta el código
// de activación ABCDEFGHIJKL; instalar() solo devuelve ok). Mismo escalado que Main.qml.
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

    QtObject {
        id: puenteEjemplo
        readonly property var clases: [
            { valor: "mesa_n",     vacio: false, chaqueta: false, liquidos: false, puertasMax: 1, enfriamientoMax: 0 },
            { valor: "mesa_b",     vacio: true,  chaqueta: false, liquidos: false, puertasMax: 1, enfriamientoMax: 0 },
            { valor: "mesa_b_lab", vacio: true,  chaqueta: false, liquidos: true,  puertasMax: 1, enfriamientoMax: 0 },
            { valor: "piso",       vacio: true,  chaqueta: true,  liquidos: false, puertasMax: 2, enfriamientoMax: 4 },
            { valor: "piso_lab",   vacio: true,  chaqueta: true,  liquidos: true,  puertasMax: 2, enfriamientoMax: 4 }
        ]
        function validarCodigo(serie, codigo) { return codigo.toUpperCase() === "ABCDEFGHIJKL" }
        function instalar(perfil) {
            console.log("PRUEBA instalar():", JSON.stringify(perfil))
            return { ok: true }
        }
    }

    Item {
        id: lienzo
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoDiseno)
        anchors.centerIn: parent
        clip: true

        Instalacion {
            anchors.fill: parent
            puente: puenteEjemplo
            teclado: panelTeclado
            onInstalacionCompletada: console.log("PRUEBA: instalacionCompletada")
        }
        PanelTeclado {
            id: panelTeclado
        }
    }
}

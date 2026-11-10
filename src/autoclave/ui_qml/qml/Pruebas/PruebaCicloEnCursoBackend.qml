import QtQuick
import Tema
import "../Pantallas"

// PRUEBA (Fase 3 de planeacion_pantalla_ciclo_en_curso.md): PantallaCicloEnCurso
// conectada al backend real (UiBridge + ProgresoCiclo + InfoEquipo), fuera de la
// navegación de producción (la entrada automática al iniciar un ciclo es la
// Fase 4). Solo lectura: no envía comandos. La abre ui_qml/prueba_ciclo_en_curso.py --backend.
Window {
    id: ventana
    width: 600; height: 960
    visible: true
    color: Colores.fondoMarinoOscuro

    property QtObject puente: null
    property QtObject progreso: null
    property QtObject infoEquipo: null

    // Orientación del lienzo (tanda horizontal): la del tamaño de esta ventana

    Binding { target: Escala; property: "horizontal"; value: Escala.esHorizontal(ventana.width, ventana.height) }
    // escala de Windows de la pantalla (zonas táctiles, tanda responsive)
    readonly property real dprPantalla: Screen.devicePixelRatio
    Binding { target: Escala; property: "dpr"; value: ventana.dprPantalla }
    Binding { target: Escala; property: "anchoLienzo"; value: Escala.anchoLienzoPara(ventana.width, ventana.height) }

    Binding {
        target: Escala
        property: "factor"
        value: Escala.factorPara(ventana.width, ventana.height)
    }
    Binding {
        target: Escala
        property: "altoLienzo"
        value: Escala.altoLienzoPara(ventana.width, ventana.height)
    }

    Item {
        width: Escala.px(Escala.anchoLienzo)
        height: Escala.px(Escala.altoLienzo)
        anchors.centerIn: parent
        clip: true

        PantallaCicloEnCurso {
            anchors.fill: parent
            puente: ventana.puente
            progreso: ventana.progreso
            infoEquipo: ventana.infoEquipo
        }
    }
}

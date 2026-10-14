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

        PantallaCicloEnCurso {
            anchors.fill: parent
            puente: ventana.puente
            progreso: ventana.progreso
            infoEquipo: ventana.infoEquipo
        }
    }
}

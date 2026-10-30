pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "Pantallas"
import "Componentes"

// Ventana del asistente de instalación (tanda 2026-10-14 T9, ARR-02 / MIG-07).
// La abre ui_qml/app.py en lugar de Main.qml cuando falta el perfil de
// instalación o es inválido, solo en la ventana principal (puerta 1). El
// puente es el real (bridge/puente_instalacion.py): escribe
// installation_profile.json. Al terminar, el asistente cierra la aplicación
// con el código 3 (CODIGO_INSTALACION_TERMINADA): el lanzador no la relanza
// (TMG-02 de T9). REI-01 (tanda 18): el resultado dice «Instalación
// completada. El equipo se reiniciará en 10 s» con cuenta regresiva y
// «Reiniciar ahora»; exe_unico.py reinicia entonces el PC (si Windows no lo
// hace, sigue con el arranque normal). ARR-06 (tanda 18): con
// `progresoArranque` (ProgresoArranqueSinPerfil), la intro de arranque se ve
// primero, encima del asistente, con el motivo. Mismo escalado que Main.qml.
Window {
    id: ventana
    width: 600; height: 960
    visible: true
    color: Colores.fondoMarinoOscuro

    property QtObject puenteInstalacion: null
    // ARR-06: fuente de la intro sin perfil; null = sin intro (pruebas)
    property QtObject progresoArranque: null
    property string versionSoftware: ""
    property bool introTerminada: false

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
            // la cuenta regresiva empieza solo con el asistente a la vista
            activo: ventana.progresoArranque === null || ventana.introTerminada
            onInstalacionCompletada: Qt.exit(3)
        }
        PanelTeclado {
            id: panelTeclado
        }

        // ARR-06: intro de arranque encima del asistente; al terminar se descarga
        Loader {
            objectName: "introArranqueInstalacion"
            anchors.fill: parent
            active: ventana.progresoArranque !== null && !ventana.introTerminada
            sourceComponent: IntroArranque {
                progreso: ventana.progresoArranque
                versionSoftware: ventana.versionSoftware
                onFinalizada: ventana.introTerminada = true
            }
        }
    }
}

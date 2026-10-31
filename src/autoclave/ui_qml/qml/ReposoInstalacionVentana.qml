pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n
import "Pantallas"

// W10 (tanda 10, D10-4.1): ventana de la pantalla 2 mientras la pantalla 1
// está en el asistente de instalación (sin perfil). La abre ui_qml/app.py en
// lugar de Main.qml para la puerta 2. Es el Reposo (logo y reloj) con el aviso
// «Instalación en curso en la pantalla 1»; no responde al toque ni usa el
// backend. Al terminar la instalación, el lanzador la cierra (D10-4.2).
// ARR-06 (tanda 18): con `progresoArranque`, la intro de arranque se ve
// primero, encima del Reposo. REI-01 (tanda 18): con `instalacionTerminada`
// (app.py lo fija al ver un perfil válido) el aviso pasa a «Instalación
// completada. El equipo se reiniciará en N s», con su propia cuenta regresiva
// (solo informa: quien reinicia es el lanzador). Mismo escalado que Main.qml.
Window {
    id: ventana
    width: 600; height: 960
    visible: true
    color: Colores.fondoMarinoOscuro

    property QtObject progresoArranque: null
    property string versionSoftware: ""
    property bool introTerminada: false
    property bool instalacionTerminada: false
    readonly property int segundosReinicio: 10
    property int segundosRestantes: segundosReinicio

    onInstalacionTerminadaChanged: if (instalacionTerminada) cuenta.start()
    Timer {
        id: cuenta
        interval: 1000
        repeat: true
        onTriggered: {
            ventana.segundosRestantes = Math.max(0, ventana.segundosRestantes - 1)
            if (ventana.segundosRestantes === 0)
                stop()
        }
    }

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
            aviso: ventana.instalacionTerminada
                   ? I18n.t("instalacion.reinicio_cuenta", I18n.lang, { segundos: ventana.segundosRestantes })
                   : I18n.t("instalacion.aviso_pantalla2", I18n.lang)
        }

        // ARR-06: intro de arranque encima del Reposo; al terminar se descarga
        Loader {
            objectName: "introArranqueReposo"
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

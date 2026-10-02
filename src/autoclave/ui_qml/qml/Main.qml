pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Tema
import "Pantallas"
import "Componentes"

Window {
    id: ventana
    width: 600; height: 960   // 5:8, igual que el lienzo de Escala
    visibility: Window.Windowed   // app.py la pasa a pantalla completa en el monitor elegido
    visible: true
    color: Colores.fondoMarinoOscuro

    // Los inyecta app.py (setInitialProperties). puente: UiBridge de solo lectura;
    // comandosPuerta: abrir/cerrar la puerta de esta ventana; ajustes: lanzador
    // del menú de configuración PySide; textosJson: assets/textos/es.json.
    // comandoCiclo: iniciar ciclo; infoEquipo: modelo/serie y panel de equipo.
    property QtObject puente: null
    property QtObject comandosPuerta: null
    property QtObject comandoCiclo: null
    property QtObject infoEquipo: null
    property QtObject ajustes: null
    // standby: activo = mostrar la pantalla de arranque (simultáneo en ambas pantallas)
    property QtObject standby: null
    property var textosJson: ({})

    // Arranque <-> principal lo decide el standby (única transición simultánea):
    // activo -> se vuelve al arranque desde cualquier pantalla; inactivo -> principal.
    // El resto de la navegación (login, paneles) es local de cada pantalla.
    function aplicarStandby() {
        if (!standby)
            return
        panelTeclado.cerrar()
        if (standby.activo) {
            if (pila.depth > 1)
                pila.pop(null)
        } else if (pila.depth === 1) {
            pila.push(cicloComp)
        }
    }
    Connections {
        target: ventana.standby
        function onActivoChanged() { ventana.aplicarStandby() }
    }

    Binding {
        target: Escala
        property: "factor"
        value: Math.min(ventana.width / Escala.anchoDiseno,
                        ventana.height / Escala.altoDiseno)
    }

    Item {
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoDiseno)
        anchors.centerIn: parent
        clip: true

        // Navegación arranque <-> ciclo por standby; desde ciclo, el avatar abre
        // el login QML (aún sin autenticación) y su casa regresa a ciclo.
        StackView {
            id: pila
            anchors.fill: parent
            initialItem: esperaComp
            // un teclado abierto no sobrevive a un cambio de pantalla
            onCurrentItemChanged: panelTeclado.cerrar()
        }

        // Teclado en pantalla de esta ventana (Paso 5 de planeacion_teclados_qml.md):
        // sobre el StackView, inyectado a las pantallas como `teclado`.
        PanelTeclado {
            id: panelTeclado
            objectName: "panelTeclado"
            textosJson: ventana.textosJson
        }
    }

    Component {
        id: esperaComp
        Arranque {
            textosJson: ventana.textosJson
            // con standby, el toque ya lo registró el filtro de eventos y el
            // cambio llega por aplicarStandby(); sin él (pruebas), navegación local
            onTocado: if (!ventana.standby) pila.push(cicloComp)
        }
    }
    Component {
        id: cicloComp
        Ciclo {
            puente: ventana.puente
            comandosPuerta: ventana.comandosPuerta
            comandoCiclo: ventana.comandoCiclo
            infoEquipo: ventana.infoEquipo
            textosJson: ventana.textosJson
            onPuertaPulsada: ventana.comandosPuerta?.alternar()
            onIniciarCicloPulsado: ventana.comandoCiclo?.iniciar()
            onAjustesPulsado: ventana.ajustes?.abrir()
            onAvatarPulsado: pila.push(loginComp)
        }
    }
    Component {
        id: loginComp
        Login {
            teclado: panelTeclado
            textosJson: ventana.textosJson
            onInicioPulsado: pila.pop()
        }
    }
}

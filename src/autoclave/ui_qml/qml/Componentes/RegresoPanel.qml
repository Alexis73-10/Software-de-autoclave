import QtQuick

// FC-05 (tanda 21, planeacion_fin_de_ciclo.md): regreso automático al panel de
// fin de ciclo. Mientras `activo` (la gráfica está a la vista en un ciclo que
// no terminó exitoso), cuenta REGRESO_PANEL_S segundos; al llegar a 0 emite
// vencido() una sola vez y se detiene. Cualquier toque en la pantalla
// (incluido el cursor de la gráfica) debe llamar reiniciarCuenta(). Con un
// modal abierto (`pausado`) la cuenta se detiene; al cerrarse el modal vuelve
// a empezar desde REGRESO_PANEL_S (cerrarlo es un toque).
//
// Tiempo inyectable para pruebas: `intervaloTickMs` es la duración de un
// «segundo» de la cuenta (1000 en el equipo).
//
// Uso (ola 2):
//   RegresoPanel {
//       id: regreso
//       activo: vistaGrafica && cicloNoExitoso
//       pausado: modalAbierto
//       onVencido: { pantallaCompleta = false; panel.volverAlPanel(); vistaGrafica = false }
//   }
//   PildoraFinCiclo { cantidad: panel.cantidad; segundos: regreso.restante }
Item {
    id: raiz
    visible: false

    // REGRESO_PANEL_S: único lugar donde se fija la duración del regreso (FC-05)
    readonly property int regresoPanelS: 30

    property bool activo: false
    property bool pausado: false
    property int intervaloTickMs: 1000

    // segundos que faltan (para la píldora roja «Alarmas (N) · SS s»)
    readonly property int restante: _restante
    readonly property bool corriendo: tick.running

    signal vencido()

    property int _restante: regresoPanelS

    function reiniciarCuenta() {
        _restante = regresoPanelS
        if (tick.running)
            tick.restart()
    }

    onActivoChanged: reiniciarCuenta()
    onPausadoChanged: if (!pausado) reiniciarCuenta()

    Timer {
        id: tick
        interval: raiz.intervaloTickMs
        repeat: true
        running: raiz.activo && !raiz.pausado && raiz._restante > 0
        onTriggered: {
            raiz._restante = Math.max(0, raiz._restante - 1)
            if (raiz._restante === 0)
                raiz.vencido()
        }
    }
}

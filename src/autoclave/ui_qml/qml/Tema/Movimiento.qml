pragma Singleton
import QtQuick

// Movimiento de la interfaz (cambios de interfaz del 31-oct, ejecutados sin
// supervisión; decisiones en docs/informes/movimiento_ui/decisiones.md).
//  - Crossfade entre secciones de OPCIONES (Componentes/CargadorSeccion.qml).
//  - Elemento compartido tarjeta -> ventana/vista (Componentes/ElementoCompartido.qml).
// Las duraciones viven aquí para ajustarlas en un solo sitio.
QtObject {
    readonly property int crossfadeMs: 220
    readonly property int compartidoMs: 320
    readonly property int fondoMs: 200

    // Sin animación: las pruebas con la plataforma "offscreen" ven los cambios
    // al instante (una prueba puede ponerlo en false para ver el movimiento).
    property bool instantaneo: Qt.platform.pluginName === "offscreen"

    // Última tarjeta tocada: la ventana o vista que se abre a continuación la
    // toma como origen de la transición (tomarOrigen). Caduca al segundo para
    // que una apertura sin tarjeta (p. ej. por una alarma) no use una vieja.
    property Item origen: null
    property double _marca: 0
    function registrarOrigen(item) { origen = item; _marca = Date.now() }
    function tomarOrigen() {
        const o = (Date.now() - _marca) < 1000 ? origen : null
        origen = null
        return o
    }
}

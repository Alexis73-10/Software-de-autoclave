pragma Singleton
import QtQuick

// Tanda 17 (R4, V17-s4-02): registro global de las capas emergentes que se
// muestran sobre toda la ventana (Desplegable, Calendario y
// VentanaDetalleAlarma; z 1000 sobre Window.contentItem). Cuando la seguridad
// pasa a urgente (paro o estado seguro por confirmar), Main.qml
// irAPanelSeguridad() llama a cerrarTodas() para que ninguna tape las acciones
// de seguridad, igual que cierra el teclado (SAF-02).
QtObject {
    signal cierreSolicitado()
    function cerrarTodas() { cierreSolicitado() }
}

pragma Singleton
import QtQuick

// Medidas y estados CONFIRMADOS de los teclados en pantalla
// (docs/mis_plans/planeacion_teclados_qml.md v2.1). En px de diseño del lienzo
// de 1200: pasar por Escala.px() al usarlas. Lo provisional va aparte, en
// TecladoProvisional.qml.
QtObject {
    // TEC-D11: tecla 96 x 88, radio 12, separación 14 (el diseñador dibujó 12 y 10)
    readonly property real anchoTecla: 96
    readonly property real altoTecla: 88
    readonly property real radioTecla: 12
    readonly property real separacion: 14
    readonly property real bordeTecla: 2          // borde_control de medidas.csv

    // TEC-D04: presionado visible al menos 90 ms; sin hover ni deshabilitado
    readonly property int presionadoMinimoMs: 90
}

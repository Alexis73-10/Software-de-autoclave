// ui_qml/components/ContenedorEscalado.qml
//
// Contenedor de escalado uniforme (§8.2 del plan de interfaz dual-
// pantalla, D-11): lienzo lógico fijo (Tokens.layout.canvas, hoy
// 768x1024), con escalado uniforme y letterbox cuando la ventana no
// respeta esa relación de aspecto.
//   scale = min(anchoVentana / lienzoAncho, altoVentana / lienzoAlto)
// Regla: ninguna vista contiene ramas condicionales por tamaño — el
// contenido de este contenedor siempre se dibuja al tamaño lógico fijo;
// este es el único componente que conoce la geometría real de la
// ventana/pantalla. lienzoAncho/lienzoAlto toman su valor por defecto de
// Tokens.layout.canvas pero no son readonly: las pruebas fijan un tamaño
// explícito para probar la matemática de escalado sin depender de cuál
// sea el tamaño de producción vigente (ver test_contenedor_escalado_qml.py).

import QtQuick
import Autoclave.Design 1.0

Item {
    id: root

    property int lienzoAncho: Tokens.layout.canvas.w
    property int lienzoAlto: Tokens.layout.canvas.h
    readonly property real factorEscala: Math.min(width / lienzoAncho, height / lienzoAlto)

    default property alias contenido: contenedor.data

    Item {
        id: contenedor
        objectName: "contenidoEscalado"
        width: root.lienzoAncho
        height: root.lienzoAlto
        scale: root.factorEscala
        anchors.centerIn: parent
    }
}

import QtQuick
import Tema

// Área de las pantallas que se diseñaron para el lienzo exacto (1200x1920 en
// vertical, 1920x1200 en horizontal). Hasta la tanda horizontal las centraba
// en un área de ese tamaño y dejaba franjas si sobraba lienzo. Tanda
// responsive (decisión de Cristian, 10-nov): sin franjas; el área LLENA el
// lienzo, que mide lo mismo que la ventana, y cada pantalla reparte lo que
// sobra con sus anclajes. A los tamaños de diseño exactos el área mide lo
// mismo que antes (el lienzo es el de diseño).
Item {
    default property alias contenido: area.data

    Item {
        id: area
        anchors.fill: parent
        clip: true
    }
}

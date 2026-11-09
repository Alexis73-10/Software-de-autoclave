import QtQuick
import Tema

// Área de alto fijo (Escala.altoDiseno) centrada verticalmente en el lienzo.
// Envuelve a las pantallas diseñadas para 1200x1920 exactos, para que el lienzo
// de alto flexible (Escala.altoLienzo, pantallas 9:16) no las deforme: se ven
// igual que antes, con franjas arriba y abajo si sobra alto. En horizontal
// (Escala.horizontal) el área es anchoDiseno x altoDiseno = 1920x1200; en
// vertical, el ancho del lienzo, como siempre.
Item {
    default property alias contenido: area.data

    Item {
        id: area
        width: Escala.horizontal ? Math.min(parent.width, Escala.px(Escala.anchoDiseno)) : parent.width
        height: Escala.px(Escala.altoDiseno)
        anchors.centerIn: parent
        clip: true
    }
}

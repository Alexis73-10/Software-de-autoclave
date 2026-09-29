import QtQuick
import Tema

// Fondo compartido por todas las pantallas excepto Arranque (que tiene su
// propio fondo de pantalla completa). Reutiliza el mismo asset del arranque
// por instrucción explícita — si el diseñador entrega un fondo distinto
// para el resto de la app, solo cambia este source.
Image {
    anchors.fill: parent
    source: "../../assets/fondos/fondo-arranque.png"
    fillMode: Image.PreserveAspectCrop
}

import QtQuick
import Tema

// Fondo compartido por todas las pantallas excepto Reposo (que tiene su
// propio fondo de pantalla completa). Reutiliza el mismo asset del arranque
// por instrucción explícita — si el diseñador entrega un fondo distinto
// para el resto de la app, solo cambia este source.
// Modo oscuro (decisión 4): en lugar de la imagen, el gradiente radial de la
// paleta §1, centrado en (70 %, 0 %), 120 % × 60 %.
Item {
    anchors.fill: parent

    Image {
        anchors.fill: parent
        visible: !Colores.fondoGradiente
        source: "../../assets/fondos/fondo-arranque.png"
        fillMode: Image.PreserveAspectCrop
    }
    FondoGradiente {
        anchors.fill: parent
        visible: Colores.fondoGradiente
        centroX: 0.70; centroY: 0.0
        radioX: 1.20; radioY: 0.60
        color0: Colores.fondoBarraSuperior     // #1A3150 en oscuro
        color1: Colores.fondoAzulMedio         // #0F1B2A al 45 %
        posicion1: 0.45
        color2: Colores.fondoMarinoOscuro      // #090E14
    }
}

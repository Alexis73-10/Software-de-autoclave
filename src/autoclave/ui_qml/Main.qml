// ui_qml/Main.qml
//
// Raíz de la ventana: envuelve el contenido en ContenedorEscalado (lienzo
// lógico fijo tomado de Tokens.layout.canvas, D-11/§8.2) y aloja la
// pantalla activa. Por ahora solo existe PantallaInicio — el enrutamiento
// entre pantallas se agrega cuando exista una segunda pantalla a la que
// navegar. PantallaInicio usa anchors.fill: parent — no declara su propio
// tamaño, lo recibe del contenedor (así app.py puede leer el tamaño de
// lienzo real desde `contenedor` sin que exista una tercera copia del
// número en la pantalla).

import QtQuick
import QtQuick.Window
import "components"
import "screens"

Window {
    id: ventana
    visible: true
    color: "black"
    title: "Autoclave"

    ContenedorEscalado {
        id: contenedor
        objectName: "contenedor"
        anchors.fill: parent

        PantallaInicio {
            anchors.fill: parent
            onAvanzar: console.log("PantallaInicio.avanzar() — siguiente pantalla aún no definida")
        }
    }
}

import QtQuick
import Tema

// Pantalla 06 · Arranque. Sin dependencias de backend: solo reloj y logo.
// Avanza al tocar cualquier punto — es la señal más simple posible; se
// reemplaza por un disparo real (ej. "backend listo") cuando se defina.
Item {
    id: raiz
    signal tocado()

    // Fondo exportado por el diseñador a 1200x1920 (reemplaza la aproximación
    // lineal de --gradient-splash). Si el archivo falta, queda vacío y se ve
    // el color de la ventana.
    Image {
        anchors.fill: parent
        source: "../../assets/fondos/fondo-arranque.png"
        fillMode: Image.PreserveAspectCrop
    }

    property var _meses: ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    property date _ahora: new Date()
    Timer { interval: 1000; running: true; repeat: true; onTriggered: raiz._ahora = new Date() }
    function _dosDigitos(n) { return n < 10 ? "0" + n : "" + n }

    Column {
        anchors.centerIn: parent
        spacing: Escala.px(24)

        // Ancho medido en 05_PNG_REFERENCIA/pantalla_01_arranque (~345px de diseño)
        Image {
            anchors.horizontalCenter: parent.horizontalCenter
            source: "../../assets/logo/logo-especifika-blanco.svg"
            width: Escala.px(345)
            height: width * 446 / 1666   // proporción del viewBox del SVG
            sourceSize.width: width
            sourceSize.height: height
            fillMode: Image.PreserveAspectFit
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: raiz._dosDigitos(raiz._ahora.getHours()) + ":" +
                  raiz._dosDigitos(raiz._ahora.getMinutes())
            color: "transparent"
            style: Text.Outline
            styleColor: "white"
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(Tipografia.relojDisplayTam)
            font.weight: Tipografia.pesoLight
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: raiz._ahora.getDate() + " " +
                  raiz._meses[raiz._ahora.getMonth()] + "  -  " +
                  raiz._ahora.getFullYear()
            color: "#C7DCFD"
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(Tipografia.relojFechaTam)
            font.weight: Tipografia.pesoMedium
        }
    }

    MouseArea { anchors.fill: parent; onClicked: raiz.tocado() }
}

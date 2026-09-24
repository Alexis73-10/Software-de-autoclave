import QtQuick
import Tema

// Barra superior común a casi todas las pantallas (06_MEDIDAS: 1080x176 en el diseño).
Rectangle {
    id: raiz
    width: Escala.px(Escala.anchoDiseno)
    height: Escala.px(176)
    color: Colores.fondoBarraSuperior

    // Reloj en vivo: formato manual (no Qt.locale) para no depender de que el
    // sistema tenga datos de localización en español instalados.
    property var _meses: ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    property date _ahora: new Date()
    Timer { interval: 1000; running: true; repeat: true; onTriggered: raiz._ahora = new Date() }

    function _dosDigitos(n) { return n < 10 ? "0" + n : "" + n }

    // Ancho medido en 05_PNG_REFERENCIA/pantalla_03_login (~245px de diseño)
    Image {
        anchors.left: parent.left
        anchors.leftMargin: Escala.px(24)
        anchors.verticalCenter: parent.verticalCenter
        source: "../../assets/logo/logo-especifika-blanco.svg"
        width: Escala.px(245)
        height: width * 446 / 1666   // proporción del viewBox del SVG
        sourceSize.width: width
        sourceSize.height: height
        fillMode: Image.PreserveAspectFit
    }

    Column {
        anchors.right: parent.right
        anchors.rightMargin: Escala.px(24)
        anchors.verticalCenter: parent.verticalCenter
        spacing: Escala.px(2)
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: raiz._dosDigitos(raiz._ahora.getHours()) + ":" +
                  raiz._dosDigitos(raiz._ahora.getMinutes())
            color: "white"
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(Tipografia.relojBarraTam)
            font.weight: Tipografia.pesoSemiBold
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
}

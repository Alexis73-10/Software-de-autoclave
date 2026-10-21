import QtQuick
import Tema
import Autoclave.I18n

// Barra superior común a casi todas las pantallas (06_MEDIDAS: 1080x176 en el diseño).
Rectangle {
    id: raiz
    width: Escala.px(Escala.anchoDiseno)
    height: Escala.px(176)
    color: "transparent"   // logo y reloj flotan sobre FondoApp

    // Campana y engranaje a la derecha, con el reloj centrado (P-07 de
    // planeacion_nuevo_usuario.md). Por defecto apagado: las pantallas que ya
    // la usan no cambian. Las señales solo avisan; quien no las conecta deja
    // los iconos inertes. Medidas del reloj grande y de los iconos: las de Ciclo.qml.
    property bool mostrarIconos: false
    property int conteoNotificaciones: 0
    signal campanaPulsada()
    signal engranajePulsado()

    // Reloj en vivo: formato manual (no Qt.locale) para no depender de que el
    // sistema tenga datos de localización en español instalados.
    // I2 (tanda 5): meses del catálogo, en el idioma vigente
    readonly property var _meses: I18n.valor("fecha.meses", I18n.lang)
                                  || ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
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
        anchors.right: raiz.mostrarIconos ? undefined : parent.right
        anchors.rightMargin: Escala.px(24)
        anchors.horizontalCenter: raiz.mostrarIconos ? parent.horizontalCenter : undefined
        anchors.verticalCenter: parent.verticalCenter
        spacing: Escala.px(2)
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: raiz._dosDigitos(raiz._ahora.getHours()) + ":" +
                  raiz._dosDigitos(raiz._ahora.getMinutes())
            color: "white"
            font.family: Tipografia.familiaReloj
            font.pixelSize: Escala.fuente(raiz.mostrarIconos ? 97 : Tipografia.relojBarraTam)
            font.weight: Tipografia.pesoSemiBold
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: raiz._ahora.getDate() + " " +
                  raiz._meses[raiz._ahora.getMonth()] + "  -  " +
                  raiz._ahora.getFullYear()
            color: "#C7DCFD"
            font.family: Tipografia.familiaReloj
            font.pixelSize: Escala.fuente(raiz.mostrarIconos ? 26 : Tipografia.relojFechaTam)
            font.weight: Tipografia.pesoMedium
        }
    }

    // ---- campana y engranaje (solo con mostrarIconos) ----
    Item {
        id: campana
        visible: raiz.mostrarIconos
        x: Escala.px(888); y: Escala.px(64)
        width: Escala.px(51); height: Escala.px(57)
        Image {
            anchors.fill: parent
            source: "../../assets/iconos/color/campana.svg"   // variante blanca
            sourceSize.width: width
            sourceSize.height: height
        }
        Rectangle {
            visible: raiz.conteoNotificaciones > 0
            x: Escala.px(34); y: -Escala.px(14)
            width: Escala.px(26); height: Escala.px(25); radius: width / 2
            color: Colores.alarmaBaja
            Text {
                anchors.centerIn: parent
                text: raiz.conteoNotificaciones
                color: "white"
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(17)
            }
        }
        MouseArea {
            anchors.fill: parent
            anchors.margins: -Escala.px(20)   // área táctil más grande que el icono
            onClicked: raiz.campanaPulsada()
        }
    }
    Item {
        visible: raiz.mostrarIconos
        x: Escala.px(1043); y: Escala.px(64)
        width: Escala.px(57); height: Escala.px(58)
        Image {
            anchors.fill: parent
            source: "../../assets/iconos/color/engranaje.svg"   // variante blanca
            sourceSize.width: width
            sourceSize.height: height
        }
        MouseArea {
            anchors.fill: parent
            anchors.margins: -Escala.px(20)
            onClicked: raiz.engranajePulsado()
        }
    }
}

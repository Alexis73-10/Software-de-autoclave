import QtQuick
import Tema
import Autoclave.I18n
import "../Componentes"

// Pantalla 06 · Reposo (antes Arranque.qml, ARR-01). Sin dependencias de backend: solo reloj y logo.
// Avanza al tocar cualquier punto — es la señal más simple posible; se
// reemplaza por un disparo real (ej. "backend listo") cuando se defina.
//
// W10 (D10-4.1): con `aviso` muestra ese texto bajo la fecha y con
// `tactil: false` ignora el toque; así lo usa ReposoInstalacionVentana.qml en
// la pantalla 2 mientras la 1 está en el asistente de instalación. Sin tocar
// esas propiedades se ve y responde igual que antes.
Item {
    id: raiz
    signal tocado()

    property string aviso: ""
    property bool tactil: true

    // Fondo exportado por el diseñador a 1200x1920 (reemplaza la aproximación
    // lineal de --gradient-splash). Si el archivo falta, queda vacío y se ve
    // el color de la ventana.
    // Modo oscuro (decisión 4): gradiente radial de la paleta §1 en lugar de la imagen
    Image {
        anchors.fill: parent
        visible: !Colores.fondoGradiente
        source: "../../assets/fondos/fondo-arranque.png"
        fillMode: Image.PreserveAspectCrop
    }
    FondoGradiente {
        anchors.fill: parent
        visible: Colores.fondoGradiente
        centroX: 0.50; centroY: 0.42
        radioX: 0.70; radioY: 0.45
        color0: Colores.fondoCieloNucleo       // #1B3352 en oscuro
        color1: Colores.fondoAzulMedio         // #0F1B2A al 55 %
        posicion1: 0.55
        color2: Colores.fondoReposoBorde       // #070B10
    }

    readonly property var _meses: I18n.valor("fecha.meses", I18n.lang) || []
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
            styleColor: Colores.textoSobreAccion
            font.family: Tipografia.familiaReloj
            font.pixelSize: Escala.fuente(Tipografia.relojDisplayTam)
            font.weight: Tipografia.pesoLight
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: raiz._ahora.getDate() + " " +
                  (raiz._meses[raiz._ahora.getMonth()] ?? "") + "  -  " +
                  raiz._ahora.getFullYear()
            color: Colores.textoFechaReposo
            font.family: Tipografia.familiaReloj
            font.pixelSize: Escala.fuente(Tipografia.relojFechaTam)
            font.weight: Tipografia.pesoMedium
        }

        Text {
            objectName: "avisoInstalacion"
            anchors.horizontalCenter: parent.horizontalCenter
            visible: raiz.aviso !== ""
            width: raiz.width - Escala.px(120)
            topPadding: Escala.px(40)
            text: raiz.aviso
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            color: Colores.textoSobreAccion
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
            font.weight: Tipografia.pesoMedium
        }
    }

    MouseArea { anchors.fill: parent; enabled: raiz.tactil; onClicked: raiz.tocado() }
}

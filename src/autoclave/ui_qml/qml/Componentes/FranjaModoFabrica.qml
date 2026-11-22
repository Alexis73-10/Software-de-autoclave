import QtQuick
import Tema
import Autoclave.I18n

// Modo fábrica (D-13, Etapa 1): franja fija «MODO FÁBRICA», sin más texto, en
// todas las pantallas de las dos ventanas mientras /status.modo_fabrica sea
// true (UiBridge.modoFabrica; la interfaz nunca lo deduce). Delgada, en el
// borde inferior del lienzo (el superior tiene el reloj de Preciclo y Ciclo en
// curso) y por encima de todo (también de las capas emergentes, z 1000). No
// recibe toques (`enabled: false`, sin MouseArea): los controles de debajo
// siguen respondiendo.
Rectangle {
    id: raiz
    objectName: "franjaModoFabrica"
    property bool activa: false

    visible: activa
    enabled: false
    height: Escala.px(30)
    color: Colores.franjaFabricaFondo

    Text {
        objectName: "textoModoFabrica"
        anchors.centerIn: parent
        width: parent.width - Escala.px(24)
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: I18n.t("fabrica.franja", I18n.lang)
        color: Colores.franjaFabricaTexto
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: Escala.fuente(20)
        font.letterSpacing: Escala.px(4)
        fontSizeMode: Text.HorizontalFit
        minimumPixelSize: Escala.fuente(12)
    }
}

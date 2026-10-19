import QtQuick
import Tema

// PROVISIONAL (PC-06, sin diseño de fila): barra de color por prioridad
// IEC 60601-1-8 (Colores.alarma*) + descripción (o el id si no hay descripción).
Item {
    id: raiz
    property string idAlarma: ""
    property string descripcion: ""
    property string prioridad: "alta"   // alta | media | baja (UiBridge.prioridad_de)
    // texto en varias líneas en vez de cortarlo (avisos de seguridad, U1)
    property bool multilinea: false

    height: multilinea ? Math.max(Escala.px(72), texto.implicitHeight + Escala.px(28)) : Escala.px(72)

    Rectangle {
        x: 0; y: Escala.px(12)
        width: Escala.px(12); height: raiz.height - Escala.px(24)
        radius: Escala.px(3)
        color: raiz.prioridad === "media" ? Colores.alarmaMedia
             : raiz.prioridad === "baja"  ? Colores.alarmaBaja
             : Colores.alarmaAlta
    }
    Text {
        id: texto
        x: Escala.px(32)
        width: raiz.width - x
        anchors.verticalCenter: parent.verticalCenter
        text: raiz.descripcion !== "" ? raiz.descripcion : raiz.idAlarma
        elide: raiz.multilinea ? Text.ElideNone : Text.ElideRight
        wrapMode: raiz.multilinea ? Text.WordWrap : Text.NoWrap
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(24)
    }
    Rectangle {
        anchors.bottom: parent.bottom
        width: raiz.width; height: Escala.px(1)
        color: "#D7D7D7"
    }
}

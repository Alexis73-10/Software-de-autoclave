import QtQuick
import Tema

// PROVISIONAL (PC-06, sin diseño de fila): barra de color por prioridad
// IEC 60601-1-8 (Colores.alarma*) + descripción (o el id si no hay descripción).
Item {
    id: raiz
    property string idAlarma: ""
    property string descripcion: ""
    property string prioridad: "alta"   // alta | media | baja (UiBridge.prioridad_de)

    height: Escala.px(72)

    Rectangle {
        x: 0; y: Escala.px(12)
        width: Escala.px(12); height: raiz.height - Escala.px(24)
        radius: Escala.px(3)
        color: raiz.prioridad === "media" ? Colores.alarmaMedia
             : raiz.prioridad === "baja"  ? Colores.alarmaBaja
             : Colores.alarmaAlta
    }
    Text {
        x: Escala.px(32)
        width: raiz.width - x
        anchors.verticalCenter: parent.verticalCenter
        text: raiz.descripcion !== "" ? raiz.descripcion : raiz.idAlarma
        elide: Text.ElideRight
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

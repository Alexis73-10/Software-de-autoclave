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
    // P-5 (tanda 6): alarma de despeje manual (COM-02/COM-03) con su botón
    property bool despejable: false
    property string textoDespejar: ""
    signal despejarPulsado()

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
        width: raiz.width - x - (raiz.despejable ? botonDespejar.width + Escala.px(16) : 0)
        anchors.verticalCenter: parent.verticalCenter
        text: raiz.descripcion !== "" ? raiz.descripcion : raiz.idAlarma
        elide: raiz.multilinea ? Text.ElideNone : Text.ElideRight
        wrapMode: raiz.multilinea ? Text.WordWrap : Text.NoWrap
        color: Colores.textoPrimario
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(24)
    }
    Rectangle {
        id: botonDespejar
        objectName: "botonDespejar"
        visible: raiz.despejable
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: Math.max(Escala.px(160), textoBoton.implicitWidth + Escala.px(32))
        height: Escala.px(56); radius: Escala.px(10)
        color: Colores.accionPrimario
        Text {
            id: textoBoton
            anchors.centerIn: parent
            text: raiz.textoDespejar
            color: "white"
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(22)
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.despejarPulsado() }
    }
    Rectangle {
        anchors.bottom: parent.bottom
        width: raiz.width; height: Escala.px(1)
        color: "#D7D7D7"
    }
}

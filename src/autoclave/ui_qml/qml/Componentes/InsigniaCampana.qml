import QtQuick
import Tema

// Insignia de la campana (contador de notificaciones). U1 (tanda 2): roja con
// el paro o la confirmación de estado seguro pendiente, y parpadeando mientras
// la confirmación espera, para que se vea sin abrir el panel; amarilla con el
// estado seguro en curso. La geometría la fija quien la usa.
Rectangle {
    id: raiz
    property int conteo: 0
    property bool urgente: false
    property bool enCurso: false
    property bool parpadeo: false
    property color colorNormal: "#08C9F9"
    property real tamFuente: 17

    visible: conteo > 0
    radius: width / 2
    color: urgente ? Colores.alarmaAlta : enCurso ? Colores.alarmaMedia : colorNormal

    Text {
        anchors.centerIn: parent
        text: raiz.conteo
        color: raiz.enCurso && !raiz.urgente ? Colores.textoPrimario : "white"
        font.family: Tipografia.familia
        font.pixelSize: Math.max(1, Math.round(raiz.tamFuente))
    }

    SequentialAnimation on opacity {
        running: raiz.parpadeo && raiz.visible
        loops: Animation.Infinite
        onRunningChanged: if (!running) raiz.opacity = 1
        NumberAnimation { to: 0.15; duration: 450 }
        NumberAnimation { to: 1; duration: 450 }
    }
}

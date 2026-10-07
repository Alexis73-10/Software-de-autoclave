import QtQuick
import Tema

// Encabezado del Menú Principal: logo, hora y fecha centradas y campana con
// contador (planeacion_menu_principal_ui_qml.md §5 y §6.1). Sin engranaje: el
// menú se abre desde el engranaje de las pantallas de preciclo y de ciclo en
// curso, y la configuración se alcanza por Iniciar sesión (decisión de Cristian,
// 2026-10-02).
// Misma geometría que el encabezado inline de PantallaPreciclo.qml (marco del diseñador,
// 1196 de ancho), copiada y no compartida: PantallaPreciclo.qml y PantallaCicloEnCurso.qml
// no se refactorizan en este trabajo (deuda técnica anotada, D-19).
// Ocupa la franja superior del marco (alto 177); `escala` como en TarjetaMenu.
Item {
    id: raiz

    property real escala: 1
    property var textosJson: ({})
    // Contador de la campana; < 0 = sin fuente -> sin contador (D-17)
    property int conteoAlarmas: -1
    // Engranaje inerte, por consistencia visual (lo usa Opciones.qml; el menú no)
    property bool conEngranaje: false

    // La campana abre el panel de notificaciones (lo resuelve la pantalla)
    signal campanaPulsada()

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    width: m(1196)
    height: m(177)

    readonly property string _iconos: "../../assets/iconos/color/"

    // Icono ubicado para que su tinta llene la caja del mockup (como Icono de PantallaPreciclo.qml)
    component Icono: Image {
        property var caja: [0, 0, 0, 0]
        property var tinta: [0, 0, 48, 48]
        readonly property real _escala: raiz.m(caja[3]) / (tinta[3] - tinta[1])
        width: 48 * _escala
        height: width
        x: raiz.m(caja[0] + caja[2] / 2) - (tinta[0] + tinta[2]) / 2 * _escala
        y: raiz.m(caja[1]) - tinta[1] * _escala
        sourceSize.width: width
        sourceSize.height: height
    }

    Image {
        x: raiz.m(73); y: raiz.m(57)
        width: raiz.m(267)
        height: width * 42427 / 158611   // proporción del viewBox del SVG
        source: "../../assets/logo/logo-especifika-blanco.svg"
        sourceSize.width: width
        sourceSize.height: height
    }

    // Reloj de pared: solo para mostrar (nunca temporiza el proceso). Meses de
    // es.json (fecha.meses), sin depender de la configuración regional del SO.
    Item {
        id: reloj
        anchors.fill: parent
        readonly property var _meses: (raiz.textosJson && raiz.textosJson.fecha
                                       && raiz.textosJson.fecha.meses) || []
        property date _ahora: new Date()
        Timer { interval: 1000; running: true; repeat: true; onTriggered: reloj._ahora = new Date() }
        function _dosDigitos(n) { return n < 10 ? "0" + n : "" + n }

        Text {
            objectName: "horaMenu"
            x: raiz.m(597.5) - width / 2
            y: raiz.m(108) - baselineOffset
            text: reloj._dosDigitos(reloj._ahora.getHours()) + ":" +
                  reloj._dosDigitos(reloj._ahora.getMinutes())
            color: "white"
            font.family: Tipografia.familiaReloj
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(97)
        }
        Text {
            objectName: "fechaMenu"
            x: raiz.m(598) - width / 2
            y: raiz.m(141) - baselineOffset
            text: reloj._ahora.getDate() + " " +
                  (reloj._meses[reloj._ahora.getMonth()] ?? "") + "  -  " +
                  reloj._ahora.getFullYear()
            color: "white"
            font.family: Tipografia.familiaReloj
            font.pixelSize: raiz.fuente(26)
        }
    }

    Icono {
        caja: [888, 64, 51, 57]; tinta: [5.85, 4.0, 42.15, 44.0]
        source: raiz._iconos + "campana.svg"   // variante blanca
    }
    Rectangle {
        objectName: "insigniaCampana"
        visible: raiz.conteoAlarmas > 0
        x: raiz.m(922); y: raiz.m(50)
        width: raiz.m(26); height: raiz.m(25); radius: width / 2
        color: "#08C9F9"   // insignia medida en el mockup de ciclo (PantallaPreciclo.qml, paleta.insignia)
        Text {
            anchors.centerIn: parent
            text: raiz.conteoAlarmas
            color: "white"
            font.family: Tipografia.familia
            font.pixelSize: raiz.fuente(17)
        }
    }
    // Engranaje solo decorativo (OPCIONES, U-6: ya se está en configuración):
    // sin zona táctil. Misma caja que el de PantallaPreciclo.qml.
    Icono {
        objectName: "engranajeEncabezado"
        visible: raiz.conEngranaje
        caja: [1043, 64, 57, 58]; tinta: [4.0, 4.0, 44.0, 44.0]
        source: raiz._iconos + "engranaje.svg"   // variante blanca
    }

    MouseArea {
        objectName: "zonaCampana"
        x: raiz.m(870); y: raiz.m(40); width: raiz.m(90); height: raiz.m(95)   // como PantallaPreciclo.qml
        onClicked: raiz.campanaPulsada()
    }
}

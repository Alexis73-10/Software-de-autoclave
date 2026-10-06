import QtQuick
import Tema

// Barra inferior del Menú Principal (planeacion_menu_principal_ui_qml.md §5, D-06):
// Salir a la izquierda, Home a la derecha, celda central vacía entre los dos
// separadores y la versión abajo a la derecha. Medidas del v3 relativas a la
// propia barra (1128 x 139; separadores en x 313 y 800; tinta de Salir 75 x 90 en
// (116, 24); casa en la misma caja que la barra de PantallaPreciclo.qml). Estilo
// de fondo, borde, separadores y versión copiado de la barra inline de
// PantallaPreciclo.qml, que no se refactoriza (D-19). `escala` como en TarjetaMenu.
Item {
    id: raiz

    property real escala: 1
    property string version: ""
    // D-12: Salir deshabilitado hasta tener canal de sesión (TODO(MP-03) en la pantalla)
    property bool salirHabilitado: false
    // Home en el propio menú: inactivo (no responde), sin atenuar — es la pantalla actual.
    // PROVISIONAL: el diseñador define si va resaltado.
    property bool inicioActivo: false

    signal salirPulsado()
    signal inicioPulsado()

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    width: m(1128)
    height: m(139)

    readonly property string _iconos: "../../assets/iconos/color/"

    Rectangle {
        anchors.fill: parent
        radius: raiz.m(26)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2); border.color: "#F5F5F5"   // bordeSuave de PantallaPreciclo.qml
    }

    component Divisor: Rectangle {
        property real cx: 0
        x: raiz.m(cx - 1); y: raiz.m(19)
        width: raiz.m(2); height: raiz.m(106)
        color: "#BEBEBE"   // divisorPie de PantallaPreciclo.qml
    }
    Divisor { cx: 313 }
    Divisor { cx: 800 }

    Item {
        objectName: "botonSalir"
        x: 0; y: 0; width: raiz.m(313); height: parent.height
        enabled: raiz.salirHabilitado
        opacity: enabled ? 1.0 : 0.4   // PROVISIONAL, misma convención que PantallaPreciclo.qml
        // tinta de salir_sesion.svg = [7.5, 4.0, 40.5, 44.0]: 90 de alto -> k = 2.25
        Image {
            x: raiz.m(116 - 7.5 * 2.25); y: raiz.m(24 - 4.0 * 2.25)
            width: raiz.m(48 * 2.25); height: width
            source: raiz._iconos + "salir_sesion.svg"
            sourceSize.width: width
            sourceSize.height: height
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.salirPulsado() }
    }

    Item {
        objectName: "botonInicio"
        x: raiz.m(800); y: 0; width: raiz.m(1128 - 800); height: parent.height
        enabled: raiz.inicioActivo
        // caja [923, 23, 88, 77] de la barra; tinta de casa.svg = [4.1, 6.8, 43.9, 41.4]
        readonly property real _k: 77 / (41.4 - 6.8)
        Image {
            x: raiz.m(923 + 44 - 800 - (4.1 + 43.9) / 2 * parent._k)
            y: raiz.m(23 - 6.8 * parent._k)
            width: raiz.m(48 * parent._k); height: width
            source: raiz._iconos + "casa.svg"
            sourceSize.width: width
            sourceSize.height: height
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.inicioPulsado() }
    }

    Text {
        x: raiz.m(1128 - 22) - width
        y: raiz.m(139 - 18) - baselineOffset
        text: raiz.version
        color: "#8F8F8F"   // versionTexto de PantallaPreciclo.qml
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(20)
    }
}

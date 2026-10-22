import QtQuick
import Tema

// Barra inferior del Menú Principal (planeacion_menu_principal_ui_qml.md §5, D-06),
// también la de Login y OPCIONES. U2 (tanda 2): Atrás a la izquierda (regresa a
// la pantalla anterior; no cierra sesión, que solo cierra la inactividad SAF-01,
// decisión 7) en el lugar del antiguo Salir, Home a la derecha, celda central vacía entre los dos
// separadores y la versión abajo a la derecha. Medidas del v3 relativas a la
// propia barra (1128 x 139; separadores en x 313 y 800; tinta de Salir 75 x 90 en
// (116, 24); casa en la misma caja que la barra de PantallaPreciclo.qml). Estilo
// de fondo, borde, separadores y versión copiado de la barra inline de
// PantallaPreciclo.qml, que no se refactoriza (D-19). `escala` como en TarjetaMenu.
Item {
    id: raiz

    property real escala: 1
    property string version: ""
    property bool atrasHabilitado: true
    // Home: activo en Menú, Login y OPCIONES (lo fija cada pantalla).
    property bool inicioActivo: false

    // Cerrar sesión en la celda central (solo OPCIONES)
    property bool cerrarSesionVisible: false

    // B1 (tanda 6): Preciclo y Ciclo en curso ponen su propio contenido en las
    // tres celdas (equipo, sesión, cancelar...). Con `personalizada` se ocultan
    // Atrás, Inicio y Cerrar sesión; los hijos declarados en la pantalla van a
    // `contenido`, con coordenadas relativas a la barra.
    property bool personalizada: false
    default property alias contenido: capa.data

    signal atrasPulsado()
    signal inicioPulsado()
    signal cerrarSesionPulsado()

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    // D8-5.2 (tanda 8): la barra mide EXACTAMENTE lo mismo que la tarjeta de
    // contenido de encima (cada pantalla fija x y width con los de su
    // tarjeta). Las posiciones horizontales del lienzo 1128 se estiran con
    // `mx`; las alturas y los iconos no cambian.
    readonly property real fx: width > 0 ? width / m(1128) : 1
    function mx(v) { return m(v) * fx }

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
        x: raiz.mx(cx) - raiz.m(1); y: raiz.m(19)
        width: raiz.m(2); height: raiz.m(106)
        color: "#BEBEBE"   // divisorPie de PantallaPreciclo.qml
    }
    Divisor { cx: 313 }
    Divisor { cx: 800 }

    Item {
        objectName: "botonAtras"
        visible: !raiz.personalizada
        x: 0; y: 0; width: raiz.mx(313); height: parent.height
        enabled: raiz.atrasHabilitado
        opacity: enabled ? 1.0 : 0.4   // PROVISIONAL, misma convención que PantallaPreciclo.qml
        // back_icon.svg centrada en la celda, 80 de alto
        Image {
            anchors.centerIn: parent
            width: raiz.m(70); height: width
            source: raiz._iconos + "back_icon.svg"
            sourceSize.width: width
            sourceSize.height: height
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.atrasPulsado() }
    }

    Item {
        objectName: "botonInicio"
        visible: !raiz.personalizada
        x: raiz.mx(800); y: 0; width: raiz.mx(1128 - 800); height: parent.height
        enabled: raiz.inicioActivo
        // home_icon.svg (viewBox 1100 x 1080, tinta casi a sangre) centrado en la celda
        Image {
            anchors.centerIn: parent
            width: raiz.m(70); height: width
            source: raiz._iconos + "home_icon.svg"
            sourceSize.width: width
            sourceSize.height: height
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.inicioPulsado() }
    }

    // Cerrar sesión: celda central, solo si la pantalla lo habilita (OPCIONES)
    Item {
        objectName: "botonCerrarSesion"
        visible: raiz.cerrarSesionVisible && !raiz.personalizada
        x: raiz.mx(313); y: 0; width: raiz.mx(800 - 313); height: parent.height
        Image {
            anchors.centerIn: parent
            width: raiz.m(70); height: width
            source: raiz._iconos + "logout_icon.svg"
            sourceSize.width: width
            sourceSize.height: height
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.cerrarSesionPulsado() }
    }

    Text {
        x: raiz.width - raiz.m(22) - width
        y: raiz.m(139 - 18) - baselineOffset
        text: raiz.version
        color: "#8F8F8F"   // versionTexto de PantallaPreciclo.qml
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(20)
    }

    // contenido propio de la pantalla (B1); encima del fondo y los separadores
    Item { id: capa; anchors.fill: parent }
}

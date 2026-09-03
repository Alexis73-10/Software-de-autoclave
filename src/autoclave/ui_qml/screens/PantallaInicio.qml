// ui_qml/screens/PantallaInicio.qml
//
// Pantalla de arranque (/splash, §10.1 del sistema de diseño): la primera
// pantalla que ve el operador al encender el equipo. Fondo, logo, reloj y
// fecha. Sin campana ni engranaje: pedido explícito del usuario para esta
// primera entrega, difiere del sistema de diseño original. Avanza al
// tocar en cualquier punto de la pantalla (en vez del avance automático
// por tiempo del sistema de diseño original) — instrucción más reciente
// del usuario. La pantalla siguiente no está diseñada todavía; `avanzar()`
// queda sin destino hasta entonces.
//
// El reloj es contorno con interior transparente (no relleno translúcido,
// que era la alternativa que el sistema de diseño dejaba abierta) — pedido
// explícito del usuario tras ver el mockup real. Text.style: Text.Outline
// + color transparente logra esto nativamente en QtQuick (verificado con
// grabToImage: solo el trazo en styleColor es visible, el interior deja
// pasar lo que hay detrás).
//
// El fondo es assets/fondo-splash.png — imagen de diseño real que el
// usuario proporcionó (fondo_800x1280.pdf), rasterizada una vez vía
// QPdfDocument. Se descartó recrear --gradient-splash con
// Qt5Compat.GraphicalEffects.RadialGradient: además de no igualar el
// original, es un efecto de shader — no verificable en esta sesión con
// capturas headless (QT_QPA_PLATFORM=offscreen no ejecuta el pipeline de
// shaders), así que usar el activo real elimina esa incertidumbre.
// fillMode: PreserveAspectCrop en vez de Stretch — la imagen quedó
// rasterizada a la proporción 800:1280 del PDF original; el lienzo lógico
// (Tokens.layout.canvas) puede cambiar de proporción (hoy 768:1024) sin
// que el fondo se deforme, a costa de recortar el sobrante.
//
// El logo (assets/logo-especifika-blanco.png) sale de LOGO ESPECIFIKA.svg
// (export de CorelDRAW): traía fill como clase CSS, que el renderizador
// SVG Tiny 1.2 de Qt no resuelve (hallazgo UI-06) — se resolvió a
// atributos directos con inline_svg_classes.py. Aun resuelto, QML Image
// lo carga en blanco (viewBox en decenas de millones de unidades; con
// QSvgRenderer directo sí renderiza) — de ahí la rasterización a PNG.
// Blanco baked-in en el propio PNG (fill="black"->"white" sobre el SVG ya
// vectorial, sin pérdida) en vez de teñido en tiempo de ejecución vía
// MultiEffect: coincide con lo que el propio sistema de diseño pedía
// (logo-especifika-blanco.svg como variante dedicada para header/splash,
// §7.3) y evita depender de un efecto de shader para una sola pantalla.
// Si más adelante el diseñador entrega el SVG blanco oficial, ese archivo
// reemplaza a este PNG derivado sin más cambios.

import QtQuick
import Autoclave.Design 1.0
import Autoclave.Controllers 1.0

Item {
    id: root

    // Tamaño por defecto para cuando este componente se instancia solo
    // (p. ej. en pruebas) — dentro de Main.qml, ContenedorEscalado ya le da
    // el tamaño real vía anchors.fill: parent, así que esto no se usa ahí.
    implicitWidth: Tokens.layout.canvas.w
    implicitHeight: Tokens.layout.canvas.h

    signal avanzar()

    function tocar() {
        root.avanzar();
    }

    RelojSplashController {
        id: reloj
        objectName: "reloj"
    }

    Image {
        id: fondo
        objectName: "fondo"
        anchors.fill: parent
        source: "../assets/fondo-splash.png"
        fillMode: Image.PreserveAspectCrop
    }

    Image {
        id: logo
        objectName: "logo"
        anchors.horizontalCenter: parent.horizontalCenter // mantiene el logo centrado horizontalmente; normalmente no hace falta tocarlo.
        y: parent.height * 0.3 //la posición vertical: 0.3 = 30% de la altura de la pantalla (del lienzo lógico, Tokens.layout.canvas) medido desde arriba. Súbelo (ej. 0.2) para subir el logo, bájalo (ej. 0.4) para bajarlo.
        width: 260  //el ancho del logo en píxeles, dentro del lienzo lógico (Tokens.layout.canvas). Súbelo o bájalo para hacerlo más grande/chico. Como es una imagen vectorial rasterizada a buena resolución, se puede agrandar bastante sin verse borrosa.
        height: width * (446 / 1666) //la altura se calcula sola a partir del ancho, para mantener la proporción original del logo (1666×446 px es el tamaño del PNG fuente). No cambies esta línea directamente — si cambias width, height se ajusta solo.
        source: "../assets/logo-especifika-blanco.png"
        fillMode: Image.PreserveAspectFit
    }

    Text {
        id: textoHora
        objectName: "textoHora"
        readonly property bool esContorno: style === Text.Outline

        text: reloj.horaActual
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.5
        color: "transparent"
        style: Text.Outline
        styleColor: Tokens.color.text.onColor
        font.family: Tokens.typography.family.ui
        font.pixelSize: Tokens.typography.scale.displayClock.size
        font.weight: Font.ExtraLight
        font.letterSpacing: Tokens.typography.scale.displayClock.size * -0.02
    }

    Text {
        id: textoFecha
        objectName: "textoFecha"
        text: reloj.fechaActual
        anchors.horizontalCenter: parent.horizontalCenter
        y: textoHora.y + textoHora.height + 16
        color: Tokens.color.text.onColor
        opacity: 0.85
        font.family: Tokens.typography.family.ui
        font.pixelSize: Tokens.typography.scale.clockDate.size
        font.weight: Tokens.typography.scale.clockDate.weight
        font.letterSpacing: Tokens.typography.scale.clockDate.size * 0.05
    }

    MouseArea {
        anchors.fill: parent
        onClicked: root.tocar()
    }
}

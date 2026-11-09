pragma Singleton
import QtQuick

QtObject {
    // Lienzo de diseño = panel real medido (1200x1920, proporción 5:8).
    // Las referencias del diseñador (06_MEDIDAS/medidas.csv) vienen en 1080x1920;
    // este es el único lugar que hay que tocar si el lienzo cambia.
    readonly property real anchoVertical: 1200
    readonly property real altoVertical: 1920

    // Tanda horizontal (9-nov): el equipo admite las dos orientaciones del
    // monitor. Con la pantalla vertical (alto > ancho) rige el lienzo vertical
    // de siempre, 1200x1920, sin ningún cambio; con la pantalla horizontal
    // (ancho >= alto) rige el lienzo horizontal fijo 1920x1200 (8:5), con los
    // mismos px de diseño, letras, botones, márgenes y colores: solo cambia la
    // disposición. La fija cada ventana raíz (Main, InstalacionVentana,
    // ReposoInstalacionVentana, NuevoUsuarioHost) con esHorizontal() sobre su
    // propio tamaño, que es el de su monitor en pantalla completa: si Windows
    // gira el monitor, la ventana cambia de tamaño y la disposición la sigue.
    // Fuera de esas raíces (pruebas que arman su propia ventana) vale false.
    property bool horizontal: false
    readonly property real anchoHorizontal: 1920
    readonly property real altoHorizontal: 1200
    function esHorizontal(ancho, alto) { return ancho > 0 && alto > 0 && ancho >= alto }

    // Lienzo vigente según la orientación
    readonly property real anchoDiseno: horizontal ? anchoHorizontal : anchoVertical
    readonly property real altoDiseno: horizontal ? altoHorizontal : altoVertical

    property real factor: 1.0

    // Alto del lienzo en px de diseño (>= altoDiseno). En pantallas más altas que
    // 5:8 (p. ej. 9:16) manda el ancho y el lienzo crece hacia abajo en vez de
    // dejar franjas: las pantallas de alto flexible (PantallaCicloEnCurso) reparten
    // ese espacio; las de alto fijo van dentro de AreaFija, centradas en un área de
    // altoDiseno. En pantallas más anchas que 5:8 manda el alto y quedan franjas laterales.
    // En horizontal es igual con el lienzo 1920x1200: más alto que 8:5 (p. ej. 4:3)
    // crece hacia abajo; más ancho (16:9), franjas laterales.
    property real altoLienzo: altoDiseno

    function px(valor) { return valor * factor }
    // pixelSize exige entero; redondear evita que Qt trunque y el texto quede chico
    function fuente(valor) { return Math.max(1, Math.round(valor * factor)) }
    // D8-5.4 (tanda 8, V8b): ningún texto se recorta; si no cabe, la letra puede
    // bajar (fontSizeMode) hasta este mínimo legible (14 px de diseño: los textos
    // del equipo van de 17 a 24 px, así que con 18 casi ninguno podía reducirse)
    readonly property int fuenteMinima: Math.max(1, Math.round(14 * factor))
}

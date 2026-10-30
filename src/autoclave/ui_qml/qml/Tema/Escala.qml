pragma Singleton
import QtQuick

QtObject {
    // Lienzo de diseño = panel real medido (1200x1920, proporción 5:8).
    // Las referencias del diseñador (06_MEDIDAS/medidas.csv) vienen en 1080x1920;
    // este es el único lugar que hay que tocar si el lienzo cambia.
    readonly property real anchoDiseno: 1200
    readonly property real altoDiseno: 1920

    property real factor: 1.0

    // Alto del lienzo en px de diseño (>= altoDiseno). En pantallas más altas que
    // 5:8 (p. ej. 9:16) manda el ancho y el lienzo crece hacia abajo en vez de
    // dejar franjas: las pantallas de alto flexible (PantallaCicloEnCurso) reparten
    // ese espacio; las de alto fijo van dentro de AreaFija, centradas en un área de
    // altoDiseno. En pantallas más anchas que 5:8 manda el alto y quedan franjas laterales.
    property real altoLienzo: altoDiseno

    function px(valor) { return valor * factor }
    // pixelSize exige entero; redondear evita que Qt trunque y el texto quede chico
    function fuente(valor) { return Math.max(1, Math.round(valor * factor)) }
    // D8-5.4 (tanda 8, V8b): ningún texto se recorta; si no cabe, la letra puede
    // bajar (fontSizeMode) hasta este mínimo legible (14 px de diseño: los textos
    // del equipo van de 17 a 24 px, así que con 18 casi ninguno podía reducirse)
    readonly property int fuenteMinima: Math.max(1, Math.round(14 * factor))
}

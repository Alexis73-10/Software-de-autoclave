pragma Singleton
import QtQuick

QtObject {
    // Lienzo de diseño = panel real medido (1200x1920, proporción 5:8).
    // Las referencias del diseñador (06_MEDIDAS/medidas.csv) vienen en 1080x1920;
    // este es el único lugar que hay que tocar si el lienzo cambia.
    readonly property real anchoDiseno: 1200
    readonly property real altoDiseno: 1920

    property real factor: 1.0

    function px(valor) { return valor * factor }
    // pixelSize exige entero; redondear evita que Qt trunque y el texto quede chico
    function fuente(valor) { return Math.max(1, Math.round(valor * factor)) }
}

pragma Singleton
import QtQuick

QtObject {
    // Lienzo de referencia del diseñador (06_MEDIDAS/medidas.csv: mesa_de_trabajo).
    // CAMBIAR estos dos valores a 1200x1920 cuando lleguen los assets corregidos
    // para el panel real medido (1200x1920, 5:8) — es el único lugar que hay que tocar.
    readonly property real anchoDiseno: 1080
    readonly property real altoDiseno: 1920

    property real factor: 1.0

    function px(valor) { return valor * factor }
    // pixelSize exige entero; redondear evita que Qt trunque y el texto quede chico
    function fuente(valor) { return Math.max(1, Math.round(valor * factor)) }
}

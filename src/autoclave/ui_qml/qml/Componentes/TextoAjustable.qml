import QtQuick
import Autoclave.I18n

// U10a (tanda 10, D10-1.1): texto de una línea que muestra el texto COMPLETO si
// cabe en `anchoDisponible` y el ABREVIADO solo si el completo no cabe. Nunca
// recorta (sin elide ni maximumLineCount, D8-5.4): si ni el abreviado cabe,
// `desborda` queda en true y la prueba de D10-1.5 lo detecta
// (tests/textos_caben_qml.py, tests/test_u10a_textos_caben_qml.py).
//
// Dos formas de uso:
//   TextoAjustable { clave: "ciclo.temp_ester"; anchoDisponible: 120 }
//       toma el completo de `clave` y el abreviado de `abrev.<clave>` (D10-1.2:
//       las abreviaturas viven solo en la sección `abrev` del catálogo, con la
//       misma ruta que su texto completo). Sin `abrev.<clave>`, siempre el completo.
//   TextoAjustable { textoCompleto: ...; textoAbreviado: ...; anchoDisponible: 120 }
//       con los dos textos ya resueltos.
//
// `anchoDisponible` es el ancho real en px de la pantalla (no del mockup): lo
// calcula quien lo usa (p. ej. hasta el divisor de la columna, menos un margen).
// No fija `width`: el ancho del ítem es el del texto mostrado.
Text {
    id: raiz

    property string clave: ""
    // Tanda 17 (SON-01): texto que se agrega a los dos (p. ej. " (monitoreo)")
    property string sufijo: ""
    property string textoCompleto: clave !== "" ? I18n.t(clave, I18n.lang) + sufijo : ""
    property string textoAbreviado: clave !== "" && I18n.existe("abrev." + clave, I18n.lang)
                                    ? I18n.t("abrev." + clave, I18n.lang) + sufijo : ""
    property real anchoDisponible: 0

    // ancho del texto completo con la fuente vigente (no depende de lo mostrado)
    readonly property real anchoCompleto: medidaCompleto.advanceWidth
    readonly property bool usaAbreviado: textoAbreviado !== "" && anchoCompleto > anchoDisponible + 0.5
    // ni lo mostrado cabe: error de diseño o de catálogo, no se recorta
    readonly property bool desborda: implicitWidth > anchoDisponible + 0.5

    text: usaAbreviado ? textoAbreviado : textoCompleto
    wrapMode: Text.NoWrap
    elide: Text.ElideNone

    TextMetrics {
        id: medidaCompleto
        font: raiz.font
        text: raiz.textoCompleto
    }
}

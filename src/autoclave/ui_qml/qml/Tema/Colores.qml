pragma Singleton
import QtQuick

// Fuente única de color: 02_COLOR/tokens.css y paleta.csv del diseñador.
// Ninguna pantalla debe escribir un hex a mano — todo pasa por aquí.
QtObject {
    // Fondos oscuros (arranque / chrome)
    readonly property color fondoMarinoOscuro:  "#1B222A"  // fondo_marino_950
    readonly property color fondoBarraSuperior: "#2C4B70"  // fondo_marino_700
    readonly property color fondoAzulMedio:     "#2E597C"  // fondo_azul_700
    readonly property color fondoCieloNucleo:   "#5C97DB"  // fondo_cielo_300 — halo del arranque
    readonly property color fondoCieloClaro:    "#99C5E2"  // fondo_cielo_200

    // Acción
    readonly property color accionPrimario:      "#1168F6" // botón primario
    readonly property color accionPrimarioTexto: "#0D53C4" // obligatorio para texto (contraste)

    // Alarmas IEC 60601-1-8 — reservado, no usar para nada que no sea alarma
    readonly property color alarmaAlta:  "#EE0000"
    readonly property color alarmaMedia: "#FFCC00"
    readonly property color alarmaBaja:  "#00CCFF"

    // Neutros / texto
    readonly property color textoPrimario:      "#031225" // neutro_900
    readonly property color textoSecundario:    "#4D4D4D" // neutro_700
    readonly property color textoGuia:          "#808080" // neutro_500 — placeholder, ≥19px
    readonly property color bordeCampo:         "#CCCCCC" // neutro_300
    readonly property color fondoTarjeta:       "#FFFFFF"
    readonly property color iconoBarraInferior: "#333333" // neutro_800
}

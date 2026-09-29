pragma Singleton
import QtQuick

// Estilos de docs/diseno/estilos_de_texto.csv (03_TIPOGRAFIA del paquete del diseñador).
// Familia: el paquete del diseñador no incluyó archivos de fuente. Montserrat se descargó
// del repositorio oficial de la fuente (licencia SIL OFL 1.1) y se eligió por semejanza
// visual con los mockups. tokens.css y tokens.json declaran "Inter" y están desactualizados.
// Relojes: Tahoma es fuente de sistema de Windows (licencia de Microsoft, no se redistribuye
// ni se copia a assets). Elegida por Cristian por semejanza visual con los relojes del mockup.
// Dependencia del sistema operativo: Windows 11. Solo tiene Regular y Bold, así que los pesos
// Light/Medium de los relojes se ven Regular y SemiBold se ve Bold.
QtObject {
    // único lugar donde se nombra cada familia; familiaReloj la usan solo los estilos reloj: true
    readonly property string familia: "Montserrat"
    readonly property string familiaReloj: "Tahoma"

    // tamaños en px de diseño — pasar por Escala.fuente() al usarlos
    readonly property int relojDisplayTam: 158
    readonly property int relojBarraTam: 54
    readonly property int relojFechaTam: 20
    readonly property int tituloPantallaTam: 36
    readonly property int campoEtiquetaTam: 22
    readonly property int campoValorTam: 26
    readonly property int botonEtiquetaTam: 26

    readonly property int pesoLight: Font.Light
    readonly property int pesoRegular: Font.Normal
    readonly property int pesoMedium: Font.Medium
    readonly property int pesoSemiBold: Font.DemiBold
    readonly property int pesoBold: Font.Bold

    // Tabla del CSV en px de diseño: tam = tamaño, lh = interlineado, peso,
    // track = tracking en % del tamaño, tab = cifras tabulares (OpenType "tnum"),
    // reloj = usa familiaReloj. Tahoma no tiene "tnum" (sus dígitos ya son de ancho fijo),
    // por eso reloj_barra y reloj_fecha van con tab: false aunque el CSV diga SI.
    // No usar directo: pasar por estilo(), que escala.
    readonly property var estilosDiseno: ({
        "reloj_display":       { tam: relojDisplayTam,   lh: 158, peso: pesoLight,    track: -2, tab: false, reloj: true },
        "reloj_barra":         { tam: relojBarraTam,     lh: 54,  peso: pesoSemiBold, track: 0,  tab: false, reloj: true },
        "reloj_fecha":         { tam: relojFechaTam,     lh: 26,  peso: pesoMedium,   track: 6,  tab: false, reloj: true },
        "titulo_pantalla":     { tam: tituloPantallaTam, lh: 44,  peso: pesoBold,     track: 5,  tab: false },
        "titulo_seccion":      { tam: 24,                lh: 30,  peso: pesoBold,     track: 8,  tab: false },
        "tarjeta_titulo":      { tam: 26,                lh: 32,  peso: pesoBold,     track: 3,  tab: false },
        "tarjeta_descripcion": { tam: 21,                lh: 28,  peso: pesoRegular,  track: 0,  tab: false },
        "cuerpo":              { tam: 26,                lh: 38,  peso: pesoRegular,  track: 0,  tab: false },
        "campo_etiqueta":      { tam: campoEtiquetaTam,  lh: 28,  peso: pesoMedium,   track: 1,  tab: false },
        "campo_valor":         { tam: campoValorTam,     lh: 34,  peso: pesoRegular,  track: 0,  tab: false },
        "campo_placeholder":   { tam: 26,                lh: 34,  peso: pesoRegular,  track: 0,  tab: false },
        "boton_etiqueta":      { tam: botonEtiquetaTam,  lh: 32,  peso: pesoSemiBold, track: 1,  tab: false },
        "sensor_valor":        { tam: 54,                lh: 58,  peso: pesoBold,     track: -1, tab: true  },
        "sensor_etiqueta":     { tam: 19,                lh: 24,  peso: pesoSemiBold, track: 2,  tab: false },
        "sensor_unidad":       { tam: 21,                lh: 26,  peso: pesoRegular,  track: 2,  tab: false },
        "kpi_valor":           { tam: 46,                lh: 50,  peso: pesoBold,     track: 0,  tab: true  },
        "temporizador":        { tam: 78,                lh: 78,  peso: pesoSemiBold, track: 1,  tab: true  },
        "chip_etiqueta":       { tam: 19,                lh: 24,  peso: pesoBold,     track: 7,  tab: false },
        "pie_nota":            { tam: 18,                lh: 24,  peso: pesoRegular,  track: 1,  tab: false },
        "grafica_eje":         { tam: 18,                lh: 22,  peso: pesoMedium,   track: 2,  tab: true  },
        "meta_version":        { tam: 16,                lh: 20,  peso: pesoMedium,   track: 4,  tab: false }
    })

    // Estilo escalado listo para usar, p. ej.:
    //   font.family: Tipografia.estilo("cuerpo").familia
    //   font.pixelSize: Tipografia.estilo("cuerpo").tamano
    //   font.weight: Tipografia.estilo("cuerpo").peso
    //   font.letterSpacing: Tipografia.estilo("cuerpo").letterSpacing
    //   font.features: Tipografia.estilo("cuerpo").features
    //   lineHeightMode: Text.FixedHeight; lineHeight: Tipografia.estilo("cuerpo").interlineado
    // Lee Escala.factor, así que los bindings se reevalúan al cambiar la escala.
    function estilo(nombre) {
        const e = estilosDiseno[nombre]
        if (e === undefined) {
            console.warn("Tipografia.estilo: estilo desconocido", nombre)
            return undefined
        }
        return {
            familia: e.reloj === true ? familiaReloj : familia,
            tamano: Escala.fuente(e.tam),
            interlineado: Escala.px(e.lh),
            peso: e.peso,
            letterSpacing: Escala.px(e.tam * e.track / 100),
            tabular: e.tab,
            features: e.tab ? { "tnum": 1 } : {}
        }
    }
}

pragma Singleton
import QtQuick

// Estilos de 03_TIPOGRAFIA/estilos_de_texto.csv.
// PENDIENTE: familia sin confirmar formalmente por el diseñador (tokens.css dice "Inter",
// el único archivo de fuente real entregado es Montserrat). Se usa Montserrat como decisión
// de trabajo, reversible cambiando esta única línea.
QtObject {
    readonly property string familia: "Montserrat"

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
}

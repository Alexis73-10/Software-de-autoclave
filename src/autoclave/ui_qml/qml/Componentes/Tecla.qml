import QtQuick
import Tema

// Tecla de los teclados en pantalla (Paso 2 de planeacion_teclados_qml.md).
// Dos estados, normal y presionado (TEC-D04): sin hover y sin deshabilitado.
// El presionado queda visible al menos Teclado.presionadoMinimoMs (90 ms)
// aunque el toque sea más corto. Medidas de Tema/Teclado.qml; tipografía y
// colores de CANCELAR y BORRAR, provisionales, de Tema/TecladoProvisional.qml.
//
// Señales: pulsada() al soltar dentro de la tecla (uso normal);
// presionada()/soltada()/cancelada() para Borrar, cuyo borrado total por
// pulsación larga decide el controlador (TEC-D12). Soltar fuera de la tecla
// emite cancelada(), no soltada().
Rectangle {
    id: raiz

    property string texto: ""
    property url icono: ""
    // "normal" | "borrar" | "confirmar" | "cancelar"
    property string variante: "normal"
    // Aa armada (PROV-02): se ve como presionada mientras dure
    property bool marcada: false
    // tamaño del texto en px de diseño (por defecto el de PROV-01)
    property int tamTexto: TecladoProvisional.tamTexto

    signal pulsada()
    signal presionada()
    signal soltada()
    signal cancelada()

    readonly property bool verPresionada: area.pressed || retencion.running
                                          || (marcada && TecladoProvisional.aaArmadaComoPresionada)
    readonly property var _estiloTexto: Tipografia.estilo(TecladoProvisional.estiloTexto)

    implicitWidth: Escala.px(Teclado.anchoTecla)
    implicitHeight: Escala.px(Teclado.altoTecla)
    radius: Escala.px(Teclado.radioTecla)
    border.width: Escala.px(Teclado.bordeTecla)

    color: {
        if (raiz.verPresionada) return Colores.accionFondoTenue
        switch (raiz.variante) {
        case "confirmar": return Colores.accionPrimario
        case "borrar":    return Colores[TecladoProvisional.borrarFondo]
        case "cancelar":  return Colores[TecladoProvisional.cancelarFondo]
        default:          return Colores.fondoTarjeta
        }
    }
    border.color: {
        if (raiz.verPresionada) return Colores.accionPrimario
        switch (raiz.variante) {
        case "confirmar": return Colores.accionPrimario
        case "borrar":    return Colores[TecladoProvisional.borrarBorde]
        case "cancelar":  return Colores[TecladoProvisional.cancelarBorde]
        default:          return Colores.bordeCampo
        }
    }
    readonly property color colorTexto: {
        if (raiz.verPresionada) return Colores.accionPrimarioTexto
        switch (raiz.variante) {
        case "confirmar": return "white"
        case "borrar":    return Colores[TecladoProvisional.borrarTexto]
        case "cancelar":  return Colores[TecladoProvisional.cancelarTexto]
        default:          return Colores.textoPrimario
        }
    }

    Text {
        anchors.centerIn: parent
        width: parent.width - Escala.px(8)
        horizontalAlignment: Text.AlignHCenter
        visible: raiz.texto !== ""
        text: raiz.texto
        elide: Text.ElideRight
        color: raiz.colorTexto
        font.family: raiz._estiloTexto.familia
        font.weight: raiz._estiloTexto.peso
        font.letterSpacing: raiz._estiloTexto.letterSpacing
        font.pixelSize: Escala.fuente(raiz.tamTexto)
        // acciones en mayúsculas como en el diseño (pág. 24); los caracteres tal cual
        font.capitalization: raiz.variante === "normal" ? Font.MixedCase : Font.AllUppercase
    }

    Image {
        anchors.centerIn: parent
        visible: raiz.texto === "" && raiz.icono.toString() !== ""
        width: Escala.px(48); height: width   // tamaño nativo de los íconos del diseñador
        source: raiz.icono
        sourceSize.width: width
        sourceSize.height: height
    }

    // Mantiene visible el presionado 90 ms desde que empieza el toque
    Timer { id: retencion; interval: Teclado.presionadoMinimoMs }

    MouseArea {
        id: area
        anchors.fill: parent
        onPressed: { retencion.restart(); raiz.presionada() }
        onReleased: {
            if (containsMouse) {
                raiz.soltada()
                raiz.pulsada()
            } else {
                raiz.cancelada()
            }
        }
        onCanceled: raiz.cancelada()
    }
}

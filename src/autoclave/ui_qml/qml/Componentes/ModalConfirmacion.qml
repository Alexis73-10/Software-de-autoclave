import QtQuick
import Tema
import Autoclave.I18n

// FC-09 (tanda 21, planeacion_fin_de_ciclo.md): modal de confirmación de la
// pantalla de ciclo y del preciclo. Mismo estilo que PanelModal.qml (fondo
// oscurecido, tarjeta blanca de radio 28, título, divisor), pero con dos
// botones: PanelModal solo trae el botón de cierre y no se modifica.
//
// Título Bold 36, divisor, cuerpo 28 con WordWrap, nota opcional resaltada
// (fondo advertenciaFondo, borde advertencia, texto advertenciaTexto) y dos
// botones de 340 × 88: «Volver» (contorno) y la acción, con color
// configurable y texto con fontSizeMode HorizontalFit (mínimo
// Escala.fuenteMinima). Tocar el fondo equivale a «Volver», sin acción.
// Solo confirmación: sin credencial ni rol.
//
// Uso (ola 2):
//   ModalConfirmacion {
//       id: modalCancelar
//       titulo: I18n.t("ciclo.<clave>", I18n.lang)
//       cuerpo: ...
//       nota: ""                              // vacía = sin nota
//       textoAccion: ...
//       colorAccion: Colores.peligroTexto
//       onAceptado: UiBridge.cancelarCiclo()
//   }
//   modalCancelar.abrir()
Item {
    id: raiz
    anchors.fill: parent
    visible: false
    z: 100

    property string titulo: ""
    property string cuerpo: ""
    property string nota: ""
    property string textoVolver: I18n.t("ciclo.modal_volver", I18n.lang)
    property string textoAccion: ""
    property color colorAccion: Colores.accionPrimario
    property color colorTextoAccion: "white"

    readonly property bool abierto: visible

    signal aceptado()
    signal cancelado()

    function abrir() { visible = true }
    function cerrar() { visible = false }
    function _volver() { cerrar(); cancelado() }
    // se cierra al aceptar: el estado del envío lo muestra la pantalla
    function _aceptar() { cerrar(); aceptado() }

    Rectangle {
        objectName: "fondoModalConfirmacion"
        anchors.fill: parent
        color: "#99000000"
        MouseArea { anchors.fill: parent; onClicked: raiz._volver() }
    }

    Rectangle {
        id: tarjeta
        objectName: "tarjetaModalConfirmacion"
        readonly property real margen: Escala.px(48)
        width: parent.width - Escala.px(160)
        // alto del contenido; si no cabe en la pantalla, el cuerpo se desplaza
        readonly property real altoContenido: zona.contentHeight
        height: Math.min(textoTitulo.y + textoTitulo.height + Escala.px(20 + 2 + 24)
                         + altoContenido + Escala.px(48) + filaBotones.height + Escala.px(48),
                         parent.height - Escala.px(192))
        anchors.centerIn: parent
        radius: Escala.px(28)
        color: Colores.fondoTarjeta
        MouseArea { anchors.fill: parent }   // no dejar pasar el toque al fondo

        Text {
            id: textoTitulo
            objectName: "tituloModalConfirmacion"
            x: tarjeta.margen; y: Escala.px(40)
            width: tarjeta.width - 2 * tarjeta.margen
            text: raiz.titulo
            wrapMode: Text.WordWrap
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(Tipografia.tituloPantallaTam)
        }
        Rectangle {
            id: linea
            x: tarjeta.margen; y: textoTitulo.y + textoTitulo.height + Escala.px(20)
            width: tarjeta.width - 2 * tarjeta.margen; height: Escala.px(2)
            color: Colores.bordeDivisor
        }

        Flickable {
            id: zona
            objectName: "zonaModalConfirmacion"
            x: tarjeta.margen
            anchors.top: linea.bottom
            anchors.topMargin: Escala.px(24)
            anchors.bottom: filaBotones.top
            anchors.bottomMargin: Escala.px(48)
            width: tarjeta.width - 2 * tarjeta.margen
            contentWidth: width
            contentHeight: columna.height
            boundsBehavior: Flickable.StopAtBounds
            interactive: contentHeight > height
            clip: true

            Column {
                id: columna
                width: zona.width
                spacing: Escala.px(28)

                Text {
                    objectName: "cuerpoModalConfirmacion"
                    width: columna.width
                    visible: text !== ""
                    text: raiz.cuerpo
                    wrapMode: Text.WordWrap
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(28)
                    lineHeight: 1.15
                }
                Rectangle {
                    objectName: "notaModalConfirmacion"
                    visible: raiz.nota !== ""
                    width: columna.width
                    height: textoNota.height + Escala.px(48)
                    radius: Escala.px(12)
                    color: Colores.advertenciaFondo
                    border.width: Escala.px(2); border.color: Colores.advertencia
                    Text {
                        id: textoNota
                        x: Escala.px(24); y: Escala.px(24)
                        width: parent.width - Escala.px(48)
                        text: raiz.nota
                        wrapMode: Text.WordWrap
                        color: Colores.advertenciaTexto
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(24)
                        lineHeight: 1.15
                    }
                }
            }
        }

        Row {
            id: filaBotones
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Escala.px(48)
            spacing: Escala.px(40)

            Rectangle {
                objectName: "botonVolverModal"
                width: Escala.px(340); height: Escala.px(88)
                radius: Escala.px(6)
                color: Colores.fondoTarjeta
                border.width: Escala.px(2); border.color: Colores.bordeCampo
                Text {
                    anchors.centerIn: parent
                    width: parent.width - Escala.px(32)
                    horizontalAlignment: Text.AlignHCenter
                    text: raiz.textoVolver
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: Escala.fuenteMinima
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                }
                MouseArea { anchors.fill: parent; onClicked: raiz._volver() }
            }
            Rectangle {
                objectName: "botonAccionModal"
                width: Escala.px(340); height: Escala.px(88)
                radius: Escala.px(6)
                color: raiz.colorAccion
                Text {
                    objectName: "textoAccionModal"
                    anchors.centerIn: parent
                    width: parent.width - Escala.px(32)
                    horizontalAlignment: Text.AlignHCenter
                    text: raiz.textoAccion
                    fontSizeMode: Text.HorizontalFit
                    minimumPixelSize: Escala.fuenteMinima
                    color: raiz.colorTextoAccion
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                }
                MouseArea { anchors.fill: parent; onClicked: raiz._aceptar() }
            }
        }
    }
}

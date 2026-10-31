import QtQuick
import Tema
import Autoclave.I18n

// FC-04 (tanda 21, planeacion_fin_de_ciclo.md): fila de acordeón del panel de
// fin de ciclo (PanelFinCiclo.qml). La fila NO decide si está abierta: lo
// decide el panel (una sola abierta a la vez) a partir de `pulsada()`.
//
// Cerrada: barra de nivel, título y hora, chevron «›». Abierta: fondo
// Colores.fondoSutil, chevron rotado 90° y el cuerpo (descripción, «QUÉ HACER»
// con la acción y la línea meta). Variante `destacada` para la fila de causa
// (FC-02): título Bold 32 y una línea de subtítulo.
//
// Ningún texto se recorta ni se elide (D8-5.4): el título usa TextoAjustable
// (abreviado si el completo no cabe) y, si ni el abreviado cabe, baja la letra
// hasta el mínimo legible; si ni así cabe, se parte en varias líneas. El resto
// de los textos usa WordWrap.
//
// Geometría en px del mockup (1196 de ancho) escalados por m(), como
// GraficaCiclo.qml: `escala` = px reales por px del mockup.
Item {
    id: raiz

    property real escala: 1.0
    property bool destacada: false
    property bool abierta: false

    property string titulo: ""
    property string tituloAbreviado: ""
    property string subtitulo: ""        // solo en la variante destacada
    property string hora: ""
    property string descripcion: ""
    property string queHacer: ""
    property string meta: ""
    // "fallo" (rojo) | "cancelado" (gris: no es alarma) | "alta" | "media" | "baja"
    // (prioridad de UiBridge.prioridad_de, mismos colores que FilaAlarma).
    // Cualquier otro valor se dibuja como "alta" (falla cerrada).
    property string nivel: "alta"

    signal pulsada()

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    // mínimo legible (Escala.fuenteMinima: 14 px de diseño) con la escala de la fila
    readonly property int fuenteMinima: fuente(14)

    readonly property color colorNivel: nivel === "cancelado" ? Colores.textoGuia
                                      : nivel === "media" ? Colores.alarmaMedia
                                      : nivel === "baja" ? Colores.alarmaBaja
                                      : Colores.alarmaAlta

    readonly property int tamTituloBase: fuente(destacada ? 32 : 26)

    // Tamaño del título sin depender de lo que se muestra (sin lazos): medidas
    // con la letra base del completo y del abreviado.
    readonly property real _anchoCompletoBase: medidaCompleto.advanceWidth
    readonly property real _anchoAbrevBase: tituloAbreviado !== "" ? medidaAbrev.advanceWidth : _anchoCompletoBase
    readonly property real _anchoMostrarBase: _anchoCompletoBase <= _anchoTitulo + 0.5
                                              ? _anchoCompletoBase
                                              : Math.min(_anchoCompletoBase, _anchoAbrevBase)
    readonly property int tamTitulo: _anchoMostrarBase <= _anchoTitulo + 0.5 || _anchoMostrarBase <= 0
                                     ? tamTituloBase
                                     : Math.max(fuenteMinima,
                                                Math.floor(tamTituloBase * _anchoTitulo / _anchoMostrarBase))
    // ni con la letra mínima cabe: se parte en líneas en vez de recortarse
    readonly property bool tituloEnVariasLineas: _anchoMostrarBase * fuenteMinima / tamTituloBase > _anchoTitulo + 0.5
    readonly property real _anchoTitulo: Math.max(1, bloqueTitulo.width)

    TextMetrics {
        id: medidaCompleto
        font.family: Tipografia.familia
        font.weight: raiz.destacada ? Tipografia.pesoBold : Tipografia.pesoSemiBold
        font.pixelSize: raiz.tamTituloBase
        text: raiz.titulo
    }
    TextMetrics {
        id: medidaAbrev
        font.family: Tipografia.familia
        font.weight: raiz.destacada ? Tipografia.pesoBold : Tipografia.pesoSemiBold
        font.pixelSize: raiz.tamTituloBase
        text: raiz.tituloAbreviado
    }

    implicitHeight: contenido.y + contenido.height + m(18)
    height: implicitHeight

    Rectangle {
        objectName: "fondoFila"
        anchors.fill: parent
        radius: raiz.m(8)
        color: raiz.abierta ? Colores.fondoSutil : "transparent"
    }

    MouseArea {
        objectName: "areaFila"
        anchors.fill: parent
        onClicked: raiz.pulsada()
    }

    Rectangle {
        objectName: "barraNivel"
        x: 0; y: raiz.m(10)
        width: raiz.m(10); height: raiz.height - raiz.m(20)
        radius: raiz.m(3)
        color: raiz.colorNivel
    }

    Column {
        id: contenido
        x: raiz.m(36); y: raiz.m(18)
        width: raiz.width - x - raiz.m(16)
        spacing: raiz.m(14)

        Item {
            id: cabecera
            width: contenido.width
            height: Math.max(bloqueTitulo.height, hora.height)

            Column {
                id: bloqueTitulo
                width: cabecera.width - hora.implicitWidth - raiz.m(16) - chevron.anchoCaja
                spacing: raiz.m(4)

                TextoAjustable {
                    id: titulo
                    objectName: "tituloFila"
                    width: raiz._anchoTitulo
                    anchoDisponible: raiz._anchoTitulo
                    textoCompleto: raiz.titulo
                    textoAbreviado: raiz.tituloAbreviado
                    wrapMode: raiz.tituloEnVariasLineas ? Text.WordWrap : Text.NoWrap
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.weight: raiz.destacada ? Tipografia.pesoBold : Tipografia.pesoSemiBold
                    font.pixelSize: raiz.tamTitulo
                }
                Text {
                    objectName: "subtituloFila"
                    visible: raiz.destacada && raiz.subtitulo !== ""
                    width: bloqueTitulo.width
                    text: raiz.subtitulo
                    wrapMode: Text.WordWrap
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: raiz.fuente(22)
                }
            }

            Text {
                id: hora
                objectName: "horaFila"
                anchors.right: chevron.left
                anchors.rightMargin: raiz.m(8)
                anchors.verticalCenter: bloqueTitulo.verticalCenter
                text: raiz.hora
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(21)
            }

            Text {
                id: chevron
                objectName: "chevronFila"
                readonly property real anchoCaja: raiz.m(40)
                anchors.right: parent.right
                anchors.verticalCenter: bloqueTitulo.verticalCenter
                width: anchoCaja
                horizontalAlignment: Text.AlignHCenter
                text: "›"
                rotation: raiz.abierta ? 90 : 0
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(34)
            }
        }

        Column {
            id: cuerpo
            objectName: "cuerpoFila"
            visible: raiz.abierta
            width: contenido.width
            spacing: raiz.m(10)

            Text {
                objectName: "descripcionFila"
                visible: raiz.descripcion !== ""
                width: cuerpo.width
                text: raiz.descripcion
                wrapMode: Text.WordWrap
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(24)
                lineHeight: 1.15
            }
            Text {
                objectName: "rotuloQueHacer"
                visible: raiz.queHacer !== ""
                width: cuerpo.width
                text: I18n.t("ciclo.fin_que_hacer", I18n.lang)
                wrapMode: Text.WordWrap
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(19)
                font.letterSpacing: raiz.m(1.5)
            }
            Text {
                objectName: "queHacerFila"
                visible: raiz.queHacer !== ""
                width: cuerpo.width
                text: raiz.queHacer
                wrapMode: Text.WordWrap
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(24)
                lineHeight: 1.15
            }
            Text {
                objectName: "metaFila"
                visible: raiz.meta !== ""
                width: cuerpo.width
                text: raiz.meta
                wrapMode: Text.WordWrap
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(19)
            }
        }
    }
}

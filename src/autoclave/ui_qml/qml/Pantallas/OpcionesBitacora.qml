pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Bitácora de auditoría (O2e, tanda 6; mockup 9). Solo lectura.
// Filtros Desde, Usuario y Tipo; filas con fecha y hora a la izquierda y una
// frase con el usuario en negrita (texto por código en el idioma vigente,
// valores en la unidad vigente). Paginación "‹ Anterior · Página n de m · Siguiente ›".
Item {
    id: raiz
    objectName: "opcionesBitacora"
    property QtObject teclado: null
    readonly property bool cambiosPendientes: false

    BitacoraController {
        id: control
        objectName: "bitacoraController"
    }
    readonly property alias controlador: control
    Component.onCompleted: control.cargar()

    function nombreTipo(t) {
        if (t === "") return I18n.t("bitacora.todos", I18n.lang)
        const k = "bitacora.tipo." + t
        return I18n.existe(k, I18n.lang) ? I18n.t(k, I18n.lang) : t
    }
    function frase(f) {
        return I18n.t(f.claveTexto, I18n.lang, { entidad: f.entidad, anterior: f.anterior,
                                                 nuevo: f.nuevo, evento: f.evento })
    }

    component Filtro: Rectangle {
        id: filtro
        property string rotulo: ""
        property string valor: ""
        signal pulsado()
        height: Escala.px(96)
        radius: Escala.px(12)
        color: Colores.fondoSutil
        border.width: Escala.px(1); border.color: Colores.bordeCampo
        Column {
            anchors.left: parent.left; anchors.leftMargin: Escala.px(16)
            anchors.right: parent.right; anchors.rightMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            Text {
                text: filtro.rotulo
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(19)
            }
            Text {
                width: parent.width; fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                text: filtro.valor
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: Escala.fuente(24)
            }
        }
        MouseArea { anchors.fill: parent; onClicked: filtro.pulsado() }
    }

    Row {
        id: filtros
        width: parent.width
        spacing: Escala.px(10)
        Filtro {
            objectName: "filtroDesde"
            width: (filtros.width - 2 * filtros.spacing) * 0.3
            rotulo: I18n.t("bitacora.desde", I18n.lang)
            valor: control.desde !== "" ? control.desde : I18n.t("bitacora.todos", I18n.lang)
            onPulsado: if (raiz.teclado) raiz.teclado.abrirAlfanumerico(
                           I18n.t("bitacora.desde_formato", I18n.lang), control.desde, 10, false,
                           (t) => raiz._desdePendiente = t)
        }
        Filtro {
            objectName: "filtroUsuario"
            width: (filtros.width - 2 * filtros.spacing) * 0.3
            rotulo: I18n.t("bitacora.usuario", I18n.lang)
            valor: control.usuario !== "" ? control.usuario : I18n.t("bitacora.todos", I18n.lang)
            onPulsado: control.siguienteUsuario()
        }
        Filtro {
            objectName: "filtroTipo"
            width: (filtros.width - 2 * filtros.spacing) * 0.4
            rotulo: I18n.t("bitacora.tipo_rotulo", I18n.lang)
            valor: raiz.nombreTipo(control.tipo)
            onPulsado: control.siguienteTipo()
        }
    }
    property string _desdePendiente: "-"
    Connections {
        target: raiz.teclado
        function onTerminado() {
            if (raiz._desdePendiente !== "-") {
                control.fijarDesde(raiz._desdePendiente)
                raiz._desdePendiente = "-"
            }
        }
    }

    Text {
        id: error
        objectName: "errorBitacora"
        anchors.top: filtros.bottom; anchors.topMargin: Escala.px(8)
        visible: control.mensaje !== ""
        width: parent.width
        height: visible ? implicitHeight : 0
        wrapMode: Text.WordWrap
        text: control.mensaje !== "" ? I18n.t(control.mensaje, I18n.lang) : ""
        color: Colores.peligroTexto
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(22)
    }

    ListView {
        id: lista
        objectName: "listaBitacora"
        anchors.top: error.bottom; anchors.topMargin: Escala.px(10)
        anchors.bottom: paginacion.top; anchors.bottomMargin: Escala.px(10)
        width: parent.width
        clip: true
        model: control.filas
        delegate: Item {
            id: fila
            required property var modelData
            objectName: "filaBitacora_" + modelData.id
            width: lista.width
            height: Math.max(Escala.px(96), textoFrase.implicitHeight + Escala.px(28))
            Column {
                id: cuando
                x: Escala.px(8)
                anchors.verticalCenter: parent.verticalCenter
                width: Escala.px(190)
                Text { text: fila.modelData.fecha; color: Colores.textoSecundario
                       font.family: Tipografia.familia; font.pixelSize: Escala.fuente(21) }
                Text { text: fila.modelData.hora; color: Colores.textoGuia
                       font.family: Tipografia.familia; font.pixelSize: Escala.fuente(20) }
            }
            Text {
                id: textoFrase
                objectName: "fraseBitacora"
                anchors.left: cuando.right; anchors.leftMargin: Escala.px(12)
                anchors.right: parent.right; anchors.rightMargin: Escala.px(8)
                anchors.verticalCenter: parent.verticalCenter
                wrapMode: Text.WordWrap
                textFormat: Text.StyledText
                // el usuario y la frase vienen de la base: se escapan antes de dar formato
                text: "<b>" + fila.modelData.usuario.replace(/&/g, "&amp;").replace(/</g, "&lt;") + "</b> "
                      + raiz.frase(fila.modelData).replace(/&/g, "&amp;").replace(/</g, "&lt;")
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(23)
            }
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Colores.bordeDivisor }
        }
    }
    Text {
        visible: control.filas.length === 0 && control.mensaje === ""
        anchors.centerIn: lista
        text: I18n.t("bitacora.vacia", I18n.lang)
        color: Colores.textoGuia
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(26)
    }

    Item {
        id: paginacion
        anchors.bottom: parent.bottom
        width: parent.width; height: Escala.px(88)
        Text {
            objectName: "paginaAnterior"
            readonly property bool habilitado: control.pagina > 1
            anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
            text: "‹ " + I18n.t("bitacora.anterior", I18n.lang)
            opacity: habilitado ? 1 : 0.35
            color: Colores.accionPrimarioTexto
            font.family: Tipografia.familia; font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(26)
            MouseArea { anchors.fill: parent; anchors.margins: -Escala.px(20); enabled: parent.habilitado
                        onClicked: control.paginaAnterior() }
        }
        Text {
            objectName: "textoPagina"
            anchors.centerIn: parent
            text: I18n.t("bitacora.pagina", I18n.lang, { n: control.pagina, m: control.paginas })
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(24)
        }
        Text {
            objectName: "paginaSiguiente"
            readonly property bool habilitado: control.pagina < control.paginas
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            text: I18n.t("bitacora.siguiente", I18n.lang) + " ›"
            opacity: habilitado ? 1 : 0.35
            color: Colores.accionPrimarioTexto
            font.family: Tipografia.familia; font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(26)
            MouseArea { anchors.fill: parent; anchors.margins: -Escala.px(20); enabled: parent.habilitado
                        onClicked: control.paginaSiguiente() }
        }
    }
}

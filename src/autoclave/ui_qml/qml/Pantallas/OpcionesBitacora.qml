pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Bitácora de auditoría (O2e, tanda 6; mockup 9). Solo lectura.
// Filtros Desde–Hasta (calendario), Usuario y Tipo (categoría; tanda 17, BIT-05); filas con fecha y hora a la izquierda y una
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

    // Tanda 17 (BIT-05): Desde y Hasta abren el calendario táctil (sin
    // teclado; por omisión Hasta = hoy y Desde sin fecha, como antes); Usuario
    // y Tipo son desplegables ("Todos" + los usuarios de la bitácora; Tipo
    // por categoría)
    readonly property var opcionesUsuario: [{ valor: "", texto: I18n.t("bitacora.todos", I18n.lang) }]
        .concat(control.usuarios.map(u => ({ valor: u, texto: u })))
    readonly property var opcionesCategoria: [{ valor: "", texto: I18n.t("bitacora.todos", I18n.lang) }]
        .concat(control.categorias.map(c => ({ valor: c, texto: raiz.nombreCategoria(c) })))
    // claves literales (sin familia dinámica): las 5 categorías de BIT-05
    function nombreCategoria(c) {
        switch (c) {
        case "seguridad": return I18n.t("bitacora.categoria.seguridad", I18n.lang)
        case "configuracion": return I18n.t("bitacora.categoria.configuracion", I18n.lang)
        case "usuarios_sesion": return I18n.t("bitacora.categoria.usuarios_sesion", I18n.lang)
        case "mantenimiento_calibracion": return I18n.t("bitacora.categoria.mantenimiento_calibracion", I18n.lang)
        case "sistema": return I18n.t("bitacora.categoria.sistema", I18n.lang)
        }
        return c
    }
    property string _campoFecha: ""           // "desde" | "hasta" mientras el calendario está abierto
    function abrirCalendario(campo) {
        _campoFecha = campo
        calendario.permiteSinFecha = true
        calendario.abrir(campo === "desde" ? control.desde : control.hasta,
                         I18n.t(campo === "desde" ? "calendario.titulo_desde" : "calendario.titulo_hasta",
                                I18n.lang))
    }

    Row {
        id: filtros
        width: parent.width
        spacing: Escala.px(10)
        z: 10                                  // los desplegables abiertos, encima de la lista
        readonly property real ancho: (width - 3 * spacing) / 4
        Filtro {
            objectName: "filtroDesde"
            width: filtros.ancho
            rotulo: I18n.t("bitacora.desde", I18n.lang)
            valor: control.desde !== "" ? control.desde : I18n.t("bitacora.todos", I18n.lang)
            onPulsado: raiz.abrirCalendario("desde")
        }
        Filtro {
            objectName: "filtroHasta"
            width: filtros.ancho
            rotulo: I18n.t("bitacora.hasta", I18n.lang)
            valor: control.hasta
            onPulsado: raiz.abrirCalendario("hasta")
        }
        Desplegable {
            objectName: "filtroUsuario"
            width: filtros.ancho
            rotulo: I18n.t("bitacora.usuario", I18n.lang)
            tituloLista: I18n.t("bitacora.usuario", I18n.lang)
            prefijoFila: "usuario_"
            opciones: raiz.opcionesUsuario
            valor: control.usuario
            onElegido: (v) => control.fijarUsuario(String(v))
        }
        Desplegable {
            objectName: "filtroTipo"
            width: filtros.ancho
            rotulo: I18n.t("bitacora.tipo_rotulo", I18n.lang)
            tituloLista: I18n.t("bitacora.tipo_rotulo", I18n.lang)
            prefijoFila: "categoria_"
            opciones: raiz.opcionesCategoria
            valor: control.categoria
            onElegido: (v) => control.fijarCategoria(String(v))
        }
    }

    Calendario {
        id: calendario
        objectName: "calendarioBitacora"
        hoy: control.hoy
        onElegida: (fecha) => {
            if (raiz._campoFecha === "desde")
                control.fijarDesde(fecha)
            else if (raiz._campoFecha === "hasta")
                control.fijarHasta(fecha)
            raiz._campoFecha = ""
        }
        onCancelada: raiz._campoFecha = ""
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
                // tipo del evento (bitacora.tipo.<evento>) para lectores de pantalla
                Accessible.description: I18n.t("bitacora.tipo." + fila.modelData.evento, I18n.lang)
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

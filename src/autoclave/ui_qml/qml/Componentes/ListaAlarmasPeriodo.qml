pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// Reportes › Alarmas del periodo (REP-10, DR-H05). Solo dibujo: `alarmas` es
// presentable()["alarmas"] ({total, filas (máx. 8), todas, hay_mas,
// texto_ver_todas, niveles: [{nivel, rotulo, cantidad, fraccion, color}],
// vacia, texto_vacio}). Cada fila muestra el título del catálogo, el nivel
// (rótulo y color de FilaAlarma/IEC 60601-1-8) y la cantidad; una barra
// reparte el total por nivel. «Ver todas» abre un panel con la lista completa
// paginada (`tamPagina` filas). Tocar una fila emite alarmaElegida(fila) (la
// pantalla abre VentanaDetalleAlarma con fila.detalle). Medidas con m().
Item {
    id: raiz
    objectName: "listaAlarmasPeriodo"

    property real escala: 1
    property var alarmas: ({})
    // Ítem sobre el que se abre el panel de «Ver todas» (la pantalla); sin él, esta lista
    property Item capa: null
    property int tamPagina: 8
    property int pagina: 1
    readonly property bool panelAbierto: panel.visible

    signal alarmaElegida(var fila)

    readonly property var _a: (alarmas && typeof alarmas === "object") ? alarmas : ({})
    readonly property var filas: secuencia(_a.filas)
    readonly property var todas: secuencia(_a.todas)
    readonly property var niveles: secuencia(_a.niveles)
    readonly property bool vacia: _a.vacia !== false && filas.length === 0
    readonly property int paginas: Math.max(1, Math.ceil(todas.length / Math.max(1, tamPagina)))
    readonly property real altoFila: m(76)

    function secuencia(v) {
        if (v === undefined || v === null || typeof v === "string" || typeof v.length !== "number") return []
        return Array.prototype.slice.call(v)
    }
    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    function colorTema(clave) {
        var c = Colores[clave]
        return c === undefined ? Colores.alarmaAlta : c
    }
    function abrirTodas() { pagina = 1; panel.visible = true }
    function cerrarTodas() { panel.visible = false }

    implicitHeight: vacia ? m(96) : columna.implicitHeight

    Text {
        objectName: "textoVacioAlarmas"
        visible: raiz.vacia
        anchors.centerIn: parent
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: String(raiz._a.texto_vacio ?? "")
        color: Colores.textoGuia
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
        font.pixelSize: raiz.fuente(24)
    }

    // Una fila de alarma (la usan la lista corta y el panel)
    component FilaPeriodo: Item {
        id: fp
        required property var modelData
        width: parent ? parent.width : 0
        height: Math.max(raiz.altoFila, tituloFila.height + codigoFila.height + raiz.m(24))
        Rectangle {
            x: 0; y: raiz.m(12)
            width: raiz.m(10); height: parent.height - raiz.m(24); radius: raiz.m(3)
            color: raiz.colorTema(fp.modelData.color)
        }
        // el título baja a varias líneas si no cabe (nunca se corta ni se abrevia)
        Text {
            id: tituloFila
            x: raiz.m(28); y: raiz.m(10)
            width: parent.width - x - raiz.m(90)
            wrapMode: Text.WordWrap
            text: String(fp.modelData.titulo ?? "")
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(22)
        }
        Text {
            id: codigoFila
            x: raiz.m(28); y: tituloFila.y + tituloFila.height + raiz.m(2)
            width: parent.width - x - raiz.m(90)
            wrapMode: Text.WordWrap
            text: String(fp.modelData.codigo_visible ?? "") + "  ·  " + String(fp.modelData.nivel_rotulo ?? "")
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: raiz.fuente(18)
        }
        Text {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: raiz.m(80)
            horizontalAlignment: Text.AlignRight
            text: String(fp.modelData.cantidad ?? 0)
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(28)
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width; height: raiz.m(2)
            color: Colores.bordeDivisor
        }
        MouseArea {
            anchors.fill: parent
            onClicked: raiz.alarmaElegida(fp.modelData)
        }
    }

    Column {
        id: columna
        visible: !raiz.vacia
        width: parent.width
        spacing: raiz.m(10)

        // total y reparto por nivel
        Item {
            width: parent.width
            height: raiz.m(60)
            Text {
                objectName: "totalAlarmas"
                anchors.verticalCenter: parent.verticalCenter
                text: String(raiz._a.total ?? 0)
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(44)
            }
            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: raiz.m(14)
                Repeater {
                    model: raiz.niveles
                    Row {
                        id: leyenda
                        required property var modelData
                        visible: (modelData.cantidad ?? 0) > 0
                        spacing: raiz.m(6)
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: raiz.m(14); height: width; radius: width / 2
                            color: raiz.colorTema(leyenda.modelData.color)
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: String(leyenda.modelData.cantidad ?? 0)
                            color: Colores.textoSecundario
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoSemiBold
                            font.pixelSize: raiz.fuente(20)
                        }
                    }
                }
            }
        }
        Row {
            width: parent.width
            height: raiz.m(12)
            Repeater {
                model: raiz.niveles
                Rectangle {
                    required property var modelData
                    width: parent.width * Math.max(0, Math.min(1, modelData.fraccion ?? 0))
                    height: parent.height
                    color: raiz.colorTema(modelData.color)
                }
            }
        }

        Repeater {
            model: raiz.filas
            FilaPeriodo { objectName: "filaAlarmaPeriodo_" + index; required property int index }
        }

        // «Ver todas»
        Item {
            visible: raiz._a.hay_mas === true
            width: parent.width
            height: visible ? raiz.m(64) : 0
            Rectangle {
                objectName: "botonVerTodasAlarmas"
                anchors.centerIn: parent
                width: Math.max(raiz.m(240), textoVer.implicitWidth + raiz.m(56)); height: raiz.m(56)
                radius: height / 2
                color: Colores.fondoSutil
                border.width: raiz.m(2); border.color: Colores.bordeDivisor
                Text {
                    id: textoVer
                    anchors.centerIn: parent
                    text: String(raiz._a.texto_ver_todas ?? "")
                    color: Colores.accionPrimarioTexto
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(22)
                }
                MouseArea { anchors.fill: parent; onClicked: raiz.abrirTodas() }
            }
        }
    }

    // ---- panel con la lista completa, paginada ----
    Item {
        id: panel
        objectName: "panelTodasAlarmas"
        visible: false
        parent: raiz.capa !== null ? raiz.capa : raiz
        anchors.fill: parent
        z: 200

        Rectangle {
            anchors.fill: parent
            color: "#99000000"
            MouseArea { anchors.fill: parent; onClicked: raiz.cerrarTodas() }
        }
        Rectangle {
            id: tarjeta
            anchors.centerIn: parent
            width: Math.min(parent.width - raiz.m(80), raiz.m(1000))
            height: Math.min(parent.height - raiz.m(160), raiz.m(1100))
            radius: raiz.m(24)
            color: Colores.fondoTarjeta
            MouseArea { anchors.fill: parent }

            Text {
                x: raiz.m(36); y: raiz.m(28)
                width: parent.width - raiz.m(72)
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                text: I18n.t("reportes.lista_alarmas_titulo", I18n.lang)
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(32)
            }
            Rectangle {
                x: raiz.m(36); y: raiz.m(84)
                width: parent.width - raiz.m(72); height: raiz.m(2)
                color: Colores.bordeDivisor
            }
            Column {
                id: listaCompleta
                x: raiz.m(36); y: raiz.m(100)
                width: parent.width - raiz.m(72)
                Repeater {
                    model: raiz.todas.slice((raiz.pagina - 1) * raiz.tamPagina, raiz.pagina * raiz.tamPagina)
                    FilaPeriodo { objectName: "filaAlarmaTodas_" + index; required property int index }
                }
            }
            // paginación y cierre
            Item {
                anchors.bottom: parent.bottom; anchors.bottomMargin: raiz.m(28)
                x: raiz.m(36); width: parent.width - raiz.m(72); height: raiz.m(64)
                Rectangle {
                    objectName: "botonPaginaAnteriorAlarmas"
                    visible: raiz.paginas > 1
                    anchors.left: parent.left
                    width: raiz.m(80); height: parent.height; radius: height / 2
                    opacity: raiz.pagina > 1 ? 1 : 0.4
                    color: Colores.fondoSutil
                    border.width: raiz.m(2); border.color: Colores.bordeDivisor
                    Text {
                        anchors.centerIn: parent
                        text: "‹"
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: raiz.fuente(32)
                    }
                    MouseArea { anchors.fill: parent; enabled: raiz.pagina > 1; onClicked: raiz.pagina -= 1 }
                }
                Text {
                    objectName: "textoPaginaAlarmas"
                    visible: raiz.paginas > 1
                    anchors.left: parent.left; anchors.leftMargin: raiz.m(96)
                    anchors.verticalCenter: parent.verticalCenter
                    text: I18n.t("reportes.pagina", I18n.lang)
                          .replace("{n}", String(raiz.pagina)).replace("{total}", String(raiz.paginas))
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: raiz.fuente(22)
                }
                Rectangle {
                    objectName: "botonPaginaSiguienteAlarmas"
                    visible: raiz.paginas > 1
                    anchors.left: parent.left; anchors.leftMargin: raiz.m(96) + raiz.m(220)
                    width: raiz.m(80); height: parent.height; radius: height / 2
                    opacity: raiz.pagina < raiz.paginas ? 1 : 0.4
                    color: Colores.fondoSutil
                    border.width: raiz.m(2); border.color: Colores.bordeDivisor
                    Text {
                        anchors.centerIn: parent
                        text: "›"
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoBold
                        font.pixelSize: raiz.fuente(32)
                    }
                    MouseArea { anchors.fill: parent; enabled: raiz.pagina < raiz.paginas; onClicked: raiz.pagina += 1 }
                }
                Rectangle {
                    objectName: "botonCerrarTodasAlarmas"
                    anchors.right: parent.right
                    width: Math.max(raiz.m(200), textoCerrar.implicitWidth + raiz.m(56)); height: parent.height
                    radius: height / 2
                    color: Colores.accionPrimario
                    Text {
                        id: textoCerrar
                        anchors.centerIn: parent
                        text: I18n.t("acciones.cerrar", I18n.lang)
                        color: "white"
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: raiz.fuente(22)
                    }
                    MouseArea { anchors.fill: parent; onClicked: raiz.cerrarTodas() }
                }
            }
        }
    }
}

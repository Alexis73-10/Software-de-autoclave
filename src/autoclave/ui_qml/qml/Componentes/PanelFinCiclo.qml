pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// FC-01..FC-05 y FC-07 (tanda 21, planeacion_fin_de_ciclo.md): panel de fin de
// ciclo. Ocupa el rectángulo de la tarjeta de la gráfica (mismo radio 30 y
// borde que GraficaCiclo.qml). Autónomo: no lee UiBridge ni el backend; todos
// los textos variables llegan ya traducidos y armados (ola 2, con
// alarmas_i18n). Aquí solo van los rótulos fijos (claves ciclo.*).
//
// De arriba hacia abajo: título («CARGA NO ESTÉRIL», o «OBSERVACIONES DEL
// CICLO» en modo observaciones), subtítulo, botón de contorno «Ver gráfica»
// arriba a la derecha y divisor (fijos); debajo, en un Flickable: la fila de
// causa (FC-02, ausente en modo observaciones), el rótulo «ALARMAS Y AVISOS DEL
// CICLO (N)» y una fila por alarma (FC-03), o «No hubo alarmas ni avisos
// durante el ciclo.». Acordeón (FC-04): una sola fila abierta a la vez; al
// entrar y en cada volverAlPanel() queda abierta la causa (FC-05).
//
// Uso (ola 2):
//   PanelFinCiclo {
//       escala: raiz.m(1)
//       modo: "fallo"                         // fallo | cancelado | emergencia | observaciones
//       subtitulo: "Ciclo 03 terminó en FALLO a las 13:21"
//       causa: ({ titulo: "Fallo en esterilización", subtitulo: "...", hora: "13:21:07",
//                 descripcion: "...", queHacer: "...", meta: "Fase: ... · Código CIC-12" })
//       alarmas: [{ titulo: "...", hora: "13:19:40", nivel: "media",
//                   descripcion: "...", queHacer: "...", meta: "..." }]
//       onVerGraficaPulsado: ...
//   }
Item {
    id: raiz

    property real escala: 1.0
    // "fallo" | "cancelado" | "emergencia" | "observaciones"; cualquier otro
    // valor se trata como "fallo" (falla cerrada, FC-01)
    property string modo: "fallo"
    property string subtitulo: ""
    // {titulo, tituloAbreviado?, subtitulo, hora, descripcion, queHacer, meta, nivel?}
    // nivel: "fallo" (barra roja) | "cancelado" (gris); sin él, sale del modo.
    property var causa: ({})
    // [{titulo, tituloAbreviado?, hora, nivel: "alta"|"media"|"baja", descripcion, queHacer, meta}]
    // en orden cronológico, sin la alarma que ya es la causa (FC-03)
    property var alarmas: []

    // Fila abierta del acordeón: -1 ninguna, 0 la causa, i + 1 la alarma i.
    property int filaAbierta: filaInicial

    signal verGraficaPulsado()

    readonly property string modoEfectivo: ["fallo", "cancelado", "emergencia", "observaciones"].indexOf(modo) >= 0
                                           ? modo : "fallo"
    readonly property bool esObservaciones: modoEfectivo === "observaciones"
    // lista JS o QVariantList del puente; cualquier otra cosa = sin alarmas
    readonly property var _alarmas: alarmas && typeof alarmas === "object" && typeof alarmas.length === "number"
                                    ? alarmas : []
    readonly property var _causa: causa && typeof causa === "object" ? causa : ({})
    // N de la píldora (FC-05): causa + alarmas
    readonly property int cantidad: (esObservaciones ? 0 : 1) + _alarmas.length
    // DECISIÓN SIN CONFIRMAR: en modo observaciones (sin causa) se abre la
    // primera observación, para que su texto se vea al entrar.
    readonly property int filaInicial: esObservaciones ? (_alarmas.length > 0 ? 1 : -1) : 0
    readonly property string nivelCausa: _causa.nivel === "fallo" || _causa.nivel === "cancelado"
                                         ? _causa.nivel
                                         : (modoEfectivo === "cancelado" ? "cancelado" : "fallo")

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }

    // FC-04: tocar una fila cerrada la abre (y cierra la otra); tocar la abierta la cierra
    function alternarFila(i) { filaAbierta = (filaAbierta === i) ? -1 : i }
    // FC-05: cada vez que se vuelve al panel, la causa queda abierta otra vez
    function volverAlPanel() {
        filaAbierta = filaInicial
        desplazable.contentY = 0
    }
    // otro modo (u otra fila inicial: llega la primera observación) = vista nueva;
    // diferido para leer filaInicial ya recalculada
    onModoEfectivoChanged: Qt.callLater(volverAlPanel)
    onFilaInicialChanged: Qt.callLater(volverAlPanel)

    function _texto(v) { return v === undefined || v === null ? "" : String(v) }

    // ======================= tarjeta =======================
    Rectangle {
        objectName: "tarjetaPanelFinCiclo"
        anchors.fill: parent
        radius: raiz.m(30)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2); border.color: "#E5E5E5"   // = GraficaCiclo.paleta.borde
    }

    // ---- cabecera fija ----
    Text {
        id: titulo
        objectName: "tituloPanelFinCiclo"
        x: raiz.m(48); y: raiz.m(36)
        width: botonVerGrafica.x - x - raiz.m(24)
        text: raiz.esObservaciones ? I18n.t("ciclo.fin_titulo_observaciones", I18n.lang)
                                   : I18n.t("ciclo.carga_no_esteril", I18n.lang)
        wrapMode: Text.WordWrap
        color: raiz.esObservaciones ? Colores.advertenciaTexto : Colores.peligroTexto
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(36)
    }
    Text {
        id: subtitulo
        objectName: "subtituloPanelFinCiclo"
        x: titulo.x
        anchors.top: titulo.bottom
        anchors.topMargin: raiz.m(6)
        width: titulo.width
        visible: text !== ""
        text: raiz.subtitulo
        wrapMode: Text.WordWrap
        color: Colores.textoSecundario
        font.family: Tipografia.familia
        font.pixelSize: raiz.fuente(22)
    }

    Rectangle {
        id: botonVerGrafica
        objectName: "botonVerGrafica"
        width: Math.max(raiz.m(199), textoVerGrafica.implicitWidth + raiz.m(48))
        height: raiz.m(66)
        x: raiz.width - raiz.m(40) - width
        y: raiz.m(34)
        radius: raiz.m(8)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2); border.color: Colores.accionPrimario
        Text {
            id: textoVerGrafica
            anchors.centerIn: parent
            text: I18n.t("ciclo.fin_ver_grafica", I18n.lang)
            color: Colores.accionPrimarioTexto
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(24)
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.verGraficaPulsado() }
    }

    Rectangle {
        id: divisor
        objectName: "divisorPanelFinCiclo"
        x: raiz.m(48)
        y: Math.max(subtitulo.visible ? subtitulo.y + subtitulo.height : titulo.y + titulo.height,
                    botonVerGrafica.y + botonVerGrafica.height) + raiz.m(24)
        width: raiz.width - raiz.m(96); height: raiz.m(2)
        color: Colores.bordeDivisor
    }

    // ---- contenido desplazable ----
    Flickable {
        id: desplazable
        objectName: "desplazablePanelFinCiclo"
        x: raiz.m(48)
        y: divisor.y + divisor.height + raiz.m(12)
        width: raiz.width - raiz.m(96)
        height: Math.max(0, raiz.height - y - raiz.m(24))
        contentWidth: width
        contentHeight: columna.height + raiz.m(12)
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Column {
            id: columna
            width: desplazable.width
            spacing: raiz.m(8)

            FilaAcordeon {
                objectName: "filaCausa"
                visible: !raiz.esObservaciones
                width: columna.width
                escala: raiz.escala
                destacada: true
                abierta: raiz.filaAbierta === 0
                nivel: raiz.nivelCausa
                // FC-02: nunca una fila vacía
                titulo: raiz._texto(raiz._causa.titulo) !== "" ? raiz._texto(raiz._causa.titulo)
                                                               : I18n.t("ciclo.fin_causa_generica", I18n.lang)
                tituloAbreviado: raiz._texto(raiz._causa.tituloAbreviado)
                subtitulo: raiz._texto(raiz._causa.subtitulo)
                hora: raiz._texto(raiz._causa.hora)
                descripcion: raiz._texto(raiz._causa.descripcion)
                queHacer: raiz._texto(raiz._causa.queHacer)
                meta: raiz._texto(raiz._causa.meta)
                onPulsada: raiz.alternarFila(0)
            }

            Item { width: 1; height: raiz.m(10); visible: !raiz.esObservaciones }

            Text {
                objectName: "rotuloAlarmasCiclo"
                width: columna.width
                text: raiz._alarmas.length > 0
                      ? I18n.t("ciclo.fin_alarmas_rotulo_n", I18n.lang, { n: raiz._alarmas.length })
                      : I18n.t("ciclo.fin_alarmas_rotulo", I18n.lang)
                wrapMode: Text.WordWrap
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(19)
                font.letterSpacing: raiz.m(1.5)
            }

            Repeater {
                model: raiz._alarmas
                delegate: FilaAcordeon {
                    id: filaAlarma
                    required property var modelData
                    required property int index
                    objectName: "filaAlarmaCiclo_" + index
                    width: columna.width
                    escala: raiz.escala
                    abierta: raiz.filaAbierta === index + 1
                    nivel: raiz._texto(modelData.nivel) !== "" ? raiz._texto(modelData.nivel) : "alta"
                    titulo: raiz._texto(modelData.titulo)
                    tituloAbreviado: raiz._texto(modelData.tituloAbreviado)
                    hora: raiz._texto(modelData.hora)
                    descripcion: raiz._texto(modelData.descripcion)
                    queHacer: raiz._texto(modelData.queHacer)
                    meta: raiz._texto(modelData.meta)
                    onPulsada: raiz.alternarFila(filaAlarma.index + 1)
                }
            }

            Text {
                objectName: "sinAlarmasCiclo"
                visible: raiz._alarmas.length === 0
                width: columna.width
                topPadding: raiz.m(8)
                text: I18n.t("ciclo.fin_sin_alarmas", I18n.lang)
                wrapMode: Text.WordWrap
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(24)
            }
        }
    }
}

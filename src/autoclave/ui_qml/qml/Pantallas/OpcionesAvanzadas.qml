pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Opciones avanzadas (C9, tanda 9, D9-10). Contenedor con dos
// partes:
//   - Manejo de ciclos (técnico e ingeniero, solo fuera de ciclo);
//   - Reasignación de entradas y salidas (R8 de la tanda 8): solo el ingeniero
//     (`puedeReasignar`); el técnico no ve el selector ni la reasignación.
// `segmento` entra en el historial de OPCIONES (D8-4.1, _propiedadesSubnivel).
// DISEÑO PROVISIONAL sin mockup.
Item {
    id: raiz
    objectName: "opcionesAvanzadas"

    property QtObject teclado: null
    property bool puedeReasignar: false
    property string motivoManejo: ""
    property string segmento: "manejo"            // "manejo" | "reasignacion"
    readonly property string segmentoVisible: puedeReasignar ? segmento : "manejo"
    readonly property bool cambiosPendientes: reasignacion.item?.cambiosPendientes ?? false

    // Cambiar de parte con cambios sin guardar en la reasignación pide confirmar
    property string _pendiente: ""
    function elegirSegmento(valor) {
        if (valor === segmentoVisible)
            return
        if (cambiosPendientes) {
            _pendiente = valor
            dialogoCambiar.abrir()
        } else {
            segmento = valor
        }
    }

    Rectangle {
        anchors.fill: parent
        color: Colores.fondoTarjeta
    }

    // Selector propio (dos líneas si el nombre no cabe; SelectorSegmentos no ajusta)
    Row {
        id: selector
        objectName: "selectorOpcionesAvanzadas"
        visible: raiz.puedeReasignar
        width: parent.width
        height: visible ? Escala.px(96) : 0
        Repeater {
            model: [{ valor: "manejo", texto: "manejo_ciclos.segmento_manejo" },
                    { valor: "reasignacion", texto: "manejo_ciclos.segmento_reasignacion" }]
            delegate: Rectangle {
                id: seg
                required property var modelData
                readonly property bool activo: modelData.valor === raiz.segmentoVisible
                objectName: "segmentoAvanzadas_" + modelData.valor
                width: selector.width / 2
                height: selector.height
                radius: Escala.px(8)
                color: activo ? Colores.accionPrimario : Colores.fondoTarjeta
                border.width: activo ? 0 : Escala.px(1)
                border.color: Colores.bordeCampo
                Text {
                    anchors.fill: parent
                    anchors.margins: Escala.px(8)
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                    text: I18n.t(seg.modelData.texto, I18n.lang)
                    color: seg.activo ? "white" : Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                    font.weight: seg.activo ? Tipografia.pesoBold : Tipografia.pesoSemiBold
                }
                MouseArea { anchors.fill: parent; onClicked: raiz.elegirSegmento(seg.modelData.valor) }
            }
        }
    }

    Item {
        id: area
        anchors.top: selector.bottom
        anchors.topMargin: raiz.puedeReasignar ? Escala.px(20) : 0
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom

        Loader {
            id: manejo
            objectName: "cargadorManejoCiclos"
            active: raiz.segmentoVisible === "manejo"
            anchors.fill: parent
            sourceComponent: OpcionesManejoCiclos {
                teclado: raiz.teclado
                motivo: raiz.motivoManejo
            }
        }

        // Solo el ingeniero: el Loader ni siquiera se activa para el técnico
        Loader {
            id: reasignacion
            objectName: "cargadorReasignacion"
            active: raiz.puedeReasignar && raiz.segmentoVisible === "reasignacion"
            anchors.fill: parent
            sourceComponent: OpcionesReasignacion {
                teclado: raiz.teclado
            }
        }
    }

    DialogoConfirmacion {
        id: dialogoCambiar
        objectName: "dialogoCambiarAvanzadas"
        mensaje: I18n.t("opciones.cambiar_seccion_pregunta", I18n.lang)
        textoConfirmar: I18n.t("opciones.cambiar_seccion_confirmar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        onConfirmado: { cerrar(); raiz.segmento = raiz._pendiente; raiz._pendiente = "" }
        onDescartado: raiz._pendiente = ""
    }
}

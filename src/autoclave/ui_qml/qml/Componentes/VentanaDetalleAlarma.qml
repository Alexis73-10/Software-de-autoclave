pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// Tanda 17 (ALM-01), DISEÑO PROVISIONAL sin mockup: ventana emergente con el
// detalle de una alarma, alerta o fallo. Las listas (tarjeta de Preciclo,
// panel de la campana) muestran solo el nombre con el color de nivel; al tocar
// una fila se abre esta ventana con nombre, nivel, código, hora de activación,
// descripción, causa o acción y estado, más las acciones que antes estaban en
// la fila (despejar en COM-02/COM-03; reconocer no existe hoy en la UI) y el
// botón Cerrar. "Confirmar y llevar a estado seguro" NO va aquí: sigue a la
// vista en la tarjeta y en el panel (DECISIÓN SIN CONFIRMAR).
//
// Los datos son una fila de AlarmListModel (roles de bridge/ui_bridge.py); con
// `alarmas` se relee la fila al cambiar el modelo (AlarmListModel.detalle). Si
// la alarma deja de estar en la lista, se conserva lo último leído y el estado
// pasa a "ya no está activa" (sin acciones).
Item {
    id: raiz

    property var alarmas: null                 // AlarmListModel (opcional)
    property var datos: ({})                   // fila vigente
    property bool vigente: true                // sigue en la lista de alarmas
    property bool despejable: false            // COM-02/COM-03 con comandos disponibles
    property string textoDespejar: I18n.t("notificaciones.despejar", I18n.lang)
    property bool abierta: false
    // Tanda 17 (R4, V17-s4-01): motivo del último rechazo de DESPEJAR (clave
    // del catálogo, ComandosSistema.mensajeDespejar); se ve dentro de la
    // ventana (antes solo en el panel de la campana, tapado por ella). Quien
    // la usa lo descarta al recibir `cerrada`.
    property string mensaje: ""
    // ESS-04 (DECISIÓN SIN CONFIRMAR): con el estado seguro detenido por la
    // sonda Principal, el botón de asignar sonda (antes solo en
    // SeccionEstadoSeguro, que en silencio se oculta) también va en el
    // detalle de la alarma del Principal (SEN-02/SEN-03)
    property bool bloqueoPorSonda: false
    readonly property bool asignarSonda: bloqueoPorSonda && vigente
                                         && (datos.codigo === "SEN-02" || datos.codigo === "SEN-03")
    signal asignarSondaPulsado()
    signal despejarPulsado(var model)
    signal cerrada()

    anchors.fill: parent
    z: 300

    function abrir(fila) {
        datos = fila ?? ({})
        vigente = true
        abierta = true
    }
    // Abre con la fila de un delegado (`model`): la del modelo vigente si
    // expone detalle(id) (AlarmListModel); si no, copia los roles conocidos
    function abrirDesde(m) {
        if (!m) return
        if (alarmas && typeof alarmas.detalle === "function") {
            const d = alarmas.detalle(String(m.id))
            if (d && d.id) { abrir(d); return }
        }
        const copia = {}
        for (const k of ["id", "level", "description", "priority", "descripciones", "codigo", "titulo",
                         "titulos", "accion", "acciones", "aparecida", "estado"])
            copia[k] = m[k]
        abrir(copia)
    }
    onVisibleChanged: if (!visible) cerrar()
    // Tanda 17 (R4, V17-s4-02): se cierra cuando la seguridad pasa a urgente
    // (Main.qml irAPanelSeguridad() -> Capas.cerrarTodas())
    Connections {
        target: Capas
        function onCierreSolicitado() { raiz.cerrar() }
    }
    function cerrar() {
        if (!abierta) return
        abierta = false
        cerrada()
    }
    function _releer() {
        if (!abierta || !alarmas || typeof alarmas.detalle !== "function" || !datos.id)
            return
        const d = alarmas.detalle(String(datos.id))
        if (d && d.id) {
            datos = d
            vigente = true
        } else {
            vigente = false
        }
    }
    Connections {
        target: raiz.alarmas
        ignoreUnknownSignals: true
        function onModelReset() { raiz._releer() }
    }

    // ---- textos ----
    function _porIdioma(mapa) { return (mapa ?? {})[I18n.lang] || "" }
    readonly property string sinDato: I18n.t("alarma_detalle.sin_dato", I18n.lang)
    readonly property string nombre: _porIdioma(datos.titulos) || datos.titulo
                                     || _porIdioma(datos.descripciones) || datos.description || datos.id || ""
    function nivelClave(nivel) {
        if (nivel === "FALLA") return "alarma_detalle.nivel_alarma"
        if (nivel === "ALERTA" || nivel === "INFORMATIVO") return "alarma_detalle.nivel_aviso"
        return "alarma_detalle.nivel_emergencia"
    }
    function textoHora(iso) {
        const s = String(iso || "")
        return s === "" ? "" : s.replace("T", " ").substring(0, 19)
    }
    function textoEstado() {
        if (!vigente) return I18n.t("alarma_detalle.estado_retirada", I18n.lang)
        const e = datos.estado || ""
        if (e === "reconocida") return I18n.t("alarma_detalle.estado_reconocida", I18n.lang)
        if (e === "resuelta") return I18n.t("alarma_detalle.estado_resuelta", I18n.lang)
        if (e === "activa") return I18n.t("alarma_detalle.estado_activa", I18n.lang)
        return ""
    }
    readonly property color colorNivel: datos.priority === "media" ? Colores.alarmaMedia
                                      : datos.priority === "baja" ? Colores.alarmaBaja
                                      : Colores.alarmaAlta

    // Abierta, la ventana se muestra sobre toda la ventana de la aplicación
    // (Window.contentItem): el panel de la campana recorta su contenido. Sin
    // ventana (pruebas) se abre en el sitio.
    Item {
        id: capa
        objectName: "capaDetalleAlarma"
        readonly property Item destino: raiz.Window.window ? raiz.Window.window.contentItem : null
        parent: raiz.abierta && destino !== null ? destino : raiz
        x: 0; y: 0
        width: parent ? parent.width : 0
        height: parent ? parent.height : 0
        visible: raiz.abierta
        z: 1000

        Rectangle {
            anchors.fill: parent
            color: "#99000000"
            MouseArea { anchors.fill: parent; onClicked: raiz.cerrar() }
        }

        Rectangle {
            id: tarjeta
            objectName: "tarjetaDetalleAlarma"
            anchors.centerIn: parent
            width: Math.min(parent.width - Escala.px(80), Escala.px(1000))
            height: Math.min(parent.height - Escala.px(120),
                             cabecera.height + contenido.contentHeight + botones.height + Escala.px(120))
            radius: Escala.px(24)
            color: Colores.fondoTarjeta
            MouseArea { anchors.fill: parent }   // no dejar pasar el toque al fondo

            Item {
                id: cabecera
                x: Escala.px(40); y: Escala.px(32)
                width: tarjeta.width - Escala.px(80)
                height: tituloVentana.implicitHeight + Escala.px(20)
                Text {
                    id: tituloVentana
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: I18n.t("alarma_detalle.titulo", I18n.lang)
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.weight: Tipografia.pesoSemiBold
                    font.pixelSize: Escala.fuente(24)
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width; height: Escala.px(2)
                    color: Colores.bordeDivisor
                }
            }

            Flickable {
                id: contenido
                x: Escala.px(40)
                anchors.top: cabecera.bottom; anchors.topMargin: Escala.px(16)
                anchors.bottom: botones.top; anchors.bottomMargin: Escala.px(20)
                width: tarjeta.width - Escala.px(80)
                contentHeight: columna.height
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: columna
                    width: parent.width
                    spacing: Escala.px(14)

                    Row {
                        spacing: Escala.px(16)
                        width: parent.width
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: Escala.px(14); height: Escala.px(48); radius: Escala.px(4)
                            color: raiz.colorNivel
                        }
                        Text {
                            objectName: "nombreDetalleAlarma"
                            width: parent.width - Escala.px(30)
                            wrapMode: Text.WordWrap
                            textFormat: Text.PlainText
                            text: raiz.nombre
                            color: Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoBold
                            font.pixelSize: Escala.fuente(30)
                        }
                    }
                    Campo {
                        objectName: "detalleNivel"
                        rotulo: I18n.t("alarma_detalle.nivel", I18n.lang)
                        valor: raiz.datos.level ? I18n.t(raiz.nivelClave(raiz.datos.level), I18n.lang) : ""
                    }
                    Campo {
                        objectName: "detalleCodigo"
                        rotulo: I18n.t("alarma_detalle.codigo", I18n.lang)
                        valor: raiz.datos.codigo || ""
                    }
                    Campo {
                        objectName: "detalleHora"
                        rotulo: I18n.t("alarma_detalle.hora", I18n.lang)
                        valor: raiz.textoHora(raiz.datos.aparecida)
                    }
                    Campo {
                        objectName: "detalleDescripcion"
                        rotulo: I18n.t("alarma_detalle.descripcion", I18n.lang)
                        valor: raiz._porIdioma(raiz.datos.descripciones) || raiz.datos.description || ""
                    }
                    Campo {
                        objectName: "detalleAccion"
                        rotulo: I18n.t("alarma_detalle.accion", I18n.lang)
                        valor: raiz._porIdioma(raiz.datos.acciones) || raiz.datos.accion || ""
                    }
                    Campo {
                        objectName: "detalleEstado"
                        rotulo: I18n.t("alarma_detalle.estado", I18n.lang)
                        valor: raiz.textoEstado()
                    }
                    Text {
                        objectName: "mensajeDespejarDetalle"
                        width: parent.width
                        visible: raiz.mensaje !== ""
                        wrapMode: Text.WordWrap
                        text: raiz.mensaje !== "" ? I18n.t(raiz.mensaje, I18n.lang) : ""
                        color: Colores.advertenciaTexto
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: Escala.fuente(22)
                    }
                }
            }

            Row {
                id: botones
                anchors.bottom: parent.bottom; anchors.bottomMargin: Escala.px(32)
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: Escala.px(24)
                height: Escala.px(88)
                Boton {
                    objectName: "botonDespejarDetalle"
                    // R4 (V17-s4-03): ya reconocida, no se ofrece despejar
                    visible: raiz.despejable && raiz.vigente && raiz.datos.estado !== "reconocida"
                    texto: raiz.textoDespejar
                    onPulsado: raiz.despejarPulsado(raiz.datos)
                }
                Boton {
                    objectName: "botonAsignarSondaDetalle"
                    visible: raiz.asignarSonda
                    texto: I18n.t("sistema.asignar_sonda_principal", I18n.lang)
                    onPulsado: { raiz.cerrar(); raiz.asignarSondaPulsado() }
                }
                Boton {
                    objectName: "botonCerrarDetalle"
                    texto: I18n.t("alarma_detalle.cerrar", I18n.lang)
                    onPulsado: raiz.cerrar()
                }
            }
        }
    }

    component Campo: Column {
        property string rotulo: ""
        property string valor: ""
        width: parent ? parent.width : 0
        spacing: Escala.px(2)
        Text {
            text: parent.rotulo
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(20)
        }
        Text {
            objectName: "valor"
            width: parent.width
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
            text: parent.valor !== "" ? parent.valor : raiz.sinDato
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(24)
        }
    }

    component Boton: Rectangle {
        id: b
        property string texto: ""
        signal pulsado()
        width: Math.max(Escala.px(300), textoBoton.implicitWidth + Escala.px(48))
        height: Escala.px(88)
        radius: Escala.px(8)
        color: Colores.accionPrimario
        Text {
            id: textoBoton
            anchors.centerIn: parent
            text: b.texto
            color: "white"
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
        }
        MouseArea { anchors.fill: parent; onClicked: b.pulsado() }
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import Autoclave.Unidades
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Parámetros del equipo (O2a, tanda 6; mockups 3, 4 y 5 aprobados).
// Entrada: tarjetas de submenú en 2 columnas (las entrega el backend según el
// perfil, D9-3: Puerta, Cámara segura, Impresión, Drenaje, Empaque, Chaqueta y
// Sistema; sin Puerta ni Empaque con puertas simples) y Configuración de la
// máquina a lo ancho.
// Submenú: filas con nombre, rango y defecto, y valor actual con su unidad;
// cada fila abre la ventana de ajuste (la misma de Parámetros del ciclo).
// Configuración de la máquina: idioma, temperatura y presión con confirmación
// (permisos de la decisión 1.9), serie y modelo en solo lectura.
// Permisos: domain/permisos_opciones (motivo* del controlador); el backend es
// la autoridad (403/409). Valores de presión y temperatura por Unidades.
Item {
    id: raiz
    objectName: "opcionesParametrosEquipo"

    property bool edicionPermitida: false      // estado y rol (OpcionesController)
    property QtObject teclado: null            // PanelTeclado de la ventana
    property string rol: ""
    property string estadoMaquina: ""

    // Puede cambiar parámetros: la sección lo permite y el backend lo aceptaría
    readonly property bool editable: edicionPermitida && control.motivoParametro === ""
    readonly property bool cambiosPendientes: ajuste.cambiado

    ParametrosEquipoController {
        id: control
        objectName: "parametrosEquipoController"
        rol: raiz.rol
        estadoMaquina: raiz.estadoMaquina
    }
    readonly property alias controlador: control
    Component.onCompleted: control.cargar()

    // Atrás: cierra la ventana de ajuste, luego sube del submenú a la entrada
    function retroceder() {
        if (ajuste.visible) {
            if (ajuste.cambiado && ajuste.editable)
                dialogoGuardarAjuste.abrir()
            else
                ajuste.cerrar()
            return true
        }
        return control.volver()
    }

    function nombreGrupo(g) { return I18n.t("opciones.equipo_grupos." + g, I18n.lang) }
    function etiqueta(clave) {
        const k = "parametros_equipo." + clave
        return I18n.existe(k, I18n.lang) ? I18n.t(k, I18n.lang) : clave
    }
    function descripcion(clave) {
        const k = "parametros_equipo_desc." + clave
        return I18n.existe(k, I18n.lang) ? I18n.t(k, I18n.lang) : ""
    }
    function convertible(p) {
        return p !== null && p !== undefined
               && Unidades.unidadIngreso(p.unidad || "", p.clave, p.clase || "", Unidades.version) !== ""
    }
    function textoP(valor, p) {
        if (valor === null || valor === undefined || !p)
            return "—"
        if (convertible(p))
            return Unidades.parametro(valor, p.unidad || "", p.clave, p.clase || "")
        const t = p.tipo === "float" ? Number(valor).toFixed(1) : String(valor)
        return p.unidad ? t + " " + p.unidad : t
    }
    function fechaHora(ts) {
        const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(String(ts || ""))
        return m ? m[3] + "/" + m[2] + "/" + m[1] + " " + m[4] + ":" + m[5] : String(ts || "")
    }
    function textoModificacion(mod) {
        return mod ? I18n.t("opciones.ultima_modificacion", I18n.lang,
                            { usuario: mod.usuario, fecha: fechaHora(mod.fecha) })
                   : I18n.t("opciones.sin_cambios", I18n.lang)
    }
    function textoMotivo() {
        if (!raiz.edicionPermitida || control.motivoParametro === "rol")
            return ""                           // ya lo dice el aviso de OPCIONES
        return control.motivoParametro === "ciclo" ? I18n.t("opciones.equipo_motivo_ciclo", I18n.lang) : ""
    }

    // ---- banda de error ----
    Rectangle {
        id: bandaError
        objectName: "errorParametrosEquipo"
        visible: control.mensaje !== ""
        anchors.top: parent.top
        width: parent.width
        height: visible ? Escala.px(72) : 0
        radius: Escala.px(12)
        color: Colores.peligroFondo
        Text {
            anchors.fill: parent; anchors.margins: Escala.px(16)
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap
            text: control.mensaje !== "" ? I18n.t(control.mensaje, I18n.lang) : ""
            color: Colores.peligroTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }
        MouseArea { anchors.fill: parent; onClicked: control.limpiarMensaje() }
    }

    // ======================= entrada: tarjetas de submenú =======================
    component TarjetaGrupo: Rectangle {
        id: tarjeta
        property string grupo: ""
        objectName: "tarjeta_" + grupo
        height: Escala.px(200)
        radius: Escala.px(18)
        color: Colores.fondoSutil
        border.color: Colores.bordeDivisor
        border.width: Escala.px(1)
        Column {
            anchors.left: parent.left; anchors.right: flecha.left
            anchors.leftMargin: Escala.px(24); anchors.rightMargin: Escala.px(8)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Escala.px(8)
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: raiz.nombreGrupo(tarjeta.grupo)
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(30)
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("opciones.equipo_grupos_desc." + tarjeta.grupo, I18n.lang)
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(20)
            }
        }
        Text {
            id: flecha
            anchors.right: parent.right; anchors.rightMargin: Escala.px(20)
            anchors.verticalCenter: parent.verticalCenter
            text: "›"
            color: Colores.textoGuia
            font.pixelSize: Escala.fuente(44)
        }
        MouseArea { anchors.fill: parent; onClicked: control.abrirGrupo(tarjeta.grupo) }
    }

    Item {
        id: vistaEntrada
        objectName: "vistaEntradaEquipo"
        visible: control.grupo === ""
        anchors.top: bandaError.bottom; anchors.topMargin: Escala.px(8)
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        Column {
            width: parent.width
            spacing: Escala.px(20)
            Text {
                objectName: "guiaParametrosEquipo"
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("opciones.equipo_guia", I18n.lang)
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(22)
            }
            Grid {
                id: rejilla
                columns: 2
                spacing: Escala.px(20)
                width: parent.width
                readonly property real anchoCelda: (width - spacing) / 2
                Repeater {
                    // D9-3 (tanda 9): la lista la entrega el backend, ya filtrada por el
                    // perfil (sin Puerta ni Empaque con puertas simples)
                    model: control.grupos.filter(g => g !== "maquina")
                    delegate: TarjetaGrupo {
                        required property string modelData
                        grupo: modelData
                        width: rejilla.anchoCelda
                    }
                }
            }
            TarjetaGrupo {
                grupo: "maquina"
                width: parent.width
                height: Escala.px(160)
            }
        }
    }

    // ======================= submenú: lista de parámetros =======================
    component Fila: Rectangle {
        id: fila
        property string titulo: ""
        property string subtitulo: ""
        property string valor: ""
        property bool chevron: true
        signal pulsada()
        width: parent ? parent.width : 0
        height: Escala.px(112)
        color: "transparent"
        Column {
            anchors.left: parent.left; anchors.leftMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.6
            Text {
                width: parent.width
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                text: fila.titulo
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(26)
            }
            Text {
                width: parent.width
                visible: text !== ""
                wrapMode: Text.WordWrap
                text: fila.subtitulo
                color: Colores.textoGuia
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(19)
            }
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: Escala.px(fila.chevron ? 52 : 12)
            anchors.verticalCenter: parent.verticalCenter
            horizontalAlignment: Text.AlignRight
            width: parent.width * 0.36
            // D8-5.4: sin recorte; dos líneas o letra menor dentro de la fila
            height: parent.height; verticalAlignment: Text.AlignVCenter
            wrapMode: Text.Wrap
            fontSizeMode: Text.Fit; minimumPixelSize: Escala.fuenteMinima
            text: fila.valor
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(26)
        }
        Text {
            visible: fila.chevron
            anchors.right: parent.right; anchors.rightMargin: Escala.px(16)
            anchors.verticalCenter: parent.verticalCenter
            text: "›"
            color: Colores.textoGuia
            font.pixelSize: Escala.fuente(40)
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width; height: 1
            color: Colores.bordeDivisor
        }
        MouseArea { anchors.fill: parent; enabled: fila.chevron; onClicked: fila.pulsada() }
    }

    Item {
        id: vistaGrupo
        objectName: "vistaGrupoEquipo"
        visible: control.grupo !== "" && control.grupo !== "maquina"
        anchors.top: bandaError.bottom; anchors.topMargin: Escala.px(8)
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom

        Text {
            id: tituloGrupo
            objectName: "tituloGrupoEquipo"
            width: parent.width
            text: control.grupo !== "" ? raiz.nombreGrupo(control.grupo) : ""
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(32)
        }
        Text {
            id: motivoGrupo
            objectName: "motivoGrupoEquipo"
            anchors.top: tituloGrupo.bottom
            width: parent.width
            visible: text !== ""
            wrapMode: Text.WordWrap
            text: raiz.textoMotivo()
            color: Colores.advertenciaTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }
        Column {
            id: listaGrupo
            objectName: "listaParametrosEquipo"
            anchors.top: motivoGrupo.visible ? motivoGrupo.bottom : tituloGrupo.bottom
            anchors.topMargin: Escala.px(12)
            width: parent.width

            // Impresora habilitada (P2, tanda 5): interruptor, en Impresión
            Rectangle {
                id: filaImpresora
                objectName: "filaImpresoraHabilitada"
                visible: control.grupo === "impresion"
                readonly property bool habilitado: raiz.edicionPermitida && control.impresoraConocida
                                                   && control.motivoParametro !== "rol"
                width: parent.width
                height: visible ? Escala.px(110) : 0
                color: "transparent"
                opacity: habilitado ? 1.0 : 0.5
                Column {
                    anchors.left: parent.left; anchors.leftMargin: Escala.px(12)
                    anchors.right: estadoImpresora.left; anchors.rightMargin: Escala.px(16)
                    anchors.verticalCenter: parent.verticalCenter
                    Text {
                        width: parent.width
                        fontSizeMode: Text.HorizontalFit; minimumPixelSize: Escala.fuenteMinima
                        text: I18n.t("opciones.equipo_impresora", I18n.lang)
                        color: Colores.textoPrimario
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(26)
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: I18n.t("opciones.equipo_impresora_ayuda", I18n.lang)
                        color: Colores.textoGuia
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(19)
                    }
                }
                Rectangle {
                    id: interruptor
                    objectName: "interruptorImpresora"
                    readonly property bool encendido: control.impresoraHabilitada
                    anchors.right: parent.right; anchors.rightMargin: Escala.px(16)
                    anchors.verticalCenter: parent.verticalCenter
                    width: Escala.px(112); height: Escala.px(60)
                    radius: height / 2
                    color: encendido ? Colores.accionPrimario : Colores.bordeDivisor
                    Rectangle {
                        width: parent.height - Escala.px(12); height: width
                        radius: width / 2
                        y: Escala.px(6)
                        x: interruptor.encendido ? parent.width - width - Escala.px(6) : Escala.px(6)
                        color: "white"
                    }
                }
                Text {
                    id: estadoImpresora
                    objectName: "estadoImpresora"
                    anchors.right: interruptor.left; anchors.rightMargin: Escala.px(16)
                    anchors.verticalCenter: parent.verticalCenter
                    text: !control.impresoraConocida ? "—"
                          : I18n.t(control.impresoraHabilitada ? "opciones.equipo_si" : "opciones.equipo_no",
                                   I18n.lang)
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(24)
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width; height: 1
                    color: Colores.bordeDivisor
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: filaImpresora.habilitado
                    onClicked: control.fijarImpresora(!control.impresoraHabilitada)
                }
            }

            Repeater {
                // D9-4 (tanda 9): propiedad notificable; se reevalúa al guardar
                model: control.parametrosGrupo
                delegate: Fila {
                    id: filaParametro
                    required property var modelData
                    objectName: "paramEquipo_" + modelData.clave
                    titulo: raiz.etiqueta(modelData.clave)
                    subtitulo: Unidades.version >= 0 && !modelData.solo_lectura
                               ? I18n.t("opciones.equipo_rango_defecto", I18n.lang,
                                        { min: raiz.textoP(modelData.min, modelData),
                                          max: raiz.textoP(modelData.max, modelData),
                                          defecto: raiz.textoP(modelData.defecto, modelData) })
                               : (modelData.ultima_modificacion
                                  ? I18n.t("opciones.equipo_atm_calibrada", I18n.lang,
                                           { fecha: raiz.fechaHora(modelData.ultima_modificacion.fecha),
                                             usuario: modelData.ultima_modificacion.usuario })
                                  : I18n.t("opciones.equipo_atm_sin_calibrar", I18n.lang))
                                 + " · " + I18n.t("opciones.equipo_atm_ayuda", I18n.lang)
                    valor: Unidades.version >= 0 ? raiz.textoP(modelData.valor, modelData) : ""
                    chevron: !modelData.solo_lectura && control.motivoParametro !== "rol"
                    onPulsada: ajuste.abrir(modelData)
                }
            }
        }
    }

    // ======================= Configuración de la máquina =======================
    // Cada cambio pide confirmación; el backend audita y decide (403/409).
    property var _cambioPendiente: null        // {tipo, valor, texto}
    function pedirCambio(tipo, valor, texto) {
        _cambioPendiente = { tipo: tipo, valor: valor, texto: texto }
        dialogoMaquina.abrir()
    }
    function aplicarCambio() {
        const c = _cambioPendiente
        _cambioPendiente = null
        if (!c)
            return
        if (c.tipo === "idioma")
            control.fijarIdioma(c.valor)
        else if (c.tipo === "temperatura")
            control.fijarUnidades(c.valor, control.unidadPresion)
        else if (c.tipo === "presion")
            control.fijarUnidades(control.unidadTemperatura, c.valor)
    }

    component Selector: Column {
        id: sel
        property string rotulo: ""
        property string tipo: ""
        property var opciones: []              // [{v, t}]
        property string elegida: ""
        property string motivo: ""             // "" = habilitado
        property string nota: ""
        width: parent ? parent.width : 0
        spacing: Escala.px(8)
        Text {
            text: sel.rotulo
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: Escala.fuente(26)
        }
        SelectorSegmentos {
            objectName: "selector_" + sel.tipo
            width: parent.width
            habilitado: sel.motivo === "" && sel.elegida !== ""
            valor: sel.opciones.findIndex(o => o.v === sel.elegida)
            opciones: sel.opciones.map((o, i) => ({ valor: i, etiqueta: o.t }))
            onElegido: (i) => {
                if (sel.opciones[i].v !== sel.elegida)
                    raiz.pedirCambio(sel.tipo, sel.opciones[i].v, sel.opciones[i].t)
            }
        }
        Text {
            objectName: "motivo_" + sel.tipo
            visible: text !== ""
            width: parent.width
            wrapMode: Text.WordWrap
            text: sel.motivo !== "" ? sel.motivo : sel.nota
            color: sel.motivo !== "" ? Colores.advertenciaTexto : Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(20)
        }
    }

    component FilaLectura: Rectangle {
        id: lectura
        property string rotulo: ""
        property string valor: ""
        width: parent ? parent.width : 0
        height: Escala.px(84)
        color: "transparent"
        Text {
            anchors.left: parent.left; anchors.leftMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            text: lectura.rotulo
            color: Colores.textoSecundario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(24)
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            text: lectura.valor !== "" ? lectura.valor : "—"
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(26)
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width; height: 1
            color: Colores.bordeDivisor
        }
    }

    Flickable {
        id: vistaMaquina
        objectName: "vistaMaquinaEquipo"
        visible: control.grupo === "maquina"
        anchors.top: bandaError.bottom; anchors.topMargin: Escala.px(8)
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        contentHeight: columnaMaquina.height
        clip: true
        Column {
            id: columnaMaquina
            width: parent.width
            spacing: Escala.px(24)
            Text {
                width: parent.width
                text: raiz.nombreGrupo("maquina")
                color: Colores.textoPrimario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(32)
            }
            Selector {
                objectName: "idiomaEquipo"
                tipo: "idioma"
                rotulo: I18n.t("opciones.equipo_idioma", I18n.lang)
                opciones: [{ v: "es", t: "Español" }, { v: "en", t: "English" }]
                elegida: control.idioma
                motivo: control.motivoIdioma === "rol" ? I18n.t("opciones.equipo_motivo_idioma_rol", I18n.lang) : ""
            }
            Selector {
                objectName: "unidadTemperatura"
                tipo: "temperatura"
                rotulo: I18n.t("opciones.equipo_unidad_temperatura", I18n.lang)
                opciones: [{ v: "C", t: "°C" }, { v: "F", t: "°F" }]
                elegida: control.unidadTemperatura
                motivo: control.motivoUnidades === "rol" ? I18n.t("opciones.equipo_motivo_unidades_rol", I18n.lang)
                        : control.motivoUnidades === "ciclo" ? I18n.t("opciones.equipo_motivo_unidades_ciclo", I18n.lang) : ""
            }
            Selector {
                objectName: "unidadPresion"
                tipo: "presion"
                rotulo: I18n.t("opciones.equipo_unidad_presion", I18n.lang)
                opciones: [{ v: "kPa", t: "kPa" }, { v: "bar", t: "bar" }, { v: "mbar", t: "mbar" },
                           { v: "psi", t: "psi" }]
                elegida: control.unidadPresion
                motivo: control.motivoUnidades === "rol" ? I18n.t("opciones.equipo_motivo_unidades_rol", I18n.lang)
                        : control.motivoUnidades === "ciclo" ? I18n.t("opciones.equipo_motivo_unidades_ciclo", I18n.lang) : ""
                nota: I18n.t("opciones.equipo_presion_nota", I18n.lang)
            }
            Column {
                width: parent.width
                FilaLectura {
                    objectName: "serieEquipo"
                    rotulo: I18n.t("opciones.equipo_serie", I18n.lang)
                    valor: control.numeroSerie
                }
                FilaLectura {
                    objectName: "modeloEquipo"
                    rotulo: I18n.t("opciones.equipo_modelo", I18n.lang)
                    valor: control.modelo
                }
                Text {
                    width: parent.width
                    topPadding: Escala.px(8)
                    wrapMode: Text.WordWrap
                    text: I18n.t("opciones.equipo_perfil_ayuda", I18n.lang)
                    color: Colores.textoGuia
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(20)
                }
            }
        }
    }

    DialogoConfirmacion {
        id: dialogoMaquina
        objectName: "dialogoMaquinaEquipo"
        mensaje: !raiz._cambioPendiente ? ""
                 : raiz._cambioPendiente.tipo === "idioma"
                   ? I18n.t("opciones.equipo_idioma_confirmar", I18n.lang, { opcion: raiz._cambioPendiente.texto })
                   : I18n.t("opciones.equipo_unidades_confirmar", I18n.lang,
                            { magnitud: I18n.t("opciones.equipo_magnitud_" + raiz._cambioPendiente.tipo, I18n.lang),
                              opcion: raiz._cambioPendiente.texto })
        textoConfirmar: I18n.t("acciones.confirmar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        onConfirmado: raiz.aplicarCambio()
        onDescartado: raiz._cambioPendiente = null
    }

    // ======================= ventana de ajuste (igual a Parámetros del ciclo) =======================
    Rectangle {
        id: ajuste
        objectName: "ventanaAjusteEquipo"
        property var param: null
        property var nuevo: null
        property bool restablecer: false        // "Por defecto": POST .../reset
        property string unidadIngreso: ""
        property string errorIngreso: ""
        readonly property var ingresosPsi: param && raiz.convertible(param) && Unidades.presion === "psi"
            ? Unidades.ingresosPsi(param.unidad || "", param.clave, param.min, param.max, param.clase || "") : []
        Connections {
            target: Unidades
            function onCambiado() {
                if (ajuste.visible && ajuste.nuevo !== null && raiz.convertible(ajuste.param)) {
                    ajuste.nuevo = null
                    ajuste.errorIngreso = I18n.t("opciones.err_unidades_cambiaron", I18n.lang)
                }
                if (ajuste.visible && ajuste.param)
                    ajuste.unidadIngreso = Unidades.unidadIngreso(ajuste.param.unidad || "", ajuste.param.clave, ajuste.param.clase || "")
            }
        }
        readonly property bool editable: raiz.editable && param !== null && !param.solo_lectura
        readonly property var valorEnEdicion: nuevo !== null ? nuevo : (param ? param.valor : null)
        readonly property bool cambiado: visible && nuevo !== null && param !== null && nuevo !== param.valor
        function guardar() {
            if (!cambiado)
                return
            const ok = restablecer && nuevo === param.defecto ? control.restablecer(param.clave)
                                                               : control.guardar(param.clave, nuevo)
            if (ok)
                cerrar()
        }
        function abrir(p) {
            param = p; nuevo = null; errorIngreso = ""; restablecer = false
            unidadIngreso = raiz.convertible(p) ? Unidades.unidadIngreso(p.unidad || "", p.clave, p.clase || "") : ""
            if (ingresosPsi.length > 0 && ingresosPsi.indexOf(unidadIngreso) < 0)
                unidadIngreso = ingresosPsi[0]
            visible = true
        }
        function recibir(v) {
            errorIngreso = ""
            restablecer = false
            let interno = Number(v)
            if (raiz.convertible(param)) {
                interno = Unidades.aInterna(Number(v), param.unidad || "", param.clave, unidadIngreso, param.clase || "")
                if (interno === null || interno === undefined || isNaN(interno)) {
                    errorIngreso = I18n.t("opciones.err_conversion", I18n.lang)
                    return
                }
            }
            interno = param.tipo === "float" ? Math.round(interno * 100) / 100 : Math.round(interno)
            if ((param.min !== null && param.min !== undefined && interno < param.min)
                    || (param.max !== null && param.max !== undefined && interno > param.max)) {
                errorIngreso = I18n.t("opciones.rango_permitido", I18n.lang,
                                      { min: raiz.textoP(param.min, param), max: raiz.textoP(param.max, param),
                                        unidad: "" })
                return
            }
            nuevo = interno
        }
        function cerrar() { visible = false; if (raiz.teclado) raiz.teclado.cerrar() }
        visible: false
        anchors.fill: parent
        color: "#80000000"
        MouseArea { anchors.fill: parent }            // modal
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            y: Escala.px(97 + 32 + 16)
            width: parent.width - Escala.px(40)
            height: columnaAjuste.height + Escala.px(72)
            radius: Escala.px(20)
            color: Colores.fondoTarjeta
            Column {
                id: columnaAjuste
                x: Escala.px(24); y: Escala.px(24)
                width: parent.width - Escala.px(48)
                spacing: Escala.px(18)
                Text {
                    text: ajuste.param ? raiz.etiqueta(ajuste.param.clave) : ""
                    font.family: Tipografia.familia; font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(30)
                    color: Colores.textoPrimario
                }
                Text {
                    text: I18n.t("opciones.secciones.parametros_sistema", I18n.lang).replace(/\n/g, " ")
                          + " · " + (ajuste.param ? raiz.nombreGrupo(ajuste.param.grupo) : "")
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                    color: Colores.textoGuia
                }
                Row {
                    spacing: Escala.px(10)
                    Repeater {
                        model: ajuste.param ? [
                            { clave: "opciones.actual", valor: raiz.textoP(ajuste.param.valor, ajuste.param), toque: false },
                            { clave: "opciones.por_defecto", valor: raiz.textoP(ajuste.param.defecto, ajuste.param),
                              toque: ajuste.param.defecto !== null && ajuste.param.defecto !== ajuste.param.valor },
                            { clave: "opciones.minimo", valor: raiz.textoP(ajuste.param.min, ajuste.param), toque: false },
                            { clave: "opciones.maximo", valor: raiz.textoP(ajuste.param.max, ajuste.param), toque: false }
                        ] : []
                        delegate: Rectangle {
                            id: tarjetaValor
                            required property var modelData
                            width: (columnaAjuste.width - Escala.px(30)) / 4
                            height: Escala.px(110)
                            radius: Escala.px(12)
                            color: Colores.fondoSutil
                            border.color: modelData.toque && ajuste.editable ? Colores.accionPrimario : "transparent"
                            border.width: Escala.px(2)
                            Column {
                                anchors.centerIn: parent
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: I18n.t(tarjetaValor.modelData.clave, I18n.lang)
                                    font.family: Tipografia.familia
                                    font.pixelSize: Escala.fuente(18)
                                    color: Colores.textoGuia
                                }
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    text: tarjetaValor.modelData.valor
                                    font.family: Tipografia.familia; font.weight: Tipografia.pesoBold
                                    font.pixelSize: Escala.fuente(26)
                                    color: Colores.textoPrimario
                                }
                            }
                            MouseArea {
                                anchors.fill: parent
                                enabled: tarjetaValor.modelData.toque && ajuste.editable
                                onClicked: { ajuste.nuevo = ajuste.param.defecto; ajuste.restablecer = true }
                            }
                        }
                    }
                }
                Rectangle {
                    objectName: "campoNuevoValorEquipo"
                    width: parent.width
                    height: Escala.px(88)
                    radius: Escala.px(12)
                    border.color: Colores.bordeCampo
                    border.width: Escala.px(2)
                    opacity: ajuste.editable ? 1 : 0.4
                    Text {
                        anchors.fill: parent; anchors.leftMargin: Escala.px(20)
                        verticalAlignment: Text.AlignVCenter
                        text: ajuste.nuevo !== null ? raiz.textoP(ajuste.nuevo, ajuste.param)
                                                    : I18n.t("opciones.toque_nuevo_valor", I18n.lang)
                        color: ajuste.nuevo !== null ? Colores.textoPrimario : Colores.textoGuia
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(26)
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: ajuste.editable && raiz.teclado !== null
                        onClicked: raiz.convertible(ajuste.param)
                            ? raiz.teclado.abrirNumerico(
                                raiz.etiqueta(ajuste.param.clave),
                                Unidades.simboloIngreso(ajuste.unidadIngreso),
                                Unidades.aMostrarEn(ajuste.valorEnEdicion, ajuste.param.unidad || "", ajuste.param.clave,
                                                    ajuste.unidadIngreso, ajuste.param.clase || ""),
                                -1e9, 1e9, 2, (v) => ajuste.recibir(v))
                            : raiz.teclado.abrirNumerico(
                                raiz.etiqueta(ajuste.param.clave), ajuste.param.unidad,
                                ajuste.valorEnEdicion, ajuste.param.min, ajuste.param.max,
                                ajuste.param.tipo === "float" ? 1 : 0, (v) => ajuste.recibir(v))
                    }
                }
                Row {
                    objectName: "selectorIngresoPsiEquipo"
                    visible: ajuste.ingresosPsi.length > 1
                    spacing: Escala.px(10)
                    Repeater {
                        model: ajuste.ingresosPsi
                        delegate: BotonFormulario {
                            required property var modelData
                            texto: String(modelData)
                            primario: ajuste.unidadIngreso === modelData
                            onPulsado: ajuste.unidadIngreso = modelData
                        }
                    }
                }
                Text {
                    objectName: "errorIngresoEquipo"
                    visible: ajuste.errorIngreso !== ""
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: ajuste.errorIngreso
                    color: Colores.peligroTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                }
                Text {
                    visible: ajuste.param !== null
                    text: ajuste.param ? I18n.t("opciones.rango_permitido", I18n.lang,
                                                { min: raiz.textoP(ajuste.param.min, ajuste.param),
                                                  max: raiz.textoP(ajuste.param.max, ajuste.param),
                                                  unidad: "" }) : ""
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(20)
                    color: Colores.textoGuia
                }
                Rectangle { width: parent.width; height: 1; color: Colores.bordeDivisor }
                Text {
                    objectName: "descripcionAjusteEquipo"
                    visible: text !== ""
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: ajuste.param ? raiz.descripcion(ajuste.param.clave) : ""
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                    color: Colores.textoPrimario
                }
                Text {
                    objectName: "modificacionAjusteEquipo"
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: raiz.textoModificacion(ajuste.param ? ajuste.param.ultima_modificacion : null)
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(20)
                    color: Colores.textoSecundario
                }
            }
        }
    }

    // Cancelar / Por defecto / Guardar: franja superior (el teclado sube desde abajo)
    Rectangle {
        id: accionesAjuste
        objectName: "accionesAjusteEquipo"
        visible: ajuste.visible
        z: 5
        anchors.left: parent.left; anchors.right: parent.right
        anchors.top: parent.top
        height: Escala.px(97 + 32)
        color: Colores.fondoTarjeta
        Row {
            anchors.centerIn: parent
            spacing: Escala.px(16)
            readonly property real anchoBoton: (accionesAjuste.width - Escala.px(40) - 2 * spacing) / 3
            BotonFormulario {
                objectName: "cancelarAjusteEquipo"
                width: parent.anchoBoton
                texto: I18n.t("acciones.cancelar", I18n.lang)
                onPulsado: ajuste.cerrar()
            }
            BotonFormulario {
                objectName: "defectoAjusteEquipo"
                width: parent.anchoBoton
                texto: I18n.t("opciones.por_defecto", I18n.lang)
                habilitado: ajuste.editable && ajuste.param !== null && ajuste.param.defecto !== null
                            && ajuste.param.defecto !== undefined && ajuste.valorEnEdicion !== ajuste.param.defecto
                onPulsado: { ajuste.nuevo = ajuste.param.defecto; ajuste.restablecer = true }
            }
            BotonFormulario {
                objectName: "guardarAjusteEquipo"
                width: parent.anchoBoton
                texto: I18n.t("acciones.guardar", I18n.lang)
                primario: true
                habilitado: ajuste.editable && ajuste.cambiado
                onPulsado: ajuste.guardar()
            }
        }
    }

    DialogoConfirmacion {
        id: dialogoGuardarAjuste
        objectName: "dialogoGuardarAjusteEquipo"
        mensaje: I18n.t("opciones.guardar_parametro_pregunta", I18n.lang)
        textoConfirmar: I18n.t("acciones.guardar", I18n.lang)
        textoCancelar: I18n.t("opciones.descartar_cambios", I18n.lang)
        onConfirmado: ajuste.guardar()
        onDescartado: ajuste.cerrar()
    }
}

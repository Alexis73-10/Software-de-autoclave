pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n

// OPCIONES › Parámetros del ciclo, Fases 2 a 4 (planeacion_opciones_parametros_ciclo.md
// rev. 3.1 §5.1 a §5.5; tanda 2026-10-14 T12). PROVISIONAL (sin diseño final):
// vive en la zona de contenido de OPCIONES con tres vistas:
//   - "programa": selector de programa, secciones (con "No se ejecuta", Q-2) y
//     fila de sensores de temperatura;
//   - "seccion": parámetros de la sección (asterisco si difieren del valor por
//     defecto; descompresión solo con el modo activo, Q-3) y ventana de ajuste
//     (actual, por defecto, mínimo y máximo; teclado numérico; interruptor para
//     booleanos, opciones para enumerados, U-17);
//   - "sensores": roles Principal / Referencia / No en uso (§5.5, sin
//     advertencia de sonda fría).
// La validación final es del backend; aquí solo se anticipa (§4.2).
Item {
    id: raiz
    objectName: "parametrosCiclo"

    property QtObject teclado: null
    property bool edicionPermitida: false      // estado y rol (OpcionesController)
    property string vista: "programa"          // programa | seccion | sensores
    // cambios sin guardar (roles de sensor): OPCIONES confirma antes de salir
    readonly property bool cambiosPendientes: vista === "sensores" && _sensoresModificados

    ParametrosCicloController {
        id: control
        objectName: "parametrosCicloController"
    }
    readonly property alias controlador: control
    Component.onCompleted: control.cargar()

    function nombreSeccion(clave) {
        const k = "opciones.secciones_programa." + clave
        return I18n.existe(k, I18n.lang) ? I18n.t(k, I18n.lang) : clave
    }
    function etiqueta(seccion, clave) {
        const k = "parametros." + seccion + "." + clave
        if (I18n.existe(k, I18n.lang))
            return I18n.t(k, I18n.lang)
        // PROVISIONAL: sin etiqueta en el catálogo, la clave legible
        const t = clave.split(".").pop().replace(/_/g, " ")
        return t.charAt(0).toUpperCase() + t.slice(1)
    }
    function texto(valor, tipo) {
        if (valor === null || valor === undefined)
            return "—"
        if (tipo === "bool")
            return I18n.t(valor ? "opciones.si" : "opciones.no", I18n.lang)
        if (tipo === "enum")
            return I18n.existe("opciones.valor_" + valor, I18n.lang)
                   ? I18n.t("opciones.valor_" + valor, I18n.lang) : String(valor)
        if (tipo === "float")
            return Number(valor).toFixed(1)
        return String(valor)
    }
    function mensajeError() {
        if (control.mensaje === "")
            return ""
        return I18n.t(control.mensaje, I18n.lang,
                      { valor: control.detalleMensaje.valor ?? "—" })
    }

    component Fila: Rectangle {
        id: fila
        property string titulo: ""
        property string valor: ""
        property string detalle: ""
        property bool marca: false
        property bool chevron: true
        signal pulsada()
        width: parent ? parent.width : 0
        height: Escala.px(92)
        color: "transparent"
        Text {
            anchors.left: parent.left; anchors.leftMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width * 0.55
            elide: Text.ElideRight
            text: fila.titulo + (fila.marca ? " *" : "")
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(26)
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: Escala.px(fila.chevron ? 52 : 12)
            anchors.verticalCenter: parent.verticalCenter
            horizontalAlignment: Text.AlignRight
            width: parent.width * 0.4
            elide: Text.ElideLeft
            textFormat: Text.StyledText
            text: "<b>" + fila.valor + "</b>" + (fila.detalle !== "" ? " <font color='#808080'>" + fila.detalle + "</font>" : "")
            color: Colores.textoPrimario
            font.family: Tipografia.familia
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
        MouseArea { anchors.fill: parent; onClicked: fila.pulsada() }
    }

    // Mensaje del último error (§5.4)
    Rectangle {
        id: bandaError
        objectName: "errorParametros"
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
            text: raiz.mensajeError()
            color: Colores.peligroTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }
        MouseArea { anchors.fill: parent; onClicked: control.limpiarMensaje() }
    }

    // ======================= vista: programa (§5.1) =======================
    Flickable {
        objectName: "vistaPrograma"
        visible: raiz.vista === "programa"
        anchors.top: bandaError.bottom; anchors.topMargin: Escala.px(8)
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        contentHeight: columnaPrograma.height
        clip: true
        Column {
            id: columnaPrograma
            width: parent.width
            spacing: Escala.px(6)
            // Selector de programa: "03 · Nombre"
            Flow {
                width: parent.width
                spacing: Escala.px(10)
                Repeater {
                    model: control.programas
                    delegate: Rectangle {
                        id: chip
                        required property var modelData
                        readonly property bool activo: modelData.numero === control.numero
                        objectName: "programa_" + modelData.numero
                        width: textoChip.implicitWidth + Escala.px(40)
                        height: Escala.px(72)
                        radius: Escala.px(36)
                        color: activo ? Colores.accionPrimario : Colores.fondoSutil
                        Text {
                            id: textoChip
                            anchors.centerIn: parent
                            text: String(chip.modelData.numero).padStart(2, "0") + " · " + chip.modelData.nombre
                                  + (chip.modelData.danado ? " ⚠" : "")
                            color: chip.activo ? "white" : Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.weight: Tipografia.pesoSemiBold
                            font.pixelSize: Escala.fuente(24)
                        }
                        MouseArea { anchors.fill: parent; onClicked: control.elegirPrograma(chip.modelData.numero) }
                    }
                }
            }
            Text {
                objectName: "programaSoloLectura"
                visible: control.numero > 0 && !control.programaEditable
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("opciones.programa_no_editable", I18n.lang)
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(22)
            }
            Repeater {
                model: control.secciones
                delegate: Fila {
                    required property var modelData
                    objectName: "seccion_" + modelData.clave
                    titulo: raiz.nombreSeccion(modelData.clave)
                    valor: modelData.no_se_ejecuta ? I18n.t("opciones.no_se_ejecuta", I18n.lang) : ""
                    onPulsada: { control.abrirSeccion(modelData.clave); raiz.vista = "seccion" }
                }
            }
            Rectangle { width: parent.width; height: Escala.px(2); color: Colores.bordeCampo }
            Fila {
                objectName: "filaSensores"
                titulo: I18n.t("opciones.sensores_titulo", I18n.lang)
                onPulsada: { control.cargarSensores(); raiz._prepararSensores(); raiz.vista = "sensores" }
            }
        }
    }

    // ======================= vista: sección (§5.2) =======================
    Item {
        objectName: "vistaSeccion"
        visible: raiz.vista === "seccion"
        anchors.top: bandaError.bottom; anchors.topMargin: Escala.px(8)
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        Row {
            id: encabezadoSeccion
            spacing: Escala.px(16)
            Text {
                objectName: "volverSeccion"
                text: "‹"
                font.pixelSize: Escala.fuente(56)
                color: Colores.accionPrimarioTexto
                MouseArea { anchors.fill: parent; anchors.margins: -Escala.px(20); onClicked: raiz.vista = "programa" }
            }
            Column {
                Text {
                    text: raiz.nombreSeccion(control.seccion)
                    font.family: Tipografia.familia; font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(32)
                    color: Colores.textoPrimario
                }
                Text {
                    text: I18n.t("opciones.secciones.parametros_ciclo", I18n.lang) + " · "
                          + String(control.numero).padStart(2, "0") + " " + control.nombrePrograma
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                    color: Colores.textoGuia
                }
            }
        }
        ListView {
            objectName: "listaParametros"
            anchors.top: encabezadoSeccion.bottom; anchors.topMargin: Escala.px(12)
            anchors.left: parent.left; anchors.right: parent.right
            anchors.bottom: pieSeccion.top
            clip: true
            model: control.parametros
            delegate: Fila {
                required property var modelData
                objectName: "param_" + modelData.clave
                width: ListView.view.width
                titulo: raiz.etiqueta(control.seccion, modelData.clave)
                valor: raiz.texto(modelData.valor, modelData.tipo)
                detalle: modelData.tipo === "bool" || modelData.tipo === "enum" ? "" : (modelData.unidad || "")
                marca: modelData.modificado
                onPulsada: ajuste.abrir(modelData)
            }
        }
        Text {
            id: pieSeccion
            anchors.bottom: parent.bottom
            width: parent.width
            wrapMode: Text.WordWrap
            text: I18n.t("opciones.leyenda_defecto", I18n.lang)
            color: Colores.textoGuia
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(20)
        }
    }

    // ======================= vista: sensores (§5.5) =======================
    property var _roles: ({})          // asignación en edición
    readonly property bool _sensoresModificados: JSON.stringify(_roles) !== JSON.stringify(control.asignacion)
    function _prepararSensores() { _roles = Object.assign({}, control.asignacion) }
    Connections {
        target: control
        function onSensoresChanged() { raiz._prepararSensores() }
    }
    function _conteo(rol) { return Object.keys(_roles).filter(s => _roles[s] === rol).length }
    function _asignar(sensor, rol) {
        const r = Object.assign({}, _roles)
        if (rol === "principal")
            for (const s in r) if (r[s] === "principal") r[s] = "no_en_uso"    // el anterior pasa a No en uso
        r[sensor] = rol
        _roles = r
    }
    readonly property bool _rolesValidos: _conteo("principal") === 1 && _conteo("referencia") <= 2

    Item {
        objectName: "vistaSensores"
        visible: raiz.vista === "sensores"
        anchors.top: bandaError.bottom; anchors.topMargin: Escala.px(8)
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        Row {
            id: encabezadoSensores
            spacing: Escala.px(16)
            Text {
                objectName: "volverSensores"
                text: "‹"
                font.pixelSize: Escala.fuente(56)
                color: Colores.accionPrimarioTexto
                MouseArea { anchors.fill: parent; anchors.margins: -Escala.px(20); onClicked: raiz.vista = "programa" }
            }
            Column {
                Text {
                    text: I18n.t("opciones.sensores_titulo", I18n.lang).toUpperCase()
                    font.family: Tipografia.familia; font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(30)
                    color: Colores.textoPrimario
                }
                Text {
                    text: I18n.t("opciones.sensores_instruccion", I18n.lang)
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                    color: Colores.textoGuia
                }
            }
        }
        Column {
            id: listaSensores
            anchors.top: encabezadoSensores.bottom; anchors.topMargin: Escala.px(16)
            width: parent.width
            spacing: Escala.px(14)
            Repeater {
                model: control.sensores
                delegate: Rectangle {
                    id: tarjeta
                    required property var modelData
                    readonly property string rol: raiz._roles[modelData.id] ?? "no_en_uso"
                    readonly property bool conSenal: modelData.estado === "disponible"
                    readonly property bool editable: control.sensoresEditable && raiz.edicionPermitida
                    objectName: "sensor_" + modelData.id
                    width: parent.width
                    height: Escala.px(170)
                    radius: Escala.px(14)
                    color: Colores.fondoSutil
                    border.color: rol !== (control.asignacion[modelData.id] ?? "no_en_uso") ? Colores.advertencia : "transparent"
                    border.width: Escala.px(2)
                    Text {
                        x: Escala.px(20); y: Escala.px(14)
                        text: tarjeta.modelData.nombre + "  ·  "
                              + (tarjeta.modelData.lectura !== null && tarjeta.modelData.lectura !== undefined
                                 ? Number(tarjeta.modelData.lectura).toFixed(1) + " °C"
                                 : I18n.t("opciones.sensor_sin_senal", I18n.lang))
                        font.family: Tipografia.familia; font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: Escala.fuente(26)
                        color: Colores.textoPrimario
                    }
                    SelectorSegmentos {
                        x: Escala.px(20); y: Escala.px(70)
                        width: parent.width - Escala.px(40)
                        habilitado: tarjeta.editable
                        valor: ["principal", "referencia", "no_en_uso"].indexOf(tarjeta.rol)
                        // reglas de §5.5: el Principal no se puede quitar directamente;
                        // Referencia hasta 2; un sensor sin señal solo admite No en uso
                        opciones: [
                            { valor: 0, etiqueta: I18n.t("sensores_ciclo.rol_principal", I18n.lang),
                              habilitada: tarjeta.conSenal },
                            { valor: 1, etiqueta: I18n.t("sensores_ciclo.rol_referencia", I18n.lang),
                              habilitada: tarjeta.conSenal && tarjeta.rol !== "principal"
                                          && (tarjeta.rol === "referencia" || raiz._conteo("referencia") < 2) },
                            { valor: 2, etiqueta: I18n.t("sensores_ciclo.rol_no_en_uso", I18n.lang),
                              habilitada: tarjeta.rol !== "principal" }
                        ]
                        onElegido: (v) => raiz._asignar(tarjeta.modelData.id, ["principal", "referencia", "no_en_uso"][v])
                    }
                }
            }
            Text {
                text: I18n.t("opciones.sensores_conteo", I18n.lang,
                             { principal: raiz._conteo("principal"), referencia: raiz._conteo("referencia") })
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(22)
                color: Colores.textoSecundario
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("opciones.sensores_nota", I18n.lang)
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(20)
                color: Colores.textoGuia
            }
        }
        BotonFormulario {
            objectName: "guardarSensores"
            anchors.bottom: parent.bottom
            anchors.right: parent.right
            texto: I18n.t("acciones.guardar", I18n.lang)
            primario: true
            habilitado: raiz._sensoresModificados && raiz._rolesValidos && control.sensoresEditable && raiz.edicionPermitida
            onPulsado: if (habilitado) control.guardarSensores(raiz._roles)
        }
    }

    // ======================= ventana de ajuste (§5.3) =======================
    Rectangle {
        id: ajuste
        objectName: "ventanaAjuste"
        property var param: null
        property var nuevo: null
        readonly property bool editable: control.seccionEditable && raiz.edicionPermitida
        function abrir(p) { param = p; nuevo = null; visible = true }
        function cerrar() { visible = false; if (raiz.teclado) raiz.teclado.cerrar() }
        visible: false
        anchors.fill: parent
        color: "#80000000"
        MouseArea { anchors.fill: parent }            // modal
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            y: Escala.px(40)
            width: parent.width - Escala.px(40)
            height: columnaAjuste.height + Escala.px(48)
            radius: Escala.px(20)
            color: Colores.fondoTarjeta
            Column {
                id: columnaAjuste
                x: Escala.px(24); y: Escala.px(24)
                width: parent.width - Escala.px(48)
                spacing: Escala.px(14)
                Text {
                    text: ajuste.param ? raiz.etiqueta(control.seccion, ajuste.param.clave) : ""
                    font.family: Tipografia.familia; font.weight: Tipografia.pesoBold
                    font.pixelSize: Escala.fuente(30)
                    color: Colores.textoPrimario
                }
                Text {
                    text: raiz.nombreSeccion(control.seccion) + " · " + control.nombrePrograma
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                    color: Colores.textoGuia
                }
                Row {
                    spacing: Escala.px(10)
                    Repeater {
                        model: ajuste.param ? [
                            { clave: "opciones.actual", valor: raiz.texto(ajuste.param.valor, ajuste.param.tipo), toque: false },
                            { clave: "opciones.por_defecto", valor: raiz.texto(ajuste.param.defecto, ajuste.param.tipo),
                              toque: ajuste.param.defecto !== null && ajuste.param.defecto !== ajuste.param.valor },
                            { clave: "opciones.minimo", valor: raiz.texto(ajuste.param.min, ajuste.param.tipo), toque: false },
                            { clave: "opciones.maximo", valor: raiz.texto(ajuste.param.max, ajuste.param.tipo), toque: false }
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
                                onClicked: ajuste.nuevo = ajuste.param.defecto
                            }
                        }
                    }
                }
                Text {
                    text: ajuste.param && ajuste.param.ultima_modificacion
                          ? I18n.t("opciones.ultima_modificacion", I18n.lang,
                                   { usuario: ajuste.param.ultima_modificacion.usuario,
                                     fecha: ajuste.param.ultima_modificacion.ts })
                          : I18n.t("opciones.sin_cambios", I18n.lang)
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(20)
                    color: Colores.textoSecundario
                }
                // Nuevo valor: numérico con el teclado; booleano y enumerado con opciones (U-17)
                Rectangle {
                    objectName: "campoNuevoValor"
                    visible: ajuste.param !== null && ajuste.param.tipo !== "bool" && ajuste.param.tipo !== "enum"
                    width: parent.width
                    height: Escala.px(88)
                    radius: Escala.px(12)
                    border.color: Colores.bordeCampo
                    border.width: Escala.px(2)
                    opacity: ajuste.editable ? 1 : 0.4
                    Text {
                        anchors.fill: parent; anchors.leftMargin: Escala.px(20)
                        verticalAlignment: Text.AlignVCenter
                        text: ajuste.nuevo !== null
                              ? raiz.texto(ajuste.nuevo, ajuste.param ? ajuste.param.tipo : "") + " " + (ajuste.param ? ajuste.param.unidad : "")
                              : I18n.t("opciones.toque_nuevo_valor", I18n.lang)
                        color: ajuste.nuevo !== null ? Colores.textoPrimario : Colores.textoGuia
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(26)
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: ajuste.editable && raiz.teclado !== null
                        onClicked: raiz.teclado.abrirNumerico(
                            raiz.etiqueta(control.seccion, ajuste.param.clave), ajuste.param.unidad,
                            ajuste.nuevo !== null ? ajuste.nuevo : ajuste.param.valor,
                            ajuste.param.min, ajuste.param.max,
                            ajuste.param.tipo === "float" ? 1 : 0,
                            (v) => { ajuste.nuevo = ajuste.param.tipo === "float" ? Number(v) : Math.round(Number(v)) })
                    }
                }
                SelectorSegmentos {
                    objectName: "selectorNuevoValor"
                    visible: ajuste.param !== null && (ajuste.param.tipo === "bool" || ajuste.param.tipo === "enum")
                    width: parent.width
                    habilitado: ajuste.editable
                    readonly property var valores: !ajuste.param ? [] : ajuste.param.tipo === "bool" ? [true, false] : ajuste.param.opciones
                    valor: valores.indexOf(ajuste.nuevo !== null ? ajuste.nuevo : (ajuste.param ? ajuste.param.valor : null))
                    opciones: valores.map((v, i) => ({ valor: i, etiqueta: raiz.texto(v, ajuste.param.tipo) }))
                    onElegido: (i) => ajuste.nuevo = valores[i]
                }
                Text {
                    visible: ajuste.param !== null && ajuste.param.tipo !== "bool" && ajuste.param.tipo !== "enum"
                    text: ajuste.param ? I18n.t("opciones.rango_permitido", I18n.lang,
                                                { min: raiz.texto(ajuste.param.min, ajuste.param.tipo),
                                                  max: raiz.texto(ajuste.param.max, ajuste.param.tipo),
                                                  unidad: ajuste.param.unidad || "" }) : ""
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(20)
                    color: Colores.textoGuia
                }
                Row {
                    anchors.right: parent.right
                    spacing: Escala.px(16)
                    BotonFormulario {
                        objectName: "cancelarAjuste"
                        texto: I18n.t("acciones.cancelar", I18n.lang)
                        onPulsado: ajuste.cerrar()
                    }
                    BotonFormulario {
                        objectName: "guardarAjuste"
                        texto: I18n.t("acciones.guardar", I18n.lang)
                        primario: true
                        habilitado: ajuste.editable && ajuste.nuevo !== null && ajuste.param !== null
                                    && ajuste.nuevo !== ajuste.param.valor
                        onPulsado: { if (habilitado && control.guardar(ajuste.param.clave, ajuste.nuevo)) ajuste.cerrar() }
                    }
                }
            }
        }
    }
}

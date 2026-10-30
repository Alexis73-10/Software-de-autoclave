pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import "../Componentes"
import Autoclave.I18n
import Autoclave.Unidades

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
    property string vista: "programa"          // programa | seccion | sensores | entradas
    // Atrás de la barra inferior: sube un nivel dentro de la sección; false si ya
    // está en la lista de programas (la pantalla Opciones entonces sale)
    function retroceder() {
        // primero cierra la ventana de ajuste; con el valor editado pregunta
        if (ajuste.visible) {
            if (ajuste.cambiado && ajuste.editable)
                dialogoGuardarAjuste.abrir()
            else
                ajuste.cerrar()
            return true
        }
        if (vista === "programa")
            return false
        vista = "programa"
        return true
    }
    // cambios sin guardar (roles de sensor): OPCIONES confirma antes de salir
    // O11: también las entradas mostradas elegidas por fila y sin guardar
    readonly property bool cambiosPendientes: (vista === "sensores" && _sensoresModificados)
                                              || (vista === "entradas" && _entradasModificadas)
                                              || ajuste.cambiado

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
    // U1 (tanda 5): un parámetro en °C o kPa se muestra y se teclea en las
    // unidades elegidas (Unidades); el backend sigue recibiendo °C / kPa abs.
    function convertible(p) {
        return p !== null && p !== undefined && p.tipo !== "bool" && p.tipo !== "enum"
               && Unidades.unidadIngreso(p.unidad || "", p.clave, p.clase || "", Unidades.version) !== ""
    }
    function textoP(valor, p) {
        if (convertible(p))
            return valor === null || valor === undefined ? "—"
                 : Unidades.parametro(valor, p.unidad || "", p.clave, p.clase || "")
        return texto(valor, p ? p.tipo : "")
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
    // Descripción corta del parámetro (catálogo parametros_desc.<sección>.<clave>)
    function descripcion(seccion, clave) {
        const k = "parametros_desc." + seccion + "." + clave
        return I18n.existe(k, I18n.lang) ? I18n.t(k, I18n.lang) : ""
    }
    // D8-5.8: un parámetro "modo" (secado, descompresión o cualquiera con
    // lista de modos del backend) se elige de una lista, no se escribe
    function esModoDescompresion(seccion, clave) { return seccion === "descompresion" && clave === "modo" }
    function esModo(seccion, p) {
        return p !== null && p !== undefined
               && ((p.modos && p.modos.length > 0) || esModoDescompresion(seccion, p.clave))
    }
    function nombreModo(n, seccion) {
        const s = seccion || "descompresion"
        const k = s === "descompresion" ? "descompresion_modos." + n + ".nombre"
                                        : "modos_programa." + s + "_" + n + "_nombre"
        return I18n.existe(k, I18n.lang) ? I18n.t(k, I18n.lang) : String(n)
    }
    function descripcionModo(n, seccion) {
        const s = seccion || "descompresion"
        const k = s === "descompresion" ? "descompresion_modos." + n + ".desc"
                                        : "modos_programa." + s + "_" + n + "_linea"
        return I18n.existe(k, I18n.lang) ? I18n.t(k, I18n.lang) : ""
    }
    // D8-5.9: una línea de descripción por modo (lista con viñetas)
    function lineaModo(n, seccion) {
        const k = "modos_programa." + seccion + "_" + n + "_linea"
        return I18n.existe(k, I18n.lang) ? I18n.t(k, I18n.lang) : ""
    }
    function introModos(seccion) {
        const k = "modos_programa." + seccion + "_intro"
        return I18n.existe(k, I18n.lang) ? I18n.t(k, I18n.lang) : ""
    }
    // valor de un modo en la lista de parámetros: número y nombre
    function textoModo(n, seccion) {
        if (n === null || n === undefined)
            return "—"
        const nombre = nombreModo(n, seccion)
        return nombre === String(n) ? String(n) : n + " · " + nombre
    }
    // D8-5.7/5.8: modos válidos que entrega el backend (ya filtrados por el
    // tipo de carga: con líquido, 4, 5 y 0); sin lista, del mínimo al máximo
    function modosDe(p) {
        if (!p)
            return []
        if (p.modos && p.modos.length > 0)
            return p.modos
        const o = []
        const mn = p.min !== null && p.min !== undefined ? p.min : 0
        const mx = p.max !== null && p.max !== undefined ? p.max : 5
        for (let n = mn; n <= mx; n++)
            o.push(n)
        return o
    }
    // D8-5.7: aviso de un cambio automático (texto del catálogo con el modo)
    function textoAviso() {
        if (control.aviso === "")
            return ""
        const m = control.detalleAviso.modo
        return I18n.t(control.aviso, I18n.lang, { modo: m, nombre: nombreModo(m, "descompresion") })
    }
    // "2026-10-20T14:05:33" -> "20/10/2026 14:05"
    function fechaHora(ts) {
        const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(String(ts || ""))
        return m ? m[3] + "/" + m[2] + "/" + m[1] + " " + m[4] + ":" + m[5] : String(ts || "")
    }
    function textoModificacion(mod) {
        return mod ? I18n.t("opciones.ultima_modificacion", I18n.lang,
                            { usuario: mod.usuario, fecha: fechaHora(mod.ts) })
                   : I18n.t("opciones.sin_cambios", I18n.lang)
    }
    function mensajeError() {
        if (control.mensaje === "")
            return ""
        // DEU-01 (tanda 16): alivios y suministro vigentes del equipo
        return I18n.t(control.mensaje, I18n.lang,
                      { valor: control.detalleMensaje.valor ?? "—",
                        alivio_camara: control.detalleMensaje.alivio_camara ?? "—",
                        alivio_chaqueta: control.detalleMensaje.alivio_chaqueta ?? "—",
                        suministro: control.detalleMensaje.suministro ?? "—" })
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
            // D8-5.4: sin recorte; dos líneas o letra menor dentro de la fila
            height: parent.height; verticalAlignment: Text.AlignVCenter
            wrapMode: Text.Wrap
            fontSizeMode: Text.Fit; minimumPixelSize: Escala.fuenteMinima
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
            // D8-5.4: sin recorte; dos líneas o letra menor dentro de la fila
            height: parent.height; verticalAlignment: Text.AlignVCenter
            wrapMode: Text.Wrap
            fontSizeMode: Text.Fit; minimumPixelSize: Escala.fuenteMinima
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

    // D8-5.7: aviso informativo de un cambio automático (p. ej. el modo de
    // descompresión al cambiar el tipo de carga); se cierra con su botón
    Rectangle {
        id: bandaAviso
        objectName: "avisoParametros"
        visible: control.aviso !== ""
        anchors.top: bandaError.bottom
        anchors.topMargin: visible ? Escala.px(8) : 0
        width: parent.width
        // T21 (FC-10): el botón Cerrar ya tiene su ancho propio (antes 0) y
        // su alto de 97: la banda lo contiene
        height: visible ? Math.max(Escala.px(72), textoAviso.implicitHeight + Escala.px(32),
                                   cerrarAviso.height + Escala.px(16)) : 0
        radius: Escala.px(12)
        color: Colores.advertenciaFondo
        Text {
            id: textoAviso
            objectName: "textoAvisoParametros"
            anchors.left: parent.left; anchors.right: cerrarAviso.left
            anchors.margins: Escala.px(16)
            anchors.verticalCenter: parent.verticalCenter
            wrapMode: Text.WordWrap
            text: raiz.textoAviso()
            color: Colores.advertenciaTexto
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }
        BotonFormulario {
            id: cerrarAviso
            objectName: "cerrarAvisoParametros"
            anchors.right: parent.right; anchors.rightMargin: Escala.px(12)
            anchors.verticalCenter: parent.verticalCenter
            texto: I18n.t("acciones.cerrar", I18n.lang)
            onPulsado: control.limpiarAviso()
        }
    }

    // ======================= vista: programa (§5.1) =======================
    Flickable {
        objectName: "vistaPrograma"
        visible: raiz.vista === "programa"
        anchors.top: bandaAviso.bottom; anchors.topMargin: Escala.px(8)
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        contentHeight: columnaPrograma.height
        clip: true
        Column {
            id: columnaPrograma
            width: parent.width
            spacing: Escala.px(6)
            // Selector de programa: "03 · Nombre". Tanda 17 (PRC-01): desplegable
            // con lista vertical desplazable (antes, una cuadrícula Flow de chips
            // que no escalaba a 15 o más programas); filas "programa_" + número
            SelectorPrograma {
                id: selectorPrograma
                objectName: "selectorPrograma"
                width: parent.width
                // encima de las filas de sección mientras la lista está abierta
                z: abierto ? 10 : 0
                programas: control.programas
                numero: control.numero
                onProgramaElegido: (n) => control.elegirPrograma(n)
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
            // O1 (tanda 5): entradas mostradas en Preciclo y Ciclo (1 a 3)
            Fila {
                objectName: "filaEntradas"
                titulo: I18n.t("opciones.entradas_titulo", I18n.lang)
                onPulsada: { control.cargarEntradas(); raiz._prepararEntradas(); raiz.vista = "entradas" }
            }
            // C9 (tanda 9, D9-10): crear, duplicar, habilitar y borrar
            // programas se movieron a Opciones avanzadas › Manejo de ciclos
            Text {
                objectName: "gestionMovida"
                width: parent.width
                topPadding: Escala.px(24)
                wrapMode: Text.WordWrap
                text: I18n.t("opciones.gestion_movida", I18n.lang)
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(22)
            }
            Text {
                objectName: "programaDeshabilitado"
                visible: control.numero > 0 && !control.programaHabilitado
                width: parent.width
                wrapMode: Text.WordWrap
                text: I18n.t("opciones.programa_deshabilitado", I18n.lang)
                color: Colores.advertenciaTexto
                font.family: Tipografia.familia
                font.pixelSize: Escala.fuente(22)
            }
        }
    }

    // ======================= vista: sección (§5.2) =======================
    Item {
        objectName: "vistaSeccion"
        visible: raiz.vista === "seccion"
        anchors.top: bandaAviso.bottom; anchors.topMargin: Escala.px(8)
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        Row {
            id: encabezadoSeccion
            spacing: Escala.px(16)
            Text {
                objectName: "volverSeccion"
                text: "‹"
                font.pixelSize: Escala.fuente(96)
                color: Colores.accionPrimarioTexto
                MouseArea { anchors.fill: parent; anchors.margins: -Escala.px(28); onClicked: raiz.vista = "programa" }
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
                readonly property bool deModo: raiz.esModo(control.seccion, modelData)
                valor: Unidades.version < 0 ? ""
                       : deModo ? raiz.textoModo(modelData.valor, control.seccion)
                       : raiz.textoP(modelData.valor, modelData)
                detalle: deModo || modelData.tipo === "bool" || modelData.tipo === "enum" || raiz.convertible(modelData)
                         ? "" : (modelData.unidad || "")
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
        anchors.top: bandaAviso.bottom; anchors.topMargin: Escala.px(8)
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        Row {
            id: encabezadoSensores
            spacing: Escala.px(16)
            Text {
                objectName: "volverSensores"
                text: "‹"
                font.pixelSize: Escala.fuente(96)
                color: Colores.accionPrimarioTexto
                MouseArea { anchors.fill: parent; anchors.margins: -Escala.px(28); onClicked: raiz.vista = "programa" }
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
            // O11: sin ancho (BotonFormulario no tiene implícito) quedaba en 0 y no se veía
            width: Escala.px(320)
            texto: I18n.t("acciones.guardar", I18n.lang)
            primario: true
            habilitado: raiz._sensoresModificados && raiz._rolesValidos && control.sensoresEditable && raiz.edicionPermitida
            onPulsado: if (habilitado) control.guardarSensores(raiz._roles)
        }
    }

    // ======================= vista: entradas mostradas (O1) =======================
    // O11 (tanda 11, D11-7.2): tres filas "Entrada 1:", "Entrada 2:" y
    // "Entrada 3:", cada una con su desplegable. La 1 es obligatoria; la 2 y la
    // 3 admiten "Ninguna" (""); una entrada elegida en una fila no aparece en
    // las otras (ParametrosCicloController.opcionesFila). El selector solo
    // ofrece las disponibles (sin sensores No en uso, D11-7.1).
    property var _filasSel: ["", "", ""]
    property int _filaAbierta: -1
    readonly property bool _entradasModificadas: JSON.stringify(_filasSel) !== JSON.stringify(control.filasEntradas)
    readonly property bool _entradasEditables: control.entradasEditable && edicionPermitida
    function _prepararEntradas() {
        _filasSel = control.filasEntradas.slice()
        _filaAbierta = -1
    }
    function _nombreEntrada(nombre) {
        if (nombre === "")
            return I18n.t("opciones.entrada_ninguna", I18n.lang)
        const base = I18n.existe("io.ai." + nombre, I18n.lang) ? I18n.t("io.ai." + nombre, I18n.lang) : String(nombre)
        // Tanda 17 (SON-01): una sonda instalada con rol No en uso se ofrece y se
        // muestra con el rótulo "(monitoreo)"
        return (control.entradasNoEnUso || []).indexOf(nombre) >= 0
               ? base + " " + I18n.t("ciclo.monitoreo", I18n.lang) : base
    }
    function _elegirEntrada(fila, nombre) {
        const f = _filasSel.slice()
        f[fila] = nombre
        _filasSel = f
        _filaAbierta = -1
    }
    Connections {
        target: control
        function onEntradasChanged() { raiz._prepararEntradas() }
    }
    Item {
        objectName: "vistaEntradas"
        visible: raiz.vista === "entradas"
        anchors.top: bandaAviso.bottom; anchors.topMargin: Escala.px(8)
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        Flickable {
            anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
            anchors.bottom: guardarEntradas.top; anchors.bottomMargin: Escala.px(12)
            contentHeight: columnaEntradas.height
            clip: true
            Column {
                id: columnaEntradas
                width: parent.width
                spacing: Escala.px(6)
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: I18n.t("opciones.entradas_nota", I18n.lang)
                    color: Colores.textoGuia
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                }
                Repeater {
                    model: 3
                    delegate: Column {
                        id: filaEntrada
                        required property int index
                        readonly property bool abierta: raiz._filaAbierta === index
                        width: parent.width
                        Fila {
                            objectName: "filaEntrada_" + (filaEntrada.index + 1)
                            titulo: I18n.t("opciones.entrada_fila", I18n.lang, { n: filaEntrada.index + 1 })
                            valor: raiz._nombreEntrada(raiz._filasSel[filaEntrada.index] ?? "")
                            chevron: raiz._entradasEditables
                            onPulsada: if (raiz._entradasEditables)
                                           raiz._filaAbierta = filaEntrada.abierta ? -1 : filaEntrada.index
                        }
                        // desplegable de la fila: "Ninguna" (filas 2 y 3) y las disponibles
                        Rectangle {
                            objectName: "opcionesEntrada_" + (filaEntrada.index + 1)
                            visible: filaEntrada.abierta
                            width: parent.width
                            height: visible ? listaOpciones.height + Escala.px(12) : 0
                            radius: Escala.px(12)
                            color: Colores.fondoSutil
                            Column {
                                id: listaOpciones
                                y: Escala.px(6)
                                width: parent.width
                                Repeater {
                                    model: filaEntrada.abierta
                                           ? (filaEntrada.index > 0 ? [""] : []).concat(
                                                 control.opcionesFila(filaEntrada.index, raiz._filasSel))
                                           : []
                                    delegate: Fila {
                                        required property var modelData
                                        objectName: "opcionEntrada_" + modelData
                                        chevron: false
                                        titulo: raiz._nombreEntrada(modelData)
                                        // la elegida, resaltada (la fuente no trae "✓")
                                        color: (raiz._filasSel[filaEntrada.index] ?? "") === modelData
                                               ? Colores.accionFondoTenue : "transparent"
                                        onPulsada: raiz._elegirEntrada(filaEntrada.index, modelData)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        BotonFormulario {
            id: guardarEntradas
            objectName: "guardarEntradas"
            anchors.bottom: parent.bottom
            anchors.right: parent.right
            // O11: sin ancho (BotonFormulario no tiene implícito) quedaba en 0 y no se veía
            width: Escala.px(320)
            texto: I18n.t("acciones.guardar", I18n.lang)
            primario: true
            habilitado: raiz._entradasEditables && (raiz._filasSel[0] ?? "") !== ""
                        && raiz._entradasModificadas
            onPulsado: if (habilitado) control.guardarFilas(raiz._filasSel)
        }
    }

    // ======================= ventana de ajuste (§5.3) =======================
    Rectangle {
        id: ajuste
        objectName: "ventanaAjuste"
        property var param: null
        property var nuevo: null
        // U1: unidad de ingreso (psig o inHg en psi si el rango cruza la atmosférica)
        property string unidadIngreso: ""
        property string errorIngreso: ""
        readonly property var ingresosPsi: param && raiz.convertible(param) && Unidades.presion === "psi"
            ? Unidades.ingresosPsi(param.unidad || "", param.clave, param.min, param.max, param.clase || "") : []
        // revisión U1 (SAF-02): si las unidades cambian con la ventana abierta,
        // lo tecleado se descarta (se interpretaría en otra unidad)
        property int versionAlAbrir: -1
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
        readonly property bool editable: control.seccionEditable && raiz.edicionPermitida
        readonly property bool esModo: param !== null && raiz.esModo(control.seccion, param)
        // D8-5.7: selector (booleano, enumerado o modo) sin mínimo ni máximo
        readonly property bool porLista: param !== null && (esModo || param.tipo === "bool" || param.tipo === "enum")
        readonly property var modos: esModo ? raiz.modosDe(param) : []
        // "Por defecto" solo si el defecto es un valor permitido (con carga
        // líquida, el defecto sólido de un modo no lo es)
        readonly property bool defectoValido: param !== null && param.defecto !== null && param.defecto !== undefined
                                              && (!esModo || modos.indexOf(param.defecto) >= 0)
        readonly property var valorEnEdicion: nuevo !== null ? nuevo : (param ? param.valor : null)
        readonly property bool cambiado: visible && nuevo !== null && param !== null && nuevo !== param.valor
        function guardar() {
            if (cambiado && control.guardar(param.clave, nuevo))
                cerrar()
        }
        function abrir(p) {
            param = p; nuevo = null; errorIngreso = ""
            unidadIngreso = raiz.convertible(p) ? Unidades.unidadIngreso(p.unidad || "", p.clave, p.clase || "") : ""
            if (ingresosPsi.length > 0 && ingresosPsi.indexOf(unidadIngreso) < 0)
                unidadIngreso = ingresosPsi[0]
            visible = true
        }
        // valor tecleado en la unidad mostrada -> interna, redondeado y validado
        function recibir(v) {
            errorIngreso = ""
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
            y: Escala.px(97 + 32 + 16)      // bajo la franja de botones
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
                            { clave: "opciones.actual", valor: raiz.textoP(ajuste.param.valor, ajuste.param), toque: false },
                            { clave: "opciones.por_defecto", valor: raiz.textoP(ajuste.param.defecto, ajuste.param),
                              toque: ajuste.defectoValido && ajuste.param.defecto !== ajuste.param.valor },
                            { clave: "opciones.minimo", valor: raiz.textoP(ajuste.param.min, ajuste.param), toque: false },
                            { clave: "opciones.maximo", valor: raiz.textoP(ajuste.param.max, ajuste.param), toque: false }
                        ].filter(t => !ajuste.porLista || (t.clave !== "opciones.minimo" && t.clave !== "opciones.maximo")) : []
                        delegate: Rectangle {
                            id: tarjetaValor
                            required property var modelData
                            objectName: "valorAjuste_" + modelData.clave
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
                // Nuevo valor: numérico con el teclado; booleano y enumerado con opciones (U-17)
                Rectangle {
                    objectName: "campoNuevoValor"
                    visible: ajuste.param !== null && !ajuste.esModo && ajuste.param.tipo !== "bool" && ajuste.param.tipo !== "enum"
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
                              ? (raiz.convertible(ajuste.param) ? raiz.textoP(ajuste.nuevo, ajuste.param)
                                 : raiz.texto(ajuste.nuevo, ajuste.param ? ajuste.param.tipo : "") + " " + (ajuste.param ? ajuste.param.unidad : ""))
                              : I18n.t("opciones.toque_nuevo_valor", I18n.lang)
                        color: ajuste.nuevo !== null ? Colores.textoPrimario : Colores.textoGuia
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(26)
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: ajuste.editable && raiz.teclado !== null
                        // U1: con unidades convertidas el teclado no acota (el rango
                        // se valida en la unidad interna en ajuste.recibir)
                        onClicked: raiz.convertible(ajuste.param)
                            ? raiz.teclado.abrirNumerico(
                                raiz.etiqueta(control.seccion, ajuste.param.clave),
                                Unidades.simboloIngreso(ajuste.unidadIngreso),
                                Unidades.aMostrarEn(ajuste.nuevo !== null ? ajuste.nuevo : ajuste.param.valor,
                                                    ajuste.param.unidad || "", ajuste.param.clave, ajuste.unidadIngreso,
                                                    ajuste.param.clase || ""),
                                -1e9, 1e9, 2, (v) => ajuste.recibir(v))
                            : raiz.teclado.abrirNumerico(
                                raiz.etiqueta(control.seccion, ajuste.param.clave), ajuste.param.unidad,
                                ajuste.nuevo !== null ? ajuste.nuevo : ajuste.param.valor,
                                ajuste.param.min, ajuste.param.max,
                                ajuste.param.tipo === "float" ? 1 : 0,
                                (v) => { ajuste.nuevo = ajuste.param.tipo === "float" ? Number(v) : Math.round(Number(v)) })
                    }
                }
                // U1: psig o inHg cuando el rango cruza la atmosférica (DECISIÓN U1-2)
                Row {
                    objectName: "selectorIngresoPsi"
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
                    objectName: "errorIngreso"
                    visible: ajuste.errorIngreso !== ""
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: ajuste.errorIngreso
                    color: Colores.peligroTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
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
                // D8-5.7: al elegir carga líquida, la regla de los modos antes de guardar
                Text {
                    objectName: "avisoLiquidoPrevio"
                    visible: ajuste.param !== null && ajuste.param.clave === "tipo_carga"
                             && ajuste.valorEnEdicion === "liquido" && ajuste.param.valor !== "liquido"
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: I18n.t("opciones.aviso_liquido_previo", I18n.lang)
                    color: Colores.advertenciaTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                }
                // Modo (D8-5.8): un botón por modo válido y qué hace el elegido
                SelectorSegmentos {
                    id: selectorModo
                    objectName: "selectorModo"
                    visible: ajuste.esModo
                    width: parent.width
                    habilitado: ajuste.editable
                    // D8-5.7/5.8: solo los modos válidos (con carga líquida, 4, 5 y 0)
                    readonly property int actual: !ajuste.esModo ? -1 : ajuste.nuevo !== null ? ajuste.nuevo : (ajuste.param ? ajuste.param.valor : -1)
                    valor: actual
                    opciones: ajuste.modos.map(n => ({ valor: n, etiqueta: String(n) }))
                    onElegido: (n) => ajuste.nuevo = n
                }
                Text {
                    objectName: "descripcionModo"
                    // detalle del modo elegido solo en descompresión (en secado
                    // la línea de la lista ya lo dice todo)
                    visible: ajuste.esModo && control.seccion === "descompresion"
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: ajuste.esModo
                          ? "<b>" + raiz.nombreModo(selectorModo.actual, control.seccion) + ".</b> "
                            + raiz.descripcionModo(selectorModo.actual, control.seccion) : ""
                    textFormat: Text.StyledText
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                    color: Colores.textoPrimario
                }
                // D8-5.9: los modos disponibles como lista, una viñeta por modo
                // (nombre y una línea); el elegido, resaltado
                Column {
                    objectName: "listaModos"
                    visible: ajuste.esModo
                    width: parent.width
                    spacing: Escala.px(6)
                    Text {
                        objectName: "introModos"
                        visible: text !== ""
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: ajuste.esModo ? raiz.introModos(control.seccion) : ""
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(20)
                        color: Colores.textoGuia
                    }
                    Text {
                        text: I18n.t("opciones.modos_titulo", I18n.lang)
                        font.family: Tipografia.familia; font.weight: Tipografia.pesoBold
                        font.pixelSize: Escala.fuente(20)
                        color: Colores.textoPrimario
                    }
                    Repeater {
                        model: ajuste.modos
                        delegate: Text {
                            required property var modelData
                            objectName: "modo_" + modelData
                            width: parent.width
                            wrapMode: Text.WordWrap
                            textFormat: Text.StyledText
                            text: "• <b>" + modelData + " · " + raiz.nombreModo(modelData, control.seccion) + ":</b> "
                                  + raiz.lineaModo(modelData, control.seccion)
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(20)
                            color: modelData === selectorModo.actual ? Colores.accionPrimarioTexto : Colores.textoPrimario
                        }
                    }
                    // con carga líquida (el backend no ofrece el modo 1): por qué faltan modos
                    Text {
                        objectName: "notaLiquidoModos"
                        visible: control.seccion === "descompresion" && ajuste.modos.length > 0
                                 && ajuste.modos.indexOf(1) < 0
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: I18n.t("modos_programa.descompresion_nota_liquido", I18n.lang)
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(20)
                        color: Colores.advertenciaTexto
                    }
                }
                Text {
                    visible: ajuste.param !== null && !ajuste.esModo && ajuste.param.tipo !== "bool" && ajuste.param.tipo !== "enum"
                    text: ajuste.param ? I18n.t("opciones.rango_permitido", I18n.lang,
                                                { min: raiz.texto(ajuste.param.min, ajuste.param.tipo),
                                                  max: raiz.texto(ajuste.param.max, ajuste.param.tipo),
                                                  unidad: ajuste.param.unidad || "" }) : ""
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(20)
                    color: Colores.textoGuia
                }
                // Pie de la tarjeta: qué hace el parámetro y quién lo modificó por última vez
                Rectangle { width: parent.width; height: 1; color: Colores.bordeDivisor }
                Text {
                    objectName: "descripcionAjuste"
                    // D8-5.9: en un modo, la lista de arriba reemplaza al texto corrido
                    visible: text !== "" && !ajuste.esModo
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: ajuste.param ? raiz.descripcion(control.seccion, ajuste.param.clave) : ""
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                    color: Colores.textoPrimario
                }
                Text {
                    objectName: "modificacionAjuste"
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

    // Cancelar / Por defecto / Guardar: franja superior de la ventana de ajuste.
    // Arriba, no abajo, porque el teclado en pantalla sube desde el borde inferior
    // y tapaba los botones mientras se editaba el valor.
    Rectangle {
        id: accionesAjuste
        objectName: "accionesAjuste"
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
                objectName: "cancelarAjuste"
                width: parent.anchoBoton
                texto: I18n.t("acciones.cancelar", I18n.lang)
                onPulsado: ajuste.cerrar()
            }
            BotonFormulario {
                objectName: "defectoAjuste"
                width: parent.anchoBoton
                texto: I18n.t("opciones.por_defecto", I18n.lang)
                habilitado: ajuste.editable && ajuste.defectoValido && ajuste.valorEnEdicion !== ajuste.param.defecto
                onPulsado: ajuste.nuevo = ajuste.param.defecto
            }
            BotonFormulario {
                objectName: "guardarAjuste"
                width: parent.anchoBoton
                texto: I18n.t("acciones.guardar", I18n.lang)
                primario: true
                habilitado: ajuste.editable && ajuste.cambiado
                onPulsado: ajuste.guardar()
            }
        }
    }

    // Atrás con un parámetro editado sin guardar: ¿guardar o descartar?
    DialogoConfirmacion {
        id: dialogoGuardarAjuste
        objectName: "dialogoGuardarAjuste"
        mensaje: I18n.t("opciones.guardar_parametro_pregunta", I18n.lang)
        textoConfirmar: I18n.t("acciones.guardar", I18n.lang)
        textoCancelar: I18n.t("opciones.descartar_cambios", I18n.lang)
        onConfirmado: ajuste.guardar()
        onDescartado: ajuste.cerrar()
    }
}

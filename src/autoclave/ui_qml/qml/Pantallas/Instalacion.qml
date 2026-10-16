pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Componentes"
import Autoclave.I18n

// Asistente de instalación del equipo (reemplaza a installation/wizard.py, tkinter).
// Se muestra solo cuando falta el perfil de instalación (arranque, etapa 1).
// Pasos, en el orden del asistente actual: activación (serie + código),
// tipo de equipo, puertas, enfriamiento (se omite si el equipo no lo admite),
// fuente de vapor (vapor_source del perfil: generator, boiler o mixed; E1b),
// datos (modelo, suministros, sondas) y resumen. Al final, pantalla de resultado.
//
// Solo presenta: la validación del código, las capacidades por clase de equipo
// y la escritura del perfil viven en el puente Python (`puente`, contrato en
// el plan). Los textos se escriben con el teclado en pantalla (`teclado`,
// PanelTeclado del host). No hay sesión ni barra de navegación: el equipo aún
// no está instalado.
Item {
    id: raiz
    objectName: "instalacion"

    property QtObject teclado: null
    property QtObject puente: null

    // El perfil quedó escrito: el host decide qué sigue (reiniciar, continuar)
    signal instalacionCompletada()


    // ── Valores capturados ───────────────────────────────────────────────
    property string serie: ""
    property string codigo: ""
    property string clase: ""            // "" = sin elegir
    property int numPuertas: 0           // 0 = sin elegir
    property string tipoPuerta: ""
    property int puertaPc: 1
    property int nivelEnfriamiento: 0
    property string fuenteVapor: ""
    property string modelo: ""
    // Falla cerrada, como el asistente actual: todo cableado/instalado por defecto
    property var suministros: ({ agua_bomba: true, agua_generador: true, aire_comprimido: true,
                                 vapor_suministro: true, suministro_electrico: true })
    property var sondas: ({ temp_camara: true, temp_2_camara: true, temp_ref: true, temp_drenaje: true })

    readonly property var clavesSuministro: ["agua_bomba", "agua_generador", "aire_comprimido",
                                             "vapor_suministro", "suministro_electrico"]
    readonly property var clavesSonda: ["temp_camara", "temp_2_camara", "temp_ref", "temp_drenaje"]
    readonly property string sondaObligatoria: "temp_camara"
    readonly property var clavesTipoPuerta: ["simple", "motorized", "locking", "motorized_locking", "advanced"]
    readonly property var clavesVapor: ["generator", "boiler", "mixed"]   // vapor_source del perfil (E1b)

    // {campo: mensaje} del paso en curso; el campo lo pinta en rojo
    property var errores: ({})
    property string errorGeneral: ""
    property string campoActivo: ""      // campo que se está escribiendo

    // ── Capacidades de la clase elegida (las entrega el puente) ──────────
    // clases: [{valor, vacio, chaqueta, liquidos, puertasMax, enfriamientoMax}]
    readonly property var clases: puente ? puente.clases : []
    readonly property var capacidad: clases.find(c => c.valor === clase)
    readonly property int maxPuertas: capacidad ? capacidad.puertasMax : 2
    readonly property int maxEnfriamiento: capacidad ? capacidad.enfriamientoMax : 4

    // ── Pasos ────────────────────────────────────────────────────────────
    // Sin clase elegida se cuenta el paso de enfriamiento; al elegirla se omite si no aplica
    readonly property var pasos: {
        const p = ["activacion", "equipo", "puertas"]
        if (clase === "" || maxEnfriamiento > 0)
            p.push("enfriamiento")
        p.push("vapor", "datos", "resumen")
        return p
    }
    property int indice: 0
    property bool terminado: false
    readonly property string pasoActual: pasos[Math.min(indice, pasos.length - 1)]

    Connections {
        target: raiz.teclado
        function onAbiertoChanged() { if (!raiz.teclado.abierto) raiz.campoActivo = "" }
    }

    // ── Campos de texto y teclado ────────────────────────────────────────
    readonly property var campos: ({
        serie:  { titulo: I18n.t("instalacion.serie", I18n.lang),  maximo: 20 },
        codigo: { titulo: I18n.t("instalacion.codigo", I18n.lang), maximo: 12 },
        modelo: { titulo: I18n.t("instalacion.modelo", I18n.lang), maximo: 30 }
    })
    function editar(nombre, siguiente) {
        if (!teclado)
            return
        const campo = campos[nombre]
        teclado.abrirAlfanumerico(campo.titulo, raiz[nombre], campo.maximo, false,
                                  texto => raiz[nombre] = texto,
                                  siguiente ? () => raiz.editar(siguiente) : null)
        campoActivo = nombre
    }
    function textoCampo(nombre) {
        return campoActivo === nombre && teclado ? teclado.textoEnEdicion : raiz[nombre]
    }

    // ── Cambios de valores ───────────────────────────────────────────────
    function elegirClase(valor) {
        clase = valor
        // como el asistente actual: se recortan los valores que la clase no admite
        if (numPuertas > maxPuertas) numPuertas = maxPuertas
        if (maxPuertas === 1) numPuertas = 1
        if (nivelEnfriamiento > maxEnfriamiento) nivelEnfriamiento = maxEnfriamiento
        if (numPuertas < 2) puertaPc = 1
        errores = ({})
    }
    function elegirPuertas(n) {
        numPuertas = n
        if (n < 2) puertaPc = 1
        errores = ({})
    }
    function alternar(grupo, clave) {
        const copia = Object.assign({}, raiz[grupo])
        copia[clave] = !copia[clave]
        raiz[grupo] = copia
    }

    // ── Validación y navegación ──────────────────────────────────────────
    function _validar(paso) {
        const e = {}
        if (paso === "activacion") {
            if (serie.trim() === "")
                e.serie = I18n.t("instalacion.error_serie", I18n.lang)
            if (codigo.trim() === "")
                e.codigo = I18n.t("instalacion.error_codigo_vacio", I18n.lang)
            else if (e.serie === undefined && puente && !puente.validarCodigo(serie.trim(), codigo.trim()))
                e.codigo = I18n.t("instalacion.error_codigo", I18n.lang)
        } else if (paso === "equipo") {
            if (clase === "")
                e.clase = I18n.t("instalacion.error_equipo", I18n.lang)
        } else if (paso === "puertas") {
            if (numPuertas === 0)
                e.numPuertas = I18n.t("instalacion.error_cantidad_puertas", I18n.lang)
            if (tipoPuerta === "")
                e.tipoPuerta = I18n.t("instalacion.error_tipo_puerta", I18n.lang)
        } else if (paso === "vapor") {
            if (fuenteVapor === "")
                e.vapor = I18n.t("instalacion.error_vapor", I18n.lang)
        } else if (paso === "datos") {
            if (modelo.trim() === "")
                e.modelo = I18n.t("instalacion.error_modelo", I18n.lang)
        }
        errores = e
        return Object.keys(e).length === 0
    }
    function siguiente() {
        if (teclado)
            teclado.cerrar()
        if (!_validar(pasoActual))
            return
        if (indice < pasos.length - 1)
            indice += 1
    }
    function atras() {
        if (teclado)
            teclado.cerrar()
        errores = ({})
        errorGeneral = ""
        if (indice > 0)
            indice -= 1
    }
    // Perfil que recibe el puente (mismos nombres que installation_profile.json)
    function perfil() {
        return {
            serial_number: serie.trim().toUpperCase(),
            model_id: modelo.trim(),
            equipment_class: clase,
            door_count: numPuertas,
            door_type: tipoPuerta,
            door_id: puertaPc,
            cooling_level: nivelEnfriamiento,
            vapor_source: fuenteVapor,           // E1b: generator | boiler | mixed
            supply_inputs: suministros,
            temperature_probes: sondas
        }
    }
    // Tipos de puerta con cerrojo controlado por el software (devices/factory/factory.py)
    readonly property bool conCerrojo: ["locking", "motorized_locking", "advanced"].indexOf(tipoPuerta) >= 0
    function pedirConfirmacion() { dialogoInstalar.abrir() }
    function instalar() {
        if (!puente)
            return
        const r = puente.instalar(perfil())
        if (r.ok) {
            errorGeneral = ""
            terminado = true
        } else {
            errorGeneral = I18n.t("instalacion.error_guardar", I18n.lang, { detalle: r.error || "" })
        }
    }

    // ── Textos derivados ─────────────────────────────────────────────────
    function etiquetaClase(valor) { return I18n.t("instalacion.clase_" + valor, I18n.lang) }
    function chipsClase(c) {
        const l = []
        if (c.vacio) l.push(I18n.t("instalacion.cap_vacio", I18n.lang))
        if (c.chaqueta) l.push(I18n.t("instalacion.cap_chaqueta", I18n.lang))
        if (c.liquidos) l.push(I18n.t("instalacion.cap_liquidos", I18n.lang))
        l.push(c.puertasMax > 1 ? I18n.t("instalacion.cap_dos_puertas", I18n.lang) : I18n.t("instalacion.cap_una_puerta", I18n.lang))
        return l
    }
    function _lista(claves, grupo, prefijo) {
        const sin = claves.filter(k => raiz[grupo][k] === false).map(k => I18n.t("instalacion." + (prefijo + k), I18n.lang))
        return sin.length > 0 ? sin.join(", ") : I18n.t("instalacion.resumen_ninguna", I18n.lang)
    }
    readonly property var filasResumen: [
        { clave: "resumen_serie", valor: serie.trim().toUpperCase() },
        { clave: "resumen_modelo", valor: modelo.trim() },
        { clave: "resumen_equipo", valor: etiquetaClase(clase) },
        { clave: "resumen_puertas", valor: numPuertas + " · " + I18n.t("instalacion.puerta_" + tipoPuerta, I18n.lang) },
        // SAF-01 de T9: el tipo de puerta decide si el software maneja el
        // cerrojo y vigila el empaque; se muestra explícito
        { clave: "resumen_cerrojo", valor: I18n.t(conCerrojo ? "instalacion.resumen_con_cerrojo"
                                                              : "instalacion.resumen_sin_cerrojo", I18n.lang) },
        { clave: "resumen_empaque", valor: I18n.t(tipoPuerta === "simple" ? "instalacion.resumen_sin_empaque"
                                                                          : "instalacion.resumen_con_empaque", I18n.lang) },
        { clave: "resumen_puerta_pc", valor: numPuertas > 1 ? I18n.t("instalacion.puerta_pc_" + puertaPc, I18n.lang) : "" },
        { clave: "resumen_enfriamiento", valor: maxEnfriamiento === 0 ? ""
              : nivelEnfriamiento === 0 ? I18n.t("instalacion.resumen_sin_enfriamiento", I18n.lang)
              : I18n.t("instalacion.resumen_nivel", I18n.lang, { n: nivelEnfriamiento }) },
        { clave: "resumen_vapor", valor: I18n.t("instalacion.vapor_" + fuenteVapor, I18n.lang) },
        { clave: "resumen_sin_vigilar", valor: _lista(clavesSuministro, "suministros", "sum_") },
        { clave: "resumen_sin_sonda", valor: _lista(clavesSonda, "sondas", "sonda_") }
    ].filter(f => f.valor !== "")

    // ── Presentación ─────────────────────────────────────────────────────
    FondoApp { anchors.fill: parent }

    BarraSuperior {
        objectName: "barraSuperior"
        mostrarIconos: false   // sin backend ni sesión: campana y engranaje no aplican
    }

    TarjetaContenido {
        id: tarjeta
        x: Escala.px(24); y: Escala.px(176)
        width: parent.width - Escala.px(48)
        height: parent.height - Escala.px(176) - Escala.px(24)

        contenido: [
            Item {
                id: lienzo
                anchors.fill: parent

                readonly property real margen: Escala.px(64)
                readonly property real ancho: width - 2 * margen

                // ---- encabezado ----
                Text {
                    objectName: "tituloInstalacion"
                    x: lienzo.margen; y: Escala.px(56)
                    text: raiz.terminado ? I18n.t("instalacion.listo_titulo", I18n.lang).toUpperCase() : I18n.t("instalacion.titulo", I18n.lang)
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(Tipografia.tituloPantallaTam)
                    font.weight: Tipografia.pesoBold
                    font.letterSpacing: Escala.px(Tipografia.tituloPantallaTam * 0.05)
                }
                IndicadorPasos {
                    id: indicador
                    objectName: "indicadorPasos"
                    visible: !raiz.terminado
                    x: lienzo.margen; y: Escala.px(140)
                    width: lienzo.ancho
                    total: raiz.pasos.length
                    actual: raiz.indice
                }
                Text {
                    objectName: "subtituloPaso"
                    visible: !raiz.terminado
                    x: lienzo.margen; y: Escala.px(212)
                    text: I18n.t("instalacion.paso_de", I18n.lang, { n: raiz.indice + 1, total: raiz.pasos.length })
                          + "  ·  " + I18n.t("instalacion.paso_" + raiz.pasoActual, I18n.lang)
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
                    font.weight: Tipografia.pesoSemiBold
                }

                // Zona de cada paso
                readonly property real yPagina: Escala.px(276)
                readonly property real altoPagina: height - yPagina - Escala.px(16)

                component Titulo: Text {
                    color: Colores.textoPrimario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(30)
                    font.weight: Tipografia.pesoBold
                    wrapMode: Text.WordWrap
                }
                component Ayuda: Text {
                    color: Colores.textoSecundario
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(21)
                    wrapMode: Text.WordWrap
                }
                component ErrorTexto: Text {
                    visible: text !== ""
                    color: Colores.peligroTexto
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(22)
                    font.weight: Tipografia.pesoMedium
                    wrapMode: Text.WordWrap
                }

                // ============ 1. Activación ============
                Item {
                    objectName: "pasoActivacion"
                    visible: !raiz.terminado && raiz.pasoActual === "activacion"
                    x: lienzo.margen; y: lienzo.yPagina
                    width: lienzo.ancho; height: lienzo.altoPagina

                    CampoFormulario {
                        id: campoSerie
                        width: parent.width
                        etiqueta: I18n.t("instalacion.serie", I18n.lang)
                        marcador: I18n.t("instalacion.serie_marcador", I18n.lang)
                        valor: raiz.textoCampo("serie")
                        activo: raiz.campoActivo === "serie"
                        mensajeError: raiz.errores.serie ?? ""
                        nombreObjeto: "campoSerie"
                        nombreError: "errorSerie"
                        onTocado: raiz.editar("serie", "codigo")
                    }
                    CampoFormulario {
                        id: campoCodigo
                        y: Escala.px(167)
                        width: parent.width
                        etiqueta: I18n.t("instalacion.codigo", I18n.lang)
                        marcador: I18n.t("instalacion.codigo_marcador", I18n.lang)
                        valor: raiz.textoCampo("codigo")
                        activo: raiz.campoActivo === "codigo"
                        mensajeError: raiz.errores.codigo ?? ""
                        nombreObjeto: "campoCodigo"
                        nombreError: "errorCodigo"
                        onTocado: raiz.editar("codigo")
                    }
                    Ayuda {
                        y: Escala.px(352)
                        width: parent.width
                        text: I18n.t("instalacion.activacion_ayuda", I18n.lang)
                    }
                }

                // ============ 2. Tipo de equipo ============
                Item {
                    objectName: "pasoEquipo"
                    visible: !raiz.terminado && raiz.pasoActual === "equipo"
                    x: lienzo.margen; y: lienzo.yPagina
                    width: lienzo.ancho; height: lienzo.altoPagina

                    Titulo { id: tituloEquipo; width: parent.width; text: I18n.t("instalacion.equipo_titulo", I18n.lang) }
                    Column {
                        y: Escala.px(64)
                        width: parent.width
                        spacing: Escala.px(16)
                        Repeater {
                            model: raiz.clases
                            delegate: OpcionTarjeta {
                                id: opcionClase
                                required property var modelData
                                objectName: "clase_" + modelData.valor
                                width: parent.width
                                titulo: raiz.etiquetaClase(modelData.valor)
                                chips: raiz.chipsClase(modelData)
                                seleccionada: raiz.clase === modelData.valor
                                onPulsado: raiz.elegirClase(modelData.valor)
                            }
                        }
                    }
                    ErrorTexto {
                        objectName: "errorClase"
                        anchors.bottom: parent.bottom
                        width: parent.width
                        text: raiz.errores.clase ?? ""
                    }
                }

                // ============ 3. Puertas ============
                Item {
                    objectName: "pasoPuertas"
                    visible: !raiz.terminado && raiz.pasoActual === "puertas"
                    x: lienzo.margen; y: lienzo.yPagina
                    width: lienzo.ancho; height: lienzo.altoPagina

                    Titulo { id: tituloCantidad; width: parent.width; text: I18n.t("instalacion.puertas_cantidad", I18n.lang) }
                    SelectorSegmentos {
                        id: selectorPuertas
                        objectName: "selectorPuertas"
                        visible: raiz.maxPuertas > 1
                        y: Escala.px(52)
                        width: parent.width
                        valor: raiz.numPuertas
                        opciones: [
                            { valor: 1, etiqueta: I18n.t("instalacion.puertas_una", I18n.lang) },
                            { valor: 2, etiqueta: I18n.t("instalacion.puertas_dos", I18n.lang) }
                        ]
                        onElegido: n => raiz.elegirPuertas(n)
                    }
                    // Equipo de una sola puerta: valor fijo, sin selector
                    Rectangle {
                        objectName: "puertaFija"
                        visible: raiz.maxPuertas === 1
                        y: Escala.px(52)
                        width: parent.width; height: Escala.px(88)
                        radius: Escala.px(8)
                        color: Colores.fondoSutil
                        border.width: 1; border.color: Colores.bordeDivisor
                        Text {
                            anchors.left: parent.left; anchors.leftMargin: Escala.px(28)
                            anchors.verticalCenter: parent.verticalCenter
                            text: I18n.t("instalacion.puertas_una", I18n.lang)
                            color: Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(Tipografia.botonEtiquetaTam)
                            font.weight: Tipografia.pesoBold
                        }
                        Image {
                            anchors.right: parent.right; anchors.rightMargin: Escala.px(28)
                            anchors.verticalCenter: parent.verticalCenter
                            width: Escala.px(36); height: width
                            source: "../../assets/iconos/color/candado.svg"
                            sourceSize.width: width
                            sourceSize.height: height
                        }
                    }
                    Titulo { id: tituloTipo; y: Escala.px(204); width: parent.width; text: I18n.t("instalacion.puertas_tipo", I18n.lang) }
                    Column {
                        id: columnaTipos
                        y: Escala.px(256)
                        width: parent.width
                        spacing: Escala.px(12)
                        Repeater {
                            model: raiz.clavesTipoPuerta
                            delegate: OpcionTarjeta {
                                required property string modelData
                                objectName: "tipoPuerta_" + modelData
                                width: parent.width
                                titulo: I18n.t("instalacion.puerta_" + modelData, I18n.lang)
                                descripcion: I18n.existe("instalacion.puerta_" + modelData + "_desc", I18n.lang)
                                             ? I18n.t("instalacion.puerta_" + modelData + "_desc", I18n.lang) : ""
                                seleccionada: raiz.tipoPuerta === modelData
                                onPulsado: { raiz.tipoPuerta = modelData; raiz.errores = ({}) }
                            }
                        }
                    }
                    ErrorTexto {
                        objectName: "errorTipoPuerta"
                        y: columnaTipos.y + columnaTipos.height + Escala.px(12)
                        width: parent.width
                        text: raiz.errores.tipoPuerta ?? ""
                    }

                    // Puerta de este PC: solo con dos puertas
                    Titulo {
                        id: tituloPuertaPc
                        visible: raiz.numPuertas > 1
                        y: columnaTipos.y + columnaTipos.height + Escala.px(64)
                        width: parent.width
                        text: I18n.t("instalacion.puerta_pc", I18n.lang)
                    }
                    SelectorSegmentos {
                        id: selectorPuertaPc
                        objectName: "selectorPuertaPc"
                        visible: raiz.numPuertas > 1
                        y: tituloPuertaPc.y + Escala.px(52)
                        width: parent.width
                        valor: raiz.puertaPc
                        opciones: [
                            { valor: 1, etiqueta: I18n.t("instalacion.puerta_pc_1", I18n.lang) },
                            { valor: 2, etiqueta: I18n.t("instalacion.puerta_pc_2", I18n.lang) }
                        ]
                        onElegido: n => raiz.puertaPc = n
                    }
                }

                // ============ 4. Enfriamiento ============
                Item {
                    objectName: "pasoEnfriamiento"
                    visible: !raiz.terminado && raiz.pasoActual === "enfriamiento"
                    x: lienzo.margen; y: lienzo.yPagina
                    width: lienzo.ancho; height: lienzo.altoPagina

                    Titulo { width: parent.width; text: I18n.t("instalacion.enfriamiento_titulo", I18n.lang) }
                    SelectorSegmentos {
                        objectName: "selectorEnfriamiento"
                        y: Escala.px(52)
                        width: parent.width
                        valor: raiz.nivelEnfriamiento
                        opciones: {
                            const o = []
                            for (let n = 0; n <= raiz.maxEnfriamiento; n++)
                                o.push({ valor: n, etiqueta: "" + n })
                            return o
                        }
                        onElegido: n => raiz.nivelEnfriamiento = n
                    }
                    Ayuda {
                        y: Escala.px(152)
                        width: parent.width
                        text: I18n.t("instalacion.enfriamiento_ayuda", I18n.lang)
                    }
                }

                // ============ 5. Fuente de vapor (NUEVO) ============
                Item {
                    objectName: "pasoVapor"
                    visible: !raiz.terminado && raiz.pasoActual === "vapor"
                    x: lienzo.margen; y: lienzo.yPagina
                    width: lienzo.ancho; height: lienzo.altoPagina

                    Titulo { width: parent.width; text: I18n.t("instalacion.vapor_titulo", I18n.lang) }
                    Column {
                        y: Escala.px(64)
                        width: parent.width
                        spacing: Escala.px(16)
                        Repeater {
                            model: raiz.clavesVapor
                            delegate: OpcionTarjeta {
                                required property string modelData
                                objectName: "vapor_" + modelData
                                width: parent.width
                                titulo: I18n.t("instalacion.vapor_" + modelData, I18n.lang)
                                descripcion: I18n.existe("instalacion.vapor_" + modelData + "_desc", I18n.lang)
                                             ? I18n.t("instalacion.vapor_" + modelData + "_desc", I18n.lang) : ""
                                seleccionada: raiz.fuenteVapor === modelData
                                onPulsado: { raiz.fuenteVapor = modelData; raiz.errores = ({}) }
                            }
                        }
                    }
                    ErrorTexto {
                        objectName: "errorVapor"
                        anchors.bottom: parent.bottom
                        width: parent.width
                        text: raiz.errores.vapor ?? ""
                    }
                }

                // ============ 6. Datos del equipo ============
                Item {
                    objectName: "pasoDatos"
                    visible: !raiz.terminado && raiz.pasoActual === "datos"
                    x: lienzo.margen; y: lienzo.yPagina
                    width: lienzo.ancho; height: lienzo.altoPagina

                    CampoFormulario {
                        width: parent.width
                        etiqueta: I18n.t("instalacion.modelo", I18n.lang)
                        marcador: I18n.t("instalacion.modelo_marcador", I18n.lang)
                        valor: raiz.textoCampo("modelo")
                        activo: raiz.campoActivo === "modelo"
                        mensajeError: raiz.errores.modelo ?? ""
                        nombreObjeto: "campoModelo"
                        nombreError: "errorModelo"
                        onTocado: raiz.editar("modelo")
                    }

                    Titulo { y: Escala.px(168); width: parent.width; text: I18n.t("instalacion.suministros_titulo", I18n.lang) }
                    Ayuda { y: Escala.px(212); width: parent.width; text: I18n.t("instalacion.suministros_ayuda", I18n.lang) }
                    Column {
                        y: Escala.px(290)
                        width: parent.width
                        Repeater {
                            model: raiz.clavesSuministro
                            delegate: FilaInterruptor {
                                required property string modelData
                                required property int index
                                objectName: "suministro_" + modelData
                                width: parent.width
                                etiqueta: I18n.t("instalacion.sum_" + modelData, I18n.lang)
                                marcado: raiz.suministros[modelData] === true
                                ultima: index === raiz.clavesSuministro.length - 1
                                onAlternado: raiz.alternar("suministros", modelData)
                            }
                        }
                    }

                    Titulo { y: Escala.px(758); width: parent.width; text: I18n.t("instalacion.sondas_titulo", I18n.lang) }
                    Ayuda { y: Escala.px(802); width: parent.width; text: I18n.t("instalacion.sondas_ayuda", I18n.lang) }
                    Column {
                        y: Escala.px(852)
                        width: parent.width
                        Repeater {
                            model: raiz.clavesSonda
                            delegate: FilaInterruptor {
                                required property string modelData
                                required property int index
                                objectName: "sonda_" + modelData
                                width: parent.width
                                etiqueta: I18n.t("instalacion.sonda_" + modelData, I18n.lang)
                                marcado: raiz.sondas[modelData] === true
                                bloqueado: modelData === raiz.sondaObligatoria
                                ultima: index === raiz.clavesSonda.length - 1
                                onAlternado: raiz.alternar("sondas", modelData)
                            }
                        }
                    }
                }

                // ============ 7. Resumen ============
                Item {
                    objectName: "pasoResumen"
                    visible: !raiz.terminado && raiz.pasoActual === "resumen"
                    x: lienzo.margen; y: lienzo.yPagina
                    width: lienzo.ancho; height: lienzo.altoPagina

                    Titulo { width: parent.width; text: I18n.t("instalacion.resumen_titulo", I18n.lang) }

                    Rectangle {
                        y: Escala.px(60)
                        width: parent.width
                        height: filas.implicitHeight + Escala.px(16)
                        radius: Escala.px(14)
                        color: Colores.fondoSutil
                        border.width: 1; border.color: Colores.bordeDivisor
                        Column {
                            id: filas
                            x: Escala.px(28); y: Escala.px(8)
                            width: parent.width - Escala.px(56)
                            Repeater {
                                model: raiz.filasResumen
                                delegate: Item {
                                    id: fila
                                    required property var modelData
                                    required property int index
                                    width: parent.width
                                    height: Math.max(Escala.px(72), valorFila.implicitHeight + Escala.px(28))
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: I18n.t("instalacion." + fila.modelData.clave, I18n.lang)
                                        color: Colores.textoSecundario
                                        font.family: Tipografia.familia
                                        font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
                                        font.weight: Tipografia.pesoMedium
                                    }
                                    Text {
                                        id: valorFila
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: parent.width * 0.6
                                        horizontalAlignment: Text.AlignRight
                                        wrapMode: Text.WordWrap
                                        maximumLineCount: 3
                                        elide: Text.ElideRight
                                        text: fila.modelData.valor
                                        color: Colores.textoPrimario
                                        font.family: Tipografia.familia
                                        font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                                        font.weight: Tipografia.pesoBold
                                    }
                                    Rectangle {
                                        visible: fila.index < raiz.filasResumen.length - 1
                                        anchors.bottom: parent.bottom
                                        width: parent.width; height: 1
                                        color: Colores.bordeDivisor
                                    }
                                }
                            }
                        }
                    }

                    // Aviso de perfil bloqueado (misma banda que el aviso de Opciones)
                    Rectangle {
                        objectName: "avisoBloqueo"
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: Escala.px(104)
                        radius: Escala.px(14)
                        color: Colores.advertenciaFondo
                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: Escala.px(28); anchors.rightMargin: Escala.px(28)
                            verticalAlignment: Text.AlignVCenter
                            wrapMode: Text.WordWrap
                            text: I18n.t("instalacion.resumen_aviso", I18n.lang)
                            color: Colores.advertenciaTexto
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(23)
                            font.weight: Tipografia.pesoSemiBold
                        }
                    }
                    // Error al guardar el perfil
                    Rectangle {
                        objectName: "errorGuardar"
                        visible: raiz.errorGeneral !== ""
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: Escala.px(120)
                        width: parent.width
                        height: Escala.px(88)
                        radius: Escala.px(14)
                        color: Colores.peligroFondo
                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: Escala.px(28); anchors.rightMargin: Escala.px(28)
                            verticalAlignment: Text.AlignVCenter
                            wrapMode: Text.WordWrap
                            text: raiz.errorGeneral
                            color: Colores.peligroTexto
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(23)
                            font.weight: Tipografia.pesoSemiBold
                        }
                    }
                }

                // ============ Resultado ============
                Item {
                    objectName: "pasoListo"
                    visible: raiz.terminado
                    x: lienzo.margen; y: lienzo.yPagina
                    width: lienzo.ancho; height: lienzo.altoPagina

                    Rectangle {
                        id: sello
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: Escala.px(200)
                        width: Escala.px(220); height: width; radius: width / 2
                        color: Colores.accionFondoTenue
                        Image {
                            anchors.centerIn: parent
                            width: parent.width * 0.5; height: width
                            source: "../../assets/iconos/color/confirmar.svg"
                            sourceSize.width: width
                            sourceSize.height: height
                        }
                    }
                    Text {
                        anchors.top: sello.bottom
                        anchors.topMargin: Escala.px(48)
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: I18n.t("instalacion.listo_texto", I18n.lang)
                        color: Colores.textoSecundario
                        font.family: Tipografia.familia
                        font.pixelSize: Escala.fuente(Tipografia.campoValorTam)
                    }
                }
            }
        ]

        // Barra de acciones (en lugar de la barra de navegación: aún no hay sesión)
        pie: [
            Item {
                anchors.fill: parent
                readonly property real margen: Escala.px(64)

                BotonFormulario {
                    objectName: "botonAtras"
                    visible: !raiz.terminado && raiz.indice > 0
                    x: parent.margen; anchors.verticalCenter: parent.verticalCenter
                    width: Escala.px(433)
                    texto: I18n.t("instalacion.atras", I18n.lang)
                    onPulsado: raiz.atras()
                }
                BotonFormulario {
                    objectName: "botonSiguiente"
                    visible: !raiz.terminado
                    x: parent.width - parent.margen - width
                    anchors.verticalCenter: parent.verticalCenter
                    width: Escala.px(508)
                    primario: true
                    texto: raiz.pasoActual === "resumen" ? I18n.t("instalacion.instalar", I18n.lang) : I18n.t("instalacion.siguiente", I18n.lang)
                    icono: raiz.pasoActual === "resumen" ? "../../assets/iconos/color/guardar.svg" : ""
                    onPulsado: {
                        if (raiz.pasoActual === "resumen")
                            raiz.pedirConfirmacion()
                        else
                            raiz.siguiente()
                    }
                }
                BotonFormulario {
                    objectName: "botonContinuar"
                    visible: raiz.terminado
                    anchors.centerIn: parent
                    width: Escala.px(508)
                    primario: true
                    texto: I18n.t("instalacion.continuar", I18n.lang)
                    onPulsado: raiz.instalacionCompletada()
                }
                Text {
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: Escala.px(16)
                    text: I18n.t("app.version", I18n.lang)
                    color: Colores.textoGuia
                    font.family: Tipografia.familia
                    font.pixelSize: Escala.fuente(16)
                    font.weight: Tipografia.pesoMedium
                }
            }
        ]
    }

    // Confirmación previa a escribir el perfil (queda bloqueado)
    DialogoConfirmacion {
        id: dialogoInstalar
        objectName: "dialogoInstalar"
        // SAF-01 de T9: sin cerrojo controlado, la confirmación lo dice expresamente
        mensaje: raiz.conCerrojo ? I18n.t("instalacion.confirmar_pregunta", I18n.lang)
                                 : I18n.t("instalacion.confirmar_sin_cerrojo", I18n.lang)
        textoConfirmar: I18n.t("instalacion.confirmar_si", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        onConfirmado: raiz.instalar()
    }
}

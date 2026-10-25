pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Componentes"
import Autoclave.I18n

// Asistente de instalación del equipo (reemplaza a installation/wizard.py, tkinter).
// Se muestra solo cuando falta el perfil de instalación (arranque, etapa 1).
// Pasos, en el orden del asistente actual: activación (serie + código),
// tipo de equipo (solo Piso y Piso laboratorio, M1/AM-3), puertas, cámara
// (capacidad nominal y tipo de carga, con la vista previa del nombre del
// modelo; M1), enfriamiento (se omite si el equipo no lo admite), fuente de
// vapor (vapor_source del perfil: generator, boiler o mixed; E1b), datos
// (suministros, sondas), contraseñas de Admin e Ingeniero (LIC-02, obligatorio
// también en reinstalación; las reglas viven en el puente) y resumen. Al
// final, pantalla de resultado.
// M1 (tanda 7, planeacion_asistente_modelo.md): el nombre del modelo lo
// calcula el puente (SPK-SAT <L><V|H>[2][-LAB]); no hay campo libre "Modelo".
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
    property int capacidadLitros: 0      // litros; 0 = sin escribir (M1)
    property string tipoCarga: ""        // "V" | "H"; "" = sin elegir (M1)
    // Falla cerrada, como el asistente actual: todo cableado/instalado por defecto
    property var suministros: ({ agua_bomba: true, agua_generador: true, aire_comprimido: true,
                                 vapor_suministro: true, suministro_electrico: true })
    property var sondas: ({ temp_camara: true, temp_2_camara: true, temp_ref: true, temp_drenaje: true })
    // LIC-02: contraseñas de las cuentas del sistema (se guardan al instalar)
    property string clave_admin: ""
    property string confirmacion_admin: ""
    property string clave_ingeniero: ""
    property string confirmacion_ingeniero: ""
    readonly property var camposContrasena: ["clave_admin", "confirmacion_admin",
                                             "clave_ingeniero", "confirmacion_ingeniero"]

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

    // ── Cámara y nombre del modelo (M1) ──────────────────────────────────
    readonly property int capacidadMin: 20
    readonly property int capacidadMax: 2000
    readonly property bool capacidadValida: capacidadLitros >= capacidadMin && capacidadLitros <= capacidadMax
    // Mientras se escribe, la vista previa sigue a lo que se lleva escrito
    readonly property int capacidadEnVivo: {
        if (campoActivo === "capacidad" && teclado) {
            const n = parseInt(teclado.textoEnEdicion, 10)
            return isNaN(n) ? 0 : n
        }
        return capacidadLitros
    }
    // La regla vive en Python (installation/modelo.py, vía el puente); "" si falta un dato
    readonly property string modeloCalculado: puente ? puente.calcularModelo(clase, capacidadEnVivo, tipoCarga, numPuertas) : ""
    function editarCapacidad() {
        if (!teclado)
            return
        teclado.abrirNumerico(I18n.t("instalacion.camara_capacidad", I18n.lang),
                              I18n.t("instalacion.unidad_litros", I18n.lang),
                              capacidadLitros > 0 ? capacidadLitros : null, capacidadMin, capacidadMax, 0,
                              v => { raiz.capacidadLitros = Math.round(v); raiz.errores = ({}) }, null)
        campoActivo = "capacidad"
    }

    // ── Pasos ────────────────────────────────────────────────────────────
    // Sin clase elegida se cuenta el paso de enfriamiento; al elegirla se omite si no aplica
    readonly property var pasos: {
        const p = ["activacion", "equipo", "puertas", "camara"]
        if (clase === "" || maxEnfriamiento > 0)
            p.push("enfriamiento")
        p.push("vapor", "datos", "contrasenas", "resumen")
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
        // LIC-02: 64 = PASSWORD_MAX del backend (validacion_usuario.py)
        clave_admin: { titulo: I18n.t("instalacion.clave_admin", I18n.lang), maximo: 64, oculto: true },
        confirmacion_admin: { titulo: I18n.t("instalacion.confirmacion_admin", I18n.lang), maximo: 64, oculto: true },
        clave_ingeniero: { titulo: I18n.t("instalacion.clave_ingeniero", I18n.lang), maximo: 64, oculto: true },
        confirmacion_ingeniero: { titulo: I18n.t("instalacion.confirmacion_ingeniero", I18n.lang), maximo: 64, oculto: true }
    })
    function editar(nombre, siguiente) {
        if (!teclado)
            return
        const campo = campos[nombre]
        teclado.abrirAlfanumerico(campo.titulo, raiz[nombre], campo.maximo, campo.oculto === true,
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
        } else if (paso === "camara") {
            if (!capacidadValida)
                e.capacidad = I18n.t("instalacion.error_capacidad", I18n.lang)
            if (tipoCarga !== "V" && tipoCarga !== "H")
                e.tipoCarga = I18n.t("instalacion.error_tipo_carga", I18n.lang)
        } else if (paso === "contrasenas") {
            // LIC-02: sin puente no se avanza (falla cerrada)
            if (!puente) {
                e.clave_admin = I18n.t("instalacion.error_contrasenas", I18n.lang)
            } else {
                const r = puente.validarContrasenas(clave_admin, confirmacion_admin,
                                                    clave_ingeniero, confirmacion_ingeniero)
                for (const campo in r)
                    e[campo] = I18n.t(r[campo].clave, I18n.lang, r[campo].valores)
            }
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
            // M1: sin model_id; el puente lo calcula de estos datos
            equipment_class: clase,
            capacidad_litros: capacidadLitros,
            tipo_carga: tipoCarga,
            door_count: numPuertas,
            door_type: tipoPuerta,
            door_id: puertaPc,
            cooling_level: nivelEnfriamiento,
            vapor_source: fuenteVapor,           // E1b: generator | boiler | mixed
            supply_inputs: suministros,
            temperature_probes: sondas,
            // LIC-02: el puente las vuelve a validar y las guarda antes del perfil
            contrasenas: { clave_admin: clave_admin, confirmacion_admin: confirmacion_admin,
                           clave_ingeniero: clave_ingeniero, confirmacion_ingeniero: confirmacion_ingeniero }
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
        // M1: el nombre del modelo va arriba y en grande (resumenModelo); aquí, capacidad y carga primero
        { clave: "resumen_capacidad", valor: capacidadLitros > 0 ? I18n.t("instalacion.litros", I18n.lang, { n: capacidadLitros }) : "" },
        { clave: "resumen_carga", valor: tipoCarga !== "" ? I18n.t("instalacion.carga_" + tipoCarga, I18n.lang) : "" },
        { clave: "resumen_serie", valor: serie.trim().toUpperCase() },
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
        { clave: "resumen_sin_sonda", valor: _lista(clavesSonda, "sondas", "sonda_") },
        { clave: "resumen_contrasenas", valor: I18n.t("instalacion.resumen_contrasenas_fijadas", I18n.lang) }
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

                // ============ 4. Cámara (M1) ============
                Item {
                    objectName: "pasoCamara"
                    visible: !raiz.terminado && raiz.pasoActual === "camara"
                    x: lienzo.margen; y: lienzo.yPagina
                    width: lienzo.ancho; height: lienzo.altoPagina

                    CampoFormulario {
                        width: parent.width
                        etiqueta: I18n.t("instalacion.camara_capacidad", I18n.lang)
                        marcador: I18n.t("instalacion.camara_capacidad_marcador", I18n.lang)
                        valor: raiz.campoActivo === "capacidad" && raiz.teclado ? raiz.teclado.textoEnEdicion
                               : (raiz.capacidadLitros > 0 ? "" + raiz.capacidadLitros : "")
                        activo: raiz.campoActivo === "capacidad"
                        mensajeError: raiz.errores.capacidad ?? ""
                        nombreObjeto: "campoCapacidad"
                        nombreError: "errorCapacidad"
                        onTocado: raiz.editarCapacidad()
                    }
                    Ayuda {
                        y: Escala.px(136)
                        width: parent.width
                        text: I18n.t("instalacion.camara_capacidad_ayuda", I18n.lang)
                    }

                    Titulo { y: Escala.px(212); width: parent.width; text: I18n.t("instalacion.camara_carga", I18n.lang) }
                    SelectorSegmentos {
                        objectName: "selectorCarga"
                        y: Escala.px(264)
                        width: parent.width
                        valor: raiz.tipoCarga === "V" ? 1 : raiz.tipoCarga === "H" ? 2 : 0
                        opciones: [
                            { valor: 1, etiqueta: I18n.t("instalacion.carga_V", I18n.lang) },
                            { valor: 2, etiqueta: I18n.t("instalacion.carga_H", I18n.lang) }
                        ]
                        onElegido: n => { raiz.tipoCarga = n === 1 ? "V" : "H"; raiz.errores = ({}) }
                    }
                    ErrorTexto {
                        objectName: "errorTipoCarga"
                        y: Escala.px(364)
                        width: parent.width
                        text: raiz.errores.tipoCarga ?? ""
                    }

                    // Vista previa del nombre calculado (se actualiza en vivo; "—" si falta un dato)
                    Rectangle {
                        y: Escala.px(440)
                        width: parent.width
                        height: Escala.px(232)
                        radius: Escala.px(14)
                        color: Colores.fondoSutil
                        border.width: 1; border.color: Colores.bordeDivisor
                        Text {
                            x: Escala.px(28); y: Escala.px(28)
                            text: I18n.t("instalacion.camara_vista_previa", I18n.lang)
                            color: Colores.textoSecundario
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
                            font.weight: Tipografia.pesoMedium
                        }
                        Text {
                            objectName: "vistaPreviaModelo"
                            x: Escala.px(28); y: Escala.px(84)
                            width: parent.width - Escala.px(56)
                            text: raiz.modeloCalculado !== "" ? raiz.modeloCalculado : "—"
                            color: raiz.modeloCalculado !== "" ? Colores.textoPrimario : Colores.textoGuia
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(76)
                            font.weight: Tipografia.pesoBold
                            fontSizeMode: Text.HorizontalFit
                            minimumPixelSize: Escala.fuente(36)
                        }
                    }
                    Ayuda {
                        y: Escala.px(696)
                        width: parent.width
                        text: I18n.t("instalacion.camara_vista_previa_ayuda", I18n.lang)
                    }
                }

                // ============ 5. Enfriamiento ============
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

                // ============ 6. Fuente de vapor ============
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

                // ============ 7. Datos del equipo ============
                Item {
                    objectName: "pasoDatos"
                    visible: !raiz.terminado && raiz.pasoActual === "datos"
                    x: lienzo.margen; y: lienzo.yPagina
                    width: lienzo.ancho; height: lienzo.altoPagina

                    // M1: sin campo libre "Modelo" (el nombre se calcula en el paso Cámara)
                    Titulo { width: parent.width; text: I18n.t("instalacion.suministros_titulo", I18n.lang) }
                    Ayuda { y: Escala.px(44); width: parent.width; text: I18n.t("instalacion.suministros_ayuda", I18n.lang) }
                    Column {
                        y: Escala.px(122)
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

                    Titulo { y: Escala.px(590); width: parent.width; text: I18n.t("instalacion.sondas_titulo", I18n.lang) }
                    Ayuda { y: Escala.px(634); width: parent.width; text: I18n.t("instalacion.sondas_ayuda", I18n.lang) }
                    Column {
                        y: Escala.px(684)
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

                // ============ 8. Contraseñas (LIC-02) ============
                Item {
                    objectName: "pasoContrasenas"
                    visible: !raiz.terminado && raiz.pasoActual === "contrasenas"
                    x: lienzo.margen; y: lienzo.yPagina
                    width: lienzo.ancho; height: lienzo.altoPagina

                    Titulo { width: parent.width; text: I18n.t("instalacion.contrasenas_titulo", I18n.lang) }
                    Ayuda { y: Escala.px(44); width: parent.width; text: I18n.t("instalacion.contrasenas_ayuda", I18n.lang) }
                    Repeater {
                        model: raiz.camposContrasena
                        delegate: CampoFormulario {
                            required property string modelData
                            required property int index
                            y: Escala.px(150) + index * Escala.px(167)
                            width: parent.width
                            etiqueta: I18n.t("instalacion." + modelData, I18n.lang)
                            marcador: I18n.t("instalacion.clave_marcador", I18n.lang)
                            valor: raiz.textoCampo(modelData)
                            oculto: true
                            activo: raiz.campoActivo === modelData
                            mensajeError: raiz.errores[modelData] ?? ""
                            nombreObjeto: "campo_" + modelData
                            nombreError: "error_" + modelData
                            onTocado: raiz.editar(modelData, index < raiz.camposContrasena.length - 1
                                                  ? raiz.camposContrasena[index + 1] : "")
                        }
                    }
                }

                // ============ 9. Resumen ============
                Item {
                    objectName: "pasoResumen"
                    visible: !raiz.terminado && raiz.pasoActual === "resumen"
                    x: lienzo.margen; y: lienzo.yPagina
                    width: lienzo.ancho; height: lienzo.altoPagina

                    Titulo { width: parent.width; text: I18n.t("instalacion.resumen_titulo", I18n.lang) }

                    // M1 (INS-03): el nombre del modelo, arriba y en grande
                    Item {
                        id: bloqueModelo
                        y: Escala.px(56)
                        width: parent.width
                        height: Escala.px(132)
                        Text {
                            text: I18n.t("instalacion.resumen_modelo", I18n.lang)
                            color: Colores.textoSecundario
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(Tipografia.campoEtiquetaTam)
                            font.weight: Tipografia.pesoMedium
                        }
                        Text {
                            objectName: "resumenModelo"
                            y: Escala.px(36)
                            width: parent.width
                            text: raiz.modeloCalculado !== "" ? raiz.modeloCalculado : "—"
                            color: Colores.textoPrimario
                            font.family: Tipografia.familia
                            font.pixelSize: Escala.fuente(68)
                            font.weight: Tipografia.pesoBold
                            fontSizeMode: Text.HorizontalFit
                            minimumPixelSize: Escala.fuente(36)
                        }
                    }

                    Rectangle {
                        y: bloqueModelo.y + bloqueModelo.height + Escala.px(8)
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
                                    height: Math.max(Escala.px(64), valorFila.implicitHeight + Escala.px(24))
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
                        objectName: "textoListo"
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

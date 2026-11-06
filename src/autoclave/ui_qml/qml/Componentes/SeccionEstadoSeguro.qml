pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Tema
import Autoclave.I18n
import Autoclave.DetalleAviso

// U1 (tanda 2, 2026-10-19): avisos de seguridad, antes franja superior de E5.
// Mockup aprobado: docs/mis_plans/mockup_estado_seguro.png (3 estados).
// 1. Paro activo: fila de alarma alta "PARO DE EMERGENCIA — NO ABRIR", sin botón.
// 2. Paro liberado, estado seguro pendiente: fila de alarma, aviso naranja y
//    botón "Confirmar y llevar a estado seguro" (cualquier operador, sin sesión).
// 3. Estado seguro en curso: botón deshabilitado "En curso…" y "NO ABRIR hasta
//    que la cámara esté segura".
// Además (DECISIÓN SIN CONFIRMAR D-U1-2/D-U1-3): "NO ABRIR" con la cámara no
// segura y el MODO PRUEBA, como filas.
// U4 (tanda 2): componente compartido por el panel de la campana (por grupo),
// la tarjeta de alarmas de Preciclo y la de Ciclo en curso. Distingue módulo E/S
// desconectado y módulo E/S sin datos válidos del paro real (paroActivo = paro
// real; sin datos del módulo E/S no se afirma paro).
// Grupos (D3, nivel del catálogo): "emergencia" (sin conexión, módulo E/S, paro y
// estado seguro), "alarma" (NO ABRIR) y "aviso" (modo prueba); "" = todos.
// ESS-04 (28-oct): con `estadoSeguroSilencioso` del puente se ocultan las
// filas del estado 3 (y no cuentan en la campana); con `noAbrirPorSensor`, la
// fila NO ABRIR. El paro, la confirmación y la falta de datos nunca se ocultan.
Column {
    id: raiz
    property QtObject puente: null
    property QtObject comandos: null    // ComandosSistema
    property string grupo: ""

    // sin conexión con el backend el puente entrega paro/estado seguro en
    // false: se avisa que el estado de seguridad es desconocido (SAF-04 de U1)
    readonly property bool sinConexion: !(puente?.connected ?? true)
    readonly property string estadoModuloEs: puente?.estadoModuloEs ?? "ok"
    readonly property bool moduloEsDesconectada: !sinConexion && estadoModuloEs === "desconectada"
    readonly property bool moduloEsSinDatos: !sinConexion && estadoModuloEs === "sin_tramas_validas"
    readonly property bool sinDatos: sinConexion || moduloEsDesconectada || moduloEsSinDatos
    readonly property bool paro: puente?.paroActivo ?? false
    readonly property bool confirmar: (puente?.estadoSeguroRequiereConfirmacion ?? false) && !paro
    readonly property bool activoSinConfirmar: (puente?.estadoSeguroActivo ?? false) && !confirmar && !paro
    // ESS-04 (28-oct): con un sensor sin lectura como único motivo, el estado
    // seguro actúa en silencio: solo se ve la alarma del sensor («No abrir la
    // puerta»). Nunca con paro, confirmación pendiente o sin datos (falla
    // cerrada: sin el dato del puente, se muestra).
    readonly property bool silencio: activoSinConfirmar && !sinDatos
                                     && (puente?.estadoSeguroSilencioso ?? false) === true
    readonly property bool enCurso: activoSinConfirmar && !silencio
    // las filas sin datos ya dicen NO ABRIR: no se repite. ESS-04: tampoco
    // con el estado seguro activo (silencioso o no) ni si el motivo es solo
    // un sensor sin lectura
    readonly property bool noAbrir: (puente?.noAbrir ?? true) && !paro && !activoSinConfirmar && !sinDatos
                                    && (puente?.noAbrirPorSensor ?? false) !== true
    readonly property bool modoPrueba: puente?.modoPrueba ?? false
    // la petición de confirmar ya salió (ComandosSistema.ocupado)
    readonly property bool enviando: confirmar && (comandos?.ocupado ?? false)

    // filas por grupo (cuentan en la insignia de la campana y en los grupos)
    readonly property int conteoEmergencia: (paro || confirmar || enCurso ? 1 : 0) + (sinDatos ? 1 : 0)
    readonly property int conteoAlarma: noAbrir ? 1 : 0
    readonly property int conteoAviso: modoPrueba ? 1 : 0
    readonly property int conteoTotal: conteoEmergencia + conteoAlarma + conteoAviso
    // filas que muestra esta instancia
    readonly property int conteo: grupo === "emergencia" ? conteoEmergencia
                                : grupo === "alarma" ? conteoAlarma
                                : grupo === "aviso" ? conteoAviso : conteoTotal
    // insignia roja: paro real, confirmación pendiente o sin datos; parpadea
    // solo con el paro real o la confirmación pendiente (U4)
    readonly property bool urgente: paro || confirmar || sinDatos
    readonly property bool parpadeo: paro || confirmar

    function enGrupo(g) { return grupo === "" || grupo === g }

    // ALD (tanda 26): toda fila abre VentanaDetalleAlarma con un modelo armado
    // en Python (domain/detalle_aviso.py); la QML solo lo entrega. Sin botones
    // que cambien estado.
    property string claveDetalle: ""
    function _activa(clave) {
        switch (clave) {
        case "sin_conexion": return sinConexion
        case "modulo_es_desconectada": return moduloEsDesconectada
        case "modulo_es_sin_datos": return moduloEsSinDatos
        case "paro": return paro
        case "estado_seguro_pendiente": return confirmar
        case "estado_seguro_en_curso": return enCurso
        case "no_abrir": return (puente?.noAbrir ?? true) && !paro
        case "modo_prueba": return modoPrueba
        }
        return false
    }
    function abrirDetalle(clave) {
        claveDetalle = clave
        cargadorDetalle.active = true      // se crea la primera vez que se usa
        cargadorDetalle.item.abrirDesde(DetalleAviso.armar(clave, puente?.contextoAviso ?? ({})))
    }
    // con el dato vivo: valores nuevos mientras la ventana está abierta; si la
    // condición se fue, «Ya no está activa»
    function _refrescarDetalle() {
        const detalle = cargadorDetalle.item
        if (!detalle || !detalle.abierta || claveDetalle === "") return
        if (!_activa(claveDetalle)) { detalle.vigente = false; return }
        const d = DetalleAviso.armar(claveDetalle, puente?.contextoAviso ?? ({}))
        if (d && d.id) { detalle.datos = d; detalle.vigente = true }
    }
    Connections {
        target: raiz.puente
        ignoreUnknownSignals: true
        function onSeguridadChanged() { raiz._refrescarDetalle() }
    }
    // Fuera del posicionamiento de la columna (no ocupa lugar ni espacio); la
    // ventana se muestra sobre toda la aplicación al abrirse. Se carga solo al
    // tocar una fila (las secciones ocultas no crean ventanas).
    Item {
        visible: false
        width: 0; height: 0
        Loader {
            id: cargadorDetalle
            active: false
            anchors.fill: parent
            sourceComponent: VentanaDetalleAlarma {
                objectName: "detalleAvisoSeguridad"
            }
        }
    }

    width: parent ? parent.width : 0
    spacing: Escala.px(16)
    onVisibleChanged: if (!visible && cargadorDetalle.item) cargadorDetalle.item.cerrar()   // ALD

    component Nota: Rectangle {
        id: nota
        property string texto: ""
        property color fondo: Colores.fondoSeccion
        property color tinta: Colores.textoGuia
        property bool borde: false
        width: raiz.width
        height: textoNota.implicitHeight + Escala.px(32)
        radius: Escala.px(10)
        color: fondo
        Rectangle {
            visible: nota.borde
            width: Escala.px(8); height: parent.height; radius: Escala.px(3)
            color: Colores.advertencia
        }
        Text {
            id: textoNota
            x: Escala.px(24)
            width: parent.width - Escala.px(48)
            anchors.verticalCenter: parent.verticalCenter
            text: nota.texto
            color: nota.tinta
            wrapMode: Text.WordWrap
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(22)
        }
    }

    // ---- sin conexión con el backend: seguridad desconocida ----
    FilaAlarma {
        objectName: "filaSeguridadDesconocida"
        tocable: true     // ALD (tanda 26): abre el detalle
        onPulsada: raiz.abrirDetalle("sin_conexion")
        visible: raiz.sinConexion && raiz.enGrupo("emergencia")
        width: raiz.width
        multilinea: true
        prioridad: "alta"
        idAlarma: "SIN_CONEXION"
        descripcion: I18n.t("sistema.seguridad_desconocida", I18n.lang)
    }

    // ---- U4: módulo E/S desconectado / sin datos válidos (no afirma paro) ----
    FilaAlarma {
        objectName: "filaModuloEsDesconectada"
        tocable: true     // ALD (tanda 26): abre el detalle
        onPulsada: raiz.abrirDetalle("modulo_es_desconectada")
        visible: raiz.moduloEsDesconectada && raiz.enGrupo("emergencia")
        width: raiz.width
        multilinea: true
        prioridad: "alta"
        idAlarma: "TARJETA_DESCONECTADA"
        descripcion: I18n.t("sistema.modulo_es_desconectada", I18n.lang)
    }
    FilaAlarma {
        objectName: "filaModuloEsSinDatos"
        tocable: true     // ALD (tanda 26): abre el detalle
        onPulsada: raiz.abrirDetalle("modulo_es_sin_datos")
        visible: raiz.moduloEsSinDatos && raiz.enGrupo("emergencia")
        width: raiz.width
        multilinea: true
        prioridad: "alta"
        idAlarma: "TARJETA_SIN_DATOS"
        descripcion: I18n.t("sistema.modulo_es_sin_datos", I18n.lang)
    }

    // ---- 1. paro activo ----
    FilaAlarma {
        objectName: "filaParo"
        tocable: true     // ALD (tanda 26): abre el detalle
        onPulsada: raiz.abrirDetalle("paro")
        visible: raiz.paro && raiz.enGrupo("emergencia")
        width: raiz.width
        multilinea: true
        prioridad: "alta"
        idAlarma: "PARO_EMERGENCIA"
        descripcion: I18n.t("sistema.paro_no_abrir", I18n.lang)
    }
    Nota {
        visible: raiz.paro && raiz.enGrupo("emergencia")
        texto: I18n.t("sistema.paro_suelte", I18n.lang)
    }

    // ---- 2. paro liberado: confirmación pendiente ----
    FilaAlarma {
        objectName: "filaEstadoSeguroPendiente"
        tocable: true     // ALD (tanda 26): abre el detalle
        onPulsada: raiz.abrirDetalle("estado_seguro_pendiente")
        visible: raiz.confirmar && raiz.enGrupo("emergencia")
        width: raiz.width
        multilinea: true
        prioridad: "alta"
        idAlarma: "ESTADO_SEGURO_PENDIENTE"
        descripcion: I18n.t("sistema.estado_seguro_pendiente", I18n.lang)
    }
    Nota {
        objectName: "avisoParoLiberado"
        visible: raiz.confirmar && raiz.enGrupo("emergencia")
        borde: true
        fondo: Colores.advertenciaFondo
        tinta: Colores.advertenciaTexto
        texto: I18n.t("sistema.paro_liberado", I18n.lang)
    }

    // ---- 3. estado seguro en curso ----
    FilaAlarma {
        objectName: "filaEstadoSeguroEnCurso"
        tocable: true     // ALD (tanda 26): abre el detalle
        onPulsada: raiz.abrirDetalle("estado_seguro_en_curso")
        visible: raiz.enCurso && raiz.enGrupo("emergencia")
        width: raiz.width
        multilinea: true
        prioridad: "media"
        idAlarma: "ESTADO_SEGURO"
        descripcion: I18n.t("sistema.estado_seguro_en_curso", I18n.lang)
    }
    // S9 (tanda 9, D9-1.2): por qué corre (arranque tras un ciclo interrumpido, A9,
    // fallo, cancelación o fin de ciclo). Nunca dice "paro liberado": ese
    // texto solo sale con la confirmación pendiente (estado 2).
    readonly property string causa: puente?.estadoSeguroCausa ?? ""
    readonly property string claveCausa: causa !== "" && causa !== "paro_liberado"
                                         ? "sistema.estado_seguro_causa_" + causa : ""
    Nota {
        objectName: "avisoCausaEstadoSeguro"
        visible: raiz.enCurso && raiz.claveCausa !== "" && raiz.enGrupo("emergencia")
        texto: raiz.claveCausa !== "" ? I18n.t(raiz.claveCausa, I18n.lang) : ""
    }
    // A10 (tanda 28): qué le falta para terminar, para que no parezca
    // colgado: «En pausa: modo prueba activo» o el motivo pendiente con su
    // valor y su límite (texto armado en domain/detalle_aviso.py)
    readonly property string textoEspera: raiz.enCurso
                                          ? DetalleAviso.textoEspera(puente?.contextoAviso ?? ({}), I18n.lang) : ""
    Nota {
        objectName: "avisoEsperaEstadoSeguro"
        visible: raiz.enCurso && raiz.textoEspera !== "" && raiz.enGrupo("emergencia")
        texto: raiz.textoEspera
    }

    // Botón de los estados 2 y 3: azul y habilitado solo con la confirmación
    // pendiente y sin petición en vuelo
    // T21 (FC-10): el botón ocupa todo el ancho de la sección; si el texto
    // («Confirmar y llevar a estado seguro») no cabe, la letra baja
    // (HorizontalFit) hasta Escala.fuenteMinima. Nunca se recorta (D8-5.4).
    Rectangle {
        id: botonConfirmar
        objectName: "botonConfirmarEstadoSeguro"
        visible: (raiz.confirmar || raiz.enCurso) && raiz.enGrupo("emergencia")
        readonly property bool habilitado: raiz.confirmar && !raiz.enviando
        width: raiz.width
        height: Escala.px(96)
        radius: height / 2
        color: Colores.accionPrimario
        opacity: habilitado ? 1.0 : 0.85
        Row {
            id: filaConfirmar
            anchors.centerIn: parent
            spacing: Escala.px(16)
            BusyIndicator {
                id: indicadorEnCurso
                objectName: "indicadorEnCurso"
                visible: (raiz.enCurso || raiz.enviando) && raiz.enGrupo("emergencia")
                running: visible
                width: Escala.px(48); height: width
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                objectName: "textoConfirmarEstadoSeguro"
                anchors.verticalCenter: parent.verticalCenter
                // ancho útil: el del botón menos el radio de cada lado y el indicador
                width: Math.min(implicitWidth, botonConfirmar.width - botonConfirmar.height
                                - (indicadorEnCurso.visible ? indicadorEnCurso.width + filaConfirmar.spacing : 0))
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: Escala.fuenteMinima
                text: (raiz.enCurso || raiz.enviando)
                      ? I18n.t("sistema.estado_seguro_en_curso_boton", I18n.lang)
                      : I18n.t("sistema.confirmar_estado_seguro", I18n.lang)
                color: Colores.textoSobreAccion
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: Escala.fuente(28)
            }
        }
        MouseArea {
            anchors.fill: parent
            enabled: parent.habilitado
            onClicked: raiz.comandos?.confirmarEstadoSeguro()
        }
    }
    Text {
        visible: raiz.confirmar && !raiz.enviando && raiz.enGrupo("emergencia")
        width: raiz.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: I18n.t("sistema.confirmar_sin_sesion", I18n.lang)
        color: Colores.textoGuia
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(20)
    }
    Text {
        objectName: "notaNoAbrirEnCurso"
        visible: (raiz.enCurso || raiz.enviando) && raiz.enGrupo("emergencia")
        width: raiz.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: I18n.t("sistema.no_abrir_hasta_segura", I18n.lang)
        color: Colores.textoGuia
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(20)
    }
    // S4 (CIC-10, opciones A + B): el estado seguro no puede terminar solo.
    // Indica qué hacer y abre la asignación de sondas (técnico/ingeniero, con
    // su login). "NO ABRIR" sigue vigente; no hay forma de declarar la cámara
    // segura a mano (opción C descartada).
    readonly property string bloqueoMotivo: puente?.estadoSeguroBloqueadoMotivo ?? ""
    // V8b (D8-5.11): el motivo en el idioma vigente (catálogo); si el backend
    // manda uno desconocido, el texto tal cual
    readonly property string bloqueoClave: puente?.estadoSeguroBloqueadoClave ?? ""
    readonly property string bloqueoTexto: bloqueoClave !== "" && I18n.existe(bloqueoClave, I18n.lang)
                                           ? I18n.t(bloqueoClave, I18n.lang) : bloqueoMotivo
    // el botón solo ayuda si el motivo es el sensor Principal (no el tiempo límite con líquido)
    // ESS-04 (DECISIÓN SIN CONFIRMAR): en silencio el botón pasa al detalle
    // de la alarma del Principal (SEN-02/SEN-03, VentanaDetalleAlarma)
    readonly property bool bloqueoPorSonda: puente?.estadoSeguroBloqueoPorSonda ?? false
    Nota {
        objectName: "avisoEstadoSeguroDetenido"
        visible: raiz.bloqueoMotivo !== "" && raiz.enCurso && raiz.enGrupo("emergencia")
        borde: true
        fondo: Colores.advertenciaFondo
        tinta: Colores.advertenciaTexto
        texto: raiz.bloqueoTexto + (raiz.bloqueoPorSonda
               ? ". " + I18n.t("sistema.estado_seguro_detenido_accion", I18n.lang) : ".")
    }
    Rectangle {
        objectName: "botonAsignarSonda"
        visible: raiz.bloqueoPorSonda && raiz.enCurso && raiz.enGrupo("emergencia")
        width: raiz.width
        height: Escala.px(80)
        radius: height / 2
        color: Colores.accionPrimario
        Text {
            objectName: "textoAsignarSonda"
            anchors.centerIn: parent
            width: Math.min(implicitWidth, parent.width - parent.height)
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: Escala.fuenteMinima
            text: I18n.t("sistema.asignar_sonda_principal", I18n.lang)
            color: Colores.textoSobreAccion
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoBold
            font.pixelSize: Escala.fuente(24)
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.comandos?.asignarSondaPrincipal() }
    }
    // rechazo del backend (p. ej. sin conexión o estado cambiado)
    Text {
        objectName: "mensajeConfirmar"
        visible: raiz.confirmar && !raiz.enviando && (raiz.comandos?.mensaje ?? "") !== ""
                 && raiz.enGrupo("emergencia")
        width: raiz.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: raiz.comandos?.mensaje ?? ""
        color: Colores.advertenciaTexto
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(20)
    }

    // ---- cámara no segura (fuera del paro y del estado seguro) ----
    FilaAlarma {
        objectName: "filaNoAbrir"
        tocable: true     // ALD (tanda 26): abre el detalle
        onPulsada: raiz.abrirDetalle("no_abrir")
        visible: raiz.noAbrir && raiz.enGrupo("alarma")
        width: raiz.width
        multilinea: true
        prioridad: "media"
        idAlarma: "NO_ABRIR"
        descripcion: {
            const motivo = raiz.puente?.noAbrirMotivo ?? ""
            const base = I18n.t("sistema.no_abrir", I18n.lang)
            return motivo !== "" ? base + " — " + motivo : base
        }
    }

    // ---- modo prueba (indicador permanente mientras dure) ----
    FilaAlarma {
        objectName: "filaModoPrueba"
        tocable: true     // ALD (tanda 26): abre el detalle
        onPulsada: raiz.abrirDetalle("modo_prueba")
        visible: raiz.modoPrueba && raiz.enGrupo("aviso")
        width: raiz.width
        multilinea: true
        prioridad: "baja"
        idAlarma: "MODO_PRUEBA"
        descripcion: I18n.t("sistema.modo_prueba", I18n.lang)
    }
}

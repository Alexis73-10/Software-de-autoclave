pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Tema
import Autoclave.I18n

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
// la tarjeta de alarmas de Preciclo y la de Ciclo en curso. Distingue tarjeta
// desconectada y tarjeta sin datos válidos del paro real (paroActivo = paro
// real; sin datos de la tarjeta no se afirma paro).
// Grupos (D3, nivel del catálogo): "emergencia" (sin conexión, tarjeta, paro y
// estado seguro), "alarma" (NO ABRIR) y "aviso" (modo prueba); "" = todos.
Column {
    id: raiz
    property QtObject puente: null
    property QtObject comandos: null    // ComandosSistema
    property string grupo: ""

    // sin conexión con el backend el puente entrega paro/estado seguro en
    // false: se avisa que el estado de seguridad es desconocido (SAF-04 de U1)
    readonly property bool sinConexion: !(puente?.connected ?? true)
    readonly property string estadoTarjeta: puente?.estadoTarjeta ?? "ok"
    readonly property bool tarjetaDesconectada: !sinConexion && estadoTarjeta === "desconectada"
    readonly property bool tarjetaSinDatos: !sinConexion && estadoTarjeta === "sin_tramas_validas"
    readonly property bool sinDatos: sinConexion || tarjetaDesconectada || tarjetaSinDatos
    readonly property bool paro: puente?.paroActivo ?? false
    readonly property bool confirmar: (puente?.estadoSeguroRequiereConfirmacion ?? false) && !paro
    readonly property bool enCurso: (puente?.estadoSeguroActivo ?? false) && !confirmar && !paro
    // las filas sin datos ya dicen NO ABRIR: no se repite
    readonly property bool noAbrir: (puente?.noAbrir ?? true) && !paro && !enCurso && !sinDatos
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

    width: parent ? parent.width : 0
    spacing: Escala.px(16)

    component Nota: Rectangle {
        id: nota
        property string texto: ""
        property color fondo: "#F2F2F2"
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
        visible: raiz.sinConexion && raiz.enGrupo("emergencia")
        width: raiz.width
        multilinea: true
        prioridad: "alta"
        idAlarma: "SIN_CONEXION"
        descripcion: I18n.t("sistema.seguridad_desconocida", I18n.lang)
    }

    // ---- U4: tarjeta desconectada / sin datos válidos (no afirma paro) ----
    FilaAlarma {
        objectName: "filaTarjetaDesconectada"
        visible: raiz.tarjetaDesconectada && raiz.enGrupo("emergencia")
        width: raiz.width
        multilinea: true
        prioridad: "alta"
        idAlarma: "TARJETA_DESCONECTADA"
        descripcion: I18n.t("sistema.tarjeta_desconectada", I18n.lang)
    }
    FilaAlarma {
        objectName: "filaTarjetaSinDatos"
        visible: raiz.tarjetaSinDatos && raiz.enGrupo("emergencia")
        width: raiz.width
        multilinea: true
        prioridad: "alta"
        idAlarma: "TARJETA_SIN_DATOS"
        descripcion: I18n.t("sistema.tarjeta_sin_datos", I18n.lang)
    }

    // ---- 1. paro activo ----
    FilaAlarma {
        objectName: "filaParo"
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
        visible: raiz.enCurso && raiz.enGrupo("emergencia")
        width: raiz.width
        multilinea: true
        prioridad: "media"
        idAlarma: "ESTADO_SEGURO"
        descripcion: I18n.t("sistema.estado_seguro_en_curso", I18n.lang)
    }
    // S9 (tanda 9, D9-1.2): por qué corre (arranque con la cámara no segura,
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
                color: "white"
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
            color: "white"
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
        visible: raiz.modoPrueba && raiz.enGrupo("aviso")
        width: raiz.width
        multilinea: true
        prioridad: "baja"
        idAlarma: "MODO_PRUEBA"
        descripcion: I18n.t("sistema.modo_prueba", I18n.lang)
    }
}

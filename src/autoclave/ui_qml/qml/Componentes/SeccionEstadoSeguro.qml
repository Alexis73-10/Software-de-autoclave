pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import Tema
import Autoclave.I18n

// U1 (tanda 2, 2026-10-19): avisos de seguridad dentro del panel de la campana,
// en lugar de la franja superior de E5. Mockup aprobado:
// docs/mis_plans/mockup_estado_seguro.png (3 estados).
// 1. Paro activo: fila de alarma alta "PARO DE EMERGENCIA — NO ABRIR", sin botón.
// 2. Paro liberado, estado seguro pendiente: fila de alarma, aviso naranja y
//    botón "Confirmar y llevar a estado seguro" (cualquier operador, sin sesión).
// 3. Estado seguro en curso: botón deshabilitado "En curso…" y "NO ABRIR hasta
//    que la cámara esté segura".
// Además (DECISIÓN SIN CONFIRMAR D-U1-2/D-U1-3): "NO ABRIR" con la cámara no
// segura y el MODO PRUEBA, como filas del mismo panel.
// Sin conexión, el puente entrega noAbrir = true (falla cerrada).
Column {
    id: raiz
    property QtObject puente: null
    property QtObject comandos: null    // ComandosSistema

    // sin conexión el puente entrega paro/estado seguro en false: se avisa que
    // el estado de seguridad es desconocido (revisión U1, SAF-04)
    readonly property bool sinConexion: !(puente?.connected ?? true)
    readonly property bool paro: puente?.paroActivo ?? false
    readonly property bool confirmar: (puente?.estadoSeguroRequiereConfirmacion ?? false) && !paro
    readonly property bool enCurso: (puente?.estadoSeguroActivo ?? false) && !confirmar && !paro
    readonly property bool noAbrir: (puente?.noAbrir ?? true) && !paro && !enCurso
    readonly property bool modoPrueba: puente?.modoPrueba ?? false
    // la petición de confirmar ya salió (ComandosSistema.ocupado)
    readonly property bool enviando: confirmar && (comandos?.ocupado ?? false)
    // filas de esta sección (cuentan en la insignia de la campana)
    readonly property int conteo: (paro || confirmar || enCurso ? 1 : 0) + (sinConexion ? 1 : 0)
                                  + (noAbrir ? 1 : 0) + (modoPrueba ? 1 : 0)
    // la insignia debe verse en rojo (y parpadear con la confirmación pendiente)
    readonly property bool urgente: paro || confirmar

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

    // ---- sin conexión: estado de paro y de estado seguro desconocido ----
    FilaAlarma {
        objectName: "filaSeguridadDesconocida"
        visible: raiz.sinConexion
        width: raiz.width
        multilinea: true
        prioridad: "alta"
        idAlarma: "SIN_CONEXION"
        descripcion: I18n.t("sistema.seguridad_desconocida", I18n.lang)
    }

    // ---- 1. paro activo ----
    FilaAlarma {
        objectName: "filaParo"
        visible: raiz.paro
        width: raiz.width
        multilinea: true
        prioridad: "alta"
        idAlarma: "PARO_EMERGENCIA"
        descripcion: I18n.t("sistema.paro_no_abrir", I18n.lang)
    }
    Nota {
        visible: raiz.paro
        texto: I18n.t("sistema.paro_suelte", I18n.lang)
    }

    // ---- 2. paro liberado: confirmación pendiente ----
    FilaAlarma {
        objectName: "filaEstadoSeguroPendiente"
        visible: raiz.confirmar
        width: raiz.width
        multilinea: true
        prioridad: "alta"
        idAlarma: "ESTADO_SEGURO_PENDIENTE"
        descripcion: I18n.t("sistema.estado_seguro_pendiente", I18n.lang)
    }
    Nota {
        objectName: "avisoParoLiberado"
        visible: raiz.confirmar
        borde: true
        fondo: Colores.advertenciaFondo
        tinta: Colores.advertenciaTexto
        texto: I18n.t("sistema.paro_liberado", I18n.lang)
    }

    // ---- 3. estado seguro en curso ----
    FilaAlarma {
        objectName: "filaEstadoSeguroEnCurso"
        visible: raiz.enCurso
        width: raiz.width
        multilinea: true
        prioridad: "media"
        idAlarma: "ESTADO_SEGURO"
        descripcion: I18n.t("sistema.estado_seguro_en_curso", I18n.lang)
    }

    // Botón de los estados 2 y 3: azul y habilitado solo con la confirmación
    // pendiente y sin petición en vuelo
    Rectangle {
        objectName: "botonConfirmarEstadoSeguro"
        visible: raiz.confirmar || raiz.enCurso
        readonly property bool habilitado: raiz.confirmar && !raiz.enviando
        width: raiz.width
        height: Escala.px(96)
        radius: height / 2
        color: Colores.accionPrimario
        opacity: habilitado ? 1.0 : 0.85
        Row {
            anchors.centerIn: parent
            spacing: Escala.px(16)
            BusyIndicator {
                objectName: "indicadorEnCurso"
                visible: raiz.enCurso || raiz.enviando
                running: visible
                width: Escala.px(48); height: width
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
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
        visible: raiz.confirmar && !raiz.enviando
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
        visible: raiz.enCurso || raiz.enviando
        width: raiz.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: I18n.t("sistema.no_abrir_hasta_segura", I18n.lang)
        color: Colores.textoGuia
        font.family: Tipografia.familia
        font.pixelSize: Escala.fuente(20)
    }
    // rechazo del backend (p. ej. sin conexión o estado cambiado)
    Text {
        objectName: "mensajeConfirmar"
        visible: raiz.confirmar && !raiz.enviando && (raiz.comandos?.mensaje ?? "") !== ""
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
        visible: raiz.noAbrir
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
        visible: raiz.modoPrueba
        width: raiz.width
        multilinea: true
        prioridad: "baja"
        idAlarma: "MODO_PRUEBA"
        descripcion: I18n.t("sistema.modo_prueba", I18n.lang)
    }
}

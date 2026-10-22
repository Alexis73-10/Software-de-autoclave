import QtQuick
import QtQuick.Effects
import Tema
import "../Componentes"
import "../../../images"   // IconoEjecucion.qml (engranaje + flechas animados)
import Autoclave.I18n

// Pantalla de ciclo en curso (docs/mis_plans/planeacion_pantalla_ciclo_en_curso.md).
// Referencia: images/pantalla_ciclo_con_grafica_editada.png (1196 x 1917).
//
// Geometría: px del mockup pasados por m() (escala uniforme con el ancho, igual
// que PantallaPreciclo.qml). El alto es flexible (Escala.altoLienzo): lo que está por
// encima de la gráfica queda fijo arriba, lo que está por debajo se ancla abajo
// (yb()) y la tarjeta de la gráfica absorbe la diferencia (plan §11).
// Cabecera, tarjeta de ciclo, tarjeta de parámetros y barra inferior replican
// la geometría de PantallaPreciclo.qml (tarjeta de parámetros desplazada +151 px);
// PENDIENTE (Fase 5): extraer las partes comunes al renombrar PantallaPreciclo.qml.
//
// Datos: tarjeta de ciclo y de parámetros, alarmas y conexión desde UiBridge
// (mismas propiedades y formatos que PantallaPreciclo.qml); fases, tiempos y gráfica desde
// ProgresoCiclo (bridge/progreso_ciclo.py), que solo consulta mientras esta
// pantalla está visible. qml/Pruebas/PruebaCicloEnCurso.qml asigna datos de
// ejemplo directamente.
// Comandos (ComandosCicloEnCurso): CANCELAR CICLO con diálogo de confirmación;
// al terminar el ciclo (resultado del backend) el botón pasa a CONFIRMAR, que
// envía /cycle/acknowledge; nunca se confirma solo (decisión de Cristian,
// 2026-10-01: un fallo no debe salir de FALLA sin que alguien lo vea). La
// navegación de entrada y salida la decide Main.qml con el estado de la máquina.
Item {
    id: raiz

    property QtObject puente: null     // UiBridge (solo lectura)
    property QtObject progreso: null   // ProgresoCiclo (solo lectura)
    property QtObject comandos: null   // ComandosCicloEnCurso (cancelar / confirmar)
    property QtObject infoEquipo: null
    // ComandosSistema (E5): Apagar equipo en el panel de equipo
    property QtObject comandosSistema: null

    // ---- datos ----
    // "?." evita TypeError si no hay puente o al destruir la pantalla.
    property bool datosVigentes: puente?.connected ?? false
    // U4 (tanda 2): estado de la tarjeta de E/S; solo cambia textos y avisos
    readonly property string estadoTarjeta: puente?.estadoTarjeta ?? "ok"
    property string cicloActivo: puente?.cicloActivo ?? ""
    property string programa: puente?.programa ?? ""
    property string tempEsterilizacion: puente?.tempEsterilizacion ?? ""
    property string tiempoEsterilizacion: puente?.tiempoEsterilizacion ?? ""
    property string tiempoSecado: puente?.tiempoSecado ?? ""
    // lecturas en vivo: sin conexión se muestran "—" (plan §15.8)
    property string tempCamara: datosVigentes ? (puente?.tempCamara ?? "") : ""
    property string tempReferencia: datosVigentes ? (puente?.tempReferencia ?? "") : ""
    property string presionCamara: datosVigentes ? (puente?.presionCamara ?? "") : ""
    // O3 (tanda 6): entradas mostradas del programa; sin puente, las tres de siempre
    property var entradas: puente?.entradasMostradas ?? [
        { clave: "temp_camara", tipo: "temp", valor: tempCamara, unidad: textos.unidadTemp },
        { clave: "temp_referencia", tipo: "temp", valor: tempReferencia, unidad: textos.unidadTemp },
        { clave: "pres_camara", tipo: "pres", valor: presionCamara, unidad: textos.unidadPresion },
    ]
    property var seriesGrafica: puente?.seriesGrafica ?? null
    property var alarmas: puente?.alarms ?? null
    // alarmas activas más los avisos de seguridad del panel (U1 de la tanda 2)
    property int conteoNotificaciones: panelNotificaciones.conteoTotal
    property string modelo: infoEquipo?.modelo ?? ""
    property string serie: infoEquipo?.serie ?? ""
    property string version: I18n.t("app.version", I18n.lang)
    // [{fase, estado, duracion_s}] de las fases que aplican
    property var fases: progreso?.fases ?? []
    // segundos (reloj monotónico del backend); restanteS null = no estimable;
    // sin conexión no se muestran (quedarían congelados)
    property var transcurridoS: datosVigentes ? (progreso?.transcurridoS ?? null) : null
    property var restanteS: datosVigentes ? (progreso?.restanteS ?? null) : null
    // gráfica: ver GraficaCiclo.datos / fases
    property var datosGrafica: progreso?.datosGrafica ?? ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
    property var fasesGrafica: progreso?.fasesGrafica ?? []
    property real tiempoActualMin: progreso?.tiempoActualMin ?? 0
    property real cursorMin: NaN
    property bool pantallaCompleta: false
    // U4 (revisión SAF-02): la gráfica a pantalla completa tapa la tarjeta de
    // seguridad superpuesta y la campana; un aviso crítico la cierra
    // SAF-04 de la revisión S2b (D8-2.16): "CARGA NO ESTÉRIL" tampoco queda
    // tapada por la gráfica a pantalla completa
    readonly property bool avisoCritico: seguridadCiclo.conteo > 0 || cargaNoEsteril
    onAvisoCriticoChanged: if (avisoCritico) pantallaCompleta = false
    onPantallaCompletaChanged: if (pantallaCompleta && avisoCritico) pantallaCompleta = false
    // "" mientras el ciclo corre; "exitoso" / "cancelado" / "fallo" al terminar
    property string resultado: progreso?.resultado ?? ""
    readonly property bool terminado: resultado !== ""
    // D8-2.16: todo ciclo terminado que no fue COMPLETADO (falla segura)
    readonly property bool cargaNoEsteril: terminado && resultado !== "exitoso"
    property bool comandoOcupado: comandos?.ocupado ?? false
    property string errorComando: comandos?.error ?? ""
    // D8-2.15 (tanda 8): clave del catálogo del aviso de una cancelación
    // aceptada en espera de los datos de la tarjeta ("" = sin aviso)
    property string avisoCancelacion: comandos?.aviso ?? ""
    onAvisoCancelacionChanged: if (avisoCancelacion !== "") avisoComando.abrir()

    // ProgresoCiclo solo consulta el backend mientras esta pantalla se ve
    Binding {
        target: raiz.progreso
        when: raiz.progreso !== null
        property: "activo"
        value: raiz.visible
    }

    // ---- acciones: las resuelve quien usa la pantalla (Fase 4) ----
    signal campanaPulsada()
    signal ajustesPulsado()
    signal avatarPulsado()
    signal equipoPulsado()
    signal cancelarPulsado()      // tras confirmar en el diálogo
    signal confirmarPulsado()
    signal tiemposPulsado()
    signal pantallaCompletaPulsado()

    function sinLectura(valor) { return valor !== "" ? valor : I18n.t("sistema.sin_lectura", I18n.lang) }

    // HH:MM:SS de segundos ya medidos por el backend; null -> "—"
    function formatoReloj(seg) {
        if (seg === null || seg === undefined || !isFinite(seg))
            return I18n.t("sistema.sin_lectura", I18n.lang)
        const s = Math.max(0, Math.floor(seg))
        const dos = n => n < 10 ? "0" + n : "" + n
        return dos(Math.floor(s / 3600)) + ":" + dos(Math.floor(s % 3600 / 60)) + ":" + dos(s % 60)
    }
    readonly property real fraccionProgreso: {
        const t = raiz.transcurridoS, r = raiz.restanteS
        if (t === null || t === undefined || r === null || r === undefined || t + r <= 0)
            return 0
        return Math.max(0, Math.min(1, t / (t + r)))
    }

    readonly property QtObject textos: QtObject {
        readonly property string cicloActivo: I18n.t("ciclo.activo", I18n.lang)
        readonly property string programa: I18n.t("ciclo.programa", I18n.lang)
        readonly property string estado: I18n.t("ciclo.estado", I18n.lang)
        readonly property string enEjecucion: I18n.t("estados.ejecutando", I18n.lang)
        readonly property string tempEster: I18n.t("ciclo.temp_ester", I18n.lang)
        readonly property string tiempoEst: I18n.t("ciclo.tiempo_est", I18n.lang)
        readonly property string tiempoSec: I18n.t("ciclo.tiempo_sec", I18n.lang)
        readonly property string tempCamara: I18n.t("ciclo.temp_camara", I18n.lang)
        readonly property string tempReferencia: I18n.t("ciclo.temp_referencia", I18n.lang)
        readonly property string presion: I18n.t("ciclo.presion", I18n.lang)
        readonly property string unidadTemp: raiz.puente?.tempUnidad || I18n.t("unidades.temperatura", I18n.lang)   // I2: unidad elegida (U1)
        readonly property string unidadTiempo: I18n.t("unidades.tiempo", I18n.lang)
        readonly property string unidadPresion: raiz.puente?.presionUnidad || I18n.t("unidades.presion", I18n.lang)
        readonly property string transcurrido: I18n.t("ciclo.tiempo_transcurrido", I18n.lang)
        readonly property string restante: I18n.t("ciclo.tiempo_restante", I18n.lang)
        readonly property string cancelar: I18n.t("ciclo.cancelar", I18n.lang)
        readonly property string modelo: I18n.t("ciclo.modelo", I18n.lang)
        readonly property string serie: I18n.t("ciclo.serie", I18n.lang)
    }

    // Colores medidos sobre el mockup (los compartidos con PantallaPreciclo.qml, iguales).
    // PENDIENTE: promover a Tema/Colores.qml cuando el diseñador los confirme.
    readonly property QtObject paleta: QtObject {
        readonly property color negro: "#000000"
        readonly property color programa: "#000209"
        readonly property color verdeEjecutando: "#25BA9E"
        readonly property color naranjaTexto: "#EC9233"
        readonly property color naranjaEstado: "#FF962B"
        readonly property color confirmarArriba: "#08AA41"   // = INICIAR CICLO de PantallaPreciclo.qml
        readonly property color confirmarAbajo: "#01501E"
        readonly property color insignia: "#08C9F9"
        readonly property color bordeTarjeta: "#E5E5E5"
        readonly property color bordeSuave: "#F5F5F5"
        readonly property color divisorCiclo: "#C0C0C0"
        readonly property color divisorParam: "#C3C3C3"
        readonly property color divisorPie: "#BEBEBE"
        readonly property color etiqueta: "#393939"
        readonly property color unidad: "#424242"
        readonly property color textoPie: "#3B3B3B"
        readonly property color versionTexto: "#8F8F8F"
        readonly property color avatarFondo: "#E6E6E6"
        readonly property color iconoGris: "#808080"
        readonly property color reloj: "#383838"
        readonly property color rotuloReloj: "#3E3E3E"
        readonly property color pistaProgreso: "#DEE4EC"
        readonly property color progresoInicio: "#04439B"
        readonly property color progresoFin: "#0BB8FA"
        readonly property color cancelarArriba: "#F40000"
        readonly property color cancelarAbajo: "#870004"
    }

    readonly property string fuenteNumeros: "Arial"   // como PantallaPreciclo.qml (PC-03)

    readonly property real anchoMockup: 1196
    readonly property real altoMockup: 1917
    function m(v) { return v * raiz.width / anchoMockup }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    // alto sobrante respecto al mockup; lo absorbe la gráfica
    readonly property real extra: raiz.height - m(altoMockup)
    function yb(v) { return m(v) + extra }

    readonly property string iconosColor: "../../assets/iconos/color/"
    readonly property string imagenes: "../../../images/"

    // Texto por línea base (bl) y centro (cx) o borde izquierdo (lx), en px del
    // mockup; abajo = true ancla la línea base al borde inferior (yb).
    component Texto: Text {
        property real cx: -1
        property real lx: -1
        property real bl: 0
        property real tam: 16
        property bool abajo: false
        font.pixelSize: raiz.fuente(tam)
        x: lx >= 0 ? raiz.m(lx) : raiz.m(cx) - width / 2
        y: (abajo ? raiz.yb(bl) : raiz.m(bl)) - baselineOffset
    }

    // Icono SVG de 48x48 cuya tinta llena la caja del mockup (como PantallaPreciclo.qml).
    component Icono: Image {
        property var caja: [0, 0, 0, 0]
        property var tinta: [0, 0, 48, 48]
        property bool abajo: false
        readonly property real _escala: raiz.m(caja[3]) / (tinta[3] - tinta[1])
        width: 48 * _escala
        height: width
        x: raiz.m(caja[0] + caja[2] / 2) - (tinta[0] + tinta[2]) / 2 * _escala
        y: (abajo ? raiz.yb(caja[1]) : raiz.m(caja[1])) - tinta[1] * _escala
        sourceSize.width: width
        sourceSize.height: height
    }

    component IconoTenido: Item {
        id: tenido
        property alias caja: fuenteIcono.caja
        property alias tinta: fuenteIcono.tinta
        property alias source: fuenteIcono.source
        property color color: "white"
        anchors.fill: parent
        Icono { id: fuenteIcono; visible: false }
        MultiEffect {
            x: fuenteIcono.x; y: fuenteIcono.y; width: fuenteIcono.width; height: fuenteIcono.height
            source: fuenteIcono
            colorization: 1.0
            colorizationColor: tenido.color
        }
    }

    component Divisor: Rectangle {
        property real cx: 0
        property real y0: 0
        property real y1: 0
        property bool abajo: false
        x: raiz.m(cx - 1); y: abajo ? raiz.yb(y0) : raiz.m(y0)
        width: raiz.m(2); height: raiz.m(y1 - y0)
    }

    // ======================= fondo =======================
    FondoApp { anchors.fill: parent }

    // ======================= cabecera (= PantallaPreciclo.qml) =======================
    Image {
        x: raiz.m(73); y: raiz.m(57)
        width: raiz.m(267)
        height: width * 42427 / 158611
        source: "../../assets/logo/logo-especifika-blanco.svg"
        sourceSize.width: width
        sourceSize.height: height
    }

    Item {
        id: reloj
        anchors.fill: parent
        // reloj del sistema: solo para mostrar la hora (no es tiempo de proceso)
        readonly property var _meses: I18n.valor("fecha.meses", I18n.lang) || []
        property date _ahora: new Date()
        Timer { interval: 1000; running: true; repeat: true; onTriggered: reloj._ahora = new Date() }
        function _dosDigitos(n) { return n < 10 ? "0" + n : "" + n }

        Texto {
            cx: 597.5; bl: 108; tam: 97
            text: reloj._dosDigitos(reloj._ahora.getHours()) + ":" +
                  reloj._dosDigitos(reloj._ahora.getMinutes())
            color: "white"
            font.family: Tipografia.familiaReloj
            font.weight: Tipografia.pesoBold
        }
        Texto {
            cx: 598; bl: 141; tam: 26
            text: reloj._ahora.getDate() + " " +
                  (reloj._meses[reloj._ahora.getMonth()] ?? "") + "  -  " +
                  reloj._ahora.getFullYear()
            color: "white"
            font.family: Tipografia.familiaReloj
        }
    }

    Item {
        anchors.fill: parent
        Icono {
            caja: [888, 64, 51, 57]; tinta: [5.85, 4.0, 42.15, 44.0]
            source: raiz.iconosColor + "campana.svg"
        }
        InsigniaCampana {
            objectName: "insigniaCampana"
            x: raiz.m(922); y: raiz.m(50)
            width: raiz.m(26); height: raiz.m(25)
            conteo: raiz.conteoNotificaciones
            urgente: panelNotificaciones.urgente
            enCurso: panelNotificaciones.avisoEnCurso
            parpadeo: panelNotificaciones.parpadeo
            colorNormal: raiz.paleta.insignia
            tamFuente: raiz.fuente(17)
        }
        MouseArea {
            x: raiz.m(870); y: raiz.m(40); width: raiz.m(90); height: raiz.m(95)
            onClicked: { raiz.campanaPulsada(); panelNotificaciones.abrir() }
        }

        Icono {
            caja: [1043, 64, 57, 58]; tinta: [4.0, 4.0, 44.0, 44.0]
            source: raiz.iconosColor + "engranaje.svg"
        }
        MouseArea {
            x: raiz.m(1025); y: raiz.m(45); width: raiz.m(95); height: raiz.m(95)
            onClicked: raiz.ajustesPulsado()
        }
    }

    // ======================= panel principal =======================
    Rectangle {
        objectName: "tarjetaCicloEnCurso"
        // B1: termina 10 px sobre la barra flotante (no 30 como en Opciones):
        // la barra de progreso llega a y 1723 del lienzo y no se reubica (D-19)
        x: raiz.m(19); y: raiz.m(177)
        width: raiz.m(1159); height: barraInferior.y - raiz.m(10) - y
        radius: raiz.m(30)
        color: Colores.fondoTarjeta
    }

    // ---- tarjeta de ciclo (= PantallaPreciclo.qml salvo ESTADO) ----
    Rectangle {
        x: raiz.m(19); y: raiz.m(404); width: raiz.m(1159); height: raiz.m(2)
        color: raiz.paleta.bordeTarjeta
    }
    Divisor { cx: 351; y0: 219; y1: 384; color: raiz.paleta.divisorCiclo }
    Divisor { cx: 839; y0: 219; y1: 384; color: raiz.paleta.divisorCiclo }

    component Rotulo: Texto {
        bl: 229; tam: 17
        color: raiz.paleta.negro
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoMedium
    }

    Rotulo { cx: 199; text: raiz.textos.cicloActivo }
    Texto {
        cx: 200; bl: 333; tam: 103
        text: raiz.sinLectura(raiz.cicloActivo)
        color: raiz.datosVigentes ? raiz.paleta.negro : Colores.textoGuia
        font.family: raiz.fuenteNumeros
        font.weight: Tipografia.pesoBold
    }

    Rotulo { cx: 599.5; text: raiz.textos.programa }
    Texto {
        cx: 599; bl: 308; tam: 36
        text: raiz.sinLectura(raiz.programa)
        color: raiz.datosVigentes ? raiz.paleta.programa : Colores.textoGuia
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
    }

    // ESTADO: "En ejecución" (plan §5.2). Al terminar, el resultado del backend
    // (PROVISIONAL, sin diseño: check verde si fue exitoso, "!" naranja si no,
    // como la insignia de PantallaPreciclo.qml).
    Rotulo { cx: 1011; text: raiz.textos.estado }
    Rectangle {
        visible: !raiz.terminado
        x: raiz.m(970); y: raiz.m(254); width: raiz.m(80); height: width; radius: width / 2
        color: raiz.paleta.verdeEjecutando
        // Engranaje animado (decisión de Cristian, 2026-10-01): images/IconoEjecucion.qml.
        // Sus SVG son verdes: brightness 1.0 los lleva a blanco. Las flechas ocupan el
        // 92 % del viewBox: con 72 px el anillo (≈ 66 px) cabe en el círculo de 80.
        IconoEjecucion {
            anchors.centerIn: parent
            size: raiz.m(72)
            running: raiz.visible
            layer.enabled: true
            layer.effect: MultiEffect { brightness: 1.0 }
        }
    }
    Rectangle {
        visible: raiz.terminado
        x: raiz.m(970); y: raiz.m(254); width: raiz.m(80); height: width; radius: width / 2
        color: raiz.resultado === "exitoso" ? raiz.paleta.verdeEjecutando : raiz.paleta.naranjaEstado
        Image {
            id: checkEstado
            visible: false
            anchors.centerIn: parent
            width: raiz.m(64); height: width
            source: raiz.iconosColor + "confirmar.svg"
            sourceSize.width: width; sourceSize.height: height
        }
        MultiEffect {
            visible: raiz.resultado === "exitoso"
            anchors.fill: checkEstado
            source: checkEstado
            brightness: 1.0
        }
        Text {
            visible: raiz.resultado !== "exitoso"
            anchors.centerIn: parent
            text: "!"
            color: "white"
            font.family: raiz.fuenteNumeros
            font.weight: Tipografia.pesoBold
            font.pixelSize: raiz.fuente(56)
        }
    }
    Texto {
        cx: 1010; bl: 380; tam: 22
        text: !raiz.terminado ? raiz.textos.enEjecucion
              : raiz.resultado ? I18n.t("estados." + raiz.resultado, I18n.lang) : ""
        color: !raiz.terminado || raiz.resultado === "exitoso" ? raiz.paleta.verdeEjecutando
                                                                : raiz.paleta.naranjaTexto
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
    }

    // ======================= barra de fases =======================
    BarraFases {
        anchors.fill: parent
        escala: raiz.m(1)
        fases: raiz.fases
    }

    // ======================= tarjeta de parámetros (= PantallaPreciclo.qml, +151) =======================
    component Etiqueta: Texto {
        tam: 12
        color: raiz.paleta.etiqueta
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
    }
    component Valor: Texto {
        bl: 554; tam: 55
        color: raiz.datosVigentes ? raiz.paleta.negro : Colores.textoGuia
        font.family: raiz.fuenteNumeros
        font.weight: Tipografia.pesoBold
    }
    component Unidad: Texto {
        bl: 606; tam: 27
        color: raiz.paleta.unidad
        font.family: raiz.fuenteNumeros
        font.weight: Tipografia.pesoBold
    }

    Item {
        anchors.fill: parent
        transform: Translate { y: raiz.m(151) }

        Rectangle {
            x: raiz.m(34); y: raiz.m(425); width: raiz.m(1129); height: raiz.m(208)
            radius: raiz.m(30)
            color: Colores.fondoTarjeta
            border.width: raiz.m(2); border.color: raiz.paleta.bordeSuave
        }
        // 6 columnas iguales (1129/6 ≈ 188 px): 3 parámetros de ciclo y 3 sensores.
        // Valor y unidad centrados en la columna; icono y etiqueta desplazados como grupo.
        Divisor { cx: 222.2; y0: 452; y1: 604; color: raiz.paleta.divisorParam }
        Divisor { cx: 410.3; y0: 452; y1: 604; color: raiz.paleta.divisorParam }
        Divisor { cx: 598.5; y0: 452; y1: 608; color: raiz.paleta.divisorParam }
        Divisor { cx: 786.7; y0: 452; y1: 606; color: raiz.paleta.divisorParam }
        Divisor { cx: 974.8; y0: 452; y1: 606; color: raiz.paleta.divisorParam }

        Icono { caja: [59.1, 448, 20, 33]; tinta: [12.25, 4.0, 36.55, 44.0]; source: raiz.iconosColor + "sensor_temperatura.svg" }
        Etiqueta { lx: 115.1; bl: 469; text: raiz.textos.tempEster }
        Valor { cx: 128.1; text: raiz.sinLectura(raiz.tempEsterilizacion) }
        Unidad { cx: 127.6; text: raiz.textos.unidadTemp }

        Icono { caja: [246.7, 447, 35, 35]; tinta: [5.9, 5.9, 42.1, 42.1]; source: raiz.iconosColor + "sensor_tiempo.svg" }
        Etiqueta { lx: 309.7; bl: 467; text: raiz.textos.tiempoEst }
        Valor { cx: 316.2; text: raiz.sinLectura(raiz.tiempoEsterilizacion) }
        Unidad { cx: 322.7; text: raiz.textos.unidadTiempo }

        IconoTenido {
            caja: [437.4, 446, 27, 39]; tinta: [10.05, 4.2, 37.95, 43.8]
            source: raiz.iconosColor + "sensor_tiempo_secado.svg"
            color: raiz.paleta.iconoGris
        }
        Etiqueta { lx: 493.4; bl: 467; text: raiz.textos.tiempoSec }
        Valor { cx: 504.4; text: raiz.sinLectura(raiz.tiempoSecado) }
        Unidad { cx: 504.4; text: raiz.textos.unidadTiempo }

        // O3 (tanda 6): las entradas mostradas del programa (1 a 3, UiBridge.entradasMostradas)
        // en las 3 columnas de la derecha, en la unidad vigente; "—" si no hay lectura o
        // el sensor está "No en uso" en el programa.
        Repeater {
            model: raiz.entradas
            delegate: Item {
                id: entrada
                required property var modelData
                required property int index
                readonly property real c0: [598.5, 786.7, 974.8][entrada.index] || 0
                readonly property bool esPresion: entrada.modelData.tipo === "pres"
                anchors.fill: parent
                visible: entrada.index < 3
                Icono {
                    visible: !entrada.esPresion
                    caja: [entrada.c0 + 26.6, 448, 20, 33]; tinta: [12.25, 4.0, 36.55, 44.0]
                    source: raiz.iconosColor + "sensor_temperatura_2.svg"
                }
                Icono {
                    visible: entrada.esPresion
                    caja: [entrada.c0 + 31.6, 450, 37, 31]; tinta: [5.3, 8.0, 43.7, 40.85]
                    source: raiz.iconosColor + "sensor_presion.svg"
                }
                Etiqueta {
                    lx: entrada.c0 + (entrada.esPresion ? 99.6 : 73.6); bl: entrada.esPresion ? 467 : 469
                    text: I18n.t("ciclo.entrada_corta_" + entrada.modelData.clave, I18n.lang)
                }
                Valor { cx: entrada.c0 + 94.1; text: raiz.datosVigentes ? entrada.modelData.valor : "—" }
                Unidad { cx: entrada.c0 + (entrada.esPresion ? 109.6 : 85.1); text: entrada.modelData.unidad || "" }
            }
        }
    }

    // ======================= gráfica (alto flexible) =======================
    GraficaCiclo {
        x: raiz.m(33); y: raiz.m(804)
        width: raiz.m(1162 - 33)
        height: raiz.yb(1598) - y
        escala: raiz.m(1)
        datos: raiz.datosGrafica
        seriesEntradas: raiz.seriesGrafica
        fases: raiz.fasesGrafica
        tiempoActualMin: raiz.tiempoActualMin
        cursorMin: raiz.cursorMin
        tiempos: raiz.fases
        onTiemposPulsado: raiz.tiemposPulsado()
        onPantallaCompletaPulsado: { raiz.pantallaCompleta = true; raiz.pantallaCompletaPulsado() }

        // D8-2.16 (tanda 8, Q1-P7), PROVISIONAL (sin diseño): todo ciclo que
        // no termine COMPLETADO ("exitoso") muestra "CARGA NO ESTÉRIL", igual
        // que el ticket (T2-c de la tanda 7). Falla cerrada: un resultado
        // desconocido también. No toma toques: no bloquea la gráfica.
        Rectangle {
            objectName: "cargaNoEsteril"
            visible: raiz.cargaNoEsteril
            anchors.horizontalCenter: parent.horizontalCenter
            y: raiz.m(40)
            width: raiz.m(960); height: raiz.m(110)
            radius: raiz.m(10)
            color: Colores.fondoTarjeta
            border.width: raiz.m(4); border.color: Colores.alarmaAlta
            Text {
                anchors.centerIn: parent
                width: parent.width - raiz.m(40)
                horizontalAlignment: Text.AlignHCenter
                fontSizeMode: Text.HorizontalFit
                minimumPixelSize: raiz.fuente(20)
                text: I18n.t("ciclo.carga_no_esteril", I18n.lang)
                color: Colores.alarmaAlta
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoBold
                font.pixelSize: raiz.fuente(56)
            }
        }

        // PROVISIONAL (sin diseño): aviso de sin conexión sobre el área de trazado,
        // mismo texto que PantallaPreciclo.qml; los datos de la gráfica quedan congelados.
        // U4: también con la tarjeta desconectada o sin datos (lo dice el texto).
        Rectangle {
            id: marcoSinConexion
            objectName: "avisoSinConexionCiclo"
            visible: !raiz.datosVigentes || raiz.estadoTarjeta !== "ok"
            anchors.horizontalCenter: parent.horizontalCenter
            y: raiz.m(170)
            width: raiz.m(960); height: avisoSinConexion.implicitHeight + raiz.m(24)
            radius: raiz.m(10)
            color: Colores.fondoSutil
            border.width: raiz.m(1.5); border.color: raiz.paleta.bordeTarjeta
            Text {
                id: avisoSinConexion
                x: raiz.m(20); width: parent.width - raiz.m(40)
                anchors.verticalCenter: parent.verticalCenter
                text: !raiz.datosVigentes ? I18n.t("sistema.sin_conexion", I18n.lang)
                    : raiz.estadoTarjeta === "desconectada"
                      ? I18n.t("sistema.tarjeta_desconectada_valores", I18n.lang)
                    : I18n.t("sistema.tarjeta_sin_datos_valores", I18n.lang)
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(24)
            }
        }

        // U4 (tanda 2), PROVISIONAL (sin diseño): esta pantalla no tiene tarjeta
        // de alarmas; las filas críticas (sin conexión, tarjeta desconectada o
        // sin datos, paro real, estado seguro) se superponen a la gráfica
        // mientras duren. NO ABRIR (permanente en ciclo) y el modo prueba (no
        // existe en ciclo) quedan en el panel de la campana. No toma toques
        // fuera de su botón: no bloquea la navegación.
        Rectangle {
            objectName: "tarjetaSeguridadCiclo"
            visible: seguridadCiclo.conteo > 0
            anchors.horizontalCenter: parent.horizontalCenter
            y: marcoSinConexion.visible ? marcoSinConexion.y + marcoSinConexion.height + raiz.m(16)
                                        : raiz.m(170)
            width: raiz.m(960)
            height: seguridadCiclo.implicitHeight + raiz.m(32)
            radius: raiz.m(10)
            color: Colores.fondoTarjeta
            border.width: raiz.m(1.5); border.color: Colores.alarmaAlta
            SeccionEstadoSeguro {
                id: seguridadCiclo
                objectName: "seguridadCiclo"
                x: raiz.m(20); y: raiz.m(16)
                width: parent.width - raiz.m(40)
                grupo: "emergencia"
                puente: raiz.puente
                comandos: raiz.comandosSistema
            }
        }
    }

    // ======================= relojes y progreso (anclados abajo) =======================
    component Reloj: Texto {
        abajo: true; bl: 1656; tam: 48
        color: raiz.paleta.reloj
        font.family: raiz.fuenteNumeros
        font.weight: Tipografia.pesoBold
    }
    component RotuloReloj: Texto {
        abajo: true; bl: 1681; tam: 19
        color: raiz.paleta.rotuloReloj
        font.family: Tipografia.familia
    }
    Reloj { cx: 426.5; text: raiz.formatoReloj(raiz.transcurridoS) }
    RotuloReloj { cx: 426.5; text: raiz.textos.transcurrido }
    Reloj { cx: 995; text: raiz.formatoReloj(raiz.restanteS) }
    RotuloReloj { cx: 994.5; text: raiz.textos.restante }

    // Barra de progreso: ancho completo bajo los relojes (plan §5.6; el mockup
    // la corta en x = 814). Sin estimación de restante queda vacía.
    Rectangle {
        id: pista
        x: raiz.m(39); y: raiz.yb(1691)
        width: raiz.m(1157 - 39); height: raiz.m(32)
        radius: height / 2
        color: raiz.paleta.pistaProgreso
        Rectangle {
            visible: raiz.fraccionProgreso > 0
            width: Math.max(height, pista.width * raiz.fraccionProgreso); height: pista.height
            radius: height / 2
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: raiz.paleta.progresoInicio }
                GradientStop { position: 1.0; color: raiz.paleta.progresoFin }
            }
        }
    }

    // ======================= barra inferior =======================
    // B1 (tanda 6, decisión 1.7): la misma BarraInferiorMenu flotante de
    // Opciones, fuera del panel principal y por debajo de él, con las funciones
    // de hoy: equipo a la izquierda, iniciar sesión al centro y CANCELAR /
    // CONFIRMAR a la derecha; versión abajo a la derecha (la de la barra).
    // Coordenadas de los hijos relativas a la barra (origen en x 34, y 1746).
    component TextoPieBarra: Text {
        property real bl: 0
        x: raiz.m(70 - 34)
        y: raiz.m(bl - 1746) - baselineOffset
        color: raiz.paleta.textoPie
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
        font.pixelSize: raiz.fuente(17)
    }
    BarraInferiorMenu {
        id: barraInferior
        objectName: "barraInferiorCicloEnCurso"
        x: raiz.m(34)
        y: raiz.yb(1746)
        escala: raiz.m(1)
        personalizada: true
        version: raiz.version

        // Celda izquierda: icono de equipo, modelo y serie
        Item {
            objectName: "botonEquipoCiclo"
            x: 0; y: 0; width: raiz.m(313); height: parent.height
            // icono_autoclave.svg (viewBox 94 x 62, tinta en 5.5..85.5 x 5.5..56.5)
            Image {
                x: raiz.m(71 - 5.5 - 34); y: raiz.m(1763 - 5.5 - 1746)
                width: raiz.m(94); height: raiz.m(62)
                source: raiz.iconosColor + "icono_autoclave.svg"
                sourceSize.width: width; sourceSize.height: height
            }
            TextoPieBarra { bl: 1838; text: raiz.textos.modelo + raiz.sinLectura(raiz.modelo) }
            TextoPieBarra { bl: 1862; text: raiz.textos.serie + raiz.sinLectura(raiz.serie) }
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    raiz.equipoPulsado()
                    raiz.infoEquipo?.actualizar()
                    panelEquipo.abrir()
                }
            }
        }

        // Celda central: avatar (iniciar sesión); deshabilitado sin conexión
        Item {
            objectName: "avatarCiclo"
            x: raiz.m(313); y: 0; width: raiz.m(800 - 313); height: parent.height
            enabled: raiz.datosVigentes
            opacity: enabled ? 1.0 : 0.4
            Rectangle {
                id: fondoAvatar
                anchors.centerIn: parent
                width: raiz.m(88); height: width; radius: width / 2
                color: raiz.paleta.avatarFondo
            }
            // usuario.svg (tinta 7.55..40.45 x 4.2..43.95 de 48): 44 de alto
            Image {
                readonly property real _e: raiz.m(44) / (43.95 - 4.2)
                width: 48 * _e; height: width
                x: fondoAvatar.x + fondoAvatar.width / 2 - (7.55 + 40.45) / 2 * _e
                y: fondoAvatar.y + fondoAvatar.height / 2 - (4.2 + 43.95) / 2 * _e
                source: raiz.iconosColor + "usuario.svg"
                sourceSize.width: width; sourceSize.height: height
            }
            MouseArea {
                anchors.centerIn: parent
                width: raiz.m(122); height: raiz.m(105)
                onClicked: raiz.avatarPulsado()
            }
        }

        // Botón CANCELAR CICLO (mockup: x 846..1081, y 1768..1856). Al terminar el
        // ciclo el mismo lugar lo ocupa CONFIRMAR (PROVISIONAL: colores de INICIAR
        // CICLO, ícono de check). Deshabilitado sin conexión y mientras hay un envío
        // en curso (anti doble toque).
        Item {
            id: botonCancelar
            objectName: "botonCancelarCiclo"
            // antes x 846, y 1768 de la pantalla; relativo a la barra (34, 1746)
            x: raiz.m(846 - 34); y: raiz.m(1768 - 1746)
            width: raiz.m(235); height: raiz.m(88)
            enabled: raiz.datosVigentes && !raiz.comandoOcupado
            opacity: enabled ? 1.0 : 0.4
            Rectangle {
                anchors.fill: parent
                radius: raiz.m(14)
                gradient: Gradient {
                    GradientStop { position: 0.0; color: raiz.terminado ? raiz.paleta.confirmarArriba : raiz.paleta.cancelarArriba }
                    GradientStop { position: 1.0; color: raiz.terminado ? raiz.paleta.confirmarAbajo : raiz.paleta.cancelarAbajo }
                }
                layer.enabled: true
                layer.effect: MultiEffect {
                    shadowEnabled: true
                    shadowColor: "#40000000"
                    shadowVerticalOffset: raiz.m(3)
                    shadowBlur: 0.4
                }
            }
            // detener.svg (blanco): anillo exterior 4..44 de 48 -> 65 px en el mockup
            Image {
                visible: !raiz.terminado
                x: raiz.m(894 - 846) - width / 2
                y: raiz.m(1812 - 1768) - height / 2
                width: raiz.m(65 * 48 / 40); height: width
                source: raiz.iconosColor + "detener.svg"
                sourceSize.width: width; sourceSize.height: height
            }
            // CONFIRMAR: anillo blanco con check (mismo tamaño que el de detener.svg)
            Rectangle {
                visible: raiz.terminado
                x: raiz.m(894 - 846) - width / 2
                y: raiz.m(1812 - 1768) - height / 2
                width: raiz.m(65); height: width; radius: width / 2
                color: "transparent"
                border.color: "white"; border.width: raiz.m(2)
                Image {
                    id: checkConfirmar
                    visible: false
                    anchors.centerIn: parent
                    width: raiz.m(48); height: width
                    source: raiz.iconosColor + "confirmar.svg"
                    sourceSize.width: width; sourceSize.height: height
                }
                MultiEffect {
                    anchors.fill: checkConfirmar
                    source: checkConfirmar
                    brightness: 1.0
                }
            }
            Text {
                x: raiz.m(941 - 846)
                y: raiz.m(1816 - 1768) - baselineOffset
                text: raiz.terminado ? I18n.t("ciclo.confirmar", I18n.lang) : raiz.textos.cancelar
                color: "white"
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoMedium
                font.pixelSize: raiz.fuente(13)
            }
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    if (raiz.terminado && (raiz.puente?.ackConfirmaEstadoSeguro ?? false)) {
                        // P-6 (tanda 6): §15.2, verificar fugas antes de confirmar
                        dialogoEstadoSeguro.abrir()
                    } else if (raiz.terminado) {
                        raiz.confirmarPulsado()
                        raiz.comandos?.confirmar()
                    } else {
                        dialogoCancelar.abrir()
                    }
                }
            }
        }
    }

    // ======================= gráfica a pantalla completa =======================
    // Solo la gráfica (leyenda y ejes incluidos) y un botón CERRAR; el cursor y la
    // actualización en vivo siguen funcionando (mismos datos que la tarjeta).
    Item {
        visible: raiz.pantallaCompleta
        anchors.fill: parent
        FondoApp { anchors.fill: parent }
        MouseArea { anchors.fill: parent }   // nada debajo recibe toques
        GraficaCiclo {
            x: raiz.m(33); y: raiz.m(40)
            width: raiz.m(1162 - 33)
            height: parent.height - raiz.m(80)
            escala: raiz.m(1)
            modoPantallaCompleta: true
            datos: raiz.datosGrafica
            seriesEntradas: raiz.seriesGrafica
            fases: raiz.fasesGrafica
            tiempoActualMin: raiz.tiempoActualMin
            onCerrarPulsado: raiz.pantallaCompleta = false
        }
    }

    // ======================= paneles (PROVISIONALES, como PantallaPreciclo.qml) =======================
    PanelNotificaciones {
        id: panelNotificaciones
        titulo: I18n.t("notificaciones.titulo", I18n.lang)
        textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
        rotuloAlertas: I18n.t("notificaciones.alertas_avisos", I18n.lang)
        textoSinAlarmas: I18n.t("ciclo.sin_alarmas", I18n.lang)
        alarmas: raiz.alarmas
        puente: raiz.puente
        comandosSistema: raiz.comandosSistema
    }
    PanelEquipo {
        comandosSistema: raiz.comandosSistema
        id: panelEquipo
        titulo: I18n.t("equipo.titulo", I18n.lang)
        textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
        filas: raiz.infoEquipo?.filas ?? []
        sinLectura: I18n.t("sistema.sin_lectura", I18n.lang)
    }

    // Cancelación: solo confirmación, sin credencial ni rol (plan §10)
    DialogoConfirmacion {
        id: dialogoCancelar
        objectName: "dialogoCancelarCiclo"
        mensaje: I18n.t("ciclo.cancelar_pregunta", I18n.lang)
        textoConfirmar: I18n.t("acciones.confirmar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: raiz.paleta.cancelarArriba
        onConfirmado: {
            raiz.cancelarPulsado()
            raiz.comandos?.cancelar()
        }
    }

    // P-6 (tanda 6): tras un paro, CONFIRMAR también lleva la cámara a estado
    // seguro (fin de ciclo §15.2): se pide verificar que no haya fugas
    DialogoConfirmacion {
        id: dialogoEstadoSeguro
        objectName: "dialogoEstadoSeguro"
        mensaje: I18n.t("ciclo.confirmar_estado_seguro_texto", I18n.lang)
        textoConfirmar: I18n.t("sistema.confirmar_estado_seguro", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        onConfirmado: {
            raiz.confirmarPulsado()
            raiz.comandos?.confirmar()
        }
    }

    // Aviso si el backend no aceptó el comando o no hay conexión: se queda en la
    // pantalla; el ciclo no se da por cancelado/confirmado (plan §10).
    Connections {
        target: raiz.comandos
        function onErrorChanged() { if (raiz.errorComando !== "") avisoComando.abrir() }
    }
    PanelModal {
        id: avisoComando
        objectName: "avisoComando"
        altoTarjeta: Escala.px(560)
        titulo: I18n.t("ciclo.aviso_titulo", I18n.lang)
        textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
        onVisibleChanged: if (!visible) {
            raiz.comandos?.descartarError()
            if (raiz.comandos?.descartarAviso) raiz.comandos.descartarAviso()
        }
        Text {
            width: parent.width
            text: raiz.errorComando === "confirmar" ? I18n.t("ciclo.confirmar_error", I18n.lang)
                : raiz.errorComando !== "" ? I18n.t("ciclo.cancelar_error", I18n.lang)
                : raiz.avisoCancelacion !== "" ? I18n.t(raiz.avisoCancelacion, I18n.lang)
                : I18n.t("ciclo.cancelar_error", I18n.lang)
            wrapMode: Text.WordWrap
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(28)
        }
    }
}

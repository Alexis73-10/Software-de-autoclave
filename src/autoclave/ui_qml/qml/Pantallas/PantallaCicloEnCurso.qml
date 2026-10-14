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

    // ---- datos ----
    // "?." evita TypeError si no hay puente o al destruir la pantalla.
    property bool datosVigentes: puente?.connected ?? false
    property string cicloActivo: puente?.cicloActivo ?? ""
    property string programa: puente?.programa ?? ""
    property string tempEsterilizacion: puente?.tempEsterilizacion ?? ""
    property string tiempoEsterilizacion: puente?.tiempoEsterilizacion ?? ""
    property string tiempoSecado: puente?.tiempoSecado ?? ""
    // lecturas en vivo: sin conexión se muestran "—" (plan §15.8)
    property string tempCamara: datosVigentes ? (puente?.tempCamara ?? "") : ""
    property string tempReferencia: datosVigentes ? (puente?.tempReferencia ?? "") : ""
    property string presionCamara: datosVigentes ? (puente?.presionCamara ?? "") : ""
    property var alarmas: puente?.alarms ?? null
    property int conteoNotificaciones: alarmas?.count ?? 0
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
    // "" mientras el ciclo corre; "exitoso" / "cancelado" / "fallo" al terminar
    property string resultado: progreso?.resultado ?? ""
    readonly property bool terminado: resultado !== ""
    property bool comandoOcupado: comandos?.ocupado ?? false
    property string errorComando: comandos?.error ?? ""

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
        readonly property string unidadTemp: I18n.t("unidades.temperatura", I18n.lang)
        readonly property string unidadTiempo: I18n.t("unidades.tiempo", I18n.lang)
        readonly property string unidadPresion: I18n.t("unidades.presion", I18n.lang)
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
        Rectangle {
            visible: raiz.conteoNotificaciones > 0
            x: raiz.m(922); y: raiz.m(50)
            width: raiz.m(26); height: raiz.m(25); radius: width / 2
            color: raiz.paleta.insignia
            Text {
                anchors.centerIn: parent
                text: raiz.conteoNotificaciones
                color: "white"
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(17)
            }
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
        x: raiz.m(19); y: raiz.m(177)
        width: raiz.m(1159); height: raiz.yb(1900) - y
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

        Icono { caja: [625.1, 448, 20, 33]; tinta: [12.25, 4.0, 36.55, 44.0]; source: raiz.iconosColor + "sensor_temperatura_2.svg" }
        Etiqueta { lx: 672.1; bl: 469; text: raiz.textos.tempCamara }
        Valor { cx: 692.6; text: raiz.sinLectura(raiz.tempCamara) }
        Unidad { cx: 683.6; text: raiz.textos.unidadTemp }

        Icono { caja: [804.3, 448, 20, 33]; tinta: [12.25, 4.0, 36.55, 44.0]; source: raiz.iconosColor + "sensor_temperatura_2.svg" }
        Etiqueta { lx: 851.3; bl: 469; text: raiz.textos.tempReferencia }
        Valor { cx: 880.8; text: raiz.sinLectura(raiz.tempReferencia) }
        Unidad { cx: 871.8; text: raiz.textos.unidadTemp }

        Icono { caja: [1006.4, 450, 37, 31]; tinta: [5.3, 8.0, 43.7, 40.85]; source: raiz.iconosColor + "sensor_presion.svg" }
        Etiqueta { lx: 1074.4; bl: 467; text: raiz.textos.presion }
        Valor { cx: 1068.9; text: raiz.sinLectura(raiz.presionCamara) }
        Unidad { cx: 1084.4; text: raiz.textos.unidadPresion }
    }

    // ======================= gráfica (alto flexible) =======================
    GraficaCiclo {
        x: raiz.m(33); y: raiz.m(804)
        width: raiz.m(1162 - 33)
        height: raiz.yb(1598) - y
        escala: raiz.m(1)
        datos: raiz.datosGrafica
        fases: raiz.fasesGrafica
        tiempoActualMin: raiz.tiempoActualMin
        cursorMin: raiz.cursorMin
        tiempos: raiz.fases
        onTiemposPulsado: raiz.tiemposPulsado()
        onPantallaCompletaPulsado: { raiz.pantallaCompleta = true; raiz.pantallaCompletaPulsado() }

        // PROVISIONAL (sin diseño): aviso de sin conexión sobre el área de trazado,
        // mismo texto que PantallaPreciclo.qml; los datos de la gráfica quedan congelados.
        Rectangle {
            visible: !raiz.datosVigentes
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
                text: I18n.t("sistema.sin_conexion", I18n.lang)
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                color: Colores.textoSecundario
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(24)
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

    // ======================= barra inferior (= PantallaPreciclo.qml salvo la derecha) =======================
    Rectangle {
        x: raiz.m(33); y: raiz.yb(1744); width: raiz.m(1130); height: raiz.m(141)
        radius: raiz.m(26)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2); border.color: raiz.paleta.bordeSuave
    }
    Divisor { abajo: true; cx: 347; y0: 1763; y1: 1869; color: raiz.paleta.divisorPie }
    Divisor { abajo: true; cx: 834; y0: 1763; y1: 1869; color: raiz.paleta.divisorPie }

    // Icono de equipo: igual que PantallaPreciclo.qml (PROVISIONAL, PC-03) hasta recibir el SVG del diseñador.
    Item {
        x: raiz.m(71); y: raiz.yb(1763); width: raiz.m(80); height: raiz.m(52)
        Rectangle {
            anchors.fill: parent
            color: "transparent"
            border.color: raiz.paleta.iconoGris; border.width: raiz.m(1.5)
        }
        Rectangle {
            x: raiz.m(42); y: raiz.m(4); width: raiz.m(18); height: raiz.m(44)
            color: "transparent"
            border.color: raiz.paleta.iconoGris; border.width: raiz.m(1.5)
        }
    }
    component TextoPie: Texto {
        abajo: true; lx: 70; tam: 17
        color: raiz.paleta.textoPie
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoSemiBold
    }
    TextoPie { bl: 1838; text: raiz.textos.modelo + raiz.sinLectura(raiz.modelo) }
    TextoPie { bl: 1862; text: raiz.textos.serie + raiz.sinLectura(raiz.serie) }
    MouseArea {
        x: raiz.m(33); y: raiz.yb(1744); width: raiz.m(347 - 33); height: raiz.m(141)
        onClicked: {
            raiz.equipoPulsado()
            raiz.infoEquipo?.actualizar()
            panelEquipo.abrir()
        }
    }

    // Avatar: deshabilitado sin conexión (como PantallaPreciclo.qml)
    Item {
        anchors.fill: parent
        enabled: raiz.datosVigentes
        opacity: enabled ? 1.0 : 0.4
        Rectangle {
            x: raiz.m(550); y: raiz.yb(1762); width: raiz.m(88); height: width; radius: width / 2
            color: raiz.paleta.avatarFondo
        }
        Icono {
            abajo: true
            caja: [576, 1784, 36, 44]; tinta: [7.55, 4.2, 40.45, 43.95]
            source: raiz.iconosColor + "usuario.svg"
        }
        MouseArea {
            x: raiz.m(550); y: raiz.yb(1762); width: raiz.m(88); height: width
            onClicked: raiz.avatarPulsado()
        }
    }

    // Botón CANCELAR CICLO (mockup: x 846..1081, y 1768..1856). Al terminar el
    // ciclo el mismo lugar lo ocupa CONFIRMAR (PROVISIONAL: colores de INICIAR
    // CICLO, ícono de check). Deshabilitado sin conexión y mientras hay un envío
    // en curso (anti doble toque).
    Item {
        id: botonCancelar
        x: raiz.m(846); y: raiz.yb(1768)
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
                if (raiz.terminado) {
                    raiz.confirmarPulsado()
                    raiz.comandos?.confirmar()
                } else {
                    dialogoCancelar.abrir()
                }
            }
        }
    }

    Text {
        x: raiz.m(1141) - width
        y: raiz.yb(1867) - baselineOffset
        text: raiz.version
        color: raiz.paleta.versionTexto
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoBold
        font.pixelSize: raiz.fuente(20)
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
    }
    PanelEquipo {
        id: panelEquipo
        titulo: I18n.t("equipo.titulo", I18n.lang)
        textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
        filas: raiz.infoEquipo?.filas ?? []
        sinLectura: I18n.t("sistema.sin_lectura", I18n.lang)
    }

    // Cancelación: solo confirmación, sin credencial ni rol (plan §10)
    DialogoConfirmacion {
        id: dialogoCancelar
        mensaje: I18n.t("ciclo.cancelar_pregunta", I18n.lang)
        textoConfirmar: I18n.t("acciones.confirmar", I18n.lang)
        textoCancelar: I18n.t("acciones.cancelar", I18n.lang)
        colorConfirmar: raiz.paleta.cancelarArriba
        onConfirmado: {
            raiz.cancelarPulsado()
            raiz.comandos?.cancelar()
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
        altoTarjeta: Escala.px(560)
        titulo: I18n.t("ciclo.aviso_titulo", I18n.lang)
        textoCerrar: I18n.t("acciones.cerrar", I18n.lang)
        onVisibleChanged: if (!visible) raiz.comandos?.descartarError()
        Text {
            width: parent.width
            text: raiz.errorComando === "confirmar" ? I18n.t("ciclo.confirmar_error", I18n.lang)
                                                     : I18n.t("ciclo.cancelar_error", I18n.lang)
            wrapMode: Text.WordWrap
            color: Colores.textoPrimario
            font.family: Tipografia.familia
            font.pixelSize: Escala.fuente(28)
        }
    }
}

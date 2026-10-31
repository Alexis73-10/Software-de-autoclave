import QtQuick
import QtQuick.Shapes
import Tema

// Círculo de una fase de la barra de fases con líquido (llenado de fases,
// contrato A-3, HAZ-LLF-01). Conserva la interfaz de FC-06: raíz Rectangle con
// `color` y `gradient`, e ícono como primer hijo.
//
// Regla de seguridad: el círculo solo se ve lleno si `estado` es "completada".
// El nivel de cualquier otro estado se acota a `tope` (tercera capa del tope).
// El líquido es una región calculada de forma analítica (arco inferior del
// círculo + borde superior ondulado) dibujada con QtQuick.Shapes.
Rectangle {
    id: raiz

    property string fase: ""
    property string estado: "pendiente"
    property var fraccion: null          // 0..1 o null
    property real escala: 1.0
    property real tope: 0.90
    // HAZ-LLF-01: aunque el enlace entregue otro valor, nunca más de 0,90
    readonly property real _topeEfectivo: Math.min(tope, 0.90)
    property real nivelIndeterminado: 0.25
    property bool datosVigentes: true
    property bool chorroHabilitado: false
    property QtObject tiempos: null
    property bool instantaneo: false

    readonly property color _liquidoInicio: "#0B7A80"
    readonly property color _liquidoFin: "#003A9C"
    readonly property color _chorro: "#07BDFF"

    // ---- nivel ----
    readonly property bool _fraccionValida: typeof fraccion === "number" && isFinite(fraccion)
    readonly property real nivelObjetivo: estado === "completada" ? 1.0
        : estado === "activa" ? (_fraccionValida ? Math.min(Math.max(0, fraccion), _topeEfectivo)
                                                 : Math.min(nivelIndeterminado, _topeEfectivo))
        : 0.0
    property real nivel: 0.0
    readonly property real nivelVisual: estado === "completada"
        ? Math.min(1.0, Math.max(0.0, nivel))
        : Math.min(_topeEfectivo, Math.max(0.0, nivel))

    // ---- onda ----
    property real amplitudOnda: (estado === "activa" && datosVigentes) ? 2 * escala : 0
    Behavior on amplitudOnda {
        enabled: !raiz.instantaneo
        NumberAnimation { duration: 300 }
    }
    property real faseOnda: 0.0
    NumberAnimation on faseOnda {
        from: 0; to: 2 * Math.PI
        duration: raiz.tiempos ? raiz.tiempos.periodoOndaMs : 2500
        loops: Animation.Infinite
        running: raiz.amplitudOnda > 0 && !raiz.instantaneo && raiz.visible
    }

    // ---- chorro ----
    readonly property bool chorroVisible: chorroHabilitado && estado === "activa"
                                          && nivelVisual < 0.5 && datosVigentes

    // ---- aspecto base ----
    readonly property color colorTerminacion: estado === "fallida" ? Colores.alarmaAlta
        : estado === "interrumpida" ? Colores.advertencia : "transparent"
    width: 85 * escala; height: width; radius: width / 2
    color: colorTerminacion.a > 0 ? colorTerminacion : "#CCCCCC"
    Behavior on color {
        enabled: !raiz.instantaneo
        ColorAnimation { duration: raiz.tiempos ? raiz.tiempos.terminacionMs : 200 }
    }
    readonly property bool _lleno: estado === "completada" && nivel >= 0.999
    gradient: _lleno ? degradadoLleno : null
    Gradient {
        id: degradadoLleno
        orientation: Gradient.Horizontal
        GradientStop { position: 0.0; color: raiz._liquidoInicio }
        GradientStop { position: 1.0; color: raiz._liquidoFin }
    }

    // (1) ícono: debe seguir siendo el primer hijo (test_t21)
    Image {
        z: 3
        anchors.centerIn: parent
        width: 48 * raiz.escala; height: width
        source: "../../assets/iconos/color/fase_" + raiz.fase + ".svg"
        sourceSize.width: width; sourceSize.height: height
    }

    // altura de la superficie en la columna x (coordenadas del círculo)
    function _ySuperficie(x) {
        const w = width
        const lam = w * 0.85
        const A = amplitudOnda
        const ph = faseOnda
        const onda = (Math.sin(2 * Math.PI * x / lam + ph)
                      + 0.35 * Math.sin(2 * Math.PI * 1.7 * x / lam - 1.3 * ph)) / 1.35
        return w * (1 - nivelVisual) + A * onda
    }

    function _puntosLiquido() {
        const w = width, R = w / 2
        const N = 36
        const sup = [], inf = []
        for (let k = 0; k <= N; k++) {
            const th = Math.PI * k / N
            const x = R - R * Math.cos(th)       // más denso en los bordes
            const dx = x - R
            const h = Math.sqrt(Math.max(0, R * R - dx * dx))
            const yb = R + h, yt = R - h
            const y = Math.min(yb, Math.max(yt, _ySuperficie(x)))
            sup.push(Qt.point(x, y))
            inf.push(Qt.point(x, yb))
        }
        return sup.concat(inf.reverse())
    }

    function _puntosChorro() {
        const w = width, R = w / 2
        const ys = w * (1 - nivelVisual)
        const dy = Math.max(0, ys - R)
        const hh = Math.sqrt(Math.max(0, R * R - dy * dy))
        const xf = (R - hh) + 0.3 * hh + 3 * escala
        const pts = []
        for (let k = 0; k <= 14; k++) {
            const t = k / 14
            pts.push(Qt.point(xf * t, R + dy * t * t))
        }
        return pts
    }

    // (2) líquido
    Shape {
        objectName: "liquidoFase_" + raiz.fase
        z: 1
        anchors.fill: parent
        visible: (raiz.estado === "activa" || raiz.estado === "completada")
                 && raiz.nivelVisual > 0 && !raiz._lleno
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeWidth: -1
            strokeColor: "transparent"
            fillGradient: LinearGradient {
                x1: 0; y1: 0; x2: raiz.width; y2: 0
                GradientStop { position: 0.0; color: raiz._liquidoInicio }
                GradientStop { position: 1.0; color: raiz._liquidoFin }
            }
            PathPolyline { path: raiz._puntosLiquido() }
        }
    }

    // (3) chorro que cae desde la boca del conector
    Shape {
        objectName: "chorroFase_" + raiz.fase
        z: 2
        anchors.fill: parent
        visible: raiz.chorroVisible
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: "transparent"
            strokeColor: raiz._chorro
            strokeWidth: Math.max(1, 3.5 * raiz.escala)
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathPolyline { path: raiz._puntosChorro() }
        }
    }

    // ---- animaciones ----
    function _t(nombre, defecto) { return tiempos ? tiempos[nombre] : defecto }

    function _terminar() {
        if (animNivel.running) animNivel.complete()
        if (animEntrada.running) animEntrada.complete()
    }

    // modo: "fijar" | "fraccion" | "cierre" | "entrada" | "salto" | "terminacion"
    // d: {estado, fraccion}; retardoMs solo para "entrada" (espera del conector)
    function aplicar(modo, d, retardoMs) {
        _terminar()
        estado = d.estado
        fraccion = (d.fraccion === undefined) ? null : d.fraccion
        const obj = nivelObjetivo
        if (modo === "fijar" || instantaneo) {
            nivel = obj
        } else if (modo === "terminacion") {
            nivel = 0.0
        } else if (modo === "entrada") {
            nivel = 0.0
            pausaEntrada.duration = retardoMs || 0
            subidaEntrada.to = obj
            animEntrada.restart()
        } else {
            let dur, fn
            if (modo === "cierre") { dur = _t("cierreMs", 300); fn = Easing.OutCubic }
            else if (modo === "salto") { dur = _t("saltoMs", 400); fn = Easing.OutQuad }
            else if (obj >= nivel) { dur = _t("subidaMs", 950); fn = Easing.Linear }
            else { dur = _t("bajadaMs", 1200); fn = Easing.OutCubic }
            animNivel.duration = dur
            animNivel.easing.type = fn
            animNivel.to = obj
            animNivel.restart()
        }
    }

    NumberAnimation { id: animNivel; target: raiz; property: "nivel" }
    SequentialAnimation {
        id: animEntrada
        PauseAnimation { id: pausaEntrada }
        NumberAnimation {
            id: subidaEntrada
            target: raiz; property: "nivel"
            duration: raiz._t("entradaMs", 700)
            easing.type: Easing.OutCubic
        }
    }
}

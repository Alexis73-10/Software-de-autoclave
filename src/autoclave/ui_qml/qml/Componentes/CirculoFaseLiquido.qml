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
        const A = amplitudOnda + _chapoteo
        const ph = faseOnda
        const onda = (Math.sin(2 * Math.PI * x / lam + ph)
                      + 0.35 * Math.sin(2 * Math.PI * 1.7 * x / lam - 1.3 * ph)) / 1.35
        // la inclinación (chapoteo) es un plano que gira alrededor del centro
        return w * (1 - nivelVisual) + A * onda + _inclin * (x - w / 2) / (w / 2)
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

    // ---- física del chorro ----
    // El chorro sale de la boca del conector (borde izquierdo, a la altura del
    // centro) con velocidad horizontal hacia dentro del círculo: la primera
    // parte vuela separada de la pared por inercia y la gravedad lo curva. La
    // velocidad de salida pulsa (borbotones: más rápido y más grueso, luego más
    // lento y fino). Si toca la pared se desliza por ella; si llega al líquido
    // lo golpea: gotas, olas e inclinación (resorte amortiguado) contra las
    // paredes. Se simula como una cadena de parcelas emitidas a ritmo fijo.
    readonly property real _boca: 7 * escala                 // alto de la boca (= conector)
    property var _parcelas: []       // [{x, y, vx, vy, w}] de la más vieja a la más nueva
    property var _gotas: []          // [{x, y, vx, vy}] salpicaduras
    property real _tChorro: 0.0      // tiempo desde que empezó a salir (fase del borbotón)
    property real _acumEmision: 0.0
    property real _inclin: 0.0       // px: la superficie sube en un lado y baja en el otro
    property real _velInclin: 0.0    // px/s
    property real _chapoteo: 0.0     // px extra de amplitud de onda por el impacto
    readonly property int _maxGotas: 14
    readonly property int _maxParcelas: 70

    readonly property real _velSalida: 68        // px/s medios (× escala)
    readonly property real _gravedadChorro: 480  // px/s² (× escala)
    readonly property real _gravedadGota: 420    // px/s² (× escala)
    readonly property real _periodoEmision: 1 / 70

    // pulso 0..~1.6 de la velocidad: dos armónicos incommensurables = irregular
    function _pulso(t) {
        const v = 1 + 0.45 * Math.sin(2 * Math.PI * 1.15 * t)
                    + 0.15 * Math.sin(2 * Math.PI * 2.9 * t + 1.1)
        return Math.max(0.3, v)
    }

    function _emitir() {
        const rel = _pulso(_tChorro)
        const hw = _boca / 2 * Math.min(1, 0.35 + 0.5 * rel)      // el borbotón rápido es más grueso
        _parcelas.push({ x: hw, y: width / 2, vx: _velSalida * escala * rel,
                         vy: 4 * escala * (Math.random() - 0.3), w: hw })
    }

    function _salpicarEn(x, y, vxp, vyp) {
        if (_gotas.length >= _maxGotas) return
        const n = 2
        for (let i = 0; i < n && _gotas.length < _maxGotas; i++)
            _gotas.push({ x: x, y: y - 1 * escala,
                          vx: 0.35 * vxp + (Math.random() - 0.5) * 70 * escala,
                          vy: -(0.25 + Math.random() * 0.35) * Math.abs(vyp) - 20 * escala })
    }

    function _pasoParcelas(dt) {
        const R = width / 2, g = _gravedadChorro * escala
        const vivas = []
        for (let i = 0; i < _parcelas.length; i++) {
            const o = _parcelas[i]
            let vx = o.vx, vy = o.vy + g * dt
            let x = o.x + vx * dt, y = o.y + vy * dt
            const lim = R - o.w
            const dx = x - R, dy = y - R, d = Math.sqrt(dx * dx + dy * dy)
            if (d > lim && d > 0) {                  // toca la pared: se desliza (sin rebote)
                const nx = dx / d, ny = dy / d
                x = R + nx * lim; y = R + ny * lim
                const vn = vx * nx + vy * ny
                if (vn > 0) { vx -= vn * nx; vy -= vn * ny }
                const roce = Math.max(0, 1 - 1.2 * dt)
                vx *= roce; vy *= roce
            }
            if (vy > 0 && y >= _ySuperficie(x)) {    // llega al líquido: golpe
                const v = Math.sqrt(vx * vx + vy * vy)
                _chapoteo = Math.min(3 * escala, _chapoteo + 0.025 * (v / (100 * escala)) * escala)
                _velInclin -= 0.018 * vx             // empuja el líquido hacia la derecha
                if (Math.random() < 0.12) _salpicarEn(x, y, vx, vy)
                continue
            }
            vivas.push({ x: x, y: y, vx: vx, vy: vy, w: o.w })
        }
        _parcelas = vivas
    }

    function _pasoGotas(dt) {
        if (_gotas.length === 0) return
        const R = width / 2, lim = R - 2.5 * escala, g = _gravedadGota * escala
        const vivas = []
        for (let i = 0; i < _gotas.length; i++) {
            const o = _gotas[i]
            let vx = o.vx, vy = o.vy + g * dt
            let x = o.x + vx * dt, y = o.y + vy * dt
            const dx = x - R, dy = y - R, d = Math.sqrt(dx * dx + dy * dy)
            if (d > lim && d > 0) {                  // rebote en la pared
                const nx = dx / d, ny = dy / d
                x = R + nx * lim; y = R + ny * lim
                const vn = vx * nx + vy * ny
                if (vn > 0) { vx -= 1.45 * vn * nx; vy -= 1.45 * vn * ny }
            }
            if (vy > 0 && y >= _ySuperficie(x)) {    // cae al líquido: onda local
                _chapoteo = Math.min(3 * escala, _chapoteo + 0.35 * escala)
                _velInclin += (x < R ? -1 : 1) * 2 * escala
                continue
            }
            vivas.push({ x: x, y: y, vx: vx, vy: vy })
        }
        _gotas = vivas
    }

    function _paso(dt) {
        if (instantaneo || !chorroVisible) {
            _tChorro = 0; _acumEmision = 0
            if (_parcelas.length > 0) _parcelas = []
            if (_gotas.length > 0) _gotas = []
        } else {
            _tChorro += dt
            _acumEmision += dt
            while (_acumEmision >= _periodoEmision && _parcelas.length < _maxParcelas) {
                _acumEmision -= _periodoEmision
                _emitir()
            }
            if (_acumEmision > _periodoEmision) _acumEmision = 0
            _pasoParcelas(dt)
        }
        _pasoGotas(dt)
        // resorte amortiguado del chapoteo (rebota en las dos paredes)
        const k = 48, c = 2.4
        _velInclin += (-k * _inclin - c * _velInclin) * dt
        _inclin = Math.max(-9 * escala, Math.min(9 * escala, _inclin + _velInclin * dt))
        _chapoteo = Math.max(0, _chapoteo - _chapoteo * 2.2 * dt)
        if (Math.abs(_inclin) < 0.01 && Math.abs(_velInclin) < 0.05) { _inclin = 0; _velInclin = 0 }
        if (_chapoteo < 0.01) _chapoteo = 0
    }

    readonly property bool _hayFisica: !instantaneo && visible
        && (chorroVisible || _parcelas.length > 0 || _gotas.length > 0
            || _inclin !== 0 || _velInclin !== 0 || _chapoteo > 0)
    FrameAnimation {
        running: raiz._hayFisica
        onTriggered: raiz._paso(Math.min(frameTime, 0.05))
    }

    // cinta del chorro: borde a cada lado de la cadena de parcelas (de la boca a la punta)
    function _puntosChorro() {
        // la cinta arranca dentro del tubo (fuera del círculo) para que no se vea separada
        const ps = _parcelas.concat([{ x: -3 * escala, y: width / 2, w: _parcelas.length ? _parcelas[_parcelas.length - 1].w : 0 }])
        const n = ps.length
        if (n < 3) return []
        const izq = [], der = []
        for (let k = 0; k < n; k++) {
            const i = n - 1 - k                      // de la más nueva (boca) a la más vieja (punta)
            const a = ps[Math.min(n - 1, i + 1)], b = ps[Math.max(0, i - 1)]
            let tx = b.x - a.x, ty = b.y - a.y
            const l = Math.sqrt(tx * tx + ty * ty) || 1
            tx /= l; ty /= l
            const w = ps[i].w * (k === n - 1 ? 0.5 : 1)   // la punta se afina
            izq.push(Qt.point(ps[i].x - ty * w, ps[i].y + tx * w))
            der.push(Qt.point(ps[i].x + ty * w, ps[i].y - tx * w))
        }
        return izq.concat(der.reverse())
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
            fillColor: raiz._chorro
            strokeWidth: -1
            strokeColor: "transparent"
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

    // gotas de la salpicadura
    Repeater {
        model: raiz._maxGotas
        delegate: Rectangle {
            required property int index
            readonly property var o: index < raiz._gotas.length ? raiz._gotas[index] : null
            z: 2
            visible: o !== null
            width: Math.max(2, 3.2 * raiz.escala); height: width; radius: width / 2
            color: raiz._chorro
            x: o ? o.x - width / 2 : 0
            y: o ? o.y - height / 2 : 0
        }
    }
}

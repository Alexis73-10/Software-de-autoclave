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
    property bool vaporTuboHabilitado: false      // el conector anterior está lleno (VAP-02a)
    property bool burbujasHabilitadas: false      // última completada mientras hay una activa (VAP-03)
    property QtObject tiempos: null
    property bool instantaneo: false

    readonly property color _liquidoInicio: estado === "activa" ? Colores.faseActiva : Colores.faseCompletadaInicio
    readonly property color _liquidoFin: estado === "activa" ? Colores.faseActivaFin : Colores.faseCompletadaFin

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

    // ---- aspecto base ----
    readonly property color colorTerminacion: estado === "fallida" ? Colores.alarmaAlta
        : estado === "interrumpida" ? Colores.advertencia : "transparent"
    width: 85 * escala; height: width; radius: width / 2
    color: colorTerminacion.a > 0 ? colorTerminacion : Colores.fasePendienteFondo
    // aro de la activa y borde de la pendiente: transparentes en el tema claro
    border.width: estado === "activa" ? 2 * escala : estado === "pendiente" ? escala : 0
    border.color: estado === "activa" ? Colores.faseActivaAro : Colores.fasePendienteBorde
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
        const ph = faseOnda
        const onda = (Math.sin(2 * Math.PI * x / lam + ph)
                      + 0.35 * Math.sin(2 * Math.PI * 1.7 * x / lam - 1.3 * ph)) / 1.35
        return w * (1 - nivelVisual) + amplitudOnda * onda
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

    // ---- vapor y burbujas (tanda 34, VAP-01..05) ----
    // Solo decoración: no leen ni escriben nivel, nivelVisual, nivelObjetivo ni
    // _lleno (HAZ-LLF-01). Partículas en arreglos JS, un FrameAnimation y un
    // grupo fijo de Rectangle redondos por Repeater (sin Canvas ni Particles).
    readonly property bool _condBase: datosVigentes && !instantaneo && visible
    readonly property bool _vaporActivo: estado === "activa" && _condBase
    readonly property bool vaporTuboActivo: _vaporActivo && vaporTuboHabilitado
    readonly property bool bocanadasActivas: _vaporActivo
    readonly property bool burbujasActivas: burbujasHabilitadas && estado === "completada" && _condBase
    // sin datos, instantáneo, oculto o en pendiente/fallida/interrumpida: se vacía en el acto
    readonly property bool _vaciarYa: !_condBase || estado === "pendiente"
                                      || estado === "fallida" || estado === "interrumpida"
    on_VaciarYaChanged: if (_vaciarYa) _vaciar()

    property var _vTubo: []
    property var _vBoc: []
    property var _vBurb: []
    property int _nVivas: 0
    property real _acTubo: 0.0
    property real _acBoc: 0.0
    property real _acBurb: 0.0
    readonly property int _maxTubo: 90
    readonly property int _maxBoc: 12
    readonly property int _maxBurb: 20
    readonly property bool _hayAnimacion: visible && !instantaneo
        && (vaporTuboActivo || bocanadasActivas || burbujasActivas || _nVivas > 0)

    function _vaciar() {
        if (_vTubo.length > 0) _vTubo = []
        if (_vBoc.length > 0) _vBoc = []
        if (_vBurb.length > 0) _vBurb = []
        _acTubo = 0; _acBoc = 0; _acBurb = 0; _nVivas = 0
    }
    function _rnd(a, b) { return a + (b - a) * Math.random() }
    // opacidad: sube en el primer 15 % de la vida y baja hasta 0 al final
    function _alfa(edad, vida, pico) {
        const f = edad / vida
        return pico * (f < 0.15 ? f / 0.15 : Math.max(0, (1 - f) / 0.85))
    }

    function _emitirTubo() {
        const e = escala, R = width / 2
        const ang = _rnd(-13, 13) * Math.PI / 180
        const v = 60 * e * _rnd(0.85, 1.15)
        _vTubo.push({ x: 1 * e, y: R + _rnd(-0.25, 0.25) * 7 * e,
                      vx: v * Math.cos(ang), vy: v * Math.sin(ang),
                      rt0: R - _rnd(5, 10) * e, edad: 0, vida: _rnd(2.2, 2.8),
                      rv: 0, a: 0, fondo: false })
    }
    function _emitirBocanada() {
        const e = escala
        const x = width * _rnd(0.15, 0.85)
        _vBoc.push({ x: x, y: _ySuperficie(x), vx: _rnd(-3, 3) * e, vy: -_rnd(14, 24) * e,
                     edad: 0, vida: _rnd(1.3, 1.8), rv: 0, a: 0, fondo: true })
    }
    function _emitirBurbuja() {
        const e = escala, R = width / 2
        const x = width * _rnd(0.125, 0.875)
        const dx = x - R
        const yb = R + Math.sqrt(Math.max(0, R * R - dx * dx))
        _vBurb.push({ x: x, y: yb - 5 * e, vy: _rnd(18, 34) * e, r0: _rnd(1.8, 3.6) * e,
                      edad: 0, rv: 0, a: 1 })
    }

    // radio visible dentro del círculo: min(r, R - 1 - d)
    function _radioVisible(x, y, r) {
        const R = width / 2, dx = x - R, dy = y - R
        return Math.min(r, R - 1 - Math.sqrt(dx * dx + dy * dy))
    }

    function _pasoTubo(dt) {
        const e = escala, R = width / 2
        const vivas = []
        const damp = Math.max(0, 1 - 2.4 * dt)
        for (let i = 0; i < _vTubo.length; i++) {
            const o = _vTubo[i]
            const edad = o.edad + dt
            if (edad >= o.vida) continue
            const vx = o.vx * damp, vy = o.vy * damp
            const dx = o.x - R, dy = o.y - R
            const d = Math.sqrt(dx * dx + dy * dy) || 1
            const w = Math.min(1, edad * 1.6) * 48 * e       // sentido horario en pantalla
            let x = o.x + (vx + (-dy / d) * w) * dt
            let y = o.y + (vy + (dx / d) * w) * dt
            const d2 = Math.sqrt((x - R) * (x - R) + (y - R) * (y - R)) || 1
            const corr = (Math.max(0, o.rt0 - 3 * e * edad) - d2) * Math.min(1, 3 * dt)
            x += (x - R) / d2 * corr; y += (y - R) / d2 * corr
            const r = (2 + 5.5 * edad) * e
            const rv = _radioVisible(x, y, r)
            vivas.push({ x: x, y: y, vx: vx, vy: vy, rt0: o.rt0, edad: edad, vida: o.vida,
                         rv: rv, a: _alfa(edad, o.vida, 0.77), fondo: y < _ySuperficie(x) })
        }
        _vTubo = vivas
    }
    function _pasoBocanadas(dt) {
        const e = escala
        const vivas = []
        for (let i = 0; i < _vBoc.length; i++) {
            const o = _vBoc[i]
            const edad = o.edad + dt
            if (edad >= o.vida) continue
            const vy = o.vy - 16 * e * dt
            const x = o.x + o.vx * dt, y = o.y + vy * dt
            const rv = _radioVisible(x, y, (3 + 4 * edad) * e)
            vivas.push({ x: x, y: y, vx: o.vx, vy: vy, edad: edad, vida: o.vida,
                         rv: rv, a: _alfa(edad, o.vida, 1.0), fondo: y < _ySuperficie(x) })
        }
        _vBoc = vivas
    }
    function _pasoBurbujas(dt) {
        const e = escala
        const vivas = []
        for (let i = 0; i < _vBurb.length; i++) {
            const o = _vBurb[i]
            const edad = o.edad + dt
            const x = o.x + _rnd(-0.25, 0.25) * e, y = o.y - o.vy * dt
            const rv = _radioVisible(x, y, o.r0 + 0.6 * e * edad)
            if (rv < 1 && edad > 0.15) continue          // salió del círculo
            vivas.push({ x: x, y: y, vy: o.vy, r0: o.r0, edad: edad, rv: rv, a: 1 })
        }
        _vBurb = vivas
    }

    function _paso(dt) {
        if (_vaciarYa) { _vaciar(); return }
        if (vaporTuboActivo) {
            _acTubo += dt
            while (_acTubo >= 0.03) { _acTubo -= 0.03; if (_vTubo.length < _maxTubo) _emitirTubo() }
        } else _acTubo = 0
        if (bocanadasActivas) {
            _acBoc += dt
            while (_acBoc >= 0.2) { _acBoc -= 0.2; if (_vBoc.length < _maxBoc) _emitirBocanada() }
        } else _acBoc = 0
        if (burbujasActivas) {
            _acBurb += dt
            while (_acBurb >= 0.12) { _acBurb -= 0.12; if (_vBurb.length < _maxBurb) _emitirBurbuja() }
        } else _acBurb = 0
        _pasoTubo(dt); _pasoBocanadas(dt); _pasoBurbujas(dt)
        _nVivas = _vTubo.length + _vBoc.length + _vBurb.length
    }

    FrameAnimation {
        running: raiz._hayAnimacion
        onTriggered: raiz._paso(Math.min(frameTime, 0.05))
    }

    component Particula: Rectangle {
        required property int index
        property var lista: []
        readonly property var o: index < lista.length ? lista[index] : null
        visible: o !== null && o.rv >= 1
        width: o ? 2 * Math.max(0, o.rv) : 0; height: width; radius: width / 2
        x: o ? o.x - width / 2 : 0
        y: o ? o.y - height / 2 : 0
        opacity: o ? o.a : 0
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

    // (3) vapor del tubo y bocanadas desde la superficie
    Item {
        objectName: "vaporFase_" + raiz.fase
        z: 2
        anchors.fill: parent
        visible: raiz._nVivas > 0
        Repeater {
            model: raiz._maxTubo
            delegate: Particula {
                lista: raiz._vTubo
                color: o && o.fondo ? Colores.faseVaporFondo : Colores.faseVapor
            }
        }
        Repeater {
            model: raiz._maxBoc
            delegate: Particula {
                lista: raiz._vBoc
                color: o && o.fondo ? Colores.faseVaporFondo : Colores.faseVapor
            }
        }
    }

    // (4) burbujas de la última fase completada
    Item {
        objectName: "burbujasFase_" + raiz.fase
        z: 2
        anchors.fill: parent
        visible: raiz._vBurb.length > 0
        Repeater {
            model: raiz._maxBurb
            delegate: Particula {
                lista: raiz._vBurb
                color: Colores.faseBurbujaRelleno
                border.width: 1.1 * raiz.escala
                border.color: Colores.faseBurbujaBorde
            }
        }
    }
}

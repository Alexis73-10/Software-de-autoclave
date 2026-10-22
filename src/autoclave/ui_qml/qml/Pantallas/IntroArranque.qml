import QtQuick
import Tema
import "../Componentes"
import Autoclave.I18n

// Intro de arranque "del vapor a la precisión" (planeacion_animacion_arranque.md).
// Dura 3,5 s, no se puede saltar y termina convertida en el splash de arranque:
// barra con el progreso real y nombre del proceso en curso. Es decorativa: no
// muestra cifras ni estados del equipo y no espera ni condiciona el arranque.
//
// Toda la animación se deriva de un único reloj `t` (s desde que se muestra) y,
// en la salida, de `s` (0–1 en 1 s): congelar ante un fallo bloqueante es pausar
// esas dos animaciones. Solo anima propiedades (sin blur ni MultiEffect); halo y
// volutas son PNG ya renderizados (tools/generar_assets_arranque.py).
// Sin parpadeos ni pulsos repetidos (D-09): cada efecto ocurre una sola vez.
// Colores: solo tokens del arranque y blanco; nunca Colores.alarma* (D-08).
Item {
    id: raiz

    // Fuente de progreso (bridge/progreso_arranque.py): fraccion, proceso,
    // terminado, falloBloqueante. null = no llega progreso (cuenta como sin backend).
    property QtObject progreso: null
    property string modelo: ""
    property string versionSoftware: ""
    // Regla 4: sin progreso durante este plazo = fallo bloqueante de arranque
    property int plazoSinProgresoMs: 20000

    // La intro llegó a su último cuadro (solo queda el fondo de reposo)
    signal finalizada()

    // ── estado ─────────────────────────────────────────────────────────────
    readonly property real duracionIntro: 3.5
    property real t: 0            // s de intro (0–3,5)
    property real s: 0            // avance de la salida (0–1 en 1 s)

    readonly property real fraccionFuente: progreso?.fraccion ?? 0
    readonly property string procesoFuente: progreso?.proceso ?? ""
    readonly property bool terminadoFuente: progreso?.terminado ?? false
    property bool sinProgreso: false
    readonly property bool falloBloqueante: (progreso?.falloBloqueante ?? false) || sinProgreso
    readonly property bool introCompleta: t >= duracionIntro
    readonly property bool enSalida: introCompleta && terminadoFuente && !falloBloqueante


    // ── curvas ─────────────────────────────────────────────────────────────
    function tramo(a, b) { return Math.max(0, Math.min(1, (t - a) / (b - a))) }
    function outCubic(x) { return 1 - Math.pow(1 - x, 3) }
    function inOutQuad(x) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2 }
    function lerp(a, b, x) { return a + (b - a) * x }

    readonly property real pHalo: outCubic(tramo(0.00, 0.60))
    readonly property real pRevela: inOutQuad(tramo(0.60, 1.40))
    readonly property real pDibujo: outCubic(tramo(1.40, 2.20))
    readonly property real pBaja: inOutQuad(tramo(2.20, 2.65))
    readonly property real pRiel: inOutQuad(tramo(2.60, 3.00))
    readonly property real pEslogan1: outCubic(tramo(2.55, 3.05))
    readonly property real pEslogan2: outCubic(tramo(2.75, 3.25))
    readonly property real pTextos: inOutQuad(tramo(3.00, 3.50))
    // Salida: 400 ms con la barra llena y 600 ms de desvanecimiento
    readonly property real visibleSalida: 1 - inOutQuad(Math.max(0, Math.min(1, (s - 0.4) / 0.6)))

    // ── geometría (fracciones de W/H; tamaños en px de diseño con Escala.px) ──
    readonly property real anchoLogo: Escala.px(480)
    readonly property real altoLogo: anchoLogo * 446 / 1666   // proporción del viewBox del SVG
    readonly property real centroLogoY: 0.38 * height
    readonly property real yLineaInicial: centroLogoY + altoLogo / 2 + Escala.px(30)
    readonly property real yBarra: 0.665 * height                // centro vertical del riel
    readonly property real altoBarra: Escala.px(14)

    // ── animaciones ────────────────────────────────────────────────────────
    NumberAnimation {
        id: animIntro
        target: raiz; property: "t"
        from: 0; to: raiz.duracionIntro
        duration: raiz.duracionIntro * 1000
        paused: running && raiz.falloBloqueante
    }
    NumberAnimation {
        id: animSalida
        target: raiz; property: "s"
        from: 0; to: 1
        duration: 1000
        paused: running && raiz.falloBloqueante
        onFinished: raiz.finalizada()
    }
    onEnSalidaChanged: if (enSalida && !animSalida.running) animSalida.start()
    // Al verse la barra, la fuente real repite las etapas ya cumplidas una a
    // una (bridge/progreso_arranque.py); el simulador no lo tiene
    onIntroCompletaChanged: if (introCompleta && typeof progreso?.reiniciarVista === "function")
                                progreso.reiniciarVista()

    Timer {
        id: vigilante
        interval: raiz.plazoSinProgresoMs
        onTriggered: if (!raiz.terminadoFuente) raiz.sinProgreso = true
    }
    function _vigilar() {
        if (terminadoFuente || falloBloqueante)
            vigilante.stop()
        else
            vigilante.restart()
    }
    // P1 (tanda 7): el fallo por plazo sin progreso se retira si el progreso
    // vuelve (backend congelado que tarda > 20 s en responder la primera vez);
    // antes la intro quedaba trabada hasta reiniciar. El fallo bloqueante que
    // publica el backend no se toca.
    function _progresoNuevo() {
        sinProgreso = false
        _vigilar()
    }
    onFraccionFuenteChanged: _progresoNuevo()
    onProcesoFuenteChanged: _progresoNuevo()
    onTerminadoFuenteChanged: _progresoNuevo()
    onFalloBloqueanteChanged: _vigilar()

    // La animación arranca con el primer cuadro ya dibujado en pantalla, no al
    // crearse: en el arranque (backend y dos pantallas a la vez) la ventana
    // tarda en mostrarse y los 3,5 s se consumían sin verse (observación de
    // Cristian, 19-oct). Respaldo: si no llega ningún cuadro (sin ventana,
    // pruebas sin pantalla), arranca a los 1,5 s.
    property bool _iniciada: false
    function _iniciar() {
        if (_iniciada)
            return
        _iniciada = true
        animIntro.start()
        _vigilar()
    }
    Connections {
        target: raiz.Window.window
        ignoreUnknownSignals: true
        function onFrameSwapped() { raiz._iniciar() }
    }
    Timer {
        interval: 1500
        running: !raiz._iniciada
        onTriggered: raiz._iniciar()
    }

    // No se puede saltar: ningún toque pasa a la pantalla de debajo
    MouseArea { anchors.fill: parent }

    // ── capas ──────────────────────────────────────────────────────────────
    // Fondo idéntico al de la pantalla de reposo (mismo asset, misma AreaFija):
    // el último cuadro de la salida coincide con ella y el relevo no tiene salto.
    AreaFija {
        anchors.fill: parent
        Image {
            anchors.fill: parent
            source: "../../assets/fondos/fondo-arranque.png"
            fillMode: Image.PreserveAspectCrop
        }
    }

    Rectangle {
        anchors.fill: parent
        color: Colores.fondoMarinoOscuro
        opacity: 1 - raiz.pRevela
        visible: opacity > 0
    }

    // Halo de vapor: nace (0–0,6 s) y se expande hasta revelar el fondo (0,6–1,4 s)
    Image {
        readonly property real radio: raiz.width * (0.10 * raiz.pHalo + 1.0 * raiz.pRevela)
        source: "../../assets/fondos/halo_arranque.png"
        width: radio * 4; height: width   // el núcleo visible del PNG ocupa ~1/4 de su lado
        x: raiz.width / 2 - width / 2
        y: raiz.centroLogoY - height / 2
        opacity: raiz.pHalo * (1 - raiz.pRevela)
        visible: opacity > 0
        smooth: true
    }

    // Tres volutas suaves que suben 0,07 H y se disipan, una sola vez
    Repeater {
        model: [{ x: 0.40, a: 0.60 }, { x: 0.52, a: 0.70 }, { x: 0.62, a: 0.80 }]
        Image {
            required property var modelData
            readonly property real p: raiz.inOutQuad(raiz.tramo(modelData.a, modelData.a + 0.6))
            source: "../../assets/fondos/voluta_vapor.png"
            width: raiz.width * 0.14; height: width * 2
            x: raiz.width * modelData.x - width / 2
            y: raiz.centroLogoY - height * 0.2 - raiz.height * 0.07 * p
            opacity: 0.06 * Math.sin(Math.PI * p)
            visible: opacity > 0
            smooth: true
        }
    }

    // Logo, revelado con un recorte centrado del mismo ancho relativo que la línea
    Item {
        width: raiz.anchoLogo * raiz.pDibujo
        height: raiz.altoLogo
        x: (raiz.width - width) / 2
        y: raiz.centroLogoY - height / 2
        clip: true
        opacity: raiz.visibleSalida
        visible: width > 0
        Image {
            x: (parent.width - width) / 2
            source: "../../assets/logo/logo-especifika-blanco.svg"
            width: raiz.anchoLogo; height: raiz.altoLogo
            sourceSize.width: width
            sourceSize.height: height
            fillMode: Image.PreserveAspectFit
        }
    }

    // Línea de precisión: se dibuja bajo el logo, baja y se convierte en el riel
    Rectangle {
        id: linea
        objectName: "rielArranque"
        readonly property real centroY: raiz.lerp(raiz.yLineaInicial, raiz.yBarra, raiz.pBaja)
        width: raiz.pBaja > 0 ? raiz.lerp(0.56, 0.72, raiz.pBaja) * raiz.width
                              : 0.56 * raiz.width * raiz.pDibujo
        height: raiz.lerp(Escala.px(3), raiz.altoBarra, raiz.pBaja)
        radius: height / 2
        x: (raiz.width - width) / 2
        y: centroY - height / 2
        color: "white"
        opacity: raiz.lerp(0.95, 0.25, raiz.pRiel) * raiz.visibleSalida
        visible: width > 0
    }

    // Relleno: sigue el progreso real desde t = 3,5 s; en la salida, lleno
    property real fraccionMostrada: !introCompleta ? 0 : (enSalida ? 1 : fraccionFuente)
    Behavior on fraccionMostrada { NumberAnimation { duration: 250; easing.type: Easing.OutQuad } }
    Rectangle {
        objectName: "rellenoArranque"
        x: linea.x
        y: raiz.yBarra - height / 2
        width: 0.72 * raiz.width * raiz.fraccionMostrada
        height: raiz.altoBarra
        radius: height / 2
        color: "white"
        opacity: 0.90 * raiz.visibleSalida
        visible: raiz.introCompleta && width > 0
    }

    // Eslogan: marca, siempre en español (D-06, ARR-02)
    Repeater {
        model: [{ texto: "Tecnología para esterilizar.", y: 0.475, p: "pEslogan1" },
                { texto: "Ingeniería para responder.",  y: 0.515, p: "pEslogan2" }]
        Text {
            required property var modelData
            readonly property real p: raiz[modelData.p]
            anchors.horizontalCenter: parent.horizontalCenter
            y: raiz.height * modelData.y - height / 2 + Escala.px(10) * (1 - p)
            text: modelData.texto
            color: "white"
            opacity: 0.95 * p * raiz.visibleSalida
            visible: opacity > 0
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoRegular
            font.pixelSize: Escala.fuente(46)
        }
    }

    Text {
        objectName: "procesoArranque"
        anchors.horizontalCenter: parent.horizontalCenter
        y: raiz.yBarra + raiz.altoBarra / 2 + Escala.px(34)
        text: I18n.existe("arranque." + raiz.procesoFuente, I18n.lang)
              ? I18n.t("arranque." + raiz.procesoFuente, I18n.lang) : ""
        color: "white"
        opacity: 0.90 * raiz.pTextos * raiz.visibleSalida
        visible: opacity > 0
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoMedium
        font.pixelSize: Escala.fuente(36)
    }

    // Pie: "<modelo>  ·  Software v<versión>"; sin modelo, solo la versión (D-07)
    Text {
        objectName: "pieArranque"
        anchors.horizontalCenter: parent.horizontalCenter
        y: raiz.height * 0.935 - height / 2
        text: {
            const version = raiz.versionSoftware !== "" ? "Software v" + raiz.versionSoftware : ""
            return [raiz.modelo, version].filter(p => p !== "").join("  ·  ")
        }
        color: Colores.textoFechaReposo
        opacity: 0.85 * raiz.pTextos * raiz.visibleSalida
        visible: opacity > 0
        font.family: Tipografia.familia
        font.weight: Tipografia.pesoMedium
        font.pixelSize: Escala.fuente(30)
    }
}

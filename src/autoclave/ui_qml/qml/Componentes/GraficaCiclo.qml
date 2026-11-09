pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import Tema
import "grafica_ejes.mjs" as Ejes
import Autoclave.I18n
import Autoclave.PosicionCard

// Tarjeta "GRÁFICA DEL CICLO" de la pantalla de ciclo en curso
// (planeacion_pantalla_ciclo_en_curso.md §8; referencia:
// images/pantalla_ciclo_con_grafica_editada.png, tarjeta en x 33..1162, y 804..1598).
//
// Geometría: px del mockup relativos a la esquina de la tarjeta, escalados por m()
// (escala = px reales por px del mockup, la misma de la pantalla). El alto es
// flexible: cabecera, leyenda e íconos de fase quedan arriba; el eje X y su título
// bajan con el alto sobrante (yb()), y el área de trazado absorbe la diferencia.
//
// Dibujo propio con QtQuick Shapes (PathPolyline), sin QtCharts. Ejes y
// decimación: grafica_ejes.mjs (probado en tests/test_grafica_ejes_js.py).
// Solo presentación: no calcula tiempos de proceso; recibe t (min) del backend.
//
// Zoom (tanda 34, ZOM-01..ZOM-07): dos dedos sobre el área de trazado amplían
// y desplazan una ventana guardada en valores absolutos (t0..t1, yIzq0..yIzq1,
// yDer0..yDer1; null = vista completa, idéntica a la de antes). La matemática
// vive en grafica_ejes.mjs (ventanaPorGesto, acotarVentana, marcasVentana...);
// aquí solo se leen los puntos de contacto. Un dedo sigue moviendo el cursor.
// La lupa de la esquina indica la vista ampliada y la restablece; también se
// restablece a los restablecerZoomMs sin tocar el área, y en el acto si cambian
// las unidades, el ciclo de `datos`, la visibilidad o quedan sin datos.
Item {
    id: raiz

    property real escala: 1.0

    // Datos: arreglos paralelos ordenados por tiempo (t_min en minutos desde el
    // inicio del ciclo); los valores sin lectura van como null.
    property var datos: ({ t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] })
    // Inicio de cada fase de la UI en el ciclo actual, en orden: [{clave, inicioMin}]
    property var fases: []
    property real tiempoActualMin: 0
    // Cursor: minuto señalado; NaN = oculto. Lo mueve el toque/arrastre sobre el
    // área de trazado y se oculta solo tras OCULTAR_CURSOR_MS sin interacción.
    property real cursorMin: NaN
    // Desplegable "Tiempos": [{fase, estado, duracion_s}] de las fases que aplican
    // (GET /cycle/current/progress; la activa se actualiza en vivo).
    property var tiempos: []
    // Pantalla completa: sin botones Tiempos / pantalla completa; botón CERRAR.
    property bool modoPantallaCompleta: false

    // Decisión delegada (plan §14), a validar visualmente; configurable.
    property int ocultarCursorMs: 5000
    // ZOM-06: restablecimiento de la vista contado desde el último toque en el
    // área de trazado (gesto de dos dedos o cursor de un dedo)
    property int restablecerZoomMs: 20000

    signal tiemposPulsado()
    signal pantallaCompletaPulsado()
    signal cerrarPulsado()


    // Series de la gráfica. O3 (tanda 6): la pantalla pasa las entradas mostradas
    // del programa (UiBridge.seriesGrafica): {clave, entrada, color, eje, unidad,
    // registrada}. Sin ellas, las tres de siempre.
    property var seriesEntradas: null
    readonly property var series: seriesEntradas && seriesEntradas.length ? seriesEntradas : _seriesPorOmision
    readonly property var _seriesPorOmision: [
        { clave: "temp_camara", texto: I18n.t("ciclo.serie_temp_camara", I18n.lang),
          textoAbrev: I18n.t("abrev.ciclo.serie_temp_camara", I18n.lang), color: Colores.serieGrafica1,
          eje: "izquierdo", unidad: I18n.t("unidades.temperatura", I18n.lang) },
        { clave: "temp_ref", texto: I18n.t("ciclo.serie_temp_ref", I18n.lang),
          textoAbrev: I18n.t("abrev.ciclo.serie_temp_ref", I18n.lang), color: Colores.serieGrafica2,
          eje: "izquierdo", unidad: I18n.t("unidades.temperatura", I18n.lang) },
        { clave: "pres_camara", texto: I18n.t("ciclo.serie_presion", I18n.lang),
          textoAbrev: I18n.t("abrev.ciclo.serie_presion", I18n.lang), color: Colores.serieGrafica3,
          eje: "derecho", unidad: I18n.t("unidades.presion", I18n.lang) },
    ]
    onSeriesChanged: filaLeyenda.tam = 21
    // Texto de la leyenda: el de la serie o el nombre corto de la entrada
    function textoSerie(s) {
        if (s.texto) return s.texto
        // Tanda 17 (SON-01): sonda instalada con rol No en uso, "(monitoreo)"
        // 28-oct: sin el sufijo "(monitoreo)" en pantalla (desbordaba)
        const n = I18n.t("ciclo.entrada_corta_" + s.entrada, I18n.lang)
        return s.registrada === false ? n + " " + I18n.t("ciclo.serie_sin_registro", I18n.lang) : n
    }
    // AJ-03 (ajustes 28-oct): abreviado de una fila del globo = nombre
    // abreviado + sufijos abreviados (abrev.ciclo.*); sin abreviatura, el
    // texto completo de esa parte
    function _abrev(clave) {
        return I18n.existe("abrev." + clave, I18n.lang) ? I18n.t("abrev." + clave, I18n.lang)
                                                         : I18n.t(clave, I18n.lang)
    }
    function textoSerieAbrev(s) {
        if (s.texto) return s.textoAbrev || s.texto
        const n = raiz._abrev("ciclo.entrada_corta_" + s.entrada)
        return s.registrada === false ? n + " " + raiz._abrev("ciclo.serie_sin_registro") : n
    }
    function _unidadEje(eje, porDefecto) {
        for (const s of series) if (s.eje === eje && s.unidad) return s.unidad
        return porDefecto
    }
    function _valor(clave, i) { const a = raiz.datos[clave]; return a ? a[i] : null }

    readonly property QtObject paleta: QtObject {
        readonly property color borde: Colores.graficaBorde
        readonly property color titulo: Colores.graficaTitulo
        readonly property color texto: Colores.graficaTexto
        readonly property color separador: Colores.graficaSeparador
        readonly property color cuadricula: Colores.graficaCuadricula
        readonly property color eje: Colores.graficaEje
        readonly property color divisorFase: Colores.graficaDivisorFase
        readonly property color iconoFase: Colores.graficaIconoFase
        readonly property color etiquetaEje: Colores.graficaTextoEje
        readonly property color tituloEje: Colores.graficaTituloEje
        readonly property color bordeBoton: Colores.graficaBordeBoton
        readonly property color cursor: Colores.graficaCursor
    }

    // OSC-05: el color de cada serie sale del tema por posición (el modo oscuro
    // no puede elegirse en Python); modelData.color se ignora.
    function colorSerie(i) {
        const k = ((i % 3) + 3) % 3
        return k === 0 ? Colores.serieGrafica1 : k === 1 ? Colores.serieGrafica2 : Colores.serieGrafica3
    }

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    // alto sobrante respecto al mockup (794): lo absorbe el área de trazado
    readonly property real _extra: height - m(794)
    function yb(v) { return m(v) + _extra }

    readonly property string iconosColor: "../../assets/iconos/color/"

    // ---- ejes ----
    function _maximo(claves) {
        let mx = null
        for (const c of claves) {
            const arr = raiz.datos[c] || []
            for (const v of arr)
                if (v !== null && v !== undefined && isFinite(v) && (mx === null || v > mx)) mx = v
        }
        return mx
    }
    readonly property var ejeX: Ejes.ejeX(tiempoActualMin)
    readonly property var ejeIzquierdo: Ejes.ejeY(_maximo(series.filter(s => s.eje === "izquierdo").map(s => s.clave)))
    readonly property var ejeDerecho: Ejes.ejeY(_maximo(series.filter(s => s.eje === "derecho").map(s => s.clave)))

    // área de trazado: x de datos 0..ejeX.maximo en 93..1035; cuadrícula 68..1059
    readonly property real xDato0: m(93)
    // diámetro del punto del cursor; la reserva de la card parte de su radio
    readonly property real diametroPuntoCursor: m(18)
    readonly property real xDato1: m(1035)
    readonly property real yArriba: m(279)
    readonly property real yAbajo: yb(709)
    // ---- ventana visible (ZOM-02) ----
    readonly property var vistaCompleta: Ejes.vistaCompleta(ejeX, ejeIzquierdo, ejeDerecho)
    // null = sin zoom; si no, la ventana absoluta fijada por el gesto
    property var ventanaZoom: null
    // transición de restablecimiento (ZOM-06): ventana de partida y avance 0..1
    property var _desdeTransicion: null
    property real _avance: 0
    readonly property bool zoomActivo: ventanaZoom !== null
    readonly property bool _conVentana: ventanaZoom !== null || _desdeTransicion !== null
    readonly property var ventana: _desdeTransicion !== null
        ? Ejes.interpolarVentana(_desdeTransicion, vistaCompleta, _avance)
        : (ventanaZoom !== null ? ventanaZoom : vistaCompleta)

    function xDe(tMin) {
        return xDato0 + (tMin - ventana.t0) / (ventana.t1 - ventana.t0) * (xDato1 - xDato0)
    }
    function yDe(v, eje) {
        const a = eje === "derecho" ? ventana.yDer0 : ventana.yIzq0
        const b = eje === "derecho" ? ventana.yDer1 : ventana.yIzq1
        return yAbajo - (v - a) / (b - a) * (yAbajo - yArriba)
    }

    // Marcas: sin zoom, exactamente las de antes (0, paso, 2·paso...); con zoom,
    // paso redondo dentro de la ventana (marcasVentana)
    function _marcasCompletas(paso, n) {
        const out = []
        for (let i = 0; i <= n; i++) out.push(i * paso)
        return out
    }
    readonly property var marcasX: _conVentana
        ? Ejes.marcasVentana(ventana.t0, ventana.t1, Ejes.DIVISIONES_X)
        : _marcasCompletas(ejeX.paso, Math.round(ejeX.maximo / ejeX.paso))
    readonly property var marcasIzquierda: _conVentana
        ? Ejes.marcasVentana(ventana.yIzq0, ventana.yIzq1, Ejes.DIVISIONES_Y)
        : _marcasCompletas(ejeIzquierdo.paso, ejeIzquierdo.divisiones)
    readonly property var marcasDerecha: _conVentana
        ? Ejes.marcasVentana(ventana.yDer0, ventana.yDer1, Ejes.DIVISIONES_Y)
        : _marcasCompletas(ejeDerecho.paso, ejeDerecho.divisiones)
    function _etiqueta(v) { return Math.round(v * 100) / 100 }

    function _puntos(serie) {
        const v = raiz.ventana
        let xs = raiz.datos.t_min || [], ys = raiz.datos[serie.clave] || []
        if (raiz._conVentana) {      // solo el tramo visible (con un vecino a cada lado)
            const tr = Ejes.tramoVentana(xs, v.t0, v.t1)
            xs = xs.slice(tr.desde, tr.hasta + 1); ys = ys.slice(tr.desde, tr.hasta + 1)
        }
        const r = Ejes.decimar(xs, ys, v.t0, v.t1, Math.max(1, xDato1 - xDato0))
        const pts = []
        for (let i = 0; i < r.x.length; i++)
            pts.push(Qt.point(xDe(r.x[i]), yDe(r.y[i], serie.eje)))
        return pts
    }

    // A11: puntos (px) de cada curva que pueden cruzar [x0, x1], con el vecino
    // de cada lado para no perder los tramos largos entre dos lecturas.
    function _curvasCerca(x0, x1) {
        const out = []
        if (isNaN(raiz.cursorMin)) return out      // cursor oculto: nada que calcular
        for (const s of raiz.series) {
            const pts = raiz._puntos(s)
            const c = []
            for (let i = 0; i < pts.length; i++) {
                const izq = i > 0 ? pts[i - 1].x : pts[i].x
                const der = i + 1 < pts.length ? pts[i + 1].x : pts[i].x
                if ((pts[i].x < x0 && der < x0) || (pts[i].x > x1 && izq > x1)) continue
                c.push({ x: pts[i].x, y: pts[i].y })
            }
            out.push(c)
        }
        return out
    }

    // índice de la lectura más cercana a t (búsqueda binaria sobre t_min)
    function _indiceCercano(t) {
        const ts = raiz.datos.t_min || []
        if (ts.length === 0) return -1
        let lo = 0, hi = ts.length - 1
        while (hi - lo > 1) {
            const mid = (lo + hi) >> 1
            if (ts[mid] < t) lo = mid; else hi = mid
        }
        return Math.abs(ts[lo] - t) <= Math.abs(ts[hi] - t) ? lo : hi
    }

    function _formatoMmSs(tMin) {
        const s = Math.max(0, Math.round(tMin * 60))
        const mm = Math.floor(s / 60), ss = s % 60
        return (mm < 10 ? "0" + mm : "" + mm) + ":" + (ss < 10 ? "0" + ss : "" + ss)
    }

    // ======================= tarjeta =======================
    Rectangle {
        anchors.fill: parent
        radius: raiz.m(30)
        color: Colores.fondoTarjeta
        border.width: raiz.m(2); border.color: raiz.paleta.borde
    }

    // Texto ubicado por línea base (bl) y por centro (cx), borde izquierdo (lx) o
    // borde derecho (rx), en px del mockup relativos a la tarjeta.
    component Texto: Text {
        property real cx: -1
        property real lx: -1
        property real rx: -1
        property real bl: 0
        property real tam: 16
        font.pixelSize: raiz.fuente(tam)
        font.family: Tipografia.familia
        x: lx >= 0 ? raiz.m(lx) : rx >= 0 ? raiz.m(rx) - width : raiz.m(cx) - width / 2
        y: raiz.m(bl) - baselineOffset
    }

    // ---- cabecera ----
    Texto {
        lx: 48; bl: 62; tam: 26
        text: I18n.t("ciclo.grafica", I18n.lang)
        color: raiz.paleta.titulo
        font.weight: Tipografia.pesoBold
    }

    // leyenda
    // O3: en fila (los nombres de las entradas tienen largo variable); si no
    // cabe antes del botón Tiempos, se reduce la letra.
    Row {
        id: filaLeyenda
        readonly property real disponible: raiz.m(840 - 88)
        property real tam: 21
        x: raiz.m(88); y: raiz.m(92)
        spacing: raiz.m(28)
        onImplicitWidthChanged: if (implicitWidth > disponible && tam > 14) tam = tam - 1
        Repeater {
            model: raiz.series
            delegate: Row {
                id: leyenda
                required property var modelData
                required property int index
                spacing: raiz.m(8)
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: raiz.m(20); height: width; radius: width / 2
                    color: raiz.colorSerie(leyenda.index)
                }
                Text {
                    text: raiz.textoSerie(leyenda.modelData)
                    color: raiz.paleta.texto
                    font.family: Tipografia.familia
                    font.pixelSize: raiz.fuente(filaLeyenda.tam)
                }
            }
        }
    }

    // botón "Tiempos": abre/cierra el desplegable de duraciones por fase
    Rectangle {
        id: botonTiempos
        visible: !raiz.modoPantallaCompleta
        x: raiz.m(856); y: raiz.m(43); width: raiz.m(154); height: raiz.m(58)
        radius: raiz.m(6)
        color: Colores.fondoTarjeta
        border.width: raiz.m(1.5); border.color: raiz.paleta.bordeBoton
        Text {
            x: raiz.m(25)
            anchors.verticalCenter: parent.verticalCenter
            text: I18n.t("ciclo.tiempos", I18n.lang)
            color: raiz.paleta.texto
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(20)
        }
        Image {
            x: raiz.m(116); y: raiz.m(24)
            width: raiz.m(14); height: width
            source: raiz.iconosColor + "chevron_abajo.svg"
            sourceSize.width: width; sourceSize.height: height
        }
        MouseArea {
            anchors.fill: parent
            onClicked: { desplegable.abierto = !desplegable.abierto; raiz.tiemposPulsado() }
        }
    }

    // botón de pantalla completa
    Rectangle {
        visible: !raiz.modoPantallaCompleta
        x: raiz.m(1037); y: raiz.m(43); width: raiz.m(58); height: raiz.m(58)
        radius: raiz.m(6)
        color: Colores.fondoTarjeta
        border.width: raiz.m(1.5); border.color: raiz.paleta.bordeBoton
        IconoColor {
            anchors.centerIn: parent
            width: raiz.m(40); height: width   // tinta 33 px (viewBox 4..44 de 48)
            source: raiz.iconosColor + "pantalla_completa.svg"
            color: Colores.textoNegro   // OSC-06: oscuro en claro, claro en oscuro
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.pantallaCompletaPulsado() }
    }

    // botón CERRAR de la pantalla completa (PROVISIONAL: sin diseño; estilo del botón Tiempos)
    Rectangle {
        visible: raiz.modoPantallaCompleta
        x: raiz.m(885); y: raiz.m(43); width: raiz.m(210); height: raiz.m(58)
        radius: raiz.m(6)
        color: Colores.fondoTarjeta
        border.width: raiz.m(1.5); border.color: raiz.paleta.bordeBoton
        Text {
            anchors.centerIn: parent
            text: I18n.t("acciones.cerrar", I18n.lang)
            color: raiz.paleta.texto
            font.family: Tipografia.familia
            font.weight: Tipografia.pesoSemiBold
            font.pixelSize: raiz.fuente(20)
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.cerrarPulsado() }
    }

    Rectangle {
        x: raiz.m(61); y: raiz.m(146); width: raiz.m(1069 - 61); height: raiz.m(2)
        color: raiz.paleta.separador
    }

    // ---- unidades de los ejes ----
    Texto {
        lx: 21; bl: 246; tam: 20
        text: raiz._unidadEje("izquierdo", I18n.t("unidades.temperatura", I18n.lang))
        color: raiz.paleta.etiquetaEje
    }
    Texto {
        lx: 1075; bl: 245; tam: 20
        text: raiz._unidadEje("derecho", I18n.t("unidades.presion", I18n.lang))
        color: raiz.paleta.etiquetaEje
    }

    // ---- cuadrícula y etiquetas Y ----
    // Sin zoom las dos escalas tienen las mismas divisiones y las líneas
    // coinciden; con zoom la cuadrícula sigue al eje izquierdo y las etiquetas
    // del derecho van en sus propias marcas redondas (ZOM-02).
    Repeater {
        model: raiz.marcasIzquierda
        delegate: Item {
            id: linea
            required property var modelData
            required property int index
            readonly property real yLinea: raiz.yDe(linea.modelData, "izquierdo")
            anchors.fill: parent
            Rectangle {
                x: raiz.m(68); y: linea.yLinea - height / 2
                width: raiz.m(1059 - 68); height: Math.max(1, raiz.m(1.2))
                color: Math.abs(linea.yLinea - raiz.yAbajo) < 0.5 ? raiz.paleta.eje : raiz.paleta.cuadricula
            }
            Text {
                x: raiz.m(55) - width
                y: linea.yLinea - height / 2 - raiz.m(3)
                text: raiz._etiqueta(linea.modelData)
                color: raiz.paleta.etiquetaEje
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(20)
            }
        }
    }
    Repeater {
        model: raiz.marcasDerecha
        delegate: Text {
            id: etiquetaDer
            required property var modelData
            x: raiz.m(1075)
            y: raiz.yDe(etiquetaDer.modelData, "derecho") - height / 2 - raiz.m(3)
            text: raiz._etiqueta(etiquetaDer.modelData)
            color: raiz.paleta.etiquetaEje
            font.family: Tipografia.familia
            font.pixelSize: raiz.fuente(20)
        }
    }
    // con zoom la marca más baja puede no caer en el borde: línea del eje aparte
    Rectangle {
        visible: raiz._conVentana
        x: raiz.m(68); y: raiz.yAbajo - height / 2
        width: raiz.m(1059 - 68); height: Math.max(1, raiz.m(1.2))
        color: raiz.paleta.eje
    }

    // ---- eje X: marcas y etiquetas ----
    Repeater {
        model: raiz.marcasX
        delegate: Item {
            id: marca
            required property var modelData
            required property int index
            readonly property real xMarca: raiz.xDe(marca.modelData)
            anchors.fill: parent
            Rectangle {
                x: marca.xMarca - width / 2; y: raiz.yAbajo
                width: Math.max(1, raiz.m(1.2)); height: raiz.m(6)
                color: raiz.paleta.eje
            }
            Text {
                x: marca.xMarca - width / 2
                y: raiz.yb(741) - baselineOffset
                text: raiz._etiqueta(marca.modelData)
                color: raiz.paleta.etiquetaEje
                font.family: Tipografia.familia
                font.pixelSize: raiz.fuente(20)
            }
        }
    }
    Text {
        x: raiz.m(564) - width / 2
        y: raiz.yb(779) - baselineOffset
        text: I18n.t("ciclo.grafica_eje_tiempo", I18n.lang)
        color: raiz.paleta.tituloEje
        font.family: Tipografia.familia
        font.pixelSize: raiz.fuente(20)
    }

    // ---- divisores de fase e íconos ----
    // Cada fase ocupa [inicio, inicio de la siguiente | tiempo actual]; la línea
    // punteada marca el comienzo de cada fase salvo la primera (en t = 0).
    Repeater {
        model: raiz.fases
        delegate: Item {
            id: tramo
            required property var modelData
            required property int index
            readonly property real inicio: tramo.modelData.inicioMin
            readonly property real fin: tramo.index + 1 < raiz.fases.length
                ? raiz.fases[tramo.index + 1].inicioMin : raiz.tiempoActualMin
            // ZOM-02: tramo recortado a la ventana (sin zoom, el tramo entero)
            readonly property real inicioVisible: Math.max(tramo.inicio, raiz.ventana.t0)
            readonly property real finVisible: Math.min(tramo.fin, raiz.ventana.t1)
            anchors.fill: parent

            Shape {
                visible: tramo.inicio > 0 && tramo.inicio >= raiz.ventana.t0
                         && tramo.inicio <= raiz.ventana.t1
                anchors.fill: parent
                ShapePath {
                    strokeColor: raiz.paleta.divisorFase
                    strokeWidth: Math.max(1, raiz.m(1.5))
                    strokeStyle: ShapePath.DashLine
                    dashPattern: [4, 3]
                    fillColor: "transparent"
                    startX: raiz.xDe(tramo.inicio); startY: raiz.m(164)
                    PathLine { x: raiz.xDe(tramo.inicio); y: raiz.yAbajo }
                }
            }
            // ícono blanco teñido de gris (misma técnica que IconoTenido de PantallaPreciclo.qml)
            Image {
                id: iconoFase
                visible: false
                width: raiz.m(52); height: width   // tinta ≈ 43 px
                x: (raiz.xDe(tramo.inicioVisible) + raiz.xDe(tramo.finVisible)) / 2 - width / 2
                y: raiz.m(205) - height / 2
                source: raiz.iconosColor + "fase_" + tramo.modelData.clave + ".svg"
                sourceSize.width: width; sourceSize.height: height
            }
            MultiEffect {
                visible: raiz.xDe(tramo.finVisible) - raiz.xDe(tramo.inicioVisible) > raiz.m(40)
                x: iconoFase.x; y: iconoFase.y; width: iconoFase.width; height: iconoFase.height
                source: iconoFase
                colorization: 1.0
                colorizationColor: raiz.paleta.iconoFase
            }
        }
    }

    // ---- series ----
    Item {
        id: areaTrazado
        // ZOM-02: con zoom las curvas se recortan al área de trazado (sin zoom,
        // el mismo recorte de antes)
        x: raiz._conVentana ? raiz.xDato0 - raiz.m(3) : 0
        y: raiz.yArriba - (raiz._conVentana ? raiz.m(3) : raiz.m(10))
        width: raiz._conVentana ? raiz.xDato1 - raiz.xDato0 + raiz.m(6) : raiz.width
        height: raiz.yAbajo - y + raiz.m(2)
        clip: true
        Repeater {
            model: raiz.series
            delegate: Shape {
                id: trazo
                required property var modelData
                required property int index
                x: -areaTrazado.x; y: -areaTrazado.y
                width: raiz.width; height: raiz.height
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: raiz.colorSerie(trazo.index)
                    strokeWidth: raiz.m(3)
                    fillColor: "transparent"
                    joinStyle: ShapePath.RoundJoin
                    capStyle: ShapePath.RoundCap
                    PathPolyline { path: raiz._puntos(trazo.modelData) }
                }
            }
        }
    }

    // ---- interacción del cursor ----
    function _tDesdeX(px) {
        const ts = raiz.datos.t_min || []
        if (ts.length === 0) return NaN
        const v = raiz.ventana
        let t = v.t0 + (px - xDato0) / (xDato1 - xDato0) * (v.t1 - v.t0)
        if (raiz._conVentana) t = Math.max(v.t0, Math.min(v.t1, t))
        return Math.max(ts[0], Math.min(ts[ts.length - 1], t))
    }
    function _moverCursor(px) {
        raiz.cursorMin = raiz._tDesdeX(px)
        ocultarCursor.restart()
    }

    // ---- zoom: ventana, límites y restablecimiento (ZOM-03..ZOM-06) ----
    readonly property var _areaPx: ({ x0: xDato0, x1: xDato1, y0: yArriba, y1: yAbajo })
    // ventana de partida de un gesto: la vigente (si había una transición en
    // curso, se interrumpe y se parte de donde iba)
    function _ventanaParaGesto() {
        const v = Ejes.interpolarVentana(raiz.ventana, raiz.ventana, 0)   // copia
        if (raiz._desdeTransicion !== null) {
            transicionZoom.stop()
            raiz._desdeTransicion = null
            raiz._fijarVentanaZoom(v)     // queda donde iba, sin saltar a la completa
        }
        return v
    }
    function _fijarVentanaZoom(v) {
        const a = Ejes.acotarVentana(v, raiz.vistaCompleta)
        raiz.ventanaZoom = Ejes.esVistaCompleta(a, raiz.vistaCompleta) ? null : a
    }
    // Para el arnés de pruebas y las capturas: fija la ventana en minutos y en
    // unidades del eje izquierdo; el derecho toma la misma fracción de su escala.
    function fijarVentana(t0, t1, yIzq0, yIzq1) {
        raiz._ventanaParaGesto()          // interrumpe una transición en curso
        const c = raiz.vistaCompleta
        const r = (c.yDer1 - c.yDer0) / (c.yIzq1 - c.yIzq0)
        raiz._fijarVentanaZoom({ t0: t0, t1: t1, yIzq0: yIzq0, yIzq1: yIzq1,
                                 yDer0: c.yDer0 + (yIzq0 - c.yIzq0) * r,
                                 yDer1: c.yDer0 + (yIzq1 - c.yIzq0) * r })
    }
    // ZOM-06: vuelve a la vista completa con la transición de 300 ms
    function restablecerVista() {
        restablecerZoom.stop()
        if (raiz.ventanaZoom === null) return
        raiz._desdeTransicion = raiz.ventanaZoom
        raiz.ventanaZoom = null
        raiz._avance = 0
        transicionZoom.restart()
    }
    // ZOM-05: en el acto, sin transición
    function restablecerAhora() {
        restablecerZoom.stop()
        transicionZoom.stop()
        raiz._gesto = null
        raiz._desdeTransicion = null
        raiz.ventanaZoom = null
    }
    // toque en el área de trazado: reinicia la cuenta de ZOM-06
    function _tocado() { restablecerZoom.restart() }

    NumberAnimation {
        id: transicionZoom
        target: raiz; property: "_avance"
        from: 0; to: 1; duration: 300
        easing.type: Easing.InOutQuad
        onFinished: raiz._desdeTransicion = null
    }
    Timer {
        id: restablecerZoom
        interval: raiz.restablecerZoomMs
        onTriggered: raiz.restablecerVista()
    }

    // ZOM-05: unidades, otro ciclo, sin datos o fuera de la vista
    readonly property string unidadesEjes: _unidadEje("izquierdo", "") + "|" + _unidadEje("derecho", "")
    onUnidadesEjesChanged: restablecerAhora()
    property var _huellaDatos: null
    onDatosChanged: {
        const t = raiz.datos ? raiz.datos.t_min : []
        if (!Ejes.continuaDatos(raiz._huellaDatos, t)) raiz.restablecerAhora()
        raiz._huellaDatos = Ejes.huellaDatos(t)
    }
    onVisibleChanged: if (!visible) restablecerAhora()

    // Rueda (solo para probar sin táctil, DECISIÓN SIN CONFIRMAR): rueda = zoom
    // en X, Ctrl + rueda = zoom en Y, centrados en el puntero.
    function _rueda(px, py, delta, enY) {
        if (!delta) return
        const frac = enY ? (raiz.yAbajo - py) / (raiz.yAbajo - raiz.yArriba)
                         : (px - raiz.xDato0) / (raiz.xDato1 - raiz.xDato0)
        raiz._fijarVentanaZoom(Ejes.ventanaPorRueda(raiz._ventanaParaGesto(), enY ? "y" : "x",
                                                    Math.pow(1.25, delta / 120),
                                                    Math.max(0, Math.min(1, frac))))
        raiz._tocado()
    }

    // Gesto de dos dedos: {inicio: {xa, ya, xb, yb}, ventana} mientras dura
    property var _gesto: null
    // true desde que se apoya el segundo dedo hasta soltar los dos: el cursor
    // queda quieto (ZOM-03)
    property bool _dosDedos: false

    // Mouse (y toque en equipos sin manejo táctil): cursor y rueda.
    MouseArea {
        id: toqueGrafica
        x: raiz.m(68); y: raiz.yArriba - raiz.m(20)
        width: raiz.m(1059 - 68); height: raiz.yAbajo - y
        preventStealing: true
        function mover(mx) {
            raiz._moverCursor(x + mx)
            raiz._tocado()
        }
        onPressed: (evento) => mover(evento.x)
        onPositionChanged: (evento) => mover(evento.x)
        onWheel: (rueda) => raiz._rueda(x + rueda.x, y + rueda.y, rueda.angleDelta.y,
                                        (rueda.modifiers & Qt.ControlModifier) !== 0)
    }
    // Táctil: encima del MouseArea y con mouseEnabled false, recibe todos los
    // puntos de contacto (el mouse sigue yendo al MouseArea). Un dedo mueve el
    // cursor como antes; dos dedos amplían y desplazan sin mover el cursor.
    // grab() en gestureStarted es el equivalente de preventStealing.
    MultiPointTouchArea {
        id: toqueMultitactil
        objectName: "toqueGraficaMultitactil"
        anchors.fill: toqueGrafica
        mouseEnabled: false
        minimumTouchPoints: 1
        maximumTouchPoints: 2
        touchPoints: [ TouchPoint { id: dedo1 }, TouchPoint { id: dedo2 } ]
        function actualizar() {
            const ox = toqueGrafica.x, oy = toqueGrafica.y
            const activos = [dedo1, dedo2].filter(p => p.pressed)
            raiz._tocado()
            if (activos.length === 2) {
                const pts = { xa: ox + dedo1.x, ya: oy + dedo1.y, xb: ox + dedo2.x, yb: oy + dedo2.y }
                raiz._dosDedos = true
                if (raiz._gesto === null) {
                    raiz._gesto = { inicio: pts, ventana: raiz._ventanaParaGesto() }
                } else {
                    raiz._fijarVentanaZoom(Ejes.ventanaPorGesto(raiz._gesto.ventana, raiz._gesto.inicio,
                                                                pts, raiz._areaPx, raiz.m(40)))
                }
            } else if (activos.length === 1) {
                raiz._gesto = null            // la ventana queda donde estaba
                if (!raiz._dosDedos) raiz._moverCursor(ox + activos[0].x)
            } else {
                raiz._gesto = null
                raiz._dosDedos = false
            }
        }
        onPressed: actualizar()
        onUpdated: actualizar()
        onReleased: actualizar()
        onCanceled: { raiz._gesto = null; raiz._dosDedos = false }
        onGestureStarted: (gesto) => gesto.grab()
    }
    Timer {
        id: ocultarCursor
        interval: raiz.ocultarCursorMs
        onTriggered: raiz.cursorMin = NaN
    }

    // ---- lupa indicadora (ZOM-07) ----
    // Única señal de vista ampliada; tocarla restablece con la transición.
    // Zona táctil de 56 × 56 px del mockup en la esquina superior derecha de la
    // cuadrícula; dibujo de 44 px. Orden: curvas < lupa < cursor y globo.
    Item {
        id: lupa
        objectName: "lupaZoomGrafica"
        visible: raiz.zoomActivo
        x: raiz.m(1059 - 6 - 56); y: raiz.yArriba + raiz.m(6)
        width: raiz.m(56); height: width
        Rectangle {
            anchors.centerIn: parent
            width: raiz.m(44); height: width; radius: width / 2
            color: Colores.fondoTarjeta
            opacity: 0.85
        }
        IconoColor {
            anchors.centerIn: parent
            width: raiz.m(30); height: width
            source: raiz.iconosColor + "lupa.svg"
            color: Colores.graficaZoomIcono
        }
        MouseArea { anchors.fill: parent; onClicked: raiz.restablecerVista() }
    }

    // ---- cursor y globo de valores ----
    Item {
        id: cursor
        readonly property int indice: isNaN(raiz.cursorMin) ? -1 : raiz._indiceCercano(raiz.cursorMin)
        readonly property real tCursor: indice >= 0 ? raiz.datos.t_min[indice] : 0
        readonly property real xCursor: raiz.xDe(tCursor)
        // con zoom, el cursor solo se ve si su lectura cae en la ventana
        visible: indice >= 0 && (!raiz._conVentana
                                 || (tCursor >= raiz.ventana.t0 && tCursor <= raiz.ventana.t1))
        anchors.fill: parent

        Rectangle {
            x: cursor.xCursor - width / 2; y: raiz.m(272)
            width: raiz.m(3); height: raiz.yAbajo - y - raiz.m(8)
            color: raiz.paleta.cursor
        }
        Repeater {
            model: raiz.series
            delegate: Rectangle {
                id: punto
                required property var modelData
                required property int index
                readonly property var valor: cursor.indice >= 0 ? raiz._valor(punto.modelData.clave, cursor.indice) : null
                // con zoom en Y, un punto fuera de la ventana no se dibuja
                visible: punto.valor !== null && punto.valor !== undefined
                         && (!raiz._conVentana
                             || (raiz.yDe(punto.valor, punto.modelData.eje) >= raiz.yArriba - 0.5
                                 && raiz.yDe(punto.valor, punto.modelData.eje) <= raiz.yAbajo + 0.5))
                x: cursor.xCursor - width / 2
                y: (punto.visible ? raiz.yDe(punto.valor, punto.modelData.eje) : 0) - height / 2
                width: raiz.diametroPuntoCursor; height: width; radius: width / 2
                color: raiz.colorSerie(punto.index)
                border.color: Colores.graficaCursorFondo; border.width: raiz.m(2)
            }
        }

        // Globo: 220 x 145 en el mockup, a la derecha del cursor salvo que no quepa;
        // nunca se sale del área de la tarjeta. AJ-03: cada nombre se abrevia si
        // no cabe hasta su valor; si ni el abreviado cabe, el globo crece lo
        // justo para la fila más ancha (y para la hora). Nunca se recorta (D8-5.4).
        Rectangle {
            id: globo
            objectName: "globoGrafica"
            // margen entre el nombre y el valor de una fila (≈ 8 px del mockup)
            readonly property real margenNombre: raiz.m(8)
            property int _revFilas: 0
            readonly property real anchoNecesario: {
                void _revFilas
                let n = hora.implicitWidth + raiz.m(18 + 18)
                for (let i = 0; i < filasGlobo.count; ++i) {
                    const f = filasGlobo.itemAt(i)
                    if (f) n = Math.max(n, f.anchoNecesario)
                }
                return n
            }
            width: Math.max(raiz.m(220), Math.ceil(anchoNecesario)); height: raiz.m(145)
            // A11 (tanda 28): la posición la calcula ui_qml/domain/posicion_card.py
            // (a un costado del cursor, en un hueco sin curvas); aquí solo se dibuja.
            readonly property var pos: PosicionCard.posicionar(
                [raiz.m(68), raiz.yArriba, raiz.m(1059), raiz.yAbajo],
                cursor.xCursor, width, height,
                raiz._curvasCerca(cursor.xCursor - width - raiz.m(40), cursor.xCursor + width + raiz.m(40)),
                raiz.diametroPuntoCursor / 2 + raiz.m(8))
            x: pos.x; y: pos.y
            radius: raiz.m(14)
            color: Colores.graficaCursorFondo
            border.width: raiz.m(1.5); border.color: Colores.graficaCursorBorde
            layer.enabled: true
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: Colores.sombraSuave
                shadowVerticalOffset: raiz.m(2)
                shadowBlur: 0.5
            }
            Text {
                id: hora
                objectName: "horaGlobo"
                x: raiz.m(18); y: raiz.m(36) - baselineOffset
                text: raiz._formatoMmSs(cursor.tCursor) + " " + I18n.t("unidades.tiempo", I18n.lang)
                color: raiz.paleta.texto
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoMedium
                font.pixelSize: raiz.fuente(21)
            }
            Repeater {
                id: filasGlobo
                model: raiz.series
                onItemAdded: globo._revFilas++
                onItemRemoved: globo._revFilas++
                delegate: Item {
                    id: filaGlobo
                    objectName: "filaGlobo"
                    required property var modelData
                    required property int index
                    readonly property var valor: cursor.indice >= 0 ? raiz._valor(filaGlobo.modelData.clave, cursor.indice) : null
                    readonly property real bl: raiz.m(61 + filaGlobo.index * 29)
                    // ancho del globo con el que cabe esta fila con el nombre
                    // abreviado (el completo si no hay abreviado)
                    readonly property real anchoNecesario: raiz.m(35) + medidaAbrev.advanceWidth
                                                           + globo.margenNombre + valorFila.implicitWidth
                                                           + raiz.m(220 - 211)
                    anchors.fill: parent
                    Rectangle {
                        x: raiz.m(17); y: filaGlobo.bl - raiz.m(10)
                        width: raiz.m(11); height: width; radius: width / 2
                        color: raiz.colorSerie(filaGlobo.index)
                    }
                    TextoAjustable {
                        id: nombreFila
                        objectName: "nombreFilaGlobo"
                        x: raiz.m(35); y: filaGlobo.bl - baselineOffset
                        textoCompleto: raiz.textoSerie(filaGlobo.modelData)
                        textoAbreviado: raiz.textoSerieAbrev(filaGlobo.modelData)
                        anchoDisponible: valorFila.x - globo.margenNombre - x
                        color: raiz.paleta.texto
                        font.family: Tipografia.familia
                        font.pixelSize: raiz.fuente(13)
                    }
                    TextMetrics {
                        id: medidaAbrev
                        font: nombreFila.font
                        text: nombreFila.textoAbreviado !== "" ? nombreFila.textoAbreviado
                                                               : nombreFila.textoCompleto
                    }
                    Text {
                        id: valorFila
                        objectName: "valorFilaGlobo"
                        // alineado a la derecha del globo (mockup: termina en x = 211 de 220)
                        x: globo.width - raiz.m(220 - 211) - width; y: filaGlobo.bl - baselineOffset
                        text: (filaGlobo.valor === null || filaGlobo.valor === undefined
                               ? I18n.t("sistema.sin_lectura", I18n.lang)
                               : Number(filaGlobo.valor).toFixed(1)) + " " + filaGlobo.modelData.unidad
                        color: raiz.paleta.texto
                        font.family: Tipografia.familia
                        font.weight: Tipografia.pesoSemiBold
                        font.pixelSize: raiz.fuente(16)
                    }
                }
            }
        }
    }

    // ---- desplegable "Tiempos" ----
    // PROVISIONAL (sin diseño en el mockup): lista bajo el botón con la duración
    // de cada fase que aplica; completadas = duración final, activa = en curso
    // (se actualiza con el progreso), pendientes = "—". Se cierra al tocar fuera.
    function _formatoDuracion(seg) {
        if (seg === null || seg === undefined || !isFinite(seg))
            return I18n.t("sistema.sin_lectura", I18n.lang)
        const s = Math.max(0, Math.floor(seg))
        const dos = n => n < 10 ? "0" + n : "" + n
        return dos(Math.floor(s / 3600)) + ":" + dos(Math.floor(s % 3600 / 60)) + ":" + dos(s % 60)
    }
    function _nombreFase(clave) {
        return I18n.existe("fases." + clave, I18n.lang) ? I18n.t("fases." + clave, I18n.lang) : ""
    }
    MouseArea {
        visible: desplegable.abierto
        anchors.fill: parent
        onClicked: desplegable.abierto = false
    }
    Rectangle {
        id: desplegable
        property bool abierto: false
        visible: abierto && !raiz.modoPantallaCompleta
        x: botonTiempos.x + botonTiempos.width - width
        y: botonTiempos.y + botonTiempos.height + raiz.m(8)
        width: raiz.m(420)
        height: columnaTiempos.height + raiz.m(16)
        radius: raiz.m(10)
        color: Colores.fondoTarjeta
        border.width: raiz.m(1.5); border.color: raiz.paleta.bordeBoton
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: Colores.sombraSuave
            shadowVerticalOffset: raiz.m(3)
            shadowBlur: 0.5
        }
        MouseArea { anchors.fill: parent }   // no cerrar al tocar dentro
        Column {
            id: columnaTiempos
            x: 0; y: raiz.m(8)
            width: parent.width
            Repeater {
                model: raiz.tiempos
                delegate: Item {
                    id: filaTiempo
                    required property var modelData
                    width: columnaTiempos.width
                    height: raiz.m(56)
                    Text {
                        x: raiz.m(24)
                        anchors.verticalCenter: parent.verticalCenter
                        text: raiz._nombreFase(filaTiempo.modelData.fase)
                        color: raiz.paleta.texto
                        font.family: Tipografia.familia
                        font.weight: filaTiempo.modelData.estado === "activa" ? Tipografia.pesoBold : Tipografia.pesoRegular
                        font.pixelSize: raiz.fuente(21)
                    }
                    Text {
                        x: parent.width - width - raiz.m(24)
                        anchors.verticalCenter: parent.verticalCenter
                        text: filaTiempo.modelData.estado === "pendiente"
                              ? I18n.t("sistema.sin_lectura", I18n.lang)
                              : raiz._formatoDuracion(filaTiempo.modelData.duracion_s)
                        color: raiz.paleta.texto
                        font.family: Tipografia.familia
                        font.weight: filaTiempo.modelData.estado === "activa" ? Tipografia.pesoBold : Tipografia.pesoRegular
                        font.pixelSize: raiz.fuente(21)
                        font.features: { "tnum": 1 }
                    }
                }
            }
        }
    }
}

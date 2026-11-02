pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.I18n

// Barra de fases de la pantalla de ciclo en curso
// (planeacion_pantalla_ciclo_en_curso.md §5.3; llenado de fases: contrato A-3
// de planeacion_llenado_fases_decisiones.md). Ocupa el ancho de la pantalla;
// geometría en px absolutos del mockup (escala = px reales por px del mockup):
// círculos de 85 px con centro en y = 480, entre x = 128 y x = 1068, nombre
// debajo (línea base 550). Las fases que no aplican no llegan en `fases`, y la
// distribución horizontal se recalcula con las que quedan.
//
// Este componente es el contenedor y el único que compara la respuesta
// anterior con la nueva; cada círculo (CirculoFaseLiquido) y cada conector
// (ConectorFase) recibe el modo de animación con aplicar(modo, ...).
Item {
    id: raiz

    property real escala: 1.0
    // [{fase: "vacio", estado: "completada" | "activa" | "pendiente"
    //                         | "fallida" | "interrumpida",
    //   fraccion: 0..1 | null, referencia_s}], en orden.
    // FC-06 (tanda 21): la fase en la que terminó el ciclo llega "fallida"
    // (fallo o paro de emergencia: círculo Colores.alarmaAlta) o "interrumpida"
    // (cancelación: Colores.advertencia), con el mismo ícono en blanco.
    property var fases: []

    // Llenado de fases. Entradas con defecto para que arneses y pruebas
    // anteriores sigan funcionando.
    property bool datosVigentes: true
    property int cicloDbId: -1
    property bool enVista: true
    property real topeFraccion: 0.90
    property real nivelIndeterminado: 0.25
    property bool instantaneo: Qt.platform.pluginName === "offscreen"
    readonly property QtObject tiempos: QtObject {
        readonly property int cierreMs: 300
        readonly property int conectorMs: 600
        readonly property int entradaMs: 700
        readonly property int subidaMs: 950
        readonly property int bajadaMs: 1200
        readonly property int saltoMs: 400
        readonly property int terminacionMs: 200
        readonly property int periodoOndaMs: 2500
    }

    function m(v) { return v * escala }
    function fuente(v) { return Math.max(1, Math.round(m(v))) }
    function nombre(clave) {
        return I18n.existe("fases." + clave, I18n.lang) ? I18n.t("fases." + clave, I18n.lang) : ""
    }

    readonly property real xPrimera: 128
    readonly property real xUltima: 1068
    readonly property real diametro: 85
    function centroX(i) {
        return fases.length > 1
            ? xPrimera + i * (xUltima - xPrimera) / (fases.length - 1)
            : (xPrimera + xUltima) / 2
    }

    function colorEtiqueta(estado) {
        return estado === "completada" ? Colores.faseEtiqueta
             : estado === "activa" ? Colores.faseEtiquetaActiva
             : Colores.fasePendienteEtiqueta
    }

    // ---- sincronización con la respuesta anterior ----
    property var _previas: []
    property bool _primeraCarga: true
    property string _claves: ""

    Timer {
        id: temporizadorPrimera
        interval: 2000
        onTriggered: raiz._primeraCarga = false
    }
    Component.onCompleted: {
        _claves = _clavesDe(fases)
        _previas = _instantanea(fases)
        temporizadorPrimera.restart()
    }
    onEnVistaChanged: if (enVista) { _primeraCarga = true; temporizadorPrimera.restart() }
    onCicloDbIdChanged: { _primeraCarga = true; temporizadorPrimera.restart() }
    onFasesChanged: {
        const claves = _clavesDe(fases)
        if (claves !== _claves) { _claves = claves; _primeraCarga = true }
        _sincronizar()
    }

    function _clavesDe(fs) { return (fs || []).map(f => f.fase).join("|") }
    function _instantanea(fs) {
        return (fs || []).map(f => ({ fase: f.fase, estado: f.estado,
                                      fraccion: (f.fraccion === undefined ? null : f.fraccion) }))
    }
    function _igual(a, b) {
        if (a === null || b === null) return a === b
        return Math.abs(a - b) < 1e-6
    }

    function _sincronizar() {
        const nuevas = _instantanea(fases)
        const previas = _previas
        const n = nuevas.length
        if (n === 0) { _previas = nuevas; return }
        const fijar = _primeraCarga || instantaneo || previas.length !== n
        const modos = [], modosCon = [], retardos = []
        const completadas = []
        if (!fijar) {
            for (let i = 0; i < n; i++)
                if (nuevas[i].estado === "completada" && previas[i].estado !== "completada")
                    completadas.push(i)
        }
        for (let i = 0; i < n; i++) {
            const q = nuevas[i]
            let modo = "nada", modoCon = "nada", retardo = 0
            if (fijar) {
                modo = "fijar"; modoCon = "fijar"
            } else {
                const p = previas[i]
                const cambioEstado = p.estado !== q.estado
                if (cambioEstado && (q.estado === "fallida" || q.estado === "interrumpida")) {
                    modo = "terminacion"
                } else if (cambioEstado) {
                    if (completadas.length >= 2) modo = "salto"
                    else if (completadas.length === 1 && i === completadas[0]) modo = "cierre"
                    else if (q.estado === "activa") {
                        modo = "entrada"
                        if (i > 0 && completadas.length === 1 && completadas[0] === i - 1)
                            retardo = tiempos.cierreMs + tiempos.conectorMs
                    } else modo = "fijar"
                } else if (!_igual(p.fraccion, q.fraccion)) {
                    modo = q.estado === "activa" ? "fraccion" : "fijar"
                }
                if (i > 0) {
                    const loNuevo = nuevas[i - 1].estado === "completada"
                    const loPrevio = previas[i - 1].estado === "completada"
                    if (loNuevo !== loPrevio) {
                        if (!loNuevo) modoCon = "fijar"
                        else if (completadas.length >= 2) modoCon = "salto"
                        else if (completadas.length === 1 && completadas[0] === i - 1) modoCon = "cierre"
                        else modoCon = "salto"
                    }
                }
            }
            modos.push(modo); modosCon.push(modoCon); retardos.push(retardo)
        }
        // una animación en curso se termina antes de arrancar el modo nuevo
        const grande = modos.some(x => x !== "nada" && x !== "fraccion") || modosCon.some(x => x !== "nada")
        if (grande) {
            for (let i = 0; i < n; i++) {
                const it = repetidor.itemAt(i)
                if (it) { it.circulo._terminar(); it.conector._terminar() }
            }
        }
        for (let i = 0; i < n; i++) {
            const it = repetidor.itemAt(i)
            if (!it) continue
            if (modos[i] !== "nada") it.circulo.aplicar(modos[i], nuevas[i], retardos[i])
            if (modosCon[i] !== "nada")
                it.conector.aplicar(modosCon[i], i > 0 && nuevas[i - 1].estado === "completada")
        }
        _previas = nuevas
        _primeraCarga = false
        temporizadorPrimera.stop()
    }

    Repeater {
        id: repetidor
        model: raiz.fases.length
        delegate: Item {
            id: fase
            required property int index
            readonly property var datos: raiz.fases[fase.index]
            readonly property real cx: raiz.centroX(fase.index)
            property alias circulo: circ
            property alias conector: con
            anchors.fill: parent
            z: raiz.fases.length - fase.index

            ConectorFase {
                id: con
                objectName: "conectorFase_" + (fase.datos ? fase.datos.fase : "")
                visible: fase.index > 0
                escala: raiz.escala
                tiempos: raiz.tiempos
                instantaneo: raiz.instantaneo
                x: fase.index > 0 ? raiz.m(raiz.centroX(fase.index - 1) + raiz.diametro / 2 - 1) : 0
                y: raiz.m(477)
                width: fase.index > 0
                       ? raiz.m(raiz.centroX(fase.index) - raiz.centroX(fase.index - 1) - raiz.diametro + 2) : 0
                height: raiz.m(7)
            }
            CirculoFaseLiquido {
                id: circ
                objectName: "circuloFase_" + (fase.datos ? fase.datos.fase : "")
                fase: fase.datos ? fase.datos.fase : ""
                escala: raiz.escala
                tope: raiz.topeFraccion
                nivelIndeterminado: raiz.nivelIndeterminado
                datosVigentes: raiz.datosVigentes
                chorroHabilitado: fase.index > 0 && con.progreso >= 1
                tiempos: raiz.tiempos
                instantaneo: raiz.instantaneo
                x: raiz.m(fase.cx - raiz.diametro / 2); y: raiz.m(480 - raiz.diametro / 2)
                Component.onCompleted: {
                    const d = fase.datos
                    if (d) {
                        circ.aplicar("fijar", d)
                        con.aplicar("fijar", fase.index > 0 && raiz.fases[fase.index - 1].estado === "completada")
                    }
                }
            }
            Text {
                x: raiz.m(fase.cx) - width / 2
                y: raiz.m(550) - baselineOffset
                text: raiz.nombre(fase.datos ? fase.datos.fase : "")
                color: raiz.colorEtiqueta(fase.datos ? fase.datos.estado : "")
                font.family: Tipografia.familia
                font.weight: Tipografia.pesoSemiBold
                font.pixelSize: raiz.fuente(13.5)
            }
        }
    }
}

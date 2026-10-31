pragma ComponentBehavior: Bound
import QtQuick
import Tema
import "../Pantallas"

// PRUEBA (Fase 2 de planeacion_pantalla_ciclo_en_curso.md): muestra
// PantallaCicloEnCurso con DATOS DE EJEMPLO que imitan el mockup
// (images/pantalla_ciclo_con_grafica_editada.png) para la revisión visual.
// NO es parte de la navegación de producción ni se conecta al backend: solo la
// abre ui_qml/prueba_ciclo_en_curso.py. Mismo escalado que Main.qml.
//
// MODO DEMOSTRACION de la barra de fases con líquido (llenado de fases, paso
// 4a): con la propiedad `demostracion` en true recorre escenarios (llenado,
// cambio de fase con chorro, vaciado parcial, reinicio de exposición, salto de
// fases, fallo, cancelación, sin referencia, sin datos vigentes) con rótulos.
// Teclas: N siguiente, P anterior, R repetir, A automático sí/no, ESPACIO pausa.
// Hay que lanzarlo con la plataforma real (no offscreen), desde la raíz del
// repositorio:
//   python tests/banco/llf_capturas_barra_fases.py --demo
// (equivale a cargar este archivo con QQmlApplicationEngine y
// setInitialProperties({"demostracion": True}); en el worktree llenado-fases
// poner antes PYTHONPATH=<raíz>\src).
Window {
    id: ventana
    width: 600; height: 960
    visible: true
    color: Colores.fondoMarinoOscuro

    property bool demostracion: false


    Binding {
        target: Escala
        property: "factor"
        value: Math.min(ventana.width / Escala.anchoDiseno, ventana.height / Escala.altoDiseno)
    }
    Binding {
        target: Escala
        property: "altoLienzo"
        value: Math.max(Escala.altoDiseno, ventana.height / Escala.factor)
    }

    readonly property var fasesFijas: [
        { fase: "precalentamiento", estado: "activa" },
        { fase: "vacio", estado: "pendiente" },
        { fase: "calentamiento", estado: "pendiente" },
        { fase: "esterilizacion", estado: "pendiente" },
        { fase: "descompresion", estado: "pendiente" },
        { fase: "secado", estado: "pendiente" },
    ]

    // ================= MODO DEMOSTRACION (solo con demostracion: true) =================
    property var fasesDemo: []
    property bool vigentesDemo: true
    property int escenario: 0
    property int paso: 0
    property bool automatico: true
    property bool pausa: false
    readonly property var claves: ["precalentamiento", "vacio", "calentamiento",
                                   "esterilizacion", "descompresion", "secado"]

    // spec: un texto por fase: "c" completada, "p" pendiente, "f" fallida,
    // "i" interrumpida, "a" activa sin referencia, "a:0.35" activa con fracción
    function armarFases(spec) {
        return spec.map((t, i) => {
            const e = t.charAt(0)
            const estado = e === "c" ? "completada" : e === "p" ? "pendiente"
                         : e === "f" ? "fallida" : e === "i" ? "interrumpida" : "activa"
            const fr = e === "a" ? (t.length > 2 ? parseFloat(t.substring(2)) : null)
                     : (e === "c" ? 1.0 : (e === "p" ? 0.0 : null))
            return { fase: ventana.claves[i], estado: estado, fraccion: fr }
        })
    }
    // paso: [espera en ms antes de aplicarlo, spec, datos vigentes]
    readonly property var escenarios: [
        { nombre: "1. Llenado progresivo de una fase (vacío)",
          pasos: [[0, ["c","a:0.05","p","p","p","p"], true], [1000, ["c","a:0.2","p","p","p","p"], true],
                  [1000, ["c","a:0.4","p","p","p","p"], true], [1000, ["c","a:0.6","p","p","p","p"], true],
                  [1000, ["c","a:0.8","p","p","p","p"], true], [1000, ["c","a:0.9","p","p","p","p"], true],
                  [1000, ["c","a:0.9","p","p","p","p"], true]] },
        { nombre: "2. Cambio de fase: conector y chorro (nivel siguiente < 0.5)",
          pasos: [[0, ["c","a:0.85","p","p","p","p"], true], [1500, ["c","c","a:0.1","p","p","p"], true],
                  [2800, ["c","c","a:0.25","p","p","p"], true], [1000, ["c","c","a:0.4","p","p","p"], true],
                  [1000, ["c","c","a:0.55","p","p","p"], true], [1000, ["c","c","a:0.7","p","p","p"], true]] },
        { nombre: "3. Recálculo con vaciado parcial (0.90 a 0.75)",
          pasos: [[0, ["c","c","a:0.85","p","p","p"], true], [1500, ["c","c","a:0.90","p","p","p"], true],
                  [1500, ["c","c","a:0.75","p","p","p"], true], [2500, ["c","c","a:0.78","p","p","p"], true]] },
        { nombre: "4. Reinicio de exposición (esterilización baja a 0)",
          pasos: [[0, ["c","c","c","a:0.5","p","p"], true], [1000, ["c","c","c","a:0.7","p","p"], true],
                  [1500, ["c","c","c","a:0.0","p","p"], true], [2500, ["c","c","c","a:0.1","p","p"], true],
                  [1000, ["c","c","c","a:0.2","p","p"], true]] },
        { nombre: "5. Salto de varias fases a la vez",
          pasos: [[0, ["c","a:0.5","p","p","p","p"], true], [2000, ["c","c","c","a:0.2","p","p"], true],
                  [2500, ["c","c","c","a:0.3","p","p"], true]] },
        { nombre: "6. Fallo en esterilización (fallida, sólida roja)",
          pasos: [[0, ["c","c","c","a:0.4","p","p"], true], [1500, ["c","c","c","a:0.5","p","p"], true],
                  [1000, ["c","c","c","f","p","p"], true]] },
        { nombre: "7. Cancelación (interrumpida, sólida naranja)",
          pasos: [[0, ["c","c","a:0.6","p","p","p"], true], [1500, ["c","c","i","p","p","p"], true]] },
        { nombre: "8. Sin referencia (nivel fijo 0.25 con onda)",
          pasos: [[0, ["c","c","a","p","p","p"], true], [3000, ["c","c","a","p","p","p"], true]] },
        { nombre: "9. Sin datos vigentes (onda detenida) y regreso",
          pasos: [[0, ["c","c","c","a:0.5","p","p"], true], [2000, ["c","c","c","a:0.5","p","p"], false],
                  [4000, ["c","c","c","a:0.55","p","p"], true], [2500, ["c","c","c","a:0.6","p","p"], true]] },
        { nombre: "10. Fin exitoso (último círculo sube a 1.0)",
          pasos: [[0, ["c","c","c","c","c","a:0.85"], true], [1500, ["c","c","c","c","c","c"], true],
                  [2500, ["c","c","c","c","c","c"], true]] }
    ]
    readonly property var escActual: escenarios[escenario]

    function iniciarEscenario(i) {
        escenario = ((i % escenarios.length) + escenarios.length) % escenarios.length
        paso = -1
        // vaciar y volver a poner las fases: la barra lo trata como primera carga
        fasesDemo = []
        vigentesDemo = true
        temporizadorDemo.interval = 400
        temporizadorDemo.restart()
    }
    function aplicarPaso(k) {
        paso = k
        const p = escActual.pasos[k]
        vigentesDemo = p[2]
        fasesDemo = armarFases(p[1])
        if (k + 1 < escActual.pasos.length) {
            temporizadorDemo.interval = escActual.pasos[k + 1][0]
            temporizadorDemo.restart()
        } else if (automatico) {
            temporizadorDemo.interval = 3000
            temporizadorDemo.restart()
        } else temporizadorDemo.stop()
    }
    Timer {
        id: temporizadorDemo
        repeat: false
        onTriggered: {
            if (ventana.pausa) { restart(); return }
            if (ventana.paso + 1 < ventana.escActual.pasos.length) ventana.aplicarPaso(ventana.paso + 1)
            else ventana.iniciarEscenario(ventana.escenario + 1)
        }
    }
    Component.onCompleted: if (demostracion) iniciarEscenario(0)
    Shortcut { sequence: "N"; enabled: ventana.demostracion; onActivated: ventana.iniciarEscenario(ventana.escenario + 1) }
    Shortcut { sequence: "P"; enabled: ventana.demostracion; onActivated: ventana.iniciarEscenario(ventana.escenario - 1) }
    Shortcut { sequence: "R"; enabled: ventana.demostracion; onActivated: ventana.iniciarEscenario(ventana.escenario) }
    Shortcut { sequence: "A"; enabled: ventana.demostracion; onActivated: ventana.automatico = !ventana.automatico }
    Shortcut { sequence: "Space"; enabled: ventana.demostracion; onActivated: ventana.pausa = !ventana.pausa }
    Rectangle {
        visible: ventana.demostracion
        z: 1000
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        height: rotuloDemo.implicitHeight + 16
        color: "#CC000000"
        Text {
            id: rotuloDemo
            anchors.fill: parent; anchors.margins: 8
            wrapMode: Text.WordWrap
            color: "white"
            font.pixelSize: 15
            text: "ESCENARIO " + ventana.escActual.nombre + "  (paso " + (ventana.paso + 1) + "/"
                  + ventana.escActual.pasos.length + (ventana.vigentesDemo ? "" : ", SIN DATOS VIGENTES") + ")\n"
                  + "[N] siguiente  [P] anterior  [R] repetir  [A] automático: "
                  + (ventana.automatico ? "sí" : "no") + "  [Espacio] pausa: " + (ventana.pausa ? "sí" : "no")
        }
    }
    // ===================================================================================

    // ---------------- DATOS DE EJEMPLO (no son lecturas reales) ----------------
    // Curvas lineales por tramos trazadas a ojo sobre el mockup; una muestra por
    // segundo durante 40 min (2400 puntos, ejercita la decimación).
    function _interpolar(puntos, t) {
        if (t <= puntos[0][0]) return puntos[0][1]
        for (let i = 1; i < puntos.length; i++) {
            if (t <= puntos[i][0]) {
                const a = puntos[i - 1], b = puntos[i]
                return a[1] + (b[1] - a[1]) * (t - a[0]) / (b[0] - a[0])
            }
        }
        return puntos[puntos.length - 1][1]
    }
    readonly property var _ejemplo: {
        const camara = [[0,44],[2,58],[5,85],[7,100],[9,117],[12,127],[15,130],[20,130],[22,128],
                        [25,118],[28,107],[31,106],[33,98],[34.5,94],[35.5,95],[37,73],[39,53],[40,46]]
        const ref = [[0,34],[3,52],[6,72],[9,98],[10,104],[12,113],[15,120],[19,122],[21,120],[23,113],
                     [26,98],[30,93],[33,83],[34.5,82],[35.5,95],[36.5,84],[38,80],[40,64]]
        // presión trazada en unidades del eje izquierdo (0..150) y llevada a 0..200 kPa
        const pres = [[0,18],[2,24],[4,45],[6,56],[8,58],[9,78],[11,82],[12,92],[15,90],[20,93],
                      [25,90],[28,78],[32,68],[35,57],[37,45],[38.5,34],[40,30]]
        const d = { t_min: [], temp_camara: [], temp_ref: [], pres_camara: [] }
        for (let s = 0; s <= 2400; s++) {
            const t = s / 60
            d.t_min.push(t)
            d.temp_camara.push(_interpolar(camara, t))
            d.temp_ref.push(_interpolar(ref, t))
            d.pres_camara.push(_interpolar(pres, t) * 200 / 150)
        }
        return d
    }
    // ---------------------------------------------------------------------------

    Item {
        width: Escala.px(Escala.anchoDiseno)
        height: Escala.px(Escala.altoLienzo)
        anchors.centerIn: parent
        clip: true

        PantallaCicloEnCurso {
            anchors.fill: parent
            // DATOS DE EJEMPLO
            cicloActivo: "03"
            programa: "BOWE & DICK"
            tempEsterilizacion: "134.0"
            tiempoEsterilizacion: "10"
            tiempoSecado: "15"
            tempCamara: "085.0"
            tempReferencia: "084.6"
            presionCamara: "100.8"
            datosVigentes: ventana.demostracion ? ventana.vigentesDemo : true
            conteoNotificaciones: 2
            modelo: "SPK-SAT 45H"
            serie: "Sn123456"
            fases: ventana.demostracion ? ventana.fasesDemo : ventana.fasesFijas
            transcurridoS: 923
            restanteS: 1477
            datosGrafica: ventana._ejemplo
            fasesGrafica: [
                { clave: "precalentamiento", inicioMin: 0 },
                { clave: "vacio", inicioMin: 8.85 },
                { clave: "esterilizacion", inicioMin: 20.0 },
                { clave: "secado", inicioMin: 33.9 },
            ]
            tiempoActualMin: 40
            cursorMin: 15.383
        }
    }
}

pragma ComponentBehavior: Bound
import QtQuick
import Tema

// Panel de teclado en pantalla (Paso 5 de planeacion_teclados_qml.md v2.1).
// Uno por ventana, declarado en Main.qml sobre el StackView e inyectado a cada
// pantalla como propiedad `teclado`. Muestra un solo teclado a la vez y entra
// desde el borde en 400 ms con cubic-bezier(0.2,0,0,1) (TEC-D06).
//
// Uso desde un campo:
//   teclado.abrirAlfanumerico(titulo, valorInicial, longitudMaxima, ocultar,
//                             texto => guardar(texto), siguiente)
//   teclado.abrirNumerico(titulo, unidad, valorInicial, minimo, maximo,
//                         decimales, valor => guardar(valor), siguiente)
// `siguiente` (opcional) es una función que abre el campo que sigue.
// Comportamiento pedido por Cristian (2026-10-01) en el uso real:
//   - Confirmar guarda el valor y pasa al campo siguiente; si no hay
//     siguiente, cierra el panel.
//   - Tocar otro campo sin Confirmar guarda lo escrito en el anterior (en el
//     numérico, solo si es un valor válido; si no, se descarta).
//   - Cancelar en el alfanumérico vacía el campo y cierra; en el numérico
//     descarta lo escrito y cierra (un campo numérico vacío no es válido).
// A diferencia de PanelModal, tocar fuera del panel no lo cierra: el toque
// llega a la pantalla (por ejemplo, a otro campo). textoEnEdicion permite al
// campo mostrar lo que se escribe. alturaOcupada dice cuánto tapa, para que
// la pantalla deje el campo activo a la vista.
//
// Modo acción (tanda 22, TEC-ACC-01..03):
//   teclado.abrirAlfanumericoAccion(titulo, valorInicial, longitudMaxima,
//                                   ocultar, texto => accion(texto))
// `alConfirmar` se llama una sola vez y solo al pulsar Confirmar con texto
// (Confirmar vacío no hace nada y deja el teclado abierto). Nada se entrega al
// escribir, al cancelar, al ocultar ni al abrir otro campo: lo escrito se
// descarta. El panel se cierra antes de llamar a `alConfirmar`, así un segundo
// Confirmar (doble toque o reentrante durante un envío síncrono) no envía nada
// y el callback puede abrir otro teclado o diálogo.
// Regla: un callback que ejecuta una acción (llamar a un controlador que envía
// al backend, abrir un diálogo u otro teclado, cambiar de pantalla) usa
// abrirAlfanumericoAccion; el modo en vivo (abrirAlfanumerico/abrirNumerico)
// es solo para asignar texto a una propiedad.
Item {
    id: raiz

    // "pie" (por defecto) o "superior"
    property string posicion: "pie"

    readonly property bool abierto: _tipo !== ""
    // Lo que se lleva escrito, para que el campo lo muestre mientras se edita.
    readonly property string textoEnEdicion: _tipo === "alfanumerico" ? alfanumerico.controlador.texto
                                           : _tipo === "numerico" ? numerico.controlador.texto
                                           : ""
    readonly property real alturaOcupada: abierto ? height : 0

    signal confirmado(var valor)
    signal cancelado()
    // Confirmar en el último campo de la cadena (no hay `siguiente`): la pantalla
    // decide qué corresponde (iniciar sesión, guardar...). Se emite con el panel
    // aún abierto, así la pantalla sabe qué campo estaba activo.
    signal terminado()

    property string _tipo: ""       // "", "numerico" o "alfanumerico"
    property var _alConfirmar: null
    property var _siguiente: null
    property var _inicialNumerico: null
    property bool _numericoComprometido: false
    // true: modo en vivo (abrirAlfanumerico/abrirNumerico); false: modo acción
    property bool _enVivo: true

    // Lo escrito llega al campo al instante, sin tocar Confirmar. Confirmar solo
    // pasa al siguiente campo; Ocultar cierra el panel conservando lo escrito.
    function _comprometerAlfanumerico() {
        if (_tipo === "alfanumerico" && _enVivo && _alConfirmar)
            _alConfirmar(alfanumerico.controlador.texto)
    }
    function _comprometerNumerico() {
        const c = numerico.controlador
        if (_tipo === "numerico" && _alConfirmar && c.valido && c.valor !== null && c.valor !== undefined) {
            _numericoComprometido = true
            _alConfirmar(c.valor)
        }
    }
    function ocultar() {
        cerrar()
    }

    function abrirAlfanumerico(titulo, valorInicial, longitudMaxima, ocultar, alConfirmar, siguiente) {
        _guardarPendiente()
        _enVivo = true
        alfanumerico.ocultarTexto = ocultar === true
        alfanumerico.abrir(titulo, valorInicial || "", longitudMaxima || 0)
        _alConfirmar = alConfirmar || null
        _siguiente = siguiente || null
        _tipo = "alfanumerico"
    }
    // Modo acción: entrega solo al Confirmar (ver la cabecera)
    function abrirAlfanumericoAccion(titulo, valorInicial, longitudMaxima, ocultar, alConfirmar) {
        _guardarPendiente()
        _enVivo = false
        alfanumerico.ocultarTexto = ocultar === true
        alfanumerico.abrir(titulo, valorInicial || "", longitudMaxima || 0)
        _alConfirmar = alConfirmar || null
        _siguiente = null
        _tipo = "alfanumerico"
    }
    function abrirNumerico(titulo, unidad, valorInicial, minimo, maximo, decimales, alConfirmar, siguiente) {
        _guardarPendiente()
        _enVivo = true
        numerico.abrir(titulo, unidad, valorInicial, minimo, maximo, decimales)
        _inicialNumerico = valorInicial
        _numericoComprometido = false
        _alConfirmar = alConfirmar || null
        _siguiente = siguiente || null
        _tipo = "numerico"
    }
    function cerrar() {
        _tipo = ""
        _alConfirmar = null
        _siguiente = null
    }

    // Al cambiar de campo sin Confirmar, lo escrito se guarda en el anterior
    // (en modo acción se descarta)
    function _guardarPendiente() {
        const alConfirmar = _alConfirmar
        _alConfirmar = null
        if (!alConfirmar || !_enVivo)
            return
        if (_tipo === "alfanumerico")
            alConfirmar(alfanumerico.controlador.texto)
        else if (_tipo === "numerico" && numerico.controlador.valido)
            alConfirmar(numerico.controlador.valor)
    }
    function _entregar(valor) {
        if (!_enVivo) {
            _entregarAccion(valor)
            return
        }
        const alConfirmar = _alConfirmar
        const siguiente = _siguiente
        _alConfirmar = null
        _siguiente = null
        if (alConfirmar)
            alConfirmar(valor)
        confirmado(valor)
        if (siguiente) {
            siguiente()     // abre el campo siguiente sin cerrar el panel
        } else {
            terminado()
            cerrar()
        }
    }
    // Modo acción: se anula el callback y se cierra el panel ANTES de llamarlo;
    // un Confirmar repetido o reentrante encuentra _alConfirmar nulo y no hace
    // nada (TEC-ACC-03).
    function _entregarAccion(valor) {
        const alConfirmar = _alConfirmar
        if (!alConfirmar || _tipo !== "alfanumerico")
            return
        if (valor === undefined || valor === null || String(valor) === "")
            return                      // vacío: sigue abierto (TEC-ACC-02)
        _alConfirmar = null
        _siguiente = null
        confirmado(valor)
        terminado()
        cerrar()
        alConfirmar(valor)
    }
    function _cancelar() {
        const alConfirmar = _enVivo ? _alConfirmar : null
        const tipo = _tipo
        const restaurar = _numericoComprometido
        cerrar()
        if (tipo === "alfanumerico" && alConfirmar)
            alConfirmar("")
        else if (tipo === "numerico" && alConfirmar && restaurar)
            alConfirmar(_inicialNumerico)   // el valor se aplicó al escribir: se devuelve
        cancelado()
    }

    readonly property real _margen: Escala.px(24)
    readonly property Item _activo: _tipo === "numerico" ? numerico : alfanumerico
    readonly property real _altoMaximo: parent ? parent.height * 0.45 : 0   // TEC-D06

    width: parent ? parent.width : 0
    height: Math.min(_activo.implicitHeight + 2 * _margen, _altoMaximo)
    visible: _fraccion > 0
    z: 10

    // Parte del panel a la vista: 0 cerrado, 1 abierto. Solo esto se anima, así
    // un cambio de tamaño de la ventana (o el arranque) no hace deslizar el panel.
    property real _fraccion: abierto ? 1 : 0
    Behavior on _fraccion {
        NumberAnimation {
            duration: 400
            easing.type: Easing.BezierSpline
            easing.bezierCurve: [0.2, 0, 0, 1, 1, 1]
        }
    }
    // entra desde su borde
    y: {
        if (!parent)
            return 0
        if (posicion === "superior")
            return -height * (1 - _fraccion)
        return parent.height - height * _fraccion
    }

    Rectangle {
        anchors.fill: parent
        color: Colores.fondoTarjeta
        // línea divisoria del lado que da a la pantalla
        Rectangle {
            width: parent.width
            height: Escala.px(Teclado.bordeTecla)
            y: raiz.posicion === "superior" ? parent.height - height : 0
            color: Colores.bordeCampo
        }
    }

    // el panel se queda con los toques que caen entre las teclas
    MouseArea { anchors.fill: parent }

    TecladoNumerico {
        id: numerico
        objectName: "tecladoNumerico"
        visible: raiz._tipo === "numerico"
        anchors.horizontalCenter: parent.horizontalCenter
        y: raiz._margen
        width: implicitWidth; height: implicitHeight
        onConfirmado: valor => raiz._entregar(valor)
        onCancelado: raiz._cancelar()
    }
    TecladoAlfanumerico {
        id: alfanumerico
        objectName: "tecladoAlfanumerico"
        visible: raiz._tipo === "alfanumerico"
        anchors.horizontalCenter: parent.horizontalCenter
        y: raiz._margen
        width: implicitWidth; height: implicitHeight
        onConfirmado: texto => raiz._entregar(texto)
        onCancelado: raiz._cancelar()
    }

    // escritura en vivo
    Connections {
        target: alfanumerico.controlador
        function onTextoChanged() { raiz._comprometerAlfanumerico() }
    }
    Connections {
        target: numerico.controlador
        function onValorChanged() { raiz._comprometerNumerico() }
        function onValidoChanged() { raiz._comprometerNumerico() }
    }

    // Ocultar teclado: solo un ícono, esquina superior derecha del recuadro
    Item {
        id: botonOcultar
        objectName: "teclaOcultarTeclado"
        width: Escala.px(64); height: width
        anchors.top: parent.top; anchors.right: parent.right
        anchors.topMargin: Escala.px(8); anchors.rightMargin: Escala.px(12)
        Image {
            anchors.centerIn: parent
            width: Escala.px(48); height: width
            source: "../../assets/iconos/color/ocultar_teclado.svg"
            sourceSize.width: width
            sourceSize.height: height
            opacity: zonaOcultar.pressed ? 0.5 : 1
        }
        MouseArea {
            id: zonaOcultar
            anchors.fill: parent
            anchors.margins: -Escala.px(8)
            onClicked: raiz.ocultar()
        }
    }
}

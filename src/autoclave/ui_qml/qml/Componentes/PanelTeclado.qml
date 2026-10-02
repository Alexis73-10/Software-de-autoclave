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
Item {
    id: raiz

    property var textosJson: ({})
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

    property string _tipo: ""       // "", "numerico" o "alfanumerico"
    property var _alConfirmar: null
    property var _siguiente: null

    function abrirAlfanumerico(titulo, valorInicial, longitudMaxima, ocultar, alConfirmar, siguiente) {
        _guardarPendiente()
        alfanumerico.ocultarTexto = ocultar === true
        alfanumerico.abrir(titulo, valorInicial || "", longitudMaxima || 0)
        _alConfirmar = alConfirmar || null
        _siguiente = siguiente || null
        _tipo = "alfanumerico"
    }
    function abrirNumerico(titulo, unidad, valorInicial, minimo, maximo, decimales, alConfirmar, siguiente) {
        _guardarPendiente()
        numerico.abrir(titulo, unidad, valorInicial, minimo, maximo, decimales)
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
    function _guardarPendiente() {
        const alConfirmar = _alConfirmar
        _alConfirmar = null
        if (!alConfirmar)
            return
        if (_tipo === "alfanumerico")
            alConfirmar(alfanumerico.controlador.texto)
        else if (_tipo === "numerico" && numerico.controlador.valido)
            alConfirmar(numerico.controlador.valor)
    }
    function _entregar(valor) {
        const alConfirmar = _alConfirmar
        const siguiente = _siguiente
        _alConfirmar = null
        _siguiente = null
        if (alConfirmar)
            alConfirmar(valor)
        confirmado(valor)
        if (siguiente)
            siguiente()     // abre el campo siguiente sin cerrar el panel
        else
            cerrar()
    }
    function _cancelar() {
        const alConfirmar = _alConfirmar
        const tipo = _tipo
        cerrar()
        if (tipo === "alfanumerico" && alConfirmar)
            alConfirmar("")
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
        textosJson: raiz.textosJson
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
        textosJson: raiz.textosJson
        onConfirmado: texto => raiz._entregar(texto)
        onCancelado: raiz._cancelar()
    }
}

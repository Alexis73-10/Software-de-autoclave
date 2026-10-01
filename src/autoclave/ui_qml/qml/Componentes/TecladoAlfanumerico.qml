pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers

// Teclado alfanumérico en pantalla (Paso 4 de planeacion_teclados_qml.md v2.1).
// Solo presenta y transmite toques: las reglas (Aa de un solo uso, longitud
// máxima, juego de caracteres) viven en domain/teclado_alfanumerico.py vía
// TecladoAlfanumericoController (TEC-D15).
//
// Distribución del diseñador (pág. 25), separación de 14 px (TEC-D11):
//   Q W E R T Y U I O P
//    A S D F G H J K L Ñ          (desplazada 22 px)
//   Aa Z X C V B N M BORRAR
//   ?123 CANCELAR espacio CONFIRMAR   (CANCELAR según PROV-03)
// Dos capas, una sola retícula: letras y ?123 (dígitos y símbolos juntos,
// como el teclado de Google para Android; decisión de Cristian que une las
// capas 123 y @._). Al cambiar de capa solo cambia el contenido de las
// teclas; las posiciones sin carácter en la capa activa se ocultan. ?123 pasa
// a ABC para volver a letras. Medidas provisionales en TecladoProvisional.
//
// Uso: abrir(titulo, valorInicial, longitudMaxima); salidas confirmado(texto)
// y cancelado().
Item {
    id: raiz

    property var textosJson: ({})
    readonly property alias controlador: ctrl

    signal confirmado(string texto)
    signal cancelado()

    function abrir(titulo, valorInicial, longitudMaxima) {
        ctrl.abrir(titulo, valorInicial, longitudMaxima)
    }

    function _tx(seccion, clave) {
        const s = textosJson ? textosJson[seccion] : undefined
        return (s && s[clave] !== undefined) ? s[clave] : ""
    }
    function _estilo(nombre) { return Tipografia.estilo(nombre) }

    readonly property real _sep: Escala.px(Teclado.separacion)
    readonly property real _anchoTecla: Escala.px(Teclado.anchoTecla)
    readonly property real _altoTecla: Escala.px(TecladoProvisional.altoTeclaAlfanumerico)
    readonly property real _paso: _anchoTecla + _sep
    // x inicial de las letras de cada fila: fila 2 desplazada; fila 3 tras Aa
    readonly property var _inicioFila: [0, Escala.px(TecladoProvisional.desplazamientoFila2), _paso]
    readonly property bool _capaLetras: ctrl.capa === "letras"

    implicitWidth: rejilla.width
    implicitHeight: encabezado.height + _sep + rejilla.height

    TecladoAlfanumericoController {
        id: ctrl
        onConfirmado: texto => raiz.confirmado(texto)
        onCancelado: raiz.cancelado()
    }

    // ---- encabezado (TEC-D13): nombre del campo y valor ----
    Column {
        id: encabezado
        width: rejilla.width
        spacing: Escala.px(4)

        Text {
            width: parent.width
            text: ctrl.titulo
            elide: Text.ElideRight
            color: Colores.textoSecundario
            font.family: raiz._estilo(TecladoProvisional.encabezadoTituloEstilo).familia
            font.weight: raiz._estilo(TecladoProvisional.encabezadoTituloEstilo).peso
            font.pixelSize: raiz._estilo(TecladoProvisional.encabezadoTituloEstilo).tamano
        }
        Text {
            objectName: "valorAlfanumerico"
            width: parent.width
            // alto fijo de una línea aunque el texto esté vacío
            height: raiz._estilo(TecladoProvisional.encabezadoValorEstilo).interlineado
            text: ctrl.texto
            elide: Text.ElideLeft   // con texto largo se ve lo último que se escribió
            color: Colores.textoPrimario
            font.family: raiz._estilo(TecladoProvisional.encabezadoValorEstilo).familia
            font.weight: raiz._estilo(TecladoProvisional.encabezadoValorEstilo).peso
            font.pixelSize: raiz._estilo(TecladoProvisional.encabezadoValorEstilo).tamano
        }
    }

    // ---- rejilla ----
    Item {
        id: rejilla
        y: encabezado.height + raiz._sep
        width: raiz._inicioFila[1] + 10 * raiz._paso - raiz._sep   // fila 2, la más ancha
        height: 4 * raiz._altoTecla + 3 * raiz._sep

        // ancho de la fila 1: borde derecho de las filas 3 y 4
        readonly property real anchoFila1: 10 * raiz._paso - raiz._sep

        // filas 1-3: posiciones de filasLetras, contenido de la capa activa (filasCapa)
        Repeater {
            model: ctrl.filasLetras
            delegate: Repeater {
                id: fila
                required property string modelData
                required property int index
                model: fila.modelData.length
                delegate: Tecla {
                    required property int index
                    readonly property string caracter: (ctrl.filasCapa[fila.index] || "").charAt(index)
                    x: raiz._inicioFila[fila.index] + index * raiz._paso
                    y: fila.index * (raiz._altoTecla + raiz._sep)
                    width: raiz._anchoTecla
                    height: raiz._altoTecla
                    visible: caracter !== ""
                    tamTexto: TecladoProvisional.tamTextoLetraAlfanumerico
                    // la etiqueta de las letras sigue el estado de Aa (Ñ/ñ incluida)
                    texto: raiz._capaLetras && ctrl.mayusculas ? caracter.toUpperCase() : caracter
                    onPulsada: ctrl.presionarCaracter(caracter)
                }
            }
        }

        // fila 3: Aa al inicio, BORRAR tras la M
        Tecla {
            objectName: "teclaAa"
            x: 0
            y: 2 * (raiz._altoTecla + raiz._sep)
            width: raiz._anchoTecla
            height: raiz._altoTecla
            texto: raiz._tx("teclado", "aa")
            marcada: ctrl.mayusculas          // PROV-02
            onPulsada: ctrl.alternarMayusculas()
        }
        Tecla {
            objectName: "teclaBorrar"
            x: rejilla.anchoFila1 - width
            y: 2 * (raiz._altoTecla + raiz._sep)
            width: Escala.px(TecladoProvisional.anchoBorrarAlfanumerico)
            height: raiz._altoTecla
            variante: "borrar"
            texto: raiz._tx("acciones", "borrar")
            // un toque borra un carácter; mantenida 600 ms, todo (TEC-D12, controlador)
            onPresionada: ctrl.presionarBorrar()
            onSoltada: ctrl.soltarBorrar()
            onCancelada: ctrl.cancelarPulsacionBorrar()
        }

        // fila 4 (PROV-03): ?123 | CANCELAR | espacio | CONFIRMAR
        Tecla {
            id: teclaCapa
            objectName: "teclaCapa"
            x: 0
            y: 3 * (raiz._altoTecla + raiz._sep)
            width: Escala.px(TecladoProvisional.anchoCapaAlfanumerico)
            height: raiz._altoTecla
            // ?123 en letras, ABC en la capa de dígitos y símbolos
            texto: raiz._capaLetras ? raiz._tx("teclado", "capa_numeros")
                                    : raiz._tx("teclado", "capa_letras")
            onPulsada: ctrl.cambiarCapa(raiz._capaLetras ? "numeros" : "letras")
        }
        Tecla {
            id: teclaCancelar
            objectName: "teclaCancelar"
            x: teclaCapa.x + teclaCapa.width + raiz._sep
            y: teclaCapa.y
            width: Escala.px(TecladoProvisional.anchoCancelarAlfanumerico)
            height: raiz._altoTecla
            variante: "cancelar"
            texto: raiz._tx("acciones", "cancelar")
            onPulsada: ctrl.cancelar()
        }
        Tecla {
            objectName: "teclaEspacio"
            x: teclaCancelar.x + teclaCancelar.width + raiz._sep
            y: teclaCapa.y
            width: teclaConfirmar.x - raiz._sep - x
            height: raiz._altoTecla
            texto: raiz._tx("teclado", "espacio")
            onPulsada: ctrl.presionarCaracter(" ")
        }
        Tecla {
            id: teclaConfirmar
            objectName: "teclaConfirmar"
            x: rejilla.anchoFila1 - width
            y: teclaCapa.y
            width: Escala.px(TecladoProvisional.anchoConfirmarAlfanumerico)
            height: raiz._altoTecla
            variante: "confirmar"
            texto: raiz._tx("acciones", "confirmar")
            onPulsada: ctrl.confirmar()
        }
    }
}

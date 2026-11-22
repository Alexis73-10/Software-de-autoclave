pragma ComponentBehavior: Bound
import QtQuick
import Tema
import Autoclave.Controllers
import Autoclave.I18n

// Teclado numérico en pantalla (Paso 3 de planeacion_teclados_qml.md v2.1).
// Solo presenta y transmite toques: las reglas (signo, punto, decimales,
// rango, borrado largo) viven en domain/teclado_numerico.py vía
// TecladoNumericoController (TEC-D15).
//
// Distribución del diseñador (pág. 24), con separación de 14 px (TEC-D11):
//   7 8 9 | CANCELAR
//   4 5 6 | BORRAR
//   1 2 3 | CONFIRMAR  (dos filas)
//   - 0 . |
// Medidas de tecla y de la columna de acciones: TecladoProvisional (*Numerico).
// Encabezado (TEC-D13): parámetro, valor que se escribe, unidad y rango; el
// rango se resalta cuando Confirmar rechaza el valor (TEC-D08, PROV-04).
//
// Uso: abrir(titulo, unidad, valorInicial, minimo, maximo, decimales);
// salidas confirmado(valor) y cancelado().
Item {
    id: raiz

    readonly property alias controlador: ctrl

    signal confirmado(real valor)
    signal cancelado()

    function abrir(titulo, unidad, valorInicial, minimo, maximo, decimales) {
        ctrl.abrir(titulo, unidad, valorInicial, minimo, maximo, decimales)
    }

    function _estilo(nombre) { return Tipografia.estilo(nombre) }

    readonly property real _sep: Escala.px(Teclado.separacion)
    readonly property real _anchoTecla: Escala.px(TecladoProvisional.anchoTeclaNumerico)
    readonly property real _altoTecla: Escala.px(TecladoProvisional.altoTeclaNumerico)
    readonly property real _anchoAcciones: Escala.px(TecladoProvisional.anchoColumnaAccionesNumerico)
    readonly property string textoRango: I18n.t("teclado." + TecladoProvisional.claveMensajeRango, I18n.lang)
        .replace("{minimo}", ctrl.minimoTexto)
        .replace("{maximo}", ctrl.maximoTexto)
        .replace("{unidad}", ctrl.unidad)
        .trim()

    // Tanda horizontal (9-nov): con el lienzo horizontal (1200 de alto) el
    // panel no puede pasar del 45 % del alto (TEC-D06, 540 px de diseño): el
    // encabezado va a la izquierda de la rejilla en vez de encima. Mismas
    // teclas y mismos tamaños. Lo fija PanelTeclado; en false (vertical, y
    // fuera del panel) todo queda como siempre.
    property bool encabezadoLateral: false
    property real anchoEncabezado: 0
    readonly property real separacionLateral: Escala.px(24)
    readonly property real anchoRejilla: rejilla.width
    // x de la rejilla dentro del teclado (0 con el encabezado encima)
    readonly property real desplazamientoRejilla: encabezadoLateral ? anchoEncabezado + separacionLateral : 0

    implicitWidth: encabezadoLateral ? desplazamientoRejilla + rejilla.width : rejilla.width
    implicitHeight: encabezadoLateral ? Math.max(encabezado.height, rejilla.height)
                                      : encabezado.height + _sep + rejilla.height

    TecladoNumericoController {
        id: ctrl
        onConfirmado: valor => raiz.confirmado(valor)
        onCancelado: raiz.cancelado()
    }

    // ---- encabezado (TEC-D13) ----
    Column {
        id: encabezado
        width: raiz.encabezadoLateral ? raiz.anchoEncabezado : rejilla.width
        spacing: Escala.px(4)

        Text {
            width: parent.width
            text: ctrl.titulo
            wrapMode: Text.Wrap
            color: Colores.textoSecundario
            font.family: raiz._estilo(TecladoProvisional.encabezadoTituloEstilo).familia
            font.weight: raiz._estilo(TecladoProvisional.encabezadoTituloEstilo).peso
            font.pixelSize: raiz._estilo(TecladoProvisional.encabezadoTituloEstilo).tamano
        }
        Row {
            spacing: Escala.px(12)
            Text {
                id: valorTexto
                // Tanda horizontal (ronda 2): con el valor vacío el texto no tiene
                // línea base y la unidad (alineada a ella) se montaba sobre el
                // rango; un espacio conserva la línea (RV-04, revisión visual
                // 19-nov: también en vertical, donde seguía montándose)
                text: ctrl.texto === "" ? " " : ctrl.texto
                color: Colores.textoPrimario
                font.family: raiz._estilo(TecladoProvisional.encabezadoValorEstilo).familia
                font.weight: raiz._estilo(TecladoProvisional.encabezadoValorEstilo).peso
                font.pixelSize: raiz._estilo(TecladoProvisional.encabezadoValorEstilo).tamano
                font.features: raiz._estilo(TecladoProvisional.encabezadoValorEstilo).features
            }
            Text {
                anchors.baseline: valorTexto.baseline
                text: ctrl.unidad
                color: Colores.textoSecundario
                font.family: raiz._estilo(TecladoProvisional.encabezadoUnidadEstilo).familia
                font.weight: raiz._estilo(TecladoProvisional.encabezadoUnidadEstilo).peso
                font.pixelSize: raiz._estilo(TecladoProvisional.encabezadoUnidadEstilo).tamano
            }
        }
        Text {
            width: parent.width
            text: raiz.textoRango
            wrapMode: Text.WordWrap
            // fuera de rango: el rango se resalta (no se usa color de alarma)
            color: ctrl.fueraDeRango ? Colores.peligroTexto : Colores.textoSecundario
            font.family: raiz._estilo(TecladoProvisional.encabezadoRangoEstilo).familia
            font.weight: ctrl.fueraDeRango ? Tipografia.pesoBold
                                           : raiz._estilo(TecladoProvisional.encabezadoRangoEstilo).peso
            font.pixelSize: raiz._estilo(TecladoProvisional.encabezadoRangoEstilo).tamano
        }
    }

    // ---- rejilla ----
    Item {
        id: rejilla
        x: raiz.desplazamientoRejilla
        y: raiz.encabezadoLateral ? 0 : encabezado.height + raiz._sep
        width: 3 * raiz._anchoTecla + 3 * raiz._sep + raiz._anchoAcciones
        height: 4 * raiz._altoTecla + 3 * raiz._sep

        // 3 columnas de caracteres x 4 filas (filasTeclas del dominio)
        Repeater {
            model: ctrl.filasTeclas
            delegate: Repeater {
                id: fila
                required property string modelData
                required property int index
                model: fila.modelData.split("")
                delegate: Tecla {
                    required property string modelData
                    required property int index
                    x: index * (raiz._anchoTecla + raiz._sep)
                    y: fila.index * (raiz._altoTecla + raiz._sep)
                    width: raiz._anchoTecla
                    height: raiz._altoTecla
                    texto: modelData
                    tamTexto: TecladoProvisional.tamTextoDigitoNumerico
                    onPulsada: ctrl.presionarTecla(modelData)
                }
            }
        }

        // columna de acciones
        Tecla {
            objectName: "teclaCancelar"
            x: 3 * (raiz._anchoTecla + raiz._sep)
            y: 0
            width: raiz._anchoAcciones
            height: raiz._altoTecla
            tamTexto: TecladoProvisional.tamTextoAccionNumerico
            variante: "cancelar"
            texto: I18n.t("acciones.cancelar", I18n.lang)
            onPulsada: ctrl.cancelar()
        }
        Tecla {
            objectName: "teclaBorrar"
            x: 3 * (raiz._anchoTecla + raiz._sep)
            y: raiz._altoTecla + raiz._sep
            width: raiz._anchoAcciones
            height: raiz._altoTecla
            tamTexto: TecladoProvisional.tamTextoAccionNumerico
            variante: "borrar"
            // ícono universal de borrar (borrar.svg del diseñador), pedido por Cristian
            icono: "../../assets/iconos/color/borrar.svg"
            // un toque borra un carácter; mantenida 600 ms, todo (TEC-D12, controlador)
            onPresionada: ctrl.presionarBorrar()
            onSoltada: ctrl.soltarBorrar()
            onCancelada: ctrl.cancelarPulsacionBorrar()
        }
        Tecla {
            objectName: "teclaConfirmar"
            x: 3 * (raiz._anchoTecla + raiz._sep)
            y: 2 * (raiz._altoTecla + raiz._sep)
            width: raiz._anchoAcciones
            height: 2 * raiz._altoTecla + raiz._sep
            tamTexto: TecladoProvisional.tamTextoAccionNumerico
            variante: "confirmar"
            texto: I18n.t("acciones.confirmar", I18n.lang)
            onPulsada: ctrl.confirmar()
        }
    }
}

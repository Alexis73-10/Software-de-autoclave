pragma Singleton
import QtQuick

// PROVISIONAL — único lugar de los valores de los teclados aprobados por
// Cristian mientras el diseñador no responde (§5 de
// docs/mis_plans/planeacion_teclados_qml.md v2.1). Al recibir la respuesta,
// se cambian aquí (y la cadena de PROV-04 en es.json) sin tocar componentes.
QtObject {
    // PROV-01: tipografía de las teclas = estilo de botón existente en
    // Tipografia ("boton_etiqueta": Montserrat SemiBold 600) con el tamaño
    // subido a 28 px (el estilo trae 26; el plan exige 28 como mínimo).
    readonly property string estiloTexto: "boton_etiqueta"
    readonly property int tamTexto: 28

    // PROV-02: Aa armada se ve como la tecla presionada (TEC-D04) mientras dure.
    readonly property bool aaArmadaComoPresionada: true

    // Colores de CANCELAR y BORRAR: decisión de Cristian (2026-10-01), CANCELAR en
    // rojo y BORRAR en amarillo. Contradice TEC-D07 (CANCELAR gris neutro) y el
    // diseño (BORRAR en rojo): avisar al diseñador. El "amarillo" usa los tokens
    // color-warning del diseñador, no el amarillo de alarma IEC 60601-1-8.
    // Claves de Colores.
    readonly property string cancelarFondo: "peligroFondo"
    readonly property string cancelarBorde: "peligroTexto"
    readonly property string cancelarTexto: "peligroTexto"
    readonly property string borrarFondo: "advertenciaFondo"
    readonly property string borrarBorde: "advertencia"
    readonly property string borrarTexto: "advertenciaTexto"

    // PROV-03 (alfanumérico, Paso 4): anchos de la fila 4 — pendiente.

    // Tamaño del numérico: decisión de Cristian (2026-10-01), el de TEC-D11
    // (96 x 88, ~44 % del ancho del lienzo) se ve pequeño en la pantalla. Ocupa
    // casi todo el ancho de 1200 (4 columnas de 262 + 3 separaciones de 14 = 1090)
    // y, con encabezado, queda bajo el 45 % de alto de TEC-D06. Las 4 columnas
    // miden igual, también la de acciones (antes 200 px, decisión del 2026-09-30).
    // Se conservan distribución, separación y radio del diseñador. Avisar al
    // diseñador. El alfanumérico sigue con Teclado.anchoTecla (su fila 2 no cabe
    // con teclas más anchas).
    readonly property real anchoTeclaNumerico: 262
    readonly property real altoTeclaNumerico: 140
    readonly property real anchoColumnaAccionesNumerico: 262
    readonly property int tamTextoDigitoNumerico: 48
    readonly property int tamTextoAccionNumerico: 34   // CONFIRMAR ~222 px, cabe en 262

    // Encabezado del numérico (TEC-D13): el diseñador fija el contenido (parámetro,
    // valor, unidad, rango) pero no su estilo; se reutilizan estilos de Tipografia.
    readonly property string encabezadoTituloEstilo: "tarjeta_titulo"   // 26 px
    readonly property string encabezadoValorEstilo: "sensor_valor"      // 54 px, cifras tabulares
    readonly property string encabezadoUnidadEstilo: "campo_valor"      // 26 px
    readonly property string encabezadoRangoEstilo: "campo_etiqueta"    // 22 px

    // PROV-04: mensaje de fuera de rango = clave "teclado.rango" de es.json
    // ("Rango: {minimo} a {maximo} {unidad}"), pendiente del texto del diseñador.
    readonly property string claveMensajeRango: "rango"
}

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

    // ---- Alfanumérico (Paso 4) ----
    // Tecla de 96 de ancho (TEC-D11): la fila 2 (10 teclas + desplazamiento de 22)
    // ya ocupa 1108 de los 1200 del lienzo, no puede ensancharse. Lo que sí
    // crece, como pidió Cristian para el numérico (2026-10-01), es el alto.
    readonly property real altoTeclaAlfanumerico: 120
    readonly property real desplazamientoFila2: 22      // "filas desplazadas 22 px" (pág. 25)
    readonly property int tamTextoLetraAlfanumerico: 34
    // Fila 3: Aa queda al inicio con ancho de tecla normal (el diseñador la dibujó
    // más angosta, ~60 px, bajo el mínimo táctil de 68). BORRAR queda tras la M
    // y se extiende hasta el borde derecho de la fila 1 ("BORRAR" a 28 px no cabe en 96).
    readonly property real anchoBorrarAlfanumerico: 206
    // PROV-03, fila 4: ?123 | CANCELAR | espacio | CONFIRMAR, alineada con los
    // bordes de la fila 1 (1086 px). 123 y @._ se unieron en una sola tecla
    // ?123 (decisión de Cristian, 2026-10-01), así el espacio mide 524 px,
    // casi las 5 teclas (536) que pide el diseñador.
    readonly property real anchoCapaAlfanumerico: 110        // ?123 / ABC
    readonly property real anchoCancelarAlfanumerico: 190
    readonly property real anchoConfirmarAlfanumerico: 220

    // Tamaño del numérico: decisiones de Cristian (2026-10-01). El de TEC-D11
    // (96 x 88) se veía pequeño; 262 x 140 quedó desproporcionado frente al
    // alfanumérico. Para que se vean del mismo equipo: mismo alto de tecla y
    // mismo tamaño de texto que el alfanumérico, y teclas del ancho de su
    // BORRAR (206). Las 4 columnas miden igual, también la de acciones (antes
    // 200 px, decisión del 2026-09-30). Se conservan distribución, separación y
    // radio del diseñador. Avisar al diseñador.
    readonly property real anchoTeclaNumerico: 206
    readonly property real altoTeclaNumerico: altoTeclaAlfanumerico
    readonly property real anchoColumnaAccionesNumerico: 206
    readonly property int tamTextoDigitoNumerico: tamTextoLetraAlfanumerico
    readonly property int tamTextoAccionNumerico: tamTexto   // CONFIRMAR ~183 px, cabe en 206

    // Encabezado de ambos teclados (TEC-D13): el diseñador fija el contenido
    // (numérico: parámetro, valor, unidad, rango; alfanumérico: campo y valor)
    // pero no su estilo; se reutilizan estilos de Tipografia, iguales en los dos.
    readonly property string encabezadoTituloEstilo: "tarjeta_titulo"   // 26 px
    readonly property string encabezadoValorEstilo: "kpi_valor"         // 46 px, cifras tabulares
    readonly property string encabezadoUnidadEstilo: "campo_valor"      // 26 px
    readonly property string encabezadoRangoEstilo: "campo_etiqueta"    // 22 px

    // PROV-04: mensaje de fuera de rango = clave "teclado.rango" de es.json
    // ("Rango: {minimo} a {maximo} {unidad}"), pendiente del texto del diseñador.
    readonly property string claveMensajeRango: "rango"
}

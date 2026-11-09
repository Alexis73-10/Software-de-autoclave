pragma Singleton
import QtQuick

// Fuente única de color: 02_COLOR/tokens.css y paleta.csv del diseñador.
// Ninguna pantalla debe escribir un hex a mano — todo pasa por aquí.
//
// Modo oscuro: cada propiedad es `oscuro ? "<oscuro>" : "<claro>"`. El valor
// claro es el de siempre (tema claro idéntico); el oscuro sale de
// docs/diseno/mockups/modo_oscuro/paleta_modo_oscuro.md (los que no están allí
// se registran como hallazgo OSC-NN en docs/informes/modo_oscuro/plan.md).
// `oscuro` lo enlaza cada raíz de ventana con Apariencia.oscuro; ninguna
// pantalla ni lógica lo lee (solo leen Colores.*). Sin enlace queda en claro.
// Un valor único (alarmas, velos, sombras, botones fijos) es igual en los dos
// temas. tests/test_tema_oscuro.py vigila este formato.
QtObject {
    property bool oscuro: false

    // Fondos oscuros (arranque / chrome)
    readonly property color fondoMarinoOscuro:  oscuro ? "#090E14" : "#1B222A"  // fondo_marino_950
    readonly property color fondoBarraSuperior: oscuro ? "#1A3150" : "#2C4B70"  // fondo_marino_700
    readonly property color fondoAzulMedio:     oscuro ? "#0F1B2A" : "#2E597C"  // fondo_azul_700
    readonly property color fondoCieloNucleo:   oscuro ? "#1B3352" : "#5C97DB"  // fondo_cielo_300 — halo del arranque
    readonly property color fondoCieloClaro:    oscuro ? "#8FB2E0" : "#99C5E2"  // fondo_cielo_200
    readonly property color textoFechaReposo:   oscuro ? "#8FB2E0" : "#C7DCFD"  // fecha de la pantalla de reposo y pie de la intro
    // Fondo de la aplicación: en claro la imagen fondo-arranque.png; en oscuro
    // el gradiente radial de la paleta §1 (FondoApp, FondoGradiente). Paradas de
    // FondoApp: fondoBarraSuperior → fondoAzulMedio → fondoMarinoOscuro; de
    // Reposo: fondoCieloNucleo → fondoAzulMedio → fondoReposoBorde.
    readonly property bool fondoGradiente: oscuro
    readonly property color fondoReposoBorde:   "#070B10"  // solo se dibuja en oscuro (§1)

    // Acción
    readonly property color accionPrimario:      oscuro ? "#4A8CFF" : "#1168F6" // botón primario
    readonly property color accionPrimarioTexto: oscuro ? "#6EA4FF" : "#0D53C4" // obligatorio para texto (contraste)
    readonly property color accionFondoTenue:    oscuro ? "#16305E" : "#E2ECFD" // color-primary-050: relleno de tecla presionada / seleccionado

    // Peligro (acciones destructivas, p. ej. BORRAR del teclado) — NO es color de alarma
    readonly property color peligroFondo: oscuro ? "#3A1416" : "#FFECEC" // color-danger-050
    readonly property color peligroTexto: oscuro ? "#FF6B6B" : "#D00000" // color-danger-strong

    // Advertencia (BORRAR del teclado) — tokens color-warning* del diseñador. NO es el
    // amarillo de alarma (alarmaMedia), que está reservado por IEC 60601-1-8.
    readonly property color advertenciaFondo: oscuro ? "#3A2610" : "#FFF4E6" // color-warning-050
    readonly property color advertencia:      oscuro ? "#FF9F3A" : "#FF9933" // color-warning
    readonly property color advertenciaTexto: oscuro ? "#FFAE5C" : "#B35A00" // color-warning-strong (texto)

    // Alarmas IEC 60601-1-8 — reservado, no usar para nada que no sea alarma.
    // Iguales en los dos temas (decisión 2 del modo oscuro).
    readonly property color alarmaAlta:  "#EE0000"
    readonly property color alarmaMedia: "#FFCC00"
    readonly property color alarmaBaja:  "#00CCFF"

    // Acentos del Menú Principal: medidos sobre el mockup v3 (planeacion_menu_principal_ui_qml.md §5).
    // No coinciden con ningún token del paquete del diseñador (accionPrimario #1168F6 y
    // advertencia #FF9933 son tonos distintos): confirmar con él si unifica. El verde NO es
    // estado de alarma; ninguno de estos sustituye a los colores alarma*.
    readonly property color menuVerde:        oscuro ? "#34C46A" : "#009535" // borde e icono (Iniciar sesión)
    readonly property color menuVerdeTexto:   oscuro ? "#4FD27F" : "#0D8C2C" // texto verde (p. ej. resultado exitoso)
    readonly property color menuAzul:         oscuro ? "#4A8CFF" : "#0361EC"
    readonly property color menuNaranja:      oscuro ? "#FF9F3A" : "#FF9720"
    readonly property color menuNaranjaTexto: oscuro ? "#FFAE5C" : "#F26500" // texto naranja (p. ej. programa)
    readonly property color menuMorado:       oscuro ? "#B46CF2" : "#9827D1"

    // Neutros / texto
    readonly property color bordeDivisor:       oscuro ? "#2A3746" : "#E6E6E6" // borde_divisor de tokens.css (aro neutro de tarjeta)
    readonly property color textoPrimario:      oscuro ? "#E9EEF4" : "#031225" // neutro_900
    readonly property color textoSecundario:    oscuro ? "#A7B3C1" : "#4D4D4D" // neutro_700
    readonly property color textoGuia:          oscuro ? "#8C98A7" : "#808080" // neutro_500 — placeholder, ≥19px
    readonly property color bordeCampo:         oscuro ? "#33445A" : "#CCCCCC" // neutro_300
    readonly property color fondoSutil:         oscuro ? "#18222F" : "#F6F6F6" // bg-subtle
    readonly property color fondoTarjeta:       oscuro ? "#152130" : "#FFFFFF"
    // Campos de formulario (Login, CampoFormulario, casilla «Recordar usuario»; OSC-21):
    // claro = el blanco que daba el Rectangle sin color; oscuro = superficie elevada (paleta §6)
    readonly property color fondoCampo:         oscuro ? "#1E2A38" : "#FFFFFF"
    readonly property color iconoCampo:         oscuro ? "#8C98A7" : "#CCCCCC" // candado del Login (OSC-18); claro = bordeCampo de hoy
    readonly property color iconoBarraInferior: oscuro ? "#E9EEF4" : "#333333" // neutro_800

    // ───────────── Propiedades nuevas del modo oscuro (plan.md §3) ─────────────
    // Claro = literal de hoy en el archivo indicado (rama dev, c43b9d0b).

    // Superficies (paleta §6)
    readonly property color fondoPanel:    oscuro ? "#131C27" : "#FFFFFF" // panel grande de Preciclo / Ciclo (hoy fondoTarjeta)
    readonly property color fondoElevado:  oscuro ? "#1E2A38" : "#FFFFFF" // filas, botones secundarios, desplegables (hoy blanco)
    readonly property color fondoPista:    oscuro ? "#243242" : "#DEE4EC" // pista de la barra de avance (Ciclo paleta.pistaProgreso)
    readonly property color bordeTarjeta:  oscuro ? "#263445" : "#E5E5E5" // Preciclo/Ciclo paleta.bordeTarjeta
    readonly property color avatarFondo:   oscuro ? "#1E2A38" : "#E6E6E6" // Preciclo/Ciclo paleta.avatarFondo (OSC-16)

    // Estado «En ejecución» (paleta §6)
    readonly property color estadoEjecucion:        oscuro ? "#2BD3A8" : "#25BA9E" // paleta.verdeEjecutando
    readonly property color estadoEjecucionCirculo: oscuro ? "#1B9C7E" : "#25BA9E"

    // Fases: BarraFases / CirculoFaseLiquido / ConectorFase (paleta §6)
    readonly property color faseCompletadaInicio: oscuro ? "#1E5FD9" : "#0B7A80" // CirculoFaseLiquido._liquidoInicio
    readonly property color faseCompletadaFin:    oscuro ? "#0E7A9A" : "#003A9C" // CirculoFaseLiquido._liquidoFin
    readonly property color faseActiva:           oscuro ? "#1E5FD9" : "#0B7A80" // llenado de la activa (inicio del degradado)
    readonly property color faseActivaFin:        oscuro ? "#1E5FD9" : "#003A9C" // fin del degradado (en oscuro, sólido; OSC-16)
    readonly property color faseActivaAro:        oscuro ? "#5933B4F5" : "#00000000" // aro #33B4F5 al 35 %; hoy sin aro (OSC-12)
    readonly property color fasePendienteFondo:   oscuro ? "#222E3C" : "#CCCCCC" // CirculoFaseLiquido
    readonly property color fasePendienteBorde:   oscuro ? "#33445A" : "#00000000" // hoy sin borde
    readonly property color fasePendienteIcono:   oscuro ? "#6B7889" : "#FFFFFF" // íconos fase_*.svg (blancos)
    readonly property color fasePendienteEtiqueta: oscuro ? "#7F8B99" : "#3C3C3C" // BarraFases paleta.etiqueta
    readonly property color faseEtiqueta:         oscuro ? "#C9D2DC" : "#3C3C3C" // oscuro del mockup 03 (OSC-16)
    readonly property color faseEtiquetaActiva:   oscuro ? "#6EC8FF" : "#3C3C3C" // OSC-12
    // Tanda 34 (VAP-01/VAP-04): vapor y burbuja de CirculoFaseLiquido; reemplazan a faseChorro. DECISIÓN SIN CONFIRMAR.
    readonly property color faseVapor:            oscuro ? "#42DCF0FF" : "#42FFFFFF" // vapor sobre el llenado
    readonly property color faseVaporFondo:       oscuro ? "#42DCF0FF" : "#8CF6FBFF" // vapor sobre el fondo de la fase
    readonly property color faseBurbujaBorde:     oscuro ? "#8CDCF0FF" : "#8CFFFFFF"
    readonly property color faseBurbujaRelleno:   oscuro ? "#24DCF0FF" : "#24FFFFFF"
    readonly property color conectorInicio:       oscuro ? "#1E5FD9" : "#003B9B" // ConectorFase
    readonly property color conectorFin:          oscuro ? "#33B4F5" : "#07BDFF"
    readonly property color conectorPendiente:    oscuro ? "#2A3746" : "#CCCCCC"

    // Barra de avance del ciclo (paleta §6)
    readonly property color progresoInicio: oscuro ? "#1E5FD9" : "#04439B" // Ciclo paleta.progresoInicio
    readonly property color progresoFin:    oscuro ? "#33B4F5" : "#0BB8FA"

    // Gráfica (paleta §6; claro = GraficaCiclo.paleta y series por omisión)
    readonly property color serieGrafica1:      oscuro ? "#5B9BFF" : "#6599FC" // temperatura de cámara
    readonly property color serieGrafica2:      oscuro ? "#B06BF0" : "#9732DA" // referencia
    readonly property color serieGrafica3:      oscuro ? "#22D3B0" : "#00CCB0" // presión
    readonly property color graficaCuadricula:  oscuro ? "#2A3746" : "#D4D4D4"
    readonly property color graficaEje:         oscuro ? "#3A4A5E" : "#DADADA"
    readonly property color graficaTextoEje:    oscuro ? "#8C98A7" : "#000000" // paleta.etiquetaEje
    readonly property color graficaCursorFondo: oscuro ? "#0F1721" : "#FFFFFF" // globo del cursor (hoy fondoTarjeta)
    readonly property color graficaCursorBorde: oscuro ? "#33445A" : "#E5E5E5" // globo del cursor (paleta.borde)
    readonly property color graficaCursor:      oscuro ? "#8C98A7" : "#3A3A3A" // línea del cursor (OSC-16)
    readonly property color graficaBorde:       oscuro ? "#263445" : "#E5E5E5" // = bordeTarjeta (OSC-04)
    readonly property color graficaTitulo:      oscuro ? "#E9EEF4" : "#010006" // = textoPrimario (OSC-04)
    readonly property color graficaTexto:       oscuro ? "#E9EEF4" : "#1A1A1A"
    readonly property color graficaSeparador:   oscuro ? "#2A3746" : "#D8D8D8"
    readonly property color graficaDivisorFase: oscuro ? "#3A4A5E" : "#BCBCBC" // líneas de fase
    readonly property color graficaIconoFase:   oscuro ? "#8C98A7" : "#505050" // OSC-16
    readonly property color graficaTituloEje:   oscuro ? "#A7B3C1" : "#333333" // = textoSecundario (OSC-04)
    readonly property color graficaBordeBoton:  oscuro ? "#33445A" : "#C8C8C8" // = bordeCampo
    readonly property color graficaZoomIcono:   oscuro ? "#5B9BFF" : "#3A6FD8" // ZOM-07, tanda 34; DECISIÓN SIN CONFIRMAR

    // Valores de sensores (tira de Preciclo/Ciclo; hoy paleta.negro)
    // valorTempCamara/Referencia/Presion: por posición de Entradas mostradas (igual que la gráfica), no por tipo de sensor.
    readonly property color valorTempCamara:     oscuro ? "#8AB6FF" : "#000000"
    readonly property color valorTempReferencia: oscuro ? "#CFA2F7" : "#000000"
    readonly property color valorPresion:        oscuro ? "#5EE3C2" : "#000000"

    // Deslizador de inicio AJ-01 (verde pastel en claro; paleta §7) y éxito. NO son colores de alarma.
    // Oscuro: lo que el deslizador ya mostraba en el tema oscuro (rama modo-oscuro).
    readonly property color deslizadorPista:          oscuro ? "#12301F" : "#E9F8EE" // pista (mezcla reposo); claro = éxito 050
    readonly property color deslizadorPistaListo:     oscuro ? "#18402A" : "#D3F1DD" // pista (mezcla listo)
    readonly property color deslizadorAcento:         oscuro ? "#2DBE66" : "#2DBE66" // verdeReposo
    readonly property color deslizadorAcentoListo:    oscuro ? "#5ED68C" : "#5ED68C" // verdeListo
    readonly property color deslizadorBrillo:         oscuro ? "#732DBE66" : "#BDEBCB" // brilloReposo; oscuro al 45 %
    readonly property color deslizadorBrilloListo:    oscuro ? "#735ED68C" : "#DDF7E5" // brilloListo; oscuro al 45 %
    readonly property color deslizadorTexto:          oscuro ? "#5ED68C" : "#007A29" // éxito fuerte: texto de la pista (≥ 4,5:1 en claro)
    readonly property color deslizadorSombraInterior: oscuro ? "#1F000000" : "#007A29" // base de la sombra interior; se usa al 12 % (Qt.alpha)
    readonly property color deslizadorNucleo:         oscuro ? "#2DBE66" : "#009933" // éxito: núcleo de la manija (triángulo blanco ≥ 3:1) y velo del fondo
    // Fondo de la manija (mezcla reposo → listo): claro = núcleo de éxito; oscuro = la pista, como ya se veía
    readonly property color deslizadorManija:         oscuro ? "#12301F" : "#009933"
    readonly property color deslizadorManijaListo:    oscuro ? "#18402A" : "#009933"
    // Magnitudes (no colores) del deslizador que cambian con el tema: el oscuro conserva las de siempre
    readonly property real deslizadorBordeAlfa:       oscuro ? 0.3 : 0.45  // alfa del borde de la pista (acento)
    readonly property real deslizadorSombraOpacidad:  oscuro ? 0.4 : 0.2   // opacidad del brillo exterior de la pista
    readonly property real deslizadorTextoAcento:     oscuro ? 0.85 : 0    // >0: el texto es el acento con ese alfa y halo; 0: usa deslizadorTexto
    // Deslizador de CANCELAR (CAN-01, tanda 34): rojo paralelo al verde de arriba; DECISIÓN SIN CONFIRMAR.
    // Comparte las magnitudes deslizador* (BordeAlfa, SombraOpacidad, TextoAcento).
    readonly property color deslizadorCancelarPista:          oscuro ? "#301212" : "#FBEAEA"
    readonly property color deslizadorCancelarPistaListo:     oscuro ? "#401818" : "#F5D0D0"
    readonly property color deslizadorCancelarAcento:         oscuro ? "#E04848" : "#E03A3A"
    readonly property color deslizadorCancelarAcentoListo:    oscuro ? "#FF6B6B" : "#F26060"
    readonly property color deslizadorCancelarBrillo:         oscuro ? "#73E04848" : "#F2BFBF" // oscuro al 45 %
    readonly property color deslizadorCancelarBrilloListo:    oscuro ? "#73FF6B6B" : "#F9DADA" // oscuro al 45 %
    readonly property color deslizadorCancelarTexto:          oscuro ? "#FF8A8A" : "#B00010" // ≥ 4,5:1 sobre la pista en claro
    readonly property color deslizadorCancelarSombraInterior: oscuro ? "#1F000000" : "#B00010" // se usa al 12 % (Qt.alpha)
    readonly property color deslizadorCancelarNucleo:         oscuro ? "#D94040" : "#D10A0A" // triángulo blanco ≥ 3:1
    readonly property color deslizadorCancelarManija:         oscuro ? "#301212" : "#D10A0A"
    readonly property color deslizadorCancelarManijaListo:    oscuro ? "#401818" : "#D10A0A"
    // Reportes (dashboard): relleno verde de éxito; oscuro = misma superficie verde oscura de la pista (paleta §7)
    readonly property color exitoFondo:               oscuro ? "#12301F" : "#E9F8EE"

    // Botones con degradado (OSC-10/11)
    readonly property color abrirPuertaArriba:  oscuro ? "#16305E" : "#2F58FB" // Preciclo Qt.rgba(47, 88, 251)
    readonly property color abrirPuertaAbajo:   oscuro ? "#16305E" : "#000049" // Preciclo Qt.rgba(0, 0, 73)
    readonly property color abrirPuertaBorde:   oscuro ? "#3B6FD8" : "#00000000" // hoy sin borde
    readonly property color abrirPuertaTexto:   oscuro ? "#E9EEF4" : "#FFFFFF"
    readonly property color cancelarArriba:     oscuro ? "#D71A1A" : "#F40000" // Ciclo paleta.cancelarArriba
    readonly property color cancelarAbajo:      oscuro ? "#A30F0F" : "#870004"
    readonly property color cancelarBorde:      oscuro ? "#FF5A5A" : "#00000000" // hoy sin borde
    readonly property color confirmarArriba:    "#08AA41" // Ciclo paleta.confirmarArriba (OSC-10: igual en los dos)
    readonly property color confirmarAbajo:     "#01501E"
    readonly property color botonNaranjaArriba: "#E67814" // Preciclo Qt.rgba(230, 120, 20) (OSC-10)
    readonly property color botonNaranjaAbajo:  "#783200" // Preciclo Qt.rgba(120, 50, 0)

    // Sin valor en la paleta (OSC-03/04/08/09/10/11): oscuro = el más cercano
    readonly property color textoSobreAccion: "#FFFFFF" // "white" sobre relleno de acción o alarma (OSC-09)
    readonly property color textoSobreAlarmaMedia: "#031225" // número sobre alarmaMedia (InsigniaCampana; OSC-16)
    readonly property color velo:        "#99000000" // velo de modales (OSC-03)
    readonly property color veloSuave:   "#80000000"
    readonly property color veloFuerte:  "#CC000000"
    readonly property color sombra:      "#40000000"
    readonly property color sombraSuave: "#30000000"
    readonly property color textoNegro:    oscuro ? "#E9EEF4" : "#000000" // paleta.negro → textoPrimario (OSC-04)
    readonly property color textoPrograma: oscuro ? "#E9EEF4" : "#000209"
    readonly property color textoTitulo:   oscuro ? "#E9EEF4" : "#010006" // Preciclo paleta.tituloAlarmas (OSC-16)
    readonly property color textoEtiqueta: oscuro ? "#A7B3C1" : "#393939" // → textoSecundario
    readonly property color textoUnidad:   oscuro ? "#A7B3C1" : "#424242"
    readonly property color textoPie:      oscuro ? "#A7B3C1" : "#3B3B3B"
    readonly property color textoVersion:  oscuro ? "#8C98A7" : "#8F8F8F" // → textoGuia
    readonly property color textoReloj:    oscuro ? "#E9EEF4" : "#383838" // → textoPrimario
    readonly property color rotuloReloj:   oscuro ? "#A7B3C1" : "#3E3E3E" // → textoSecundario
    readonly property color textoVacio:    oscuro ? "#8C98A7" : "#969BA0" // → textoGuia
    readonly property color bordeSuave:    oscuro ? "#263445" : "#F5F5F5" // → bordeTarjeta
    readonly property color divisorCiclo:  oscuro ? "#2A3746" : "#C0C0C0" // → bordeDivisor
    readonly property color divisorParam:  oscuro ? "#2A3746" : "#C3C3C3"
    readonly property color divisorPie:    oscuro ? "#2A3746" : "#BEBEBE"
    readonly property color lineaAlarmas:  oscuro ? "#2A3746" : "#D7D7D7"
    readonly property color insignia:      oscuro ? "#00CCFF" : "#08C9F9" // insignia de la campana (OSC-08)
    readonly property color textoInsignia: oscuro ? "#031225" : "#FFFFFF" // número de la insignia (OSC-08)
    readonly property color iconoBarraMenu: oscuro ? "#E9EEF4" : "#231F20" // back/home de BarraInferiorMenu (OSC-16)
    readonly property color seleccionSutil:     oscuro ? "#16305E" : "#E8F0FE" // → accionFondoTenue (OSC-11)
    readonly property color puertaCerradaFondo: oscuro ? "#1E2A38" : "#EAF1F8" // → fondoElevado
    readonly property color puertaCerradaBorde: oscuro ? "#3B6FD8" : "#2C4B70" // IndicadorPuerta «PUERTA CERRADA»: claro = fondoBarraSuperior (OSC-22); oscuro = borde de acción (paleta §2)
    readonly property color puertaCerradaTexto: oscuro ? "#6EA4FF" : "#2C4B70" // texto e ícono; claro = fondoBarraSuperior, oscuro = accionPrimarioTexto (≥ 3:1 sobre puertaCerradaFondo)
    readonly property color fondoSeccion:       oscuro ? "#18222F" : "#F2F2F2" // → fondoSutil
    readonly property color peligroFuerte:      "#B71C1C" // PanelEquipo (OSC-10)
    readonly property color naranjaTexto:  oscuro ? "#FFAE5C" : "#EC9233" // → advertenciaTexto
    readonly property color naranjaEstado: oscuro ? "#FF9F3A" : "#FF962B" // → advertencia
}

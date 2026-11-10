pragma Singleton
import QtQuick

QtObject {
    // Lienzo de diseño = panel real medido (1200x1920, proporción 5:8).
    // Las referencias del diseñador (06_MEDIDAS/medidas.csv) vienen en 1080x1920;
    // este es el único lugar que hay que tocar si el lienzo cambia.
    readonly property real anchoVertical: 1200
    readonly property real altoVertical: 1920

    // Tanda horizontal (9-nov): el equipo admite las dos orientaciones del
    // monitor. Con la pantalla vertical (alto > ancho) rige el lienzo vertical
    // de siempre, 1200x1920, sin ningún cambio; con la pantalla horizontal
    // (ancho >= alto) rige el lienzo horizontal fijo 1920x1200 (8:5), con los
    // mismos px de diseño, letras, botones, márgenes y colores: solo cambia la
    // disposición. La fija cada ventana raíz (Main, InstalacionVentana,
    // ReposoInstalacionVentana, NuevoUsuarioHost) con esHorizontal() sobre su
    // propio tamaño, que es el de su monitor en pantalla completa: si Windows
    // gira el monitor, la ventana cambia de tamaño y la disposición la sigue.
    // Fuera de esas raíces (pruebas que arman su propia ventana) vale false.
    property bool horizontal: false
    readonly property real anchoHorizontal: 1920
    readonly property real altoHorizontal: 1200
    function esHorizontal(ancho, alto) { return ancho > 0 && alto > 0 && ancho >= alto }

    // Lienzo vigente según la orientación
    readonly property real anchoDiseno: horizontal ? anchoHorizontal : anchoVertical
    readonly property real altoDiseno: horizontal ? altoHorizontal : altoVertical

    property real factor: 1.0

    // Alto del lienzo en px de diseño (>= altoDiseno). En pantallas más altas que
    // 5:8 (p. ej. 9:16) manda el ancho y el lienzo crece hacia abajo en vez de
    // dejar franjas: las pantallas de alto flexible (PantallaCicloEnCurso) reparten
    // ese espacio; las de alto fijo van dentro de AreaFija, centradas en un área de
    // altoDiseno. En pantallas más anchas que 5:8 manda el alto y quedan franjas laterales.
    // En horizontal es igual con el lienzo 1920x1200: más alto que 8:5 (p. ej. 4:3)
    // crece hacia abajo; más ancho (16:9), franjas laterales.
    property real altoLienzo: altoDiseno

    // ── Regla de proyección (tanda responsive, 10-nov) ────────────────────
    // Una sola implementación para las dos orientaciones y para las 4 raíces:
    // cada raíz solo enlaza factor = factorPara(ancho, alto) y, si su contenido
    // admite alto flexible (Main), altoLienzo = altoLienzoPara(ancho, alto),
    // con el tamaño real de su ventana en px LÓGICOS (los que entrega Qt 6 con
    // la escala de Windows ya aplicada). Así el lienzo ocupa la misma fracción
    // de la pantalla física a 100, 125, 150 o 200 %: la escala de Windows se
    // compensa (no agranda la interfaz) y solo cambia la nitidez.
    //   - Manda el lado que primero se llena: factor = min(ancho / anchoDiseno,
    //     alto / altoDiseno) del lienzo de la orientación de ESE tamaño (no de
    //     `horizontal`, que se enlaza aparte: sin estados intermedios al girar).
    //   - Sobra alto: el lienzo crece hacia abajo (altoLienzo); las pantallas de
    //     alto fijo se centran en AreaFija. Sobra ancho: franjas laterales del
    //     color de fondo de la ventana (Colores.fondoMarinoOscuro, del tema).
    //     Nunca se deforma ni se recorta el lienzo.
    //   - Con un tamaño inválido (0, negativo, NaN o infinito: ventana aún sin
    //     geometría) el factor vale 1 y el alto el de diseño, nunca 0 ni NaN.
    //   - No hay factor mínimo: por debajo del tamaño mínimo soportado el lienzo
    //     se sigue achicando entero (nada queda fuera de la pantalla); las zonas
    //     táctiles conservan su mínimo con margenTactil*().
    // A 1200x1920 y 1920x1200 al 100 % da exactamente factor 1 y el alto de
    // diseño, como antes de esta tanda.
    function _medidaValida(v) { return typeof v === "number" && isFinite(v) && v > 0 }
    function anchoDisenoPara(ancho, alto) { return esHorizontal(ancho, alto) ? anchoHorizontal : anchoVertical }
    function altoDisenoPara(ancho, alto) { return esHorizontal(ancho, alto) ? altoHorizontal : altoVertical }
    function factorPara(ancho, alto) {
        if (!_medidaValida(ancho) || !_medidaValida(alto))
            return 1.0
        return Math.min(ancho / anchoDisenoPara(ancho, alto), alto / altoDisenoPara(ancho, alto))
    }
    function altoLienzoPara(ancho, alto) {
        const altoD = altoDisenoPara(ancho, alto)
        if (!_medidaValida(ancho) || !_medidaValida(alto))
            return altoD
        return Math.max(altoD, alto / factorPara(ancho, alto))
    }

    // Escala de Windows de la pantalla de la ventana raíz (Screen.devicePixelRatio,
    // la enlaza cada raíz; 1 fuera de ellas). Solo la usan las zonas táctiles:
    // el lienzo ya está en px lógicos.
    property real dpr: 1.0
    function _dprValido() { return _medidaValida(dpr) ? dpr : 1.0 }
    // Escala física del lienzo: px físicos por px de diseño (factor x dpr). No
    // cambia con la escala de Windows para una misma resolución física.
    readonly property real escalaFisica: factor * _dprValido()

    // Tamaño mínimo soportado (DECISIÓN SIN CONFIRMAR, informe de la tanda):
    // escala física 0,5, es decir 1024x600 en horizontal y 600x1024 en
    // vertical en px físicos, a cualquier escala de Windows.
    readonly property real escalaFisicaMinima: 0.5
    function soportado(anchoLogico, altoLogico, dprPantalla) {
        const d = _medidaValida(dprPantalla) ? dprPantalla : 1.0
        return factorPara(anchoLogico, altoLogico) * d >= escalaFisicaMinima - 1e-9
    }

    // Zonas táctiles mínimas (DECISIÓN SIN CONFIRMAR): una zona táctil nunca
    // queda por debajo de min(44 px físicos, su propio tamaño de diseño). Lo
    // que sobra se agrega como margen INVISIBLE de la zona (MouseArea con
    // márgenes negativos), sin cambiar el dibujo. A escala física 1 o más (las
    // medidas de diseño exactas) el margen es 0: nada cambia en 1200x1920 ni
    // en 1920x1200 al 100 %.
    readonly property real tactilMinimoFisico: 44
    // `ladoLogico`: el lado de la zona en px lógicos (su width o height real).
    // Devuelve cuánto extenderla por cada lado, en px lógicos (>= 0).
    function margenTactil(ladoLogico) {
        if (!_medidaValida(ladoLogico) || !_medidaValida(factor))
            return 0
        const d = _dprValido()
        const ladoDiseno = ladoLogico / factor
        const minimoLogico = Math.min(tactilMinimoFisico, ladoDiseno) / d
        return Math.max(0, (minimoLogico - ladoLogico) / 2)
    }

    function px(valor) { return valor * factor }
    // pixelSize exige entero; redondear evita que Qt trunque y el texto quede chico
    function fuente(valor) { return Math.max(1, Math.round(valor * factor)) }
    // D8-5.4 (tanda 8, V8b): ningún texto se recorta; si no cabe, la letra puede
    // bajar (fontSizeMode) hasta este mínimo legible (14 px de diseño: los textos
    // del equipo van de 17 a 24 px, así que con 18 casi ninguno podía reducirse)
    readonly property int fuenteMinima: Math.max(1, Math.round(14 * factor))
}

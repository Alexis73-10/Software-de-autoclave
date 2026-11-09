// Lógica pura de la gráfica del ciclo (planeacion_pantalla_ciclo_en_curso.md §8):
// ejes autoajustables con pasos "limpios" y decimación para dibujar un tope de
// puntos sin perder picos. Sin dependencias de QML: la prueba
// tests/test_grafica_ejes_js.py la ejecuta con QJSEngine.

// Eje X en minutos: pasos permitidos y tope de intervalos (≈ 8–9 etiquetas).
const PASOS_X_MIN = [1, 2, 5, 10, 15, 30, 60];
const MAX_INTERVALOS_X = 8;

// Ejes Y: siempre desde 0, con el mismo número de divisiones en ambos ejes para
// que las líneas de cuadrícula coincidan; margen sobre el dato máximo.
export const DIVISIONES_Y = 5;
const MARGEN_Y = 0.05;
const MANTISAS_Y = [1, 2, 2.5, 3, 4, 5, 6, 8];

export function ejeX(tMin) {
    const t = Math.max(0, Number(tMin) || 0);
    let paso = PASOS_X_MIN[PASOS_X_MIN.length - 1];
    for (const p of PASOS_X_MIN) {
        if (Math.ceil(t / p) <= MAX_INTERVALOS_X) { paso = p; break; }
    }
    const intervalos = Math.max(1, Math.ceil(t / paso));
    return { maximo: intervalos * paso, paso: paso };
}

export function ejeY(datoMax) {
    const objetivo = Math.max(Number(datoMax) || 0, 0) * (1 + MARGEN_Y);
    if (!(objetivo > 0))
        return { maximo: DIVISIONES_Y, paso: 1, divisiones: DIVISIONES_Y };
    const necesario = objetivo / DIVISIONES_Y;
    let potencia = Math.pow(10, Math.floor(Math.log10(necesario)));
    for (;;) {
        for (const m of MANTISAS_Y) {
            // redondeo para evitar 2.9999999 por coma flotante
            const paso = Math.round(m * potencia * 1e6) / 1e6;
            if (paso >= necesario)
                return { maximo: Math.round(paso * DIVISIONES_Y * 1e6) / 1e6, paso: paso,
                         divisiones: DIVISIONES_Y };
        }
        potencia *= 10;
    }
}

// ===================== Zoom (tanda 34, ZOM-02..ZOM-06) =====================
// Ventana visible en valores absolutos: { t0, t1 } en minutos y
// { yIzq0, yIzq1 }, { yDer0, yDer1 } en las unidades vigentes de cada eje.
// La vista completa es la de siempre: ejes desde 0 hasta ejeX/ejeY.

// Ventana mínima (ZOM-04): 2 min en X y el 10 % de la escala completa en Y.
export const VENTANA_MIN_X_MIN = 2;
export const VENTANA_MIN_FRACCION_Y = 0.1;
// Divisiones aproximadas de las marcas con zoom (las mismas que sin zoom).
export const DIVISIONES_X = MAX_INTERVALOS_X;
const EJES_Y = [["yIzq0", "yIzq1"], ["yDer0", "yDer1"]];

// Vista completa a partir de los ejes de hoy (ejeX, ejeY izquierdo y derecho).
export function vistaCompleta(ejeXv, ejeIzq, ejeDer) {
    return { t0: 0, t1: ejeXv.maximo, yIzq0: 0, yIzq1: ejeIzq.maximo,
             yDer0: 0, yDer1: ejeDer.maximo };
}

// Marcas de una ventana [min, max] con paso redondo (1, 2 o 5 × 10^n), el menor
// que deja a lo sumo `divisionesObjetivo` intervalos; ninguna marca fuera.
export function marcasVentana(min, max, divisionesObjetivo) {
    const a = Number(min), b = Number(max);
    const n = Math.max(1, Math.floor(Number(divisionesObjetivo) || 1));
    if (!isFinite(a) || !isFinite(b) || !(b > a)) return [];
    const necesario = (b - a) / n;
    let potencia = Math.pow(10, Math.floor(Math.log10(necesario)));
    let paso = 0;
    for (;;) {
        for (const m of [1, 2, 5]) {
            const p = Math.round(m * potencia * 1e9) / 1e9;
            if (p >= necesario * (1 - 1e-9)) { paso = p; break; }
        }
        if (paso > 0) break;
        potencia *= 10;
    }
    const eps = paso * 1e-6;
    const out = [];
    for (let k = Math.ceil((a - eps) / paso); k * paso <= b + eps; k++)
        out.push(Math.round(k * paso * 1e9) / 1e9);
    return out;
}

// Ventana tras un gesto de dos dedos (ZOM-03). `inicio` y `actual` son los dos
// puntos de contacto { xa, ya, xb, yb } en px; `area` el rectángulo de datos
// { x0, x1, y0 (arriba), y1 (abajo) } en px; `umbral` la separación mínima en
// px para escalar un eje. Factor por eje = separación actual / inicial en ese
// eje, centrado en el punto medio inicial; el desplazamiento del punto medio
// mueve la ventana. Los dos ejes Y reciben la misma transformación en px, así
// que se escalan y desplazan con la misma fracción. Sin acotar (acotarVentana).
export function ventanaPorGesto(ventana, inicio, actual, area, umbral) {
    const anchoPx = (area.x1 - area.x0) || 1, altoPx = (area.y1 - area.y0) || 1;
    const dx0 = Math.abs(inicio.xb - inicio.xa), dy0 = Math.abs(inicio.yb - inicio.ya);
    const dx = Math.abs(actual.xb - actual.xa), dy = Math.abs(actual.yb - actual.ya);
    const fx = dx0 >= umbral ? Math.max(dx, 1e-6) / dx0 : 1;
    const fy = dy0 >= umbral ? Math.max(dy, 1e-6) / dy0 : 1;
    const cx0 = (inicio.xa + inicio.xb) / 2, cy0 = (inicio.ya + inicio.yb) / 2;
    const cx = (actual.xa + actual.xb) / 2, cy = (actual.ya + actual.yb) / 2;
    const out = {};
    // X: el instante bajo el punto medio inicial queda bajo el punto medio actual
    const w = ventana.t1 - ventana.t0;
    const tc = ventana.t0 + (cx0 - area.x0) / anchoPx * w;
    const w2 = w / fx;
    out.t0 = tc - (cx - area.x0) / anchoPx * w2;
    out.t1 = out.t0 + w2;
    // Y (px hacia abajo, valores hacia arriba)
    for (const [k0, k1] of EJES_Y) {
        const h = ventana[k1] - ventana[k0];
        const vc = ventana[k0] + (area.y1 - cy0) / altoPx * h;
        const h2 = h / fy;
        out[k0] = vc - (area.y1 - cy) / altoPx * h2;
        out[k1] = out[k0] + h2;
    }
    return out;
}

// Rueda del mouse (solo para probar sin táctil): amplía un eje ("x" o "y", los
// dos Y a la vez) por `factor` (> 1 acerca), dejando fijo el punto en la
// fracción `fraccion` del eje (0 = izquierda/abajo, 1 = derecha/arriba).
export function ventanaPorRueda(ventana, eje, factor, fraccion) {
    const out = Object.assign({}, ventana);
    const f = factor > 0 ? factor : 1;
    const pares = eje === "x" ? [["t0", "t1"]] : EJES_Y;
    for (const [k0, k1] of pares) {
        const w = ventana[k1] - ventana[k0];
        const c = ventana[k0] + fraccion * w;
        const w2 = w / f;
        out[k0] = c - fraccion * w2;
        out[k1] = out[k0] + w2;
    }
    return out;
}

function _acotarTramo(a, b, lo, hi, minimo) {
    const total = hi - lo;
    let ancho = Math.min(Math.max(b - a, minimo), total);
    if (!(ancho > 0)) ancho = total;
    let ini = (a + b) / 2 - ancho / 2;
    if (ini < lo) ini = lo;
    if (ini + ancho > hi) ini = hi - ancho;
    return [ini, ini + ancho];
}

// Límites de ZOM-04: la ventana queda dentro de la vista completa (también al
// desplazar) y no baja de la mínima; si la vista completa es menor que la
// mínima, ese eje no se amplía.
export function acotarVentana(ventana, completa) {
    const out = {};
    [out.t0, out.t1] = _acotarTramo(ventana.t0, ventana.t1, completa.t0, completa.t1,
                                    VENTANA_MIN_X_MIN);
    for (const [k0, k1] of EJES_Y) {
        const minimo = (completa[k1] - completa[k0]) * VENTANA_MIN_FRACCION_Y;
        [out[k0], out[k1]] = _acotarTramo(ventana[k0], ventana[k1], completa[k0], completa[k1],
                                          minimo);
    }
    return out;
}

// La ventana coincide con la vista completa (sin zoom).
export function esVistaCompleta(ventana, completa) {
    for (const [k0, k1] of [["t0", "t1"], ...EJES_Y]) {
        const tol = Math.abs(completa[k1] - completa[k0]) * 1e-6;
        if (Math.abs(ventana[k0] - completa[k0]) > tol || Math.abs(ventana[k1] - completa[k1]) > tol)
            return false;
    }
    return true;
}

// Interpolación lineal entre dos ventanas (transición de restablecimiento;
// la curva InOutQuad la aplica la animación sobre f).
export function interpolarVentana(a, b, f) {
    const out = {};
    for (const k of ["t0", "t1", "yIzq0", "yIzq1", "yDer0", "yDer1"])
        out[k] = a[k] + (b[k] - a[k]) * f;
    return out;
}

// Tramo de índices [desde, hasta] de xs (ordenadas) que cubre [xMin, xMax],
// con un vecino a cada lado para no cortar las líneas en los bordes.
export function tramoVentana(xs, xMin, xMax) {
    const n = xs.length;
    if (n === 0) return { desde: 0, hasta: -1 };
    let lo = 0, hi = n;                       // primer índice con x >= xMin
    while (lo < hi) { const m = (lo + hi) >> 1; if (xs[m] < xMin) lo = m + 1; else hi = m; }
    const desde = Math.max(0, lo - 1);
    lo = 0; hi = n;                           // primer índice con x > xMax
    while (lo < hi) { const m = (lo + hi) >> 1; if (xs[m] <= xMax) lo = m + 1; else hi = m; }
    const hasta = Math.min(n - 1, lo);
    return { desde: desde, hasta: hasta };
}

// Huella de los datos para saber si la serie nueva continúa la anterior (el
// ciclo en curso solo agrega lecturas al final) o es otro ciclo (ZOM-05).
export function huellaDatos(tMin) {
    const t = tMin || [];
    return { n: t.length, primero: t.length ? t[0] : null, ultimo: t.length ? t[t.length - 1] : null };
}
export function continuaDatos(huella, tMin) {
    const t = tMin || [];
    if (t.length === 0) return false;              // sin datos: se restablece
    if (!huella || huella.n === 0) return true;    // nada previo con qué comparar
    return t.length >= huella.n && t[0] === huella.primero && t[huella.n - 1] === huella.ultimo;
}

// Reduce una serie (xs ordenadas, ys con huecos null) a lo sumo a 4 puntos por
// columna de píxel (primero, mínimo, máximo y último de cada columna), en orden
// de tiempo. Los puntos sin lectura (null/undefined/no finitos) se descartan.
export function decimar(xs, ys, xMin, xMax, columnas) {
    const px = [], py = [];
    for (let i = 0; i < xs.length; i++) {
        const y = ys[i];
        if (y === null || y === undefined || !isFinite(y)) continue;
        px.push(xs[i]); py.push(y);
    }
    const cols = Math.max(1, Math.floor(columnas));
    if (px.length <= cols * 4) return { x: px, y: py };

    const rango = (xMax - xMin) || 1;
    const ox = [], oy = [];
    let i = 0;
    while (i < px.length) {
        const col = Math.min(cols - 1, Math.floor((px[i] - xMin) / rango * cols));
        let j = i, iMin = i, iMax = i;
        while (j < px.length &&
               Math.min(cols - 1, Math.floor((px[j] - xMin) / rango * cols)) === col) {
            if (py[j] < py[iMin]) iMin = j;
            if (py[j] > py[iMax]) iMax = j;
            j++;
        }
        const elegidos = Array.from(new Set([i, iMin, iMax, j - 1])).sort((a, b) => a - b);
        for (const k of elegidos) { ox.push(px[k]); oy.push(py[k]); }
        i = j;
    }
    return { x: ox, y: oy };
}

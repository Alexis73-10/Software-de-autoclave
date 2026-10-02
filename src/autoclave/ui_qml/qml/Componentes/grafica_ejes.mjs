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

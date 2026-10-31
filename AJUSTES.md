# AJUSTES (tanda «llenado de fases», rama llenado-fases)

## 2026-10-31 · Paso 2 backend / revisión · Endurecer el LLF de progreso_ciclo (hallazgo 1, BAJA)
- Se pidió: que el bloque LLF de `armar_progreso`/`fraccion_fase` no pueda tumbar el endpoint (un int gigante como 10**400 pasa `_segundos_validos` y `float()` lanza OverflowError).
- Decidió: revisor (Opus); director.
- Cambio: nuevo `_segundos_llf` (conversión a float finito o None) usado solo por el LLF; `fraccion_fase` lo usa y el cálculo por fase de `armar_progreso` va en try/except (fraccion=None, referencia_s=None ante error). `_segundos_validos`, `restante_s`, `resultado`, `fase_terminacion` y `terminacion` no cambian. Invariante: ningún estado distinto de «completada» da fraccion > 0.90.
- Archivos: `src/autoclave/core/runtime/progreso_ciclo.py`.

## 2026-10-31 · Paso 2 backend / revisión · Pruebas faltantes del revisor
- Se pidió: (a) entradas extremas del conteo propio, (b) barrido de estados y caso esterilización 0/420, (d) normalizar_progreso con fallida/interrumpida/activa y 1.0, (e) endpoint con `context.estado` MagicMock real.
- Decidió: revisor (Opus); director.
- Archivos: `tests/test_llf_fraccion_fases.py`, `tests/test_llf_dominio_fraccion.py`, `tests/test_backend_ciclo_en_curso_endpoints.py` (la prueba (e) vive allí por usar su fixture `entorno`).

## 2026-10-31 · Hallazgos aceptados / no corregidos
- Hallazgo 3: `float(_tiempo_seg)` antes de escribir el restante de exposición; despreciable. Aceptado.
- Hallazgo 4: el simulador no pasa `total_exposicion_s`, así que allí la esterilización activa muestra 0.0; fuera del alcance de la tanda. Aceptado.
- Hallazgo 5: los atributos de exposición quedan con valor viejo tras cierres de `CicloState` hasta el reset de la siguiente esterilización; sin efecto (el conteo propio exige estado «activa»). Aceptado.

## Ajuste: tope efectivo en QML (revisión, hallazgo 2)
- Qué: `CirculoFaseLiquido.qml` usa `_topeEfectivo = Math.min(tope, 0.90)`; el enlace ya no puede subir el tope (HAZ-LLF-01).
- Decidió: revisor; aplicó: director.

## Hallazgo fuera de alcance (no corregido)
- `tiempo_restante` (restante_s) lanza OverflowError con un entero gigante en `exposicion_restante_s` y TypeError con referencias None. Preexistente, ajeno a esta tanda; queda para otra.

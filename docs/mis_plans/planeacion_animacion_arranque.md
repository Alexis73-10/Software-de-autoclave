# Planeación — Animación de arranque (intro "del vapor a la precisión")

Estado: borrador v1.1 · 12-oct-2026 (v1.1: logo, barra y textos más grandes y con más peso) · Software de Autoclave (Especifika)
Referencia visual: `docs/diseno/referencias/intro_arranque_preview.mp4` (los nombres de proceso del video son de ejemplo).

## 1. Objetivo
Animación de entrada de ~3,5 s que se reproduce cada vez que el software enciende, no se puede saltar y termina convertida en el splash funcional de arranque: barra de progreso y nombre del proceso real. Es decorativa: no muestra cifras, estados del equipo ni mensajes de "listo".

## 2. Decisiones
| # | Decisión |
|---|---|
| D-01 | Concepto: el vapor (halo difuso) da paso a la precisión (una línea), según el eslogan. |
| D-02 | No se muestra la máquina, para que sirva igual en toda la familia (SAT 180, SAT 430, mesa, laboratorio, puertas manuales o automáticas). |
| D-03 | Se implementa en QML nativo, no en video: no depende de códecs, encaja con `Escala`/`Colores`/`Tipografia` y puede interrumpirse por una alarma. |
| D-04 | Se reproduce en cada encendido, no es saltable y se muestra en las dos pantallas. |
| D-05 | Cada proceso de pantalla (`doble_pantalla.py` lanza uno por puerta) reproduce su propia intro. No hay sincronización entre procesos: las pantallas están en lados distintos de la barrera y nadie ve las dos a la vez. |
| D-06 | El eslogan queda visible durante todo el arranque, siempre en español (es marca, no texto de interfaz). Ver ARR-02. |
| D-07 | Pie con el modelo del equipo (`infoEquipo`, `model_id` del perfil) y la versión del software. Si falta el modelo, solo se muestra la versión. |
| D-08 | Colores, solo tokens de `Colores.qml`: `fondoMarinoOscuro`, `fondoCieloNucleo` y `fondoCieloClaro`, más blanco y `#C7DCFD` (ya usado en la fecha de reposo; agregarlo como token). Se prohíben `alarmaAlta`, `alarmaMedia` y `alarmaBaja`. |
| D-09 | Sin parpadeos ni pulsos repetidos: cada efecto ocurre una sola vez, para no confundirse con las frecuencias de alarma de IEC 60601-1-8 (0,4–2,8 Hz). |

## 3. Composición (fracciones de la altura H y del ancho W de la ventana; tamaños en px de diseño con `Escala.px`)
| Elemento | Posición | Estilo |
|---|---|---|
| Fondo | Pantalla completa | `assets/fondos/fondo-arranque.png`, PreserveAspectCrop (igual que `FondoApp`) |
| Logo | Centro en x = 0,5 W, y = 0,38 H; ancho 480 px | `logo-especifika-blanco.svg` |
| Línea de precisión | 30 px bajo el borde inferior del logo; ancho final 0,56 W; grosor 3 px | Blanco al 95 % |
| Eslogan, línea 1 | y = 0,475 H, centrado | Montserrat Regular 46 px, blanco al 95 % |
| Eslogan, línea 2 | y = 0,515 H | Igual |
| Barra (riel) | y = 0,665 H, ancho 0,72 W, alto 14 px, radio 7 px | Blanco al 25 % |
| Barra (relleno) | Sobre el riel | Blanco al 90 % |
| Nombre del proceso | 34 px bajo la barra | Montserrat Medium 36 px, blanco al 90 % |
| Pie | y = 0,935 H | Montserrat Medium 30 px, `#C7DCFD` al 85 % (mismo tono de la fecha en reposo). Texto: `"<modelo>  ·  Software v<versión>"` |

## 4. Línea de tiempo (s desde que la ventana se muestra)
| Tramo | Animación | Curva |
|---|---|---|
| 0,00–0,60 | Pantalla `fondoMarinoOscuro`. Nace un halo `fondoCieloNucleo` en (0,5 W; 0,38 H), con radio de 0 a 0,10 W y opacidad de 0 a 1. | OutCubic |
| 0,60–1,40 | El halo se expande y revela el fondo completo: la capa oscura pasa a opacidad 0. Tres volutas blancas suaves (opacidad ≤ 6 %) suben 0,07 H y se disipan. | InOutQuad |
| 1,40–2,20 | La línea se dibuja desde el centro hacia los lados, de 0 a 0,56 W. El logo se revela con un recorte centrado del mismo ancho relativo. | OutCubic |
| 2,20–2,65 | La línea baja a la posición de la barra: ancho 0,72 W, grosor de 3 a 14 px. | InOutQuad |
| 2,60–3,00 | La línea pasa a ser el riel (opacidad de 95 % a 25 %). | InOutQuad |
| 2,55–3,05 | Eslogan, línea 1: opacidad de 0 a 0,95 y desplazamiento de +10 px a 0. | OutCubic |
| 2,75–3,25 | Eslogan, línea 2: igual. | OutCubic |
| 3,00–3,50 | Aparecen el nombre del proceso y el pie. | InOutQuad |
| ≥ 3,50 | El relleno de la barra sigue el progreso real (animación de 250 ms entre valores). | OutQuad |

Salida: cuando el arranque termina **y** la intro ya llegó a 3,5 s, la barra se mantiene llena 400 ms. Luego eslogan, barra, proceso y pie se desvanecen en 600 ms y queda solo el fondo, que es el mismo de la pantalla de reposo (`Arranque.qml`, ver ARR-01). Así el relevo no tiene salto.

## 5. Reglas de comportamiento
1. **No retrasa la seguridad.** El backend y el lanzador inician en paralelo desde t = 0. La intro solo muestra información; no espera ni condiciona ninguna etapa del arranque.
2. **Tiempo mínimo.** Si el arranque termina antes de 3,5 s, se espera a que la intro termine; el costo máximo es 3,5 s más la salida. Si el arranque tarda más, la barra queda en el progreso real.
3. **Fallos.**
   - *Bloqueante:* la capa de alarma se superpone de inmediato sobre la intro, en cualquier tramo. La intro se congela en su estado actual y no se pasa a reposo.
   - *Degradable* (p. ej. sin base de datos): el arranque continúa. La alarma se muestra según el catálogo y la intro sigue.
   - *Informativa:* no interrumpe.
4. **Sin backend.** Si no llega progreso en 20 s (valor configurable), se considera fallo bloqueante de arranque y se aplica la regla 3.
5. **Idioma.** El nombre del proceso usa `assets/textos/<idioma>.json`. El eslogan es fijo en español.
6. **Rendimiento.** Solo animaciones de propiedades QML (opacidad, escala, ancho, posición). Sin `MultiEffect` ni blur en tiempo real. El halo y las volutas son PNG con alfa ya renderizados.

## 6. Interfaz con el arranque (dependencia)
La intro necesita un objeto inyectado por `app.py` (propuesto: `progresoArranque`) con:
- `fraccion: real` (0–1, etapas completadas / total)
- `proceso: string` (clave de texto del proceso en curso)
- `terminado: bool`
- `falloBloqueante: bool`

Ese objeto depende de la secuencia de arranque (etapas, verificación de sensores, clasificación de fallos), que aún no tiene plan propio. Mientras no exista, Code debe implementar un simulador con las etapas de ejemplo de la previsualización, sin conectarlo al flujo real.

## 7. Archivos
- **Nuevo** `qml/Pantallas/IntroArranque.qml`: la intro y el splash.
- **Nuevos** `assets/fondos/halo_arranque.png` (radial `fondoCieloNucleo` → transparente, 512 px) y `assets/fondos/voluta_vapor.png` (blanca, alfa suave, 256 × 512 px). Se generan con un script en `tools/`.
- **Modificar** `Main.qml`: `IntroArranque` es lo primero que se muestra. Al terminar, pasa a la pantalla de reposo actual.
- **Modificar** `app.py`: inyectar `progresoArranque` y la versión del software (`importlib.metadata.version("autoclave")`).
- `assets/textos/es.json` y `en.json`: nombres de los procesos de arranque.

## 8. Hallazgos
| Código | Severidad | Hallazgo | Recomendación |
|---|---|---|---|
| ARR-01 | Media | `Pantallas/Arranque.qml` no es el arranque: es la pantalla de reposo con reloj (*standby*). El nombre choca con esta función nueva. | Renombrar `Arranque.qml` → `Reposo.qml` (y sus referencias en `Main.qml`) en un cambio aparte, antes de crear `IntroArranque.qml`. |
| ARR-02 | Baja | No existe una versión oficial del eslogan en inglés. El requisito bilingüe aplica a la interfaz. | Mantener el eslogan en español. Si Especifika define una versión oficial en inglés, se agrega como texto de marca. |
| ARR-03 | Media | No existe la fuente de progreso del arranque (§6). | Plan de la secuencia de arranque antes de conectar la intro al flujo real. |
| ARR-04 | Baja | La ventana QML es 5:8 (600 × 960). Las referencias del diseñador son 9:16. | Usar solo fracciones de H/W y `Escala.px`; no hay posiciones absolutas en 1920. |
| ARR-05 | Info | El video del SAT 180 (`arranque_sat180.mp4`, 9:16) no se usa en el equipo. | Reservarlo para uso comercial (web, ferias). |

## 9. Fuera de alcance
La secuencia de arranque en sí (etapas, sensores, clasificación de fallos), el apagado y el sonido (la intro no tiene audio).

## 10. Criterios de aceptación
1. La intro dura 3,5 s ± 1 cuadro y la salida es de 1,0 s, medidas en el PC industrial.
2. El último cuadro de la salida es idéntico al fondo de la pantalla de reposo (comparación visual en las dos pantallas).
3. Un fallo bloqueante simulado en t = 0,3 s, 1,5 s y 3,0 s muestra la alarma sobre la intro en menos de 200 ms.
4. Sin backend, el fallo de arranque aparece a los 20 s.
5. Ningún cuadro contiene cifras de proceso, colores de alarma ni la palabra "listo".
6. Con `en.json` activo, los procesos salen en inglés y el eslogan en español.
7. Las dos pantallas reproducen la intro de forma independiente sin errores en el log.
8. Uso de CPU/GPU durante la intro dentro de lo normal del PC industrial (sin caídas de cuadros visibles).

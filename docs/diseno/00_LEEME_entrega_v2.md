# ENTREGA — INTERFAZ DE USUARIO AUTOCLAVE

**Versión 1.0 · 2026** · Documento índice del paquete.
Destino: pantalla táctil vertical, mesa de diseño 1080 × 1920 px, RGB, interfaz en QML (Qt 6) sobre Windows 11.

---

## CÓMO ESTÁ ORGANIZADO ESTE PAQUETE

| Carpeta | Contiene | Punto de la solicitud |
|---|---|---|
| `01_ESPECIFICACIONES` | PDF de 31 páginas con todas las especificaciones diagramadas | 1.6 |
| `02_COLOR` | Paleta en `.ase` para Illustrator, `.csv`, y tokens `.css` / `.json` para el programador | 3 |
| `03_TIPOGRAFIA` | Los 21 estilos de texto nombrados, con px, interlineado, peso y tracking | 2 |
| `04_ICONOS_SVG` | 49 íconos en SVG 48 × 48 px (monocromo y color) + PNG al doble + índice | 9 |
| `05_PNG_REFERENCIA` | Las 6 pantallas a 1080 × 1920 px, 72 ppp | 10 |
| `06_MEDIDAS` | Márgenes, rellenos, separaciones, radios y bordes en px enteros | 4 |
| `07_TEXTOS` | Textos finales en español (JSON listo para i18n) y el caso más largo de cada campo variable | 11 |

Los puntos 5 (componentes y estados), 6 (pantallas y navegación), 7 (teclados) y 8 (gráfica de ciclo) están especificados **dentro del PDF** de `01_ESPECIFICACIONES`, porque son especificación gráfica, no archivos sueltos.

---

## TRES COSAS QUE HAY QUE RESOLVER ANTES DE SEGUIR

**1. El archivo se está haciendo en CorelDRAW, no en Illustrator.**
Los metadatos del PDF entregado dicen `CorelDRAW 2021 / Corel PDF Engine 23.0`. La solicitud pide expresamente trabajo en Adobe Illustrator y no mezclar con CorelDRAW. Hay que decidir: migrar el archivo a `.ai` nativo o pedir al cliente que acepte el flujo actual por escrito. Reexportar un PDF desde Corel **no** equivale a un `.ai` editable con capas nombradas.

**2. La proporción ya casi está, faltan 4 px.**
Las mesas nuevas miden 1:1,7816. La proporción 9:16 exacta es 1:1,7778. Llevadas a 1080 px de ancho, las pantallas quedan en **1924 px de alto en vez de 1920**. Es un ajuste de 0,2 %: basta con fijar la mesa en 1080 × 1920 px exactos y reencajar, no hay que rediseñar nada. Los PNG de `05_PNG_REFERENCIA` ya están a 1080 × 1920.

**3. Faltan los colores y el componente de alarma.**
IEC 60601-1-8 exige tres prioridades visuales diferenciadas. Se añadieron a la paleta (`alarma_alta #EE0000`, `alarma_media #FFCC00`, `alarma_baja #00CCFF`) pero **el componente todavía no está dibujado**. Anatomía y frecuencias de parpadeo: página 13 del PDF.

---

## 02_COLOR — cómo se usa

- `paleta_especifika.ase` → en Illustrator: panel **Muestras › menú › Abrir biblioteca de muestras › Otra biblioteca**. Trae 46 colores agrupados en 6 familias. Todo objeto del arte debe apuntar a una muestra, nunca a un color escrito a mano.
- `tokens.css` y `tokens.json` → para el programador. Un solo archivo con hexadecimales en todo el proyecto.
- `paleta.csv` → la misma paleta en texto plano, para pegar en cualquier documento.

Cuatro colores del arte **no son legibles como texto** y tienen una variante oscura obligatoria: naranja `#FF9933` → `#B35A00`; turquesa `#03C9B2` → `#00806F`; verde `#009933` → `#007A29`; y el texto blanco sobre la zona clara del degradado necesita un velo. Detalle en la página 14 del PDF.

---

## 04_ICONOS_SVG — qué hay y qué falta

```
svg/         49 íconos monocromos (fill #031225) — versión normativa, Qt les aplica el color
svg_color/   los mismos 49 con los colores originales del diseño
png_96/      vista previa a 96 × 96 px (el doble de la mesa)
indice_iconos.csv      lista de archivos con su origen
indice_visual_iconos.png   hoja de contacto para revisar de un vistazo
```

Todos cumplen: mesa cuadrada de 48 × 48 px, `viewBox="0 0 48 48"`, atributos de presentación, sin texto vivo, sin filtros, sin máscaras, sin imágenes incrustadas, decimales a 2, `baseProfile="tiny"`. Se extrajeron de los vectores reales de los dos PDF, no se redibujaron.

**42 íconos provienen del arte.** Siete son generados porque no existían en los mockups y hacen falta para los teclados y los campos: `mas`, `menos`, `confirmar`, `borrar`, `chevron_izquierda`, `chevron_arriba`, `ojo_ocultar`. Están marcados como *Generado* en `indice_iconos.csv`.

**Faltan por dibujar** (no existen en ningún mockup, se necesitan para completar el sistema):

| Archivo | Para qué |
|---|---|
| `alarma_alta.svg`, `alarma_media.svg`, `alarma_baja.svg` | Las tres prioridades de IEC 60601-1-8 |
| `sin_conexion.svg` | Banda de pérdida de comunicación con el controlador |
| `modo_prueba.svg` | Banda de modo prueba activo |
| `puerta_1.svg`, `puerta_2.svg` | Flechas de carga y descarga, espejadas |
| `entrada_digital.svg`, `salida_digital.svg` | Pantallas de entradas y salidas |
| `calibracion.svg` | Calibración de sensores |
| `red_ethernet.svg` | Conexión por cable, junto a `conectividad.svg` (wifi) |
| `bloqueo.svg` | Puerta bloqueada durante el ciclo |

Notas de uso: `sensor_temperatura_2` es el termómetro morado de *Temp 1*; `sensor_tiempo_secado` son las líneas de vapor de *Tiempo Sec.*; `alerta` es el signo de admiración del distintivo de estado; `campana` y `campana_alerta` son el mismo dibujo con y sin distintivo.

---

## 05_PNG_REFERENCIA

- `pantallas_1080x1920/` → las 6 pantallas a la medida solicitada, 72 ppp. Arranque, nuevo usuario y ciclo en curso provienen del archivo corregido; menú, inicio de sesión y opciones, del anterior.
- `proporcion_original/` → las mismas pantallas del archivo anterior sin ajustar, para comparar qué cambió.

Son **referencia visual, no fuente de medida ni de color**. Las medidas se toman de `06_MEDIDAS` y del `.ai`; los colores, de `02_COLOR`.

---

## LO QUE FALTA PRODUCIR

1. Archivo `.ai` editable con capas nombradas, mesas de 1080 × 1920 px exactos.
2. Catorce pantallas: secado, ciclos, menú de impresión, entradas/salidas, entradas digitales, temperaturas, presiones, salidas digitales, parámetros de ciclo, calibración de sensores, emergentes, error, sin conexión y modo prueba. Inventario completo en la página 21 del PDF.
3. Una mesa por componente con sus cinco estados (normal, presionado, deshabilitado, seleccionado, activo/alarma). Sin estado *hover*.
4. Tres mesas de teclado: numérico, alfanumérico letras y alfanumérico símbolos.
5. Los once íconos pendientes de la tabla de arriba.
6. Archivos de fuente `.ttf` u `.otf` con licencia que permita instalarlos con el software. El PDF viene con el texto en curvas, así que la familia no se puede extraer: hay que confirmarla.

## LO QUE HAY QUE PREGUNTARLE AL CLIENTE

1. Resolución y diagonal de la pantalla más pequeña del catálogo.
2. Familia tipográfica definitiva y quién entrega los archivos de fuente.
3. Validación regulatoria de frecuencias y colores de alarma, y si hace falta señal acústica.
4. ¿Un solo panel para las dos puertas o uno por puerta?
5. Matriz de roles y permisos por módulo.
6. Rangos, bandas de advertencia y límites de cada variable por programa.
7. Catálogo de códigos de alarma con su mensaje redactado en lenguaje de operador.

## CORRECCIONES DE TEXTO DETECTADAS EN EL ARTE

| Dice | Debe decir | Motivo |
|---|---|---|
| `°Kpa` | `kPa` | Kilopascal: k minúscula, P mayúscula, sin símbolo de grado |
| `Tiempo 1` (leyenda de la gráfica) | `Temp 1` | La tarjeta de sensor la llama *Temp 1*: es la misma variable |
| `Active` (interruptor de nuevo usuario) | `Activo` | Quedó en inglés |

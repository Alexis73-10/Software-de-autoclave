# Planeación: Pantalla de ciclo (mockup-01) — Software de Autoclave

Destino sugerido en el repo: `docs\mis_plans\planeacion_pantalla_ciclo_ui.md`
Imagen de referencia obligatoria: `pantalla_ciclo_sin_grafica.png` (1196 × 1917 px). Copiarla junto a este archivo, por ejemplo en `docs\mis_plans\ref\`.

---

## 0. Reglas de trabajo para Claude Code

1. Leer el código existente de la capa UI (`src/autoclave/ui_pyside/`, `ui/window/main_window.py`, `ui/cycle/cycle_window.py`) antes de proponer o modificar nada. Si el stack de la vista (QML o Widgets) no es evidente, detenerse y preguntar (PC-02).
2. No asumir datos faltantes. Todo lo que este documento marca como pendiente (sección 9) se resuelve preguntando a Cristian, no decidiendo por cuenta propia.
3. Si encuentra discrepancias entre este documento y el código o la imagen, reportarlas como notas de consistencia; no corregirlas en silencio.
4. Trabajar en la rama `dev`. No hacer commit hasta que Cristian confirme visualmente el resultado.
5. No tocar archivos ajenos a esta pantalla. No modificar la lógica de puertas, del ciclo ni del backend: esta tarea es de presentación y de enlace con los servicios que ya existen.
6. Tono de reporte: técnico, directo. Sin explicaciones largas salvo que la complejidad lo exija.

---

## 1. Objetivo

Implementar la pantalla de ciclo del autoclave de forma que, renderizada a 1196 × 1917 px, coincida con `pantalla_ciclo_sin_grafica.png` en posición, tamaño, color y texto. Los textos y valores del mockup son datos de ejemplo; en la aplicación deben venir de los servicios reales (sección 7).

Cambios de diseño respecto a la pantalla de ciclo anterior (contexto, ya aplicados en la imagen):

- Se elimina la gráfica del ciclo, la barra de fases y el contador de tiempo transcurrido.
- El botón "Pausar ciclo" se reemplaza por un único botón que alterna abrir/cerrar puerta.
- El botón "Cancelar ciclo" se reemplaza por "Iniciar ciclo".
- El espacio liberado aloja el listado de alarmas y avisos.
- En la barra inferior, el ícono de carpeta se reemplaza por el avatar de usuario del login.

---

## 2. Sistema de coordenadas

- Lienzo de referencia: 1196 × 1917 px, origen arriba a la izquierda. Relación de aspecto 0.6239 (≈ 10:16).
- Todas las medidas de este documento están en píxeles del lienzo de referencia. Formato: `x, y, w, h` (esquina superior izquierda y tamaño). Se midieron directamente sobre la imagen.
- La resolución real de la pantalla táctil aún no está confirmada (PC-01). Implementar todas las medidas escalables: definir un factor `s = ancho_real / 1196` y multiplicar cada medida por `s`, o construir sobre un lienzo lógico de 1196 × 1917 con escalado uniforme.
- Cuando dos medidas del documento discrepen con la imagen, prevalece la imagen.

---

## 3. Fondo

Degradado azul que ocupa todo el lienzo. Es el mismo fondo de las demás pantallas del mockup. Reutilizar el fondo compartido de la aplicación si ya existe; si no, reconstruirlo con las muestras siguientes.

Muestras RGB por altura `y`, tomadas en el margen izquierdo (x = 8) y en el margen derecho (x = 1188). El degradado varía en vertical y algo en horizontal (el lado derecho es más claro en la zona media):

```
y     izquierda          derecha
0     (31, 59, 83)       (44, 61, 91)
120   (47, 86, 119)      (52, 85, 139)
240   (62, 106, 155)     (62, 106, 171)
360   (62, 126, 174)     (73, 123, 196)
480   (67, 134, 186)     (83, 139, 213)
600   (72, 135, 189)     (96, 154, 218)
720   (70, 133, 186)     (112, 169, 224)
840   (59, 127, 176)     (129, 180, 223)
960   (52, 119, 162)     (144, 190, 224)
1080  (44, 111, 138)     (154, 195, 223)
1200  (47, 97, 124)      (156, 196, 221)
1320  (43, 81, 100)      (145, 181, 207)
1440  (35, 63, 77)       (123, 153, 179)
1560  (30, 46, 59)       (101, 123, 147)
1680  (27, 34, 42)       (78, 94, 117)
1800  (25, 32, 40)       (64, 79, 98)
```

---

## 4. Cabecera (sobre el fondo, elementos blancos)

- Logotipo "especifika": `x=73, y=57, w=267, h=71`. Activo vectorial del diseñador (blanco).
- Hora "16:00": `x=475, y=38, w=245, h=70`. Blanco, negrita, tipografía sans geométrica (Montserrat Bold como sustituto; alto de dígito 69 px, equivale a ≈ 96 px de tamaño de fuente).
- Fecha "12 oct - 2026": `x=509, y=122, w=178, h=19`. Blanco, regular, ≈ 22 px.
- Campana: `x=888, y=64, w=51, h=57`, ícono blanco. Insignia circular `x=922, y=50, w=26, h=25`, color `#08C9F9` (8, 201, 249), con el número "2" en blanco.
- Engranaje: `x=1043, y=64, w=57, h=58`, ícono blanco.

La hora y la fecha vienen del reloj del sistema. El número de la insignia es el conteo de alarmas o avisos activos (ver PC-04).

---

## 5. Panel principal y tarjetas

### 5.1 Panel contenedor

- `x=19, y=177, w=1159, h=1723` (llega hasta y=1899). Relleno `#FFFFFF`. Radio de esquina ≈ 30 px.
- Contiene, de arriba hacia abajo: tarjeta de ciclo, tarjeta de parámetros, tarjeta de alarmas y avisos, fila de botones, barra inferior.

### 5.2 Tarjeta de ciclo (parte superior del panel)

- Ocupa `x=19`, `y=177` hasta `y=405`. Línea inferior de 2 px, color `#E5E5E5` (229, 229, 229), en y = 404–405.
- Dos divisores verticales de 2 px, color ≈ `#C0C0C0`, en `x=350` y `x=838`, de y=219 a y=383.
- Columna izquierda (centro ≈ x=200):
  - Rótulo "CICLO ACTIVO": `x=137, y=217, w=124, h=12`. Negro, mayúsculas, ≈ 17 px, peso medio.
  - Valor "03": `x=148, y=259, w=104, h=74`. Negro (0,0,0), negrita tipo Arial/Helvetica, ≈ 102 px.
  - Texto "No preparado": `x=126, y=359, w=150, h=21`. Naranja `#EC9233` (236, 146, 51), semibold, ≈ 22 px.
- Columna central (centro ≈ x=594):
  - Rótulo "PROGRAMA": `x=547, y=217, w=105, h=12`. Mismo estilo que el rótulo izquierdo.
  - Nombre del programa: `x=469, y=282, w=260, h=26`. Color `#000209`, Montserrat Bold 36 px, centrado horizontalmente en la columna. En el mockup dice "BOWE & DICK".
  - Punto de estado: círculo `x=503, y=342, w=21, h=21`, color `#25BA9E` (37, 186, 158).
  - Texto "Ejecutando": `x=543, y=344, w=120, h=20`. Mismo color `#25BA9E`, ≈ 20 px.
- Columna derecha (centro ≈ x=1010):
  - Rótulo "ESTADO": `x=976, y=217, w=70, h=12`.
  - Círculo naranja: `x=972, y=256, w=78, h=78`, color `#FF962B` (255, 150, 43), con signo "!" blanco centrado.
  - Texto "No preparado": `x=935, y=359, w=150, h=21`. Color `#EC9233`.

### 5.3 Tarjeta de parámetros

- Ocupa aproximadamente `x=34, y=426, w=1129, h=207` (borde superior en y≈425–426, inferior en y≈631–632). Borde de 2 px muy claro (≈ `#F5F5F5`), fondo blanco, radio ≈ 30 px.
- Cinco columnas. En cada una: ícono, etiqueta, valor y unidad. Posiciones medidas:

```
Col 1  ícono termómetro gris   x=73,  y=448, w=20, h=33
       etiqueta "Temp. Ester." x=129, y=460, w=75, h=11
       valor    "134.0"        x=87,  y=515, w=130, h=38
       unidad   "°C"           x=138, y=587, w=27, h=19
Col 2  ícono reloj gris        x=294, y=447, w=35, h=35
       etiqueta "Tiempo Est."  x=357, y=458, w=72, h=12
       valor    "3.5"          x=335, y=515, w=73, h=38
       unidad   "min"          x=354, y=585, w=48, h=21
Col 3  ícono vapor gris        x=532, y=446, w=27, h=39
       etiqueta "Tiempo Sec."  x=588, y=458, w=74, h=12
       valor    "15"           x=570, y=515, w=58, h=41
       unidad   "min"          x=575, y=585, w=48, h=21
Col 4  ícono termómetro morado x=751, y=448, w=20, h=33
       etiqueta "Temp cámara"  x=798, y=460, w=83, h=12
       valor    "085.0"        x=761, y=515, w=139, h=41
       unidad   "°C"           x=808, y=587, w=27, h=19
Col 5  ícono manómetro turquesa x=983, y=450, w=37, h=31
       etiqueta "Presión"      x=1051, y=458, w=45, h=9
       valor    "100.8"        x=977, y=515, w=137, h=41
       unidad   "°Kpa"         x=1031, y=587, w=60, h=24
```

- Divisores verticales de 2 px, color ≈ `#C3C3C3`, entre columnas (x ≈ 254, 481, 707, 937; verificar sobre la imagen).
- Estilos:
  - Etiqueta: Montserrat SemiBold 12 px, color `#393939` (57, 57, 57).
  - Valor: negrita tipo Arial/Helvetica ≈ 54 px, color `#000000`, centrado en su columna.
  - Unidad: negrita tipo Arial/Helvetica ≈ 27 px, color `#424242` (66, 66, 66).
- Los valores del mockup son de ejemplo. Los formatos visibles son: un decimal (134.0), sin decimales (15), tres dígitos enteros con cero a la izquierda (085.0). Definir el formato por campo antes de enlazar datos (PC-04).

### 5.4 Tarjeta de alarmas y avisos

- `x=34, y=655, w=1130, h=944` (y=655 a 1598). Borde de 2 px, color `#E5E5E5`, radio ≈ 30 px, fondo blanco.
- Título "ALARMAS Y AVISOS": `x=81, y=697, w=272, h=20`. Color `#010006`, Poppins Bold ≈ 28 px, mayúsculas.
- Línea divisoria: `x=81` a `x=1116`, `y=737`, 2 px, color `#D7D7D7` (215, 215, 215).
- Texto de estado vacío "Sin alarmas ni avisos activos": centrado en `(598, 1166)`, ancho ≈ 399, alto ≈ 21. Poppins Regular ≈ 28 px, color `#969BA0` (150, 155, 160).
- El listado real de alarmas y avisos se define después (PC-06). En esta etapa se implementa el contenedor, el título, la línea y el estado vacío, con un modelo de lista que pueda poblarse luego sin cambiar la geometría.

---

## 6. Fila de botones y barra inferior

### 6.1 Botón abrir/cerrar puerta (izquierda)

- Cuerpo: `x=41, y=1615, w=298, h=110`. Radio ≈ 14 px. Sombra suave hacia abajo (≈ 8 px, muy tenue).
- Relleno: degradado vertical azul. Muestras a x=310: y=1618 → (46, 86, 246); y=1654 → (31, 57, 187); y=1690 → (16, 28, 130); y=1714 → (4, 9, 91).
- Círculo blanco de contorno: `x=64, y=1629, w=84, h=84`, contorno ≈ 4 px, sin relleno.
- Ícono de puerta blanco dentro del círculo, centrado en `(105.5, 1670.5)`, alto ≈ 42 px. PROVISIONAL: usar `open_door_1.png` / `close_door_1.png` (PC-03).
- Texto "ABRIR PUERTA": inicia en `x=172`, línea base y=1676, Poppins Medium 17 px, blanco, mayúsculas. Altura de mayúscula ≈ 12 px.

### 6.2 Botón Iniciar ciclo (derecha)

- Cuerpo: `x=845, y=1616, w=302, h=110`. Radio ≈ 14 px. Misma sombra.
- Relleno: degradado vertical verde. Muestras a x=1010: y=1618 → (8, 168, 64); y=1654 → (6, 144, 55); y=1690 → (6, 112, 44); y=1714 → (2, 90, 34). Referencia de color: verde del ícono de "Iniciar ciclo" del menú principal (6, 151, 56).
- Círculo blanco de contorno: `x=866, y=1629, w=84, h=84`, contorno ≈ 4 px.
- Triángulo "play" blanco centrado en el círculo, ligeramente desplazado a la derecha para compensación óptica.
- Texto "INICIAR CICLO": inicia en `x=980`, línea base y=1676, Poppins Medium 17 px, blanco.

### 6.3 Zona central de la fila

Vacía (donde estaba el contador de tiempo transcurrido). No colocar ningún elemento.

### 6.4 Barra inferior

- Tarjeta: `x=33, y=1744, w=1130, h≈141` (borde superior y=1744–1745, inferior y≈1884). Borde de 2 px muy claro (≈ `#F5F5F5`), radio ≈ 26 px, fondo blanco.
- Divisores verticales de 2 px, color ≈ `#BEBEBE`, en `x=346` y `x=833`, de y=1763 a y=1869.
- Izquierda: ícono de equipo (`x=70, y=1763`) y dos líneas de texto: "Modelo: SPK-SAT 45H" y "Serie: Sn123456". Montserrat SemiBold ≈ 15 px, color `#3B3B3B`. El bloque completo ocupa `x=70, y=1763, w=187, h=99`.
- Centro: avatar de usuario, círculo de 88 px de diámetro con centro en `(594, 1806)` (`x=550, y=1762`). Mismo avatar que la pantalla de login (círculo gris claro con silueta de usuario). Toque → misma acción que abría la carpeta solo si Cristian lo confirma (PC-05b); por ahora el destino es indefinido.
- Derecha: ícono de inicio (casa), `x=957, y=1769, w=88, h=77`, color `#232323`. Texto "V: 1.0": `x=1091, y=1852, w=50, h=15`, color `#8F8F8F`, negrita ≈ 18 px.

---

## 7. Comportamiento y enlace con el código existente

Información tomada del código actual; verificar antes de reutilizar.

- Botón de puerta: el código de la interfaz anterior decide la acción con `ui_service.get_estado_puerta(door_name)`. Si el estado es `"ABIERTO"` ejecuta `door_commands.close(door_name)`; en cualquier otro caso ejecuta `door_commands.open(door_name)`. Devuelve `(ok, motivo)`; si `ok` es falso y hay `motivo`, se muestra un aviso de "Acción no permitida" con el motivo.
- Imágenes: se cargan de `autoclave/images/` con `open_door_{n}.png`, `close_door_{n}.png` y `start_cycle.png` (n = puerta de origen). Reutilizarlas para el estado provisional.
- Botón Iniciar ciclo: llama a `ui_service.start_cycle()`; si el backend lo rechaza (devuelve falso) no se abre la ventana de ciclo y se registra la advertencia.
- Las reglas de permisos y de seguridad de puerta viven en `ServicioPuertas` y en `AdvancedDoor`. La UI no controla hardware directamente.
- Fuente de cada campo del mockup (ciclo activo, nombre de programa, estado, Temp. Ester., Tiempo Est., Tiempo Sec., Temp cámara, Presión): sin definir todavía (PC-04).

---

## 8. Criterios de aceptación

1. Renderizar la pantalla sin interfaz visible (modo offscreen, `QT_QPA_PLATFORM=offscreen`) a 1196 × 1917 px con los datos de ejemplo del mockup y guardar el resultado como PNG.
2. Comparar contra `pantalla_ciclo_sin_grafica.png` y generar una imagen de diferencia.
3. Umbral inicial sugerido: diferencia media por canal menor a 8/255 en zonas sin texto (fondo, tarjetas, botones, bordes). Las diferencias en texto se aceptan mientras las tipografías reales del diseñador estén pendientes (PC-03), pero cada texto debe conservar posición y tamaño dentro de ±2 px.
4. Verificar a mano: alineación de las cinco columnas de parámetros, centrado del nombre del programa, los dos botones en las posiciones indicadas y la zona central de la fila vacía.
5. Cristian confirma visualmente. Solo después se hace el commit.

---

## 9. Puntos abiertos (resolver preguntando a Cristian)

- PC-01: Resolución real de la pantalla táctil (Faytech 12.1") en orientación vertical y política de escalado. El lienzo de referencia (1196 × 1917) no es una resolución nativa conocida.
- PC-02: Stack de esta vista. El plan de UI eligió QML/Qt Quick sobre PySide6, pero `ui_pyside/views/login.py` está hecho con Widgets y hojas de estilo. Confirmar cuál corresponde para la pantalla de ciclo.
- PC-03: Activos definitivos del diseñador. Pendientes: tipografías reales (aquí se usaron Montserrat, Poppins y una sans tipo Arial como sustitutos), íconos SVG definitivos de abrir/cerrar puerta y de iniciar ciclo, y el avatar. Recordar la restricción de Qt SVG Tiny 1.2 (texto convertido a trazos, sin CSS embebido, filtros ni degradados complejos).
- PC-04: Enlace de datos. Definir la fuente y el formato de cada campo. Además, el mockup muestra "No preparado" junto a "Ejecutando" y un botón "Iniciar ciclo" en una pantalla de ciclo en ejecución; confirmar la lógica de estados y cuándo se habilita el botón. Definir también qué cuenta la insignia de la campana.
- PC-05: Comportamiento del botón de puerta en estados intermedios (abriendo, cerrando, atrapada, desconocida, error) y texto del estado alterno ("CERRAR PUERTA"; el mockup solo muestra "ABRIR PUERTA"). Definir además el destino del toque en el avatar de la barra inferior.
- PC-06: Formato del listado de alarmas y avisos (fila, prioridad, colores, sonido). Debe cumplir IEC 60601-1-8 en colores de prioridad.
- PC-07: Ortografía y unidades del mockup. "BOWE & DICK" está escrito así por indicación de Cristian (la grafía habitual es "Bowie & Dick"); "Temp cámara" lleva tilde por decisión mía; la unidad de presión aparece como "°Kpa" y lo correcto es "kPa". Implementar estos textos como constantes fáciles de cambiar hasta que se confirmen.

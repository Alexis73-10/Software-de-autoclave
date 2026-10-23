# V8b — Textos completos y traducciones (tanda 8)

Rama `tanda-8-v8b` (worktree `agent-a4e1a61384f94e185`), creada desde `tanda-8` (23704cb).
Puntos: D8-5.4 (sin abreviaturas ni recortes), D8-5.5 (sin mezclar idiomas), D8-5.11 (barrido
de traducciones). Trabajo sin supervisión; la sesión se cortó una vez por límite de uso y se
retomó (los cambios pendientes se commitearon por grupos al retomar).

**V8b se une la ÚLTIMA.** Las pruebas son genéricas (recorren todo el catálogo, todo el QML y
todo el Python de la UI): al unir `tanda-8` con los textos de R8, E1, V8a, L8 y D8, fallarán
donde esos textos no cumplan, y ahí hay que repasarlos (lo pedirá la sesión principal).

## Commits

| Commit | Contenido |
|---|---|
| 6768e33 | Pruebas genéricas `tests/test_v8b_textos.py` (TDD, antes del barrido) |
| 032105a | Catálogos `es.json`/`en.json` y `docs/mis_plans/revision_traducciones.md` |
| 71d3912 | Motivos de fallo sin "Timeout" (3 fases, solo textos) y motivo de CIC-10 traducible (`alarmas_i18n.py`, `ui_bridge.py`) |
| 72bddb3 | Componentes QML sin recorte + `Escala.fuenteMinima` |
| 67e8873 | Pantallas QML sin recorte |
| 6d851d9 | Pruebas existentes ajustadas a los textos nuevos, `test_v8b_truncado_qml.py`, `v8b_capturas.py` |
| 83d7134 | `Escala.fuenteMinima` de 18 a 14 px de diseño (ver decisión 3) |
| 88d0352 | `test_opciones_qml.py`: el nombre largo del cajón puede ocupar más de dos líneas |
| 53ecb8a | Capturas es/en regeneradas con el QML final |
| (último) | Este informe y el registro de pruebas |


## Qué se hizo, por punto

### D8-5.4 — ningún texto abreviado ni recortado
- Catálogos: se completaron todas las abreviaturas ("Temp. ester." → "Temperatura de
  esterilización", "Pres. chaqueta" → "Presión de chaqueta", "Pág." → "Página", "Compl." →
  "Completados", "N.º" → "número"…; en inglés "Ster. Temp." → "Sterilization temperature",
  etc.). Resuelve el término dudoso T-07.
- Sección nueva `parametros.<sección>.<clave>` (95 nombres visibles en es y en): antes
  OPCIONES › Parámetros del ciclo mostraba la clave convertida ("Presion add ester"), y en
  español también con la interfaz en inglés.
- QML: se quitaron todos los `elide: Text.Elide*` y `maximumLineCount` de pantallas y
  componentes. Según el caso: `wrapMode: Text.Wrap` (dos líneas) o
  `fontSizeMode: Text.HorizontalFit` con `minimumPixelSize: Escala.fuenteMinima` (letra menor,
  mínimo 18 px de diseño, nueva propiedad en `Tema/Escala.qml`). En filas de alto fijo se
  añadió `height: parent.height; verticalAlignment: Text.AlignVCenter` para que el texto en
  dos líneas quede centrado.
- Única excepción, marcada `// v8b-permitido:`: el eco del teclado alfanumérico
  (`TecladoAlfanumerico.qml`), que con texto largo muestra el final de lo tecleado (ElideLeft).
- Revisión de truncado de I4 extendida al español a 1024 px (`tests/test_v8b_truncado_qml.py`).

### D8-5.5 — sin mezclar idiomas
- `es.json`: "timeout" → "tiempo límite", "duty" → "ciclo de trabajo", "LOGIN" → "INICIO DE
  SESIÓN", "ON/OFF" → "ENCENDIDA/APAGADA", "Offset" → "Desplazamiento", etc.
- `en.json`: sin palabras ni letras del español (salvo "Español" en el selector de idioma).
- Motivos de fallo que arma Python: `calentamiento.py`, `descompresion.py` y
  `protocolo_fallo.py` cambian "Timeout de …" por "Tiempo límite de …". **Solo cambia el
  texto** (verificado con el diff; ningún código compara esos textos — búsqueda de
  "Timeout de" en `src/` y `tests/`).
- Lista completa de cambios en `docs/mis_plans/revision_traducciones.md` (sección "Revisión
  V8b"), estado **sin revisar**.

### D8-5.11 — barrido de traducciones
- Paridad de claves es/en: prueba que lista las claves faltantes en cada sentido; hoy 0.
- Literales QML visibles fuera del catálogo: barrido completo; los que quedan son códigos
  internos, fuentes, formatos, motivos que van a la bitácora y el eslogan de marca (lista
  explícita `_LITERALES_PERMITIDOS` en la prueba, por texto).
- Python de la UI (`ui_qml/**/*.py`): prueba que falla si arma un texto visible fuera del
  catálogo (lista explícita `_PY_PERMITIDOS`).
- Motivo de estado seguro detenido (CIC-10): el backend lo manda en español; ahora
  `alarmas_i18n.clave_motivo_bloqueo()` lo reconoce por su comienzo y la UI lo muestra con
  `estado_seguro_motivos.<clave>` en el idioma vigente (si no lo reconoce, el texto tal cual).
  La decisión de mostrar el botón de sondas (antes `indexOf("Principal")` en QML) pasó a
  `ui_bridge` (`estadoSeguroBloqueoPorSonda`), calculada sobre el texto crudo en español, como
  antes. La plantilla de la alarma en inglés también recibe el motivo traducido.

## Pruebas nuevas

- `tests/test_v8b_textos.py`: paridad de claves, abreviaturas conocidas, punto de abreviatura
  en medio del texto, anglicismos en es, español en en, elide y maximumLineCount en QML,
  literales QML, textos visibles en el Python de la UI, nombre visible de todo parámetro de
  programa, citas «…» de las descripciones, motivos de CIC-10 (clave en ambos idiomas,
  reconocimiento, no mezcla en inglés, entrega por `ui_bridge`).
- `tests/test_v8b_truncado_qml.py`: sin textos truncados en español a 1024 px, por pantalla.
- `tests/v8b_capturas.py`: script de capturas es/en (no es prueba de pytest).

## Resultado de las pruebas

Con `PYTHONPATH=<worktree>/src` (`autoclave.__file__` =
`C:/Users/tecni/Documents/codigo_autoclave/.claude/worktrees/agent-a4e1a61384f94e185/src/autoclave/__init__.py`, comprobado).

Pruebas relevantes, **un proceso de pytest por archivo**: los 72 archivos de prueba que citan
algún QML tocado, más i18n, truncado (I4 y V8b), alarmas, protocolo de fallo, calentamiento y
descompresión: **1200 passed, 0 failed** (`docs/informes/tanda8/suites/v8b_relevantes.log`).
Entre ellos: `test_v8b_textos.py` 19 passed, `test_v8b_truncado_qml.py` 22 passed,
`test_i18n.py` 63 passed, `test_i18n_linea_base.py` 5 passed, `test_i4_truncado_qml.py` 22 passed.

Hallazgos de esta corrida, ya corregidos:
- `test_menu_principal_componentes_qml.py`: el programa largo del último ciclo desbordaba su
  tarjeta. Causa: `Escala.fuenteMinima` (18 px) era mayor que la letra del texto (17 px), así
  que `fontSizeMode` no podía reducir nada. Se bajó el mínimo a 14 px.
- `test_opciones_qml.py`: exigía exactamente dos líneas en el cajón para un nombre de prueba
  muy largo; sin el recorte (D8-5.4) ocupa tres y la fila crece. La prueba ahora exige "dos o
  más líneas y el texto cabe en la fila".

Nota: corriendo esos 72 archivos en UN solo proceso, pytest se cae (código 127) en
`test_c1a_teclado_pyside.py::test_tecla_a_escala_uno_mide_96x88`, al mezclar pruebas QML
(QGuiApplication) con widgets PySide (QApplication). Aislada pasa (19 passed) en esta rama y
en el repositorio principal: ajeno a V8b; en la suite completa el orden es otro.

La suite completa NO se corrió (orden de la sesión principal para esta continuación).

## Capturas

`docs/informes/tanda8/capturas/v8b/V8b_<es|en>_<pantalla>.png` (22 pantallas del banco de I4
por idioma, 1024x1638, sin backend) y `resumen.json` con los textos recortados o desbordados
por pantalla (todos vacíos).
Regeneradas con el QML final (44 capturas, 22 por idioma). Limitación: el banco carga cada
pantalla sola, sin backend ni iconos, así que algunas subpantallas de Opciones se ven casi
vacías (p. ej. Parámetros del ciclo muestra solo su lista); sirven para revisar textos, no el
aspecto final. Faltan capturas con datos reales (pendiente).

## DECISIONES SIN CONFIRMAR

1. Excepciones a D8-5.5 en `es.json`: "software", "firmware", "hardware" (sin equivalente de
   uso común), siglas (USB, PDF, CSV, PWM, SMTP, IP, PC, E/S), nombres propios y marcas
   (SPK-SAT, F0, Bowie & Dick, Especifika).
2. Pie del arranque "Software v<versión>": notación de versión igual en es y en (literal
   permitido en QML).
3. Mínimo legible para la letra que se reduce: 14 px de diseño (`Escala.fuenteMinima`). Se
   empezó con 18, pero los textos del equipo van de 17 a 24 px y con 18 casi ninguno podía
   reducirse. Los textos que pueden reducirse usan `fontSizeMode: Text.HorizontalFit`.
4. Eco del teclado alfanumérico: se mantiene ElideLeft (muestra lo último tecleado); no es un
   texto del sistema sino lo que escribe el usuario.
5. Nombres visibles de los 95 parámetros de programa (sección `parametros`) redactados por
   Claude, en especial "Margen de recuperación por presión" / "Margen de falla…" de
   Esterilización: requieren revisión técnica de Cristian.
6. `estado_seguro_motivos.*` (motivos de CIC-10 en ambos idiomas): textos de seguridad,
   requieren revisión explícita.
7. Los motivos de fallo de las fases siguen saliendo en español desde el backend (van al
   registro y al ticket); solo se cambió la palabra "Timeout". Traducir todos los motivos de
   fallo por clave quedaría para otra etapa.

## PREGUNTAS PARA CRISTIAN

- ¿Se aceptan las excepciones de la decisión 1, o "software/firmware" deben ir de otra forma?
- ¿Revisar el glosario de nombres de parámetros (`parametros.*`) antes de la entrega?

## Pendientes

- Repasar los textos que agreguen R8, E1, V8a, L8 y D8 cuando se una `tanda-8` en esta rama
  (las pruebas genéricas los señalarán).
- Revisión de Cristian de `revision_traducciones.md` (todo "sin revisar").
- Capturas con backend y datos reales (las actuales son del banco sin backend).
- Suite completa no corrida en esta continuación (la sesión principal la corre al unir).
- Los motivos de fallo de las fases y el ticket siguen en español aunque la interfaz esté en
  inglés (decisión 7).
- U-2 (rev. 3.1) decía "dos líneas" en el cajón de Opciones; con D8-5.4 puede ser más. Avisar
  a Cristian para actualizar la planeación.

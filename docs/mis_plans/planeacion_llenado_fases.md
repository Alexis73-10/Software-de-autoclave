# Planeación: llenado tipo líquido en la barra de fases (pantalla de ciclo en curso)

Estado: ETAPA 1 (lectura y planeación). Sin código. Sin decisiones de Cristian todavía (ver «Decisiones», vacía).
Fecha: 31-oct-2026. Prefijo de hallazgos: LLF-NN. Prefijo de preguntas: P-NN.

## 0. Nota de rama

La rama actual es `automatizacion-instalacion`, que tiene muchos cambios sin confirmar ajenos a esta tanda (perfil, secretos, ticket, PDF, QML de instalación...). **La rama de trabajo de esta tanda debe salir de `dev`** (p. ej. `llenado-fases`), no de la rama actual. Ninguno de los archivos de esta tanda debe arrastrar cambios de `automatizacion-instalacion`. Antes de crear la rama hay que confirmar que `dev` está limpio y al día. Al terminar, se une a `dev` (etapa K) como las tandas anteriores, solo cuando Cristian confirme visualmente el resultado.

## 1. Alcance y supuestos

Alcance:
- Cada círculo de fase se llena «como agua» en proporción al avance de la fase, con la superficie viva (onda).
- Cuando el tiempo de la fase se recalcula, el círculo se vacía parcialmente con una transición suave.
- En el cambio de fase, el conector se llena de izquierda a derecha y un chorro cae dentro del círculo siguiente mientras su nivel esté bajo la mitad.
- El backend publica la fracción por fase y la UI solo dibuja.

Fuera de alcance: lógica de fases, tiempos de proceso, `restante_s` total, gráfica, panel de fin de ciclo, PantallaPreciclo.

Supuestos:
- S1. La UI es un proceso aparte del backend de control: el cliente consulta por HTTP (`ui_qml/bridge/progreso_ciclo.py:77,80`). Una animación en la UI no puede retrasar `ControlLoop`.
- S2. No existe tema oscuro en el proyecto. `Tema/Colores.qml` solo tiene «Fondos oscuros (arranque / chrome)» (línea 7). La barra usa una paleta local fija (`BarraFases.qml:48-55`). El requisito «tema claro/oscuro» se evalúa solo como compatibilidad futura.
- S3. Lienzo de diseño 1200×1920 (`Tema/Escala.qml:8-9`). La barra está en px del mockup por `escala` (`BarraFases.qml:16,24`).
- S4. Qt/PySide6 6.11.1 (`requirements.lock.txt:34` PySide6, `:36` Addons, `:37` Essentials, `:49` shiboken6).

## 2. Lectura del código actual

### 2.1 `src/autoclave/ui_qml/qml/Componentes/BarraFases.qml`
- Propiedades: `escala` (l. 16) y `fases` (l. 22), una lista `[{fase, estado}]` con estados completada/activa/pendiente/fallida/interrumpida (l. 17-21).
- `resaltada()` trata activa y completada igual: «TODO-DISEÑO (plan 14.8)» (l. 29-31). El plan lo confirma en `docs/mis_plans/planeacion_pantalla_ciclo_en_curso.md:258`.
- `colorTerminacion()`: fallida = `Colores.alarmaAlta`, interrumpida = `Colores.advertencia`, si no transparente (l. 33-37). Los valores son `#EE0000` (`Colores.qml:31`) y `#FF9933` (`Colores.qml:27`).
- Geometría (l. 39-46): `xPrimera` 128, `xUltima` 1068, `diametro` 85; `centroX(i)` reparte las fases que llegan.
- Paleta local (l. 48-55): pendiente `#CCCCCC`, activa `#0B7A80`→`#003A9C`, conector `#003B9B`→`#07BDFF`, etiqueta `#3C3C3C`.
- Conectores (l. 60-79): `Rectangle` en `y = m(477)`, alto `m(7)`, desde el borde derecho del círculo i hasta el izquierdo del i+1 (l. 66-69). **Se pintan azules si la fase de la izquierda está activa o completada** (l. 65): el conector que sale de la fase activa ya se ve lleno.
- Círculos (l. 81-120): `Rectangle` con `objectName: "circuloFase_" + fase` (l. 91), en `y = m(480 - 42.5)`, `radius = width/2` (l. 93-94). El color es el de terminación o gris (l. 95), con degradado horizontal si está resaltado (l. 96-102). El ícono `Image` blanco de 48 px es el **primer hijo** (l. 103-108). El nombre va debajo, en la línea base 550 (l. 110-118).
- Importa `QtQuick.Effects` (l. 3) sin usarlo.

### 2.2 `src/autoclave/ui_qml/qml/Pantallas/PantallaCicloEnCurso.qml`
- `property var fases: progreso?.fases ?? []` (l. 66). Tiempos solo con datos vigentes (l. 69-70).
- Barra de fases: `BarraFases { anchors.fill: parent; escala: raiz.m(1); fases: raiz.fases }` (l. 467-472).
- Precedente útil: la barra de progreso global usa `fraccionProgreso = t/(t+r)` acotada a [0,1] (l. 169-174) y queda vacía sin estimación (l. 744-762).

### 2.3 `src/autoclave/ui_qml/domain/ciclo_en_curso.py`
- Importa `FASES_UI` del núcleo (l. 15). Estados válidos en `_ESTADOS_FASE` (l. 19).
- `normalizar_progreso` (l. 96-139): por fase solo conserva `fase`, `estado` (desconocido = "pendiente") y `duracion_s` (l. 104-113). **Un campo nuevo del backend se descarta aquí si no se agrega.**

### 2.4 `src/autoclave/core/runtime/progreso_ciclo.py`
- `EXTENSION_MIN = 5` y `_EXTENSION_S` (l. 21-24).
- `restante_fase(e, d_ref)` (l. 115-119): dentro de la referencia da `d_ref - e`; después, `300 - ((e - d_ref) % 300)`, un diente de sierra que se renueva cada 5 min.
- `tiempo_restante` (l. 127-149): la esterilización usa su restante propio (`restante_activa`) si es válido (l. 143-146).
- `armar_progreso` (l. 152-222): `e_activa = transcurrido - inicio_activa` (l. 175). Por fase arma `{fase, estado, duracion_s}` (l. 177-184). Con FC-06, la fase de terminación queda fallida/interrumpida, las anteriores completadas y las siguientes pendientes con `duracion_s = None` (l. 186-204). `restante_s` es None si el ciclo terminó sin éxito (l. 206-212).
- `fase_terminacion` (l. 53-74): con `FALLO_<FASE>` es esa fase; si no, la última registrada.

### 2.5 Ruta `GET /cycle/current/progress` (`src/autoclave/backend/rutas/ciclo.py:185-227`)
- Las fases aplicables salen de la copia del programa en ejecución (l. 198-199).
- `referencias` = `db.get_duraciones_referencia(tipo)` traducidas a fase UI y sumadas (l. 204-208). **Se usan solo para el restante; no se publican por fase.**
- `exposicion_restante_s` de `context.estado` (l. 213-215) se pasa a `armar_progreso` (l. 216-217).
- `db_manager.get_duraciones_referencia` (`services/domain/logging/db_manager.py:1337-1355`): toma el último ciclo COMPLETADO del mismo `tipo_ciclo` que tenga fases; si no hay, devuelve `{}`.
- El simulador llama igual: `simulador/servidor.py:88` (`_referencias`) y `:186` (`armar_progreso(...)` posicional).

### 2.6 Esterilización (`state_machine/cycle_phases/esterilizacion.py`)
- `tiempo_seg = (get_param("esterilizacion","tiempo_esterilizacion") or 3.5) * 60` (l. 641). Se guarda en `self._tiempo_seg` al inicializar (l. 667-669).
- `_publicar_restante` (l. 284-296): detenida (excursión confirmada) publica el total; si no, `max(0, timer_fin - now)`. Se pone en None en FALLO (l. 324) y al salir (l. 850, 861).
- **El total de exposición no se publica**; es un atributo privado.

### 2.7 Puente QML (`src/autoclave/ui_qml/bridge/progreso_ciclo.py`)
- Sondea cada `INTERVALO_MS = 1000` (l. 23), solo con `activo` (pantalla visible) (l. 113-123).
- `progresoChanged` se emite solo si cambia lo normalizado (l. 96-99). `fases` se entrega tal cual (l. 168-170).
- `ciclo_db_id` existe en lo normalizado (`ciclo_en_curso.py:125`) pero **no se expone como propiedad** a QML.

### 2.8 Arneses
- `Pruebas/PruebaCicloEnCurso.qml`: ventana de 600×960 (l. 13) con `fases` fijas de ejemplo (l. 83-90). No tiene animación ni control del avance.
- `Pruebas/PruebaCicloEnCursoBackend.qml`: 600×960 (l. 11), conectado a `progreso` real (l. 36-41).
- `Pruebas/PruebaFinDeCiclo.qml`: 800×1280 (l. 15), `property var fases` (l. 24) pasada a la pantalla (l. 127). La usa `tests/banco/t21_capturas_fin_ciclo.py` (`grabWindow`, l. 134).
- `Tema/Movimiento.qml`: duraciones centralizadas (l. 10-12) e `instantaneo` con la plataforma offscreen (l. 16).

### 2.9 Módulos QML ya usados
- `QtQuick.Shapes` con `Shape.CurveRenderer`: `Pantallas/MenuPrincipal.qml:3,146-149`, `Componentes/GraficaCiclo.qml:4,427-432`, `Pantallas/PantallaPreciclo.qml:3,792-796`.
- `QtQuick.Effects`/`MultiEffect`: varios (p. ej. `GraficaCiclo.qml:409`, `PantallaCicloEnCurso.qml:276`).
- No se usan `Canvas`, `ShaderEffect` ni shaders `.qsb`. No hay configuración de RHI (`QSG_RHI*`/`QT_QUICK_BACKEND`) en `src/`.
- `Componentes/IconoColor.qml:7-8`: «MultiEffect no se dibuja con QT_QPA_PLATFORM=offscreen».

## 3. Fuente de la fracción de llenado

### 3.1 Regla
**El backend decide la fracción; la UI solo la dibuja** (y la acota de forma defensiva al normalizar). Se agregan por fase en `armar_progreso`:
- `fraccion`: número en [0, 1] o `null` (no estimable).
- `referencia_s`: la referencia usada (número o `null`), para trazabilidad y diagnóstico. No se dibuja.

El cálculo vive en una función pura nueva de `core/runtime/progreso_ciclo.py` (p. ej. `fraccion_fase(...)`), probada aparte. La constante del tope (`TOPE_FRACCION_ACTIVA`, §4) también vive ahí y la importa `ui_qml/domain/ciclo_en_curso.py`, como ya importa `FASES_UI` (l. 15).

### 3.2 Comportamiento por caso (propuesta; se confirma con P-01..P-04)

| Caso | `fraccion` | Nota |
|---|---|---|
| Pendiente | 0.0 | Sin líquido, círculo gris. |
| Activa con referencia, dentro de ella | `e / (e + restante_fase(e, ref))` = `e/ref`, acotada a `TOPE` | Crece linealmente. |
| Activa que excede su referencia | `e / (e + restante_fase)`, acotada a `TOPE` | Al renovarse el bloque de 5 min (`progreso_ciclo.py:119`) el restante salta de ~0 a 300 s y la fracción baja. Es el «vaciado parcial» pedido. Ejemplo con ref 600 s: en e = 600 → 0,667; justo antes de 900 → tope 0,90; en 900 → 900/1200 = 0,75. |
| Activa sin referencia (primer ciclo del programa, o fase nueva en el programa) | `null` | La UI muestra un nivel fijo «indeterminado» con onda y sin avance (P-02). Coherente con `restante_s = null` y con la barra global vacía (`PantallaCicloEnCurso.qml:744-745`). |
| Esterilización activa | `1 - restante_exp / total_exp`, acotada a [0, TOPE] | `restante_exp` = `estado.exposicion_restante_s`; `total_exp` = total de exposición (ver LLF-03, «requiere arquitecto»). Una excursión confirmada publica restante = total (`esterilizacion.py:290-291`), así que la fracción baja a 0 y el círculo se vacía hasta el fondo. Con F0 activo y la exposición cumplida, el restante es 0 pero la fase sigue: el tope la deja en 0,90. `restante_exp` null (primer tick) da 0,0. |
| Completada | 1.0 | Solo con `estado == "completada"`. |
| Fallida / interrumpida | `null` (recomendado) | La UI pinta el círculo sólido con el color de terminación, como hoy (P-06). Alternativa: congelar el último nivel en ese color. |
| Vacío (pulsos) y calentamiento (por condición) | Igual que «activa con referencia» (temporal) | Sin duración fija, la referencia histórica es la mejor estimación disponible. Usar el conteo de pulsos de PREVACIO exigiría publicar estado de una fase de control: fuera de alcance (P-04). |
| Precalentamiento y secado (tiempo de programa) | Temporal por referencia (v1) | Opción futura: usar el tiempo del programa como en esterilización (P-04). |

Monotonía: dentro de la referencia la fracción solo sube. Solo baja en (a) la renovación del bloque de 5 min, (b) el reinicio de la exposición y (c) el corrimiento del fin de exposición sin datos (SAF-05, tanda 16). La UI anima toda bajada con la transición de vaciado (§7).

## 4. Regla de no inducir a error

**Regla:** un círculo nunca se ve lleno mientras el backend no diga `estado == "completada"`. Se aplica en tres capas:
1. Backend: `fraccion <= TOPE_FRACCION_ACTIVA` para todo estado distinto de completada.
2. Dominio UI (`normalizar_progreso`): fracción no numérica, no finita o fuera de [0,1] → `null`; activa por encima del tope → tope; completada → 1,0 aunque llegue otra cosa; pendiente → 0.
3. QML: el nivel visual de un círculo no completado se acota otra vez a `TOPE` (la onda no debe tocar el tope del círculo).

**Tope propuesto: 0,90.** Justificación:
- El círculo mide 85 px de mockup. Con 0,90 queda una franja vacía de ~8,5 px más la amplitud de la onda (~2 px), que se distingue a 1024 px de ancho (≈ 7 px reales). Con 0,95 la franja (~4 px de mockup, ~3,5 px reales) se confunde con el borde antialias y la cresta de la onda.
- Los casos en que la fracción «natural» llega a 1 sin estar completada son reales: el final de cada bloque de extensión (`restante_fase` → 0) y la esterilización con F0 pendiente. Además, la duración real nunca coincide con la de referencia.
- El tope solo afecta al último 10 % de una fase, donde la estimación es menos fiable.

Severidad del hallazgo sin esta regla: ALTA (LLF-01). Un círculo lleno se lee como «fase terminada». En esterilización el operador podría creer cumplida la exposición. El resultado del ciclo y la apertura siguen bajo control del backend (panel de fin de ciclo, `camara_segura`, interlock), así que el daño directo es bajo, pero es información engañosa en la fase que esteriliza.

## 5. Técnica de dibujo (Qt 6.11 / PySide6 6.11.1)

### 5.1 Comparación

| Criterio | QtQuick.Shapes (región analítica) | Canvas (2D) | ShaderEffect / MultiEffect con máscara |
|---|---|---|---|
| Costo en la PC de la estación | Bajo: una ruta de ~30 segmentos por cuadro, solo en el círculo activo. Con CurveRenderer se triangula en CPU al cambiar la ruta. | Medio-alto: rasteriza en CPU cada cuadro y sube la textura. | Bajo en GPU. Con WARP (sin GPU) es más caro. |
| Nitidez a distintas `escala` | Vectorial, nítida; CurveRenderer da antialias analítico (ya se usa en `GraficaCiclo.qml:432`). | Hay que redimensionar el lienzo con `escala`; riesgo de borrosidad. | Nítida si la máscara se genera a la resolución real. |
| Degradado actual #0B7A80→#003A9C | `ShapePath.fillGradient` (LinearGradient horizontal): idéntico. | `createLinearGradient`: idéntico. | Hay que pasarlo al shader o como fuente. |
| Recorte circular | Sin máscara: la región del líquido se construye como intersección analítica (arco inferior del círculo + borde superior ondulado entre las dos intersecciones). | `clip()` con arco: trivial. | Máscara (la que `IconoColor.qml` usa). |
| Pruebas offscreen | Sí se dibuja con la plataforma offscreen (las pruebas actuales de Shapes lo muestran). | Sí. | **No se dibuja offscreen** (`IconoColor.qml:7-8`): pruebas y capturas sin el líquido. |
| Empaquetado | Ya incluido (Shapes en uso). | Ya en QtQuick. | `ShaderEffect` propio exige `.qsb` (herramienta `qsb`, archivos nuevos en los 3 `.spec`). |
| Tema claro/oscuro | Colores por propiedades (tokens futuros). | Igual. | Igual. |

### 5.2 Recomendación
**QtQuick.Shapes con `Shape.CurveRenderer` y la región del líquido calculada analíticamente** (sin máscara ni shader). Motivos:
- Ya está en el proyecto y empaquetado.
- Es vectorial y nítido a cualquier `escala`, y conserva el degradado.
- Se puede probar offscreen; las capturas existentes usan esa misma ruta.
- El costo queda acotado: solo el círculo activo anima la onda; los completados son estáticos (§6).

El conector y el chorro también se hacen con `Rectangle`/`Shape` simples. Plan B, si CurveRenderer resulta caro con una ruta que cambia cada cuadro (se mide en el paso 7): `Shape.GeometryRenderer` con `layer.samples: 4` solo en el círculo activo.

Riesgo de verificación: no se conocen la GPU ni el controlador de la PC de la estación. Sin configuración de RHI, Qt usa D3D11 en Windows y WARP si no hay GPU. Hay que medir la CPU del proceso de UI en el banco (LLF-08).

## 6. Apariencia: activa frente a completada (cierra TODO-DISEÑO 14.8)

- **Pendiente:** círculo gris `#CCCCCC`, sin líquido, ícono blanco (como hoy).
- **Activa:** fondo gris y líquido con el degradado #0B7A80→#003A9C hasta `fraccion`; superficie con onda animada continua (período ~2,5 s, amplitud ~2 px de mockup); ícono blanco encima.
- **Completada:** lleno al 100 %, mismo degradado, **sin onda**, quieto. Se distingue de la activa por el movimiento y el nivel (la activa nunca supera 0,90). Opcional (P-07): un aro fino exterior más oscuro o una marca de verificación pequeña.
- **Fallida / interrumpida:** sólido en `Colores.alarmaAlta` / `Colores.advertencia`, sin onda, ícono blanco. Así se conserva FC-06 y lo que verifica `tests/test_t21_panel_fin_ciclo_qml.py:584-591`.
- **Sin referencia:** nivel fijo `nivelIndeterminado` (propuesta 0,25) con onda, sin subir (P-02).

## 7. Coreografía del cambio de fase

Estados de entrada: dos respuestas sucesivas donde la fase i pasa de activa a completada y la i+1 de pendiente a activa.

Secuencia propuesta (duraciones en `Tema/Movimiento.qml`, ajustables en un solo sitio; total ≈ 1,6 s, P-06):
1. **Cierre del círculo i** (300 ms, OutCubic): el nivel sube de su valor (≤ 0,90) a 1,0 y la onda se apaga con la amplitud bajando a 0.
2. **Conector i→i+1** (600 ms, InOutQuad): un `Rectangle` con `clip` y degradado #003B9B→#07BDFF crece de izquierda a derecha.
3. **Chorro** (al llegar a la boca del conector, borde izquierdo del círculo i+1 en y ≈ 480): un hilo curvo (`Shape`, ~4 px de mockup) cae del borde de la boca hasta la superficie del líquido, recortado al interior del círculo. Solo existe mientras el nivel de i+1 sea menor que 0,5 (la boca está a media altura: centro del conector y = 477 + 3,5 ≈ 480 = centro del círculo).
4. **Nivel de i+1** (700 ms, desde 0, a la vez que el chorro): sube a la fracción objetivo. Si el objetivo es ≥ 0,5, el chorro se corta al cruzar 0,5 y el resto sube sin chorro. La onda arranca con la subida.

Dos lecturas posibles del pedido 3 (P-04b): (A) el chorro sigue cayendo, delgado, durante toda la fase activa mientras el nivel esté bajo la mitad; (B) el chorro solo aparece en la transición. Recomendación: **A**, por coherencia física (el conector queda lleno y es la fuente del líquido), con un hilo fino y sin salpicadura para no distraer. La primera fase no tiene conector de entrada, así que nunca tiene chorro.

Casos borde:
- **Progreso nuevo a mitad de animación:** la secuencia en curso se completa al instante (`complete()`) y arranca la nueva. Los niveles siempre animan hacia el último valor recibido; nunca se encola más de una transición.
- **Varias fases saltadas de golpe** (p. ej. se perdieron sondeos o una fase duró menos de 1 s): sin coreografía por fase. Las intermedias pasan a completadas y sus conectores a llenos en una sola animación corta (≤ 400 ms). Solo la última transición (hacia la nueva activa) se coreografía.
- **Primera fase:** sin conector de entrada ni chorro; el nivel sube desde 0 con la onda.
- **Fin en fallo o cancelación:** se detienen todas las animaciones, se apaga la onda y el círculo de terminación pasa a color sólido (fundido de 200 ms). Los conectores de la izquierda quedan como completados y no se dibuja ningún conector de salida.
- **Fin exitoso:** el último círculo hace el paso 1 (sube a 1,0) sin conector de salida.
- **Regreso a la pantalla con el ciclo avanzado:** el puente deja de sondear sin pantalla (`bridge/progreso_ciclo.py:118-122`). Con la primera respuesta tras activarse, la barra fija estados y niveles **sin animación** (bandera `_primeraCarga`) y luego arranca la onda. Lo mismo al cambiar `ciclo_db_id` (hay que exponerlo, LLF-07).
- **Suavizado del nivel:** los datos llegan cada 1 s (`bridge/progreso_ciclo.py:23`). El nivel visual anima con `Behavior` lineal de ~950 ms hacia el objetivo cuando sube y con OutCubic de ~1200 ms cuando baja (recálculo). Sin extrapolación propia: la UI no estima tiempos.
- **Sin conexión:** `fases` conserva los últimos datos. La onda puede seguir, pero el nivel no avanza. Propuesta: detener la onda cuando `datosVigentes` es falso, para que no parezca «vivo» con datos congelados (P-08).
- **Pruebas offscreen:** con `Movimiento.instantaneo` (`Tema/Movimiento.qml:16`) todo es inmediato y la onda queda con fase fija, para que las pruebas sean deterministas.

## 8. Impacto en pruebas

### 8.1 Pruebas existentes afectadas
- `tests/test_progreso_ciclo.py:203-208` y `:228`: comparan diccionarios exactos por fase. Hay que agregar `fraccion` y `referencia_s` o comparar por claves.
- `tests/test_ciclo_en_curso_dominio.py:116`, `:128-130`: igualdad exacta de la fase normalizada.
- `tests/test_t21_panel_fin_ciclo_qml.py:565-591`: depende de que `circuloFase_<f>` tenga `color` y `gradient` y de que `childItems()[0]` sea el `Image` del ícono. **Hay que conservar esa interfaz** (el `objectName` en un `Rectangle` base con `color`/`gradient` y el ícono como primer hijo) o actualizar la prueba con la nueva estructura (LLF-04).
- Sin cambio esperado, por revisar: `tests/test_backend_ciclo_en_curso_endpoints.py:97-102`, `tests/test_t21_fin_de_ciclo_backend.py:43-75,239-279`, `tests/test_t21_fin_de_ciclo_ui.py:24-48`, `tests/test_progreso_ciclo_bridge.py:65-66`, `tests/test_t12_c13_excursion_referencia.py:248-268`, `tests/test_i18n_linea_base.py:125`.
- `GraficaCiclo.qml` recibe `tiempos: raiz.fases` (`PantallaCicloEnCurso.qml:590`; usa `duracion_s`, `GraficaCiclo.qml:642,662`): una clave extra no le afecta.
- `_suites_t11/` es una copia antigua y no se toca.

### 8.2 Pruebas nuevas
- **Backend puro** (`tests/test_llf_fraccion_fases.py`, `req("LLF-...")`): pendiente 0; dentro de la referencia lineal; en e = ref; diente de sierra en las extensiones (baja en la renovación); tope en 0,90 en todos los no completados; sin referencia null; esterilización con restante, detenida (0), restante 0 con F0 pendiente (tope), restante None (0); completada 1; fallida/interrumpida según la decisión; `referencia_s` publicada.
- **Ruta**: `GET /cycle/current/progress` publica `fraccion`/`referencia_s` (extender `test_backend_ciclo_en_curso_endpoints.py`) y el total de exposición según A-1.
- **Dominio UI**: acota y descarta valores malos (str, NaN, inf, −0,1, 1,5); completada fuerza 1; activa acotada al tope.
- **QML offscreen** (`tests/test_llf_barra_fases_qml.py`, subproceso como `test_t21_panel_fin_ciclo_qml.py`):
  - nivel visual = fracción (dentro de tolerancia);
  - un no completado nunca supera el tope aunque la entrada diga 1,0;
  - completada sin onda;
  - conector de la fase activa gris y de la completada lleno;
  - chorro visible solo con el nivel bajo 0,5 y nunca en la primera fase;
  - primera carga sin animación;
  - salto de varias fases;
  - fallo a mitad de la secuencia;
  - sin avisos QML.
- **Arnés**: `Pruebas/PruebaCicloEnCurso.qml` con un modo de demostración que avanza la fracción y dispara cambios de fase, recálculo y fallo con teclas o un temporizador, para revisarlo a ojo y para el mockup (P-12).
- **Capturas**: nuevo `tests/banco/llf_capturas_barra_fases.py` (patrón de `t21_capturas_fin_ciclo.py:134`), en ventana de 1024 px de ancho (1024×1638) y en la base 1200×1920. Escenarios: pendiente, activa 0,1/0,45/0,9, completada, sin referencia, fallida, interrumpida, chorro a media transición, recálculo. Con plataforma real (no offscreen) para ver el antialias.

## 9. Impacto normativo (IEC 62304 Clase C / ISO 14971)

- El cambio toca un elemento de software de Clase C (UI de la pantalla de ciclo) y un módulo puro del backend (`progreso_ciclo.py`). **No toca actuadores, fallas, temporizadores de proceso ni el resultado del ciclo.** El nuevo campo es solo de presentación.
- Si se decide publicar el total de exposición desde la fase (A-1, opción b), se toca `esterilizacion.py` (lógica de control): un cambio de una línea que solo publica estado, pero **pasa por el revisor** de todos modos.
- Hace falta una solicitud de cambio, análisis de riesgo y verificación.
- **Registro de riesgos** (`docs/riesgos/registro_riesgos.md`, mismo formato de 6 columnas que las secciones recientes, p. ej. l. 235-237): nueva sección «Llenado de la barra de fases (fecha)» con **HAZ-LLF-01** (propuesto, BAJA):
  - Peligro: un círculo de fase lleno se lee como fase cumplida (en especial la esterilización) cuando el backend no la dio por completada, o el nivel se lee como tiempo de exposición garantizado.
  - Daño posible: decisión equivocada del operador sobre la carga (p. ej. dar por cumplida la exposición).
  - Control: tope 0,90 en tres capas, lleno solo con «completada», el resultado lo da solo el panel de fin de ciclo (FC-01), interlock y `camara_segura` independientes de la UI.
  - Residual: BAJO.
  - Verificación: las pruebas de §8.2.
- **Matriz de trazabilidad** (`docs/riesgos/matriz_trazabilidad.md`, última fila REQ-35 en la l. 41): nueva fila **REQ-36** «La barra de fases nunca muestra lleno un círculo cuyo estado no sea completada», con fuente en este documento, el riesgo HAZ-LLF-01 y las pruebas de §8.2.
- **SOUP**: sin módulo nuevo (Shapes ya está en PySide6 6.11.1, ya en `docs/riesgos/lista_soup.md`). Si se eligiera ShaderEffect, haría falta `qsb` y revisar los `.spec`; no se recomienda.
- CLAUDE.md: una sección corta al cierre (campo `fraccion`, tope y ubicación de la constante).

## 10. Hallazgos

| ID | Sev. | Hallazgo | Evidencia |
|---|---|---|---|
| LLF-01 | ALTA | La fracción ingenua `e/(e+restante)` llega a ~1,0 sin «completada»: al final de cada bloque de 5 min y en esterilización con la exposición cumplida y F0 pendiente. Hace falta el tope del §4. | `progreso_ciclo.py:115-119`; `esterilizacion.py:293` |
| LLF-02 | MEDIA | La referencia por fase no se publica. Sale del último ciclo COMPLETADO del mismo programa, sea cual sea (un ciclo atípico distorsiona todas las fracciones del siguiente). Sin ciclo previo no hay referencia. | `rutas/ciclo.py:204-208`; `db_manager.py:1337-1355` |
| LLF-03 | ALTA | El total de exposición no se publica (`_tiempo_seg` privado). Replicarlo en la ruta con `(get_param(...) or 3.5)*60` puede divergir de la fase (valor por defecto, migraciones). **Requiere arquitecto** (A-1). | `esterilizacion.py:641,667-669,284-296` |
| LLF-04 | MEDIA | La prueba FC-06 depende de la estructura interna del círculo (`color`, `gradient`, `childItems()[0]`). | `tests/test_t21_panel_fin_ciclo_qml.py:571-580` |
| LLF-05 | MEDIA | MultiEffect y ShaderEffect no se dibujan offscreen: si se usan, las pruebas y capturas automáticas no ven el líquido. | `IconoColor.qml:7-8` |
| LLF-06 | MEDIA | El conector de salida de la fase activa ya se pinta azul. Contradice «el conector se llena en el cambio de fase». | `BarraFases.qml:65` |
| LLF-07 | BAJA | QML no tiene `ciclo_db_id` para detectar un ciclo nuevo y reiniciar sin animación; el puente solo expone `fases`. | `bridge/progreso_ciclo.py:168-170`; `ciclo_en_curso.py:125` |
| LLF-08 | MEDIA | Rendimiento sin medir en la PC de la estación (GPU desconocida; sin configuración de RHI, D3D11 o WARP). La onda continua debe medirse en banco (CPU del proceso de UI). El control no se ve afectado (proceso aparte). | sin `QSG_RHI` en `src/` |
| LLF-09 | BAJA | Hay que actualizar las pruebas con igualdad exacta de diccionarios por fase. | `test_progreso_ciclo.py:203-208,228`; `test_ciclo_en_curso_dominio.py:116,128-130` |
| LLF-10 | BAJA | «Completada» sin diseño (TODO-DISEÑO 14.8); esta tanda lo cierra (§6). | `BarraFases.qml:29-31`; `planeacion_pantalla_ciclo_en_curso.md:258` |
| LLF-11 | BAJA | Ícono blanco sobre gris `#CCCCCC` (contraste bajo, ya hoy). Con el líquido parcial el ícono cruza dos fondos. | `BarraFases.qml:103-108` |
| LLF-12 | BAJA | Paleta fija local, no son tokens de `Colores`. No hay tema oscuro: «claro/oscuro» no aplica hoy. Conviene llevar los colores nuevos a propiedades para un futuro tema. | `BarraFases.qml:48-55`; `Colores.qml:7` |
| LLF-13 | BAJA | Sondeo de 1 s: sin suavizado el nivel sube a saltos. Al volver a la pantalla, el nivel salta. | `bridge/progreso_ciclo.py:23,118-122` |
| LLF-14 | BAJA | Vacío por pulsos y calentamiento por condición: la fracción temporal es solo una estimación; puede quedar en el tope un rato largo. | `progreso_ciclo.py:94-112` |
| LLF-15 | BAJA | La fase de terminación sin `FALLO_<FASE>` sale de la última fila registrada (heurística). El color de terminación puede caer en la fase vecina; ya pasa hoy. | `progreso_ciclo.py:53-74` |
| LLF-16 | BAJA | `armar_progreso` se llama de forma posicional desde el simulador. Los parámetros nuevos deben tener valor por defecto. | `simulador/servidor.py:186` |

## 11. Preguntas para Cristian (con recomendación)

- **P-01. ¿Qué representa exactamente el nivel?** Recomendación: la fracción estimada de la fase activa respecto a su duración de referencia (último ciclo exitoso del mismo programa), y en esterilización el tiempo de exposición cumplido. No representa garantía de nada; tope de 0,90 hasta «completada».
- **P-02. ¿Qué hacer sin referencia (primer ciclo del programa)?** Recomendación: nivel fijo bajo (0,25) con onda, sin subir, igual que el restante muestra «—». Alternativa: círculo vacío con onda mínima.
- **P-03. ¿Cuánto se vacía en un recálculo?** Recomendación: hasta el nivel honesto que da la nueva estimación (extensión: p. ej. de 0,90 a 0,75; reinicio de exposición: hasta 0, porque la exposición vuelve a contar desde cero), con transición de ~1,2 s.
- **P-04. ¿Fases con duración de programa?** Recomendación: solo esterilización usa su conteo propio en esta tanda; vacío, calentamiento, precalentamiento, descompresión y secado usan la referencia histórica. Publicar el conteo de pulsos del vacío queda para otra tanda.
- **P-04b. ¿El chorro cae durante toda la fase (mientras el nivel esté bajo la mitad) o solo en la transición?** Recomendación: durante toda la fase, como un hilo fino (lectura A del §7).
- **P-05. ¿El conector muestra algo durante la fase, o solo cambia en el cambio de fase?** Recomendación: gris mientras la fase de la izquierda está activa; se llena solo en el cambio y queda lleno después. (Hoy se ve azul durante la fase activa, LLF-06.)
- **P-06. ¿Duración de la animación de cambio?** Recomendación: ≈ 1,6 s en total (300 + 600 + 700 ms), ajustable en `Tema/Movimiento.qml`.
- **P-07. ¿Colores?** Recomendación: líquido con el degradado actual #0B7A80→#003A9C; completada igual, llena y quieta; fallida e interrumpida sólidas en `alarmaAlta`/`advertencia` y sin líquido. ¿Quiere además un aro o una marca de verificación en la completada?
- **P-08. ¿Se detiene la onda sin conexión con el backend?** Recomendación: sí, para que no parezca vivo con datos congelados.
- **P-09. ¿El tope de 0,90 le parece bien, o prefiere 0,85/0,95?** Recomendación: 0,90 (§4).
- **P-10. ¿La fase fallida/interrumpida conserva el nivel que tenía (en rojo/naranja) o queda sólida?** Recomendación: sólida, como hoy (FC-06).
- **P-11. ¿Aprueba registrar HAZ-LLF-01 y REQ-36?** Recomendación: sí.
- **P-12. ¿Quiere un mockup animado antes de implementar?** Recomendación: sí. El arnés `PruebaCicloEnCurso.qml` con el modo demostración (paso 4a), revisado en el equipo antes del paso 4b, porque la sensación de la onda y del chorro solo se juzga en movimiento.

## 12. Decisiones

Ver `docs/mis_plans/planeacion_llenado_fases_decisiones.md` (respuestas de Cristian a P-01..P-12 y contrato A-1..A-3 cerrado por el arquitecto).

## 13. Decisiones estructurales que requieren arquitecto

- **A-1** (requiere arquitecto): fuente del total de exposición. (a) La ruta lo lee de la copia del programa (`programa_en_ejecucion`, `rutas/ciclo.py:198`) replicando `or 3.5` (riesgo de divergencia). (b) `EsterilizacionFase._publicar_restante` publica también `estado.exposicion_total_s`: toca código de control, una línea, pasa por el revisor. Inclinación del planeador: (b).
- **A-2** (requiere arquitecto): contrato exacto de los campos (`fraccion`, `referencia_s`, nombre y ubicación de `TOPE_FRACCION_ACTIVA`, valor para fallida/interrumpida) y firma de `armar_progreso` con parámetros nuevos por defecto (LLF-16).
- **A-3** (requiere arquitecto): estructura QML. Mantener `BarraFases.qml` como contenedor y extraer `Componentes/CirculoFaseLiquido.qml` y `Componentes/ConectorFase.qml`; conservar o no la interfaz de `circuloFase_<f>` que usa la prueba FC-06; cómo se entrega `ciclo_db_id`/primera carga.

## 14. Plan de implementación

### Conjuntos de archivos (sin solapes)
- **Conjunto A (backend):** `src/autoclave/core/runtime/progreso_ciclo.py`, `src/autoclave/backend/rutas/ciclo.py`, `src/autoclave/state_machine/cycle_phases/esterilizacion.py` (solo si A-1 = b), `tests/test_progreso_ciclo.py`, `tests/test_backend_ciclo_en_curso_endpoints.py`, `tests/test_t12_c13_excursion_referencia.py`, nuevo `tests/test_llf_fraccion_fases.py`.
- **Conjunto B (dominio y puente UI):** `src/autoclave/ui_qml/domain/ciclo_en_curso.py`, `src/autoclave/ui_qml/bridge/progreso_ciclo.py` (exponer `cicloDbId`), `tests/test_ciclo_en_curso_dominio.py`, `tests/test_progreso_ciclo_bridge.py`.
- **Conjunto C (QML):** `src/autoclave/ui_qml/qml/Componentes/BarraFases.qml`, nuevos `Componentes/CirculoFaseLiquido.qml` y `Componentes/ConectorFase.qml` (según A-3), `Tema/Movimiento.qml`, `Pantallas/PantallaCicloEnCurso.qml` (solo pasar `cicloDbId`/`datosVigentes` a la barra), `Pruebas/PruebaCicloEnCurso.qml`, `Pruebas/PruebaFinDeCiclo.qml` (fracciones de ejemplo), `tests/test_t21_panel_fin_ciclo_qml.py`, nuevo `tests/test_llf_barra_fases_qml.py`, nuevo `tests/banco/llf_capturas_barra_fases.py`.
- **Conjunto D (documentación):** `docs/riesgos/registro_riesgos.md`, `docs/riesgos/matriz_trazabilidad.md`, `docs/mis_plans/planeacion_pantalla_ciclo_en_curso.md` (cerrar 14.8), `CLAUDE.md`, informe `docs/informes/llenado_fases/R_informe.md` y `estado.md`.

### Pasos

| # | Paso | Rol | Conjunto | Depende de | Paralelo con | Terminado cuando |
|---|---|---|---|---|---|---|
| 0 | Rama `llenado-fases` desde `dev` limpio | implementador | — | — | — | `git branch --show-current` = `llenado-fases`, base = `dev`, árbol limpio. |
| 1 | Cerrar A-1..A-3 y volcar respuestas de Cristian en «Decisiones» | arquitecto | (doc) | respuestas P-01..P-12 | — | Contrato escrito: campos, tipos, tope, valores por estado, firma, estructura QML. |
| 2 | Fracción y referencia en el backend (+ total de exposición) | implementador | A | 1 | 3, 4a | `pytest tests/test_llf_fraccion_fases.py tests/test_progreso_ciclo.py tests/test_backend_ciclo_en_curso_endpoints.py tests/test_t12_c13_excursion_referencia.py` en verde; ningún no completado > tope. |
| 3 | Normalización y `cicloDbId` en el puente | implementador | B | 1 (importa la constante del paso 2: acordar nombre en 1) | 2, 4a | `pytest tests/test_ciclo_en_curso_dominio.py tests/test_progreso_ciclo_bridge.py` en verde; valores malos descartados; tope aplicado. |
| 4a | Mockup animado en el arnés (si P-12 = sí) | implementador | C | 1 | 2, 3 | Arnés con modo demostración: avance, cambio de fase, recálculo, salto y fallo; Cristian lo aprueba en el equipo. |
| 4b | Barra de fases con líquido, onda, conector y chorro | implementador | C | 4a aprobado, 3 (propiedades del puente) | — | `pytest tests/test_llf_barra_fases_qml.py tests/test_t21_panel_fin_ciclo_qml.py tests/test_pantalla_ciclo_en_curso_qml.py` en verde, sin avisos QML. |
| 5 | Suite completa y capturas a 1024 px y 1200×1920 | probador | — | 2, 3, 4b | — | `pytest tests` sin rojas nuevas respecto a `dev`; capturas de §8.2 guardadas en `docs/informes/llenado_fases/capturas/`. |
| 6 | Revisión de seguridad y de la regla de no inducir a error | revisor | — | 5 | 7 | Informe sin hallazgos ALTOS abiertos; LLF-01 y LLF-03 cerrados; si se tocó `esterilizacion.py`, revisión explícita. |
| 7 | Medición en banco: CPU del proceso de UI con la onda, en la PC de la estación | probador | — | 5 | 6 | CPU media de la UI con ciclo en curso ≤ +5 puntos frente a `dev` (umbral a confirmar); sin saltos visibles. |
| 8 | Documentación normativa y cierre | implementador | D | 6, 7 | — | HAZ-LLF-01 y REQ-36 agregados; 14.8 cerrado; CLAUDE.md al día; informe y `estado.md`; si lo lanza `lanzar_prompt.ps1`, `CERRADO.txt`. |

Paralelismo: tras el paso 1, los conjuntos A, B y C (4a) corren en paralelo, con hasta 3 implementadores. D espera a 6 y 7. Ningún archivo pertenece a dos conjuntos. `PantallaCicloEnCurso.qml` es solo de C.

### Puntos que obligan a pasar por el revisor
- Cualquier cambio en `esterilizacion.py` (A-1 b): es código de control, aunque solo publique estado.
- La regla de tope en las tres capas (LLF-01).
- Que ningún cambio de `progreso_ciclo.py` altere `restante_s`, `resultado`, `fase_terminacion` ni `terminacion` (no regresión de FC-06/FC-13).

### Criterios de aceptación globales
1. Con un ciclo en curso, el círculo activo muestra líquido con onda en proporción a `fraccion` y nunca supera 0,90 sin «completada».
2. Al renovarse un bloque de 5 min o reiniciarse la exposición, el nivel baja con transición suave hasta el valor nuevo.
3. En el cambio de fase, el conector se llena de izquierda a derecha y cae el chorro mientras el nivel del círculo siguiente esté bajo la mitad; de la mitad hacia arriba se llena sin chorro.
4. Completada: llena y quieta. Fallida e interrumpida: sólidas en sus colores (FC-06 intacto).
5. Volver a la pantalla o empezar un ciclo nuevo no reproduce animaciones viejas.
6. Pruebas automáticas en verde, offscreen y deterministas; capturas a 1024 px y 1200×1920 revisadas.
7. CPU de la UI medida en banco dentro del umbral acordado.
8. Riesgo y trazabilidad actualizados.

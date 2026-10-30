# Verificación I18N-26 — impresión periódica del ticket del ciclo

Fecha: 2026-10-08. Rama `dev` (HEAD `8492927`) + directorio de trabajo. Verificación de solo lectura: no se modificó ningún archivo del repositorio (comparado `git status --porcelain` antes y después: idéntico; `data/autoclave.db` sin tocar).

Severidades = propuesta; las valida el responsable técnico.

---

## 1. Método

- El simulador del repositorio (`src/autoclave/simulador/`) es un backend falso para la UI y **no instancia `CycleLogger`** (sin referencias a `CycleLogger`, `DbManager` ni impresora). Por eso se condujo el `CycleLogger` real directamente, como permite la tarea.
- Script temporal fuera del repo (carpeta temporal de la sesión), ejecutado con `PYTHONDONTWRITEBYTECODE=1` y el directorio del repo como cwd (lo exige `resource_path`):
  - `CycleLogger` **real** (`cycle_logger.py`) y `ticket_formatter.py` **real**.
  - `DbManager` **real** sobre un archivo SQLite en `%TEMP%\verif_ticket_*` (no `data/`).
  - `ConfigManager` **real** cargando `global_params.json` (solo lectura): `intervalo_impresion = 60`, `intervalo_imprecion_esterilizacion = 30`.
  - Impresora falsa: guarda cada `enqueue()` con el segundo del ciclo (reloj monotónico simulado) y la fase vigente. Nada sale a impresora ni a puerto serie.
  - Reloj controlado: se reemplazó en memoria el módulo `time` que usa `cycle_logger` por un objeto con `time()` (pared) y `monotonic()` independientes. Tick de 1 s.
- Línea de tiempo simulada (estado global `CICLO`; `fase_ciclo` y `sub_estado_ciclo` escritos a mano, con los pasos reales de `prevacio.py:37-42`):

| Fase | Duración simulada | Subestados |
|---|---|---|
| PRECALENTAMIENTO | 600 s | — |
| PRE_VACIO | 655 s | `""` 10 s, `DECOMPRESION` 30 s, 3 pulsos × (`VACIO_BAJO` 90, `HOLD_BAJO` 30, `APAGANDO_VACIO` 5, `VAPOR_ALTO` 60, `HOLD_ALTO` 20) |
| CALENTAMIENTO | 600 s | — |
| ESTERILIZACION | 210 s (3,5 min) | — |
| DESCOMPRESION | 300 s | — |
| SECADO | 900 s | — |
| COMPLETADO | 10 s, luego estado global → PREPARADO | — |

Limitación: las fases no las produjo la máquina de estados real sino el guion anterior. Solo `prevacio.py` publica `sub_estado_ciclo` (`prevacio.py:72,261,275`; ninguna otra fase lo escribe — `grep "sub_estado_ciclo\s*="`), así que el guion reproduce lo que vería `CycleLogger` en un ciclo real con esas duraciones.

---

## 2. Requisito esperado

Sí hay requisito escrito, aunque incompleto:

| Fuente | Qué dice |
|---|---|
| `docs/superpowers/specs/2026-07-06-printer-realtime-cycle-ticket-design.md:15-17` | `intervalo_impresion` para fases **W/H (warming/heating)**; `intervalo_imprecion_esterilizacion` para fase **S**; "cada cambio de fase fuerza un registro inmediato". |
| `docs/superpowers/plans/2026-07-06-printer-realtime-cycle-ticket.md:5` y `:805` | Cada lectura se imprime según esos dos intervalos "o en cada cambio de fase"; la prueba manual de `:805` solo cubre CALENTAMIENTO/ESTABILIZACION y ESTERILIZACION. |
| `cycle_logger.py:17-21` (comentario del propio módulo) | `W (Warming) → PRECALENTAMIENTO, PRE_VACIO`; `H → CALENTAMIENTO`; `S → ESTERILIZACION`; `E (Exhaust/End) → COMPLETADO, CANCELADO, FALLO, EMERGENCIA`. |
| `docs/mis_plans/planeacion_opciones.md:63-64` | "Tasa de impresión (general)" `intervalo_impresion` 60 s, 10–3600; "Tasa de impresión (esterilización)" `intervalo_impresion_esterilizacion` 30 s (corrige la errata). 0 no permitido. |
| `docs/mis_plans/planeacion_opciones.md:273` | Decisión 5: "intervalo de impresión, ticket y zumbador pasan a `time.monotonic()`". |
| `docs/mis_plans/planeacion_backend_parametros.md:156-161` (§12, OPC-08) | Alcance aprobado incluye `cycle_logger.py:362` (intervalo de impresión) y `:229,375` (`timestamp_rel` del ticket). |
| `CLAUDE.md` (sección "Máquina de estados del ciclo", convención de temporizadores) | Todo temporizador de proceso usa `time.monotonic()`; `time.time()` solo para sellos de registro. |

Vacíos del requisito:
- **DESCOMPRESION y SECADO no tienen intervalo definido en ningún documento.** El spec solo nombra W/H/S; el comentario del módulo pone "E (Exhaust/End)" pero lo asigna a los cierres, no a DESCOMPRESION. La "tasa general" de `planeacion_opciones.md:63` sugiere que aplica a todo lo que no es esterilización, pero no lo dice.
- Ningún documento fija la alineación ni el ancho de columna de la fila del ticket de ciclo. El spec de ticket de arranque fija 48 caracteres por línea en papel de 58 mm (`docs/superpowers/plans/2026-07-02-printer-startup-ticket.md:15`) "con la misma estética que `ticket_formatter.py`".

Origen de la discrepancia: desde el commit que creó el módulo (`e5f6db5`, 2026-05-21) `_FASE_A_CODIGO` ya producía `PH`/`PG`/`PV` mientras `_INTERVALO_PARAM` usaba `W`; nunca coincidieron. `2beb1b1` (2026-08-05) y `410109f` (2026-10-01) solo quitaron ESTABILIZACION y PURGA.

---

## 3. H1 — filas periódicas por fase: **CONFIRMADA**

Salida de la ejecución (segundos del reloj del ciclo):

```
intervalo_impresion = 60 | intervalo_imprecion_esterilizacion = 30
PRECALENTAMIENTO  dur= 600s filas=  1 t=[1]
PRE_VACIO         dur= 655s filas= 17 t=[600, 610, 640, 730, 760, 765, 825, 845, 935, 965, 970, 1030]...
                  deltas=[5, 10, 20, 30, 60, 90]
CALENTAMIENTO     dur= 600s filas= 10 deltas=[60]
ESTERILIZACION    dur= 210s filas=  7 deltas=[30]
DESCOMPRESION     dur= 300s filas=  1 t=[2065]
SECADO            dur= 900s filas=  0 t=[]
COMPLETADO        dur=  10s filas=  1 t=[3265]
(fin)             dur=   0s filas=  1 t=[3275]
```

| Fase | Código | Intervalo configurado (efectivo en código) | Intervalo esperado por requisito | Filas emitidas | Intervalo observado | ¿Coincide? |
|---|---|---|---|---|---|---|
| PRECALENTAMIENTO | `PH` | ninguno (`_INTERVALO_PARAM.get("PH")` → `None`, `cycle_logger.py:357-359`) | 60 s (W) | 1 en 600 s | solo la fila de entrada | **No** |
| PRE_VACIO | `PV` | ninguno | 60 s (W) | 17 en 655 s | 5–90 s, solo en cambios de subestado | **No** (filas solo por subestado; un paso largo, p. ej. `VACIO_BAJO` hasta su timeout, queda sin filas intermedias) |
| CALENTAMIENTO | `H` | 60 s | 60 s | 10 en 600 s | 60 s | Sí |
| ESTERILIZACION | `S` | 30 s | 30 s | 7 en 210 s | 30 s | Sí |
| DESCOMPRESION | `" "` | ninguno | sin requisito | 1 en 300 s | solo la fila de entrada | Sin requisito (no periódica) |
| SECADO | `" "` | ninguno | sin requisito | **0** en 900 s | — | Sin requisito, pero ver abajo |
| COMPLETADO / cierre | `E` | ninguno (por diseño) | — | 2 (`E` al entrar en COMPLETADO y `E` de `_on_fin`) | 10 s entre ambas | Fila `E` duplicada |

Hallazgos adicionales observados en la misma ejecución:
- **SECADO no imprime ni siquiera la fila de entrada.** DESCOMPRESION y SECADO producen el mismo código `" "` (`cycle_logger.py:340`, valor por defecto de `.get`), así que `cambio_fase` (`:347`) es falso en esa transición. En el ticket, los 900 s de secado son invisibles.
- **El código `F` nunca se guarda.** Con cierre `CANCELADO`, `FALLO` o `EMERGENCIA` las lecturas guardadas son `[' ', 'E', 'H', 'PH', 'PV', 'S']`. Esos valores no están en `_FASES_EN_CURSO`, así que `update()` llama directo a `_on_fin()` (`:152-157`), que siempre escribe `"E"` (`:268`). Las entradas `F` de `_FASE_A_CODIGO` (`:53-55`) son código muerto, y un ciclo fallido termina con la misma letra que uno completado.

Texto de las filas (extracto):

```
PH 00:00:01 0040.1 0075.1      (única fila de 10 min de precalentamiento)
PV 00:10:00 0060.5 0020.0
...
PV 00:20:35 0060.3 0020.0
H 00:20:55 0120.2 0200.0
...
S 00:33:55 0135.0 0307.0
  00:34:25 0110.0 0120.0       (DESCOMPRESION, código en blanco; SECADO no aparece)
E 00:54:25 0085.3 0075.0
E 00:54:35 0085.5 0075.4
```

---

## 4. H2 — reloj: **CONFIRMADA**

Lugares del módulo que miden tiempo (`cycle_logger.py`):

| Línea | Reloj | Uso |
|---|---|---|
| `:229` | `time.time()` | `_ciclo_inicio` (base de `timestamp_rel` del ticket) |
| `:362` | `time.time()` | `ahora` para el intervalo de impresión |
| `:375` | `time.time()` | `ahora` en `_registrar_lectura`: `timestamp_rel` y `_ultimo_log` (`:394`) |
| `:252`, `:282`, `:388` | `datetime.now()` | fecha/hora de encabezado, pie y `timestamp_abs` (sellos de registro: uso correcto) |
| `:100`, `:192`, `:236`, `:264`, `:303` | `reloj_mono` (`time.monotonic` por defecto) | gráfica y tramos de fase (pantalla), no el ticket |

Efecto medido (salto solo del reloj de pared; el monotónico sigue normal):

| Caso | Efecto observado |
|---|---|
| Sin salto | CALENTAMIENTO 10 filas cada 60 s; ESTERILIZACION 7 filas cada 30 s |
| −3600 s en CALENTAMIENTO (t=1455) | CALENTAMIENTO: **4 filas en vez de 10**; las 6 restantes se omiten (`ahora − _ultimo_log` negativo). ESTERILIZACION recupera la cadencia (la fila de cambio de fase reinicia `_ultimo_log`), pero **todas sus filas, y las siguientes, imprimen `00:00:00`** (`elapsed` negativo, recortado a 0 por `_fmt_elapsed`, `:420`) |
| −3600 s en ESTERILIZACION (t=1900) | **2 filas en vez de 7**: no se imprime ninguna fila periódica durante el resto de la esterilización |
| −20 s en ESTERILIZACION | Un hueco real de 50 s, pero el ticket imprime marcas con 30 s de separación (`00:31:25 → 00:31:55`): la hora relativa impresa ya no corresponde al tiempo real transcurrido |
| +3600 s en ESTERILIZACION | Una fila adelantada (15 s en vez de 30) y desde ahí **`timestamp_rel` corrido +1 h** (`00:31:25 → 01:31:40`) |

No se observaron ráfagas (como `_ultimo_log` toma el `ahora` de la última fila, un salto hacia adelante produce una sola fila extra) ni bloqueo del hilo de control. Un salto hacia atrás deja la impresión periódica **detenida** hasta que el reloj de pared recupera lo retrocedido o hasta el siguiente cambio de fase/subestado. En ningún caso se altera la gráfica de pantalla, que sí usa reloj monotónico; el ticket y la gráfica quedan en desacuerdo.

---

## 5. H3 — formato: **CONFIRMADA (desalineación de 1 columna; sin desborde)**

`ticket_formatter.py:55` hace `.ljust(1)`, que no recorta ni rellena códigos de 2 caracteres. Texto real generado:

```
  Hora      C      kPa          ← encabezado (ticket_formatter.py:48)
PH 00:00:01 0040.1 0075.1      len=25
PV 00:10:00 0060.5 0020.0      len=25
H 00:20:55 0120.2 0200.0       len=24
S 00:30:55 0134.5 0307.0       len=24
  00:34:25 0110.0 0120.0       len=24   (DESCOMPRESION, código " ")
E 00:54:25 0085.3 0075.0       len=24
```

Las filas `PH`/`PV` quedan desplazadas una columna a la derecha respecto de `H`/`S`/`E` y del encabezado. No desbordan el papel: la línea más larga mide 25 caracteres frente a los 48 documentados para 58 mm. El encabezado tampoco cae exactamente sobre las columnas de las filas de 1 carácter: "Hora" empieza en la columna 2, igual que la hora; "C" está en la columna 12, dentro del campo de temperatura (columnas 11–16). Impresión en papel real: **no verificada** (prohibido usar la impresora).

---

## 6. Coherencia esquema / claves / datos

Códigos realmente guardados en `lecturas.fase_codigo` (BD temporal, ciclo completado):

```
[(' ', 1), ('E', 2), ('H', 10), ('PH', 1), ('PV', 17), ('S', 7)]
```

| Fuente | Códigos | ¿Coincide con lo guardado? |
|---|---|---|
| `db_manager.py:57` (comentario del esquema) | `W / H / S / E` | No: `W` nunca se guarda; faltan `PH`, `PV` y `" "` |
| `cycle_logger.py:18-21` (comentario del módulo) | `W`, `H`, `S`, `E` | No |
| `cycle_logger.py:47-56` (`_FASE_A_CODIGO`) | `PH`, `PV`, `H`, `S`, `E`, `F` | Parcial: `F` nunca se guarda (§3); falta `" "` |
| `cycle_logger.py:70-84` (`_INTERVALO_PARAM`, `_INTERVALO_DEFAULT`) | `W`, `H`, `S`, `E` | No: `W` nunca se produce |
| `docs/mis_plans/inventario_cadenas_i18n.md:224` | `PH, PV, H, S, E, F` | Parcial (mismo caso que `_FASE_A_CODIGO`) |
| `tests/test_acciones_ciclos_puente.py:41` | usa `"C"` como dato de prueba | Valor ficticio, no lo produce el código |

---

## 7. No verificado

| Punto | Motivo |
|---|---|
| Ciclo con la máquina de estados real (fases y subestados producidos por `CicloState` y las fases) | El simulador del repo no ejecuta `CycleLogger`; montar el backend completo escribiría en `data/autoclave.db` (`DbManager()` sin ruta en `backend/context.py:79`) y abriría la impresora y el puerto serie reales. Se usó un guion de fases. |
| Duración real de las fases y de los pasos de prevacío | Dependen de la planta; las duraciones de §1 son supuestas. Las conclusiones de H1 no dependen de ellas (dependen solo de qué código se produce). |
| Salto real del reloj del sistema operativo | Se simuló reemplazando `time.time` en memoria; no se cambió la hora de Windows. |
| Aspecto en papel (alineación, caracteres) | Prohibido imprimir. Ancho tomado de los specs de arranque (48 caracteres). |
| Reimpresión y PDF (`format_ticket`, `acciones_ciclos.py`) | No ejecutados; usan el mismo `format_row`, así que heredan la desalineación de H3 y las filas ausentes guardadas en BD, pero no se comprobó. |
| `datetime.now()` (encabezado, pie, `timestamp_abs`) ante saltos | No se parcheó; es sello de registro, fuera de la regla de reloj monotónico. |

---

## 8. Hallazgos propuestos

### I18N-26a — Sin filas periódicas en PRECALENTAMIENTO y PRE_VACIO
- **Severidad propuesta:** Alta
- **Evidencia:** §3; `cycle_logger.py:47-49` (`PH`/`PV`) frente a `:70-75` y `:80-84` (`W`); `:357-359`.
- **Descripción:** el requisito (`2026-07-06-printer-realtime-cycle-ticket-design.md:15`) pide filas cada `intervalo_impresion` en W. En ejecución, 600 s de precalentamiento dejan 1 fila y el prevacío solo imprime en cambios de subestado. Presente desde el commit de creación.
- **Estado:** Abierto

### I18N-26b — SECADO sin ninguna fila y DESCOMPRESION sin filas periódicas; sin requisito definido
- **Severidad propuesta:** Media
- **Evidencia:** §3; ambas fases dan `" "` (`cycle_logger.py:340`), sin intervalo y sin detección de cambio de fase entre ellas.
- **Descripción:** el ticket no muestra el secado (0 filas en 900 s), ni la evolución de la descompresión. Además, ningún documento define qué intervalo les corresponde.
- **Estado:** Abierto

### I18N-26c — Intervalo y hora relativa del ticket con reloj de pared
- **Severidad propuesta:** Alta
- **Evidencia:** §4; `cycle_logger.py:229,362,375`.
- **Descripción:** un retroceso del reloj suprime las filas periódicas de esterilización (2 de 7) e imprime `00:00:00` en el resto del ciclo; un avance corre la hora impresa. Contradice `CLAUDE.md` y la decisión 5 de `planeacion_opciones.md:273`, ya en el alcance aprobado de `planeacion_backend_parametros.md` §12. Relacionado con C-01.
- **Estado:** Abierto (corrección ya planificada en OPC-08)

### I18N-26d — Cierre anormal impreso como `E`; código `F` inalcanzable
- **Severidad propuesta:** Media
- **Evidencia:** §3; `cycle_logger.py:152-157` y `:268`; `:53-55` nunca se usan.
- **Descripción:** por la letra de la última fila no se distingue un ciclo fallido de uno completado (el pie sí lo dice en "Estado:"). Además, el cierre normal imprime dos filas `E`.
- **Estado:** Abierto

### I18N-26e — Desalineación de columnas con códigos de 2 caracteres
- **Severidad propuesta:** Baja
- **Evidencia:** §5; `ticket_formatter.py:55`.
- **Descripción:** las filas `PH`/`PV` se desplazan una columna frente al resto y al encabezado. No hay desborde.
- **Estado:** Abierto

### I18N-26f — Documentación de códigos de fase incoherente con los datos
- **Severidad propuesta:** Baja
- **Evidencia:** §6; `db_manager.py:57`, `cycle_logger.py:17-21`.
- **Descripción:** el esquema y el comentario del módulo documentan `W/H/S/E`; la BD guarda `PH/PV/H/S/E/" "`. Cualquier consumidor (reportes, PDF, i18n de la letra de fase) que confíe en el comentario fallará.
- **Estado:** Abierto

---

## 9. Opciones de corrección (planeación, sin código)

**I18N-26a / 26b — intervalo por fase**
- Opción A: mapear los intervalos por **nombre de fase** (`fase_ciclo`) en lugar de por letra, con una tabla única fase → parámetro; la letra queda solo para imprimir. Riesgo bajo; requiere decidir el intervalo de DESCOMPRESION y SECADO.
- Opción B: unificar letras e intervalos (agregar `PH`, `PV` y un código propio para DESCOMPRESION y SECADO a la tabla de intervalos). Riesgo bajo, pero mantiene dos tablas que pueden volver a divergir.
- En ambas: dar código distinto a DESCOMPRESION y a SECADO para que el cambio entre ellas genere fila. Agregar pruebas que recorran todas las fases y cuenten filas por fase (no existen hoy: `tests/test_cycle_logger_printer.py` solo cubre CALENTAMIENTO).
- Riesgo común: más filas en papel (con 60 s en todas las fases no estériles, el ciclo simulado de ~55 min pasaría de 38 filas a unas 70; estimación, no ejecutada). Revisar consumo de papel con Cristian.

**I18N-26c — reloj**
- Ya planificado en `planeacion_backend_parametros.md` §12: intervalo y `timestamp_rel` con `time.monotonic()` (el módulo ya tiene `reloj_mono` inyectable, usado por la gráfica). Riesgo: cambio en el registro de evidencia; requiere prueba con reloj controlado como la de este informe. `timestamp_abs`, encabezado y pie siguen con reloj de pared.

**I18N-26d — cierre**
- Hacer que `_on_fin` use el código según el resultado (`E` completado, `F` otros) y evitar la fila `E` duplicada (o documentar que la segunda es intencional). Riesgo: cambia el contenido de tickets e históricos; los ciclos ya guardados conservarán `E`.

**I18N-26e — formato**
- Fijar el ancho de la columna de fase al código más largo (2) y ajustar el encabezado a las columnas reales; o volver a códigos de 1 letra. Decidirlo junto con la traducción de la letra de fase (D-01 de `planeacion_i18n.md`). Riesgo bajo; afecta reimpresión y PDF.

**I18N-26f — documentación**
- Actualizar el comentario del esquema y del módulo cuando se cierren 26a/26b/26d, con la lista final de códigos. Sin migración de datos (columna `TEXT`). Riesgo nulo.

---

## 10. Preguntas abiertas para Cristian

1. ¿Qué intervalo deben tener DESCOMPRESION y SECADO? ¿La "tasa general" (`intervalo_impresion`) o uno propio?
2. ¿PRECALENTAMIENTO y PRE_VACIO deben imprimir cada `intervalo_impresion` además de las filas por cambio de subestado del prevacío?
3. ¿Se conservan los códigos de 2 letras (`PH`, `PV`) o se vuelve a 1 letra? ¿Qué letra para DESCOMPRESION y SECADO?
4. ¿Un ciclo fallido, cancelado o en emergencia debe cerrar con `F`? ¿La doble fila `E` del cierre normal es deseada?
5. ¿I18N-26c se corrige dentro de OPC-08 (`planeacion_backend_parametros.md` §12) o en el plan propio del ticket que pide I18N-26?
6. ¿Ancho real de la impresora instalada (48 caracteres según los specs de arranque)?
7. ¿Se abre un plan propio del ticket del ciclo que agrupe 26a–26f, como indica `planeacion_i18n.md:250`?

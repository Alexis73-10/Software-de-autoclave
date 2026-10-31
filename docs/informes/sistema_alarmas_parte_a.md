# Sistema de alarmas, Parte A: catálogo, modelo, historial y contrato

Fecha: 2026-10-07. Rama: `alarmas-parte-a` (worktree `.worktrees/alarmas-parte-a`), creada desde `dev` en `9a94de4`. Lista para unir a `dev` cuando la apruebes.

Documentos de referencia: spec `docs/superpowers/specs/2026-10-06-sistema-alarmas-parte-a-design.md`, plan `docs/superpowers/plans/2026-10-07-sistema-alarmas-parte-a.md` y análisis previo `docs/informes/analisis_sistema_alarmas.md`.

## 1. En pocas palabras

- Todas las alarmas del equipo salen ahora de un **catálogo único** con código (SIS-01, PRE-06, COM-01…), nivel, título, descripción con valores reales y acción para el operador.
- `AlarmManager` maneja **instancias** con hora de aparición, resolución y reconocimiento, protegidas con un candado porque el reconocimiento llega por HTTP mientras el ControlLoop activa y resuelve.
- Cada aparición, resolución y reconocimiento queda en la tabla **`alarmas_historial`** de la base de datos. La escritura se hace desde un hilo propio, nunca desde el hilo de control.
- `/status` entrega el contrato nuevo de alarmas, con los campos viejos para compatibilidad. Hay dos endpoints nuevos: reconocer una alarma y consultar el historial.
- Cuando un ciclo falla, `motivo_fallo` y la nueva columna `codigo_fallo` llevan el código y el texto de la alarma causante, y el ticket imprime "código · título".
- La API vieja (`Alarm`, `AlarmType`, `report`/`clear`, `estado.Alarmas_activas`) se eliminó.
- **No se tocó** ninguna salida digital, el buzer, `reset_all_outputs`, el orden de las ramas de fallo de `CicloState.run()` ni los niveles con que dispara cada alarma.

## 2. Resultado de las pruebas

Suite completa al final (`$env:PYTHONPATH="src"; python -m pytest -q -p no:cacheprovider`): **1799 passed, 6 warnings** (77,8 s). Las 6 advertencias ya estaban antes de empezar (scipy/qfluentwidgets, `QMouseEvent` ×3, `utcnow` ×2); ninguna es nueva.

Base del worktree al empezar: **1641 passed**. El plan decía 1794, pero ese número incluía pruebas de `dev` que no tienen commit y por eso no están en el worktree. La rama deja **158 pruebas más** que la base (1799 − 1641).

Las pruebas se corren con `PYTHONPATH=src` porque el paquete instalado en modo editable apunta al árbol principal (`dev`), no al worktree.

## 3. Qué se hizo, por tarea del plan

| Tarea | Commit(s) | Qué hizo |
|---|---|---|
| 0. Documentos | `13ff2f7` | Análisis, spec y plan de la Parte A. |
| 1. Catálogo | `a1afed5` | `state_machine/alarms/catalogo.py`: niveles (INFORMATIVO, AVISO, ALARMA, FALLO_CRITICO), las 31 definiciones de la tabla de la spec y `NOMBRES_LEGIBLES` para sensores, fases y puertas. |
| 2. Instancias y API nueva | `75abc17`, `8ad2b66` | `InstanciaAlarma`, `activar` / `resolver` / `reconocer` / `resolver_todas_por_reinicio`, candado y oyentes. La corrección `8ad2b66` devolvió los logs por severidad de `report()`, que se perdían mientras la API vieja seguía en uso. |
| 3. Historial | `46582c0` | Tabla `alarmas_historial` e índice; columna `codigo_fallo` en `ciclos` con migración; `HistorialAlarmas` como oyente; SIS-02 si falla la escritura. |
| 4. Instancia única | `edaed13` | Un solo `AlarmManager`, creado en `BackendContext` e inyectado a `ControlLoop` y `StateMachine`; registro del historial con `ciclo_id` desde `CycleLogger`; salida de FALLA con `resolver_todas_por_reinicio()`. |
| 5. `/status` y endpoints | `23ea685` | DTO nuevo de alarmas con campos de compatibilidad (`id`, `level`, `description`, `source_state`), `eventos_recientes`, `POST /alarms/{clave}/acknowledge` y `GET /alarms/history`. |
| 6. PREPARACION y PREPARADO | `1349a58` | Suministros, chaqueta, cámara, agua residual, drenaje, puertas y sensores usan el catálogo (SUM, PRE, PUE-01, SEN-01). |
| 7. FALLA, HIBERNACION, ControlLoop y puertas | `e7f9828`, `54d772b` | SIS-01, COM-01 y PUE-04/05 con el catálogo. La corrección `54d772b` arregló la espera de hardware de `main.py`, que buscaba el id viejo `NO_HAY_CONEXION`. |
| 8. CICLO | `6f6d3d2` | Fallos de fase (CIC-01…06), puertas (PUE-02/03), sensor ausente (SEN-02), corte eléctrico (SUM-01), desconexión (COM-02) y apertura automática (CIC-07/08) con el catálogo; `motivo_fallo` = "código · título: descripción" y `codigo_fallo`. |
| 9. Base de datos y tickets | `cc2540d` | `cerrar_ciclo()` guarda `codigo_fallo`; el ticket del ciclo imprime "código · título"; el ticket de alarmas activas usa los campos nuevos. |
| 10. Quitar la API vieja | `d3ddc3e` | Se borraron `alarm.py` y `alarm_types.py`, la API vieja de `AlarmManager` y `estado.Alarmas_activas`. Una prueba nueva impide que vuelvan a aparecer en `src/`. |

## 4. Rondas de corrección

### Ronda F (revisiones de seguridad y de concurrencia)

| Ítem | Commit | Qué corrigió |
|---|---|---|
| F1 | `7260947` | `/status`: `alarms` lleva solo las alarmas ACTIVAS; las resueltas sin reconocer van en la clave nueva `alarmas_sin_reconocer`. `main.py` espera el hardware con `card_connected`. |
| F2 | `03048d0` | Registrar la alarma de un fallo de ciclo nunca puede impedir que corra el protocolo de fallo: si el registro lanzara una excepción, se registra en el log, se deja un motivo de respaldo y el protocolo se ejecuta igual. |
| F3 | `4a2c174` | El historial ya no escribe en SQLite desde el hilo de control: encola el evento y un hilo escritor propio lo guarda en orden. Se agregaron `vaciar()` y `detener()`. |
| F4 | `7f8e2cd` | Reconocer una alarma que desapareció en ese instante da 404; textos de SIS-01 y COM-02; limpieza de pruebas. |

### Ronda G (revisión final de la rama)

| Ítem | Commit | Qué corrigió |
|---|---|---|
| G1 | `0554c5b` | Si una ALARMA o FALLO_CRITICO resuelta sin reconocer vuelve a aparecer, se crea una instancia y una fila nuevas en el historial, con su propia hora y ciclo. Antes se reabría la fila de la primera vez. Se eliminó el evento `REACTIVADA` y `DbManager.reabrir_alarma`. |
| G2 | `a2dcbc7` | COM-01 ya no queda en el historial en cada arranque por el handshake serial normal. Mientras la tarjeta nunca haya conectado, COM-01 aparece solo si la desconexión dura la tolerancia completa (5 s). Después de la primera conexión, una caída la activa de inmediato, como antes. |
| G3 | (este commit) | Correcciones fechadas en la spec y este informe. |

## 5. Hallazgos de las revisiones y cómo se trató cada uno

**Revisión de seguridad (safety-reviewer).** 0 críticos, 4 importantes, 4 menores.

| Hallazgo | Qué pasaba | Cómo se trató |
|---|---|---|
| SAF-01 | Tras el handshake del arranque, COM-01 quedaba resuelta sin reconocer y la espera de hardware de `main.py` creía que no había tarjeta (esperaba 40 s y mostraba un mensaje falso). | F1: `main.py` usa `card_connected`. G2: el handshake normal ya no activa COM-01. |
| SAF-02 | Sin pantalla de reconocimiento (llega en la Parte C), las resueltas sin reconocer se veían para siempre en `alarms`. | F1, por decisión tuya: se separan en `alarmas_sin_reconocer` hasta la Parte C. |
| SAF-03 | Si registrar la alarma de un fallo de ciclo lanzaba una excepción, se saltaba `_protocolo.ejecutar()`. | F2: el registro está protegido y el protocolo corre siempre. |
| SAF-04 | El INSERT de SQLite se hacía en el hilo de control, justo antes del protocolo de fallo. | F3: hilo escritor propio con cola. |
| SAF-05 | Reactivar una resuelta sin reconocer reabría la fila vieja. | G1 (se adelantó; estaba previsto para B/C). |
| SAF-07 | El reconocimiento no exige autenticación. | Pendiente, obligatorio en la Parte C (§7). |
| SAF-08 | Un reconocimiento que llegara antes de que se escribiera la aparición se perdía. | F3: la cola es FIFO, así que la aparición siempre se escribe primero. |
| SAF-06 | Menor. | Revisado; no bloquea la Parte A. |

**Revisión de temporización y concurrencia (timing-auditor).** 0 críticos, 3 importantes, 6 menores.

| Hallazgo | Qué pasaba | Cómo se trató |
|---|---|---|
| TMG-01 | Igual a SAF-04. | F3. |
| TMG-02 | SUM-06 (vapor) no tiene debounce: un rebote del contacto genera una escritura por tick. | La escritura ya no está en el hilo de control (F3). El debounce cambia cuándo dispara la alarma, así que queda para la Parte B. |
| TMG-03 | Igual a SAF-08. | F3. |
| TMG-04 | `ciclo_id` queda vacío si la alarma aparece en el primer tick de CICLO o durante la espera de confirmación. | Pendiente para la Parte B (§7). |
| TMG-05…09 | Menores. | Revisados; no bloquean la Parte A. Los que siguen abiertos están en §7. |

**Revisión final de la rama.** Veredicto: "lista después de correcciones", con 3 importantes.

| Hallazgo | Cómo se trató |
|---|---|
| I-1: el historial juntaba todas las repeticiones de una alarma en la fila de la primera vez, con hora y ciclo equivocados. | G1. |
| I-2: COM-01 quedaba en el historial en cada arranque. | G2. |
| I-3: faltaban este informe y las correcciones de la spec. | G3. |

## 6. Desviaciones de la spec y decisiones tomadas

Todas quedaron escritas en la spec como "Corrección del 2026-10-07".

- **Reactivación (§5.2, §6.1, §6.2).** Una alarma resuelta sin reconocer que vuelve a aparecer es una ocurrencia nueva: instancia y fila nuevas, evento `APARECIDA`. La spec decía reabrir la misma fila. Motivo: sin pantalla de reconocimiento hasta la Parte C, la regla original dejaba registros con hora y ciclo equivocados. Costo: más filas en el historial; se puede revisar en la Parte C.
- **`/status` (§7.1).** `alarms` lleva solo las ACTIVAS; las resueltas sin reconocer van en `alarmas_sin_reconocer`, con el mismo formato, hasta la Parte C. Decisión tuya del 2026-10-07. `main.py` usa `card_connected` para esperar la tarjeta al arrancar.
- **Historial asíncrono (§6.2).** Escribe desde un hilo propio con una cola en orden; `vaciar()` y `detener()`.
- **COM-01 en el arranque (§4.3).** Mientras la tarjeta nunca haya conectado, COM-01 aparece solo tras 5 s de desconexión continua.
- **Textos (§4.3).** SIS-01: "Se presionó el paro de emergencia en estado {estado}." (se quitó "Todas las salidas están apagadas", que es falso en CICLO, donde el protocolo ventea). COM-02 muestra los segundos con un decimal.
- **Buzer (§5.5, corrección hecha al preparar el plan).** El reconocimiento no toca el buzer en la Parte A.
- **Commits por tarea en la rama**, no uno solo al final, porque elegiste trabajar en un worktree aparte. La unión a `dev` espera tu aprobación.

## 7. Pendientes para la Parte B y la Parte C

**Parte B**

- Debounce de SUM-06 (suministro de vapor), para que un rebote no genere apariciones y escrituras repetidas.
- `ciclo_id` vacío cuando la alarma aparece en el primer tick de CICLO o durante la espera de confirmación: tomarlo de `ciclo_id_pantalla`.
- Llamar a `detener()` del historial al apagar el backend. Hoy el hilo es daemon y lo que esté en la cola al cerrar el proceso se pierde.
- `timeout` explícito en `sqlite3.connect`.
- Guardia alrededor de `activar(COM_01)` en el ControlLoop, igual a la que protege el protocolo de fallo.
- Log en `resolver_todas_por_reinicio()` (hoy no deja rastro de qué resolvió).
- Pruebas que faltan: `cerrar_ciclo(codigo_fallo)` con base de datos real y que SIS-02 no se guarde en el historial.
- `time.time()` en el manejo de puertas: cambiarlo por `time.monotonic()`, como el resto de los temporizadores.
- Alarmas nuevas de puertas, fases, comunicación y sensores.
- Separar CIC-01…06 por causa, con valores (hoy llevan el `motivo_fallo` que deja la fase).

**Parte C**

- Pantalla de reconocimiento y pestaña de alarmas en Reportes.
- Autenticación del reconocimiento (obligatoria): hoy `POST /alarms/{clave}/acknowledge` acepta cualquier nombre de usuario.
- Fechas de solo día en `/alarms/history` (por ejemplo `2026-10-07`): hoy pasan la validación, pero la comparación es de texto y "hasta" deja fuera las alarmas de ese día. Corregir antes de la UI.
- Volver a mostrar las resueltas sin reconocer dentro del flujo de reconocimiento y revisar si la regla de reactivación de G1 se mantiene.

## 8. Cómo unir la rama a `dev`

1. **Antes de unir**, haz commit o guarda tus cambios pendientes en `dev`. La rama se creó desde `9a94de4` y tus cambios sin commit en `dev` quedaron intactos, pero `git merge` se niega a sobrescribir archivos modificados y sin commit.
2. Desde el checkout principal, en `dev`: `git merge alarmas-parte-a`.
3. Corre la suite completa en `dev` con `PYTHONPATH=src` y revisa que no haya pruebas nuevas en rojo por la mezcla con tus cambios.
4. Cuando todo esté bien, puedes borrar el worktree (`git worktree remove .worktrees/alarmas-parte-a`) y la rama.

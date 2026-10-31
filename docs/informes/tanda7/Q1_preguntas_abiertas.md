# Q1 ★ — Respuestas a las preguntas abiertas (decisión 1.3), tanda 7

Rama `tanda-7-q1`, desde `e8e42d7`. Fuente: `docs/mis_plans/instruccion_claude_code_tanda_7.md` §1.3 (recomendaciones aceptadas por Cristian). Contexto: `docs/informes/tanda6/R1_hallazgos_pendientes.md`, `T2_respuestas_T1.md`, `T2_matriz_actualizada.md`, `T2_ensayo_tabla.md`.

Etapa de seguridad (IEC 62304 Clase C). La sesión principal corre `safety-reviewer`, `timing-auditor` y `sensor-role-auditor` sobre la rama. Este subagente no los corrió.

## Qué se hizo (un commit por punto, cada uno con sus pruebas)

| Punto | Commit | Cambio | Archivos | Pruebas nuevas |
|---|---|---|---|---|
| R1-P1 | `308d33a` | `ControlLoop.exit_test_mode()` devuelve `True` solo si la tarjeta confirmó el ALL_OFF. Cada `modo_prueba_sale` de la bitácora anota `all_off_confirmado` (salida normal, logout, sesión bloqueada o cerrada por gestión, inactividad, dueño caducado, salida forzada). `/io/test/exit` lo devuelve en la respuesta. Lo que se apaga no cambia. | `control_loop.py`, `server.py` | `test_q1_r1p1_ack_salida_prueba.py` (7) |
| R1-P2 | `3398ea2` | PREPARADO: `ejecutor()` devuelve el resultado de los tres lazos y `esta_preparado(lazos)` lo usa, sin volver a llamar a `mantener_presion_camara`, `mantener_chaqueta` ni `mantener_drenaje`. El aire de cámara cierra a los 3 ticks reales (antes a los 1,5). | `preparado.py` | `test_q1_r1p2_preparado_un_lazo_por_tick.py` (5) |
| R1-P3 | `17fcdea` | `rango_calentamiento` se separa en `rango_calentamiento_temp` (°C) y `rango_calentamiento_pres` (kPa), los dos de clase "diferencia" y con defecto 2,0, en los 8 perfiles (factory/user). `migrar_parametros()` en `cycle_manager.py` corre en `Cycle.__init__` (archivo, defecto del hospital, `.bak`, instantánea de recuperación): copia el valor viejo a los dos. `calentamiento.py` usa cada rango con su magnitud y, si faltan las claves nuevas, cae a la vieja. Se actualizaron i18n `parametros_desc` (es/en), el filtro de PySide, el comentario de `unidades.py` y CLAUDE.md. | `cycle_manager.py`, `calentamiento.py`, 8 JSON, `es.json`, `en.json`, `params_ciclo.py`, `unidades.py`, CLAUDE.md, `revision_traducciones.md` | `test_q1_r1p3_rango_calentamiento.py` (20); ajustada `test_c1c_clase_parametros.py` |
| R1-P4 | `92c5e46` | `ProtocoloFallo.update()` detecta el Principal sin lectura (None, no finito o 0) con el protocolo ya en marcha por otra causa. Entonces pasa a `solo_lenta`: cierra la rápida, la chaqueta, la contrapresión y el agua de chaqueta, y sigue solo por la lenta, sin escalar. Queda enclavado. Cubre el resultado pendiente en CICLO y el estado seguro, que lo registra (`estado_seguro_solo_lenta`). Con eso aplica P-2: FALLA → PREPARACION sin técnico y CIC-10. | `protocolo_fallo.py`, `estado_seguro.py` | `test_q1_r1p4_principal_perdido_tras_protocolo.py` (10) |
| T2-a | `60dc00c` | CicloState mide con `time.monotonic()` el tramo en que la fase no corre por la tolerancia de DI vencida. Al volver los datos, o si el ciclo termina antes, suma los segundos a `estado.sin_datos_tarjeta_s` y la fase los descuenta: `EsterilizacionFase.pausar_exposicion()` corre el fin del conteo. El pie del ticket anota "Sin datos de la tarjeta: n s" / "No control board data: n s" (cp437). | `ciclo.py`, `esterilizacion.py`, `status.py`, `ticket_formatter.py`, `cycle_logger.py` | `test_q1_t2a_exposicion_pausa_di.py` (17) |
| R1-P5 | `d988b95` | Con `PARO_EMERGENCIA` sin `PARO_REAL` y el ciclo dentro de la tolerancia (`CicloState.tolerancia_di_activa`), `/cycle/abort` acepta. Pone `CICLO_CANCELADO` y responde `pendiente: true`, `codigo: cancelacion_en_espera_datos` y el texto (es/en). Al volver los datos el ciclo queda CANCELADO. Si la tolerancia vence, queda FALLO_CONEXION y P-7 limpia la marca. Con paro real, resultado pendiente o fuera de la tolerancia: 409, como antes. | `ciclo.py`, `server.py`, i18n | `test_q1_r1p5_abort_en_tolerancia_di.py` (10) |
| T2-b | `e9e4e7c` | `ControlLoop` cuenta los ticks seguidos con `estado_tarjeta == "ok"` y expone `enlace_confirmado_ok` (3 seguidos). `AlarmManager` no reconoce ni despeja COM-02/03 activas sin enlace ok. Al salir de FALLA tampoco las resuelve si el enlace volvió a caer. Una que ya estaba reconocida y siguió activa se despeja con un nuevo DESPEJAR. `/alarms/{clave}/acknowledge` responde 409 con el motivo (es/en). No se pide sesión (D-06). | `alarm_manager.py`, `control_loop.py`, `context.py`, `server.py`, i18n | `test_q1_t2b_despejar_exige_enlace_ok.py` (12) |
| T2-c | `113035e` | "*** CARGA NO ESTÉRIL ***" / "*** LOAD NOT STERILE ***" en el pie de todo ciclo que no termine COMPLETADO: FALLO_*, CANCELADO, EMERGENCIA, INTERRUMPIDO, SENSOR_AUSENTE y cualquier resultado vacío o desconocido. Aplica en vivo y al reimprimir. | `ticket_formatter.py` | `test_q1_t2c_no_esteril_si_no_completado.py` (18); ajustada `test_t2_p9_reimprimir_interrumpido.py` |
| Ensayo | `5214b3a` | Planta simulada de E1 en los 4 programas: celdas de R1-P3, R1-P4, R1-P5, T2-a y T2-c. | `tests/test_q1_ensayo_simulador.py`, `Q1_ensayo_tabla.md` | 20 + 1 escritor (omitido) |
| Banco | `6e35af7` | Casos B-11 (R1-P2), C-07 (T2-b), D-37 y E-08 (R1-P3), F-08 (T2-a), F-09 (T2-c), F-10 (R1-P4) y F-11 (R1-P5). `.md` y `.html` regenerados con `generar.py`. | `hoja_pruebas_banco/pruebas.py`, `hoja_pruebas_banco_equipo_pruebas.{md,html}` | — |
| Riesgos | `abe9311` | HAZ-Q1-01 a HAZ-Q1-08 y REQ-19 a REQ-26. Se actualizaron los residuales de HAZ-T2-03, -04 y -06. | `docs/riesgos/registro_riesgos.md`, `matriz_trazabilidad.md` | — |

Ningún id de alarma existente se renombró. Todos los temporizadores nuevos usan `time.monotonic()`.

## Ensayo con la planta simulada (4 programas)
Tabla completa en `docs/informes/tanda7/Q1_ensayo_tabla.md` (`Q1_ESCRIBIR_INFORME=1`). Resumen:

| Celda de `T2_matriz_actualizada.md` | Bowie & Dick | Instr. 134 | Instr. 121 | Líquidos |
|---|---|---|---|---|
| CICLO · fin normal, con los rangos separados (R1-P3) | COMPLETADO, 12,9 min, sin marca | COMPLETADO, 10,9 min | COMPLETADO, 21,3 min | COMPLETADO, 21,9 min |
| CICLO · cancelación + Principal perdido con el protocolo en marcha (R1-P4) | `solo_lenta` False→True; sin rápida, chaqueta ni contrapresión después; ES sale sin técnico | ídem | ídem | ídem (P = 120,6 kPa a los 20 min: la lenta ventea despacio) |
| CICLO · trama DI vencida + `/cycle/abort` (R1-P5) | tolerancia activa, sin protocolo durante ella; CANCELADO al volver los datos; marca limpia; ticket "Sin datos…: 2 s" y NO ESTÉRIL | ídem | ídem | ídem |
| CICLO · trama DI vencida 3 s en ESTERILIZACION (T2-a) | 210 s programados → 213,5 s reales; vapor OFF en la tolerancia; ticket "Sin datos de la tarjeta: 3 s"; COMPLETADO sin marca | ídem (210 → 213,5) | 900 → 903,5 | 900 → 903,5 |
| CICLO · paro pulsado (T2-c) | EMERGENCIA con "CARGA NO ESTÉRIL" | ídem | ídem | ídem |

La extensión es de 3,5 s y no de 3,0 porque el simulador avanza en ticks de 0,5 s.

R1-P1, R1-P2 y T2-b no dependen del programa ni de la planta (modo prueba, PREPARADO y alarmas). Se verifican con sus pruebas unitarias. La celda "FALLA · reconocimiento" (COM-02/03 hasta DESPEJAR) ahora exige además el enlace en "ok" (T2-b).

## Pruebas
- **Línea base** (según `comun.md`): 5020 passed / 2 skipped / 3 xfailed.
- **Pruebas nuevas:** 120 en 9 archivos `tests/test_q1_*` (una omitida: el escritor del informe). Se ajustaron 6 pruebas existentes: 4 aserciones en `test_io_test_mode_endpoints.py`, 1 en `test_io_momentaneas_keepalive.py`, la de clase de `rango_calentamiento` en `test_c1c_clase_parametros.py` y la de "otros resultados sin marca" en `test_t2_p9_reimprimir_interrumpido.py`.
- **Durante el trabajo** se corrieron las pruebas afectadas tras cada commit, todas en verde: 188 (R1-P1), 477 (R1-P2), 1529 (R1-P3), 470 (R1-P4), 1635 (T2-a), 89 (R1-P5), 1975 (T2-b) y 651 (T2-c).
- **Suite completa después:** ver el final de este informe.

**AVISO para la sesión principal (entorno).** El paquete `autoclave` está instalado en modo editable apuntando a `C:\Users\tecni\Documents\codigo_autoclave\src`. Dentro de un worktree, `python -m pytest` importa el código del repositorio PRINCIPAL, no el del worktree, y las pruebas pasan o fallan contra otro código. Todas las corridas de Q1 se hicieron con `PYTHONPATH=<worktree>/src`, comprobado con `autoclave.__file__`. Hay que hacer lo mismo con las demás ramas antes de dar su suite por buena.

## DECISIONES SIN CONFIRMAR
Para revertir cualquiera: `git revert <commit>` del punto.

- **Q1-D1 (R1-P1, `308d33a`).** Sin ACK solo se anota en la bitácora y en el log, sin reintentar ni bloquear la reanudación: la decisión pide auditar sin cambiar lo que se apaga. La cancelación del modo prueba por el paro no pasa por `exit_test_mode`, así que su `modo_prueba_sale` sigue sin el campo. Alternativa: reintentar el ALL_OFF.
- **Q1-D2 (R1-P2, `3398ea2`).** La corrección se aplicó a los tres lazos, no solo a `mantener_presion_camara`: chaqueta y drenaje tenían el mismo doble conteo en sus confirmadores. `esta_preparado()` sin argumento (llamada directa, pruebas) corre los lazos una vez. Alternativa: solo presión de cámara.
- **Q1-D3 (R1-P3, `17fcdea`).**
  - La migración ocurre en memoria al cargar. El archivo queda en el formato nuevo la próxima vez que se guarda el programa: en el arranque no se escribe nada.
  - Los dos parámetros heredan `min`/`max` del viejo (0 a 30).
  - `unidades.SIN_CONVERSION` conserva el nombre viejo para un archivo sin migrar.
  - Alternativa: reescribir los archivos al arrancar.
- **Q1-D4 (R1-P4, `92c5e46`).**
  - Sin debounce, igual que P-2: una sola lectura None o 0 basta y queda enclavado aunque el Principal vuelva a leer. **Cambiado en la revisión (`43e117b`, SAF-01/SEN-02/TMG-07): con el protocolo en marcha ahora exige 3 lecturas inválidas seguidas. P-2 (disparo por el Principal perdido en ciclo) no cambia.**
  - También aplica al protocolo que P-1 dispara tras el ack de un COMPLETADO con la cámara no segura.
  - Alternativa: 3 lecturas.
- **Q1-D5 (R1-P5, `d988b95`).**
  - Se acepta solo cuando el propio ciclo ya está en la tolerancia, es decir, cuando un tick ya vio la DI vencida. Entre el vencimiento de la DI y ese tick (menos de un tick) sigue el 409.
  - La desconexión total (COM-02, la tolerancia de 5 s del ControlLoop) no cambia: sigue en 409.
  - La respuesta es `{"ok": true, "action": "CICLO_CANCELADO", "pendiente": true, "codigo": "cancelacion_en_espera_datos", "mensaje": ...}`.
- **Q1-D6 (T2-a, `60dc00c`).**
  - El total del ticket suma los segundos sin datos de todo el ciclo, no solo los de ESTERILIZACION. Solo la exposición de ESTERILIZACION se pausa.
  - El timeout de F0 (2 × tiempo) no se corre.
  - Los segundos se redondean al entero.
  - Alternativa: anotar solo los de ESTERILIZACION.
- **Q1-D7 (T2-b, `e9e4e7c`).**
  - "3 tramas vigentes seguidas" se toma como 3 ticks seguidos con `estado_tarjeta == "ok"` (enlace hecho y DI vigente), con la misma semántica que P-3.
  - En CICLO, sin enlace ok, tampoco se reconoce COM-02/03, porque reconocer es lo que después las despeja.
  - Sin verificador conectado (dobles de prueba) no se exige nada. `BackendContext` siempre lo conecta, y sin lazo de control responde False (falla cerrada).
- **Q1-D8 (T2-c, `113035e`).** Un resultado vacío o desconocido también lleva la marca (falla segura).

## PREGUNTAS PARA CRISTIAN
Transiciones de ciclo y puertas no definidas en §1.3: no se tocaron.
- **Q1-P1:** si al salir del modo prueba la tarjeta no confirma el ALL_OFF, ¿se reintenta o se impide reanudar la máquina? Hoy solo se anota.
- **Q1-P2:** durante la tolerancia por DI vencida siguen corriendo los demás temporizadores de fase: timeout y ventana de estabilidad de CALENTAMIENTO, PREVACIO, DESCOMPRESION y SECADO. La decisión solo pausó la exposición. ¿Se pausan también?
- **Q1-P3:** el F0 sigue acumulando durante la tolerancia, con la temperatura real y el vapor cortado. ¿Se excluye?
- **Q1-P4:** ¿la desconexión total de la tarjeta (antes de los 5 s de COM-02) también debe aceptar `/cycle/abort` como R1-P5?
- **Q1-P5:** la línea "Sin datos de la tarjeta: n s" no se guarda en la base, así que la reimpresión no la muestra (pasa lo mismo con los avisos de uniformidad). ¿Se agrega una columna? Toca `db_manager.py`, punto de choque.
- **Q1-P6:** ¿se muestra en la pantalla QML el texto de "cancelación en espera" (R1-P5) y el motivo del rechazo de DESPEJAR (T2-b)? Hoy el panel muestra el texto de la excepción HTTP y la cancelación no muestra nada nuevo.
- **Q1-P7:** ¿la pantalla de resultado del ciclo (no solo el ticket) debe decir también "carga no estéril"?

## Comprobaciones manuales para Cristian (banco)
B-11, C-07, D-37, E-08, F-08, F-09, F-10 y F-11 de la hoja de pruebas de banco. En resumen:
- **B-11:** el aire de cámara cierra al tercer tick en banda.
- **C-07:** DESPEJAR rechazado sin enlace y aceptado sin sesión al volver.
- **D-37/E-08:** los dos rangos visibles, convertidos como banda; un programa viejo migra; la rampa no cambia.
- **F-08:** un corte de 2-3 s alarga la esterilización y aparece en el ticket.
- **F-09:** marca en todos los tickets no completados.
- **F-10:** perder el Principal tras cancelar deja solo la lenta.
- **F-11:** cancelar durante el corte breve.

## Archivos de choque tocados
- `src/autoclave/i18n/es.json`, `en.json`: claves nuevas `ciclo.cancelacion_en_espera_datos` y `notificaciones.despejar_sin_enlace`; `parametros_desc.calentamiento.rango_calentamiento` reemplazada por `_temp` y `_pres`, y texto de `factor_calentamiento` (es).
- `docs/mis_plans/revision_traducciones.md`: 3 filas "sin revisar".
- No se tocaron `Instalacion.qml` ni `db_manager.py`.

## Suite completa
(se completa abajo)

## Revisión de la sesión principal (22-oct)

Revisores: `safety-reviewer` (SAF, Altos/Críticos: 0), `timing-auditor` (TMG) y `sensor-role-auditor` (SEN). Se corrigió solo lo pedido, con la opción más conservadora y reversible. Un commit por hallazgo, cada uno con su prueba escrita antes (falló primero). Para revertir: `git revert <commit>`.

| ID | Severidad | Estado | Detalle |
|---|---|---|---|
| SAF-01 | Medio | Corregido, `43e117b` | `solo_lenta` con el protocolo en marcha exige 3 lecturas inválidas seguidas del Principal (`_DEBOUNCE_LECTURAS`); una válida reinicia el contador. Mismo hallazgo que SEN-02 y TMG-07. |
| SAF-02 | Medio | Pendiente | Pausa T2-a en una desconexión total de menos de 5 s. No se tocó. |
| SAF-03 | Bajo | Corregido, `59131af` | `_tick_fallido()` pone `_ticks_tarjeta_ok` a 0. Un tick que lanza, antes o después de contar, no deja `enlace_confirmado_ok` en True. |
| SAF-04 | Bajo | Corregido, `737ef06` | `migrar_parametros()`: si el `rango_calentamiento` viejo no es dict, crea `_temp` y `_pres` con el defecto de fábrica (2,0, `diferencia`, 0-30) y deja una advertencia en el log. Mismo hallazgo que SEN-07a. |
| SAF-05 | Bajo | Corregido, `f10615f` | El pie del ticket compara con igualdad exacta con "COMPLETADO". Es el único valor real: `CicloState` fija `estado.fase_ciclo = "COMPLETADO"`, `CycleLogger` cierra con él y la base filtra con `='COMPLETADO'`. |
| TMG-01 | Alto | Corregido, `733b19f` | Los retornos tempranos de `_tick()` (sin conexión y primera DI pendiente) reinician `_f0_ultimo_tick`. `_acumular_f0` no suma un hueco de más de 2 × `interval`: solo reinicia el sello. Cubre también la parte F0 de SEN-03. |
| TMG-02 | Medio | Pendiente | Pausa T2-a en una desconexión total de menos de 5 s (mismo tema que SAF-02). |
| TMG-03 | Medio | Pendiente | Fuera del alcance de esta corrección. |
| TMG-04 | Medio | Pendiente | Fuera del alcance de esta corrección. |
| TMG-05 | Medio | Pendiente | Fuera del alcance de esta corrección. |
| TMG-06 | Medio | Corregido, `6932e1c` | `pasar_a_solo_lenta()` abre la lenta en el mismo paso, también con `pres_camara` None, salvo vacío confirmado (`P < atm − rango`). Es el mismo criterio que el caso "presión desconocida" de `ejecutar()`. Mismo hallazgo que SEN-04. |
| TMG-07 | Medio | Corregido, `43e117b` | Ver SAF-01. |
| TMG-08 | Bajo | Pendiente | Fuera del alcance de esta corrección. |
| TMG-09 | Bajo | Pendiente | Fuera del alcance de esta corrección. |
| TMG-10 | Bajo | Pendiente | Fuera del alcance de esta corrección. |
| TMG-11 | Bajo | Pendiente | Fuera del alcance de esta corrección. |
| TMG-12 | Bajo | Pendiente | Fuera del alcance de esta corrección. |
| SEN-01 | Alto | Pendiente (ya estaba en la base) | `convert_pressures` recorta a 0,0 kPa la lectura de un transductor sin señal, y `CicloState` y `ProtocoloFallo` la toman como válida. No lo introdujo Q1. |
| SEN-02 | Medio | Corregido, `43e117b` | Ver SAF-01. |
| SEN-03 | Medio | Corregido en la parte F0, `733b19f` | Ver TMG-01. |
| SEN-04 | Bajo | Corregido, `6932e1c` | Ver TMG-06. |
| SEN-05 | Bajo | Pendiente | Fuera del alcance de esta corrección. |
| SEN-06 | Bajo | Pendiente | Fuera del alcance de esta corrección. |
| SEN-07a | Bajo | Corregido, `737ef06` | Ver SAF-04. |
| SEN-07b | Bajo | Corregido, `f82a8a9` | `_load_factory_params` (PySide `params_ciclo.py`) pasa los parámetros de fábrica por `migrar_parametros()`. |
| SEN-08 | Bajo | Pendiente | Fuera del alcance de esta corrección. |
| RR-01 (re-revisión, timing y safety) | Medio/Bajo | Corregido, `88858a0` | `_acumular_f0` seguía sumando F0 durante la tolerancia por DI vencida: la fase estaba pausada, pero `fase_ciclo` seguía en ESTERILIZACION y los ticks de 0,5 s no activaban el tope. Ahora recibe los mismos datos vigentes del paso 5. Sin ellos, o con `tolerancia_di_activa`, reinicia `_f0_ultimo_tick` y no acredita nada. Responde también Q1-P3. |
| TMG-02 (re-revisión) | Bajo | Pendiente | El tope de dt de TMG-01 está ligado al intervalo nominal y, si se supera, descarta todo el dt en vez de acreditar hasta el tope. |
| `permite_salir_de_falla` | — | PREGUNTA PARA CRISTIAN | `estado_seguro.py` deja salir de FALLA sin técnico en cuanto el protocolo está en `solo_lenta` (criterio de P-2). No se cambió. ¿Se mantiene esa regla, ahora que `solo_lenta` puede llegar tras el protocolo en marcha (R1-P4)? |

### Notas de las correcciones
- **TMG-01.** El umbral es 2 × `interval`, 1 s con el lazo de 0,5 s. Si un tick tarda más de 0,5 s (más el `sleep`), ese tramo no suma F0. Ese error va del lado seguro: el F0 queda contado de menos y el ciclo se alarga. `tests/test_control_loop_f0.py` construye el lazo con `interval=60.0` porque sus pasos son de 60 s.
- **SAF-01.** Se ajustaron `test_q1_r1p4_principal_perdido_tras_protocolo.py` (3 updates por pérdida) y el evento R1-P4 de `test_q1_ensayo_simulador.py` (3 ticks). No se regeneró `Q1_ensayo_tabla.md`: la celda de R1-P4 da el mismo resultado, solo cambian los ticks que tarda en entrar.
- **RR-01.** Con esto, Q1-P3 (F0 durante la tolerancia) queda resuelto: no se acumula. Si Cristian prefiere otro criterio, se revierte `88858a0`.
- **SAF-04.** Si el valor viejo es un número suelto, no se copia: se usa el defecto 2,0, como se pidió. La advertencia del log anota el valor descartado.

### Pruebas nuevas (revisión)
`test_q1rev_f0_corte_enlace.py` (5), `test_q1rev_solo_lenta_debounce.py` (3), `test_q1rev_solo_lenta_abre_lenta.py` (5), `test_q1rev_migracion_rango_no_dict.py` (5), `test_q1rev_params_ciclo_fabrica_migrada.py` (2), `test_q1rev_no_esteril_igualdad_exacta.py` (5), `test_q1rev_enlace_ok_tick_fallido.py` (2) y, de la re-revisión, `test_q1rev_f0_pausa_di.py` (4). Total: 31.

### Suite completa tras la revisión
Corrida por la sesión principal sobre la unión de esta rama (hasta `88858a0`) con `tanda-7` (commit 8a4a63d), en un worktree limpio: **5405 passed, 3 skipped, 3 xfailed** (19 min 59 s). El subagente no llegó a anotar su propia corrida en la rama (su tarea en segundo plano se cortó).

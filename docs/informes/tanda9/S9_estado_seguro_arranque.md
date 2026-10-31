# S9 ★ — Estado seguro al arrancar y bloqueos (tanda 9, D9-1)

Rama `tanda-9-s9` (worktree `.claude/worktrees/agent-a8977a28ac4adbe26`). El S9 original se cortó por el límite de uso con el código, las pruebas y los documentos ya en commits, pero sin informe. Esta continuación aplicó las correcciones de la revisión ★ pasada 1 (`C:/Users/tecni/Documents/_suites_t9/s9_revision_1.md`), actualizó las pruebas viejas que todavía afirmaban el comportamiento que D9-1 revierte y escribió este informe.

Fuente de verdad: `docs/mis_plans/decisiones_tanda_9.md` §"Causa común" y §D9-1; etapa S9 de `docs/mis_plans/instruccion_claude_code_tanda_9.md`.

## 1. Qué se hizo, por punto D9

| Punto | Qué se hizo | Dónde |
|---|---|---|
| D9-1.1 | Al arrancar con la cámara no segura el protocolo corre solo, sin confirmación, con el programa conservador (`_programa_para_arranque`) y en `solo_lenta`: con presión sobre atm + brecha solo la lenta (nunca rápida, chaqueta ni contrapresión, cualquier modo y carga); con vacío bajo atm − brecha, aire atmosférico (rama existente de `ProtocoloFallo`, ahora con 3 lecturas, ver SAF-03); sin presión no abre nada. NO ABRIR sigue hasta la cámara segura. | `control_loop.py` (`_procesar_recuperacion`), `protocolo_fallo.py` |
| D9-1.2 | La confirmación se exige solo tras un paro real (`PARO_REAL`) visto con el protocolo en marcha. `ProtocoloEstadoSeguro.origen`/`causa` ("paro_liberado", "arranque", "fallo", "cancelado", "completado") publicada en `/status` → `UiBridge.estadoSeguroCausa` → texto en `SeccionEstadoSeguro.qml`; "paro liberado" solo con la confirmación pendiente. | `estado_seguro.py`, `state_machine.py`, `server.py`, `ui_bridge.py`, `SeccionEstadoSeguro.qml`, i18n |
| D9-1.3 | Con el estado seguro activo o la recuperación pendiente se permiten modo prueba (el protocolo se pausa con `pausar("modo_prueba")` y se reanuda tras el ALL_OFF de salida), apagado (sin el 409 `estado_seguro_activo`; queda `estado_seguro_activo` en la bitácora) y cambio de programa (backend y `PantallaPreciclo.qml`). El inicio sigue bloqueado. `programas_para_seguridad` incluye el programa del protocolo y el de la recuperación; `temp_max_tras_ciclo` toma la menor; `ProtocoloEstadoSeguro` añade su propio programa. Revisión ★ SAF-01: el modo prueba ya no puede abrir puertas ni encender vapor en ese estado (ver §3). | `control_loop.py`, `estado_seguro.py`, `server.py`, `PantallaPreciclo.qml` |
| D9-1.4 | Presión de cámara sin lectura (3 lecturas, en los dos sentidos) → `bloqueado_motivo` «Sensor de presión de cámara sin lectura…» → CIC-10 (clave i18n `estado_seguro_motivos.sin_presion_camara`) además de SEN-06; NO ABRIR; sin bloquear lo de D9-1.3. Revisión ★: cuenta tramas AI distintas y la trama AI vencida cuenta como presión perdida. | `protocolo_fallo.py`, `alarmas_i18n.py`, i18n |
| D9-1.5 | Login siempre permitido, también con paro o confirmación pendiente: se quitó la vuelta forzada del login/cambio de clave en `Main.qml`; la confirmación sigue en la tarjeta de Preciclo y en la campana. | `Main.qml` |
| D9-1.6 | Coherencia puerta-presión: alarma nueva **SEN-10** (ALARMA, bloquea el inicio) «Presión de cámara incoherente con la puerta abierta», con las 3 causas posibles en la acción; solo fuera de ciclo y fuera del modo prueba; 3 lecturas para aparecer y 3 coherentes (con la puerta ABIERTA, revisión ★ SAF-02) para despejarse. | `core/runtime/coherencia_puerta_presion.py` (nuevo), `catalogo.py`, i18n, `control_loop.py` |
| Riesgos / banco | HAZ-S9-01 a 05; hoja de banco C-05, C-05b a C-05h. | `docs/riesgos/registro_riesgos.md`, `docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md` |

## 2. Commits

S9 original:
- `a21329e` feat: estado seguro de arranque sin confirmación, bloqueos D9-1.3, CIC-10 sin presión y SEN-10.
- `3171551` feat: QML — login siempre permitido, causa del estado seguro, programa cambiable.
- `f10d5c3` test: celdas de arranque con la planta simulada en los 4 programas.
- `57b2844` docs: hoja de banco C-05 a C-05f, riesgos HAZ-S9-01 a 04 y SEN-10 en el catálogo.

Correcciones de la revisión ★ (esta continuación):
- `49ef046` fix: AI vencida = presión perdida, debounce por trama, aire atmosférico cerrado con presión (TMG-02/03/04/05, SAF-03).
- `ba18b89` fix: SEN-10 no se despeja al cerrar la puerta y cuenta tramas AI (SAF-02/TMG-01/TMG-03).
- `9e19ab1` fix: modo prueba sin apertura de puertas ni vapor con estado seguro o cámara no segura (SAF-01) — incluye el cableado de `control_loop.py` de TMG-02/03/05/06.
- `5d10ad8` test: pruebas de la revisión 1, celdas SAF-01/SAF-03 en la planta y pruebas viejas al comportamiento D9-1.
- `0f74541` docs: hoja de banco C-05b/e/f/g/h, HAZ-S9-03/04/05, catálogo SEN-10 y tabla de ensayo regenerada.
- `378c2a7` test: SEN-10 en las tablas de `test_alarmas_catalogo.py`; `8505017` docs: este informe (pasada 1).

Correcciones de la revisión ★ pasada 2:
- `12b4ecf` fix: AI vencida = datos no vigentes también en el protocolo del ciclo y DESCOMPRESION (R2-A1, R2-M1, R2-M2, R2-B2/B3/B4).
- `40891e7` fix: la apertura de puertas evalúa la cámara con la presión vigente (R2-M3).
- `aceac46` fix: modo prueba falla cerrada y sin aire comprimido ni vapor de fuente con estado seguro (R2-B1, P-a).
- `b391f13` test: pruebas de la revisión 2 y celda `ai_vencida_en_protocolo` en la planta.
- `68ce439` fix: pruebas viejas ajustadas (`test_i18n.py`, `test_t2_p2_principal_perdido.py`); `38c880b` documentos de la pasada 2.

Correcciones de la revisión ★ pasada 3:
- `b1e51f0` fix: decisión inicial del protocolo pendiente con la AI vencida y sin aire atmosférico sin referencia (R3-A1, (b)).
- `032c702` fix: NO ABRIR de `/status` con la presión vigente (R3-M1).
- `76d9c6d` test: pruebas de la revisión 3.
- commit siguiente: pruebas viejas ajustadas (`test_t4_camara_segura.py` por R3-M1, `test_protocolo_fallo_modo_descompresion.py` por (b)), tabla de ensayo, riesgos, hoja de banco y este informe.

## 3. Revisión ★ (pasada 1, sesión principal) — estado de cada hallazgo

| Hallazgo | Nivel | Verificado contra el código | Estado | Cómo |
|---|---|---|---|---|
| SAF-01 | Crítico | Real: con D9-1.3 el modo prueba se permite con el estado seguro y `/io/test/output` no comprobaba nada para puertas/vapor; las puertas no se actualizan en pausa. | **Corregido** (DECISIÓN SIN CONFIRMAR de la sesión principal) | `core/runtime/salidas_prueba_seguridad.py` (regla pura); `ControlLoop.salidas_prueba_bloqueadas()` (estado seguro, recuperación, `camara_segura.evaluar` con los programas de seguridad, el menor `temp_max_apertura` y `presion_vigente`; error = todas); `/io/test/output` rechaza encender `abrir_puerta_N`/`desbloqueo_puerta_N` (código `salida_prueba_camara_no_segura`) y `descompresion_rapida`/`descompresion_chaqueta`/`vapor_camara` (`salida_prueba_estado_seguro`); también la inversión de D-ES-16 (cierre con atrapamiento → apertura) se rechaza y solo suelta el cierre; el lazo las apaga en cada tick del modo prueba y anota `salida_prueba_cortada` una vez por salida reportada encendida. Textos i18n es/en `io.err_puerta_camara_no_segura`, `io.err_salida_estado_seguro`. |
| SAF-02 / TMG-01 | Alto | Real: `_evaluar` devolvía False (coherente) con todas las puertas cerradas. | **Corregido** | Puerta cerrada = None (no evaluable): conteo a cero y SEN-10 confirmada se mantiene y se reafirma; solo la despejan 3 lecturas coherentes con una puerta abierta. Prueba «SEN-10 activa → cerrar puerta → sigue activa y bloquea inicio». Catálogo, C-05f y HAZ-S9-04 actualizados. |
| TMG-02 | Alto | Real: «sin presión» era solo None; con DI vigente y AI vencida, Units conserva la última presión. | **Corregido** | `ControlLoop._lectura_ai()` → `ProtocoloEstadoSeguro.lectura_ai` → `ProtocoloFallo.lectura_ai`. Con AI vencida: `_pres_camara()` = None (no abre aire comprimido ni nada nuevo; `_alivio_sobrepresion`, `pasar_a_solo_lenta` y `_ventear_tras_sellado` también la usan), presión perdida de inmediato (CIC-10), el estado seguro no cuenta ticks seguros, la recuperación de arranque no la da por segura y `_seguir_programa_ultimo_ciclo` no cuenta. |
| SAF-03 | Medio | Real: en la rama P > atm + brecha con `_presurizado_al_disparo` (y `solo_lenta`) el aire atmosférico no se cerraba; la rama de vacío abría el aire con una sola lectura. | **Corregido** | Aire cerrado siempre con P > atm + brecha; vacío: descompresiones cerradas en el acto (lado seguro) y aire solo con 3 lecturas seguidas (también en la sub-rama de enfriamiento sin contrapresión). Planta simulada: verificación POR TICK (aire abierto con P publicada > atm + brecha = falla) en todas las celdas, más la celda `arranque_vacio_con_fuga`. |
| TMG-03 | Medio | Real: los debounces nuevos contaban ticks. | **Corregido** | `SerialLink.secuencia_ultima_ai()` (nuevo); coherencia y `_seguir_presion_perdida` cuentan solo tramas AI distintas; contadores a cero con tick no evaluable, sin datos vigentes o en pausa. Enlace que no informa el número (dobles de prueba): cada tick cuenta (mismo criterio que D8-2.9). |
| TMG-04 | Medio | Real: `_sin_sonda_desde` seguía corriendo durante el modo prueba. | **Corregido** | `pausar("modo_prueba")` marca la pausa; al reanudar, `reanudar(tras_modo_prueba=True)` reinicia la espera sellada sin sonda (tras un paro sigue corriendo, como antes). |
| TMG-05 | Bajo | Real. | **Corregido** | `reanudar()` pone a cero `_lecturas_enfriada`, `_lecturas_presion_perdida/_vuelta`, `_lecturas_principal_perdido` y `_lecturas_vacio`; `enter_test_mode()` pone a cero `_ticks_seguros_recuperacion`. |
| TMG-06 | Bajo | Real. | **Corregido** | `coherencia_puerta_presion.update()` en try/except con `logger.exception` y reinicio del conteo. |
| TMG-07 | Bajo | Real (cosmético). | **Documentado, sin corregir** (por instrucción) | `_estado_seguro_status()` lee sin `_sm_lock`; los eventos de bitácora van en hilos daemon sin orden garantizado. |

Ningún hallazgo resultó no real.

## 3b. Revisión ★ pasada 2 (re-revisión de 57b2844..8505017) — estado de cada hallazgo

| Hallazgo | Nivel | Verificado contra el código | Estado | Cómo |
|---|---|---|---|---|
| R2-A1 (TMG-02 en CICLO) | Alto | Real: `CicloState` llama `_protocolo.update()` sin `lectura_ai`; sin ella la AI congelada contaba como vigente y `_tick_enfriamiento` reabría el aire comprimido. | **Corregido** | Proveedor común `estado.lectura_ai` (lo publica el ControlLoop; `core/runtime/vigencia_ai.py`, leído del `__dict__` del estado para que un MagicMock no invente uno). El `ProtocoloFallo` lo usa si no tiene `lectura_ai` propio: el del ciclo, con la confirmación pendiente y la AI vencida, cierra el aire comprimido y no lo reabre. La fase DESCOMPRESION (modos 4/5, anterior a S9) también: barato y seguro (solo deja de abrir aire comprimido con la AI vencida). Prueba «FALLO modo 4 presurizado, confirmación pendiente, AI vencida → aire comprimido cerrado». |
| R2-M1 | Medio | Real: la AI vencida contaba como transductor perdido y a los 3 ticks enclavaba `solo_lenta` (venteo de líquido sellado). | **Corregido** (DECISIÓN SIN CONFIRMAR de la sesión principal) | AI vencida = datos no vigentes: no se abre nada nuevo (cierra el aire comprimido), lo abierto se mantiene, el sellado no decide el venteo, no cuenta para `_lecturas_principal_perdido` ni para `pasar_a_solo_lenta`; `_presion_camara_perdida()` solo es True con la AI vigente y la presión sin lectura (transductor que manda tramas). CIC-10 + NO ABRIR fuera de ciclo, log en ciclo. Celda de planta `ai_vencida_en_protocolo` (4 programas). |
| R2-M2 | Medio | Real. | **Corregido** | `_lecturas_vacio` cuenta por número de trama AI (`_seq_vacio`). |
| R2-M3 | Medio | Real (anterior a S9): `_can_open_physical` evaluaba sin `datos_vigentes`. | **Corregido** | `ServicioPuertas(presion_vigente=...)` ← `BackendContext.presion_vigente` (← `ControlLoop.presion_vigente`; False sin ControlLoop). Evalúa con `datos_vigentes=`; error = no abre. Cubre `/doors/{n}/open` y la apertura automática (mismo camino). |
| R2-B1 | Bajo | Real. | **Corregido** | Respuesta que no es dict = todas bloqueadas; `tests/backend_doble.py` deja el doble en `{}` salvo que la prueba lo configure. |
| R2-B2 | Bajo | Real. | **Corregido** | `_primera_di_mono` (primera DI vigente de la conexión); la espera de la primera AI se mide desde ahí. |
| R2-B3 | Bajo | Real. | **Corregido** | `ejecutar()` lee la AI: con la AI vencida no abre válvulas; en vacío no abre el aire (cuenta la primera lectura; update() lo abre con la tercera). |
| R2-B4 | Bajo | Real. | **Corregido** | `SerialLink.estado_ultima_ai()` → (edad, seq) en una toma de `data_lock`; `ControlLoop._lectura_ai()` lo usa (dobles sin él: dos tomas, como antes). Sin trama: (None, None) → no vigente. |
| R2-B5 | Bajo | Real. | **Documentado, sin cambio** (por instrucción) | `_ticks_seguros`, `_ticks_seguros_recuperacion` y `_ticks_seguros_tras_ciclo` cuentan ticks, no tramas: excepción a TMG-03, aceptada (con la AI vencida no cuentan). |
| P-a | — | — | **Aplicada** (DECISIÓN SIN CONFIRMAR de la sesión principal) | Con estado seguro o recuperación pendiente el modo prueba tampoco enciende `aire_comprimido_camara`, `vapor_generador` ni `vapor_caldera`; `vapor_chaqueta` sigue permitida. |

Altos/Críticos abiertos: ninguno (pendiente la re-revisión de la sesión principal).

## 3c. Revisión ★ pasada 3 — estado de cada hallazgo

| Hallazgo | Nivel | Verificado contra el código | Estado | Cómo |
|---|---|---|---|---|
| R3-A1 (causado por R2-B3) | Alto | Real: con la AI vencida en `ejecutar()` nunca se fijaban `_presurizado_al_disparo` ni el timeout del modo; al volver la AI un líquido en modo 4/5 tomaba la rama "sin contrapresión" (lenta abierta) y un sólido quedaba sin escalada. | **Corregido** (opción preferida por la revisión) | Con la AI vencida, `ejecutar()` deja la decisión inicial PENDIENTE (`_decision_pendiente`: "abrir" o "presurizado"), con todo cerrado (ALL_OFF del disparo; `update()` reafirma el aire comprimido cerrado y no abre nada). El primer `update()` con la AI vigente la toma: con "abrir", el mismo paso 2 del disparo (`_decision_inicial`: presurizada → `_presurizado_al_disparo`, timeout, paso del modo; vacío → primera lectura de vacío; sin presión → lenta sin escalar); con "presurizado" (paro / cámara sellada), solo marca la presión al disparo y, si `reanudar()` ya corrió, arma el timeout. Se quitó la rama muerta de `ejecutar()`. Pruebas: «cancelación con AI vencida, líquido modo 4, presurizada → al volver la AI, contrapresión y lenta cerrada»; «sólido con AI vencida → al volver se arma el timeout»; paro + reanudar; vacío pendiente. |
| R3-M1 | Medio | Real: `_camara_segura_status` usaba `datos_vigentes` (solo DI). | **Corregido** | Usa `ControlLoop.presion_vigente` (DI + AI + estado publicado); falla cerrada. |
| (a) | Alto, anterior a S9 | Real según el revisor (no cambiado). | **PREGUNTA** (transición de ciclo no definida) | Ver pregunta 18. |
| (b) | Medio, anterior a S9 | Real. | **Corregido** (barato, no toca otras transiciones) | `_referencia_atm_configurada()`: sin `presion_admosferica`/`rango_presion_atm` numéricos y positivos el protocolo NO abre el aire atmosférico (sigue usando 101,3/20 kPa para lo demás, sin cambio). |
| (c) | Bajos | Reales. | **Documentados** | Pregunta 19. |

## 4. Pruebas

Siempre con `PYTHONPATH=C:/Users/tecni/Documents/codigo_autoclave/.claude/worktrees/agent-a8977a28ac4adbe26/src`; `autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a8977a28ac4adbe26\src\autoclave\__init__.py`.

- `tests/test_s9_revision_1.py` (nuevo, 59 pruebas): primero en rojo (ImportError del módulo nuevo y luego 10 fallos de backend/i18n), después **59 passed**.
- `tests/test_s9_planta_simulada.py`: **28 passed, 1 skipped** (7 celdas × 4 programas; la omitida es la escritura del informe). Con `S9_ESCRIBIR_INFORME=1`: **29 passed**; tabla regenerada en `docs/informes/tanda9/S9_ensayo_tabla.md`, `ticks_aire_abierto_con_presion=0` en las 28 filas.
- `tests/test_s9_estado_seguro_arranque.py` 47 passed; `tests/test_s9_login_y_causa_qml.py` 5 passed.
- Módulos tocados y sus importadores (`grep -rl` en `tests/` por protocolo_fallo, estado_seguro, coherencia, control_loop, `/io/test/output`, serial_link, sesion_backend, entradas_salidas_controller, salidas_prueba): 132 archivos, cada uno en su propio proceso pytest: **2732 passed, 7 skipped, 0 failed** tras corregir `tests/test_alarmas_catalogo.py` (2 fallos que venían del S9 original: SEN-10 no estaba en las tablas de niveles y plantillas de la prueba; ahora 141 passed). `test_enviar_comando.py` y `test_serial_directo.py` no tienen pruebas (scripts de hardware, «no tests ran»). Cada archivo en su propio proceso: corridos juntos en un solo pytest, `test_c1_ajustes_pyside_sesion.py` (PySide) termina el proceso con código 127 a mitad de la corrida; solo pasa (20 passed) y también en la base, así que es una interacción de Qt entre archivos, ajena a S9.
- Pruebas viejas que fallaban YA en `57b2844` (11, afirmaban lo que D9-1 revierte; el S9 original no las actualizó) y ahora siguen a D9-1: `test_s2_cycle_select.py` (2 → aceptan con estado seguro/recuperación), `test_t2_p1_completado_estado_seguro.py` y `test_t5_estado_seguro.py` (`iniciar(..., origen=...)`), `test_t6_arranque_seguro.py` (sin confirmación al arrancar; modo prueba permitido con recuperación y puertas bloqueadas), `test_t7_apagar_equipo.py` (apaga con estado seguro), `test_v8a_cambio_programa_sin_datos.py` (el estado seguro ya no bloquea el cambio), `test_u1_seguridad_navegacion_qml.py` (D9-1.5: el login no se interrumpe), `test_alarmas_catalogo.py` (SEN-10 en las tablas). Además, por las correcciones: `test_protocolo_fallo_modo_descompresion.py` (aire tras 3 lecturas de vacío), `test_t8_e1_aire_atmosferico_prueba.py` (el lazo ahora sí apaga salidas de puerta en modo prueba; la prueba mira solo el canal del aire), dobles de `test_t6`/`test_s9_estado_seguro_arranque.py` con `edad_ultima_ai` (sin edad = AI vencida).
- **Pasada 2:** `tests/test_s9_revision_2.py` (nuevo, 26 pruebas) primero en rojo (20 fallos), después **26 passed**; `test_s9_revision_1.py` 59 passed (2 ajustadas: lista de salidas con P-a, espera desde la primera DI). Planta simulada con `S9_ESCRIBIR_INFORME=1`: **33 passed** (8 celdas × 4 programas + informe), `ticks_aire_abierto_con_presion=0` en las 32 filas; celda nueva `ai_vencida_en_protocolo`: sin válvulas nuevas, sin terminar el estado seguro y con CIC-10 durante el corte, y termina al volver las tramas. Importadores ampliados (además: ser_puertas, context, backend_doble, descompresion, vigencia_ai): **182 archivos**, cada uno en su propio proceso: 4022 passed, 7 skipped, 3 xfailed y 2 fallos, ambos corregidos después y en verde: `test_i18n.py::test_toda_familia_dinamica_esta_enumerada` (venía del S9 original: la familia `sistema.estado_seguro_causa_` no estaba enumerada; 67 passed) y `test_t2_p2_principal_perdido.py::test_solo_lenta_en_vacio_abre_aire_atmosferico` (R2-B3: aire con la tercera lectura; 18 passed). `test_protocolo_fallo_modo_descompresion.py` ajustada igual (18 passed).
- **Pasada 3:** `tests/test_s9_revision_3.py` (nuevo, 8 pruebas) primero en rojo (5 fallos), después **8 passed**; con las de las pasadas 1 y 2 y `test_s9_estado_seguro_arranque.py`: 140 passed. Planta simulada con `S9_ESCRIBIR_INFORME=1`: **33 passed**, tabla regenerada (sin celda nueva: el disparo con la AI vencida no ocurre en el arranque, que espera la primera AI; lo cubren las pruebas unitarias). Importadores (los de la pasada 2 más los que nombran `/status`): **186 archivos**, cada uno en su propio proceso: 4125 passed, 7 skipped, 3 xfailed y 4 fallos, todos de pruebas que afirmaban el comportamiento anterior y ya ajustadas (40 passed): `test_t4_camara_segura.py` (2; el doble ahora fija `presion_vigente`, R3-M1) y `test_protocolo_fallo_modo_descompresion.py` (2; el doble de configuración ahora trae la referencia atmosférica, (b)).
- No se corrió la suite completa (regla 8).

## 5. DECISIONES SIN CONFIRMAR

1. **SAF-01 (de la sesión principal, tal como está en la revisión):** en modo prueba, mientras el estado seguro esté activo, haya recuperación de arranque pendiente, o `camara_segura.evaluar` dé NO segura (o sin dato): `/io/test/output` RECHAZA encender `abrir_puerta_N`, `desbloqueo_puerta_N` (todas las salidas de apertura/desbloqueo de puertas) y, con estado seguro activo o recuperación pendiente, también `descompresion_rapida`, `descompresion_chaqueta` y `vapor_camara`. Además el lazo las fuerza a cero en cada tick en esas condiciones. Detalles míos dentro de esa decisión: la cámara se evalúa con `presion_vigente` (DI + AI + estado publicado); un error al evaluar bloquea todas; la inversión de D-ES-16 hacia `abrir_puerta_N` también se rechaza; `bloqueo_puerta_N` y `cerrar_puerta_N` no se tocan. Consecuencia: **en el equipo de pruebas sin sensores la apertura de puertas desde Entradas / Salidas queda bloqueada siempre** (cámara sin presión = no segura).
2. TMG-02: la trama AI vencida (> 1,5 s, `_VIGENCIA_DI_SEG`) se trata igual que el transductor sin lectura: CIC-10 de inmediato (la vigencia ya es un filtro temporal) y, fuera del arranque, el paso irreversible a `solo_lenta` de R1-P4 tras 3 ticks (abre la lenta con la presión desconocida, criterio D8-1.2 ya vigente).
3. Pregunta 7 de la revisión: la recuperación de arranque espera la primera trama AI de la conexión hasta 1,5 s antes de decidir (antes, si la primera DI llegaba antes que la primera AI, `pres_camara` era None y arrancaba el protocolo por "sin presión"). Pasado ese plazo sin AI, decide como sin presión (D9-1.4).
4. SAF-03: en la rama de vacío las descompresiones se cierran en el acto y solo la apertura del aire espera 3 lecturas (si se esperaba también para cerrar, la lenta quedaba abierta en vacío 2 ticks; la planta lo detectó).
5. SEN-10 confirmada se reafirma también mientras la coherencia no es evaluable (puerta cerrada, sin datos), para que un reconocimiento de FALLA no la borre con la causa sin verificar.
6. (S9 original) Arranque sin presión y con la cámara a presión real: no se ventea a ciegas (HAZ-S9-02).
7. **R2-M1 (de la sesión principal):** AI vencida o "esperando la primera AI de la conexión" = DATOS NO VIGENTES, igual que la DI vencida: no se abren válvulas nuevas (en particular NO aire comprimido y NO aire atmosférico), las ya abiertas se mantienen, NO cuenta para `_lecturas_principal_perdido` ni para `pasar_a_solo_lenta`, no cuenta ticks seguros; se informa (CIC-10 fuera de ciclo, log en ciclo). El enclavamiento a `solo_lenta` queda solo para el transductor que SÍ manda tramas sin lectura válida. Mío dentro de esa decisión: el aire comprimido se CIERRA (no solo "no se abre"), porque se reafirma en pulsos y abierto sin realimentación es justo la sobrepresión de R2-A1; esto reemplaza mi decisión 2 de la pasada 1.
8. **P-a (de la sesión principal):** con estado seguro activo o recuperación pendiente se bloquean también `aire_comprimido_camara` y el vapor de generador o caldera (`vapor_generador`, `vapor_caldera`) en modo prueba; `vapor_chaqueta` queda permitida.
9. R2-A1 en la fase DESCOMPRESION (modos 4/5): sin aire comprimido con la AI vencida (lo demás de la fase sin cambio).
10. R2-M3: sin ControlLoop construido la presión no es vigente → las puertas no abren por software.
11. R3-A1: la decisión inicial diferida no cuenta como "disparo" para el plazo del modo: el timeout se arma al tomarla (con "abrir") o al reanudar (con "presurizado"), igual que en el disparo normal; el tiempo con la AI vencida no se descuenta del plazo.
12. (b): sin la referencia atmosférica configurada el protocolo no abre el aire atmosférico (la cámara en vacío real queda en vacío hasta configurarla; NO ABRIR sigue porque `camara_segura` también exige la configuración).

## 6. PREGUNTAS PARA CRISTIAN

De los revisores:
1. ¿Hay bloqueo físico de puerta por presión independiente del software?
2. ¿La toma de aire atmosférico tiene antirretorno?
3. D9-1.2: solo se cuenta un paro visto con el protocolo ya activo; un paro pulsado y liberado antes, en el mismo encendido, no exige confirmación en un fallo posterior. ¿Es la lectura buscada?
4. Apagado con el estado seguro activo: ¿en qué estado quedan bloqueo y empaque de puerta sin energía?
5. Líquido en modo 4/5 arrancando presurizado se ventea por la lenta sin contrapresión (HAZ-S9-01). ¿Validado para recipientes sellados?
6. ¿Cuál es el periodo real de las tramas AI/DI del ESP32? (de él depende que 1,5 s sin AI sea un fallo real y no un hueco normal).
7. ¿La primera AI tras la primera DI deja `pres_camara` None unos ticks? Verificado en el código: sí (Units arranca con presión None hasta la primera trama AI). Corregido con la espera de la primera AI (decisión 3); confirmar en banco que no aparece CIC-10 en cada encendido.
8. D9-1.4 "se detiene": ¿la lenta o el aire ya abiertos quedan abiertos (actual) o se cierran?
9. ¿Modo prueba con la cámara sellada (D8-2.10)?

Mías:
10. SAF-01 en el banco sin sensores: ¿se acepta no poder probar `abrir_puerta`/`desbloqueo_puerta` desde Entradas / Salidas, o se quiere una excepción explícita (p. ej. solo con perfil de banco o con confirmación de ingeniero)?
11. ¿Las salidas de vacío (`vacio_camara`, `bomba_vacio`) y `agua_chaqueta` también deben bloquearse en modo prueba con el estado seguro activo? Hoy no (la decisión no las nombra).

De la re-revisión (pasada 2):
12. P-a: con el estado seguro activo, ¿`vapor_chaqueta` debe seguir permitida en modo prueba? (hoy sí: no entra a la cámara).
13. P-b: en modo prueba el ALL_OFF apaga `cerrar_puerta_N` y nadie infla el empaque (`bloquear_on`); ¿la puerta queda retenida mecánicamente con la cámara presurizada?
14. P-c: ¿el empaque se desinfla solo con `bomba_vacio`/`vacio_camara`? Si sí, deberían bloquearse junto con las puertas.
15. P-d: SEN-10 vive solo en memoria; un reinicio con la puerta cerrada la borra. ¿Debe persistir?
16. P-e: periodo real de las tramas AI del ESP32 y retardo de la primera AI tras la conexión (la vigencia es 1,5 s).
17. Mía: con la AI vencida el CIC-10 usa el texto «Sensor de presión de cámara sin lectura…»; ¿se quiere un texto propio («sin datos analógicos de la tarjeta»)?

De la re-revisión (pasada 3):
18. (a) Alto anterior a S9 (TMG-02 en CICLO, `control_loop.py`, paso 5 y `_acumular_f0`): en CICLO, `state_machine.update()` y `_acumular_f0()` no exigen la trama AI vigente; con la DI viva y la AI muerta, ESTERILIZACION puede terminar COMPLETADO y el F0 acumula sobre valores congelados. Propuesta del revisor: tratar la AI vencida como la DI vencida (tolerancia P-3 y aborto). No se cambió: es una transición de ciclo no definida en las decisiones. ¿Se aplica?
19. (c) Bajos: `temp_max_apertura` al cerrar el estado seguro sale solo del programa del protocolo (`estado_seguro.py`, no el menor de todos); S4 `reemplazar_programa` deja fuera el programa original de los programas de seguridad; `_lectura_ai()` se consulta en vivo en el paso 5 (no la toma del inicio del tick). ¿Se corrigen en una etapa aparte?

## 7. Pendientes

- Re-revisión ★ (safety, timing) de la sesión principal sobre este diff (no se lanzaron revisores aquí, por instrucción).
- Banco: C-05 a C-05h (C-05g y C-05h nuevos; C-05h necesita poder suspender solo las tramas `AI:`).
- La tabla índice al inicio de la hoja de banco (fila C-05) no lista los casos C-05b a C-05h.
- TMG-07 sin corregir (cosmético); R2-B5 documentado (los ticks seguros cuentan ticks).

## 8. Puntos de choque

- **Alarma nueva:** SEN-10 (creada por el S9 original; ninguna nueva en las correcciones). Si choca al unir, renumerar en `catalogo.py`, i18n (`alarmas.SEN-10`), `docs/catalogo_alarmas.md`, `registro_riesgos.md`, hoja de banco C-05f y las pruebas S9.
- **i18n** (`es.json`/`en.json`): `sistema.estado_seguro_causa_*`, `alarmas.SEN-10`, `estado_seguro_motivos.sin_presion_camara`, `io.err_puerta_camara_no_segura`, `io.err_salida_estado_seguro`.
- **`control_loop.py`:** recuperación de arranque, `programas_para_seguridad`, `temp_max_tras_ciclo`, `enter_test_mode`, `set_active_cycle`, coherencia en `_tick`, `salidas_prueba_bloqueadas`/`_vigilar_salidas_prueba_seguridad`, `_lectura_ai`/`_secuencia_ai`. B9 también toca este archivo (unir S9 primero).
- **`set_io.py`:** no tocado.
- **`server.py`:** `/status` (`causa`), `/system/shutdown`, `/io/test/output`.
- **`serial_link.py`:** `secuencia_ultima_ai()` nuevo.
- **Bitácora (A9, D9-6):** eventos nuevos `estado_seguro_pausado`, `salida_prueba_cortada`; `estado_seguro_iniciado` lleva `origen`. Revisar contra la lista de "solo lo necesario" de A9.
- **QML compartidos:** `Main.qml`, `SeccionEstadoSeguro.qml`, `PantallaPreciclo.qml`.
- `ui_qml/sesion_backend.py` y `entradas_salidas_controller.py` (códigos de rechazo nuevos).
- `db_manager.py`: no tocado (sin migración).
- Pasada 2: `core/runtime/vigencia_ai.py` (nuevo), `state_machine/cycle_phases/descompresion.py`, `services/domain/puertas/ser_puertas.py`, `backend/context.py` (constructor de `ServicioPuertas`), `tests/backend_doble.py` (lo importan todas las pruebas del backend), `serial_link.py` (`estado_ultima_ai`). `EstadoAutoclave` recibe el atributo `lectura_ai` desde el ControlLoop (sin tocar `status.py`).

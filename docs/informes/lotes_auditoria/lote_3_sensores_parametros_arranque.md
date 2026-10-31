# Auditoría planes vs. código — LOTE 3 (sensores, parámetros y arranque)

- **Fecha:** 2026-10-07
- **Norma:** NTC-IEC 62304:2019 (IEC 62304:2006), Clase C — cláusulas 5.2.6, 5.4.4, 8.2.3, 7.4.
- **Base auditada:** rama `audit/62304-snapshot`, commit **8d1884c** (2026-10-07 21:37, = `dev` e7bccf2 + cambios sin commit). Todas las citas `ruta:línea` se refieren a 8d1884c, salvo las marcadas con el nombre de otra rama.
- **Alcance:**
  - `docs/mis_plans/planeacion_sensores_ciclo.md`
  - `docs/mis_plans/planeacion_arranque_y_modo_sin_bd.md`
  - `docs/mis_plans/planeacion_opciones_parametros_ciclo.md`
  - `docs/mis_plans/planeacion_opciones.md`
  - `docs/plan_modificaciones_adc_ino.md`
- **Modo:** solo lectura. No se corrige ni se propone; no se decide quién tiene razón.
- **Comprobación de la base:** los cuatro planes de `mis_plans` del directorio de `dev` tienen el mismo tamaño en bytes que en 8d1884c.

## Diferencias e7bccf2 → 8d1884c en rutas del lote

```
.../mis_plans/planeacion_arranque_y_modo_sin_bd.md | 198 ++++++
docs/mis_plans/planeacion_opciones.md              | 283 +++++++++
.../planeacion_opciones_parametros_ciclo.md        | 260 ++++++++
docs/mis_plans/planeacion_sensores_ciclo.md        | 216 +++++++
src/autoclave/config/serial_link.json              |  10 +
src/autoclave/core/managers/validacion_config.py   |  33 +
src/autoclave/main.py                              |  23 +-
.../services/domain/logging/db_manager.py          | 197 +++++-
src/autoclave/ui_qml/assets/textos/es.json         |   1 +
src/autoclave/ui_qml/bridge/ui_bridge.py           |  13 +-
.../ui_qml/controllers/login_controller.py         |  12 +-
src/autoclave/ui_qml/domain/permisos_opciones.py   |   6 +-
.../ui_qml/qml/Componentes/BarraSuperior.qml       |  64 +-
src/autoclave/ui_qml/qml/Main.qml                  |   2 +-
src/autoclave/ui_qml/qml/NuevoUsuarioHost.qml      |  52 ++
.../ui_qml/qml/Pantallas/NuevoUsuario.qml          | 675 +++++++++++++++++++++
src/autoclave/ui_qml/qml/Pantallas/Opciones.qml    |   8 +-
.../ui_qml/qml/Pantallas/PantallaCicloEnCurso.qml  |  66 +-
.../ui_qml/qml/Pantallas/PantallaPreciclo.qml      |  58 +-
.../ui_qml/qml/Pruebas/PruebaCicloEnCurso.qml      |   1 +
20 files changed, 2093 insertions(+), 85 deletions(-)
```

---

## planeacion_sensores_ciclo (código @ 8d1884c)

**Estado:**
- El plan se declara **BORRADOR rev. 2, pendiente de aprobación**.
- Fecha: no versionado en `dev`. Modificación del archivo: 2026-10-02 13:35.
- Commits que lo citan: ninguno.
- Otra rama: `feature/roles-sensor-temperatura` (87fca2f, 2026-09-08). Tiene 16 commits que no están en el snapshot y le faltan 36 del snapshot. Implementa roles de sensor con otro modelo, que el plan descarta integrar (S-7).
- Commits posteriores en el área: 8d1884c 2026-10-07 snapshot.

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×17 (hechos de §3 y decisiones que mantienen lo existente):**<ul><li>`cycle_temperature_sensors` `{"1":"temp_camara","2":"temp_ref"}` en los JSON, sin lector;</li><li>`has_liquid_sensor` solo en `mesa_b_lab`/`piso_lab`;</li><li>control y fallas con `temp_camara`;</li><li>F0 con `min(temp_camara, temp_2_camara)` si hay sensor de líquidos (la línea citada en el plan, 198-230, se movió a 251-259);</li><li>`_SENSORES_TEMP_CRITICOS=["temp_camara"]` y vigilancia antes de `fase.update()`;</li><li>`RESET_FALLA` vacía todas las alarmas (OPC-24);</li><li>canales de `map_temp`;</li><li>ADC en 0 o ≥4095 → `None`;</li><li>`temp_ref` está en `lecturas_grafica` y no en `lecturas`;</li><li>ningún código Python lee los YAML `io_enabled`/`io_contract`, e `solids_liquids.yaml:10-11` está mal indentado;</li><li>`ERROR_AI_*` solo con lectura `== 0` (OPC-09);</li><li>F0 no se guarda en `ciclos`;</li><li>el ticket usa `temp_camara`;</li><li>la calibración PySide permite `admin`/`tecnico`;</li><li>la rama tiene máximo 1 referencia, principal opcional con caída a `temp_camara`, sin auditoría ni permisos;</li><li>puertas y apertura automática siguen con `temp_camara` (S-8/RS-07);</li><li>calibración sin cambio de roles (RS-10/C-5).</li></ul> | COINCIDE | factory/instrumental_134.json:6-9; equipment.py:36-50; calentamiento.py:223, 237; esterilizacion.py:190; control_loop.py:251-259; ciclo.py:32-33, 440-460, 474-475; state_machine.py:119-124; falla.py:33-36; status.py:12-19; converters.py:169-174; db_manager.py:35-61, 74-82; solids_liquids.yaml:10-11; preparacion.py:122-139; preparado.py:249-261; cycle_logger.py:379; calibracion_sensor.py:37; ser_puertas.py:51-53; ciclo.py:269; `feature/roles-sensor-temperatura`:cycle_manager.py:70-103, server.py:540-557 | — | — |
| 1 | Instalación actual `equipment_class = "piso"` (§3) | NO VERIFICADO | `installation_profile.json` no está versionado en el repositorio | — | — |
| 2 | S-5: cambian la asignación biomédico, técnico e ingeniero | DIFIERE | `biomedico` ya no es un rol (roles.py:10-23) | plan desactualizado probable (planeacion_backend_autenticacion D25) | SEGURIDAD |
| 3 | S-1/RS-03: el Principal decide control de vapor, fallas, saturación final y ticket | EN OTRA RAMA | `feature/roles-sensor-temperatura` 27b7c37/0674dcb: el vapor se controla con la sonda de **referencia** (`_temp_control`) y las fallas con la principal; semántica distinta de S-1. En el snapshot no existe | — | SEGURIDAD |
| 4 | S-2/§4.3: exactamente 1 Principal y 0-2 Referencias | EN OTRA RAMA | En la rama: máximo 1 referencia y Principal opcional (cycle_manager.py:70-74, 98-101 de esa rama) | — | SEGURIDAD |
| 5 | §4.2: formato `sensor → rol` y migración perezosa | EN OTRA RAMA | En la rama se lee `cycle_temperature_sensors` (cycle_manager.py:151 de esa rama); sin migración perezosa | — | FUNCIONAL |
| 6 | RS-02: `PUT /cycle/sensor-roles`, todo o nada, auditado | EN OTRA RAMA | En la rama: `PATCH /cycle/sensor-roles`, sin auditoría, sin rol, sin guard de estado y escrito con `git_autocommit` (server.py:536-557 de esa rama) | — | SEGURIDAD |
| 7 | RS-04: no tocar F0 hasta aprobar C-1 | EN OTRA RAMA | En la rama, 6b5db35 cambia la base de F0 al sensor principal. En el snapshot F0 no cambió | — | SEGURIDAD |
| 8 | §4.1: módulo `catalogo_sensores` | NO IMPLEMENTADO | `git grep catalogo_sensores` sin resultados | — | FUNCIONAL |
| 9 | §4.4: `ASIGNACION_SENSORES_INVALIDA` bloquea el inicio | NO IMPLEMENTADO | `git grep` sin resultados | — | SEGURIDAD |
| 10 | RS-01: `GET /cycle/sensors` con estados `disponible`/`sin_senal`/`no_instalado` | NO IMPLEMENTADO | No existe en ninguna rama | — | FUNCIONAL |
| 11 | RS-05: `SENSOR_AUSENTE` vigila también los sensores en uso | NO IMPLEMENTADO | Solo `temp_camara`/`pres_camara` (ciclo.py:32-33) | — | SEGURIDAD |
| 12 | RS-06: verificación de asignación y lecturas al iniciar el ciclo | NO IMPLEMENTADO | `/cycle/start` solo mira `LISTO_PARA_CICLO` (server.py:912-930) | — | SEGURIDAD |
| 13 | RS-08: guardar en `ciclos` la asignación, F0 y número de programa; `temp_principal` en `lecturas` | NO IMPLEMENTADO | db_manager.py:35-61 | — | SEGURIDAD |
| 14 | RS-09: `None` como sin señal y sin `TypeError` en las bandas | NO IMPLEMENTADO | preparacion.py:122-139; control_banda.py:18-25 | — | SEGURIDAD |

**Resumen:** 31 afirmaciones: COINCIDE 17 · DIFIERE 1 · NO IMPLEMENTADO 7 · EN OTRA RAMA 5 · NO VERIFICADO 1.

---

## planeacion_arranque_y_modo_sin_bd (código @ 8d1884c)

**Estado:**
- Fecha: no versionado en `dev`. Modificación del archivo: 2026-10-07 09:45. El plan se fecha 2026-10-02 con una actualización del 2026-10-07.
- Commits que lo citan: ninguno.
- Otra rama: el plan menciona la rama `feat/serial-v2-wip`, que **no existe** (`git branch -a`).
- Commits posteriores en el área: 8d1884c (snapshot), e7bccf2, 2d4ffa8.
- **Nota de coherencia:** la actualización del 2026-10-07 anuncia que la tarjeta ESP32 será reemplazada por módulos M31-U con Modbus TCP. `planeacion_protocolo_serial_esp32.md` (LOTE 2) no registra ese cambio.

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×10 (hallazgos vigentes en el código):**<ul><li>ARR-01: `BackendContext` se inicializa al importar `server.py`;</li><li>ARR-02: el ticket de arranque sigue en el `main.py` de tkinter;</li><li>SEN-01: `None` no dispara `ERROR_AI_*`;</li><li>SEN-02: la presión se recorta con `max(0.0, …)`;</li><li>SEN-03: `evaluar_banda` compara `None` sin protección;</li><li>BD-01: `DbManager()` sin protección en el contexto;</li><li>BD-02: `crear_ciclo`, `cerrar_ciclo` e `insertar_lectura` sin try;</li><li>BD-04: consecutivo `MAX(numero_ciclo)+1` con índice no UNIQUE;</li><li>BD-05: sin número de programa en `ciclos`;</li><li>§7.8: host `127.0.0.1`.</li></ul> | COINCIDE | server.py:48; context.py:28-50, 77; main.py:306; preparacion.py:122-139; converters.py:228; control_banda.py:18-25; cycle_logger.py:219, 270, 385; db_manager.py:35-50, 68-70, 305-311; main.py (backend):9, 33 | — | — |
| 1 | Lanzador único que arranca las dos UI y el backend; backend como subproceso (D1, D2, §3) | NO IMPLEMENTADO | "Solo se conecta al backend…; no lo arranca ni lo apaga" (ui_qml/app.py:6-10) | — | FUNCIONAL |
| 2 | Inicialización por etapas con el puerto abierto y endpoint de estado de arranque (ARR-01) | NO IMPLEMENTADO | server.py:48; no existe la ruta | — | SEGURIDAD |
| 3 | Splash de 9 etapas con barra, timeouts y clasificación (§4, §5) | NO IMPLEMENTADO | `reloj_splash` es el reloj de la pantalla de espera (ui_qml/domain/reloj_splash.py:1-15) | — | FUNCIONAL |
| 4 | Etapa 7 "Conectando con módulos de E/S" (Modbus TCP) | NO IMPLEMENTADO | No hay capa Modbus | — | SEGURIDAD |
| 5 | `validar_canal()` única para arranque y supervisión (§6) | NO IMPLEMENTADO | `git grep validar_canal` sin resultados | — | SEGURIDAD |
| 6 | Clasificación de sensores bloqueantes y degradables (§6, D-06) | NO IMPLEMENTADO | `ERROR_AI_*` bloquea por los seis canales de temperatura (preparacion.py:105-139) | — | SEGURIDAD |
| 7 | BD-03: la calibración se escribe, se confirma en git y se recarga antes de auditar | DIFIERE | git ya no existe; la auditoría sigue después de escribir y recargar, sin rollback (server.py:422-448) | plan desactualizado probable (planeacion_backend_autenticacion D9) | SEGURIDAD |
| 8 | BD-06: una base nueva siembra `admin`/`admin1234` | DIFIERE | Siembra `admin` e `ingeniero`, ambos con `debe_cambiar_clave` (db_manager.py:115-126, 618-633) | plan desactualizado probable (D5) | SEGURIDAD |
| 9 | §7.1: `/db/estado` y alarma `OPERANDO_SIN_BD` | NO IMPLEMENTADO | `git grep` sin resultados | — | SEGURIDAD |
| 10 | §7.3: `CycleLogger` protegido con try/except | NO IMPLEMENTADO | cycle_logger.py:219, 270, 385 | — | SEGURIDAD |
| 11 | — | SIN DOCUMENTAR | Protección parcial: las escrituras de gráfica y fases pasan por `_guardar` con try (cycle_logger.py:317, 326-331) | — | FUNCIONAL |
| 12 | §7.4: respaldo JSONL por ciclo | NO IMPLEMENTADO | `git grep respaldo_ciclos` sin resultados | — | SEGURIDAD |
| 13 | §7.5: contador persistente, UUID, UNIQUE, instantánea del programa y marcado de interrumpidos | NO IMPLEMENTADO | db_manager.py:305-311 | — | SEGURIDAD |
| 14 | §7.6: login sin base ("Continuar sin operador") | NO IMPLEMENTADO | login_controller.py:64-87 | — | SEGURIDAD |
| 15 | §7.7: base corrupta renombrada y marca `BD_BLOQUEADA` | NO IMPLEMENTADO | `git grep BD_BLOQUEADA` sin resultados | — | SEGURIDAD |
| 16 | §7.8: el backend es el único custodio; las UI dejan de abrir `DbManager` | NO IMPLEMENTADO | El login QML abre `DbManager` (login_controller.py:28-30, 76). Nuevo usuario ya pasa por el backend (puente.py:34-43) | — | SEGURIDAD |
| 17 | §8: retiro del ejecutable tkinter | NO IMPLEMENTADO | main.py:28; ui/window/main_window.py:7-8 | — | FUNCIONAL |
| 18 | §9.1: fase A respaldada en la rama `feat/serial-v2-wip` | DIFIERE | La rama no existe; el código serial v2 solo está en 8d1884c, sin commit en ninguna rama, y tampoco en `dev` dd8f107 | indeterminado | SEGURIDAD |
| 19 | §3: los ajustes de tiempo del arranque usan `time.monotonic()` | NO VERIFICADO | No existe el arranque nuevo para verificarlo | — | — |

**Resumen:** 29 afirmaciones: COINCIDE 10 · DIFIERE 3 · NO IMPLEMENTADO 14 · SIN DOCUMENTAR 1 · NO VERIFICADO 1.

---

## planeacion_opciones_parametros_ciclo (código @ 8d1884c)

**Estado:**
- El plan se declara BORRADOR rev. 3.1.
- Fecha: no versionado en `dev`. Modificación del archivo: 2026-10-07 09:37.
- Commits que lo citan: 2d4ffa8 2026-10-07 "pantalla OPCIONES (Fase 1, marco)".
- Otra rama: no.
- Commits posteriores en el área: e7bccf2 2026-10-07 "el ingeniero edita OPCIONES en cualquier estado"; 8d1884c.

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×12 (Fase 1, marco):**<ul><li>cajón con 5 entradas técnicas en orden y nombre (U-2);</li><li>QML puro con `m()` (U-3);</li><li>"Próximamente", sin abrir vistas PySide (U-4);</li><li>cajón modal de ~mitad del ancho, fondo atenuado y confirmación al cambiar de sección (U-19);</li><li>el engranaje abre el login QML y luego OPCIONES (U-18);</li><li>barra inferior Salir/Inicio con confirmación (U-5);</li><li>encabezado con campana y engranaje inerte (U-6);</li><li>`puedeVer` en un único módulo (§4.3);</li><li>la sesión expone `usuario`, `nombre` y `rol` (§4.4, Fase 1);</li><li>estados sin sesión, solo lectura y sin secciones (§5.0);</li><li>área táctil de 64 px o más (U-14);</li><li>sin edición en QML antes de la especificación 1 (§7, Fase 3).</li></ul> | COINCIDE | permisos_opciones.py:19, 35-54; es.json:6-20; Opciones.qml:10, 94-97, 110-115, 121-245, 291, 349-365; EncabezadoMenu.qml:20; Main.qml:32-43, 78-80, 184; opciones_controller.py:43-62 | — | — |
| 1 | U-7: las secciones técnicas las ven biomédico, técnico e ingeniero | DIFIERE | Solo técnico e ingeniero (permisos_opciones.py:21, 36-40) | plan desactualizado probable (D25) | FUNCIONAL |
| 2 | U-8/§4.5: edición solo en PREPARACION/PREPARADO; con ciclo en curso, solo lectura | DIFIERE | El ingeniero edita en cualquier estado (permisos_opciones.py:61-72; e7bccf2) | plan desactualizado probable (e7bccf2) | SEGURIDAD |
| 3 | §3 (estado actual): roles con `biomedico` | DIFIERE | roles.py:10-23 | plan desactualizado probable | COSMÉTICO |
| 4 | Pantallas 1 a 4: programa y fase (§5.1), parámetros de la fase (§5.2), ventana de ajuste (§5.3), errores (§5.4), sensores (§5.5) y datos con valor por defecto (§6, §6.1) — 6 afirmaciones (Fases 2 a 4) | NO IMPLEMENTADO | Cada sección muestra solo "Próximamente" (Opciones.qml:191-194) | — | FUNCIONAL |

**Resumen:** 21 afirmaciones: COINCIDE 12 · DIFIERE 3 · NO IMPLEMENTADO 6.

---

## planeacion_opciones (código @ 8d1884c)

**Estado:**
- El plan se declara borrador v4.
- Fecha: no versionado en `dev`. Modificación del archivo: 2026-10-07 14:00.
- Commits que lo citan: ninguno. 2d4ffa8 cita `planeacion_opciones_parametros_ciclo`, no este.
- Otra rama: no.
- Commits posteriores en el área: e7bccf2; 8d1884c.

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×12:**<ul><li>roles A/T/I, biomédico no es rol (§1.1);</li><li>cajón con Salir/Inicio (§1.2);</li><li>"Próximamente" (§1.4);</li><li>textos por clave i18n (§1.6);</li><li>modo prueba técnico e ingeniero (§2);</li><li>`rango_presion_atm` 1-10 kPa (§3.2);</li><li>tabla `audit_log` (§3.9);</li><li>R-02 (presión atmosférica y puertas cerradas para encender);</li><li>R-05 en las escrituras que existen (calibración y parámetros de ciclo);</li><li>no entra en suspensión con ciclo en curso (§6);</li><li>resolución de OPC-02 (guard del modo prueba y bind local);</li><li>calibración V1 de dos puntos con ganancia y offset (§8).</li></ul> | COINCIDE | roles.py:13-23; Opciones.qml:194, 217-227; server.py:404-448, 1119, 1143, 1224-1268; validacion_config.py:13, 25-32; db_manager.py:138-149; standby.py:14, 36; main.py (backend):9 | — | — |
| 1 | §2: Parámetros del sistema en solo lectura para admin | DIFIERE | Admin no ve la sección (permisos_opciones.py:37) | indeterminado | FUNCIONAL |
| 2 | §2: Fecha y hora, Bitácora e Información del sistema para todos los roles | NO IMPLEMENTADO | No existen esas secciones (permisos_opciones.py:35-43) | — | FUNCIONAL |
| 3 | §2: fases del ciclo en solo lectura para técnico y edición para ingeniero | DIFIERE | La interfaz da edición al técnico en PREPARACION/PREPARADO para cualquier sección (permisos_opciones.py:68-72). El backend limita los parámetros de ciclo al ingeniero (server.py:1074) | indeterminado | SEGURIDAD |
| 4 | §2: calibración de sensores solo para ingeniero | DIFIERE | El backend la limita al ingeniero (server.py:399), pero la vista PySide la permite a `admin` y `tecnico` (calibracion_sensor.py:37) | indeterminado | SEGURIDAD |
| 5 | §2/§3.6: Usuarios solo para admin | DIFIERE | El backend también deja crear usuarios al ingeniero (server.py:323; roles.py:28-31). Contradice a `planeacion_backend_autenticacion` D26 | indeterminado (contradicción entre planes) | SEGURIDAD |
| 6 | §3.1: sensores, entradas mostradas y gestión de programas — 3 afirmaciones | NO IMPLEMENTADO | Solo "Próximamente" | — | FUNCIONAL |
| 7 | §3.2: claves nuevas `timeout_chaqueta`, `ciclos_servicio`, `dias_servicio` | NO IMPLEMENTADO | global_params.json:1-16 | — | FUNCIONAL |
| 8 | §3.2: valores objetivo: `tiempo_standby` 10 (0-60), `temp_max_apertura` 80, impresión 10-3600, `timeout_puerta` 5-600 | NO IMPLEMENTADO | JSON: 5 (1-60), 120, 0-3600, 0-3600 (global_params.json:5, 8, 12-15) | — | SEGURIDAD |
| 9 | §3.2: `presion_atmosferica` sin respaldo 101.3 en el código | NO IMPLEMENTADO | global_params.json:3 (`presion_admosferica`); base_fase.py:44 | — | SEGURIDAD |
| 10 | §3.6: tabla `operadores` | NO IMPLEMENTADO | db_manager.py:35-112 | — | FUNCIONAL |
| 11 | §3.9: eventos mínimos de bitácora (contadores, fecha y hora, suspensión, restauración, reasignación de E/S) | NO IMPLEMENTADO | `git grep` sin esos eventos | — | SEGURIDAD |
| 12 | R-01: con ciclo en curso se bloquea todo cambio de configuración | DIFIERE | El ingeniero calibra y edita otros programas en CICLO (server.py:169-171, 418-420, 1087-1094; permisos_opciones.py:61-72) | indeterminado (contradice a `planeacion_backend_autenticacion` D14) | SEGURIDAD |
| 13 | R-03: reasignación de E/S con reautenticación | NO IMPLEMENTADO | — | — | SEGURIDAD |
| 14 | R-04: confirmación y bitácora en reinicio de contadores y restauración | NO IMPLEMENTADO | — | — | FUNCIONAL |
| 15 | §5: calibración atmosférica automática | NO IMPLEMENTADO | `git grep` sin resultados | — | SEGURIDAD |
| 16 | §6: suspensión en el backend (HIBERNACION real, salidas apagadas), con 0 = desactivada | NO IMPLEMENTADO | Vive en el puente QML; un 0 se convierte en 5 min (standby.py:34-45); ningún código transita a HIBERNACION (`git grep set_machine_state(GlobalState.HIBERNACION)` sin resultados) | — | SEGURIDAD |
| 17 | §7 OPC-07/OPC-13: respaldos del código eliminados | NO IMPLEMENTADO | base_fase.py:44, 47; advanced_door.py:397-398 | — | SEGURIDAD |
| 18 | §7 OPC-08: `timeout_puerta` con monotonic | NO IMPLEMENTADO | advanced_door.py:372, 416 | — | SEGURIDAD |
| 19 | §7 OPC-11: lectura en vivo en `ServicioPuertas` | NO IMPLEMENTADO | ser_puertas.py:41-44 | — | SEGURIDAD |
| 20 | §10.2: los cambios se aplican solo en PREPARADO | DIFIERE | Guard "distinto de CICLO", que permite PREPARACION y FALLA (server.py:76) | indeterminado | SEGURIDAD |
| 21 | §3.10: Información del sistema con versión del firmware | NO VERIFICADO | No se revisó `info_equipo.py` | — | — |

**Resumen:** 35 afirmaciones: COINCIDE 12 · DIFIERE 6 · NO IMPLEMENTADO 16 · NO VERIFICADO 1.

Nota: el rango 1-10 kPa de `rango_presion_atm` que el código atribuye a `planeacion_backend_parametros.md` (validacion_config.py:9-10; LOTE 2, PAR 22) sí aparece en este plan, en §3.2.

---

## docs/plan_modificaciones_adc_ino.md (código @ 8d1884c)

**Estado:**
- Fecha: un solo commit, 90eb9e6 (2026-07-28).
- Commits que lo citan: f066b10 (2026-07-24, "reducir ruido de captura ADC segun plan_modificaciones_adc_ino"), **anterior** al commit del plan.
- Otra rama: no.
- Commits posteriores en `Hardware`: 17758bd 2026-07-28 (mover el .ino a su carpeta).

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×10:**<ul><li>`analogReadResolution(12)` y `ADC_11db` en `setup()` (Cambio 1);</li><li>`ADC_SAMPLES 64` (Cambio 2);</li><li>`ADC_SETTLE_US 800` (Cambio 3);</li><li>`ADC_DISCARD 2` con descarte de 50 µs;</li><li>promedio de 64 muestras cada 50 µs;</li><li>selector `((canal & 0x0F) << 8)`;</li><li>`analogMin`/`analogMax` por canal con inicio en 4095/0 (Cambio 4);</li><li>comando `RESET_MINMAX` que responde `OK RESET_MINMAX`;</li><li>`ADC_MS_PER_CH 20`;</li><li>publicación cada 500 ms.</li></ul> | COINCIDE | Comunicacion_esclava_ESP32_V2.ino:20-21, 43-44, 57-60, 120-126, 156-191, 208 | — | — |
| 1 | Cambio 4: permite leer `analogMax - analogMin` por canal sin depender de la trama `AI:` | DIFIERE | El mínimo y el máximo se calculan pero no se publican en ninguna trama (publicarEstados, .ino:207-229) | indeterminado | FUNCIONAL |
| 2 | Fuera de alcance: la presión atmosférica (~74.6 kPa) se resta en la calibración de Python | DIFIERE | `converters.py` no resta ninguna atmósfera (`grep atm\|relativ` sin resultados). `planeacion_opciones.md` §5.5 dice lo contrario: presión absoluta, sin resta en ninguna capa | indeterminado (contradicción entre documentos) | SEGURIDAD |

**Resumen:** 12 afirmaciones: COINCIDE 10 · DIFIERE 2.

### Complemento al LOTE 2 (firmware V2, leído completo en este lote)

Las filas que el LOTE 2 dejó como NO VERIFICADO quedan así, sin modificar ese informe:

- **FW-01 (sin `lastError()`):** COINCIDE (.ino:200-203, sin llamadas a `lastError`).
- **FW-02 (`DO:` publica la variable sombra):** COINCIDE (.ino:225-227).
- **FW-06 (los expansores de salida solo se escriben al recibir un comando):** COINCIDE (.ino:54-55, 91-92, 114-115, 143-146).
- **FW-07 (byte bajo del MUX en 0 y DI49-56 desde `d4`):** COINCIDE (.ino:166, 203, 222).
- **§5.9 (ADC1/GPIO36, 12 bits, 11 dB, 64 muestras):** COINCIDE (.ino:16, 43-44, 156).

---

## 1. Resumen del lote

| Plan | Afirm. | COINCIDE | DIFIERE | NO IMPL. | EN OTRA RAMA | SIN DOC. | NO VERIF. |
|---|---|---|---|---|---|---|---|
| planeacion_sensores_ciclo | 31 | 17 | 1 | 7 | 5 | 0 | 1 |
| planeacion_arranque_y_modo_sin_bd | 29 | 10 | 3 | 14 | 0 | 1 | 1 |
| planeacion_opciones_parametros_ciclo | 21 | 12 | 3 | 6 | 0 | 0 | 0 |
| planeacion_opciones | 35 | 12 | 6 | 16 | 0 | 0 | 1 |
| plan_modificaciones_adc_ino | 12 | 10 | 2 | 0 | 0 | 0 | 0 |
| **Total** | **128** | **61** | **15** | **43** | **5** | **1** | **3** |

## 2. Discrepancias con impacto SEGURIDAD, por criticidad aparente

1. **Sensores desconectados sin detección:**
   - fuera de ciclo, `None` no dispara alarma y las bandas lanzan `TypeError` en cada tick (hallazgos SEN-01 y SEN-03 vigentes, fila COINCIDE de ARR; corrección RS-09 no implementada, SEN 14);
   - un lazo de presión abierto se lee como 0 por el recorte (SEN-02);
   - `validar_canal()` y la clasificación de sensores no existen (ARR 5, 6).
2. **Suspensión:** vive en el puente QML; HIBERNACION nunca se alcanza, las salidas no las apaga el backend y un 0 se convierte en 5 min (OPC 16).
3. **Base de datos:**
   - si falla al abrir, el backend no arranca (BD-01);
   - `crear_ciclo`/`cerrar_ciclo`/`insertar_lectura` no están protegidos (BD-02);
   - sin modo degradado, sin respaldo JSONL ni contador persistente con UNIQUE (ARR 9-15);
   - el login QML sigue abriendo `DbManager` (ARR 16).
4. **Ediciones con ciclo en curso:** R-01 de `planeacion_opciones`, U-8 de `planeacion_opciones_parametros_ciclo` y §10.2 piden bloquear; el código y `planeacion_backend_autenticacion` (D14) dejan editar al ingeniero (OPC 12, 20; OPP 2). Es una contradicción entre planes.
5. **Matriz de permisos frente al código y a otros planes:**
   - Usuarios: solo admin en el plan, también ingeniero en el backend (OPC 5);
   - calibración: solo ingeniero en el plan, admin/técnico en PySide (OPC 4);
   - fases: solo lectura para el técnico en el plan, edición en la interfaz (OPC 3).
6. **Presión absoluta o relativa:** el plan ADC dice restar la atmósfera en Python; `planeacion_opciones` dice no restar en ninguna capa; el código no resta (ADC 2).
7. **Código serial v2 sin respaldo en ninguna rama**, contra lo que dice el plan de arranque (ARR 18).
8. **Roles de sensor en `feature/roles-sensor-temperatura`:**
   - otra semántica: el vapor se controla con la referencia;
   - escritura sin auditoría ni permisos;
   - cambio de la base de F0 sin la decisión C-1 (SEN 3-7).
9. **Respaldos `or 101.3`/`or 20.0`, copias de configuración en `ServicioPuertas` y `time.time()` en `timeout_puerta`** (OPC 17-19).
10. **Valores objetivo de §3.2 no aplicados** (p. ej. `temp_max_apertura` 120 frente a 80 en el plan) (OPC 8).
11. **Inicio de ciclo sin verificación de asignación ni de sensores en uso** (SEN 9, 11, 12); sin registro de asignación, F0 ni programa en `ciclos` (SEN 13).
12. **Hallazgos desactualizados en el plan de arranque:** BD-03 (calibración no atómica, sin git) y BD-06 (semillas) (ARR 7, 8).

## 3. Qué no se pudo verificar y por qué

- **`installation_profile.json`:** no está versionado. No se confirma `equipment_class = "piso"`.
- **Arranque nuevo:** no existe, así que no se verifica el uso de `time.monotonic()` en él.
- **`info_equipo.py`:** no se revisó (información del sistema y versión del firmware).
- **Pruebas no ejecutadas:** no se corrió pytest (`test_opciones_*.py`, `test_permisos_opciones.py`, `test_reloj_splash*.py`). No se califica la verificación de cambios (8.2.3).
- **QML:** no se ejecutó. Las afirmaciones visuales (tamaños, colores, atenuación) se verificaron solo por lectura del código, no por captura.
- **Ruido real del ADC:** no se midió en hardware el pico a pico después del Cambio 1-3 (checklist del plan ADC).
- **Rama `feature/roles-sensor-temperatura`:** se leyó solo lo necesario para ubicar la implementación; no se auditó completa.

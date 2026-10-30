# Auditoría planes vs. código — LOTE 1 (proceso y seguridad)

- **Fecha:** 2026-10-07
- **Norma:** NTC-IEC 62304:2019 (IEC 62304:2006), Clase C — cláusulas 5.2.6, 5.4.4, 8.2.3, 7.4.
- **Base auditada:** rama `audit/62304-snapshot`, commit **8d1884c** (2026-10-07 21:37, = `dev` e7bccf2 + cambios sin commit). Todas las citas `ruta:línea` se refieren a 8d1884c.
- **Alcance:** `docs/mis_plans/planeacion_fase_calentamiento.md`, `planeacion_fase_esterilizacion.md`, `planeacion_f0.md`, `docs/catalogo_alarmas.md`.
- **Modo:** solo lectura. No se corrige ni se propone; no se decide quién tiene razón.

## Diferencias e7bccf2 → 8d1884c en rutas del lote

(`git diff --stat e7bccf2 audit/62304-snapshot` sobre state_machine, cycles, core/runtime, control_loop, logging, backend, installation y los 4 documentos; sin interpretar)

```
src/autoclave/backend/autenticacion.py             | 117 ++++
src/autoclave/backend/context.py                   |  25 +-
src/autoclave/backend/contrasenas.py               |  53 ++
src/autoclave/backend/main.py                      |   6 +-
src/autoclave/backend/server.py                    | 699 +++++++++++++++++----
.../services/domain/logging/db_manager.py          | 197 +++++-
src/autoclave/services/domain/loop/control_loop.py | 142 +++--
7 files changed, 1060 insertions(+), 179 deletions(-)
```

---

## planeacion_fase_calentamiento (código @ 8d1884c)

**Estado:**
- Fechas del plan: primer commit 2c7a05d (2026-07-28), último 6cdd984 (2026-08-05 00:12).
- Commits que lo citan: d15f801 (2026-07-28, rediseño de CALENTAMIENTO).
- Otra rama: `feature/roles-sensor-temperatura` (27b7c37, sensor por rol).
- Commits posteriores en el área:
  - cee1cc4 2026-08-05 16:25 reemplazar APROXIMACION/PWM_ACTIVO por controlador continuo
  - e6a8999 2026-08-05 funciones puras de duty
  - c6d59ab 2026-08-06 escalar piso duty_estable
  - 93b33dc 2026-09-02 migrar a time.monotonic()
  - 410109f 2026-10-01 eliminar fase PURGA

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×23:** los 13 parámetros de la tabla con su defecto, mínimo, máximo y unidad (§2); tasa no produce FALLO (§3, §6); escapes de dos estados, incluidos los casos borde off=0 y on=0 (§4.2, §4.3); entrada a ESTABLE con T≥t_obj Y P≥P_obj (§5); ventana continua con reinicio y timeout de recuperación (§5); tiempo_estable=0 completa en el mismo tick (§5); timeout global instantáneo (§6); FALLO apaga 3 salidas (§6); salidas y HAL (§1, §7); temperatura_calentamiento es independiente (§1); los parámetros obsoletos ya no existen (§1, §9) | COINCIDE | factory/instrumental_134.json:55-67; calentamiento.py:170-200, 226, 234-235, 158-168, 203, 360-367, 374-379, 383-404, 388; `git grep` de los obsoletos sin resultados | — | — |
| 1 | Pipeline `PRECAL→PURGA→PRE_VACIO→CAL→ESTER` (§1) | DIFIERE | ciclo.py:78-85: PRECAL, PREVACIO, CAL, ESTER, DESCOMP, SECADO; no hay PURGA | plan desactualizado probable (410109f) | FUNCIONAL |
| 2 | La sección tiene 13 parámetros (§1, §2, §9) | DIFIERE | El código lee 15; también `rango_temp_estabilizacion` y `timeout_recuperacion_estabilizacion` (calentamiento.py:216-217; json:68-69). Los §3 y §5 del plan sí los usan | plan desactualizado probable (6cdd984 actualizó solo una parte) | SEGURIDAD |
| 3 | `rango_calentamiento` [kPa] es la banda alrededor de P_sat(T_actual) que da entrada a PWM (§2 fila 5 y notas) | DIFIERE | Se usa como margen de proximidad y sobrepaso contra los objetivos fijos, tanto para temperatura (°C) como para presión (kPa) (calentamiento.py:288-301) | plan desactualizado probable (cee1cc4) | SEGURIDAD |
| 4 | `factor_calentamiento` = % OFF de un PWM fijo (§2 fila 4, §4.1) | DIFIERE | Define `duty_estable = 1 - factor/100`, el piso del término de proximidad (calentamiento.py:287, 302) | plan desactualizado probable (cee1cc4) | SEGURIDAD |
| 5 | La tasa actúa como bang-bang por tick, solo en APROXIMACION (§3, §4.1) | DIFIERE | El duty es proporcional `tasa_max/tasa_actual`, rige en toda la fase y mide sobre una ventana de 10 s (calentamiento.py:79, 84-90, 251-265, 282-285) | plan desactualizado probable (cee1cc4) | SEGURIDAD |
| 6 | Máquina interna de 3 tramos APROXIMACION→PWM_ACTIVO→ESTABLE, sin retorno (§3, §4.1) | DIFIERE | 2 tramos: RAMPA (duty continuo) y ESTABLE_PREESTERILIZACION (calentamiento.py:9-53, 304-381) | plan desactualizado probable (cee1cc4) | SEGURIDAD |
| 7 | Se entra a PWM cuando `\|P−P_sat(T)\| ≤ rango_calentamiento` (§4.1) | DIFIERE | No existe esa condición en el código (calentamiento.py:267-357) | plan desactualizado probable | SEGURIDAD |
| 8 | Los tres lazos son independientes de T/P en cada tick (§4.4) | DIFIERE | Si T o P es None, la fase retorna antes de actualizar los escapes, que se quedan en su último estado (calentamiento.py:239-240 frente a 360-367) | indeterminado | FUNCIONAL |
| 9 | `dentro_rango` simétrico: `\|T−t_obj\|≤rango_temp_estab` Y `\|P−P_obj\|≤presion_add` (§3, §5) | DIFIERE | Solo un lado: `t_obj ≤ T ≤ t_obj+rango` Y `p_obj ≤ P ≤ p_obj+p_add` (calentamiento.py:381) | indeterminado | SEGURIDAD |
| 10 | Los temporizadores usan `time.time()` (§5, §6) | DIFIERE | Usan `time.monotonic()` (calentamiento.py:226, 234, 242) | plan desactualizado probable (93b33dc) | SEGURIDAD |
| 11 | Con sensor None la fase devuelve EN_CURSO y "el timeout global eventualmente lo captura" (§8) | DIFIERE | Si temp_camara es None al entrar, el timeout no se arma (calentamiento.py:222-226). El timeout solo existe a partir de la primera lectura válida | indeterminado | SEGURIDAD |
| 12 | Sensor de líquido secundario pendiente (§1, §9) | EN OTRA RAMA | `feature/roles-sensor-temperatura` 27b7c37: `_temp_control()` y `_principal_en_saturacion()` en calentamiento.py | — | SEGURIDAD |
| 13 | — | SIN DOCUMENTAR | Corte `duty_calidad_vapor`: con T≥97% de t_obj sin presión de saturación, duty=0; no aplica en ESTABLE (calentamiento.py:81, 116-125, 304-307) | — | SEGURIDAD |
| 14 | — | SIN DOCUMENTAR | Techo independiente `P ≥ p_obj+p_add` fuerza duty=0 (calentamiento.py:311-313) | — | SEGURIDAD |
| 15 | — | SIN DOCUMENTAR | `_duty_por_sobrepaso` reduce el piso hacia 0 cuando se pasa el objetivo (calentamiento.py:102-113, 298-302) | — | SEGURIDAD |
| 16 | — | SIN DOCUMENTAR | Con `intervalo_segmentos_calor ≤ 0` el duty se aplica directo, sin PWM (calentamiento.py:338-350) | — | FUNCIONAL |
| 17 | — | SIN DOCUMENTAR | El patrón `or <defecto>` cambia un valor configurado en 0: `rango_temp_estabilizacion=0` se vuelve 1.0, aunque el JSON permite mínimo 0 (calentamiento.py:216; json:68) | — | SEGURIDAD |
| 18 | — | SIN DOCUMENTAR | A nivel CicloState, si `temp_camara` o `pres_camara` es None se aborta con SENSOR_AUSENTE (ciclo.py:32-33, 440-460) | — | SEGURIDAD |

**Resumen:** 42 afirmaciones: COINCIDE 23 · DIFIERE 11 · EN OTRA RAMA 1 · SIN DOCUMENTAR 7 (13-18 son 6 filas; la fila 13 incluye también la ventana de 10 s de la fila 5).

---

## planeacion_fase_esterilizacion (código @ 8d1884c)

**Estado:**
- Fechas del plan: primer commit 69438a6 (2026-07-28), último 6cdd984 (2026-08-05 00:12).
- Commits que lo citan: 69438a6.
- Otra rama: `feature/roles-sensor-temperatura` (0674dcb).
- Commits posteriores en el área:
  - 0477fd1 2026-08-05 11:17 RECUPERACION también por caída de presión
  - c4b64ab 2026-08-06 relación brecha_segura/error_presion
  - 2f59198 2026-08-06 F0
  - 93b33dc 2026-09-02 monotonic
  - 410109f 2026-10-01 eliminar PURGA

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×30:** los 14 parámetros de la tabla con valor, mínimo y máximo en los perfiles factory (§2); RECUPERACION = vapor ON continuo; banda fija [−2,+1] kPa sobre P_sat(T_actual) con ON y OFF forzados; dentro de banda, PWM con factor% OFF; techo `P_control_max`; transición bidireccional en cada tick (§4.1); escapes de dos estados (§4.2, §4.3); timer de finalización fijado al iniciar, sin pausa (§5); los 4 umbrales de falla contra t_est fijo; debounce 3; FALLO apaga 3 salidas; sensor None → EN_CURSO (§6); RTC excluido; parámetros obsoletos ausentes (§1, §9) | COINCIDE | factory/instrumental_134.json:73-86, factory/bowe_dick.json:88-89; esterilizacion.py:47-49, 78-88, 90-120, 126-152, 174, 179-180, 190-193, 198-232, 241-260, 268 | — | — |
| 1 | Pipeline `…→CAL→ESTER→(fin de ciclo)` (§1) | DIFIERE | Después vienen DESCOMPRESION y SECADO (ciclo.py:82-84) | indeterminado | FUNCIONAL |
| 2 | La sección tiene 14 parámetros (§1, §2, §9) | DIFIERE | El código lee 15, también `brecha_segura_presion` (esterilizacion.py:163; json:87) | plan desactualizado probable (0477fd1, c4b64ab) | SEGURIDAD |
| 3 | Defecto `presion_add_esterilizacion=11` e `intervalo_segmentos_ester=3` (§2 filas 8 y 9) | DIFIERE | Los 3 perfiles `user/*.json` traen 9.0 y 2 (user/*.json:399, 406). Los factory coinciden | indeterminado (commits "actualizar parametros (auto)" del 2026-08-06) | SEGURIDAD |
| 4 | RECUPERACION ⇔ `T < t_est + brecha_segura_temperatura` (§2 fila 12, §3) | DIFIERE | `T < t_est+brecha_seg` **O** `P < P_sat(t_est) − brecha_segura_presion` (esterilizacion.py:241-244) | plan desactualizado probable (0477fd1) | SEGURIDAD |
| 5 | Los lazos son independientes de T/P (§4.4) | DIFIERE | Con sensor None se retorna antes de actualizar los escapes (esterilizacion.py:192-193 frente a 253-260) | indeterminado | FUNCIONAL |
| 6 | `COMPLETADO` cuando `time.time() ≥ _timer_fin` (§5) | DIFIERE | `time.monotonic()` (esterilizacion.py:180, 195, 268) | plan desactualizado probable (93b33dc) | SEGURIDAD |
| 7 | El tiempo es la única condición de éxito (§5) | DIFIERE | Con `F0=true` también exige `f0_acumulado ≥ F0_objetivo` (esterilizacion.py:270-284) | plan desactualizado probable (2f59198) | SEGURIDAD |
| 8 | No existe timeout de fase (§1, §8) | DIFIERE | Con `F0=true` hay un timeout de 2×tiempo que lleva a FALLO (esterilizacion.py:181-182, 286-290) | plan desactualizado probable (2f59198) | SEGURIDAD |
| 9 | Viene de CALENTAMIENTO tras ESTABLE_PREESTERILIZACION (§1) | DIFIERE | El comentario de cabecera dice "viene ya validada de ESTABILIZACION" (esterilizacion.py:6-7) | indeterminado | COSMÉTICO |
| 10 | Sensor `None` sin mitigación; la mitigación quedaría en CicloState, fuera de alcance (§8) | SIN DOCUMENTAR | CicloState aborta con SENSOR_AUSENTE si `temp_camara` o `pres_camara` es None (ciclo.py:32-33, 440-460) | — | SEGURIDAD |
| 11 | Sensor secundario pendiente (§1, §9) | EN OTRA RAMA | `feature/roles-sensor-temperatura` 0674dcb: fallas por sonda principal, PWM por sonda de control | — | SEGURIDAD |
| 12 | `tiempo_esterilizacion` mínimo 0 (§2 fila 6) | SIN DOCUMENTAR | `or 3.5` convierte un 0 configurado en 3.5 min (esterilizacion.py:156) | — | SEGURIDAD |

**Resumen:** 42 afirmaciones: COINCIDE 30 · DIFIERE 9 · EN OTRA RAMA 1 · SIN DOCUMENTAR 2.

---

## planeacion_f0 (código @ 8d1884c)

**Estado:**
- Fechas del plan: un solo commit, 2f59198 (2026-08-06), que trae plan y código juntos.
- Commits que citan el nombre: ninguno.
- Otra rama: `feature/roles-sensor-temperatura` (6b5db35).
- Commits posteriores en el área:
  - 410109f 2026-10-01 eliminar PURGA
  - 8d1884c 2026-10-07 snapshot (control_loop: RLock, bloqueo por configuración)

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| 1 | Pipeline `…PURGA…ESTABILIZACION…SECADO→DESCOMPRESION` (§1) | DIFIERE | No hay PURGA ni ESTABILIZACION, y el orden es DESCOMP→SECADO (ciclo.py:78-85) | plan desactualizado probable (la fusión es del 2026-08-05; 410109f) | FUNCIONAL |
| 2 | Acumula en {CALENTAMIENTO, ESTABILIZACION, ESTERILIZACION} (§4) | COINCIDE | control_loop.py:23, 239 | — | — |
| 3 | Se detiene al terminar ESTER; no acumula en SECADO ni DESCOMP (§1) | COINCIDE | control_loop.py:23, 242-244 | — | — |
| 4 | `cap.has_liquid_sensor` "ya usado en EsterilizacionFase" (§1) | DIFIERE | esterilizacion.py no usa `cap`; solo lo usa control_loop.py:255 | indeterminado | COSMÉTICO |
| 5 | Existe la clave `sensores_temp["temp_2_camara"]` (§1) | COINCIDE | status.py:14 | — | — |
| 6 | `estado.f0_acumulado: float = 0.0` (§1, §8) | COINCIDE | status.py:118 | — | — |
| 7 | `F0` bool, defecto false (§2) | COINCIDE | factory/instrumental_134.json:12 y los 5 perfiles | — | — |
| 8 | `F0_objetivo` 12, rango 0-60, en todos los perfiles (§2, §8) | COINCIDE | factory/*.json:13; user/*.json:16. El plan sigue marcando el rango "propuesto — confirmar" (§2, §10.1) | — | — |
| 9 | Timeout = 2×tiempo, sin parámetro en el perfil (§2, §6.1) | COINCIDE | esterilizacion.py:181-182 | — | — |
| 10 | `10**((T−121.1)/10)·dt`, z y T_ref fijos (§3) | COINCIDE | letalidad.py:4-11 | — | — |
| 11 | Ubicación de la función "a definir" (§3, §10.2) | COINCIDE | Resuelto en `letalidad.py`; el plan no lo registra como cerrado | — | — |
| 12 | `dt_min` real, no el intervalo nominal (§3) | COINCIDE | control_loop.py:246-261 | — | — |
| 13 | Paso en `_tick()` después de `estado.update` (§4) | COINCIDE | control_loop.py:156, 214-216 | — | — |
| 14 | Tres condiciones de ejecución (§4) | COINCIDE | control_loop.py:237-241 | — | — |
| 15 | T_ref = min(T1,T2) con degradación a T1 (§4) | COINCIDE | control_loop.py:255-259 | — | — |
| 16 | `temp_camara` None no acumula ni lanza excepción (§4) | COINCIDE | control_loop.py:251-253 | — | — |
| 17 | El primer tick inicializa sin sumar (§4) | COINCIDE | control_loop.py:246-249 | — | — |
| 18 | Reset de `f0_acumulado` en `CicloState.reset()` junto a `motivo_fallo` (§5) | COINCIDE | ciclo.py:109-110 | — | — |
| 19 | `_f0_ultimo_tick` se resetea en CicloState.reset o al detectar CALENTAMIENTO con f0==0 (§5) | DIFIERE | Se resetea a None cada vez que falla una condición; ninguna de las dos opciones del plan (control_loop.py:242-244) | indeterminado (mismo commit) | SEGURIDAD |
| 20 | Timeout armado al iniciar, junto a `_timer_fin` (§6.1) | COINCIDE | esterilizacion.py:179-183 | — | — |
| 21 | FALLO con `alarm_id="ESTERILIZACION_TIMEOUT_F0"`; `_fallo(id, msg)` (§6.1, §6.2) | DIFIERE | `_fallo(mensaje)` recibe solo texto (prefijo en el mensaje); la alarma que se emite es `FALLO_ESTERILIZACION` (esterilizacion.py:84-88, 287-290; ciclo.py:499-510) | indeterminado (mismo commit) | SEGURIDAD |
| 22 | Fin con tiempo Y F0; completar se evalúa antes que el timeout (§6.2) | COINCIDE | esterilizacion.py:277-292 | — | — |
| 23 | Con F0=false, el comportamiento no cambia (§1, §6.2) | COINCIDE | esterilizacion.py:270-275 | — | — |
| 24 | Pseudocódigo con `time.time()` (§6.2) | DIFIERE | `time.monotonic()` (esterilizacion.py:180, 182, 195) | plan desactualizado probable (93b33dc) | SEGURIDAD |
| 25 | Las validaciones TEMP/PRES no se tocan (§6.3) | COINCIDE | esterilizacion.py:198-232 | — | — |
| 26 | Línea "F0 total: {:.1f} min" en el ticket solo si F0 (§7) | COINCIDE | cycle_logger.py:273-284; ticket_formatter.py:64-65, 80-81 | — | — |
| 27 | Los 8 archivos afectados existen con el cambio descrito (§8) | COINCIDE | Archivos citados en las filas 6, 10, 13, 18, 20 y 26 | — | — |
| 28 | — | SIN DOCUMENTAR | Si falta `F0_objetivo`, `or 0.0` deja el objetivo en 0 y el criterio se cumple siempre (esterilizacion.py:171) | — | SEGURIDAD |
| 29 | — | SIN DOCUMENTAR | Los ticks sin conexión (control_loop.py:152-153) o con bloqueo por configuración (171-175) retornan antes de `_acumular_f0` sin poner `_f0_ultimo_tick` en None. Al volver, `dt_min` incluye el hueco (la tolerancia de desconexión es 5 s, :37) | — | SEGURIDAD |
| 30 | T_ref por sensor (§4) | EN OTRA RAMA | `feature/roles-sensor-temperatura` 6b5db35: "F0 acumula contra el sensor principal… en vez de has_liquid_sensor+min" (distinto del plan) | — | SEGURIDAD |

**Resumen:** 30 afirmaciones: COINCIDE 22 · DIFIERE 5 · EN OTRA RAMA 1 · SIN DOCUMENTAR 2.

---

## docs/catalogo_alarmas.md (código @ 8d1884c)

**Estado:**
- Fechas del documento: un solo commit, 041f35b (2026-09-29); el encabezado dice "Generado 2026-09-18".
- Commits que lo citan: ninguno.
- Otra rama: `alarmas-parte-a` excluida por instrucción.
- Commits posteriores en el área:
  - aede91a 2026-09-29 unificar TEMP_DRENAJE_ALTA
  - 410109f 2026-10-01 eliminar PURGA
  - 8d1884c 2026-10-07 snapshot (backend/context.py)

| # | Afirmación del catálogo (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| 1 | PARO_EMERGENCIA en PREPARADO/PREPARACION: recuperable **no** | DIFIERE | Los helpers `alarm()` fijan `recoverable=True` (preparado.py:37, 48; preparacion.py:57, 65) | indeterminado | SEGURIDAD |
| 2 | SUMINISTRO_VAPOR ALERTA, no bloqueante | COINCIDE | preparado.py:103; preparacion.py:182 | — | — |
| 3 | CHAQUETA_FRIA temporizada en PREPARADO, inmediata en PREPARACION | COINCIDE | preparado.py:120-121, 196-201; preparacion.py:199-201 | — | — |
| 4 | CHAQUETA_SOBRECALENTADA "solo en PREPARADO" | DIFIERE | También se genera en PREPARACION (preparacion.py:205-207) | indeterminado | SEGURIDAD |
| 5 | TEMP_DRENAJE_ALTA en `obj+rango`, temporizada / inmediata | COINCIDE | preparado.py:186-187; preparacion.py:279-281; control_banda.py:19, 24 | — | — |
| 6 | PRESION_CAMARA_BAJA/ALTA en atm±rango | COINCIDE | preparado.py:140-161; preparacion.py:220-244 | — | — |
| 7 | PUERTA_1/2_ABIERTA en PREPARADO | COINCIDE | preparado.py:211-219 | — | — |
| 8 | AGUA_RESIDUAL_CAMARA en PREPARACION | COINCIDE | preparacion.py:252-258 | — | — |
| 9 | SUMINISTRO_ELECTRICO en PREPARADO | COINCIDE | preparado.py:277-281 | — | — |
| 10 | ERROR_AI_<SENSOR>, lista fija en PREPARACION y todos los sensores en PREPARADO | COINCIDE | preparacion.py:105-139; preparado.py:249-261 | — | — |
| 11 | SUMINISTRO_<SERVICIO> con lista fija | COINCIDE | preparado.py:268-274; preparacion.py:144-158 | — | — |
| 12 | CICLO PARO_EMERGENCIA EMERGENCIA, no recuperable | COINCIDE | ciclo.py:395-401 | — | — |
| 13 | FALLO_SUMINISTRO_ELECTRICO | COINCIDE | ciclo.py:411-417 | — | — |
| 14 | FALLO_PUERTA_x_ABIERTA FALLA, recuperable | COINCIDE | ciclo.py:143-144, 428-434 | — | — |
| 15 | FALLO_PUERTA_x_EMPAQUE con < 0.6×presion_empaque | COINCIDE | ciclo.py:136, 146-148 | — | — |
| 16 | SENSOR_AUSENTE para temp_camara/pres_camara | COINCIDE | ciclo.py:32-33, 440-457 | — | — |
| 17 | FALLO_CONEXION: recuperable **no** | DIFIERE | `recoverable=True` (ciclo.py:537-543) | indeterminado | SEGURIDAD |
| 18 | FALLO_<FASE> incluye `PURGA` | DIFIERE | No existe la fase PURGA; los nombres son PRECALENTAMIENTO, PRE_VACIO, CALENTAMIENTO, ESTERILIZACION, DESCOMPRESION, SECADO (ciclo.py:78-85; `name=` de cada fase). El resto de la fila coincide (ciclo.py:499-510) | plan desactualizado probable (410109f) | FUNCIONAL |
| 19 | SUMINISTRO_VAPOR en CICLO | COINCIDE | ciclo.py:161-173 | — | — |
| 20 | TEMP_DRENAJE_ALTA en CICLO, no bloqueante, debounce 3 | COINCIDE | ciclo.py:34, 200-219 | — | — |
| 21 | TIMEOUT_APERTURA_AUTOMATICA, una vez | COINCIDE | ciclo.py:279-294 | — | — |
| 22 | APERTURA_AUTOMATICA_DENEGADA a los 60 s, reintento cada 5 s | COINCIDE | ciclo.py:35-36, 314-335 | — | — |
| 23 | NO_HAY_CONEXION "fuera de un ciclo en curso" | DIFIERE | Se reporta en cualquier estado; durante un ciclo se suma FALLO_CONEXION a los 5 s (control_loop.py:107-119, 134-137). Los flags FALLA, bloqueante y recuperable sí coinciden | indeterminado | SEGURIDAD |
| 24 | ABRIENDO_MODO_SEGURO_<nombre> | COINCIDE | advanced_door.py:376-382 | — | — |
| 25 | CERRANDO_MODO_SEGURO_<nombre> | COINCIDE | advanced_door.py:465-471 | — | — |
| 26 | PARO_EMERGENCIA en FALLA/HIBERNACION, no recuperable | COINCIDE | falla.py:23-28; hibernacion.py:18-23 | — | — |
| 27 | `report()` deduplica por id | COINCIDE | alarm_manager.py:19-21 | — | — |
| 28 | No hay catálogo central; los ids son literales | COINCIDE | `git grep alarm_id=` en src/ | — | — |
| 29 | `blocks_operation` vale True por defecto | COINCIDE | alarm.py:12 | — | — |
| 30 | "Recuperable = puede auto-limpiarse" (Cómo leer) | DIFIERE | Solo se auto-limpian las ALERTA recuperables; una FALLA o EMERGENCIA recuperable no (alarm.py:25-33; alarm_manager.py:45-50) | indeterminado | FUNCIONAL |
| 31 | — | SIN DOCUMENTAR | `CONFIGURACION_INVALIDA` FALLA, no recuperable, bloqueante, `source_state="ARRANQUE"` (backend/context.py:115-122). Solo existe en 8d1884c; no está en e7bccf2 | — | SEGURIDAD |
| 32 | — | SIN DOCUMENTAR | En PREPARADO, PRESION_CAMARA_BAJA/ALTA también son temporizadas (preparado.py:155, 161) | — | FUNCIONAL |
| 33 | — | SIN DOCUMENTAR | Un solo `timer_estabilidad` se comparte entre todas las alarmas temporizadas de PREPARADO (preparado.py:21, 196-201) | — | FUNCIONAL |
| 34 | — | SIN DOCUMENTAR | Para FALLO_PUERTA_x_EMPAQUE, si falta `presion_empaque` se usa 300; con sensor de empaque None no hay chequeo (ciclo.py:136, 147) | — | SEGURIDAD |

**Resumen:** 34 afirmaciones: COINCIDE 24 · DIFIERE 6 · SIN DOCUMENTAR 4.

---

## 1. Resumen del lote

| Plan | Afirm. | COINCIDE | DIFIERE | NO IMPL. | EN OTRA RAMA | SIN DOC. | NO VERIF. |
|---|---|---|---|---|---|---|---|
| planeacion_fase_calentamiento | 42 | 23 | 11 | 0 | 1 | 7 | 0 |
| planeacion_fase_esterilizacion | 42 | 30 | 9 | 0 | 1 | 2 | 0 |
| planeacion_f0 | 30 | 22 | 5 | 0 | 1 | 2 | 0 |
| catalogo_alarmas.md | 34 | 24 | 6 | 0 | 0 | 4 | 0 |
| **Total** | **148** | **99** | **31** | **0** | **3** | **15** | **0** |

## 2. Discrepancias con impacto SEGURIDAD, por criticidad aparente

1. **Algoritmo de CALENTAMIENTO:** el plan describe un control de 3 tramos (APROXIMACION bang-bang → PWM por banda de P_sat(T) → ESTABLE). El código usa un duty continuo con 3 términos más un techo, y cambia el significado de `rango_calentamiento`, `factor_calentamiento` y la tasa. Ver CAL 3-7.
2. **Tres mecanismos de CALENTAMIENTO que limitan el vapor no están en el plan:** el corte por calidad de vapor al 97%, el techo `p_obj+p_add` y el escalado por sobrepaso (CAL 13-15).
3. **Criterio de banda de ESTABLE_PREESTERILIZACION:** el plan lo define simétrico (±) y el código lo aplica solo por encima del objetivo (CAL 9).
4. **Disparo de RECUPERACION en ESTERILIZACION:** el código también dispara por presión (`brecha_segura_presion`), parámetro que no está en el plan (EST 2, 4).
5. **CALENTAMIENTO sin timeout si `temp_camara` es None al entrar:** el plan afirma que el timeout global lo captura (CAL 11). A nivel ciclo existe SENSOR_AUSENTE (CAL 18).
6. **Valores en 0 que el código reemplaza:** `tiempo_esterilizacion=0` se vuelve 3.5 min y `rango_temp_estabilizacion=0` se vuelve 1.0, aunque el rango del perfil permite 0 (EST 12, CAL 17).
7. **F0 con huecos de enlace:** tras ticks sin conexión o con bloqueo, `dt_min` incluye el tiempo del hueco (F0 29). Si falta `F0_objetivo`, el objetivo queda en 0 (F0 28).
8. **Reset de `_f0_ultimo_tick`:** el mecanismo del código no es ninguna de las dos opciones del plan (F0 19).
9. **Timeout de F0 sin alarma propia:** el plan pide `alarm_id="ESTERILIZACION_TIMEOUT_F0"`; el código emite `FALLO_ESTERILIZACION` con el motivo en texto (F0 21).
10. **Recuperabilidad distinta al catálogo:** `FALLO_CONEXION` y `PARO_EMERGENCIA` (en PREPARADO y PREPARACION) tienen `recoverable=True`; el catálogo dice "no" (CAT 1, 17).
11. **NO_HAY_CONEXION se reporta también durante el ciclo**, al contrario de lo que dice el catálogo (CAT 23).
12. **Perfiles `user/`:** `presion_add_esterilizacion=9` e `intervalo=2`, frente a 11 y 3 del plan (EST 3).
13. **CHAQUETA_SOBRECALENTADA en PREPARACION** no figura en el catálogo (CAT 4).
14. **CONFIGURACION_INVALIDA** (solo en el snapshot) no figura en el catálogo (CAT 31). FALLO_PUERTA_x_EMPAQUE usa 300 si falta `presion_empaque` y no verifica con sensor None (CAT 34).
15. **Relojes:** los planes dicen `time.time()` y el código usa `time.monotonic()` (CAL 10, EST 6, F0 24).
16. **Funcionalidad de sensor secundario por rol** existe solo en `feature/roles-sensor-temperatura` y difiere del modelo de los planes (CAL 12, EST 11, F0 30).

## 3. Qué no se pudo verificar y por qué

- **Specs referenciadas:** no se leyeron las specs de `docs/superpowers/specs/` que citan los planes y el código (control continuo, fusión, tasa solo control). Están fuera del lote, así que no se confirmó si documentan lo marcado como SIN DOCUMENTAR.
- **Excel de origen:** no está disponible para validar los nombres "Excel" de las tablas.
- **Pruebas no ejecutadas:** no se corrió pytest. Sin evidencia de pruebas no se califica la verificación de las modificaciones (8.2.3).
- **Comportamiento en ejecución:** no se ejecutó el código. La duración real del tick, la cuantización del sensor y el efecto del duty sobre la válvula no están observados.
- **Filas FMEA:** de la prosa del FMEA (§8) solo se verificaron las afirmaciones de detección o control que tienen código. Las causas y los efectos son prosa y no se califican.
- **`alarmas-parte-a`:** no se revisó, por instrucción. No se sabe si ahí existe un catálogo central o otra severidad.
- **Severidad 1-4 de `ui_qml/domain/alarmas.py`:** no se verificó; el propio catálogo la declara fuera de su alcance.

**Fuera del lote, sin calificar:** `advanced_door.py:372, 462` usa `time.time()` para `timeout_puerta`, y CLAUDE.md exige `time.monotonic()` para los timers de proceso.

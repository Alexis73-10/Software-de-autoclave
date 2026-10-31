# Etapa 3 (T-17): copia del programa al iniciar el ciclo y regla de fases pendientes

**Fecha:** 2026-10-10 · **Rama:** `dev` (sobre `3c5968e`) · **Suite:** 2236 en verde · **Sin commit.**
**Spec:** `planeacion_backend_autenticacion.md` v7, §5.8 y criterio 11c.
**Evaluación previa IEC 62304:** Clase C (parámetros de esterilización y F0); sin solicitud de cambio formal (NRM-02); sin fichero de riesgos (NRM-01). Se invalidan y se repitieron: unitarias de CicloState/ControlLoop/CycleLogger, endpoints de parámetros y progreso, regresión completa.

## Qué se hizo
- **Copia profunda** (`Cycle.copia()`, `cycle_manager.py`): al entrar en CICLO, `CicloState.reset()` copia el programa almacenado; las fases, el protocolo de fallo y el propio `CicloState` (chaqueta, válvula de reposo, apertura automática) leen la copia.
- **Regla de fases pendientes** (`CicloState.aplicar_si_fase_pendiente`): un cambio del ingeniero en CICLO se guarda siempre en el programa almacenado; llega también a la copia solo si la fase de esa sección **aún no ha iniciado**. La fase actual y las terminadas cuentan como iniciadas; con el ciclo terminado (esperando confirmación o en el protocolo de fallo) nada se aplica. Mapa de secciones: `estabilizacion`→CALENTAMIENTO; `globals`, `finalizacion` y cualquier otra → "Global" (siempre desde el siguiente ciclo).
- **Backend** (`PATCH /cycle/parameter`): se quita el 409 provisional `programa_en_curso`. La decisión corre bajo `_sm_lock` (`ControlLoop.aplicar_a_ciclo_en_curso`). La respuesta y `audit_log` indican `aplica`: `"en_curso"` o `"siguiente"`. Otro programa en CICLO: siempre `"siguiente"` (5b).
- **Otros lectores durante el ciclo** pasan a la copia (`ControlLoop.programa_en_ejecucion()`): acumulación de F0, cabecera y pie del ticket (`CycleLogger`), fases que aplican en `/cycle/current/progress`.

## Revisiones (safety-reviewer, timing-auditor)

**Corregido:**

| Id | Sev. | Hallazgo | Corrección |
|---|---|---|---|
| SAF-01 / TMG-02 | Alta | La entrada a CICLO (y la copia) corría un tick después del cambio de estado; en ese tick el registro del ciclo leía la copia del ciclo anterior: cabecera del ticket con temperatura/tiempo de esterilización viejos si se editaron en PREPARADO. Regresión introducida por T-17 | `StateMachine` ejecuta la entrada a CICLO en el mismo tick de la transición, bajo `_sm_lock` |
| SAF-03 / TMG-04 | Baja | En ese mismo tick, un PATCH podía responder `"siguiente"` para un cambio que sí rige el ciclo que arranca; el progreso podía usar la copia vieja 0,5 s | Misma corrección |
| TMG-01 | Alta | `DescompresionFase.reset()` fijaba `modo` al iniciar el ciclo: un cambio de modo con la fase pendiente se informaba como aplicado, la fase corría con el viejo y el protocolo de fallo / válvula de reposo con el nuevo | El modo se lee al iniciar la fase. Las demás fases no guardan parámetros en `reset()` (verificado) |

| SAF-02 | Media | `set_param` solo validaba tipo/mín/máx: dos cambios que deben ir juntos podían quedar repartidos si la fase iniciaba entre ambos | **Decisión de Cristian:** `temperatura_calentamiento` y `temperatura_esterilizacion` deben ser iguales; editar una ajusta la otra en la misma operación (`_VINCULADOS`, `cycle_manager.py`), validando ambas (si una queda fuera de rango, no cambia ninguna). En CICLO solo llegan a la copia si **las dos** fases están pendientes; si CALENTAMIENTO ya inició, ambas rigen desde el siguiente ciclo. `audit_log` registra la pareja en `detalle.vinculados`. Se retiró la relación `brecha_segura_presion < brecha_error_presion` (premisa equivocada, ver preguntas). |

**No corregido:**
- **TMG-03 (Media, previo) — se aborda aparte (decisión de Cristian):** `_save_cycle_json` trunca y reescribe el JSON del programa; un corte de luz a mitad lo deja corrupto y al arrancar se descarta en silencio (`print`). Propuesta: escritura atómica (temporal + `os.replace`) y registro de error al cargar.
- La vista PySide de parámetros actualiza en local solo el parámetro editado, no su pareja (además, hoy recibe 401 por no enviar token).
- Los programas `factory` se pueden editar en memoria (no se guardan); previo a T-17.
- **UI:** la spec pide que la UI muestre si el cambio aplicó al ciclo en curso. Hoy ninguna UI con token edita parámetros: la vista PySide llama sin token (401 desde la etapa 1) y la edición QML está en OPCIONES fase 2 (bloqueada). Queda el campo `aplica` en la respuesta para cuando exista.

## Preguntas abiertas
1. **Brechas de presión de ESTERILIZACION (aclaración de Cristian):** `brecha_error_presion` es cuánto puede bajar la presión por debajo de la de esterilización antes del fallo (p. ej. 304 kPa a 134 °C con 2 kPa → hasta 302 kPa); `brecha_segura_presion` es la banda **hacia arriba** donde debe mantenerse la presión. El código actual (`esterilizacion.py:9-13`, y CLAUDE.md) la usa **hacia abajo**: RECUPERACION si `P < P_sat(T_est) − brecha_segura_presion`. No lo cambié: es la lógica de control de la fase que esteriliza y necesita tu definición:
   - ¿RECUPERACION debe activarse con `P < P_sat(T_est) + brecha_segura_presion` (vapor a fondo hasta subir por encima de la banda)?
   - "El valor por defecto siempre será 0": ¿de cuál de las dos brechas, y en qué perfiles? Hoy todos traen `brecha_error_presion = 2.0` y `brecha_segura_presion = 1.5`.
   - ¿Aplica lo mismo a las brechas de temperatura (`brecha_segura_temperatura` 0,3 hacia arriba, `brecha_error_temperatura` 0,1 hacia abajo, que ya funcionan así)?
2. **`despresurizacion`:** se quitó del mapa y de los 3 programas `user`, donde estaba vacía. Corrección a lo que dije antes: en `factory/bowe_dick.json` **no** está vacía, trae `tipo_despresurizacion`, `tiempo_despresurizacion` y `rango_presion_despresurizacion`, que ningún código lee. No la toqué: ¿se quita también? Mientras exista, un cambio en ella durante un ciclo se trata como "Global" (rige desde el siguiente). La spec v7 (§5.8) aún la menciona.

## Pruebas
- Nueva: `test_t17_copia_programa.py` (19 pruebas, varias parametrizadas; incluye parámetros vinculados): copia al entrar, 11c, siguiente ciclo, fases pendientes/iniciadas/terminadas, secciones globales, ciclo terminado, copia en el mismo tick, modo de descompresión.
- Ajustadas: `test_backend_autenticacion.py` (409 provisional → 3 pruebas de §5.8, más parámetro vinculado auditado), dobles del programa con `copia()` en `test_ciclo_*`, `test_control_loop_f0.py`, `test_backend_ciclo_en_curso_endpoints.py`.

## Verificación
Sin cambio visual. Verificación sugerida en banco con backend real: iniciar un ciclo, editar `secado.tiempo_secado` durante CALENTAMIENTO (respuesta `aplica: "en_curso"`, el secado usa el nuevo valor) y `calentamiento.*` (respuesta `"siguiente"`, la fase no cambia). Requiere un cliente con token de ingeniero (curl), porque ninguna UI lo envía todavía.

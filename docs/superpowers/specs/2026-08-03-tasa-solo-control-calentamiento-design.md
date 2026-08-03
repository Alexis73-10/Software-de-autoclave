# Remover FALLO por tasa en CALENTAMIENTO — solo control

**Proyecto:** Software-de-autoclave (Especifika S.A.S.)
**Alcance:** Modificación puntual de `src/autoclave/state_machine/cycle_phases/calentamiento.py`. Sigue directamente al cambio anterior (`docs/superpowers/specs/2026-08-03-tasa-control-calentamiento-design.md`), aún sin mergear (PR #28, rama `tasa-control-calentamiento`) — este documento amplía esa spec, no la reemplaza.

---

## 1. Cambio de decisión

La spec anterior decidió explícitamente que `tasa_calentamiento`/`tasa_presion` sirvieran **a la vez** de techo de control (bang-bang en `APROXIMACION`) y de umbral de FALLO (debounce de 3 lecturas, sin cambios respecto al código previo al rediseño). Esa decisión se revierte parcialmente: **`tasa_calentamiento`/`tasa_presion` pasan a ser exclusivamente parámetros de control.** El camino de FALLO por pendiente excesiva se elimina por completo — no se reemplaza por un umbral separado, ni se conserva con otro nombre.

El mecanismo de control del paso 5 (bang-bang directo por tick, sin tiempo mínimo de apagado, solo limita la dirección de subida en temperatura) **no cambia**. Ver la spec anterior para el detalle completo de esa lógica.

## 2. Riesgo aceptado (decisión explícita, confirmada por el usuario)

Sin el chequeo de FALLO, si la válvula `vapor_camara` no responde al comando OFF (ej. atascada abierta, actuador dañado) y la tasa real de temperatura o presión sigue subiendo sin control, **no hay ningún aborto automático por esa causa específica**. El único respaldo que queda activo es `timeout_calentamiento` (timer global de fase), que detecta "demasiado lento" pero no "demasiado rápido".

Esto es una decisión de diseño explícita, confirmada por el usuario, no una omisión. Se documenta en la FMEA (sección 8 del plan de fase) como riesgo aceptado, siguiendo el mismo patrón ya usado en este documento para otras decisiones similares (ej. `ESTABLE_PREESTERILIZACION` sin timer de recuperación).

## 3. Alcance del cambio de código

- Ningún parámetro nuevo ni eliminado de los perfiles JSON — `tasa_calentamiento`/`tasa_presion` siguen existiendo con los mismos rangos, solo cambia su rol documentado.
- `_DEBOUNCE_LECTURAS` (constante del módulo) y los contadores `_contador_exceso_temp`/`_contador_exceso_pres` (atributos de instancia) se eliminan por completo — tras quitar el chequeo de falla por tasa, nada más en `calentamiento.py` los usa.
- El cálculo de `tasa_t`/`tasa_p` (paso 3) se conserva sin cambios de fórmula — sigue alimentando el control del paso 5 — pero pierde el bloque que incrementaba contadores y llamaba a `self._fallo(...)`.
- El paso 5 (control bang-bang) no se toca — ya no dependía del resultado del chequeo de falla, solo de `tasa_t`/`tasa_p`/`tasa_t_max`/`tasa_p_max`.
- `PWM_ACTIVO`, `ESTABLE_PREESTERILIZACION`, el timeout global, y el resto de la fase no cambian.

## 4. Pseudocódigo del cambio (paso 3 de `update()`)

Reemplaza el bloque actual (que incluye el chequeo de falla) por:

```python
# ── 3. Cálculo de pendiente ──────────────────────────────────────
# tasa_t/tasa_p alimentan el control de vapor_camara en APROXIMACION
# (paso 5). Ya no disparan FALLO — ver spec de remoción de FALLO
# (docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md);
# riesgo aceptado si vapor_camara no responde al comando OFF.
tasa_t = None
tasa_p = None
if self._t_tick_anterior is not None:
    dt_min = (now - self._t_tick_anterior) / 60
    if dt_min > 0:
        tasa_t = (temp - self._temp_anterior) / dt_min
        tasa_p = (pres - self._pres_anterior) / dt_min

self._temp_anterior = temp
self._pres_anterior = pres
self._t_tick_anterior = now
```

`reset()` pierde las líneas que inicializan `_contador_exceso_temp`/`_contador_exceso_pres` a 0. La constante `_DEBOUNCE_LECTURAS = 3` (módulo) se elimina.

## 5. Casos de prueba a cubrir (actualización de `tests/test_calentamiento_fase.py`)

**Se eliminan** (validaban el camino de FALLO que ya no existe):
- `test_tasa_calentamiento_no_falla_con_1_o_2_lecturas_excesivas`
- `test_tasa_calentamiento_falla_al_tercer_exceso_consecutivo`
- `test_tasa_calentamiento_bidireccional_detecta_caida_abrupta`
- `test_tasa_presion_falla_al_tercer_exceso_consecutivo`
- `test_tasa_deshabilitada_con_cero_no_falla_por_salto_grande` (su premisa — que deshabilitar evita un FALLO espurio — ya no aplica, porque ningún valor de tasa produce FALLO)
- `test_aproximacion_bangbang_apaga_valvula_en_cada_tick_antes_del_debounce_de_fallo` (su nombre y premisa — "antes del debounce de fallo" — dejan de tener sentido; el comportamiento de control que verificaba queda cubierto por los tests de bang-bang existentes)

**Se agrega:**
- Un test que fuerza 10 ticks consecutivos con tasa de temperatura Y presión muy por encima del límite, y verifica que en ninguno de ellos el resultado es `FaseResult.FALLO` (solo `EN_CURSO`, con `vapor_camara_off` llamado en cada tick) — la regresión que prueba que la remoción del camino de FALLO es completa, no solo que tardaba más en dispararse.

**Se mantienen sin cambios** (siguen siendo válidos, no dependen del camino de FALLO):
- Los 8 tests de bang-bang restantes (`test_aproximacion_bangbang_on_*`, `_off_si_*`, `_vuelve_a_on_*`, `_tasa_*_deshabilitada`, `_no_apaga_por_caida_abrupta_*`).
- `test_pwm_activo_ignora_tasa_calentamiento_excedida`.
- Todos los tests de `PWM_ACTIVO`, escapes, finalización, timeout global, sensores `None`.

## 6. Documentación a actualizar (`docs/mis_plans/planeacion_fase_calentamiento.md`)

- **Sección 2** (tabla de parámetros), filas 6 y 7: el rol pasa de `"Setpoint de control (...) + umbral de falla (debounce 3 lecturas)"` a `"Setpoint de control (techo de subida en APROXIMACION, bang-bang de vapor_camara)"` — sin la parte de falla.
- **Sección 3**: la frase `"El chequeo de tasa_calentamiento / tasa_presion (con debounce de 3 lecturas) corre también en paralelo... y puede producir FALLO desde cualquier tramo"` se elimina — ya no es cierta. La nota de "Actualización (control por tasa en APROXIMACION)" existente se mantiene (sigue describiendo el control correctamente) pero se le quita cualquier referencia a que ese cálculo también dispara FALLO.
- **Sección 6** ("Condiciones de FALLO"): se eliminan las filas "Exceso pendiente temperatura" y "Exceso pendiente presión" de la tabla, junto con el párrafo "Justificación del debounce de 3 lecturas" que las acompañaba (queda huérfano — no hay más debounce en esta fase).
- **Sección 8** (FMEA): las filas "Todo tramo | Sobrepresión..." y "Todo tramo | Rampa de temperatura anómala..." pierden su columna "Detección" (`tasa_presion`/`tasa_calentamiento` con debounce de 3 lecturas) — pasa a `"Ninguna a nivel de esta fase (riesgo aceptado — ver sección 2 de docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md)"`. Sus columnas "Prevención/control" (`FALLO` + apagado de salidas) pasan a reflejar que ya no hay apagado automático por esta vía — solo el control por tasa en `APROXIMACION`, que no cubre `PWM_ACTIVO`.

## 7. Integración

El PR #28 (`tasa-control-calentamiento` → `dev`) sigue abierto y sin mergear — este cambio se agrega como commits nuevos a esa misma rama (es la misma feature, aún sin revisar), no como PR separado. Al finalizar, se hace fast-forward de `dev` local a la nueva punta de la rama, igual que en el ciclo anterior.

## 8. Fuera de alcance

- Cualquier umbral de FALLO alternativo o de respaldo para pendiente excesiva — se decidió explícitamente no agregar ninguno.
- Cambios a `PWM_ACTIVO`, `ESTABLE_PREESTERILIZACION`, el timeout global, o cualquier otra fase.
- Cambios a los perfiles JSON (parámetros, rangos, defaults).

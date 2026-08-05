# Fusión de ESTABILIZACION en CALENTAMIENTO — diseño

**Proyecto:** Software-de-autoclave (Especifika S.A.S.)
**Alcance:** Eliminar la fase `ESTABILIZACION` del pipeline de ciclo. Su función de sostenimiento pasa a vivir dentro del tramo `ESTABLE_PREESTERILIZACION` de `CalentamientoFase`, rediseñado para esperar convergencia real (no tiempo fijo) antes de entregar control a `ESTERILIZACION`.

---

## 1. Problema

CALENTAMIENTO entrega control a ESTERILIZACION con presión visiblemente alta — inercia térmica (chaqueta/paredes calientes) hace que la temperatura y presión sigan subiendo después de cruzar el setpoint, y ninguna de las dos fases del pipeline actual espera a que esa inercia se disipe antes de avanzar:

- El tramo `ESTABLE_PREESTERILIZACION` de `calentamiento.py` arma un timer fijo (`tiempo_estable_preesterilizacion`, 3s por defecto) desde el primer instante en que `temp >= t_obj and pres >= p_obj`, y **nunca lo reinicia** aunque la presión siga subiendo durante el sostenimiento — es un riesgo aceptado documentado explícitamente en el diseño anterior.
- `EstabilizacionFase` repite el mismo patrón de timer fijo (mismo parámetro, mismo valor), y su chequeo de "dentro de rango" solo verifica que la presión sea consistente con la saturación a la **temperatura actual** (que puede estar igualmente inflada por la inercia) — nunca compara contra el objetivo real `p_obj`.
- Los parámetros que usa `EstabilizacionFase` (`tiempo_estable_preesterilizacion`, `rango_temp_estabilizacion`, `presion_add_calentamiento`, `timeout_recuperacion_estabilizacion`) viven todos en la sección `calentamiento` del perfil — nunca existió una sección `estabilizacion` real en los perfiles activos (`instrumental_134.json`). `bowe_dick.json` sí tiene una sección `estabilizacion` huérfana con otros nombres de clave (`tiempo_estabilizacion`, `temperatura_estabilizacion`, ...) que ningún código lee — cruft de un diseño anterior.
- La UI (`cycle_window.py`, `cycle_buffer.py`) ya referencia esa sección `estabilizacion.*` inexistente en mapeos de fase — dead code que nunca resolvió correctamente.

Conclusión: ESTABILIZACION como fase separada no aporta una responsabilidad propia distinta de CALENTAMIENTO — es una duplicación parcial y desalineada de sus parámetros. Se fusiona.

---

## 2. Decisión de diseño

- Pipeline nuevo: `... → CALENTAMIENTO → ESTERILIZACION → ...` (se quita ESTABILIZACION).
- El tramo `ESTABLE_PREESTERILIZACION` de CALENTAMIENTO pasa de "timer fijo desde el primer cruce" a "timer que exige una ventana **continua** dentro de banda respecto a los objetivos fijos (`t_obj`, `p_obj`), reiniciándose cada vez que sale de banda". Esto es lo que efectivamente resuelve el problema: mientras la presión esté por encima de la banda tolerada, el conteo no avanza — la fase espera a que la inercia se disipe (vía escape lento + ausencia de nueva inyección de vapor) antes de completar.
- Se preserva un timeout de recuperación dedicado (mismo rol que tenía en `EstabilizacionFase`) para no perder el diagnóstico específico "no logró estabilizar" frente al timeout general de calentamiento.
- Ningún parámetro cambia de sección JSON — todos ya viven en `calentamiento`.

---

## 3. Máquina de estados del tramo `ESTABLE_PREESTERILIZACION`

```
PWM_ACTIVO ──(temp >= t_obj Y pres >= p_obj)──► ESTABLE_PREESTERILIZACION
                                                   │
                                                   │  _timer_recuperacion_fin = None (sin armar aún)
                                                   ▼
                                     ┌─────────────────────────────┐
                                     │  cada tick:                  │
                                     │  dentro_rango =               │
                                     │    t_obj <= temp <= t_obj + rango_temp_estabilizacion
                                     │    Y p_obj <= pres <= p_obj + presion_add_calentamiento
                                     └─────────────────────────────┘
                                                   │
                          ┌────────────────────────┴────────────────────────┐
                          │ dentro_rango = True                              │ dentro_rango = False
                          ▼                                                   ▼
        _timer_recuperacion_fin = None (cancela cualquier cuenta         si _timer_recuperacion_fin is None:
        regresiva de recuperación pendiente)                                 _timer_recuperacion_fin = now + timeout_recuperacion_estabilizacion*60
        _timer_sostenido_desde arrancado (si None)                       _timer_sostenido_desde = None (reinicio)
        si now - _timer_sostenido_desde >= tiempo_estable_preesterilizacion  fase_en_sostenimiento = False
          → COMPLETADO                                                    si now > _timer_recuperacion_fin → FALLO
        fase_en_sostenimiento = True
```

- `vapor_camara` sigue en PWM_ACTIVO con el mismo duty cycle (`factor_calentamiento` / `intervalo_segmentos_calor`), sin cambios — no hay control activo adicional para "bajar" la presión, solo se deja de premiar el cruce instantáneo.
- `descompresion_lenta` / `descompresion_rapida` siguen sus temporizadores de dos estados independientes, sin cambios.
- No hay retroceso a `APROXIMACION` ni a `PWM_ACTIVO` una vez alcanzado `ESTABLE_PREESTERILIZACION` — solo se reinicia el conteo interno del tramo.

---

## 4. Parámetros (sin cambios de sección, todos en `calentamiento`)

| Parámetro | Rol nuevo |
|---|---|
| `tiempo_estable_preesterilizacion` | Duración de la ventana **continua** dentro de banda requerida para completar |
| `rango_temp_estabilizacion` | Tolerancia de `temp` **por encima** de `t_obj` para `dentro_rango` (banda de un solo lado — ver corrección debajo) |
| `presion_add_calentamiento` | Doble rol: define `p_obj = P_sat(t_obj) + presion_add_calentamiento` (sin cambio) y ahora también el ancho de tolerancia de `pres` **por encima** de `p_obj` para `dentro_rango` |
| `timeout_recuperacion_estabilizacion` | Timeout dedicado: si nunca se logra una ventana continua dentro de este tiempo, `FALLO` específico |

Ningún parámetro nuevo. Ninguna migración de sección JSON.

---

## 5. Fallas

| Condición | Acción |
|---|---|
| `_timer_recuperacion_fin` armado (fuera de banda de forma continua) y `now > _timer_recuperacion_fin` | `FALLO` — motivo: "Calentamiento: no se logró sostener condición estable en Xs". El timer se cancela (`None`) apenas vuelve a estar dentro de banda — mismo patrón que `EstabilizacionFase._timer_recuperacion` en el diseño anterior. |
| `timeout_calentamiento` global excedido (sin cambios, cubre toda la fase) | `FALLO` — motivo existente, sin cambios |

Al entrar en `FALLO` se apagan las mismas tres salidas de siempre (`vapor_camara`, `descompresion_lenta`, `descompresion_rapida`) — sin I/O nuevo.

---

## 6. Impacto en orquestación (`ciclo.py`)

- Quitar `EstabilizacionFase` de `_fases` (línea 73) y su import (línea 25).
- Pipeline resultante: `PRECALENTAMIENTO → PURGA → PRE_VACIO → CALENTAMIENTO → ESTERILIZACION → SECADO → DESCOMPRESION`.

## 7. Impacto en UI de configuración (`params_ciclo.py`)

Sin cambios. Los tabs "Calentamiento" y "Estabilización" ya filtran distintas claves dentro de la misma sección `calentamiento` (`_CAL_MAIN_KEYS` / `_CAL_ESTAB_KEYS`) — la separación visual para el operador se mantiene igual aunque el motor de fases fusione la lógica.

## 8. Limpieza de mapeos muertos

Estas referencias a `estabilizacion.*` (sección que nunca existió en perfiles activos) se eliminan junto con la fase:

- `src/autoclave/ui/cycle/cycle_window.py:47` — entrada `"ESTABILIZACION"` en `_FASE_TEMP_TARGET`.
- `src/autoclave/ui/cycle/data/cycle_buffer.py:21` — entrada `"ESTABILIZACION"` en `FASE_DURACION_PARAM`.
- `src/autoclave/services/domain/logging/cycle_logger.py:49,64` — entrada `"ESTABILIZACION"` en `_FASE_A_CODIGO` y `_FASES_EN_CURSO`; corregir comentario de cabecera (línea 16). Nota: hoy `_FASE_A_CODIGO["ESTABILIZACION"] = "E"` (Exhaust/End) contradice el propio comentario del archivo (debería ser "H"/Heating) — un bug latente en el código de ticket impreso que desaparece al quitar la fase.

**Fuera de alcance:** la sección JSON `"estabilizacion"` huérfana en `bowe_dick.json` (factory y user) no se toca — ningún código la lee, y el archivo parece gestionado por un proceso externo de auto-actualización (commits recurrentes "chore: actualizar parametros de ciclo bowe_dick (auto)").

## 9. Tests

- Eliminar `tests/test_estabilizacion_fase.py`.
- Ampliar `tests/test_calentamiento_fase.py` con:
  - Completa solo tras ventana continua de `tiempo_estable_preesterilizacion` segundos dentro de banda.
  - El conteo se reinicia si `pres` (o `temp`) sale de banda a mitad del sostenimiento — caso central que motivó este rediseño (overshoot por inercia).
  - `FALLO` dedicado si nunca se logra una ventana continua dentro de `timeout_recuperacion_estabilizacion`.
  - `fase_en_sostenimiento` alterna `True`/`False` correctamente en cada reinicio.
- Revisar `tests/test_control_loop_desconexion_ciclo.py` (modificado en el working tree actual) por si asume índices o nombres de fase que incluyan ESTABILIZACION.

## 10. Documentación a actualizar

- `CLAUDE.md`: diagrama de secuencia de fases, lista de fases (quitar bullet de `estabilizacion.py`), agregar nota de rediseño (estilo la sección existente de ESTERILIZACION) documentando el motivo.
- `docs/mis_plans/planeacion_fase_calentamiento.md`: reescribir secciones 1, 3, 5 y 8 (máquina de estados, condición de finalización, FMEA) con la lógica de ventana continua.
- `docs/mis_plans/planeacion_fase_esterilizacion.md`: actualizar diagrama de pipeline (línea 25) y referencia a "salir de ESTABILIZACION" (línea 30) → "salir de CALENTAMIENTO".

---

## 11. Riesgos aceptados / fuera de alcance

- No hay control activo de venteo rápido si la presión se pasa de banda durante el sostenimiento — se sigue confiando en `descompresion_lenta` + ausencia de nueva inyección de vapor para que baje pasivamente. Si en comisionamiento se observa que esto tarda demasiado (choca seguido con el timeout de recuperación), la mitigación sería abrir `descompresion_rapida` como parte del tramo — explícitamente fuera de este alcance salvo que se solicite.
- **Recuperación pasiva también por debajo de banda.** `EstabilizacionFase` (fase eliminada) hacía recuperación activa: `vapor_camara` en ON continuo mientras `temp < t_obj`. El tramo fusionado no reproduce ese control — `vapor_camara` sigue en el duty cycle normal de `PWM_ACTIVO` (paso 5 de `calentamiento.py`) sin importar cuán lejos esté por debajo del objetivo; solo cambia la condición de finalización (sección 3), no el control de la válvula. Si en comisionamiento se observa que el timeout de recuperación dispara con frecuencia por este motivo, la mitigación sería forzar `vapor_camara` ON continuo por debajo de banda dentro del tramo — explícitamente fuera de este alcance salvo que se solicite.
- No se toca la sección JSON huérfana `estabilizacion` de `bowe_dick.json` (ver sección 8).

### Corrección post-revisión (2026-08-05): banda de un solo lado

La revisión final de la implementación encontró que la fórmula original de `dentro_rango` en las secciones 3-4 de este documento era **simétrica** (`|temp - t_obj| <= rango_temp_estabilizacion`, `|pres - p_obj| <= presion_add_calentamiento`), heredada sin querer de una lectura descuidada de "banda de tolerancia". Eso permitía completar el tramo con `temp`/`pres` **por debajo** del objetivo — contradiciendo la condición de entrada al tramo (`temp >= t_obj Y pres >= p_obj`) y, más grave, entregando a ESTERILIZACION con margen insuficiente: esa fase falla por temperatura/presión baja con solo `brecha_error_temperatura=0.1°C` / `brecha_error_presion=2kPa` de tolerancia y 3 ticks de debounce (~1.5s) — un handoff por debajo del setpoint aborta el ciclo casi de inmediato.

Corregido a banda de un solo lado en `calentamiento.py:224`:

```python
dentro_rango = t_obj <= temp <= t_obj + rango_temp_estab and p_obj <= pres <= p_obj + p_add
```

Tolera overshoot por encima del objetivo (el propósito de este tramo) pero nunca acepta una lectura por debajo — consistente con la condición de entrada. Ver `tests/test_calentamiento_fase.py::test_sostenimiento_no_completa_si_temp_cae_por_debajo_del_objetivo` y `::test_sostenimiento_no_completa_si_presion_cae_por_debajo_del_objetivo` (regresión). Las secciones 3-4 de arriba ya reflejan la fórmula corregida.
- Sensor de líquido secundario (`temp_camara_2`) — pendiente compartido ya documentado, no afectado por este cambio.

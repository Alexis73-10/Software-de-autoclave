# Corrección de sobrepaso de temperatura en CALENTAMIENTO — diseño

**Proyecto:** Software-de-autoclave (Especifika S.A.S.)
**Alcance:** `src/autoclave/state_machine/cycle_phases/calentamiento.py` — control de `vapor_camara` (paso 5 de `update()`). No se toca ninguna otra fase ni parámetro JSON.

---

## 1. Problema

El 2026-08-05 se corrió el ciclo "Instrumental 121°C" (`ciclo id=72`, perfil `instrumental_121.json`, objetivo `temperatura_calentamiento=121.0°C`). CALENTAMIENTO arrancó con el objetivo correcto (`objetivo 121.0°C / 215.3 kPa`, log 14:40:17) pero la temperatura real, según `lecturas` en `data/autoclave.db`, subió sin control hasta **133.4°C** antes de que el sistema abortara solo por timeout de recuperación:

```
14:40:17  CALENTAMIENTO inicia, temp=90.0°C
14:41:19  cruza objetivo (temp>=121, pres>=215.3) → entra a ESTABLE_PREESTERILIZACION
          ...pero un instante después ya está "fuera de rango"
14:43:18  pico: 133.4°C / 304 kPa
14:43:31  recién ahí entra a PWM_ACTIVO (control modulado)
14:46:20  FALLO automático: "no se logró sostener condición estable en 5 min"
```

**Causa raíz confirmada:** el gate que decide cuándo pasar de "válvula abierta a fondo" (tramo APROXIMACION, sin modulación) a "válvula modulada" (PWM_ACTIVO) es:

```python
# calentamiento.py:174 (código actual)
if not self._en_pwm and abs(pres - p_saturacion_kpa(temp)) <= rango_cal:
    self._en_pwm = True
```

Esto compara la presión contra la curva de saturación de la **temperatura actual**, que va subiendo — una referencia móvil, no contra el objetivo fijo. Con los datos reales del ciclo:

| Temp | P_sat(T) | Presión real | Diferencia |
|---|---|---|---|
| 89.0°C | 68.4 kPa | 143.4 kPa | +75 kPa |
| 120.3°C | 199.8 kPa | 231.5 kPa | +31.7 kPa |
| 133.4°C | 297.0 kPa | 304.0 kPa | +7.0 kPa |

La presión real corrió persistentemente 7-75 kPa por encima de la curva de saturación pura durante toda la subida (efecto conocido: presión de chaqueta, aire residual, calibración de sensor — el mismo fenómeno que ya motivó la corrección de ESTERILIZACION, ver `CLAUDE.md`). La condición `abs(pres - P_sat(temp)) <= rango_cal` (2 kPa) no se cumplió hasta que la cámara ya estaba a ~133°C, así que la válvula se quedó abierta a fondo mucho después de haber cruzado los 121°C.

Es la misma clase de bug ya identificada y corregida en `esterilizacion.py` (comparar contra una referencia que se mueve con `T_actual` en vez de contra el setpoint fijo), pero nunca se replicó en `calentamiento.py`.

---

## 2. Decisión de diseño

Tres mecanismos, evaluados en cada tick dentro del paso 5 (control de `vapor_camara`), sin parámetros JSON nuevos:

1. **Gate de entrada a PWM_ACTIVO anclado al objetivo fijo** — corrige la causa raíz.
2. **Tope de temperatura al 97% del objetivo**, con espera activa a que la presión "corresponda" a la temperatura actual — evita que el sensor de temperatura corra por delante de la presión real (vapor no saturado) incluso antes de llegar al 100%.
3. **Techo independiente** — corta el vapor sin importar el tramo si la presión ya rebasó lo tolerado, en vez de esperar pasivamente hasta 5 min a que la inercia se disipe.

Los tres son puramente correctivos/preventivos sobre el control de la válvula; no cambian la máquina de estados de tramos (`APROXIMACION → PWM_ACTIVO → ESTABLE_PREESTERILIZACION`, sin retroceso) ni las condiciones de éxito/fallo ya existentes.

---

## 3. Mecanismo 1 — Gate de entrada a PWM_ACTIVO (línea ~174)

Antes:
```python
if not self._en_pwm and abs(pres - p_saturacion_kpa(temp)) <= rango_cal:
    self._en_pwm = True
```

Después:
```python
if not self._en_pwm and (pres >= p_obj - rango_cal or temp >= t_obj):
    self._en_pwm = True
```

- `pres >= p_obj - rango_cal`: entra a PWM cuando la presión se acerca al objetivo real (`p_obj`), no cuando "parece" vapor saturado según una temperatura que sigue subiendo. Con los datos del ciclo real, esto habría disparado entre 110.6°C y 120.3°C — antes de cruzar 121°C.
- `or temp >= t_obj`: seguro en la dirección contraria (si la temperatura se adelanta a la presión). Garantiza que la válvula nunca siga a fondo una vez cruzado el setpoint de temperatura, sin importar qué esté haciendo la presión.
- Sigue siendo unidireccional/latching (`_en_pwm` nunca vuelve a `False`), sin cambios en esa propiedad.

---

## 4. Mecanismo 2 — Tope de temperatura al 97% con espera de presión

Nueva constante de módulo (mismo estilo que `_BANDA_PWM_BAJA`/`_BANDA_PWM_ALTA` de `esterilizacion.py`):

```python
_FACTOR_TOPE_TEMPERATURA = 0.97
```

Chequeo, evaluado en cada tick sin importar `_en_pwm` (antes del bang-bang o PWM):

```python
temp_cap = _FACTOR_TOPE_TEMPERATURA * t_obj
p_min_para_temp = p_saturacion_kpa(temp) + p_add   # recalculado en vivo cada tick

if temp >= temp_cap and pres < p_min_para_temp:
    self.set_do.vapor_camara_off()
    self._pwm_abierto = False
    self._t_pulso_pwm = None
```

- Pausa la inyección de vapor mientras `temp` ya alcanzó el 97% de `t_obj` pero la presión todavía no llegó al nivel que "correspondería" a esa temperatura (`P_sat(temp) + presion_add_calentamiento`, el mismo criterio que define `p_obj` pero evaluado con la temperatura actual en vez de la fija).
- `p_min_para_temp` se recalcula cada tick con la temperatura real — no se congela al cruzar el 97%.
- Mientras la pausa está activa, `temp < t_obj` por construcción (97% < 100%), así que no interfiere con la entrada a `ESTABLE_PREESTERILIZACION` (paso 7): ese timer simplemente no puede empezar todavía.
- No genera `FALLO` ni tiene timeout propio — es una pausa de control, no una condición de fase. Si la presión nunca "alcanza" a la temperatura, el ciclo queda calentando en el tope hasta el timeout general de `timeout_calentamiento` (sin cambios, ya existente).

---

## 5. Mecanismo 3 — Techo independiente

```python
p_techo = p_obj + p_add   # mismo límite superior que ya usa dentro_rango en el paso 7

if pres >= p_techo:
    self.set_do.vapor_camara_off()
    self._pwm_abierto = False
    self._t_pulso_pwm = None
```

- Reutiliza el límite superior que el paso 7 (`dentro_rango`) ya usa para tolerar sobrepaso durante `ESTABLE_PREESTERILIZACION` (`p_obj <= pres <= p_obj + p_add`) — no es un valor nuevo, solo se le da un efecto activo sobre la válvula en vez de ser solo un chequeo de "¿ya se completó?".
- Corta el vapor sin importar el tramo (`APROXIMACION`, `PWM_ACTIVO` o `ESTABLE_PREESTERILIZACION`) mientras la presión esté por encima del límite tolerado, en vez de dejar que el duty cycle normal siga inyectando vapor durante toda la ventana de recuperación pasiva de 5 min (`timeout_recuperacion_estabilizacion`).
- No reemplaza esa recuperación pasiva ni su `FALLO` — es una segunda línea de defensa activa, no un cambio en la condición de fallo.

---

## 6. Orden de evaluación combinado (paso 5 completo)

```python
temp_cap = _FACTOR_TOPE_TEMPERATURA * t_obj
p_min_para_temp = p_saturacion_kpa(temp) + p_add
p_techo = p_obj + p_add

if temp >= temp_cap and pres < p_min_para_temp:
    # Mecanismo 2 — pausa por temperatura adelantada a la presión
    self.set_do.vapor_camara_off()
    self._pwm_abierto = False
    self._t_pulso_pwm = None
elif pres >= p_techo:
    # Mecanismo 3 — techo independiente
    self.set_do.vapor_camara_off()
    self._pwm_abierto = False
    self._t_pulso_pwm = None
elif not self._en_pwm:
    # APROXIMACION — bang-bang existente, sin cambios
    ...
else:
    # PWM_ACTIVO — duty cycle existente, sin cambios
    ...
```

Los mecanismos 2 y 3 son mutuamente excluyentes en la práctica: el 2 exige presión *baja* respecto a la temperatura actual, el 3 exige presión *alta* respecto al objetivo fijo. El gate de entrada a PWM_ACTIVO (mecanismo 1, paso 4, antes de este bloque) no cambia de posición en el flujo — sigue evaluándose independientemente en cada tick.

---

## 7. Qué NO cambia

- La máquina de estados de tramos (`APROXIMACION → PWM_ACTIVO → ESTABLE_PREESTERILIZACION`, sin retroceso).
- El timer de `ESTABLE_PREESTERILIZACION`, su ventana continua y su timeout de recuperación (`timeout_recuperacion_estabilizacion`).
- El timeout global de fase (`timeout_calentamiento`).
- Los escapes (`descompresion_lenta`/`descompresion_rapida`), que siguen sus temporizadores de dos estados independientes sin cambios.
- `esterilizacion.py` y cualquier otra fase.
- No hay parámetros nuevos en los JSON de ciclo (`instrumental_121.json`, `instrumental_134.json`, `bowe_dick.json`, factory y user).

---

## 8. Tests

Ampliar `tests/test_calentamiento_fase.py` con:

- **Regresión del bug real:** entra a PWM_ACTIVO cuando `pres >= p_obj - rango_cal` aunque `P_sat(temp_actual)` esté lejos de la presión real (reproduce con datos sintéticos el escenario del ciclo 72 — presión persistentemente por encima de la curva de saturación).
- Entra a PWM_ACTIVO cuando `temp >= t_obj` aunque la presión esté rezagada (caso inverso).
- El tope de 97% pausa `vapor_camara` cuando `temp >= 0.97*t_obj` y `pres < P_sat(temp) + p_add`, y libera la pausa apenas la presión alcanza ese nivel.
- El tope de 97% no interfiere con la entrada a `ESTABLE_PREESTERILIZACION` (la fase no puede completarse mientras la pausa está activa, porque `temp < t_obj`).
- El techo independiente fuerza OFF cuando `pres >= p_obj + p_add`, sin importar `_en_pwm`, y se libera cuando la presión vuelve a bajar del techo.
- Regresión: un calentamiento normal (sin overshoot, presión siguiendo la curva de saturación de cerca) completa igual que antes — ninguno de los tres mecanismos debe activarse en el caso sano.

---

## 9. Riesgos aceptados / fuera de alcance

- Si `timeout_calentamiento` se agota mientras el tope de 97% mantiene la pausa (presión nunca "alcanza" a la temperatura), la fase falla por el timeout global existente — no se agrega un timeout dedicado para esta pausa (fuera de alcance salvo que se solicite).
- No se replica el mecanismo del techo/tope de temperatura hacia atrás en `esterilizacion.py` (que ya tiene su propio techo, con otra lógica bidireccional) — cambio acotado a `calentamiento.py`.
- El caso de sensor `None` sigue sin timeout dedicado (riesgo aceptado ya documentado en `CLAUDE.md`), sin cambios.

---

## 10. Documentación a actualizar

- `CLAUDE.md`: sección de `calentamiento.py` — agregar nota de rediseño del control de `vapor_camara` (paso 5) documentando los tres mecanismos y el motivo (sobrepaso real observado en ciclo 72, 2026-08-05).
- Comentario de cabecera de `calentamiento.py` — actualizar la descripción de PWM_ACTIVO para reflejar el nuevo gate anclado a objetivo fijo y los dos mecanismos adicionales.

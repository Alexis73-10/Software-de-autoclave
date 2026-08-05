# Control continuo de rampa en CALENTAMIENTO — diseño

**Proyecto:** Software-de-autoclave (Especifika S.A.S.)
**Alcance:** `src/autoclave/state_machine/cycle_phases/calentamiento.py` — reemplaza los pasos 4 y 5 de `update()` (gate de entrada a PWM_ACTIVO y control de `vapor_camara`). No toca `ESTABLE_PREESTERILIZACION` (paso 7), los escapes (paso 6), el cálculo de pendiente (paso 3) ni ninguna otra fase.

**Reemplaza a:** `docs/superpowers/specs/2026-08-05-fix-overshoot-calentamiento-design.md` (no implementado). Ese spec corregía el mismo bug (sobrepaso a 133.4°C en ciclo 72, objetivo 121°C) con tres mecanismos discretos superpuestos al gate existente. Este diseño ataca la misma causa raíz de otra forma: elimina el gate discreto en sí mismo y lo reemplaza por una ley de control continua, por lo que sus mecanismos 1 y 2 quedan sin objeto. El mecanismo 3 (techo independiente de presión) se conserva como resguardo de seguridad — ver sección 5.

---

## 1. Problema

El control actual de `vapor_camara` durante la subida tiene dos tramos discretos con una transición abrupta entre ellos:

- **APROXIMACION**: bang-bang por tick (ON a fondo salvo que la pendiente ya supere `tasa_calentamiento`/`tasa_presion`).
- **PWM_ACTIVO**: se activa cuando `abs(pres - P_sat(temp)) <= rango_calentamiento` — comparación contra una referencia que se mueve con la temperatura actual, no contra el objetivo fijo.

Esa comparación contra una referencia móvil es la causa raíz confirmada del sobrepaso real del ciclo 72 (2026-08-05): con la presión corriendo persistentemente por encima de la curva de saturación pura (efecto de presión de chaqueta / aire residual / calibración), la condición de entrada a PWM_ACTIVO no se cumplió hasta que la cámara ya estaba a ~133°C — la válvula se quedó abierta a fondo mucho después de cruzar el objetivo de 121°C. Detalle completo de los datos del ciclo en el spec reemplazado.

Además del bug puntual, el diseño de dos tramos con gate discreto es frágil por construcción: cualquier salto de "válvula a fondo" a "válvula modulada" depende de que la condición de entrada se cumpla en el momento correcto, y un desfase entre sensores (temperatura vs. presión) puede retrasar esa transición indefinidamente.

## 2. Objetivo del rediseño

Reemplazar los dos tramos y su gate por **un único controlador continuo** que en cada tick calcula directamente qué tan abierta debe estar la válvula (duty cycle entre 0 y 1), de forma que:
1. Nunca sostenga una pendiente de temperatura o presión por encima de `tasa_calentamiento`/`tasa_presion`.
2. Los pulsos de vapor se acorten de forma continua a medida que se acerca al objetivo o al límite de tasa, en vez de un salto abrupto de tramo.
3. La proximidad al objetivo se mida siempre contra la referencia fija (`t_obj`/`p_obj`), nunca contra `P_sat(temp_actual)`.

La secuencia de tramos internos de la fase queda:

```
RAMPA (control continuo)  →  ESTABLE_PREESTERILIZACION (sin cambios)
```

`ESTABLE_PREESTERILIZACION` no se modifica: su condición de entrada (`temp >= t_obj and pres >= p_obj`, paso 7 actual) ya es independiente del estado `_en_pwm`/tramo, así que el cambio es transparente para esa parte de la fase.

## 3. Ley de control

Dos duty cycles independientes, calculados en cada tick; se aplica el más restrictivo (mínimo):

### 3.1 `duty_tasa` — límite de pendiente

```python
def _duty_por_tasa(tasa_actual, tasa_max):
    if tasa_max <= 0 or tasa_actual is None or tasa_actual <= 0:
        return 1.0
    return min(tasa_max / tasa_actual, 1.0)

duty_tasa = min(
    _duty_por_tasa(tasa_t, tasa_t_max),
    _duty_por_tasa(tasa_p, tasa_p_max),
)
```

Control por realimentación de razón: si la pendiente medida (misma ventana de 10s del paso 3 actual, sin cambios) ya superó el límite configurado, el duty de la próxima ventana baja proporcionalmente; si está por debajo, no hay restricción (`1.0`). Se autoestabiliza en `tasa_actual ≈ tasa_max` sin ganancias que tunear. `tasa_max <= 0` reproduce la semántica actual de "0 = sin límite"; `tasa_actual` en `None` (ventana aún sin suficiente historia) o `<= 0` (temperatura/presión plana o bajando) tampoco restringen, igual que hoy.

### 3.2 `duty_proximidad` — distancia al objetivo fijo

```python
duty_estable = 1.0 - factor_pct / 100.0

def _prox(dist, margen):
    if margen <= 0:
        return 1.0 if dist > 0 else 0.0
    return max(0.0, min(dist / margen, 1.0))

p = max(_prox(t_obj - temp, rango_cal), _prox(p_obj - pres, rango_cal))
duty_proximidad = duty_estable + (1.0 - duty_estable) * p
```

Lejos del objetivo (`dist >= rango_calentamiento` en cualquiera de las dos variables) → `duty_proximidad = 1.0`, equivalente al bang-bang actual de APROXIMACION. Dentro de la banda o ya cruzado (`dist <= 0`) → `duty_proximidad = duty_estable`, el mismo duty que hoy aplica PWM_ACTIVO de forma fija vía `factor_calentamiento`. Entre ambos extremos interpola lineal — la distancia se mide siempre contra `t_obj`/`p_obj` fijos, nunca contra `P_sat(temp_actual)`, eliminando la causa raíz del bug del ciclo 72.

### 3.3 Duty final y aplicación

```python
duty = min(duty_tasa, duty_proximidad)
t_on_pwm  = intervalo * duty
t_off_pwm = intervalo - t_on_pwm
self._tick_dos_estados(
    "_t_pulso_pwm", "_pwm_abierto", t_on_pwm, t_off_pwm,
    self.set_do.vapor_camara_on, self.set_do.vapor_camara_off, now,
)
```

Se evalúa en cada tick, reemplazando por completo los pasos 4 y 5 actuales (gate de entrada + bang-bang/PWM condicional). Reutiliza el mismo helper `_tick_dos_estados` que ya usan PWM_ACTIVO y `esterilizacion.py`, sin cambios en ese helper. Como `t_on`/`t_off` se recalculan en cada tick a partir de datos vivos, un pulso en curso puede acortarse o extenderse frente a lo que se calculó al iniciarlo — es intencional: da respuesta más fina que esperar a que termine el periodo completo del pulso.

## 4. Parámetros — ninguno nuevo

Reutiliza los parámetros existentes de la sección `calentamiento` de los JSON de ciclo, con un rol continuo en vez de discreto:

| Parámetro | Rol anterior | Rol nuevo |
|---|---|---|
| `tasa_calentamiento` / `tasa_presion` | Techo de pendiente en bang-bang de APROXIMACION | Igual, ahora alimenta `duty_tasa` de forma proporcional |
| `rango_calentamiento` | Umbral de entrada a PWM_ACTIVO (gate discreto, contra `P_sat(temp)`) | Ancho de interpolación de `duty_proximidad` (contra `t_obj`/`p_obj` fijos) |
| `factor_calentamiento` | % OFF fijo dentro de PWM_ACTIVO | Duty de convergencia (`duty_estable`) — mismo significado práctico |
| `intervalo_segmentos_calor` | Periodo del pulso PWM | Sin cambio |

No se agregan parámetros a los JSON de ciclo (`instrumental_121.json`, `instrumental_134.json`, `bowe_dick.json`, factory y user).

## 5. Techo independiente de presión (resguardo de seguridad, retenido)

`duty_proximidad` no baja a `0.0` una vez cruzado el objetivo — se estabiliza en `duty_estable` (p. ej. 30% si `factor_calentamiento=70`). Si la inercia térmica empuja la presión bien por encima de `p_obj` mientras `duty_tasa` no lo detecta (pendiente ya no creciendo en el momento evaluado), el controlador seguiría inyectando vapor a `duty_estable` en vez de cortar. Se retiene el mecanismo 3 del spec reemplazado como resguardo, evaluado *después* de calcular `duty`:

```python
p_techo = p_obj + p_add
if pres >= p_techo:
    duty = 0.0
```

No es parte de la ley de control proporcional — es un corte duro de emergencia, igual que en el diseño original. Reutiliza `p_add`, ya en alcance; no agrega parámetros.

## 6. Casos borde

- `tasa_t`/`tasa_p` en `None` (los primeros ~10s de fase, ventana del paso 3 aún sin suficiente historia) → `duty_tasa = 1.0`, misma semántica que el bang-bang actual.
- `tasa_calentamiento`/`tasa_presion` en `0` (deshabilitado) → sin restricción por esa vía, igual que hoy.
- `rango_calentamiento` en `0` → `duty_proximidad` degenera a un escalón (`1.0` lejos, `duty_estable` en o después del objetivo), sin división por cero.
- `factor_calentamiento` en `0` → `duty_estable = 1.0` (válvula siempre a fondo incluso convergido); en `100` → `duty_estable = 0.0` (cerrada al converger) — misma semántica que la fórmula actual de PWM_ACTIVO.
- Sensor `None` → ya se corta en el paso 2 existente, antes de llegar a este cálculo; sin cambios.

## 7. Qué NO cambia

- `ESTABLE_PREESTERILIZACION`: su gate de entrada, ventana continua de sostenimiento y timeout de recuperación (`timeout_recuperacion_estabilizacion`).
- El timeout global de fase (`timeout_calentamiento`).
- Los escapes (`descompresion_lenta`/`descompresion_rapida`), temporizadores de dos estados independientes sin tocar.
- El cálculo de pendiente del paso 3 (`_historial_pendiente`, ventana `_VENTANA_PENDIENTE_SEG`) — se reutiliza tal cual, sin cambios.
- `esterilizacion.py` y cualquier otra fase.
- No hay parámetros nuevos en ningún JSON de ciclo.

## 8. Riesgos aceptados / fuera de alcance

- Igual que el spec reemplazado: si `timeout_calentamiento` se agota mientras la presión está atascada por debajo de lo que la temperatura sugeriría, la fase falla por el timeout global existente — no se agrega timeout dedicado.
- El caso de sensor en `None` sigue sin timeout dedicado (riesgo ya documentado en `CLAUDE.md`), sin cambios.
- No se replica esta ley de control continua en `esterilizacion.py`, que ya tiene su propia lógica bidireccional con banda fija — cambio acotado a `calentamiento.py`.
- El estado `_en_pwm` y el log "banda alcanzada — entra a PWM_ACTIVO" desaparecen; cualquier código o test que dependa de ese estado interno debe actualizarse (ver sección 9).

## 9. Tests

Reemplazar/ampliar `tests/test_calentamiento_fase.py`:

- `duty_tasa` baja de `1.0` cuando la pendiente medida supera `tasa_max`, y vuelve a `1.0` cuando la pendiente baja del límite.
- `duty_proximidad` interpola linealmente entre `1.0` (a `rango_calentamiento` de distancia o más) y `duty_estable` (en o después de `t_obj`/`p_obj`), medido siempre contra los objetivos fijos — no contra `P_sat(temp_actual)`.
- Regresión del bug real (ciclo 72): con presión persistentemente por encima de la curva de saturación pura, el duty ya empieza a bajar antes de cruzar el objetivo, en vez de mantenerse en `1.0` hasta 133°C.
- Techo independiente: `pres >= p_obj + p_add` fuerza `duty = 0.0` sin importar `duty_tasa`/`duty_proximidad`.
- Caso sano (sin overshoot, presión siguiendo de cerca la curva de saturación): el ciclo completa con el mismo resultado final que con el código actual.
- Casos borde de la sección 6 (`rango_calentamiento=0`, `factor_calentamiento` en `0`/`100`, tasas deshabilitadas).
- Eliminar/actualizar cualquier test existente que dependa del estado `_en_pwm` o del log de "entra a PWM_ACTIVO", que ya no existen.

## 10. Documentación a actualizar (en la implementación)

- `CLAUDE.md`: sección de `calentamiento.py` — reemplazar la descripción de tramos `APROXIMACION → PWM_ACTIVO → ESTABLE_PREESTERILIZACION` por `RAMPA (control continuo) → ESTABLE_PREESTERILIZACION`, documentando la ley de control de la sección 3.
- Comentario de cabecera de `calentamiento.py` — actualizar para reflejar el controlador continuo en vez de los dos tramos discretos.
- Marcar `docs/superpowers/specs/2026-08-05-fix-overshoot-calentamiento-design.md` como reemplazado por este documento (ya referenciado arriba).

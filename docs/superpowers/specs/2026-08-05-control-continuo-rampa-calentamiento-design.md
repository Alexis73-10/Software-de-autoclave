# Control continuo de rampa en CALENTAMIENTO — diseño

**Proyecto:** Software-de-autoclave (Especifika S.A.S.)
**Alcance:** `src/autoclave/state_machine/cycle_phases/calentamiento.py` — reemplaza los pasos 4 y 5 de `update()` (gate de entrada a PWM_ACTIVO y control de `vapor_camara`). No toca `ESTABLE_PREESTERILIZACION` (paso 7), los escapes (paso 6), el cálculo de pendiente (paso 3) ni ninguna otra fase.

**Reemplaza a:** `docs/superpowers/specs/2026-08-05-fix-overshoot-calentamiento-design.md`. De sus tres mecanismos, el **mecanismo 1** (gate anclado a `p_obj`/`t_obj`) ya se implementó por separado y está en `dev` (commits `211f2fd`, `5201370`) — este diseño lo reemplaza otra vez, de raíz: en vez de corregir el gate discreto, lo elimina y lo reemplaza por una ley de control continua (sección 2). El **mecanismo 2** (tope de temperatura al 97% con espera de presión) no está implementado todavía y se conserva aquí como tercer término del duty (`duty_calidad_vapor`, sección 3.3). El **mecanismo 3** (techo independiente de presión) tampoco está implementado y se conserva como resguardo de seguridad (sección 6).

**Nota de coordinación (2026-08-05):** este spec se escribió en paralelo a una sesión que implementaba el spec reemplazado; esa sesión ya había commiteado el mecanismo 1 antes de que este documento se aprobara. La Tarea 2 del plan de implementación debe partir del `calentamiento.py` real en `dev` (con el gate `pres >= p_obj - rango_cal or temp >= t_obj` ya presente), no de la versión pre-fix descrita en la sección 1.

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

Tres duty cycles independientes, calculados en cada tick; se aplica el más restrictivo (mínimo):

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

cercania = min(_prox(t_obj - temp, rango_cal), _prox(p_obj - pres, rango_cal))
duty_proximidad = duty_estable + (1.0 - duty_estable) * cercania
```

`min()`, no `max()`: cada variable puede disparar la reducción de duty por sí sola, igual que el gate que reemplaza (`pres >= p_obj - rango_cal OR temp >= t_obj`, un OR de dos condiciones independientes). Con `max()` el duty solo bajaría cuando **ambas** variables estuvieran cerca a la vez, perdiendo el seguro de la dirección contraria (mecanismo 1 original: si la temperatura cruza `t_obj` antes de que la presión se acerque a `p_obj`, la válvula debe dejar de estar a fondo igual).

Lejos del objetivo (`dist >= rango_calentamiento` en **ambas** variables) → `duty_proximidad = 1.0`. Tan pronto **cualquiera** de las dos entra en su banda (`dist <= 0`) → `duty_proximidad = duty_estable`, el mismo duty que hoy aplica PWM_ACTIVO de forma fija vía `factor_calentamiento`. Entre ambos extremos interpola lineal — la distancia se mide siempre contra `t_obj`/`p_obj` fijos, nunca contra `P_sat(temp_actual)`, eliminando la causa raíz del bug del ciclo 72.

### 3.3 `duty_calidad_vapor` — temperatura no adelantada a la presión real

Retoma el mecanismo 2 del spec reemplazado, expresado como tercer término del duty en vez de una pausa aparte. Cubre un caso que `duty_proximidad` no cubre: la temperatura puede estar lejos de `t_obj` (o incluso cerca) mientras la presión real no "corresponde" a esa temperatura — vapor no saturado, típicamente por calor de chaqueta llegando al sensor antes de que la cámara esté realmente llena de vapor a esa condición. Es un chequeo de consistencia física, no de distancia al objetivo:

```python
_FACTOR_TOPE_TEMPERATURA = 0.97

def _duty_por_calidad_vapor(temp, pres, t_obj, p_add):
    temp_cap = _FACTOR_TOPE_TEMPERATURA * t_obj
    if temp < temp_cap:
        return 1.0
    p_min_para_temp = p_saturacion_kpa(temp) + p_add  # recalculado en vivo cada tick
    return 1.0 if pres >= p_min_para_temp else 0.0
```

Sin restricción (`1.0`) mientras `temp` no llegó al 97% de `t_obj`. Al cruzar ese umbral, exige que la presión ya "corresponda" a la temperatura actual (`P_sat(temp) + p_add`, el mismo criterio que define `p_obj` pero evaluado con la temperatura real en vez de la fija) — si no, corta el duty a `0.0` por completo (pausa binaria, igual que el mecanismo original; no es una interpolación continua porque lo que se verifica es una condición física de sí/no, no una distancia). `p_min_para_temp` se recalcula cada tick con la temperatura real, nunca se congela al cruzar el 97%. Como `temp < t_obj` por construcción mientras la pausa está activa (97% < 100%), no interfiere con la entrada a `ESTABLE_PREESTERILIZACION` (paso 7): ese gate simplemente no puede cumplirse todavía. No genera `FALLO` ni tiene timeout propio — si la presión nunca "alcanza" a la temperatura, el ciclo queda pausado hasta el timeout general de `timeout_calentamiento`, sin cambios.

### 3.4 Duty final y aplicación

```python
duty = min(duty_tasa, duty_proximidad, duty_calidad_vapor)
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

No se agregan parámetros a los JSON de ciclo (`instrumental_121.json`, `instrumental_134.json`, `bowe_dick.json`, factory y user). `_FACTOR_TOPE_TEMPERATURA = 0.97` (sección 3.3) es una constante de módulo, mismo estilo que `_VENTANA_PENDIENTE_SEG` — no un parámetro configurable por ciclo, igual que en el spec reemplazado.

## 5. Techo independiente de presión (resguardo de seguridad, retenido)

Ni `duty_proximidad` ni `duty_calidad_vapor` bajan a `0.0` de forma permanente una vez cruzado el objetivo — `duty_proximidad` se estabiliza en `duty_estable` (p. ej. 30% si `factor_calentamiento=70`) y `duty_calidad_vapor` vuelve a `1.0` en cuanto la presión "alcanza" a la temperatura. Si la inercia térmica empuja la presión bien por encima de `p_obj` mientras `duty_tasa` no lo detecta (pendiente ya no creciendo en el momento evaluado), el controlador seguiría inyectando vapor en vez de cortar. Se retiene el mecanismo 3 del spec reemplazado como resguardo, evaluado *después* de calcular `duty`:

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
- `temp < 0.97 * t_obj` → `duty_calidad_vapor = 1.0` sin importar la presión (el chequeo no se activa todavía).
- `temp >= 0.97 * t_obj` y `pres >= P_sat(temp) + p_add` → `duty_calidad_vapor = 1.0` (presión ya corresponde a la temperatura real).
- Sensor `None` → ya se corta en el paso 2 existente, antes de llegar a este cálculo; sin cambios.

## 7. Qué NO cambia

- `ESTABLE_PREESTERILIZACION`: su gate de entrada, ventana continua de sostenimiento y timeout de recuperación (`timeout_recuperacion_estabilizacion`).
- El timeout global de fase (`timeout_calentamiento`).
- Los escapes (`descompresion_lenta`/`descompresion_rapida`), temporizadores de dos estados independientes sin tocar.
- El cálculo de pendiente del paso 3 (`_historial_pendiente`, ventana `_VENTANA_PENDIENTE_SEG`) — se reutiliza tal cual, sin cambios.
- `esterilizacion.py` y cualquier otra fase.
- No hay parámetros nuevos en ningún JSON de ciclo.

## 8. Riesgos aceptados / fuera de alcance

- Igual que el spec reemplazado: si `timeout_calentamiento` se agota mientras `duty_calidad_vapor` mantiene la pausa (presión nunca "alcanza" a la temperatura), la fase falla por el timeout global existente — no se agrega timeout dedicado para este caso.
- El caso de sensor en `None` sigue sin timeout dedicado (riesgo ya documentado en `CLAUDE.md`), sin cambios.
- No se replica esta ley de control continua en `esterilizacion.py`, que ya tiene su propia lógica bidireccional con banda fija — cambio acotado a `calentamiento.py`.
- El estado `_en_pwm` y el log "objetivo cercano — entra a PWM_ACTIVO" desaparecen; cualquier código o test que dependa de ese estado interno debe actualizarse (ver sección 9).

## 9. Tests

Reemplazar/ampliar `tests/test_calentamiento_fase.py`:

- `duty_tasa` baja de `1.0` cuando la pendiente medida supera `tasa_max`, y vuelve a `1.0` cuando la pendiente baja del límite.
- `duty_proximidad` interpola linealmente entre `1.0` (a `rango_calentamiento` de distancia o más) y `duty_estable` (en o después de `t_obj`/`p_obj`), medido siempre contra los objetivos fijos — no contra `P_sat(temp_actual)`.
- `duty_calidad_vapor` permanece en `1.0` mientras `temp < 0.97*t_obj`; cae a `0.0` al cruzar ese umbral si la presión no corresponde a `P_sat(temp) + p_add`; vuelve a `1.0` apenas la presión alcanza ese nivel.
- Regresión del bug real (ciclo 72): con presión persistentemente por encima de la curva de saturación pura, el duty ya empieza a bajar antes de cruzar el objetivo, en vez de mantenerse en `1.0` hasta 133°C.
- Techo independiente: `pres >= p_obj + p_add` fuerza `duty = 0.0` sin importar los otros tres términos.
- Caso sano (sin overshoot, presión siguiendo de cerca la curva de saturación): el ciclo completa con el mismo resultado final que con el código actual.
- Casos borde de la sección 6 (`rango_calentamiento=0`, `factor_calentamiento` en `0`/`100`, tasas deshabilitadas, `duty_calidad_vapor` antes/después del 97%).
- Eliminar/actualizar cualquier test existente que dependa del estado `_en_pwm` o del log de "entra a PWM_ACTIVO", que ya no existen.

## 10. Documentación a actualizar (en la implementación)

- `CLAUDE.md`: sección de `calentamiento.py` — reemplazar la descripción de tramos `APROXIMACION → PWM_ACTIVO → ESTABLE_PREESTERILIZACION` por `RAMPA (control continuo) → ESTABLE_PREESTERILIZACION`, documentando la ley de control de la sección 3.
- Comentario de cabecera de `calentamiento.py` — actualizar para reflejar el controlador continuo en vez de los dos tramos discretos.
- Marcar `docs/superpowers/specs/2026-08-05-fix-overshoot-calentamiento-design.md` como reemplazado por este documento (ya referenciado arriba).

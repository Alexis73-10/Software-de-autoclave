# Control por tasa en la fase CALENTAMIENTO (tramo APROXIMACION)

**Proyecto:** Software-de-autoclave (Especifika S.A.S.)
**Alcance:** Modificación puntual de `src/autoclave/state_machine/cycle_phases/calentamiento.py` — el tramo `APROXIMACION` deja de abrir `vapor_camara` en ON continuo y pasa a un control bang-bang gobernado por `tasa_calentamiento`/`tasa_presion`.

---

## 1. Problema

`tasa_calentamiento` (°C/min) y `tasa_presion` (kPa/min) existen hoy en los 4 perfiles JSON (`user/` y `factory/`, `instrumental_134` y `bowe_dick`, sección `calentamiento`) pero **solo se usan para detectar falla**: si la pendiente medida tick a tick supera el umbral durante 3 lecturas consecutivas (`_DEBOUNCE_LECTURAS`), la fase pasa a `FaseResult.FALLO`.

Mientras tanto, el tramo `APROXIMACION` controla `vapor_camara` con un simple `vapor_camara_on()` sin condición — la única salida binaria que eleva la cámara se mantiene abierta todo el tiempo hasta que la lectura entra en la banda `rango_calentamiento` alrededor de `P_sat(T_actual)`. No hay ningún mecanismo que module la velocidad de subida; el límite de tasa es puramente reactivo (detecta el problema después de que ya ocurrió).

El objetivo de este cambio es que esos dos parámetros pasen a **gobernar activamente** la válvula durante `APROXIMACION`, para lograr una rampa más controlada, dado que la única actuación posible sobre `vapor_camara` es ON/OFF (no hay control proporcional real de caudal).

## 2. Alcance

- **Se modifica únicamente el tramo `APROXIMACION`** de `CalentamientoFase` (el paso 5 de `update()`, rama `if not self._en_pwm:`).
- `PWM_ACTIVO` y `ESTABLE_PREESTERILIZACION` **no cambian** — siguen usando el ciclo PWM de `factor_calentamiento`/`intervalo_segmentos_calor`, sin relación con la tasa medida. Decisión explícita: la fase mantiene sus tres tramos actuales sin retroceso entre ellos; este cambio no introduce tramos nuevos ni altera la transición `APROXIMACION → PWM_ACTIVO` (que sigue siendo `abs(pres - P_sat(temp)) <= rango_calentamiento`).
- El chequeo de **FALLO por pendiente excesiva no cambia** (paso 3 de `update()`): mismo cálculo, mismo umbral (`tasa_calentamiento`/`tasa_presion`), mismo debounce de 3 lecturas, misma semántica bidireccional para temperatura (`abs()`) y unidireccional para presión.
- **Sin parámetros nuevos.** `tasa_calentamiento` y `tasa_presion` ya están definidos en los 4 perfiles con los rangos actuales (0–100 °C/min y 0–300 kPa/min); solo cambia su rol documentado, de "umbral de falla" a "umbral de falla + techo de control".
- **Sin cambios de UI** — `params_ciclo.py` ya renderiza estos parámetros desde el JSON; no hay claves nuevas que exponer.

## 3. Mecanismo de control

Reutiliza el mismo cálculo de pendiente que ya existe para el chequeo de falla (`tasa_t = (temp - self._temp_anterior) / dt_min`, `tasa_p = (pres - self._pres_anterior) / dt_min`, con `dt_min = (now - self._t_tick_anterior) / 60`). No se duplica el cálculo: se captura en variables reutilizables en el paso 3 y se consume en el paso 5.

Durante `APROXIMACION` (`not self._en_pwm`), en cada tick:

```
valvula_ON = (tasa_t_disponible == False)                    # sin dato de pendiente aún -> ON por defecto
             OR (
                 (tasa_calentamiento <= 0 OR tasa_t <= tasa_calentamiento)
                 AND
                 (tasa_presion <= 0 OR tasa_p <= tasa_presion)
             )
```

Detalles:

- **Solo dirección de subida importa para control.** `tasa_t` se compara sin valor absoluto — a diferencia del chequeo de falla, que sí usa `abs()` porque una caída abrupta de temperatura también es anómala. La válvula no puede enfriar la cámara, así que una caída de temperatura nunca debe forzarla a apagarse. `tasa_p` ya era unidireccional en el chequeo de falla existente (mismo criterio, se reutiliza tal cual).
- **`tasa_calentamiento <= 0` o `tasa_presion <= 0` deshabilita ese límite** — mismo convenio que ya usa el chequeo de falla (`if tasa_t_max > 0`). Con el valor 0, esa componente del `AND` no puede forzar OFF.
- **Primer tick del tramo (o cualquier tick sin pendiente calculable):** cuando `self._t_tick_anterior is None` o `dt_min` no es `> 0`, no hay `tasa_t`/`tasa_p` disponibles ese tick — la válvula permanece ON (comportamiento actual, sin cambios).
- **Bang-bang directo por tick, sin tiempo mínimo de apagado.** Cada tick reevalúa la condición desde cero; no hay estado de "enclavado OFF" ni parámetro de dwell mínimo. La válvula ya cicla a esta granularidad en `PWM_ACTIVO` (`intervalo_segmentos_calor`, típicamente 2 s), así que el hardware ya opera en ese régimen.
- **Sin logging adicional por tick** — consistente con el resto de la fase, que solo loggea en transiciones de tramo y al completar/fallar. No se agrega un log en cada apagado por límite de tasa.

### Relación con el chequeo de FALLO

El chequeo de FALLO (paso 3) no se modifica: mismo umbral, mismo debounce de 3 lecturas, misma lógica. La diferencia es de comportamiento esperado, no de código: en operación normal, el nuevo control debería evitar que la pendiente cruce el umbral de forma sostenida. Si el debounce de falla se dispara *a pesar de* que el control ya está forzando la válvula OFF, es indicio de una falla real (válvula pegada en posición abierta, fuga de vapor directa, sensor descalibrado) — no de un setpoint mal calibrado. Esto reutiliza el mismo valor de parámetro para ambos roles (control y falla), sin margen adicional entre ellos, según fue confirmado explícitamente para este diseño.

## 4. Pseudocódigo del cambio (paso 5 de `update()`)

```python
# paso 3 (existente, ampliado para capturar tasa_t/tasa_p fuera del bloque condicional)
tasa_t = None
tasa_p = None
if self._t_tick_anterior is not None:
    dt_min = (now - self._t_tick_anterior) / 60
    if dt_min > 0:
        tasa_t = (temp - self._temp_anterior) / dt_min
        tasa_p = (pres - self._pres_anterior) / dt_min
        # ... chequeos de FALLO sin cambios, usan tasa_t / tasa_p ...

# paso 5 (modificado)
if not self._en_pwm:
    dentro_de_tasa = (
        (tasa_t is None or tasa_t_max <= 0 or tasa_t <= tasa_t_max)
        and (tasa_p is None or tasa_p_max <= 0 or tasa_p <= tasa_p_max)
    )
    if dentro_de_tasa:
        self.set_do.vapor_camara_on()
    else:
        self.set_do.vapor_camara_off()
else:
    # PWM_ACTIVO: sin cambios
    ...
```

## 5. Casos de prueba a cubrir (actualización de `tests/test_calentamiento_fase.py`)

- Tramo `APROXIMACION`, primer tick (sin pendiente previa): válvula ON.
- Tramo `APROXIMACION`, pendiente de temperatura dentro del límite y de presión dentro del límite: válvula ON.
- Tramo `APROXIMACION`, pendiente de temperatura excede `tasa_calentamiento`: válvula OFF ese tick, aunque la presión esté dentro de rango.
- Tramo `APROXIMACION`, pendiente de presión excede `tasa_presion`: válvula OFF ese tick, aunque la temperatura esté dentro de rango.
- Tramo `APROXIMACION`, pendiente vuelve a estar dentro del límite en el tick siguiente: válvula vuelve a ON (sin tiempo mínimo de apagado).
- `tasa_calentamiento = 0` (deshabilitado): el control de temperatura no puede forzar OFF, solo el de presión.
- `tasa_presion = 0` (deshabilitado): el control de presión no puede forzar OFF, solo el de temperatura.
- Caída abrupta de temperatura (pendiente negativa que excedería `abs()` en el chequeo de falla): no fuerza OFF por control — la válvula permanece ON salvo que la falla por debounce ya la haya apagado por otra vía.
- El chequeo de FALLO existente (debounce de 3 lecturas) sigue disparando `FaseResult.FALLO` de forma independiente si la pendiente se mantiene por encima del umbral pese al control — caso de válvula que no responde.
- `PWM_ACTIVO`/`ESTABLE_PREESTERILIZACION`: sin cambios de comportamiento respecto a los tests existentes (regresión).

## 6. Documentación a actualizar tras implementar

- `docs/mis_plans/planeacion_fase_calentamiento.md`: fila 6/7 de la tabla de parámetros (sección 2, rol pasa de "Umbral de falla" a "Setpoint de control + umbral de falla"), sección 3 (diagrama de máquina de estados, agregar la nota de que `APROXIMACION` ya no es "ON continuo" sino bang-bang gobernado por tasa), y sección 4.1 (lógica de control de `vapor_camara`).
- Comentario de cabecera de `calentamiento.py` (líneas 1–20): la frase "tasa_calentamiento/tasa_presion vigilan la pendiente ... y pueden producir FALLO" deja de ser toda la historia; agregar que en `APROXIMACION` también gobiernan la válvula.
- `CLAUDE.md` no necesita cambios — no describe el detalle interno de `CALENTAMIENTO`, solo la marca como "rediseñada" y remite al plan.

## 7. Fuera de alcance

- Cualquier forma de control proporcional real (PID, PWM variable dentro de `APROXIMACION`) — la única actuación sigue siendo ON/OFF bang-bang, tal como se decidió.
- Cambios a `PWM_ACTIVO`/`ESTABLE_PREESTERILIZACION`.
- Margen o parámetro separado entre techo de control y umbral de falla — se usa el mismo valor para ambos, decisión explícita de este diseño.
- Tiempo mínimo de apagado / anti-chattering — bang-bang directo por tick, decisión explícita de este diseño.
- Sensor de líquido secundario (`temp_camara_2`) — pendiente compartido con el resto de la fase, fuera de este cambio.

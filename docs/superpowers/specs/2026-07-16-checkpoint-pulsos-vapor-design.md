# Checkpoint de calentamiento: pulsos de vapor con techo de temperatura

## Contexto

`src/autoclave/state_machine/cycle_phases/calentamiento.py` verifica vapor saturado
en dos checkpoints (80% y 97% de `temperatura_calentamiento`). Mientras un checkpoint
está pendiente, si `P_real < P_sat(T) - tolerancia` (indicio de aire residual / vapor
no saturado), la válvula de vapor se abre de forma **continua**
(`self.set_do.vapor_camara_on()`) hasta la siguiente evaluación.

Como el vapor que entra también calienta la cámara, esta apertura continua puede hacer
que la temperatura suba y alcance `temperatura_calentamiento` sin que el checkpoint
llegue a liberarse por presión. El handoff `2026-07-15` (`docs/handoff/handoff-2026-07-15-calentamiento-analisis.md`)
documentó y corrigió por separado el bug de orden que permitía completar la fase con
un checkpoint pendiente (ver `docs/superpowers/specs/2026-05-26-fases-criticas-ciclo-design.md:120-138`
para el flujo de referencia). Este spec cubre la segunda mitad de esa sesión: mitigar
el escenario en el origen, limitando cuánto puede subir la temperatura mientras se
purga aire residual.

**Relación con el fix de orden:** son dos mecanismos independientes y complementarios.
El fix de orden es la defensa en profundidad (un checkpoint pendiente siempre bloquea
`COMPLETADO`, pase lo que pase). Este cambio es la mitigación en el origen: evita que
la temperatura llegue a dispararse en primer lugar. Ninguno reemplaza al otro.

## Alcance

Solo `src/autoclave/state_machine/cycle_phases/calentamiento.py`, dentro del bloque
`# 4. Lógica de checkpoint` (rama donde `P_real < P_sat(T) - tolerancia`). No cambia:

- La condición de liberación del checkpoint (sigue siendo solo presión dentro de
  tolerancia de `P_sat(T)`, vía `_verificar_vapor_saturado`).
- La rama de exceso de presión (`pres > p_sat + tolerancia` → `vapor_camara_off()`),
  que ya apaga la válvula y no necesita pulsos.
- El fix de orden checkpoint/finalización (ya aplicado, sesión anterior).

## Parámetros nuevos

Se agregan a la sección `"calentamiento"` del JSON de ciclo, mismo formato que los
parámetros existentes (`temperatura_calentamiento`, `rango_presion_calentamiento`, etc.),
en los 4 archivos `*_134.json` (`factory/` y `user/`, `bowe_dick` e `instrumental_134`):

| Parámetro | Tipo | Unidad | Default | Rango sugerido | Descripción |
|---|---|---|---|---|---|
| `margen_techo_calentamiento` | float | °C | 2.0 | 0–10 | Se suma al checkpoint activo (`self._checkpoints[0]`) para formar el techo de temperatura durante la verificación |
| `tiempo_apertura_vapor_checkpoint` | int | sec | 3 | 1–60 | Duración del pulso ON de vapor mientras se purga aire residual |
| `tiempo_cierre_vapor_checkpoint` | int | sec | 5 | 1–60 | Duración de la pausa OFF entre pulsos |

**Ancla del techo:** `checkpoint_actual + margen`, donde `checkpoint_actual` es
`self._checkpoints[0]` (el umbral del checkpoint que se está verificando en ese
momento — 80% o 97% de `t_obj` según cuál esté pendiente). Se recalcula en cada tick,
por lo que se ajusta automáticamente si el checkpoint activo cambia entre 80% y 97%.

**Alcance del margen:** un único parámetro global para toda la fase (no uno por
checkpoint). Se aplica igual al verificar el checkpoint del 80% y al del 97%.

## Cambio de comportamiento

Dentro de la rama `else` (equivalente a `P_real < P_sat(T) - tolerancia`) del bloque de
checkpoint, se reemplaza la apertura continua por un control de pulsos con techo:

```
p_sat  = p_saturacion_kpa(temp)
techo  = self._checkpoints[0] + margen_techo
now    = time.time()

if pres > p_sat + tolerancia:
    self.set_do.vapor_camara_off()
    self._t_pulso_vapor_chk = None
elif temp < techo:
    t_on  = self.cycle.get_param("calentamiento", "tiempo_apertura_vapor_checkpoint")
    t_off = self.cycle.get_param("calentamiento", "tiempo_cierre_vapor_checkpoint")
    if self._t_pulso_vapor_chk is None:
        self._t_pulso_vapor_chk = now
        self._vapor_chk_abierto = True
        self.set_do.vapor_camara_on()
    else:
        elapsed = now - self._t_pulso_vapor_chk
        if self._vapor_chk_abierto and elapsed >= t_on:
            self.set_do.vapor_camara_off()
            self._vapor_chk_abierto = False
            self._t_pulso_vapor_chk = now
        elif not self._vapor_chk_abierto and elapsed >= t_off:
            self.set_do.vapor_camara_on()
            self._vapor_chk_abierto = True
            self._t_pulso_vapor_chk = now
        # si no venció ni t_on ni t_off: mantener la salida como está (no repetir la
        # llamada set_do en cada tick dentro del mismo tramo del pulso)
else:
    # techo alcanzado: verificación continua sin agregar vapor
    self.set_do.vapor_camara_off()
    self._t_pulso_vapor_chk = None
```

(Idéntico al patrón de `_tick_sub_enfriamiento` en `descompresion.py:147-166`, salvo que
acá no hay rama `t_off == 0` — los tiempos de pulso del checkpoint siempre son > 0 por
rango del parámetro.)

Al forzar `vapor_camara_off()` por techo alcanzado (o por exceso de presión), se
resetea `self._t_pulso_vapor_chk = None` para que, cuando vuelva a ser necesario pulsar
(`temp` baja del techo, o la presión vuelve a estar por debajo de `P_sat - tolerancia`),
el siguiente pulso arranque siempre en ON completo — no se preserva fase a mitad de
ciclo ON/OFF entre pausas.

**Estado nuevo en la fase** (inicializado en `reset()`):

- `self._t_pulso_vapor_chk`: timestamp (`time.time()`) de inicio del pulso ON/OFF
  actual, o `None` si no hay pulso en curso.
- `self._vapor_chk_abierto`: booleano, `True` mientras el pulso actual es la mitad ON.

Ambos se reinician a `None` / `False` también cuando un checkpoint se libera
(`self._checkpoints.pop(0)`), para que el siguiente checkpoint (si lo hay) empiece con
un pulso ON limpio en vez de heredar el estado de temporización del checkpoint anterior.

**Condición de liberación del checkpoint:** no cambia. Sigue siendo únicamente
`_verificar_vapor_saturado(temp, pres, tolerancia)` — el techo de temperatura no es un
requisito adicional para liberar, es solo un freno sobre el mecanismo de pulsos.

## Fuera de alcance

- Extraer un helper de pulsos compartido con `descompresion.py` (`_pulse()` en
  `base_fase.py`). Se descartó por ahora: el patrón se repetiría solo dos veces y
  `descompresion.py` es código que funciona hoy y no necesita tocarse para este cambio.
  Revisar si aparece una tercera fase con la misma necesidad.
- Checkpoints 80%/97% en código vs. 50%/90% en el spec original (pendiente arrastrado,
  `handoff-2026-07-02` / `handoff-2026-07-15`, sección "Para continuar" punto 3).
- `presion_add_calentamiento`, posible parámetro vestigial (mismo handoff, punto 4).

## Testing

Casos nuevos en `tests/test_calentamiento_fase.py`:

1. Con `temp < techo` y presión baja (`P_real < P_sat - tolerancia`): la válvula recibe
   pulsos ON siguiendo `tiempo_apertura_vapor_checkpoint` / `tiempo_cierre_vapor_checkpoint`
   (verificar al menos una transición ON→OFF con `time.time()` mockeado o avance de reloj).
2. Con `temp >= techo` y presión baja: la válvula se fuerza OFF y no se llama
   `vapor_camara_on()` en absoluto, aunque la presión siga pidiendo vapor.
3. Al bajar `temp` de nuevo por debajo del techo tras haberlo alcanzado: los pulsos se
   retoman (siguiente pulso arranca en ON).
4. Al liberar un checkpoint con pulsos en curso: `_t_pulso_vapor_chk` y
   `_vapor_chk_abierto` quedan reseteados antes de evaluar el siguiente checkpoint.
5. `test_checkpoint_pendiente_bloquea_completacion` (ya existente, del fix de orden)
   sigue pasando sin modificaciones — confirma que ambos mecanismos coexisten.

Suite completa (`pytest tests/`) debe seguir pasando.

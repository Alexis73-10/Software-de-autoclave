# Handoff — 2026-07-15

## Sesión: Análisis de la fase CALENTAMIENTO — bug de orden en checkpoint vs finalización

### Estado del repo al cerrar

- **Rama:** `dev` (HEAD: `70e73c8`)
- **Cambios de código:** ninguno — sesión de solo análisis/lectura
- **Tests:** sin cambios, no se ejecutó la suite en esta sesión

---

### Lo que se hizo hoy

Sesión puramente de análisis (sin tocar código) sobre `src/autoclave/state_machine/cycle_phases/calentamiento.py`, a pedido del usuario ("analiza la fase de calentamiento y explícame detalladamente").

#### 1. Explicación detallada de la fase CALENTAMIENTO

Se recorrió el flujo completo: inicialización, timeout global, condición de finalización, entrada/lógica de checkpoints (80% y 97% de `temperatura_calentamiento`), y control de rampa bang-bang. Se revisó `base_fase.py` (helpers `_temp_camara`, `_pres_camara`, `_verificar_vapor_saturado`), `steam.py` (fórmula de Antoine para `p_saturacion_kpa`), los parámetros JSON de la sección `"calentamiento"` en `instrumental_134.json`, y `tests/test_calentamiento_fase.py`.

Se confirmó (ya documentado en el handoff anterior `2026-07-02`) que los checkpoints en código son 80%/97%, pero el spec (`docs/superpowers/specs/2026-05-26-fases-criticas-ciclo-design.md:116-117`) documenta 50%/90%. Sigue sin resolverse — ver sección de pendientes.

#### 2. Bug encontrado: orden invertido entre checkpoint y condición de finalización

**Síntoma:** si la presión se queda por debajo de `P_sat(temp)` durante un checkpoint (posible aire residual / vapor no saturado) y la válvula permanece abierta intentando igualar presión, la **temperatura puede seguir subiendo** (el vapor que entra también calienta) y alcanzar `temperatura_calentamiento` **antes** de que el checkpoint se libere.

**Causa raíz — orden de evaluación en `calentamiento.py:update()`:**

```
(código actual)
3. ¿temp >= t_obj?          → COMPLETADO   (líneas 66-85)
4. ¿entra a checkpoint?                     (líneas 87-95)
5. lógica de checkpoint → EN_CURSO          (líneas 97-112)
6. control de rampa
```

El chequeo de finalización se evalúa **antes** que la lógica de checkpoint. Si en un mismo tick `temp >= t_obj` es verdadero, la fase retorna `COMPLETADO` de inmediato sin llegar nunca a evaluar si el checkpoint pendiente se liberó.

**Esto contradice el spec original** (`docs/superpowers/specs/2026-05-26-fases-criticas-ciclo-design.md:120-138`), que define el orden al revés:

```
(spec)
2. Control de rampa
3. Checkpoint (si queda alguno) → EN_CURSO mientras no se libere
4. Condición de finalización → COMPLETADO
```

En el spec, el `return EN_CURSO` del checkpoint corta el flujo antes de llegar a evaluar finalización — por diseño, un checkpoint pendiente **bloquea** la finalización. En la implementación actual eso no ocurre: el checkpoint puede quedar sin resolver y la fase avanza igual a `ESTABILIZACION`.

**Impacto:** el mecanismo de checkpoint existe justamente para detectar aire residual mal purgado (vapor no saturado). Si la fase puede completar sin liberarlo, ese control de calidad queda inoperante en el peor caso — cuando la temperatura "engaña" con una lectura alta mientras el vapor real no está saturado.

**Estado: NO corregido.** Queda como pendiente explícito para la próxima sesión (ver abajo). No se tocó el código.

---

### Cambio de comportamiento planificado (para la próxima sesión)

El usuario definió el rediseño de la lógica de checkpoint cuando la presión está por debajo de la de saturación. **Corrección importante respecto a lo anotado en la conversación inicial:** el nuevo rango de temperatura NO es una segunda condición que deba cumplirse junto con la presión para liberar el checkpoint — el checkpoint se sigue liberando solo por presión, igual que hoy. Es un **freno de seguridad sobre el mecanismo de pulsos**, no un requisito de liberación.

- **Actualmente:** si `P_real < P_sat(temp) - tolerancia`, la válvula se abre de forma continua (`vapor_camara_on()`) hasta la siguiente evaluación.
- **Cambio propuesto:** manejarlo por **pulsos de vapor** (ráfagas cortas) en lugar de apertura continua.
- **Nuevo parámetro:** temperatura añadida / rango de temperatura (nombre a definir), que actúa como **techo de temperatura** durante la verificación del checkpoint.
- **Comportamiento de los pulsos:**
  1. Mientras `P_real < P_sat(temp) - tolerancia` **y** `temp` no ha alcanzado el techo (checkpoint + rango) → sigue metiendo pulsos de vapor.
  2. Si `temp` alcanza/supera el techo → **deja de meter pulsos** (no más `vapor_camara_on()`), pero sigue evaluando presión y temperatura en cada tick (verificación continua, sin agregar vapor).
  3. Cuando `temp` vuelve a bajar por debajo del techo → retoma los pulsos si la presión lo sigue requiriendo.
  4. La condición de liberación del checkpoint no cambia: solo presión dentro de tolerancia de `P_sat(temp)`, como hoy.
- **Propósito:** que la temperatura no se dispare y llegue a temperatura de esterilización sin haber pasado siquiera el primer checkpoint — es decir, actúa como mitigación directa del bug de orden descrito arriba, aunque no lo reemplaza (ver nota abajo).

**Sin definir todavía:**
- Nombre final del nuevo parámetro y su ubicación en el JSON de ciclo.
- Punto de referencia (ancla) del techo de temperatura: ¿relativo al valor del checkpoint (`checkpoint[0]`/`[1]`), a la temperatura al entrar al checkpoint, o un límite absoluto independiente de `t_obj`?
- Duración/intervalo de cada pulso de vapor (tiempo ON / tiempo OFF).
- Si el techo de temperatura es un único parámetro global para la fase o uno por checkpoint.
- **El bug de orden (sección anterior) sigue siendo un problema independiente.** El techo de temperatura debería, en la práctica, evitar que se dispare el escenario del bug — pero no lo corrige a nivel de código: si el techo quedara mal configurado (muy cerca de `t_obj`) o si alguna otra ruta empuja `temp >= t_obj` mientras el checkpoint sigue abierto, la fase completaría igual sin liberar el checkpoint. Se recomienda corregir el orden como defensa en profundidad, no como sustituto del techo de temperatura.

---

### Para continuar

Pendientes identificados, en orden sugerido de abordaje:

1. **Corregir el orden checkpoint → finalización** en `calentamiento.py` (mover el chequeo de completación después de la lógica de checkpoint, o exigir `not self._checkpoints` como condición adicional para `COMPLETADO`). Es prerequisito lógico del punto 2.
2. **Implementar checkpoint por pulsos de vapor + doble condición (presión + temperatura)** — diseño arriba, falta definir parámetros exactos antes de codear. Recomendado pasar por `superpowers:brainstorming` o `superpowers:writing-plans` antes de tocar código, dado que cambia el contrato del parámetro JSON de ciclo.
3. **Checkpoints 80/97% vs spec 50/90%** (arrastrado desde `handoff-2026-07-02`): decidir si se actualiza el spec o el código, y corregir `test_checkpoint_entra_en_sostenimiento` si aplica.
4. `presion_add_calentamiento` en el JSON de ciclo parece redundante/vestigial — el código solo usa `rango_presion_calentamiento`. Revisar si se elimina o se le da uso.
5. Pendientes arrastrados de `handoff-2026-07-02`: Menú E/S (Tasks 4-7), Fase 2 de impresora (impresión en tiempo real durante el ciclo).

---

### Commits de esta sesión

Ninguno — sesión de solo análisis y documentación.

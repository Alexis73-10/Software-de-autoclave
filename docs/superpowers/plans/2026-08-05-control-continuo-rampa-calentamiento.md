# Control continuo de rampa en CALENTAMIENTO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar los tramos discretos `APROXIMACION`/`PWM_ACTIVO` de `calentamiento.py` por un único controlador continuo de `vapor_camara` que nunca exceda `tasa_calentamiento`/`tasa_presion`, nunca inyecte vapor cuando la temperatura corre por delante de una presión no saturada, y module la válvula con pulsos cada vez más cortos a medida que se acerca al objetivo — sin depender de una referencia móvil (`P_sat(temp_actual)`) para decidir el tramo.

**Architecture:** Tres funciones puras (`_duty_por_tasa`, `_duty_por_proximidad`, `_duty_por_calidad_vapor`) calculan cada una un duty cycle entre 0 y 1; `update()` toma el mínimo de las tres, aplica un corte duro de emergencia si la presión supera el techo (`p_obj + p_add`), y alimenta el resultado al mismo helper `_tick_dos_estados` que ya usan PWM_ACTIVO/ESTERILIZACION. Sin estado de tramo (`_en_pwm` desaparece); el control es el mismo en cada tick desde que empieza la fase hasta que se cruza a `ESTABLE_PREESTERILIZACION` (paso 7, sin cambios).

**Tech Stack:** Python 3.14, pytest, `unittest.mock.MagicMock` (mismo patrón de test ya usado en el archivo).

## Nota de coordinación (leer antes de dispatchar la Tarea 2)

Este plan se escribió en paralelo a otra sesión que implementó y commiteó por separado el "mecanismo 1" de un spec anterior (`docs/superpowers/specs/2026-08-05-fix-overshoot-calentamiento-design.md`, ya reemplazado): el gate de entrada a PWM_ACTIVO quedó anclado a `pres >= p_obj - rango_cal or temp >= t_obj` (commits `211f2fd`, `5201370` en `dev`). Ese gate — y el estado `_en_pwm` que lo acompaña — es exactamente lo que la Tarea 2 de este plan reemplaza por completo. El código base real en `dev` al momento de escribir este plan (después de esos commits) es el que se cita textualmente en la Tarea 2, Step 4 — **no** una versión anterior. Si al dispatchar la Tarea 2 el archivo real difiere del texto citado ahí, releer `src/autoclave/state_machine/cycle_phases/calentamiento.py` antes de proceder y ajustar el brief.

## Global Constraints

- No se agregan parámetros nuevos a ningún JSON de ciclo (factory ni user) — spec sección 4. `_FACTOR_TOPE_TEMPERATURA = 0.97` es una constante de módulo fija, no un parámetro de ciclo.
- `ESTABLE_PREESTERILIZACION`, los escapes (`descompresion_lenta`/`rapida`), el cálculo de pendiente del paso 3 (`_historial_pendiente`) y el timeout global de fase no se modifican — spec secciones 5 y 7.
- Cada test debe evitar depender de `time.sleep` real; usar los mismos patrones de manipulación directa de atributos de timer (`fase._t_pulso_pwm -= N`) que ya usa el resto del archivo.
- Referencia autoritativa de la fórmula: `docs/superpowers/specs/2026-08-05-control-continuo-rampa-calentamiento-design.md` (versión con `duty_calidad_vapor` como tercer término y `min()`, no `max()`, en `duty_proximidad`).

---

### Task 1: Funciones puras de duty cycle

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py` (agregar constante y funciones a nivel de módulo, después de `_VENTANA_PENDIENTE_SEG` y antes de `class CalentamientoFase`)
- Test: `tests/test_calentamiento_fase.py` (nueva sección al final del archivo)

**Interfaces:**
- Produces: `_duty_por_tasa(tasa_actual: float | None, tasa_max: float) -> float`, `_duty_por_proximidad(dist: float, margen: float) -> float`, `_duty_por_calidad_vapor(temp: float, pres: float, t_obj: float, p_add: float) -> float` — las tres son funciones puras de módulo (no métodos), usadas por Task 2. `_FACTOR_TOPE_TEMPERATURA = 0.97` es la constante de módulo que usa la tercera.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/test_calentamiento_fase.py`:

```python
# ── Funciones puras de duty cycle (control continuo) ─────────────────────
from autoclave.state_machine.cycle_phases.calentamiento import (
    _duty_por_tasa,
    _duty_por_proximidad,
    _duty_por_calidad_vapor,
)


def test_duty_por_tasa_sin_restriccion_si_tasa_max_es_cero():
    assert _duty_por_tasa(tasa_actual=1000.0, tasa_max=0.0) == 1.0


def test_duty_por_tasa_sin_restriccion_si_tasa_actual_es_none():
    assert _duty_por_tasa(tasa_actual=None, tasa_max=10.0) == 1.0


def test_duty_por_tasa_sin_restriccion_si_tasa_actual_es_negativa_o_cero():
    assert _duty_por_tasa(tasa_actual=0.0, tasa_max=10.0) == 1.0
    assert _duty_por_tasa(tasa_actual=-5.0, tasa_max=10.0) == 1.0


def test_duty_por_tasa_uno_si_pendiente_dentro_del_limite():
    assert _duty_por_tasa(tasa_actual=5.0, tasa_max=10.0) == 1.0


def test_duty_por_tasa_proporcional_si_pendiente_excede_el_limite():
    assert _duty_por_tasa(tasa_actual=20.0, tasa_max=10.0) == 0.5


def test_duty_por_proximidad_uno_lejos_del_objetivo():
    assert _duty_por_proximidad(dist=10.0, margen=2.0) == 1.0


def test_duty_por_proximidad_cero_en_o_despues_del_objetivo():
    assert _duty_por_proximidad(dist=0.0, margen=2.0) == 0.0
    assert _duty_por_proximidad(dist=-5.0, margen=2.0) == 0.0


def test_duty_por_proximidad_interpola_dentro_de_la_banda():
    assert _duty_por_proximidad(dist=1.0, margen=2.0) == 0.5


def test_duty_por_proximidad_margen_cero_es_un_escalon():
    assert _duty_por_proximidad(dist=5.0, margen=0.0) == 1.0
    assert _duty_por_proximidad(dist=0.0, margen=0.0) == 0.0
    assert _duty_por_proximidad(dist=-1.0, margen=0.0) == 0.0


def test_duty_por_calidad_vapor_sin_restriccion_bajo_el_tope_del_97_por_ciento():
    # t_obj=134 -> tope = 129.98; temp=129.0 esta debajo, sin importar la presion
    assert _duty_por_calidad_vapor(temp=129.0, pres=0.0, t_obj=134.0, p_add=11.0) == 1.0


def test_duty_por_calidad_vapor_cero_si_supera_el_tope_y_presion_no_corresponde():
    from autoclave.core.runtime.steam import p_saturacion_kpa
    # temp=130 >= tope (129.98); presion muy por debajo de P_sat(130)+11
    assert _duty_por_calidad_vapor(temp=130.0, pres=1.0, t_obj=134.0, p_add=11.0) == 0.0


def test_duty_por_calidad_vapor_uno_si_presion_ya_corresponde_a_la_temperatura():
    from autoclave.core.runtime.steam import p_saturacion_kpa
    temp = 130.0
    p_min = p_saturacion_kpa(temp) + 11.0
    assert _duty_por_calidad_vapor(temp=temp, pres=p_min, t_obj=134.0, p_add=11.0) == 1.0
```

- [ ] **Step 2: Correr los tests y confirmar que fallan**

Run: `python -m pytest tests/test_calentamiento_fase.py -k duty_por -v`
Expected: FAIL — `ImportError: cannot import name '_duty_por_tasa'`

- [ ] **Step 3: Implementar las funciones**

En `src/autoclave/state_machine/cycle_phases/calentamiento.py`, insertar después de la constante `_VENTANA_PENDIENTE_SEG` (línea 49 actual) y antes de `class CalentamientoFase`:

```python
_FACTOR_TOPE_TEMPERATURA = 0.97


def _duty_por_tasa(tasa_actual, tasa_max):
    """Duty (0 a 1) por limite de pendiente: 1.0 si no hay restriccion
    configurada o la pendiente ya esta dentro del limite; cae
    proporcionalmente (tasa_max / tasa_actual) si lo excede."""
    if tasa_max <= 0 or tasa_actual is None or tasa_actual <= 0:
        return 1.0
    return min(tasa_max / tasa_actual, 1.0)


def _duty_por_proximidad(dist, margen):
    """Fraccion de rampa restante hacia el objetivo: 1.0 a `margen` unidades
    o mas de distancia, 0.0 en o despues del objetivo (dist <= 0), lineal
    en el medio."""
    if margen <= 0:
        return 1.0 if dist > 0 else 0.0
    return max(0.0, min(dist / margen, 1.0))


def _duty_por_calidad_vapor(temp, pres, t_obj, p_add):
    """Corte binario (0 o 1): una vez que temp cruza el 97% de t_obj, exige
    que la presion ya corresponda a la temperatura real (P_sat(temp) +
    p_add) -- evita inyectar cuando el sensor de temperatura corre por
    delante de vapor no saturado."""
    temp_cap = _FACTOR_TOPE_TEMPERATURA * t_obj
    if temp < temp_cap:
        return 1.0
    p_min_para_temp = p_saturacion_kpa(temp) + p_add
    return 1.0 if pres >= p_min_para_temp else 0.0
```

- [ ] **Step 4: Correr los tests y confirmar que pasan**

Run: `python -m pytest tests/test_calentamiento_fase.py -k duty_por -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_fase.py
git commit -m "feat: agregar funciones puras de duty cycle para control continuo de CALENTAMIENTO"
```

---

### Task 2: Reemplazar el gate y el control de `vapor_camara` por el controlador continuo

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py` (`reset()`, `update()` pasos 4-5, docstring de cabecera del módulo)
- Test: `tests/test_calentamiento_fase.py` (eliminar tests obsoletos atados a `_en_pwm`, agregar tests del controlador continuo)

**Interfaces:**
- Consumes: `_duty_por_tasa`, `_duty_por_proximidad`, `_duty_por_calidad_vapor` (Task 1); `self._tick_dos_estados` (ya existente, sin cambios); `tasa_t`, `tasa_p`, `t_obj`, `p_obj`, `p_add`, `factor_pct`, `rango_cal`, `intervalo`, `temp`, `pres`, `now` (ya calculados en pasos previos de `update()`, sin cambios).
- Produces: `self._duty_actual` (float, nuevo atributo de instancia) — expone el duty aplicado en el último tick, mismo rol de observabilidad para tests que ya cumplen `self._pwm_abierto`/`self._en_sostenimiento`.

- [ ] **Step 1: Confirmar el estado real del archivo antes de escribir tests**

Leer `src/autoclave/state_machine/cycle_phases/calentamiento.py` y confirmar que el paso 4 actual es:

```python
        # ── 4. Entrada a PWM (unidireccional) ─────────────────────────────
        # Ancla la entrada al objetivo fijo (p_obj/t_obj), no a la curva de
        # saturación de la temperatura actual (que se mueve mientras sube) —
        # ver docs/superpowers/specs/2026-08-05-fix-overshoot-calentamiento-design.md.
        if not self._en_pwm and (pres >= p_obj - rango_cal or temp >= t_obj):
            self._en_pwm = True
            logger.info("Calentamiento: objetivo cercano (%.1f kPa / %.1f°C) — entra a PWM_ACTIVO", p_obj, t_obj)

        # ── 5. Control de vapor_camara ─────────────────────────────────────
        if not self._en_pwm:
            ...
        else:
            ...
```

(gate ya anclado a `p_obj`/`t_obj` por el commit `5201370`, ver nota de coordinación al inicio de este plan). Si el archivo real difiere de este bloque, detenerse y pedir el bloque actual antes de continuar — el Step 4 de esta tarea reemplaza exactamente este texto.

- [ ] **Step 2: Escribir los tests que fallan (nuevo comportamiento)**

En `tests/test_calentamiento_fase.py`, agregar esta sección nueva (después de la sección "PWM duty cycle" existente, antes de tocar nada más):

```python
# ── Controlador continuo (RAMPA) ──────────────────────────────────────────

def test_lejos_del_objetivo_duty_es_uno_y_vapor_on_continuo():
    fase, estado, set_do = _make_fase(t_obj=134.0, t_inicial=20.0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 1.0
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_duty_baja_por_presion_cercana_al_objetivo_aunque_lejos_de_p_sat_temp():
    """Regresion del bug real (ciclo 72, 2026-08-05): la presion corre
    persistentemente por encima de P_sat(temp_actual) durante toda la
    subida (chaqueta/aire residual/calibracion). duty_proximidad se mide
    contra p_obj fijo, nunca contra P_sat(temp_actual) -- por eso ya cae
    antes de cruzar el objetivo. temp=110 se mantiene bien debajo del tope
    del 97% (129.98 con t_obj=134) para que duty_calidad_vapor no
    interfiera en este caso."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 110.0  # P_sat(110) ~ 146 kPa, muy lejos de p_obj
    estado.sensores_pres["pres_camara"] = p_obj - 1.0  # a 1 kPa del objetivo, dentro de rango=2.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual < 1.0


def test_calidad_vapor_fuerza_cero_si_temp_supera_el_tope_y_presion_no_corresponde():
    """Si la temperatura ya cruzo t_obj (por lo tanto tambien el tope del
    97%) pero la presion esta muy por debajo de lo que esa temperatura
    implicaria (vapor no saturado), duty_calidad_vapor gana sobre
    duty_proximidad y fuerza duty a 0 -- mas estricto que el duty_estable
    que aplicaria por proximidad sola. Reemplaza el viejo seguro
    unidireccional del gate anterior (temp >= t_obj) con uno mas estricto."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = 50.0  # muy por debajo de lo que P_sat(134)+11 exige
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 0.0


def test_calidad_vapor_no_restringe_por_debajo_del_tope_de_97_por_ciento():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 129.0  # < 0.97*134 = 129.98
    estado.sensores_pres["pres_camara"] = 50.0  # lejos de P_sat(129)+11, pero el tope no se activo aun
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 1.0  # ni proximidad ni calidad_vapor restringen todavia


def test_duty_estable_igual_al_factor_configurado_en_el_objetivo():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=70.0)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()
    assert fase._duty_actual == 0.3  # 1 - 70/100


def test_duty_estable_cero_si_factor_es_cien():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=100.0)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 0.0
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_duty_interpola_linealmente_dentro_de_la_banda_de_proximidad():
    """Ejercita la interpolacion via la distancia de PRESION (no de
    temperatura): con temp=100 bien debajo del tope del 97%,
    duty_calidad_vapor no interfiere y se puede aislar la formula de
    duty_proximidad."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 100.0  # dist_t grande -> prox_t=1.0 (clamped)
    estado.sensores_pres["pres_camara"] = p_obj - 1.0  # dist_p=1.0, margen=2.0 -> prox_p=0.5
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    # cercania=min(1.0, 0.5)=0.5 -> duty_proximidad=0.5+0.5*0.5=0.75
    assert abs(fase._duty_actual - 0.75) < 1e-9


def test_techo_independiente_fuerza_duty_cero_sin_importar_el_resto():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=0.0)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj + 20.0  # supera el techo (p_obj + presion_add)
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual == 0.0
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_duty_tasa_restringe_incluso_cerca_del_objetivo():
    """Cambio de comportamiento intencional respecto al diseno anterior: la
    tasa ya no es exclusiva de un tramo de aproximacion -- restringe en
    todo momento. Se ejercita via tasa_presion, con temp=100 (debajo del
    tope del 97%) para que duty_calidad_vapor no enmascare el efecto, y un
    salto de presion pequeno (+3 kPa) para quedar bajo el techo
    independiente (p_obj + 11) y no enmascararlo tampoco."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=0.0,
                                       tasa_calentamiento=200.0, tasa_presion=10.0)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 100.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # duty_proximidad ya en duty_estable=1.0 (factor=0), sin tasa aun

    _sembrar_historial(fase, 100.0, p_obj, 10)
    estado.sensores_pres["pres_camara"] = p_obj + 3.0  # 18 kPa/min > tasa_presion=10, bajo el techo
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._duty_actual < 1.0


def test_pwm_pulso_on_luego_off_por_tiempo():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0, intervalo=2)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    set_do.reset_mock()
    result = fase.update()  # duty=0.5 -> primer pulso ON
    assert result == FaseResult.EN_CURSO
    assert fase._pwm_abierto is True
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()

    set_do.reset_mock()
    fase._t_pulso_pwm -= 2  # simular que paso t_on (50% de 2s = 1s)
    fase.update()
    assert fase._pwm_abierto is False
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_pwm_factor_cero_permanece_encendido():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=0.0, intervalo=2)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()
    set_do.reset_mock()
    fase.update()
    set_do.vapor_camara_off.assert_not_called()
    set_do.vapor_camara_on.assert_called()
```

- [ ] **Step 3: Eliminar los tests obsoletos atados a `_en_pwm`**

Borrar de `tests/test_calentamiento_fase.py` (quedan reemplazados por los del Step 2 o ya no aplican porque el estado/tramo que verifican desaparece):

- `test_aproximacion_vapor_on_continuo_lejos_de_la_banda` (reemplazado por `test_lejos_del_objetivo_duty_es_uno_y_vapor_on_continuo`)
- `test_entra_a_pwm_dentro_de_la_banda`
- `test_pwm_no_retorna_a_aproximacion_si_sale_de_la_banda`
- `test_entra_a_pwm_por_presion_cercana_al_objetivo_aunque_lejos_de_p_sat_temp` (reemplazado por `test_duty_baja_por_presion_cercana_al_objetivo_aunque_lejos_de_p_sat_temp`)
- `test_entra_a_pwm_por_temperatura_si_presion_esta_rezagada` (el seguro que verificaba — entrar a PWM_ACTIVO por temperatura sola — queda superado por `test_calidad_vapor_fuerza_cero_si_temp_supera_el_tope_y_presion_no_corresponde`, que es más estricto: fuerza `duty=0`, no solo `duty_estable`)
- `test_pwm_pulso_on_luego_off_por_tiempo` (la versión vieja, que arranca provocando la entrada a PWM_ACTIVO — queda reemplazada por la versión nueva agregada en el Step 2 con el mismo nombre)
- `test_pwm_factor_cero_permanece_encendido` (idem, reemplazada por la versión nueva del Step 2)
- `test_pwm_activo_ignora_tasa_calentamiento_excedida` (el comportamiento que verifica — la tasa es exclusiva de un tramo — ya no existe; ver `test_duty_tasa_restringe_incluso_cerca_del_objetivo` en el Step 2, que verifica lo opuesto a propósito)
- Toda la sección `# ── Control por tasa en APROXIMACION (bang-bang) ──`: `test_aproximacion_bangbang_on_primer_tick_sin_pendiente_disponible`, `test_aproximacion_bangbang_on_si_tasas_dentro_del_limite`, `test_aproximacion_bangbang_off_si_tasa_temperatura_excede`, `test_aproximacion_bangbang_off_si_tasa_presion_excede`, `test_aproximacion_bangbang_vuelve_a_on_sin_tiempo_minimo_de_apagado`, `test_aproximacion_bangbang_tasa_temperatura_deshabilitada`, `test_aproximacion_bangbang_tasa_presion_deshabilitada`, `test_aproximacion_bangbang_no_apaga_por_caida_abrupta_de_temperatura`, `test_tasa_excedida_muchos_ticks_consecutivos_nunca_produce_fallo`

  Estas prueban un ON/OFF binario de un solo tick que ya no existe (`duty_tasa` es proporcional, no binario) — el comportamiento subyacente que importa (tasa deshabilitada con 0, sin dato = sin restricción, no produce FALLO, no limita caída de temperatura) ya está cubierto por los tests puros de `_duty_por_tasa` del Task 1 y por `test_duty_tasa_restringe_incluso_cerca_del_objetivo` a nivel de integración.

- [ ] **Step 4: Correr los tests nuevos y confirmar que fallan**

Run: `python -m pytest tests/test_calentamiento_fase.py -k "duty_baja or duty_estable or duty_interpola or techo_independiente or duty_tasa_restringe or lejos_del_objetivo or calidad_vapor" -v`
Expected: FAIL — `AttributeError: 'CalentamientoFase' object has no attribute '_duty_actual'`

- [ ] **Step 5: Implementar el controlador continuo**

En `src/autoclave/state_machine/cycle_phases/calentamiento.py`, dentro de `reset()`, reemplazar:

```python
        self._en_pwm = False
```

por:

```python
        self._duty_actual = None
```

Luego, en `update()`, reemplazar por completo los pasos 4 y 5 actuales (confirmados en el Step 1 de esta tarea: el gate `if not self._en_pwm and (pres >= p_obj - rango_cal or temp >= t_obj): ...` seguido del bloque `if not self._en_pwm: ... else: ...`) por:

```python
        # ── 4. Duty cycle continuo de vapor_camara ─────────────────────────
        # Reemplaza los tramos discretos APROXIMACION/PWM_ACTIVO: duty_tasa
        # limita la pendiente (paso 3), duty_proximidad se acerca a
        # duty_estable a medida que temp/pres se acercan a los objetivos
        # fijos t_obj/p_obj (nunca contra P_sat(temp_actual)), y
        # duty_calidad_vapor corta a 0 si la temperatura ya cruzo el tope
        # del 97% pero la presion no corresponde a vapor saturado a esa
        # temperatura. Gana el mas restrictivo (min); el techo independiente
        # corta a 0 sin importar el resto si la presion ya rebaso lo
        # tolerado.
        duty_tasa = min(
            _duty_por_tasa(tasa_t, tasa_t_max),
            _duty_por_tasa(tasa_p, tasa_p_max),
        )

        duty_estable = 1.0 - factor_pct / 100.0
        cercania = min(
            _duty_por_proximidad(t_obj - temp, rango_cal),
            _duty_por_proximidad(p_obj - pres, rango_cal),
        )
        duty_proximidad = duty_estable + (1.0 - duty_estable) * cercania

        duty_calidad_vapor = _duty_por_calidad_vapor(temp, pres, t_obj, p_add)

        duty = min(duty_tasa, duty_proximidad, duty_calidad_vapor)

        p_techo = p_obj + p_add
        if pres >= p_techo:
            duty = 0.0

        self._duty_actual = duty

        t_on_pwm = intervalo * duty
        t_off_pwm = intervalo - t_on_pwm
        self._tick_dos_estados(
            "_t_pulso_pwm", "_pwm_abierto", t_on_pwm, t_off_pwm,
            self.set_do.vapor_camara_on, self.set_do.vapor_camara_off, now,
        )
```

Actualizar el docstring de cabecera del módulo (líneas 1-31 actuales) para describir la secuencia `RAMPA (control continuo) → ESTABLE_PREESTERILIZACION` en vez de `APROXIMACION → PWM_ACTIVO → ESTABLE_PREESTERILIZACION`, resumiendo los tres términos del duty (tasa, proximidad, calidad de vapor) y referenciando `docs/superpowers/specs/2026-08-05-control-continuo-rampa-calentamiento-design.md`.

- [ ] **Step 6: Correr toda la suite de `calentamiento` y confirmar que pasa**

Run: `python -m pytest tests/test_calentamiento_fase.py -v`
Expected: PASS — todos los tests (los que quedaron sin tocar de ESTABLE_PREESTERILIZACION/escapes/timeout/sensores, más los nuevos del controlador continuo).

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_fase.py
git commit -m "feat: reemplazar tramos APROXIMACION/PWM_ACTIVO por controlador continuo en CALENTAMIENTO"
```

---

### Task 3: Actualizar documentación de proyecto

**Files:**
- Modify: `CLAUDE.md` (sección de `calentamiento.py`)

**Interfaces:**
- Consumes: nada (solo texto descriptivo, sin código).

- [ ] **Step 1: Actualizar la descripción de `calentamiento.py` en CLAUDE.md**

En la sección "Fases y su estado de diseño", reemplazar el bullet de `calentamiento.py`:

```markdown
- `calentamiento.py` — **rediseñado** (ver `docs/mis_plans/planeacion_fase_calentamiento.md`): tramos APROXIMACION → PWM_ACTIVO → ESTABLE_PREESTERILIZACION, sin retroceso entre ellos. ESTABLE_PREESTERILIZACION exige una ventana continua de estabilidad (con reinicio ante overshoot) antes de entregar control a ESTERILIZACION — fusiona lo que antes era la fase separada `EstabilizacionFase` (ver `docs/superpowers/specs/2026-08-04-fusion-calentamiento-estabilizacion-design.md`).
```

por:

```markdown
- `calentamiento.py` — **rediseñado**: RAMPA (control continuo de `vapor_camara` vía duty cycle — el mínimo entre tres términos: un límite de pendiente `tasa_calentamiento`/`tasa_presion`, una aproximación lineal a `factor_calentamiento` a medida que `temp`/`pres` se acercan a los objetivos fijos, y un corte si la temperatura supera el 97% del objetivo sin que la presión corresponda a vapor saturado — más un techo independiente de presión como resguardo — ver `docs/superpowers/specs/2026-08-05-control-continuo-rampa-calentamiento-design.md`) → ESTABLE_PREESTERILIZACION. ESTABLE_PREESTERILIZACION exige una ventana continua de estabilidad (con reinicio ante overshoot) antes de entregar control a ESTERILIZACION — fusiona lo que antes era la fase separada `EstabilizacionFase` (ver `docs/superpowers/specs/2026-08-04-fusion-calentamiento-estabilizacion-design.md`).
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: actualizar CLAUDE.md con el controlador continuo de RAMPA en CALENTAMIENTO"
```

---

### Task 4: Verificación final de la suite completa

**Files:**
- Ninguno (solo verificación, sin cambios de código).

- [ ] **Step 1: Correr toda la suite de tests del proyecto**

Run: `python -m pytest tests/ -v`
Expected: PASS — sin regresiones en otras fases (en particular `test_esterilizacion_fase.py` y `test_steam.py`, que no deberían verse afectados por este cambio).

- [ ] **Step 2: Confirmar que no quedan referencias muertas a `_en_pwm`**

Run: `grep -rn "_en_pwm" src/ tests/`
Expected: sin resultados (o solo en `src/logs/autoclave.log`, que es un log histórico, no código).

# Checkpoint de Calentamiento por Pulsos de Vapor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar la apertura continua de vapor durante los checkpoints de la fase CALENTAMIENTO por pulsos ON/OFF limitados por un techo de temperatura, para que la temperatura no se dispare hacia `t_obj` mientras se purga aire residual / vapor no saturado.

**Architecture:** Cambio contenido en un solo archivo de lógica (`calentamiento.py`) más 4 archivos de configuración JSON. Dentro del bloque de checkpoint existente, la rama que hoy llama `vapor_camara_on()` de forma continua pasa a togglear ON/OFF con temporizador (mismo patrón ya usado en `descompresion.py:147-166`), y no pulsa en absoluto si `temp` alcanza un techo (`checkpoint_actual + margen`).

**Tech Stack:** Python 3.14, pytest, `unittest.mock.MagicMock` para los tests de fase (mismo patrón que el resto de `tests/test_calentamiento_*.py`).

## Global Constraints

- La condición de liberación del checkpoint no cambia: solo `_verificar_vapor_saturado` (presión dentro de tolerancia de `P_sat(T)`). El techo de temperatura es un freno sobre los pulsos, no un requisito adicional de liberación.
- No usar valores `default=` en las llamadas a `cycle.get_param(...)` para los parámetros nuevos — el codebase ya eliminó los defaults silenciosos para esta fase (commit `70e73c8`); un ciclo mal configurado debe fallar de forma visible, no operar con un valor hardcodeado.
- No tocar `descompresion.py` ni extraer un helper compartido de pulsos (fuera de alcance del spec).
- No cambiar la rama de exceso de presión (`pres > p_sat + tolerancia` → `vapor_camara_off()`).
- Spec de referencia: `docs/superpowers/specs/2026-07-16-checkpoint-pulsos-vapor-design.md`.

---

### Task 1: Agregar los parámetros nuevos a los 4 JSON de ciclo

**Files:**
- Modify: `src/autoclave/cycles/factory/instrumental_134.json`
- Modify: `src/autoclave/cycles/factory/bowe_dick.json`
- Modify: `src/autoclave/cycles/user/instrumental_134.json`
- Modify: `src/autoclave/cycles/user/bowe_dick.json`

**Interfaces:**
- Produces: 3 claves nuevas dentro de `parameters.calentamiento` en cada archivo, leídas por `Cycle.get_param("calentamiento", <clave>)` (ver `src/autoclave/core/managers/cycle_manager.py:16`) — consumidas por Task 3.

- [ ] **Step 1: Agregar las 3 claves a `parameters.calentamiento` en los 4 archivos**

En cada uno de los 4 archivos, dentro del objeto `parameters.calentamiento` (ya contiene `temperatura_calentamiento`, `tasa_calentamiento`, `timeout_calentamiento`, `rango_presion_calentamiento`, etc.), agregar estas 3 entradas con el mismo formato que las existentes:

```json
    "margen_techo_calentamiento": {
      "value": 2.0,
      "type": "float",
      "unit": "°C",
      "min": 0,
      "max": 10
    },
    "tiempo_apertura_vapor_checkpoint": {
      "value": 3,
      "type": "int",
      "unit": "sec",
      "min": 1,
      "max": 60
    },
    "tiempo_cierre_vapor_checkpoint": {
      "value": 5,
      "type": "int",
      "unit": "sec",
      "min": 1,
      "max": 60
    }
```

Insertarlas justo después de `"rango_presion_calentamiento"` en cada archivo, respetando la indentación (2 espacios) y las comas del JSON circundante.

- [ ] **Step 2: Verificar que los 4 archivos cargan y exponen las 3 claves**

Run:
```bash
python -c "
import json
archivos = [
    'src/autoclave/cycles/factory/instrumental_134.json',
    'src/autoclave/cycles/factory/bowe_dick.json',
    'src/autoclave/cycles/user/instrumental_134.json',
    'src/autoclave/cycles/user/bowe_dick.json',
]
claves = ['margen_techo_calentamiento', 'tiempo_apertura_vapor_checkpoint', 'tiempo_cierre_vapor_checkpoint']
for path in archivos:
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    calentamiento = data['parameters']['calentamiento']
    faltantes = [c for c in claves if c not in calentamiento]
    print(path, 'OK' if not faltantes else f'FALTAN: {faltantes}')
"
```
Expected: las 4 líneas terminan en `OK`. Si algún archivo imprime `FALTAN: [...]`, el JSON tiene un error de sintaxis o la clave quedó mal ubicada — revisar antes de continuar.

- [ ] **Step 3: Commit**

```bash
git add src/autoclave/cycles/factory/instrumental_134.json src/autoclave/cycles/factory/bowe_dick.json src/autoclave/cycles/user/instrumental_134.json src/autoclave/cycles/user/bowe_dick.json
git commit -m "feat: agregar parámetros de pulso de vapor y techo al checkpoint de calentamiento"
```

---

### Task 2: Escribir los tests de pulsos y techo (deben fallar contra el código actual)

**Files:**
- Modify: `tests/test_calentamiento_fase.py`

**Interfaces:**
- Consumes: `CalentamientoFase` (constructor y `update()`) de `src/autoclave/state_machine/cycle_phases/calentamiento.py`; `p_saturacion_kpa` de `autoclave.core.runtime.steam`.
- Produces: 4 tests nuevos que Task 3 debe poner en verde. Todos usan `_make_fase` (fixture ya existente en este archivo, líneas 7-30).

- [ ] **Step 1: Agregar las 3 claves nuevas al mock de `get_param` en `_make_fase`**

Editar la función `_make_fase` (líneas 7-30 de `tests/test_calentamiento_fase.py`) agregando las 3 claves nuevas al diccionario `valores` dentro de `get_param`:

```python
def _make_fase(t_obj=134.0, tasa=5.0, timeout_min=60, tolerancia=9.0, t_inicial=20.0,
               margen_techo=2.0, tiempo_apertura=3, tiempo_cierre=5):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": t_inicial}
    estado.sensores_pres = {"pres_camara": 100.0}
    estado.fase_en_sostenimiento = False
    set_do = MagicMock()
    cycle  = MagicMock()
    def get_param(seccion, param, default=None):
        valores = {
            "temperatura_calentamiento": t_obj,
            "tasa_calentamiento":        tasa,
            "timeout_calentamiento":     timeout_min,
            "rango_presion_calentamiento": tolerancia,
            "margen_techo_calentamiento": margen_techo,
            "tiempo_apertura_vapor_checkpoint": tiempo_apertura,
            "tiempo_cierre_vapor_checkpoint": tiempo_cierre,
        }
        return valores.get(param, default)
    cycle.get_param.side_effect = get_param
    config = MagicMock()
    alarms = MagicMock()
    cap    = MagicMock()
    cap.has_liquid_sensor = False

    fase = CalentamientoFase(estado, set_do, cycle, config, alarms, cap)
    fase.reset()
    return fase, estado, set_do
```

Esto no cambia el comportamiento de ningún test existente: los parámetros nuevos tienen defaults (`margen_techo=2.0`, `tiempo_apertura=3`, `tiempo_cierre=5`) que ningún test previo consulta todavía.

- [ ] **Step 2: Agregar los 4 tests nuevos al final del archivo**

```python
def test_checkpoint_pulso_on_luego_off_por_tiempo():
    """Presión baja y temp por debajo del techo → pulsos ON/OFF por tiempo."""
    fase, estado, set_do = _make_fase(t_obj=134.0, tolerancia=9.0)
    fase.update()  # inicializar

    estado.sensores_temp["temp_camara"] = 107.2  # 80% de 134 → checkpoint 1
    estado.sensores_pres["pres_camara"] = 50.0   # muy por debajo de P_sat(107.2)-9
    result = fase.update()  # entra a checkpoint + primer pulso
    assert result == FaseResult.EN_CURSO
    assert fase._vapor_chk_abierto is True
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()

    set_do.reset_mock()
    fase._t_pulso_vapor_chk -= 4  # simular que ya pasó tiempo_apertura_vapor_checkpoint (3s)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._vapor_chk_abierto is False
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_checkpoint_techo_alcanzado_fuerza_off_sin_pulsar():
    """Si temp alcanza el techo (checkpoint + margen), deja de pulsar aunque la presión siga baja."""
    fase, estado, set_do = _make_fase(t_obj=134.0, tolerancia=9.0, margen_techo=2.0)
    fase.update()  # inicializar

    # checkpoint 1 = 107.2, techo = 107.2 + 2.0 = 109.2
    estado.sensores_temp["temp_camara"] = 109.2
    estado.sensores_pres["pres_camara"] = 50.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._t_pulso_vapor_chk is None
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_checkpoint_retoma_pulso_al_bajar_del_techo():
    """Tras frenar por techo, si temp vuelve a bajar del techo, retoma pulsos ON."""
    fase, estado, set_do = _make_fase(t_obj=134.0, tolerancia=9.0, margen_techo=2.0)
    fase.update()  # inicializar

    estado.sensores_temp["temp_camara"] = 109.2  # en el techo → frena
    estado.sensores_pres["pres_camara"] = 50.0
    fase.update()
    assert fase._t_pulso_vapor_chk is None

    set_do.reset_mock()
    estado.sensores_temp["temp_camara"] = 108.0  # baja del techo de nuevo
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._vapor_chk_abierto is True
    set_do.vapor_camara_on.assert_called()


def test_checkpoint_liberado_resetea_estado_de_pulso():
    """Al liberar el checkpoint, el estado de temporización del pulso queda limpio."""
    from autoclave.core.runtime.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(t_obj=134.0, tolerancia=9.0)
    fase.update()  # inicializar

    estado.sensores_temp["temp_camara"] = 107.2
    estado.sensores_pres["pres_camara"] = 50.0
    fase.update()  # entra a checkpoint, arranca pulso ON
    assert fase._t_pulso_vapor_chk is not None

    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(107.2)  # presión correcta → libera
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_checkpoint is False
    assert fase._t_pulso_vapor_chk is None
    assert fase._vapor_chk_abierto is False
```

- [ ] **Step 3: Correr los tests nuevos y confirmar que fallan contra el código actual**

Run: `pytest tests/test_calentamiento_fase.py -v -k "pulso or techo"`
Expected: los 4 tests nuevos fallan (el código actual todavía abre la válvula de forma continua sin togglear ni respetar un techo — no existen los atributos `_vapor_chk_abierto` / `_t_pulso_vapor_chk`, así que las aserciones sobre ellos deben dar `AttributeError` o `AssertionError`). Los tests preexistentes en el archivo deben seguir en verde.

- [ ] **Step 4: Commit**

```bash
git add tests/test_calentamiento_fase.py
git commit -m "test: agregar casos para pulsos de vapor con techo en checkpoint de calentamiento"
```

---

### Task 3: Implementar los pulsos de vapor con techo en `calentamiento.py`

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py:21-28` (método `reset`)
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py:79-95` (bloque `# 4. Lógica de checkpoint`)
- Modify: `tests/test_calentamiento_fase.py:69-81` (ajustar aserción que queda inválida con el nuevo comportamiento)

**Interfaces:**
- Consumes: `self.cycle.get_param("calentamiento", "margen_techo_calentamiento")`, `self.cycle.get_param("calentamiento", "tiempo_apertura_vapor_checkpoint")`, `self.cycle.get_param("calentamiento", "tiempo_cierre_vapor_checkpoint")` (agregados en Task 1); `p_saturacion_kpa` (ya importado en el archivo).
- Produces: atributos de instancia `self._t_pulso_vapor_chk` (float timestamp o `None`) y `self._vapor_chk_abierto` (bool), consumidos únicamente dentro de este mismo archivo.

- [ ] **Step 1: Agregar el estado nuevo en `reset()`**

En `src/autoclave/state_machine/cycle_phases/calentamiento.py`, reemplazar:

```python
    def reset(self):
        self._inicializado = False
        self._t_inicio = None
        self._t_inicio_fase = None
        self._timer_timeout_fin = None
        self._checkpoints = None
        self._en_checkpoint = False
        self.estado.fase_en_sostenimiento = False
```

por:

```python
    def reset(self):
        self._inicializado = False
        self._t_inicio = None
        self._t_inicio_fase = None
        self._timer_timeout_fin = None
        self._checkpoints = None
        self._en_checkpoint = False
        self._t_pulso_vapor_chk = None
        self._vapor_chk_abierto = False
        self.estado.fase_en_sostenimiento = False
```

- [ ] **Step 2: Reemplazar el bloque de lógica de checkpoint**

Reemplazar:

```python
        # ── 4. Lógica de checkpoint — bloquea la finalización mientras esté
        #      pendiente, aunque temp ya haya alcanzado t_obj ─────────────
        if self._en_checkpoint:
            if pres is None:
                return FaseResult.EN_CURSO
            if self._verificar_vapor_saturado(temp, pres, tolerancia):
                logger.info("Calentamiento: checkpoint %.1f°C liberado", self._checkpoints[0])
                self._checkpoints.pop(0)
                self._en_checkpoint = False
                self.estado.fase_en_sostenimiento = False
            else:
                p_sat = p_saturacion_kpa(temp)
                if pres > p_sat + tolerancia:
                    self.set_do.vapor_camara_off()
                else:
                    self.set_do.vapor_camara_on()
            return FaseResult.EN_CURSO
```

por:

```python
        # ── 4. Lógica de checkpoint — bloquea la finalización mientras esté
        #      pendiente, aunque temp ya haya alcanzado t_obj ─────────────
        if self._en_checkpoint:
            if pres is None:
                return FaseResult.EN_CURSO
            if self._verificar_vapor_saturado(temp, pres, tolerancia):
                logger.info("Calentamiento: checkpoint %.1f°C liberado", self._checkpoints[0])
                self._checkpoints.pop(0)
                self._en_checkpoint = False
                self.estado.fase_en_sostenimiento = False
                self._t_pulso_vapor_chk = None
                self._vapor_chk_abierto = False
            else:
                p_sat = p_saturacion_kpa(temp)
                margen = self.cycle.get_param("calentamiento", "margen_techo_calentamiento")
                techo  = self._checkpoints[0] + margen
                if pres > p_sat + tolerancia:
                    self.set_do.vapor_camara_off()
                    self._t_pulso_vapor_chk = None
                elif temp < techo:
                    t_on  = self.cycle.get_param("calentamiento", "tiempo_apertura_vapor_checkpoint")
                    t_off = self.cycle.get_param("calentamiento", "tiempo_cierre_vapor_checkpoint")
                    now = time.time()
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
                else:
                    self.set_do.vapor_camara_off()
                    self._t_pulso_vapor_chk = None
            return FaseResult.EN_CURSO
```

- [ ] **Step 3: Correr los tests de pulso/techo y confirmar que ahora pasan**

Run: `pytest tests/test_calentamiento_fase.py -v -k "pulso or techo"`
Expected: los 4 tests de Task 2 pasan (`4 passed`).

- [ ] **Step 4: Correr el archivo completo y detectar la regresión esperada**

Run: `pytest tests/test_calentamiento_fase.py -v`
Expected: `test_checkpoint_pendiente_bloquea_completacion` falla en la línea
`set_do.vapor_camara_off.assert_not_called()`. Esto es esperado: ese test salta la
temperatura a 135°C (muy por encima del techo del checkpoint 1, que es
107.2 + 2.0 = 109.2), y con el nuevo comportamiento eso ahora fuerza
`vapor_camara_off()` en vez de mantener la válvula abierta — el techo está haciendo
exactamente lo que se diseñó para hacer. El propósito original del test (un
checkpoint pendiente bloquea `COMPLETADO`) sigue intacto; solo la aserción sobre la
salida de vapor quedó desactualizada.

- [ ] **Step 5: Corregir la aserción desactualizada**

En `tests/test_calentamiento_fase.py`, reemplazar:

```python
def test_checkpoint_pendiente_bloquea_completacion():
    """Si temp >= t_obj pero un checkpoint sigue sin liberarse, no completa."""
    fase, estado, set_do = _make_fase(t_obj=134.0)
    fase.update()  # inicializar

    # Salta directo a t_obj sin pasar por los checkpoints con presión correcta
    # (aire residual / vapor no saturado: presión fija en 100.0 kPa)
    estado.sensores_temp["temp_camara"] = 135.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_checkpoint is True
    set_do.vapor_camara_off.assert_not_called()
    set_do.descompresion_lenta_off.assert_not_called()
```

por:

```python
def test_checkpoint_pendiente_bloquea_completacion():
    """Si temp >= t_obj pero un checkpoint sigue sin liberarse, no completa."""
    fase, estado, set_do = _make_fase(t_obj=134.0)
    fase.update()  # inicializar

    # Salta directo a t_obj sin pasar por los checkpoints con presión correcta
    # (aire residual / vapor no saturado: presión fija en 100.0 kPa). La temperatura
    # también supera el techo del checkpoint (107.2 + 2.0 = 109.2), así que el
    # mecanismo de pulsos fuerza la válvula a OFF en vez de pulsar — eso es correcto,
    # lo que este test verifica es que la fase NO completa mientras tanto.
    estado.sensores_temp["temp_camara"] = 135.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_checkpoint is True
    set_do.descompresion_lenta_off.assert_not_called()
```

- [ ] **Step 6: Correr el archivo completo de nuevo**

Run: `pytest tests/test_calentamiento_fase.py -v`
Expected: todos los tests pasan (`13 passed`).

- [ ] **Step 7: Correr la suite completa del proyecto**

Run: `pytest tests/ --ignore=tests/test_io_views.py -q`
Expected: `320 passed` o más (según cuántos tests existan al momento de ejecutar), 0 failed. `tests/test_io_views.py` se excluye porque ya falla antes de este cambio por un módulo pendiente de otra tarea (`autoclave.ui_pyside.views._io_base`), no relacionado.

- [ ] **Step 8: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_fase.py
git commit -m "feat: pulsos de vapor con techo de temperatura en checkpoint de calentamiento"
```

---

## Self-Review Notes

- **Cobertura del spec:** parámetros nuevos (Task 1), ancla del techo = `checkpoints[0] + margen` (Task 3 Step 2), alcance global del margen (un solo `get_param`, no por checkpoint — Task 3 Step 2), pulsos ON/OFF por tiempo (Task 3 Step 2), reset de estado al liberar checkpoint (Task 3 Step 2, rama `if`), condición de liberación sin cambios (Task 3 Step 2 no toca la rama `if self._verificar_vapor_saturado(...)`), los 5 casos de testing del spec están cubiertos (Task 2 cubre 1-4; Task 3 Step 4-6 cubre explícitamente el punto 5, incluyendo el ajuste de la aserción desactualizada que el propio spec anticipaba como posible fricción con el fix de orden anterior).
- **Placeholders:** ninguno — todo el código de cada step es el código final a aplicar.
- **Consistencia de tipos/nombres:** `_t_pulso_vapor_chk` y `_vapor_chk_abierto` se usan con el mismo nombre en Task 3 (implementación) y Task 2 (tests, ya escritos antes por TDD) — verificado.

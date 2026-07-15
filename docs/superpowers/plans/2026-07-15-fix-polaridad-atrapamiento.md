# Corrección de polaridad de señal de atrapamiento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corregir la interpretación de la señal de atrapamiento de puertas avanzadas: el sensor físico es NC (`0` = atrapada, `1` = normal), pero el código actual la lee al revés (`atrapamiento() == 1` como "atrapada"), por lo que el sistema nunca detecta un atrapamiento real.

**Architecture:** El fix vive enteramente en `src/autoclave/devices/puertas/advanced_door.py`. El método `atrapamiento()` pasa de devolver el bit crudo del sensor a devolver un booleano semántico ya invertido (`True` = atrapada). El único punto de consumo (`_from_cerrando`) se simplifica para usar ese booleano directamente. No se toca `status.py` (mapa crudo de DI, sin inversión, correcto que siga así) ni `simple_door.py` (no tiene este sensor).

**Tech Stack:** Python, pytest, unittest.mock.MagicMock.

## Global Constraints

- Único archivo de producción a modificar: `src/autoclave/devices/puertas/advanced_door.py`.
- No modificar `status.py` ni el mapa `map_di` — es un passthrough genérico de hardware, sin inversión de polaridad por canal.
- No modificar `simple_door.py` — no tiene sensor de atrapamiento.
- La suite completa de tests debe quedar en verde al finalizar (`pytest`).

---

### Task 1: Corregir polaridad de `atrapamiento()` y su único consumidor

**Files:**
- Modify: `src/autoclave/devices/puertas/advanced_door.py:199-203` (método `atrapamiento`)
- Modify: `src/autoclave/devices/puertas/advanced_door.py:478` (uso en `_from_cerrando`)
- Modify: `tests/test_advanced_door_safe_mode.py:14` (fixture `_make_door`)
- Test: `tests/test_advanced_door_safe_mode.py` (tests nuevos de polaridad)

**Interfaces:**
- Consumes: nada de tareas anteriores (tarea única).
- Produces: `AdvancedDoor.atrapamiento() -> bool` (antes devolvía el bit crudo `0`/`1`/`False`; ahora devuelve `True` cuando la puerta está atrapada, `False` en caso contrario). Ningún otro archivo del repo llama a este método (verificado por búsqueda), así que no hay otros consumidores que actualizar.

- [ ] **Step 1: Escribir los tests de polaridad (deben fallar con el código actual)**

Agregar al final de `tests/test_advanced_door_safe_mode.py` (después de la línea 124, `test_modo_seguro_usa_umbral_atmosferico_al_cerrar`):

```python

# ─── Polaridad de la señal de atrapamiento (NC: 0 físico = atrapada) ──────────

def test_atrapamiento_en_0_transiciona_a_atrapada():
    """Sensor NC: valor físico 0 significa puerta atrapada."""
    door, set_do, alarm_mgr, _ = _make_door(fallo_suministro=False)
    door.estado.sensores_di["atrapamiento_puerta_1"] = 0
    door._from_cerrando()
    door.estado.update_door_state.assert_called_with("Puerta 1", DoorState.ATRAPADA)


def test_atrapamiento_en_1_no_transiciona_a_atrapada():
    """Sensor NC: valor físico 1 significa operación normal, no atrapada."""
    door, set_do, alarm_mgr, _ = _make_door(fallo_suministro=False)
    door.estado.sensores_di["atrapamiento_puerta_1"] = 1
    door._from_cerrando()
    assert (
        ("Puerta 1", DoorState.ATRAPADA)
        not in [c.args for c in door.estado.update_door_state.call_args_list]
    )
```

- [ ] **Step 2: Ejecutar los tests nuevos y confirmar que fallan**

Run: `pytest tests/test_advanced_door_safe_mode.py -k atrapamiento -v`

Expected: `test_atrapamiento_en_0_transiciona_a_atrapada` FALLA (con el código actual, `atrapamiento() == 1` no se cumple cuando el valor es `0`, así que nunca llama a `update_door_state` con `ATRAPADA`). `test_atrapamiento_en_1_no_transiciona_a_atrapada` también FALLA (con valor `1`, el código actual SÍ dispara `ATRAPADA`, lo contrario de lo esperado).

- [ ] **Step 3: Corregir `atrapamiento()` en `advanced_door.py`**

Reemplazar (líneas 199-203):

```python
    def atrapamiento(self, ):
        if "atrapamiento" not in self.di:
            return False
        val = self.estado.sensores_di.get(self.di["atrapamiento"])
        return val if val is not None else False
```

por:

```python
    def atrapamiento(self, ):
        # Sensor NC: el equipo envía 0 cuando la puerta está atrapada y 1 en
        # operación normal, señal invertida respecto al resto de las DI.
        if "atrapamiento" not in self.di:
            return False
        val = self.estado.sensores_di.get(self.di["atrapamiento"])
        if val is None:
            return False
        return val == 0
```

- [ ] **Step 4: Corregir el sitio de uso en `_from_cerrando`**

Reemplazar (línea 478):

```python
        if self.atrapamiento() == 1:
```

por:

```python
        if self.atrapamiento():
```

- [ ] **Step 5: Ejecutar los tests nuevos y confirmar que pasan**

Run: `pytest tests/test_advanced_door_safe_mode.py -k atrapamiento -v`

Expected: PASS (ambos tests).

- [ ] **Step 6: Ejecutar toda la suite del archivo y ver qué rompe**

Run: `pytest tests/test_advanced_door_safe_mode.py -v`

Expected: FALLAN los tests de `_from_cerrando` que no son de atrapamiento (`test_modo_normal_no_genera_alarma_al_cerrar`, `test_modo_seguro_no_activa_bomba_al_cerrar`, `test_modo_seguro_genera_alarma_al_cerrar`, `test_modo_seguro_usa_umbral_atmosferico_al_cerrar`), porque el fixture `_make_door` fija `"atrapamiento_puerta_1": 0`, que con la polaridad corregida ahora significa "atrapada" y corta la ejecución de `_from_cerrando` antes de llegar a la lógica que esos tests verifican.

- [ ] **Step 7: Corregir el fixture para reflejar "no atrapada" por defecto**

En `tests/test_advanced_door_safe_mode.py`, reemplazar (línea 14):

```python
        "puerta_1_abierta": 0, "puerta_1_cerrada": 0, "atrapamiento_puerta_1": 0,
```

por:

```python
        "puerta_1_abierta": 0, "puerta_1_cerrada": 0, "atrapamiento_puerta_1": 1,
```

- [ ] **Step 8: Ejecutar toda la suite del archivo y confirmar que todo pasa**

Run: `pytest tests/test_advanced_door_safe_mode.py -v`

Expected: PASS (todos los tests, incluidos los dos nuevos de polaridad).

- [ ] **Step 9: Ejecutar la suite completa del proyecto**

Run: `pytest`

Expected: PASS (sin regresiones en otros archivos de test, en particular `tests/test_door_from_profile.py` que también referencia `atrapamiento` pero solo verifica la presencia de la clave de configuración, no su polaridad).

- [ ] **Step 10: Commit**

```bash
git add src/autoclave/devices/puertas/advanced_door.py tests/test_advanced_door_safe_mode.py
git commit -m "fix: corregir polaridad invertida de señal de atrapamiento (NC: 0=atrapada)"
```

---

## Self-Review Notes

- **Spec coverage:** los 4 puntos de "Cambio" del spec (invertir `atrapamiento()`, simplificar el call site, ajustar fixture, test nuevo de polaridad) están cubiertos en los steps 3, 4, 7 y 1 respectivamente. "Fuera de alcance" (`status.py`, `simple_door.py`) no requiere tareas, solo se documenta en Global Constraints.
- **Placeholders:** ninguno — todo step de código trae el diff completo y los comandos traen su output esperado explícito.
- **Type consistency:** `atrapamiento()` se usa una sola vez en todo el repo (verificado por búsqueda), así que no hay riesgo de firmas desalineadas entre tareas.

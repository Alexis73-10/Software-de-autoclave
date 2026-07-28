# Margen mínimo de entrada a Esterilización — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Garantizar que la fase CALENTAMIENTO nunca se dé por completada (y por tanto nunca se entre a ESTERILIZACION) con temperatura o presión demasiado cerca del setpoint, imponiendo un piso de 0.2°C quemado en código que el JSON del ciclo no puede reducir.

**Architecture:** Se añade una constante de seguridad no configurable a `ParametrosGlobales`. La condición de completación de `CalentamientoFase.update()` combina el margen del JSON con ese piso vía `max()`, y añade una condición de presión derivada de la curva de saturación (`p_saturacion_kpa`) en el mismo punto de temperatura umbral, sin introducir un segundo número de margen en kPa.

**Tech Stack:** Python 3.14, pytest, `unittest.mock.MagicMock` para los fixtures de fase.

## Global Constraints

- El valor del piso es `0.2` °C, exactamente. No configurable vía JSON de ciclo.
- El piso nunca reduce un margen mayor configurado en el JSON — solo eleva un margen menor.
- El piso de presión se deriva de `p_saturacion_kpa(t_completar)`, no de un segundo número en kPa mantenido a mano.
- No se modifica `esterilizacion.py` ni ningún archivo JSON de ciclo.

---

### Task 1: Piso mínimo sobre el margen de temperatura

**Files:**
- Modify: `src/autoclave/state_machine/machine/parametros_globales.py`
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py:1-14` (import), `:42` (cálculo de `margen_ester`)
- Test: `tests/test_calentamiento_fase.py`

**Interfaces:**
- Produces: `parametros_globales.MARGEN_MINIMO_ENTRADA_ESTERILIZACION` (float, °C) — constante de solo lectura consumida por `CalentamientoFase.update()`.
- Consumes: nada nuevo de otros módulos; usa el `parametros_globales` singleton ya existente (patrón usado en `state_machine/states/preparacion.py`).

- [ ] **Step 1: Escribir los tests que fallan**

Añadir al final de `tests/test_calentamiento_fase.py`:

```python
def test_margen_minimo_hardcoded_ignora_json_menor():
    """Aunque el JSON pida un margen de entrada menor al piso (0.2°C), se
    exige al menos el piso antes de completar."""
    from autoclave.core.runtime.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(t_obj=134.0, margen_entrada_esterilizacion=0.05)
    fase.update()  # inicializar

    estado.sensores_temp["temp_camara"] = 129.98  # 97% — libera el checkpoint
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(129.98)
    fase.update()

    estado.sensores_temp["temp_camara"] = 134.05  # t_obj + 0.05 (json), no alcanza el piso
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.05)
    result = fase.update()
    assert result == FaseResult.EN_CURSO

    estado.sensores_temp["temp_camara"] = 134.2  # t_obj + 0.2 (piso)
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.2)
    result = fase.update()
    assert result == FaseResult.COMPLETADO


def test_margen_json_mayor_al_piso_se_respeta():
    """Si el JSON pide un margen mayor al piso, se respeta el mayor (el piso
    no lo recorta)."""
    from autoclave.core.runtime.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(t_obj=134.0, margen_entrada_esterilizacion=1.0)
    fase.update()  # inicializar

    estado.sensores_temp["temp_camara"] = 129.98  # 97% — libera el checkpoint
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(129.98)
    fase.update()

    estado.sensores_temp["temp_camara"] = 134.5  # t_obj + 0.5, por debajo del margen JSON (1.0)
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.5)
    result = fase.update()
    assert result == FaseResult.EN_CURSO

    estado.sensores_temp["temp_camara"] = 135.0  # t_obj + 1.0 (margen JSON)
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(135.0)
    result = fase.update()
    assert result == FaseResult.COMPLETADO
```

- [ ] **Step 2: Ejecutar los tests para confirmar que fallan**

Run: `python -m pytest tests/test_calentamiento_fase.py -k margen_minimo_hardcoded or margen_json_mayor -v`
Expected: FAIL — `test_margen_minimo_hardcoded_ignora_json_menor` completa en 134.05 en vez de esperar a 134.2 (el JSON de 0.05 no tiene piso todavía).

- [ ] **Step 3: Añadir la constante en `parametros_globales.py`**

Reemplazar el contenido completo de `src/autoclave/state_machine/machine/parametros_globales.py`:

```python


class ParametrosGlobales:
    PRESION_ATMOSFERICA = 74.5  # Presion atmosferica en kPa
    RANGO_PRES_ATMOSFERICA = 10.0  # Rango de tolerancia en kPa
    TEMP_DRENAJE = 90.0  # Temperatura maxima de drenaje en °C
    MARGEN_MINIMO_ENTRADA_ESTERILIZACION = 0.2  # °C — piso no configurable

parametros_globales = ParametrosGlobales()
```

- [ ] **Step 4: Aplicar el piso en `calentamiento.py`**

En `src/autoclave/state_machine/cycle_phases/calentamiento.py`, añadir el import junto a los existentes (tras la línea `from .base_fase import BaseFase, FaseResult`):

```python
from autoclave.state_machine.machine.parametros_globales import parametros_globales
```

Y reemplazar la línea:

```python
        margen_ester = self.cycle.get_param("calentamiento", "margen_entrada_esterilizacion") or 0.5
```

por:

```python
        margen_ester = max(
            self.cycle.get_param("calentamiento", "margen_entrada_esterilizacion") or 0.5,
            parametros_globales.MARGEN_MINIMO_ENTRADA_ESTERILIZACION,
        )
```

- [ ] **Step 5: Ejecutar los tests para confirmar que pasan**

Run: `python -m pytest tests/test_calentamiento_fase.py tests/test_calentamiento_caps.py -v`
Expected: PASS — todos los tests, incluidos los dos nuevos. (Los tests preexistentes no se ven afectados porque ninguno usa un `margen_entrada_esterilizacion` por debajo de 0.2°C.)

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/machine/parametros_globales.py src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_fase.py
git commit -m "feat: piso minimo de 0.2C sobre el margen de entrada a esterilizacion"
```

---

### Task 2: Piso de presión derivado de la curva de saturación

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py` (sección 5 — completación)
- Test: `tests/test_calentamiento_fase.py`
- Test: `tests/test_calentamiento_caps.py`

**Interfaces:**
- Consumes: `p_saturacion_kpa(t: float) -> float` de `autoclave.core.runtime.steam` (ya importado en `calentamiento.py`); `margen_ester` y `t_completar` producidos en la sección 5 (Task 1).
- Produces: nada consumido por otras fases — el cambio es interno a la condición de completación de `CalentamientoFase`.

- [ ] **Step 1: Escribir los tests que fallan**

Añadir al final de `tests/test_calentamiento_fase.py`:

```python
def test_no_completa_si_presion_insuficiente():
    """Temperatura alcanza el margen pero la presión se queda por debajo de
    P_sat(t_completar) → no completa (piso de presión)."""
    from autoclave.core.runtime.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(t_obj=134.0, margen_entrada_esterilizacion=0.5)
    fase.update()  # inicializar

    estado.sensores_temp["temp_camara"] = 129.98  # 97% — libera el checkpoint
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(129.98)
    fase.update()

    estado.sensores_temp["temp_camara"] = 135.0  # >= t_obj + margen (134.5)
    # la presión se queda en el nivel del checkpoint, por debajo de P_sat(134.5)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.descompresion_lenta_off.assert_not_called()


def test_pres_none_no_completa():
    """Si no hay lectura de presión, la fase no completa (y no lanza excepción)."""
    from autoclave.core.runtime.steam import p_saturacion_kpa
    fase, estado, set_do = _make_fase(t_obj=134.0, margen_entrada_esterilizacion=0.5)
    fase.update()  # inicializar

    estado.sensores_temp["temp_camara"] = 129.98
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(129.98)
    fase.update()

    estado.sensores_temp["temp_camara"] = 135.0
    estado.sensores_pres.pop("pres_camara", None)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
```

- [ ] **Step 2: Ejecutar los tests para confirmar que fallan**

Run: `python -m pytest tests/test_calentamiento_fase.py -k presion_insuficiente or pres_none -v`
Expected: FAIL — `test_no_completa_si_presion_insuficiente` obtiene `COMPLETADO` porque hoy la completación no chequea presión.

- [ ] **Step 3: Añadir el piso de presión en `calentamiento.py`**

Reemplazar la sección 5 completa (`# ── 5. Verificar completación ...` hasta el `else:` final de esa sección) por:

```python
        # ── 5. Verificar completación ───────────────────────────────────
        # Se exige temp >= t_obj + margen_ester (no justo t_obj): la lectura
        # real fluctúa un poco al llegar al objetivo, así que completar justo
        # en t_obj puede caer por debajo de temperatura_esterilizacion en el
        # primer tick de ESTERILIZACION (que no tiene tolerancia) y disparar
        # un FALLO espurio. El margen da un colchón contra esa fluctuación.
        # margen_ester nunca baja de MARGEN_MINIMO_ENTRADA_ESTERILIZACION
        # (Task 1), y la presión exigida se deriva de la misma curva de
        # saturación en vez de mantener un segundo número de margen en kPa.
        t_completar = t_obj + margen_ester
        p_completar = p_saturacion_kpa(t_completar)
        if pres is None:
            return FaseResult.EN_CURSO
        if self.cap.has_liquid_sensor:
            temp2 = self._temp_camara_2()
            if temp2 is None:
                return FaseResult.EN_CURSO
            if temp >= t_completar and temp2 >= t_completar and pres >= p_completar:
                logger.info(
                    "Calentamiento: COMPLETADO — camara=%.1f°C liquido=%.1f°C pres=%.1fkPa",
                    temp, temp2, pres,
                )
                self._apagar_salidas()
                return FaseResult.COMPLETADO
        else:
            if temp >= t_completar and pres >= p_completar:
                logger.info(
                    "Calentamiento: COMPLETADO — %.1f°C / %.1fkPa alcanzados",
                    temp, pres,
                )
                self._apagar_salidas()
                return FaseResult.COMPLETADO
```

- [ ] **Step 4: Actualizar los tests preexistentes que ahora requieren presión suficiente**

En `tests/test_calentamiento_fase.py`:

En `test_completado_cuando_alcanza_temperatura`, entre la línea `estado.sensores_temp["temp_camara"] = 135.0` y `result = fase.update()`, insertar:

```python
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(135.0)
```

En `test_no_completa_justo_en_t_obj_espera_margen_entrada_esterilizacion`, entre `estado.sensores_temp["temp_camara"] = 134.5  # == t_obj + margen` y `result = fase.update()` (segunda ocurrencia), insertar:

```python
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(134.5)
```

En `test_salidas_apagadas_al_completar`, entre `estado.sensores_temp["temp_camara"] = 135.0  # >= t_obj + margen_entrada_esterilizacion (134.5)` y `fase.update()`, insertar:

```python
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(135.0)
```

En `tests/test_calentamiento_caps.py`:

En `test_sin_sensor_liquido_completa_con_un_sensor`, tras `estado.sensores_temp["temp_camara"] = 135.0`, insertar (y añadir el import al inicio de la función):

```python
def test_sin_sensor_liquido_completa_con_un_sensor():
    from autoclave.core.runtime.steam import p_saturacion_kpa
    fase, estado, _ = _make_fase(has_liquid_sensor=False)
    fase.update()  # inicializar
    _liberar_checkpoints(fase, estado)
    estado.sensores_temp["temp_camara"] = 135.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(135.0)
    result = fase.update()
    assert result == FaseResult.COMPLETADO
```

En `test_con_sensor_liquido_completa_cuando_ambos_llegan`:

```python
def test_con_sensor_liquido_completa_cuando_ambos_llegan():
    from autoclave.core.runtime.steam import p_saturacion_kpa
    fase, estado, _ = _make_fase(has_liquid_sensor=True)
    fase.update()  # inicializar
    _liberar_checkpoints(fase, estado)
    estado.sensores_temp["temp_camara"]   = 135.0
    estado.sensores_temp["temp_2_camara"] = 135.0
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(135.0)
    result = fase.update()
    assert result == FaseResult.COMPLETADO
```

- [ ] **Step 5: Ejecutar toda la suite de calentamiento para confirmar que pasa**

Run: `python -m pytest tests/test_calentamiento_fase.py tests/test_calentamiento_caps.py -v`
Expected: PASS — todos los tests, incluidos los 2 nuevos de este task y los 2 de Task 1.

- [ ] **Step 6: Ejecutar la suite completa para descartar regresiones en otras fases**

Run: `python -m pytest tests/ -v`
Expected: PASS — ningún otro test importa ni depende de `CalentamientoFase.update()` fuera de los dos archivos ya tocados (confirmar en la salida).

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_fase.py tests/test_calentamiento_caps.py
git commit -m "feat: piso de presion en la entrada a esterilizacion via curva de saturacion"
```

# Remover FALLO por tasa en CALENTAMIENTO — solo control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar por completo el camino de FALLO por pendiente excesiva (`tasa_calentamiento`/`tasa_presion`) en `CalentamientoFase` — esos parámetros quedan exclusivamente como control (bang-bang en `APROXIMACION`, sin cambios ahí).

**Architecture:** Un solo archivo de producción se modifica (`src/autoclave/state_machine/cycle_phases/calentamiento.py`): el paso 3 de `update()` pierde el bloque de debounce+FALLO, conserva solo el cálculo de `tasa_t`/`tasa_p`. `reset()` pierde los contadores de exceso. La constante `_DEBOUNCE_LECTURAS` se elimina (queda sin uso). El paso 5 (control bang-bang) no se toca.

**Tech Stack:** Python, pytest, `unittest.mock.MagicMock` (mismo patrón de test ya usado en `tests/test_calentamiento_fase.py`).

## Global Constraints

- Ningún parámetro nuevo ni eliminado de los perfiles JSON.
- Sin umbral de FALLO alternativo o de respaldo para pendiente excesiva — decisión explícita, no se agrega ninguno.
- El paso 5 (control bang-bang: ON salvo que `tasa_t`/`tasa_p` superen `tasa_calentamiento`/`tasa_presion`, solo dirección de subida en temperatura, sin tiempo mínimo de apagado) no cambia.
- `PWM_ACTIVO`, `ESTABLE_PREESTERILIZACION`, el timeout global (`timeout_calentamiento`) y el resto de la fase no cambian.
- Rama de trabajo: `tasa-control-calentamiento` (PR #28, aún sin mergear) — este trabajo se agrega como commits nuevos a esa misma rama, no una rama/PR separada.
- Spec completa: `docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md`.

---

### Task 1: Eliminar el chequeo de FALLO por pendiente

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py:1-23` (comentario de cabecera), `:32` (constante `_DEBOUNCE_LECTURAS`), `:39-50` (`reset()`), `:146-179` (paso 3)
- Test: `tests/test_calentamiento_fase.py`

**Interfaces:**
- Consumes: `self.cycle.get_param("calentamiento", "tasa_calentamiento")` y `"tasa_presion"` (sin cambios de firma).
- Produces: ninguna interfaz nueva. Se eliminan los atributos de instancia `_contador_exceso_temp`/`_contador_exceso_pres` (dejan de existir tras `reset()`) y la constante de módulo `_DEBOUNCE_LECTURAS`.

- [ ] **Step 1: Eliminar los tests que validaban el camino de FALLO por pendiente (ya no existe)**

En `tests/test_calentamiento_fase.py`, eliminar por completo estas 6 funciones (junto con el comentario de sección `# ── FALLO: debounce de pendiente (3 lecturas consecutivas) ──` que las precede):

- `test_tasa_calentamiento_no_falla_con_1_o_2_lecturas_excesivas`
- `test_tasa_calentamiento_falla_al_tercer_exceso_consecutivo`
- `test_tasa_calentamiento_bidireccional_detecta_caida_abrupta`
- `test_tasa_presion_falla_al_tercer_exceso_consecutivo`
- `test_tasa_deshabilitada_con_cero_no_falla_por_salto_grande`
- `test_aproximacion_bangbang_apaga_valvula_en_cada_tick_antes_del_debounce_de_fallo` (al final del archivo, sección `# ── Control por tasa en APROXIMACION (bang-bang) ──`)

En `test_aproximacion_bangbang_no_apaga_por_caida_abrupta_de_temperatura`, el docstring termina con `"que sí es bidireccional (ver test_tasa_calentamiento_bidireccional_detecta_caida_abrupta)."` — esa referencia queda rota porque el test referenciado se elimina. Reemplazar el docstring completo de esa función por:

```python
def test_aproximacion_bangbang_no_apaga_por_caida_abrupta_de_temperatura():
    """El control solo limita la dirección de subida (sin abs()) porque la
    válvula no puede enfriar la cámara."""
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0, tasa_presion=200.0)
    fase.update()

    fase._temp_anterior = 100.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 50.0  # caída de 50°C/min
    estado.sensores_pres["pres_camara"] = 110.0  # dentro de rango
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()
```

- [ ] **Step 2: Actualizar el docstring de `_make_fase` (razón de que tasa_* quede en 0 por defecto)**

Reemplazar el docstring actual de `_make_fase` (líneas 14-18):

```python
    """tasa_calentamiento/tasa_presion quedan en 0 (deshabilitadas, ver guard
    '> 0' en calentamiento.py) por defecto: los tests que no ejercitan el
    debounce de pendiente cambian temperatura/presión entre ticks sin
    control de tiempo real, lo que produciría una tasa artificialmente alta
    y un FALLO espurio si el chequeo estuviera activo."""
```

por:

```python
    """tasa_calentamiento/tasa_presion quedan en 0 (deshabilitadas, ver guard
    '> 0' en calentamiento.py) por defecto: los tests que no ejercitan el
    control por tasa cambian temperatura/presión entre ticks sin control de
    tiempo real, lo que produciría una tasa artificialmente alta y forzaría
    vapor_camara a OFF de forma espuria si el control estuviera activo."""
```

- [ ] **Step 3: Agregar el test que prueba que la remoción del camino de FALLO es completa**

Agregar al final de `tests/test_calentamiento_fase.py` (después de `test_aproximacion_bangbang_no_apaga_por_caida_abrupta_de_temperatura`, que ahora queda como la última función tras el Step 1):

```python
def test_tasa_excedida_muchos_ticks_consecutivos_nunca_produce_fallo():
    """tasa_calentamiento/tasa_presion son ahora puramente de control — ya
    no existe ningún camino de FALLO por pendiente, sin importar cuántos
    ticks consecutivos excedan el límite (ver spec de remoción de FALLO,
    docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md)."""
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0, tasa_presion=50.0)
    fase.update()  # inicializar

    result = FaseResult.EN_CURSO
    for _ in range(10):
        fase._temp_anterior = 20.0
        fase._pres_anterior = 100.0
        fase._t_tick_anterior = time.time() - 60
        estado.sensores_temp["temp_camara"] = 100.0  # 80°C/min, muy por encima de 10
        estado.sensores_pres["pres_camara"] = 500.0  # 400 kPa/min, muy por encima de 50
        set_do.reset_mock()
        result = fase.update()
        assert result == FaseResult.EN_CURSO
        set_do.vapor_camara_off.assert_called()
        set_do.vapor_camara_on.assert_not_called()

    assert result != FaseResult.FALLO
```

- [ ] **Step 4: Correr los tests y verificar el estado esperado (algunos ya no existen, el nuevo aún no tiene código que lo respalde)**

Run (con `PYTHONPATH="$(pwd)/src"` desde la raíz del worktree — este repo tiene una instalación editable de pip que apunta a otro checkout, así que sin esto `pytest` ejecutaría silenciosamente el código de otro directorio): `PYTHONPATH="$(pwd)/src" python -m pytest tests/test_calentamiento_fase.py -v`
Expected: el nuevo test `test_tasa_excedida_muchos_ticks_consecutivos_nunca_produce_fallo` FALLA — con `tasa_calentamiento`/`tasa_presion` activos y el código de producción todavía sin cambiar, al tercer tick el chequeo de debounce actual dispara `FaseResult.FALLO`, y la aserción `assert result == FaseResult.EN_CURSO` no se cumple. El resto de los tests restantes debe seguir pasando (no se tocó producción todavía).

- [ ] **Step 5: Actualizar el comentario de cabecera del archivo**

En `src/autoclave/state_machine/cycle_phases/calentamiento.py`, reemplazar las líneas 19-23 actuales (el último párrafo del comentario de cabecera):

```python
# escape_lento y escape_rapido corren con temporizadores de dos estados
# independientes en paralelo durante toda la fase (no sincronizados con los
# tramos anteriores). tasa_calentamiento/tasa_presion también vigilan la
# pendiente con debounce de 3 lecturas y pueden producir FALLO desde
# cualquier tramo (chequeo sin cambios, independiente del control anterior).
```

por:

```python
# escape_lento y escape_rapido corren con temporizadores de dos estados
# independientes en paralelo durante toda la fase (no sincronizados con los
# tramos anteriores). tasa_calentamiento/tasa_presion son puramente de
# control (bang-bang en APROXIMACION) — no producen FALLO; si vapor_camara
# no responde al comando OFF, no hay aborto automático por esta vía (riesgo
# aceptado, ver docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md).
```

- [ ] **Step 6: Eliminar la constante `_DEBOUNCE_LECTURAS`**

En `calentamiento.py`, eliminar la línea:

```python
_DEBOUNCE_LECTURAS = 3
```

(y la línea en blanco sobrante que quede, si aplica, para mantener el mismo espaciado que el resto del archivo — una sola línea en blanco entre el `logger = ...` y la definición de la clase).

- [ ] **Step 7: Eliminar los contadores de exceso en `reset()`**

Reemplazar el bloque actual dentro de `reset()`:

```python
        # Debounce de pendiente (tasa_calentamiento / tasa_presion)
        self._temp_anterior = None
        self._pres_anterior = None
        self._t_tick_anterior = None
        self._contador_exceso_temp = 0
        self._contador_exceso_pres = 0
```

por:

```python
        # Pendiente instantánea (tasa_calentamiento / tasa_presion) —
        # alimenta el control de vapor_camara en APROXIMACION, paso 5
        self._temp_anterior = None
        self._pres_anterior = None
        self._t_tick_anterior = None
```

- [ ] **Step 8: Eliminar el bloque de FALLO del paso 3, dejando solo el cálculo de pendiente**

Reemplazar el bloque completo (busca el comentario `# ── 3. Debounce de pendiente`):

```python
        # ── 3. Debounce de pendiente ──────────────────────────────────────
        # Nota: la rampa de temperatura se vigila en valor absoluto (subida O
        # caída abrupta son ambas anómalas, ver FMEA sección 8); la de presión
        # solo en sentido de subida (sobrepresión por PWM mal calibrado).
        # tasa_t/tasa_p también alimentan el control de vapor_camara en
        # APROXIMACION (paso 5) — mismo cálculo, capturado una sola vez aquí.
        tasa_t = None
        tasa_p = None
        if self._t_tick_anterior is not None:
            dt_min = (now - self._t_tick_anterior) / 60
            if dt_min > 0:
                tasa_t = (temp - self._temp_anterior) / dt_min
                if tasa_t_max > 0 and abs(tasa_t) > tasa_t_max:
                    self._contador_exceso_temp += 1
                else:
                    self._contador_exceso_temp = 0
                if self._contador_exceso_temp >= _DEBOUNCE_LECTURAS:
                    return self._fallo(
                        f"Pendiente de temperatura excesiva: {tasa_t:.1f}°C/min (máx {tasa_t_max:.1f}°C/min)"
                    )

                tasa_p = (pres - self._pres_anterior) / dt_min
                if tasa_p_max > 0 and tasa_p > tasa_p_max:
                    self._contador_exceso_pres += 1
                else:
                    self._contador_exceso_pres = 0
                if self._contador_exceso_pres >= _DEBOUNCE_LECTURAS:
                    return self._fallo(
                        f"Pendiente de presión excesiva: {tasa_p:.1f} kPa/min (máx {tasa_p_max:.1f} kPa/min)"
                    )

        self._temp_anterior = temp
        self._pres_anterior = pres
        self._t_tick_anterior = now
```

por:

```python
        # ── 3. Cálculo de pendiente ──────────────────────────────────────
        # tasa_t/tasa_p alimentan el control de vapor_camara en APROXIMACION
        # (paso 5). No disparan FALLO — riesgo aceptado si vapor_camara no
        # responde al comando OFF, ver spec de remoción de FALLO.
        tasa_t = None
        tasa_p = None
        if self._t_tick_anterior is not None:
            dt_min = (now - self._t_tick_anterior) / 60
            if dt_min > 0:
                tasa_t = (temp - self._temp_anterior) / dt_min
                tasa_p = (pres - self._pres_anterior) / dt_min

        self._temp_anterior = temp
        self._pres_anterior = pres
        self._t_tick_anterior = now
```

Nota: `tasa_t_max`/`tasa_p_max` (leídos al inicio de `update()`) siguen usándose sin cambios en el paso 5 — no se tocan.

- [ ] **Step 9: Correr los tests y verificar que todos pasan**

Run: `PYTHONPATH="$(pwd)/src" python -m pytest tests/test_calentamiento_fase.py -v`
Expected: PASS — todos los tests, incluyendo `test_tasa_excedida_muchos_ticks_consecutivos_nunca_produce_fallo` (ahora el código de producción ya no dispara FALLO) y los 8 tests de bang-bang + `test_pwm_activo_ignora_tasa_calentamiento_excedida` (sin cambios de comportamiento, regresión).

- [ ] **Step 10: Correr la suite completa del proyecto**

Run: `PYTHONPATH="$(pwd)/src" python -m pytest tests/ --ignore=tests/test_io_views.py -q`
Expected: PASS — sin regresiones en otras fases. (`tests/test_io_views.py` está roto desde antes por una ruta de módulo obsoleta, sin relación con este cambio — se excluye igual que en el ciclo anterior.)

- [ ] **Step 11: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_fase.py
git commit -m "feat: remover FALLO por tasa en CALENTAMIENTO — tasa_calentamiento/tasa_presion solo control

Se elimina el camino de FALLO por pendiente excesiva (debounce de 3
lecturas). tasa_calentamiento/tasa_presion quedan exclusivamente como
techo de control (bang-bang en APROXIMACION, sin cambios ahi). Riesgo
aceptado si vapor_camara no responde al comando OFF (ver spec).

Ver docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md"
```

---

### Task 2: Actualizar documentación de la fase

**Files:**
- Modify: `docs/mis_plans/planeacion_fase_calentamiento.md` (secciones 2, 3, 6, 8)

**Interfaces:**
- Consumes: ninguna — cambio de documentación, no de código.
- Produces: ninguna.

- [ ] **Step 1: Actualizar el rol de `tasa_calentamiento`/`tasa_presion` en la tabla de parámetros (sección 2)**

Reemplazar las filas 6 y 7 de la tabla:

```markdown
| 6 | Tasa de calentamiento | `tasa_calentamiento` | °C/min | 50 | 0 | 100 | Setpoint de control (techo de subida en APROXIMACION, bang-bang de `vapor_camara`) + umbral de falla (debounce 3 lecturas) |
| 7 | Tasa de presion | `tasa_presion` | kPa/min | 100 | 0 | 300 | Setpoint de control (techo de subida en APROXIMACION, bang-bang de `vapor_camara`) + umbral de falla (debounce 3 lecturas) |
```

por:

```markdown
| 6 | Tasa de calentamiento | `tasa_calentamiento` | °C/min | 50 | 0 | 100 | Setpoint de control — techo de subida en APROXIMACION, bang-bang de `vapor_camara`. No produce FALLO. |
| 7 | Tasa de presion | `tasa_presion` | kPa/min | 100 | 0 | 300 | Setpoint de control — techo de subida en APROXIMACION, bang-bang de `vapor_camara`. No produce FALLO. |
```

- [ ] **Step 2: Quitar la mención de FALLO en la sección 3 (máquina de estados)**

Reemplazar el párrafo:

```markdown
El chequeo de `tasa_calentamiento` / `tasa_presion` (con debounce de 3 lecturas) corre también en paralelo, activo durante toda la fase, y puede producir `FALLO` desde cualquier tramo.
```

por:

```markdown
`tasa_calentamiento` / `tasa_presion` ya no producen `FALLO` — son exclusivamente parámetros de control, consumidos por el bang-bang de `APROXIMACION` (ver nota de actualización debajo y sección 4.1).
```

- [ ] **Step 3: Eliminar la sección 6 completa ("Condiciones de FALLO")**

Eliminar por completo el bloque desde el encabezado `## 6. Condiciones de FALLO` hasta (sin incluir) el separador `---` que sigue al párrafo `Al entrar en FALLO, se apagan las tres salidas...`. Es decir, eliminar:

```markdown
## 6. Condiciones de FALLO

| Condición | Umbral | Debounce | Acción |
|---|---|---|---|
| Timeout global | `time.time() > t_inicio_fase + timeout_calentamiento*60` | Ninguno (instantáneo) | `FALLO`, apagar `vapor_camara` |
| Exceso pendiente temperatura | `ΔT/Δtick > tasa_calentamiento` (por minuto) | 3 lecturas consecutivas | `FALLO`, apagar `vapor_camara` |
| Exceso pendiente presión | `ΔP/Δtick > tasa_presion` (por minuto) | 3 lecturas consecutivas | `FALLO`, apagar `vapor_camara` |
| Sensores/puertas | Delegado a `alarm_manager` | — | Fuera del alcance de esta fase (corre en paralelo durante todo el ciclo) |

**Justificación del debounce de 3 lecturas:** un umbral de 1 sola lectura fuera de rango es demasiado sensible al ruido típico de sensores de presión/temperatura industrial y generaría falsos positivos en una fase agresiva (hasta 50 °C/min de tasa configurada). Con tick de control ~1s, 3 lecturas equivalen a ~3s de persistencia — da margen sin comprometer el tiempo de reacción ante un evento real de fuga o descontrol.

Al entrar en `FALLO`, se apagan las tres salidas (`vapor_camara`, `descompresion_lenta`, `descompresion_rapida`) — mismas salidas usadas en operación normal, sin I/O adicional que forzar.

---
```

y reemplazarlo por esta versión reducida (mantiene el timeout global y el `---` de cierre, quita solo lo que ya no aplica):

```markdown
## 6. Condiciones de FALLO

| Condición | Umbral | Debounce | Acción |
|---|---|---|---|
| Timeout global | `time.time() > t_inicio_fase + timeout_calentamiento*60` | Ninguno (instantáneo) | `FALLO`, apagar `vapor_camara` |
| Sensores/puertas | Delegado a `alarm_manager` | — | Fuera del alcance de esta fase (corre en paralelo durante todo el ciclo) |

`tasa_calentamiento`/`tasa_presion` **no** producen `FALLO` — son exclusivamente parámetros de control (sección 4.1). Riesgo aceptado explícito: si `vapor_camara` no responde al comando OFF, no hay aborto automático por esta vía (ver `docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md`).

Al entrar en `FALLO`, se apagan las tres salidas (`vapor_camara`, `descompresion_lenta`, `descompresion_rapida`) — mismas salidas usadas en operación normal, sin I/O adicional que forzar.

---
```

- [ ] **Step 4: Actualizar las filas de sobrepresión y rampa anómala en la FMEA (sección 8)**

Reemplazar la fila:

```markdown
| Todo tramo | Sobrepresión por PWM mal calibrado (`factor_calentamiento` muy bajo) en PWM_ACTIVO, o por control por tasa insuficiente en APROXIMACION | Presión sube más rápido de lo esperado | `intervalo_segmentos_calor`/`factor_calentamiento` mal configurados para el volumen de cámara (PWM_ACTIVO); `tasa_presion` configurado muy alto (APROXIMACION) | `tasa_presion` con debounce de 3 lecturas — activo en toda la fase; en APROXIMACION también alimenta el control bang-bang de `vapor_camara` (ver sección 4.1) | `FALLO` + apagado de salidas |
```

por:

```markdown
| Todo tramo | Sobrepresión por PWM mal calibrado (`factor_calentamiento` muy bajo) en PWM_ACTIVO, o por control por tasa insuficiente en APROXIMACION | Presión sube más rápido de lo esperado | `intervalo_segmentos_calor`/`factor_calentamiento` mal configurados para el volumen de cámara (PWM_ACTIVO); `tasa_presion` configurado muy alto (APROXIMACION) | Ninguna a nivel de esta fase (riesgo aceptado — ver sección 2 de `docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md`) | En APROXIMACION, `tasa_presion` gobierna `vapor_camara` en bang-bang (sección 4.1); en PWM_ACTIVO no hay mitigación automática |
```

Reemplazar la fila:

```markdown
| Todo tramo | Rampa de temperatura anómala (subida o caída abrupta) | Riesgo de choque térmico, indicativo de fuga o sensor dañado | Sensor de temperatura defectuoso, fuga de vapor directa a cámara | `tasa_calentamiento` con debounce de 3 lecturas — activo en toda la fase; en APROXIMACION también alimenta el control bang-bang de `vapor_camara` (solo dirección de subida, ver sección 4.1) | `FALLO` + apagado de salidas |
```

por:

```markdown
| Todo tramo | Rampa de temperatura anómala (subida o caída abrupta) | Riesgo de choque térmico, indicativo de fuga o sensor dañado | Sensor de temperatura defectuoso, fuga de vapor directa a cámara | Ninguna a nivel de esta fase (riesgo aceptado — ver sección 2 de `docs/superpowers/specs/2026-08-03-tasa-solo-control-calentamiento-design.md`) | En APROXIMACION, `tasa_calentamiento` gobierna `vapor_camara` en bang-bang, solo dirección de subida (sección 4.1); una caída abrupta no tiene mitigación en ningún tramo |
```

- [ ] **Step 5: Leer la sección 8 completa y confirmar que la tabla markdown sigue bien formada**

Después de los edits del Step 4, releer `## 8. Matriz de modos de falla (FMEA simplificado)` completa (todas las filas) y confirmar que cada fila sigue teniendo 6 columnas (7 símbolos `|`), sin texto duplicado ni huérfano.

- [ ] **Step 6: Commit**

```bash
git add docs/mis_plans/planeacion_fase_calentamiento.md
git commit -m "docs: reflejar remocion de FALLO por tasa en CALENTAMIENTO"
```

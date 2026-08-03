# Control por tasa en tramo APROXIMACION de CALENTAMIENTO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que `tasa_calentamiento` y `tasa_presion` gobiernen activamente `vapor_camara` durante el tramo `APROXIMACION` de `CalentamientoFase` (bang-bang por tick), en vez de ser solo un umbral de falla reactivo.

**Architecture:** Un solo archivo de producción se modifica (`src/autoclave/state_machine/cycle_phases/calentamiento.py`): el paso 3 de `update()` (debounce de pendiente) captura `tasa_t`/`tasa_p` en variables reutilizables en vez de calcularlas y descartarlas; el paso 5 (control de `vapor_camara`) usa esas variables para decidir ON/OFF cuando `not self._en_pwm`. `PWM_ACTIVO`/`ESTABLE_PREESTERILIZACION` y el chequeo de FALLO por debounce quedan sin cambios funcionales.

**Tech Stack:** Python, pytest, `unittest.mock.MagicMock` (mismo patrón de test ya usado en `tests/test_calentamiento_fase.py`).

## Global Constraints

- Sin parámetros nuevos en los perfiles JSON — se reutilizan `tasa_calentamiento`/`tasa_presion` tal como existen hoy (rangos 0–100 °C/min y 0–300 kPa/min).
- Sin margen entre techo de control y umbral de falla — mismo valor para ambos roles.
- Sin tiempo mínimo de apagado (dwell) — bang-bang directo por tick.
- El control de temperatura solo limita la dirección de subida (sin `abs()`); el de presión ya era unidireccional.
- `PWM_ACTIVO` y `ESTABLE_PREESTERILIZACION` no se modifican.
- Spec completa: `docs/superpowers/specs/2026-08-03-tasa-control-calentamiento-design.md`.

---

### Task 1: Control bang-bang de `vapor_camara` en APROXIMACION

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py:1-23` (comentario de cabecera), `:143-172` (paso 3 — captura de `tasa_t`/`tasa_p`), `:179-188` (paso 5 — control de `vapor_camara`)
- Test: `tests/test_calentamiento_fase.py` (agregar sección nueva al final del archivo)

**Interfaces:**
- Consumes: `self.cycle.get_param("calentamiento", "tasa_calentamiento")` y `"tasa_presion"` (ya existen, sin cambios de firma). `self._temp_anterior`, `self._pres_anterior`, `self._t_tick_anterior` (atributos de instancia ya existentes, sin cambios).
- Produces: ninguna interfaz nueva expuesta a otras fases — el cambio es interno a `update()`. No se agregan atributos de instancia nuevos (no se necesita persistir `tasa_t`/`tasa_p` entre ticks, son variables locales de cada llamada a `update()`).

- [ ] **Step 1: Escribir los tests que fallan (comportamiento nuevo del bang-bang en APROXIMACION)**

Agregar al final de `tests/test_calentamiento_fase.py`:

```python
# ── Control por tasa en APROXIMACION (bang-bang) ──────────────────────────

def test_aproximacion_bangbang_on_primer_tick_sin_pendiente_disponible():
    """Aunque tasa_calentamiento/tasa_presion estén habilitadas, el primer
    tick no tiene pendiente calculable (_t_tick_anterior aún None) — la
    válvula permanece ON por defecto."""
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0, tasa_presion=50.0)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_pwm is False
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_aproximacion_bangbang_on_si_tasas_dentro_del_limite():
    fase, estado, set_do = _make_fase(tasa_calentamiento=50.0, tasa_presion=200.0)
    fase.update()  # inicializar, primer tick sin pendiente

    fase._temp_anterior = 20.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60  # dt = 1 min
    estado.sensores_temp["temp_camara"] = 40.0  # 20°C/min <= 50
    estado.sensores_pres["pres_camara"] = 150.0  # 50 kPa/min <= 200
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_aproximacion_bangbang_off_si_tasa_temperatura_excede():
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0, tasa_presion=200.0)
    fase.update()

    fase._temp_anterior = 20.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 40.0  # 20°C/min > 10
    estado.sensores_pres["pres_camara"] = 150.0  # 50 kPa/min <= 200, dentro
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO  # 1 sola lectura, debounce de falla (3) no dispara aún
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_aproximacion_bangbang_off_si_tasa_presion_excede():
    fase, estado, set_do = _make_fase(tasa_calentamiento=100.0, tasa_presion=30.0)
    fase.update()

    fase._temp_anterior = 20.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 25.0  # 5°C/min <= 100, dentro
    estado.sensores_pres["pres_camara"] = 200.0  # 100 kPa/min > 30
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_aproximacion_bangbang_vuelve_a_on_sin_tiempo_minimo_de_apagado():
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0, tasa_presion=200.0)
    fase.update()

    fase._temp_anterior = 20.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 40.0  # excede -> OFF
    estado.sensores_pres["pres_camara"] = 150.0
    fase.update()
    assert fase._en_pwm is False

    fase._t_tick_anterior = time.time() - 60  # siguiente tick, dt = 1 min otra vez
    estado.sensores_temp["temp_camara"] = 41.0  # 1°C/min <= 10 ahora
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_aproximacion_bangbang_tasa_temperatura_deshabilitada():
    fase, estado, set_do = _make_fase(tasa_calentamiento=0.0, tasa_presion=30.0)
    fase.update()

    fase._temp_anterior = 20.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 200.0  # 180°C/min, sería enorme pero deshabilitado (0)
    estado.sensores_pres["pres_camara"] = 110.0  # 10 kPa/min <= 30, dentro
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_aproximacion_bangbang_tasa_presion_deshabilitada():
    fase, estado, set_do = _make_fase(tasa_calentamiento=100.0, tasa_presion=0.0)
    fase.update()

    fase._temp_anterior = 20.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 25.0  # 5°C/min <= 100, dentro
    estado.sensores_pres["pres_camara"] = 900.0  # 800 kPa/min, sería enorme pero deshabilitado (0)
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_aproximacion_bangbang_no_apaga_por_caida_abrupta_de_temperatura():
    """El control solo limita la dirección de subida (sin abs()) porque la
    válvula no puede enfriar la cámara — a diferencia del chequeo de falla,
    que sí es bidireccional (ver test_tasa_calentamiento_bidireccional_detecta_caida_abrupta)."""
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0, tasa_presion=200.0)
    fase.update()

    fase._temp_anterior = 100.0
    fase._pres_anterior = 100.0
    fase._t_tick_anterior = time.time() - 60
    estado.sensores_temp["temp_camara"] = 50.0  # caída de 50°C/min, excedería abs(10) del chequeo de falla
    estado.sensores_pres["pres_camara"] = 110.0  # dentro de rango
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_aproximacion_bangbang_apaga_valvula_en_cada_tick_antes_del_debounce_de_fallo():
    """El control por bang-bang ya actúa en los ticks que preceden al FALLO
    por debounce de 3 lecturas — no espera a que se dispare la falla."""
    fase, estado, set_do = _make_fase(tasa_calentamiento=10.0)
    fase.update()  # inicializar

    for _ in range(2):  # los primeros 2 excesos no fallan (debounce=3)
        fase._temp_anterior = 20.0
        fase._t_tick_anterior = time.time() - 60
        estado.sensores_temp["temp_camara"] = 40.0  # 20°C/min > 10
        set_do.reset_mock()
        result = fase.update()
        assert result == FaseResult.EN_CURSO
        set_do.vapor_camara_off.assert_called()
        set_do.vapor_camara_on.assert_not_called()
```

- [ ] **Step 2: Correr los tests nuevos y verificar que fallan**

Run: `python -m pytest tests/test_calentamiento_fase.py -k bangbang -v`
Expected: FAIL — los tests que esperan `vapor_camara_off` fallan con `AssertionError: Expected 'vapor_camara_off' to have been called` (el código actual llama `vapor_camara_on()` sin condición en `APROXIMACION`). El test del primer tick (`test_aproximacion_bangbang_on_primer_tick_sin_pendiente_disponible`) puede pasar ya (comportamiento no cambia ahí) — está bien, confirma que no rompe ese caso.

- [ ] **Step 3: Actualizar el comentario de cabecera del archivo**

En `src/autoclave/state_machine/cycle_phases/calentamiento.py`, reemplazar las líneas 1–20 actuales por:

```python
# state_machine/cycle_phases/calentamiento.py
#
# FASE 4 — CALENTAMIENTO
#
# Eleva la cámara desde la salida de PRE_VACIO hasta el punto de vapor
# saturado del setpoint de esterilización (temperatura_calentamiento +
# presion_add_calentamiento) y sostiene esa condición durante
# tiempo_estable_preesterilizacion segundos. Tres tramos internos, sin
# retroceso entre ellos:
#   APROXIMACION              vapor_camara en bang-bang por tick: ON salvo
#                              que la pendiente ya supere tasa_calentamiento/
#                              tasa_presion (0 = sin límite; solo limita subida)
#   PWM_ACTIVO                entra al alcanzar |P - P_sat(T)| <= rango_calentamiento;
#                              vapor_camara en PWM (factor_calentamiento / intervalo_segmentos_calor)
#   ESTABLE_PREESTERILIZACION sostenimiento; timer no se reinicia si la
#                              condición sale momentáneamente de rango (riesgo
#                              aceptado, a diferencia de EstabilizacionFase)
#
# escape_lento y escape_rapido corren con temporizadores de dos estados
# independientes en paralelo durante toda la fase (no sincronizados con los
# tramos anteriores). tasa_calentamiento/tasa_presion también vigilan la
# pendiente con debounce de 3 lecturas y pueden producir FALLO desde
# cualquier tramo (chequeo sin cambios, independiente del control anterior).
```

- [ ] **Step 4: Capturar `tasa_t`/`tasa_p` en el paso 3 (debounce de pendiente)**

En `calentamiento.py`, reemplazar el bloque actual (busca el comentario `# ── 3. Debounce de pendiente`):

```python
        # ── 3. Debounce de pendiente ──────────────────────────────────────
        # Nota: la rampa de temperatura se vigila en valor absoluto (subida O
        # caída abrupta son ambas anómalas, ver FMEA sección 8); la de presión
        # solo en sentido de subida (sobrepresión por PWM mal calibrado).
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

- [ ] **Step 5: Implementar el bang-bang en el paso 5 (control de `vapor_camara`)**

En `calentamiento.py`, reemplazar el bloque actual (busca el comentario `# ── 5. Control de vapor_camara`):

```python
        # ── 5. Control de vapor_camara ─────────────────────────────────────
        if not self._en_pwm:
            self.set_do.vapor_camara_on()
        else:
            t_off_pwm = intervalo * (factor_pct / 100.0)
            t_on_pwm  = intervalo - t_off_pwm
            self._tick_dos_estados(
                "_t_pulso_pwm", "_pwm_abierto", t_on_pwm, t_off_pwm,
                self.set_do.vapor_camara_on, self.set_do.vapor_camara_off, now,
            )
```

por:

```python
        # ── 5. Control de vapor_camara ─────────────────────────────────────
        if not self._en_pwm:
            # Bang-bang directo por tick: ON salvo que la pendiente ya
            # supere el techo de tasa_calentamiento/tasa_presion. Solo se
            # limita la dirección de subida (tasa_t sin abs()) porque la
            # válvula no puede enfriar la cámara. tasa_t/tasa_p en None
            # (sin dato de pendiente aún) o el umbral en 0 (deshabilitado)
            # no pueden forzar OFF.
            dentro_de_tasa = (
                (tasa_t is None or tasa_t_max <= 0 or tasa_t <= tasa_t_max)
                and (tasa_p is None or tasa_p_max <= 0 or tasa_p <= tasa_p_max)
            )
            if dentro_de_tasa:
                self.set_do.vapor_camara_on()
            else:
                self.set_do.vapor_camara_off()
        else:
            t_off_pwm = intervalo * (factor_pct / 100.0)
            t_on_pwm  = intervalo - t_off_pwm
            self._tick_dos_estados(
                "_t_pulso_pwm", "_pwm_abierto", t_on_pwm, t_off_pwm,
                self.set_do.vapor_camara_on, self.set_do.vapor_camara_off, now,
            )
```

- [ ] **Step 6: Correr toda la suite de la fase y verificar que pasa (incluye regresión)**

Run: `python -m pytest tests/test_calentamiento_fase.py -v`
Expected: PASS — todos los tests, incluyendo los 9 nuevos de bang-bang y los existentes de `PWM_ACTIVO`, debounce de falla, sostenimiento y finalización (regresión, sin cambios de comportamiento en esas rutas).

- [ ] **Step 7: Correr la suite completa del proyecto**

Run: `python -m pytest -v`
Expected: PASS — sin regresiones en otras fases (`esterilizacion.py`, `estabilizacion.py`, etc. no se tocan).

- [ ] **Step 8: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_fase.py
git commit -m "feat: control por tasa en tramo APROXIMACION de CALENTAMIENTO

tasa_calentamiento/tasa_presion pasan de ser solo umbral de falla a
gobernar vapor_camara con bang-bang directo por tick, ya que la
valvula solo admite ON/OFF. PWM_ACTIVO y el chequeo de FALLO no
cambian. Ver docs/superpowers/specs/2026-08-03-tasa-control-calentamiento-design.md"
```

---

### Task 2: Actualizar documentación de la fase

**Files:**
- Modify: `docs/mis_plans/planeacion_fase_calentamiento.md:64-65` (tabla de parámetros), `:116` (nota tras el diagrama), `:124` (sección 4.1)

**Interfaces:**
- Consumes: ninguna — cambio de documentación, no de código.
- Produces: ninguna — no afecta a otros tasks ni a código.

- [ ] **Step 1: Actualizar el rol de `tasa_calentamiento`/`tasa_presion` en la tabla de parámetros**

En `docs/mis_plans/planeacion_fase_calentamiento.md`, reemplazar las filas 6 y 7 de la tabla (sección 2):

```markdown
| 6 | Tasa de calentamiento | `tasa_calentamiento` | °C/min | 50 | 0 | 100 | Umbral de falla — pendiente máxima de temperatura (debounce 3 lecturas) |
| 7 | Tasa de presion | `tasa_presion` | kPa/min | 100 | 0 | 300 | Umbral de falla — pendiente máxima de presión (debounce 3 lecturas) |
```

por:

```markdown
| 6 | Tasa de calentamiento | `tasa_calentamiento` | °C/min | 50 | 0 | 100 | Setpoint de control (techo de subida en APROXIMACION, bang-bang de `vapor_camara`) + umbral de falla (debounce 3 lecturas) |
| 7 | Tasa de presion | `tasa_presion` | kPa/min | 100 | 0 | 300 | Setpoint de control (techo de subida en APROXIMACION, bang-bang de `vapor_camara`) + umbral de falla (debounce 3 lecturas) |
```

- [ ] **Step 2: Agregar nota de actualización tras el diagrama de la sección 3**

En la misma spec, después de la línea `El chequeo de \`tasa_calentamiento\` / \`tasa_presion\` (con debounce de 3 lecturas) corre también en paralelo, activo durante toda la fase, y puede producir \`FALLO\` desde cualquier tramo.` y antes del separador `---` que le sigue, insertar:

```markdown

**Actualización (control por tasa en APROXIMACION):** dentro del tramo `APROXIMACION`, `vapor_camara` deja de ser "ON continuo" sin condición — pasa a un bang-bang directo por tick: ON salvo que la pendiente medida (`tasa_t`/`tasa_p`, mismo cálculo del chequeo de falla) ya supere `tasa_calentamiento`/`tasa_presion`. Solo limita la dirección de subida (la válvula no puede enfriar). `PWM_ACTIVO` y `ESTABLE_PREESTERILIZACION` no cambian. Ver detalle en `docs/superpowers/specs/2026-08-03-tasa-control-calentamiento-design.md`.
```

(El diagrama ASCII de la máquina de estados no se redibuja — sigue siendo esquemático; la nota de texto documenta el comportamiento real.)

- [ ] **Step 3: Actualizar la sección 4.1 (Control de `vapor_camara`)**

Reemplazar la línea:

```markdown
- Tramo `APROXIMACION`: `vapor_camara` en `ON` continuo (sin PWM, sin límite de rampa activo — `tasa_calentamiento` solo vigila, no limita).
```

por:

```markdown
- Tramo `APROXIMACION`: `vapor_camara` en bang-bang directo por tick — ON salvo que la pendiente medida ese tick (`tasa_t = (temp - temp_anterior)/dt_min`, `tasa_p` análogo) ya supere `tasa_calentamiento`/`tasa_presion` (0 deshabilita ese límite). Solo se limita la dirección de subida: `tasa_t` se compara sin valor absoluto porque la válvula no puede enfriar la cámara. Sin tiempo mínimo de apagado — se reevalúa cada tick.
```

- [ ] **Step 4: Commit**

```bash
git add docs/mis_plans/planeacion_fase_calentamiento.md
git commit -m "docs: reflejar control por tasa en tramo APROXIMACION de calentamiento"
```

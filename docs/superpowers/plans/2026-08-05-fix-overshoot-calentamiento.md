# Corrección de sobrepaso de temperatura en CALENTAMIENTO — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corregir el sobrepaso de temperatura observado en CALENTAMIENTO (ciclo 72, 2026-08-05: objetivo 121°C, pico real 133.4°C) agregando tres mecanismos de control en `calentamiento.py`, sin parámetros JSON nuevos.

**Architecture:** Tres cambios acotados al `update()` de `CalentamientoFase`, paso 4 (gate de entrada a PWM_ACTIVO) y paso 5 (control de `vapor_camara`). Ningún cambio a la máquina de estados de tramos, a otras fases, ni a los perfiles JSON.

**Tech Stack:** Python 3.14, pytest, `unittest.mock.MagicMock` para los fixtures de fase.

## Global Constraints

- Spec de referencia: `docs/superpowers/specs/2026-08-05-fix-overshoot-calentamiento-design.md` — todo el diseño detallado (fórmulas exactas, tabla de datos del ciclo real) vive ahí; este plan no lo repite salvo lo estrictamente necesario para cada tarea.
- No se agregan parámetros JSON nuevos — todo reutiliza `temperatura_calentamiento`, `presion_add_calentamiento`, `rango_calentamiento` ya existentes en la sección `calentamiento` de los perfiles.
- La única constante nueva de código es `_FACTOR_TOPE_TEMPERATURA = 0.97`, a nivel de módulo en `calentamiento.py`.
- No se toca `esterilizacion.py` ni ninguna otra fase.
- Archivo bajo prueba: `src/autoclave/state_machine/cycle_phases/calentamiento.py`. Archivo de tests: `tests/test_calentamiento_fase.py`. Ejecutar con `python -m pytest tests/test_calentamiento_fase.py -v` desde la raíz del repo.
- Baseline verificado antes de empezar: `python -m pytest tests/test_calentamiento_fase.py -q` → 32 passed.

---

### Task 1: Gate de entrada a PWM_ACTIVO anclado al objetivo fijo (mecanismo 1)

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py:191-194`
- Modify: `tests/test_calentamiento_fase.py` (5 tests existentes actualizan su valor de disparo; 2 tests nuevos)

**Interfaces:**
- Consumes: nada de tareas anteriores (primera tarea).
- Produces: el gate de entrada a `_en_pwm` queda anclado a `p_obj`/`t_obj` (ya calculados como variables locales en `update()`, líneas 127 y 143 del archivo actual). La Tarea 2 inserta código *antes* de este bloque en el paso 5, sin depender de ningún nombre nuevo introducido aquí.

El código actual en `calentamiento.py:126-267` (método `update()`) tiene, en el paso 4 (líneas 191-194):

```python
        # ── 4. Entrada a PWM (unidireccional) ─────────────────────────────
        if not self._en_pwm and abs(pres - p_saturacion_kpa(temp)) <= rango_cal:
            self._en_pwm = True
            logger.info("Calentamiento: banda alcanzada (%.1f kPa) — entra a PWM_ACTIVO", rango_cal)
```

Esto compara la presión contra la curva de saturación de la temperatura **actual** (que sube), en vez del objetivo fijo `p_obj`/`t_obj` — causa raíz confirmada del sobrepaso de 121°C a 133.4°C en el ciclo real (ver spec sección 1).

- [ ] **Step 1: Actualizar los 5 tests existentes que dependen del gate viejo para disparar con el valor nuevo**

Estos 5 tests en `tests/test_calentamiento_fase.py` fuerzan la entrada a PWM_ACTIVO con `temp_camara=130.0` y `pres_camara=p_saturacion_kpa(130.0)` (el gate viejo). Con el gate nuevo (`pres >= p_obj - rango_cal or temp >= t_obj`), ese valor de presión ya no dispara nada porque `t_obj=134.0` por defecto y `p_saturacion_kpa(130.0)` está muy por debajo de `p_obj - rango_cal`. Reemplazar la línea de presión en cada uno por `p_obj` (calculado como `p_saturacion_kpa(134.0) + 11.0`, que es `>= p_obj - rango_cal` trivialmente).

Reemplazar completo (líneas 86-170 actuales):

```python
def test_entra_a_pwm_dentro_de_la_banda():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 130.0
    estado.sensores_pres["pres_camara"] = p_obj
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_pwm is True


def test_pwm_no_retorna_a_aproximacion_si_sale_de_la_banda():
    """Una vez en PWM_ACTIVO, no hay retroceso aunque la lectura salga
    momentáneamente de la banda (evita chattering, ver plan sección 4.1)."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 130.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()
    assert fase._en_pwm is True

    estado.sensores_pres["pres_camara"] = 50.0  # muy fuera de la banda ahora
    fase.update()
    assert fase._en_pwm is True


# ── PWM duty cycle ────────────────────────────────────────────────────────

def test_pwm_pulso_on_luego_off_por_tiempo():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0, intervalo=2)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 130.0
    estado.sensores_pres["pres_camara"] = p_obj
    set_do.reset_mock()
    result = fase.update()  # entra a PWM, primer pulso ON
    assert result == FaseResult.EN_CURSO
    assert fase._pwm_abierto is True
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()

    set_do.reset_mock()
    fase._t_pulso_pwm -= 2  # simular que pasó t_on (50% de 2s = 1s)
    fase.update()
    assert fase._pwm_abierto is False
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_pwm_factor_cero_permanece_encendido():
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=0.0, intervalo=2)
    fase.update()
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 130.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # entra a PWM
    set_do.reset_mock()
    fase.update()
    set_do.vapor_camara_off.assert_not_called()
    set_do.vapor_camara_on.assert_called()


def test_pwm_activo_ignora_tasa_calentamiento_excedida():
    """El control por tasa es exclusivo de APROXIMACION (plan, restricción
    global) — una vez en PWM_ACTIVO, una pendiente que excedería
    tasa_calentamiento no debe forzar OFF fuera del ciclo PWM programado.
    El salto de temperatura se mantiene pequeño y dentro del objetivo
    (132°C, con t_obj=134°C) para no cruzar el tope del 97% ni el techo
    independiente agregados en la Tarea 2 de este plan — ver
    docs/superpowers/specs/2026-08-05-fix-overshoot-calentamiento-design.md."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0, intervalo=2,
                                       tasa_calentamiento=10.0, tasa_presion=200.0)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 130.0
    estado.sensores_pres["pres_camara"] = p_obj
    fase.update()  # entra a PWM_ACTIVO
    assert fase._en_pwm is True

    _sembrar_historial(fase, 130.0, p_obj, 10)  # ventana corta: un salto chico ya excede la tasa
    fase._pwm_abierto = False
    fase._t_pulso_pwm = time.time() - 100
    estado.sensores_temp["temp_camara"] = 132.0  # 12°C/min > 10, pero se mantiene bajo t_obj
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()
```

- [ ] **Step 2: Agregar 2 tests nuevos que reproducen el bug real y su seguro inverso**

Agregar al final del bloque `# ── Entrada a PWM_ACTIVO ─────────────────────────────────────────────────` (después de `test_pwm_no_retorna_a_aproximacion_si_sale_de_la_banda`, antes del comentario `# ── PWM duty cycle`):

```python
def test_entra_a_pwm_por_presion_cercana_al_objetivo_aunque_lejos_de_p_sat_temp():
    """Regresión del bug real (ciclo 72, 2026-08-05): la presión corre
    persistentemente por encima de P_sat(temp_actual) durante toda la subida
    (chaqueta/aire residual/calibración) — el gate viejo (abs(pres -
    P_sat(temp)) <= rango_cal) nunca se cumplía hasta muy tarde. El nuevo
    gate debe disparar por cercanía al objetivo fijo p_obj, sin importar
    P_sat(temp_actual)."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 110.0  # P_sat(110) ~ 146 kPa, muy lejos de p_obj
    estado.sensores_pres["pres_camara"] = p_obj - 1.0  # a 1 kPa del objetivo
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_pwm is True


def test_entra_a_pwm_por_temperatura_si_presion_esta_rezagada():
    """Seguro en la dirección contraria: si la temperatura cruza t_obj antes
    de que la presión se acerque a p_obj, igual se entra a PWM_ACTIVO —
    nunca se sigue con la válvula a fondo una vez cruzado el setpoint de
    temperatura."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0)
    fase.update()  # inicializar
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = 50.0  # muy por debajo de p_obj
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert fase._en_pwm is True
```

- [ ] **Step 3: Correr los tests y verificar que fallan (rojo) contra el código viejo**

Run: `python -m pytest tests/test_calentamiento_fase.py -v -k "pwm or entra_a_pwm"`
Expected: FAIL en los 7 tests tocados (`test_entra_a_pwm_dentro_de_la_banda`, `test_pwm_no_retorna_a_aproximacion_si_sale_de_la_banda`, `test_pwm_pulso_on_luego_off_por_tiempo`, `test_pwm_factor_cero_permanece_encendido`, `test_pwm_activo_ignora_tasa_calentamiento_excedida`, `test_entra_a_pwm_por_presion_cercana_al_objetivo_aunque_lejos_de_p_sat_temp`, `test_entra_a_pwm_por_temperatura_si_presion_esta_rezagada`) — todos con `assert fase._en_pwm is True` fallando porque el gate viejo nunca se cumple con estos valores.

- [ ] **Step 4: Implementar el gate nuevo**

En `src/autoclave/state_machine/cycle_phases/calentamiento.py`, reemplazar el paso 4 (líneas 191-194):

```python
        # ── 4. Entrada a PWM (unidireccional) ─────────────────────────────
        if not self._en_pwm and abs(pres - p_saturacion_kpa(temp)) <= rango_cal:
            self._en_pwm = True
            logger.info("Calentamiento: banda alcanzada (%.1f kPa) — entra a PWM_ACTIVO", rango_cal)
```

por:

```python
        # ── 4. Entrada a PWM (unidireccional) ─────────────────────────────
        # Ancla la entrada al objetivo fijo (p_obj/t_obj), no a la curva de
        # saturación de la temperatura actual (que se mueve mientras sube) —
        # ver docs/superpowers/specs/2026-08-05-fix-overshoot-calentamiento-design.md.
        if not self._en_pwm and (pres >= p_obj - rango_cal or temp >= t_obj):
            self._en_pwm = True
            logger.info("Calentamiento: objetivo cercano (%.1f kPa / %.1f°C) — entra a PWM_ACTIVO", p_obj, t_obj)
```

- [ ] **Step 5: Correr los tests y verificar que pasan (verde)**

Run: `python -m pytest tests/test_calentamiento_fase.py -v`
Expected: PASS en los 34 tests (32 originales + 2 nuevos).

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_fase.py
git commit -m "fix: anclar gate de entrada a PWM_ACTIVO al objetivo fijo en CALENTAMIENTO

El gate comparaba la presión contra P_sat(temp_actual) en vez del
objetivo fijo p_obj/t_obj, causa raíz del sobrepaso de 121°C a 133.4°C
observado en ciclo 72 (2026-08-05). Ver
docs/superpowers/specs/2026-08-05-fix-overshoot-calentamiento-design.md."
```

---

### Task 2: Tope de temperatura al 97% y techo independiente (mecanismos 2 y 3)

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py:49` (constante nueva), `:196-218` (paso 5 completo), `:1-31` (comentario de cabecera)
- Modify: `tests/test_calentamiento_fase.py` (4 tests nuevos)
- Modify: `CLAUDE.md:27`

**Interfaces:**
- Consumes: `p_obj`, `t_obj`, `p_add` (variables locales ya existentes en `update()`, líneas 127-143); el gate de la Tarea 1 (sin dependencia directa de código, solo conviven en el mismo método).
- Produces: paso 5 de `update()` queda con dos chequeos nuevos (`temp_cap`/`p_min_para_temp` y `p_techo`) evaluados antes de las ramas bang-bang/PWM existentes. Nada de esto es consumido por tareas posteriores (última tarea del plan).

- [ ] **Step 1: Escribir los 4 tests nuevos (mecanismos 2 y 3)**

Agregar en `tests/test_calentamiento_fase.py`, después del bloque `# ── PWM duty cycle ────────────────────────────────────────────────────────` y antes de `# ── Escape lento / escape rápido`:

```python
# ── Tope de temperatura al 97% (espera de presión) ───────────────────────

def test_tope_97_pausa_vapor_si_presion_no_corresponde_a_la_temperatura():
    """Mecanismo 2: si temp ya llegó al 97% de t_obj pero la presión aún no
    alcanza P_sat(temp actual) + presion_add_calentamiento, se pausa el
    vapor (no se sigue subiendo temperatura sin presión real que la respalde)."""
    fase, estado, set_do = _make_fase(t_obj=100.0, presion_add=11.0, rango=2.0)
    fase.update()  # inicializar
    temp = 97.5  # 97.5% de 100 >= temp_cap (97.0)
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(temp) + 11.0 - 5.0  # 5 kPa por debajo de lo esperado
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()


def test_tope_97_libera_pausa_cuando_presion_alcanza_lo_esperado():
    fase, estado, set_do = _make_fase(t_obj=100.0, presion_add=11.0, rango=2.0)
    fase.update()
    temp = 97.5
    estado.sensores_temp["temp_camara"] = temp
    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(temp) + 11.0 - 5.0
    fase.update()  # pausado

    estado.sensores_pres["pres_camara"] = p_saturacion_kpa(temp) + 11.0  # alcanza el nivel esperado
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


def test_tope_97_no_pausa_por_debajo_del_tope():
    """Regresión: por debajo del 97% de t_obj, el tope no debe activarse
    aunque la presión esté baja — eso lo sigue manejando el bang-bang normal
    de APROXIMACION."""
    fase, estado, set_do = _make_fase(t_obj=100.0, presion_add=11.0, rango=2.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 90.0  # 90% de 100, bajo temp_cap (97.0)
    estado.sensores_pres["pres_camara"] = 10.0  # muy baja, no "corresponde" a 90°C tampoco
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called()
    set_do.vapor_camara_off.assert_not_called()


# ── Techo independiente ───────────────────────────────────────────────────

def test_techo_independiente_apaga_vapor_sin_importar_pwm():
    """Mecanismo 3: si la presión ya supera p_obj + presion_add_calentamiento,
    se apaga el vapor sin importar el duty cycle programado."""
    fase, estado, set_do = _make_fase(t_obj=134.0, presion_add=11.0, rango=2.0, factor=50.0, intervalo=2)
    fase.update()  # inicializar
    p_obj = p_saturacion_kpa(134.0) + 11.0
    estado.sensores_temp["temp_camara"] = 134.0
    estado.sensores_pres["pres_camara"] = p_obj  # entra a PWM (gate mecanismo 1)
    fase.update()
    assert fase._en_pwm is True

    estado.sensores_pres["pres_camara"] = p_obj + 11.0 + 1.0  # rebasa p_techo = p_obj + presion_add
    set_do.reset_mock()
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_off.assert_called()
    set_do.vapor_camara_on.assert_not_called()
    assert fase._pwm_abierto is False
```

- [ ] **Step 2: Correr los tests nuevos y verificar que fallan (rojo)**

Run: `python -m pytest tests/test_calentamiento_fase.py -v -k "tope_97 or techo_independiente"`
Expected: FAIL en los 4 tests — el código actual no tiene ninguno de los dos mecanismos, así que `vapor_camara_off` nunca se llama donde se espera (los tests de pausa/techo) o el bang-bang normal ya pasaba de todos modos (el test de "no pausa por debajo del tope" puede pasar por casualidad con el código viejo — si pasa ya en este punto, está bien, confirma que no rompe nada al agregar el mecanismo; lo importante es que los otros 3 fallen).

- [ ] **Step 3: Agregar la constante de módulo**

En `src/autoclave/state_machine/cycle_phases/calentamiento.py`, después de la línea 49 (`_VENTANA_PENDIENTE_SEG = 10`):

```python
_VENTANA_PENDIENTE_SEG = 10

# Tope de temperatura mientras la presión no "corresponde" a la temperatura
# actual (mecanismo 2, ver docs/superpowers/specs/
# 2026-08-05-fix-overshoot-calentamiento-design.md): pausa el vapor si ya
# se llegó al 97% del objetivo pero P_sat(temp_actual) + presion_add_calentamiento
# todavía no se alcanzó — evita que el sensor de temperatura corra por
# delante de la presión real (vapor no saturado).
_FACTOR_TOPE_TEMPERATURA = 0.97
```

- [ ] **Step 4: Implementar los mecanismos 2 y 3 en el paso 5**

Reemplazar el paso 5 completo (líneas 196-218 actuales):

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

por:

```python
        # ── 5. Control de vapor_camara ─────────────────────────────────────
        temp_cap = _FACTOR_TOPE_TEMPERATURA * t_obj
        p_min_para_temp = p_saturacion_kpa(temp) + p_add
        p_techo = p_obj + p_add

        if temp >= temp_cap and pres < p_min_para_temp:
            # Mecanismo 2: la temperatura ya llegó al 97% del objetivo pero
            # la presión todavía no "corresponde" a esa temperatura (vapor
            # no saturado) — no se sigue calentando hasta que la presión
            # alcance P_sat(temp actual) + presion_add_calentamiento.
            self.set_do.vapor_camara_off()
            self._pwm_abierto = False
            self._t_pulso_pwm = None
        elif pres >= p_techo:
            # Mecanismo 3 (techo independiente): corta el vapor sin importar
            # el tramo si la presión ya rebasó lo tolerado, en vez de esperar
            # pasivamente a que la inercia se disipe (mismo límite que ya usa
            # dentro_rango en el paso 7 para tolerar sobrepaso).
            self.set_do.vapor_camara_off()
            self._pwm_abierto = False
            self._t_pulso_pwm = None
        elif not self._en_pwm:
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

- [ ] **Step 5: Correr los tests nuevos y verificar que pasan (verde)**

Run: `python -m pytest tests/test_calentamiento_fase.py -v -k "tope_97 or techo_independiente"`
Expected: PASS en los 4 tests.

- [ ] **Step 6: Correr el archivo de test completo y confirmar cero regresiones**

Run: `python -m pytest tests/test_calentamiento_fase.py -v`
Expected: PASS en los 38 tests (34 de la Tarea 1 + 4 nuevos de esta tarea). Si algo falla fuera de los tests tocados en este plan, detenerse y re-investigar antes de continuar — no ajustar aserciones para forzar el verde.

- [ ] **Step 7: Actualizar el comentario de cabecera del archivo**

En `src/autoclave/state_machine/cycle_phases/calentamiento.py`, reemplazar las líneas 10-24 actuales:

```python
#   APROXIMACION              vapor_camara en bang-bang por tick: ON salvo
#                              que la pendiente ya supere tasa_calentamiento/
#                              tasa_presion (0 = sin límite; solo limita subida)
#   PWM_ACTIVO                entra al alcanzar |P - P_sat(T)| <= rango_calentamiento;
#                              vapor_camara en PWM (factor_calentamiento / intervalo_segmentos_calor)
#   ESTABLE_PREESTERILIZACION entra al cruzar temp>=t_obj y pres>=p_obj; exige
#                              una ventana CONTINUA de tiempo_estable_preesterilizacion
#                              segundos dentro de banda (|T-t_obj|<=rango_temp_estabilizacion
#                              Y |P-p_obj|<=presion_add_calentamiento) — el conteo
#                              se reinicia si sale de banda, así se espera a que
#                              la inercia térmica se disipe antes de completar.
#                              Timeout de recuperación dedicado
#                              (timeout_recuperacion_estabilizacion) si nunca
#                              converge. Ver docs/superpowers/specs/
#                              2026-08-04-fusion-calentamiento-estabilizacion-design.md
```

por:

```python
#   APROXIMACION              vapor_camara en bang-bang por tick: ON salvo
#                              que la pendiente ya supere tasa_calentamiento/
#                              tasa_presion (0 = sin límite; solo limita subida)
#   PWM_ACTIVO                entra al acercarse al objetivo fijo (pres >=
#                              p_obj - rango_calentamiento, o temp >= t_obj
#                              como seguro inverso); vapor_camara en PWM
#                              (factor_calentamiento / intervalo_segmentos_calor)
#   ESTABLE_PREESTERILIZACION entra al cruzar temp>=t_obj y pres>=p_obj; exige
#                              una ventana CONTINUA de tiempo_estable_preesterilizacion
#                              segundos dentro de banda (|T-t_obj|<=rango_temp_estabilizacion
#                              Y |P-p_obj|<=presion_add_calentamiento) — el conteo
#                              se reinicia si sale de banda, así se espera a que
#                              la inercia térmica se disipe antes de completar.
#                              Timeout de recuperación dedicado
#                              (timeout_recuperacion_estabilizacion) si nunca
#                              converge. Ver docs/superpowers/specs/
#                              2026-08-04-fusion-calentamiento-estabilizacion-design.md
#
# Control de vapor_camara (paso 5), de mayor a menor prioridad — corrección
# 2026-08-05 tras sobrepaso real de 121°C a 133.4°C (ver docs/superpowers/
# specs/2026-08-05-fix-overshoot-calentamiento-design.md):
#   1. Tope 97%     temp >= 0.97*t_obj Y pres < P_sat(temp)+presion_add_calentamiento
#                    -> pausa (vapor OFF) hasta que la presión "corresponda"
#                    a la temperatura actual.
#   2. Techo        pres >= p_obj + presion_add_calentamiento -> vapor OFF,
#                    sin importar el tramo activo.
#   3. Normal       bang-bang (APROXIMACION) o PWM (PWM_ACTIVO), como antes.
```

- [ ] **Step 8: Actualizar CLAUDE.md**

En `CLAUDE.md:27`, reemplazar:

```markdown
- `calentamiento.py` — **rediseñado** (ver `docs/mis_plans/planeacion_fase_calentamiento.md`): tramos APROXIMACION → PWM_ACTIVO → ESTABLE_PREESTERILIZACION, sin retroceso entre ellos. ESTABLE_PREESTERILIZACION exige una ventana continua de estabilidad (con reinicio ante overshoot) antes de entregar control a ESTERILIZACION — fusiona lo que antes era la fase separada `EstabilizacionFase` (ver `docs/superpowers/specs/2026-08-04-fusion-calentamiento-estabilizacion-design.md`).
```

por:

```markdown
- `calentamiento.py` — **rediseñado** (ver `docs/mis_plans/planeacion_fase_calentamiento.md`): tramos APROXIMACION → PWM_ACTIVO → ESTABLE_PREESTERILIZACION, sin retroceso entre ellos. ESTABLE_PREESTERILIZACION exige una ventana continua de estabilidad (con reinicio ante overshoot) antes de entregar control a ESTERILIZACION — fusiona lo que antes era la fase separada `EstabilizacionFase` (ver `docs/superpowers/specs/2026-08-04-fusion-calentamiento-estabilizacion-design.md`). El gate APROXIMACION→PWM_ACTIVO y el control de `vapor_camara` se corrigieron el 2026-08-05 tras un sobrepaso real de 121°C a 133.4°C: el gate se ancla al objetivo fijo (antes seguía P_sat(temp_actual), causa raíz), se agregó un tope al 97% de temperatura que pausa el vapor hasta que la presión "corresponda" a la temperatura actual, y un techo independiente que corta el vapor si la presión supera `p_obj + presion_add_calentamiento` (ver `docs/superpowers/specs/2026-08-05-fix-overshoot-calentamiento-design.md`).
```

- [ ] **Step 9: Correr toda la suite de tests del proyecto**

Run: `python -m pytest -q`
Expected: mismo número de passed que antes de este plan, más los 6 tests nuevos (2 de la Tarea 1, 4 de esta tarea) — cero failures nuevas. Si algo fuera de `test_calentamiento_fase.py` falla, investigar antes de continuar (podría indicar un test en otro archivo que también dependía del gate viejo).

- [ ] **Step 10: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/calentamiento.py tests/test_calentamiento_fase.py CLAUDE.md
git commit -m "fix: agregar tope de 97% y techo independiente al control de CALENTAMIENTO

Mecanismos 2 y 3 del rediseño de sobrepaso (ver
docs/superpowers/specs/2026-08-05-fix-overshoot-calentamiento-design.md):
pausa el vapor si la temperatura llega al 97% del objetivo sin presión
real que la respalde, y un techo independiente corta el vapor sin
esperar la recuperación pasiva de 5 min cuando la presión ya rebasó lo
tolerado."
```

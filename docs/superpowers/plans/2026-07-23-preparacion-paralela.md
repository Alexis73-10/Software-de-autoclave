# PREPARACION en paralelo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir `preparacion_state` de un secuenciador lineal por pasos (`self.step`) a ejecución paralela continua de sus 4 condiciones cada tick, igual patrón que `preparado_state`, sin cambiar ninguna verificación/condición existente.

**Architecture:** `ejecutor()` deja de gatear funciones por `self.step` y las llama todas cada tick. Las dos únicas funciones que comparten una salida física (`igualar_presion_camara` y `drenar_camara`, ambas controlan `descompresion_rapida`) dejan de escribir esa salida directamente: retornan una tupla `(ok, quiere_rapida)` y `ejecutor()` combina el segundo valor con OR antes de escribir la salida una sola vez. El chequeo de paro de emergencia se mueve al inicio de `run()` (antes de `supervisor()`), igual que en `preparado.run()`.

**Tech Stack:** Python, pytest, unittest.mock.MagicMock (mismo patrón de test ya usado en `tests/test_preparacion_*.py` y `tests/test_preparado_*.py`).

## Global Constraints

- Las verificaciones y condiciones (bandas de presión, chequeos de sensores, decisiones de abrir/cerrar cada salida) no cambian de valor — solo cambia cuándo se evalúan y, para `descompresion_rapida`, cómo se combina.
- No se toca `preparado.py`.
- No se agrega debounce de alarmas, ni `puertas_cerradas()`, ni timeout nuevo a PREPARACION (spec: `docs/superpowers/specs/2026-07-23-preparacion-paralela-design.md`, sección "Fuera de alcance").
- `state_machine.py` no se modifica — sigue llamando `self.preparacion.reset()` al entrar a PREPARACION y `self.preparacion.run()` en cada tick; ambos métodos deben seguir existiendo con la misma firma.

---

### Task 1: `igualar_presion_camara()` retorna `(ok, quiere_rapida)` en vez de accionar `descompresion_rapida` directamente

**Files:**
- Modify: `src/autoclave/state_machine/states/preparacion.py:232-261`
- Test: `tests/test_preparacion_presion_camara.py` (nuevo)

**Interfaces:**
- Produces: `preparacion_state.igualar_presion_camara() -> tuple[bool, bool]` — `(presion_ok, quiere_descompresion_rapida)`. `quiere_descompresion_rapida=True` únicamente cuando `pres_camara > presion_admosferica + rango_presion_atm`.
- No sigue llamando `self.set_do.descompresion_rapida_on()/off()` — esa decisión pasa a `ejecutor()` (Task 3).

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_preparacion_presion_camara.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.preparacion import preparacion_state


def _make_preparacion(pres_camara, presion_admosferica=1013.0, rango=5.0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres_camara}
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    config.get.side_effect = lambda key: {
        "presion_admosferica": presion_admosferica,
        "rango_presion_atm": rango,
    }[key]
    p = preparacion_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_presion_en_banda_ok_sin_pedir_rapida():
    p, alarm_mgr, set_do = _make_preparacion(pres_camara=1013.0)
    ok, quiere_rapida = p.igualar_presion_camara()
    assert ok is True
    assert quiere_rapida is False
    set_do.aire_admosferico_camara_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_rapida_off.assert_not_called()


def test_presion_baja_pide_aire_no_pide_rapida():
    p, alarm_mgr, set_do = _make_preparacion(pres_camara=1000.0)
    ok, quiere_rapida = p.igualar_presion_camara()
    assert ok is False
    assert quiere_rapida is False
    set_do.aire_admosferico_camara_on.assert_called()
    ids = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "PRESION_CAMARA_BAJA" in ids


def test_presion_alta_pide_rapida():
    p, alarm_mgr, set_do = _make_preparacion(pres_camara=1030.0)
    ok, quiere_rapida = p.igualar_presion_camara()
    assert ok is False
    assert quiere_rapida is True
    set_do.aire_admosferico_camara_off.assert_called()
    ids = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "PRESION_CAMARA_ALTA" in ids
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_preparacion_presion_camara.py -v`
Expected: FAIL — `igualar_presion_camara()` hoy retorna `True`/`False`/`None` (no tupla), y llama `set_do.descompresion_rapida_on/off` directamente, así que `assert_not_called()` de esas dos líneas también fallaría en el caso "presión alta".

- [ ] **Step 3: Implementar**

Reemplazar `igualar_presion_camara` en `preparacion.py` (líneas 232-261):

```python
    def igualar_presion_camara(self):
            """Retorna (ok, quiere_descompresion_rapida). No acciona la
            válvula descompresion_rapida directamente: esa salida es
            compartida con drenar_camara() y se combina en ejecutor()."""
            presion_camara = self.estado.sensores_pres["pres_camara"]
            presion_atmosferica = self.config.get("presion_admosferica")
            rango_presion_atmosferica = self.config.get("rango_presion_atm")
            pres_cam_min = presion_atmosferica - rango_presion_atmosferica
            pres_cam_max = presion_atmosferica + rango_presion_atmosferica

            if pres_cam_min <= presion_camara <= pres_cam_max:
                # Presión igualada
                self.set_do.aire_admosferico_camara_off()
                self.set_do.descompresion_lenta_off()
                self.alarm_manager.clear("PRESION_CAMARA_BAJA")
                self.alarm_manager.clear("PRESION_CAMARA_ALTA")
                return True, False

            if presion_camara < pres_cam_min:
                # Abrir entrada de aire comprimido a la camara
                self.set_do.aire_admosferico_camara_on()
                alarm_id = "PRESION_CAMARA_BAJA"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False, False

            # presion_camara > pres_cam_max: requiere venteo/vacío
            self.set_do.aire_admosferico_camara_off()
            alarm_id = "PRESION_CAMARA_ALTA"
            self.alarm(alarm_id, AlarmType.ALERTA)
            return False, True
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_preparacion_presion_camara.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/preparacion.py tests/test_preparacion_presion_camara.py
git commit -m "refactor: igualar_presion_camara retorna (ok, quiere_rapida) sin accionar la valvula directamente"
```

---

### Task 2: `drenar_camara()` retorna `(ok, quiere_rapida)` en vez de accionar `descompresion_rapida` directamente

**Files:**
- Modify: `src/autoclave/state_machine/states/preparacion.py:263-273` (números de línea previos a Task 1; tras Task 1 la función se desplaza pero el contenido a reemplazar es identificable por su firma `def drenar_camara(self):`)
- Test: `tests/test_preparacion_drenaje.py` (nuevo)

**Interfaces:**
- Consumes: nada de Task 1.
- Produces: `preparacion_state.drenar_camara() -> tuple[bool, bool]` — `(drenaje_ok, quiere_descompresion_rapida)`. `quiere_descompresion_rapida=True` cuando `agua_camara` (DI) está activo.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_preparacion_drenaje.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.preparacion import preparacion_state


def _make_preparacion(agua_camara):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_di = {"agua_camara": agua_camara}
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    p = preparacion_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_sin_agua_residual_ok_sin_pedir_rapida():
    p, alarm_mgr, set_do = _make_preparacion(agua_camara=0)
    ok, quiere_rapida = p.drenar_camara()
    assert ok is True
    assert quiere_rapida is False
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_rapida_off.assert_not_called()


def test_con_agua_residual_pide_rapida():
    p, alarm_mgr, set_do = _make_preparacion(agua_camara=1)
    ok, quiere_rapida = p.drenar_camara()
    assert ok is False
    assert quiere_rapida is True
    set_do.descompresion_rapida_on.assert_not_called()
    ids = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "AGUA_RESIDUAL_CAMARA" in ids
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_preparacion_drenaje.py -v`
Expected: FAIL — `drenar_camara()` hoy retorna `True`/`False` (no tupla) y llama `set_do.descompresion_rapida_on/off` directamente.

- [ ] **Step 3: Implementar**

Reemplazar `drenar_camara` en `preparacion.py`:

```python
    def drenar_camara(self):
            """Retorna (ok, quiere_descompresion_rapida). No acciona la
            válvula descompresion_rapida directamente: esa salida es
            compartida con igualar_presion_camara() y se combina en
            ejecutor()."""
            agua_residual = self.estado.sensores_di["agua_camara"]
            if not agua_residual:
                self.alarm_manager.clear("AGUA_RESIDUAL_CAMARA")
                return True, False

            alarm_id = "AGUA_RESIDUAL_CAMARA"
            self.alarm(alarm_id, AlarmType.ALERTA)
            return False, True
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_preparacion_drenaje.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/preparacion.py tests/test_preparacion_drenaje.py
git commit -m "refactor: drenar_camara retorna (ok, quiere_rapida) sin accionar la valvula directamente"
```

---

### Task 3: `ejecutor()` corre las 4 condiciones en paralelo cada tick; `run()` mueve el chequeo de emergencia antes de `supervisor()`; se elimina `self.step`

**Files:**
- Modify: `src/autoclave/state_machine/states/preparacion.py` — `__init__` (líneas 19-26), `run()` (60-67), `ejecutor()` (79-120), `reset()` (288-289), y el bloque de comentario descriptivo del estado (líneas 28-40).
- Test: `tests/test_preparacion_ejecutor_paralelo.py` (nuevo)

**Interfaces:**
- Consumes: `igualar_presion_camara() -> (bool, bool)` y `drenar_camara() -> (bool, bool)` de Tasks 1-2; `suministrar_vapor_chaqueta() -> bool` y `verificar_temperatura_drenaje() -> bool` (sin cambios, firmas ya existentes).
- Produces: `preparacion_state.run() -> bool` y `preparacion_state.ejecutor() -> bool` (firmas sin cambios respecto a antes — `state_machine.py:76` sigue llamando `self.preparacion.run()` igual que hoy, sin modificaciones ahí). `preparacion_state` deja de tener el atributo `self.step`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_preparacion_ejecutor_paralelo.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.preparacion import preparacion_state


def _make_preparacion(paro_emergencia=0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_di = {"paro_emergencia": paro_emergencia}
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    p = preparacion_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def _stub_condiciones(p, chaqueta=True, presion=(True, False), drenaje=(True, False), temp=True):
    p.suministrar_vapor_chaqueta = lambda: chaqueta
    p.igualar_presion_camara = lambda: presion
    p.drenar_camara = lambda: drenaje
    p.verificar_temperatura_drenaje = lambda: temp


def test_valvula_rapida_abre_si_presion_la_pide_aunque_drenaje_no():
    p, alarm_mgr, set_do = _make_preparacion()
    _stub_condiciones(p, presion=(False, True), drenaje=(True, False))
    p.ejecutor()
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_rapida_off.assert_not_called()


def test_valvula_rapida_abre_si_drenaje_la_pide_aunque_presion_no():
    p, alarm_mgr, set_do = _make_preparacion()
    _stub_condiciones(p, presion=(True, False), drenaje=(False, True))
    p.ejecutor()
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_rapida_off.assert_not_called()


def test_valvula_rapida_cierra_si_ninguna_la_pide():
    p, alarm_mgr, set_do = _make_preparacion()
    _stub_condiciones(p, presion=(True, False), drenaje=(True, False))
    p.ejecutor()
    set_do.descompresion_rapida_off.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()


def test_ejecutor_retorna_true_solo_si_las_4_condiciones_ok():
    p, alarm_mgr, set_do = _make_preparacion()
    _stub_condiciones(p, chaqueta=True, presion=(True, False), drenaje=(True, False), temp=True)
    assert p.ejecutor() is True


def test_ejecutor_retorna_false_si_alguna_condicion_falla():
    p, alarm_mgr, set_do = _make_preparacion()
    _stub_condiciones(p, chaqueta=True, presion=(False, False), drenaje=(True, False), temp=True)
    assert p.ejecutor() is False


def test_ejecutor_evalua_las_4_condiciones_en_el_mismo_tick():
    # Antes (secuencial), drenar_camara/verificar_temperatura_drenaje ni se
    # llamaban si la chaqueta o la presion aun no estaban listas. Ahora deben
    # evaluarse siempre, sin importar el resultado de las demas.
    p, alarm_mgr, set_do = _make_preparacion()
    llamadas = []
    p.suministrar_vapor_chaqueta = lambda: (llamadas.append("chaqueta"), False)[1]
    p.igualar_presion_camara = lambda: (llamadas.append("presion"), (False, False))[1]
    p.drenar_camara = lambda: (llamadas.append("drenaje"), (True, False))[1]
    p.verificar_temperatura_drenaje = lambda: (llamadas.append("temp"), True)[1]

    p.ejecutor()

    assert set(llamadas) == {"chaqueta", "presion", "drenaje", "temp"}


def test_run_maneja_emergencia_sin_llamar_supervisor():
    p, alarm_mgr, set_do = _make_preparacion(paro_emergencia=1)

    def _supervisor_no_debe_llamarse():
        raise AssertionError("supervisor() no debe llamarse durante una emergencia")

    p.supervisor = _supervisor_no_debe_llamarse

    result = p.run()

    assert result is False
    set_do.reset_all_outputs.assert_called_once()
    set_do.buzer_emergencia.assert_called_once()


def test_preparacion_state_no_tiene_atributo_step():
    p, _, _ = _make_preparacion()
    assert not hasattr(p, "step")


def test_reset_no_falla_sin_step():
    p, _, _ = _make_preparacion()
    p.reset()  # no debe lanzar excepción
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_preparacion_ejecutor_paralelo.py -v`
Expected: FAIL en la mayoría — `ejecutor()` hoy es la cadena `if self.step ==`, no llama las 4 condiciones sin un `self.step` ya avanzado, no combina `descompresion_rapida` con OR, y `run()` hoy sí llama `supervisor()` primero (haría que `test_run_maneja_emergencia_sin_llamar_supervisor` falle con el `AssertionError` del stub). `test_preparacion_state_no_tiene_atributo_step` también falla porque `__init__` hoy fija `self.step = 0`.

- [ ] **Step 3: Implementar**

En `preparacion.py`, reemplazar `__init__` (líneas 19-26):

```python
class preparacion_state:
    def __init__(self, alarm_manager, estado, set_do, cycle, config):
        self.alarm_manager = alarm_manager
        self.estado = estado
        self.set_do = set_do
        self.cycle = cycle
        self.config = config
```

Reemplazar el bloque de comentario descriptivo (líneas 28-40) para que ya no describa una secuencia de pasos:

```python
    #definicion del estado preparacion:
    # Todas las condiciones se evalúan en paralelo, cada tick, sin bloquear
    # unas a otras (mismo patrón que preparado_state):
    # - verificar todas las señales de sensores
    # - verificar suministro de servicios (vapor, agua, aire comprimido)
    # - suministrar vapor a la chaqueta
    # - igualar la presión de cámara a la atmosférica si es necesario
    # - drenar la cámara si tiene agua residual
    # - enfriar el drenaje si su temperatura no es segura
    # PREPARACION termina cuando las 4 condiciones están OK en el mismo tick.
```

Reemplazar `run()` (líneas 60-67):

```python
    def run(self):
        if self.estado.sensores_di["paro_emergencia"]:
            self.set_do.reset_all_outputs()
            self.alarm("PARO_EMERGENCIA", AlarmType.EMERGENCIA)
            self.set_do.buzer_emergencia()
            return False
        else:
            self.set_do.buzer_off()
            self.alarm_manager.clear("PARO_EMERGENCIA")

        if not self.supervisor():
            return False

        return self.ejecutor()
```

Reemplazar `ejecutor()` (líneas 79-120, incluyendo el chequeo de emergencia que se movió a `run()`):

```python
    def ejecutor(self):
        logger.info("Ejecución del estado PREPARACION (paralelo)")

        chaqueta_lista = self.suministrar_vapor_chaqueta()
        presion_ok, quiere_rapida_presion = self.igualar_presion_camara()
        drenaje_ok, quiere_rapida_drenaje = self.drenar_camara()
        temp_ok = self.verificar_temperatura_drenaje()

        if quiere_rapida_presion or quiere_rapida_drenaje:
            self.set_do.descompresion_rapida_on()
        else:
            self.set_do.descompresion_rapida_off()

        return chaqueta_lista and presion_ok and drenaje_ok and temp_ok
```

Reemplazar `reset()` (líneas 288-289):

```python
    def reset(self):
        pass
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_preparacion_ejecutor_paralelo.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/preparacion.py tests/test_preparacion_ejecutor_paralelo.py
git commit -m "feat: PREPARACION ejecuta sus 4 condiciones en paralelo cada tick, sin self.step"
```

---

### Task 4: Actualizar `tests/test_preparacion_chaqueta.py` (dependía de `self.step`, ya eliminado)

**Files:**
- Modify: `tests/test_preparacion_chaqueta.py` (reemplazo completo)

**Interfaces:**
- Consumes: `suministrar_vapor_chaqueta() -> bool` (sin cambios), `ejecutor()` de Task 3, y el patrón de stub `_stub_condiciones`-style usado en Task 3 (no se importa, se re-declara localmente para mantener el archivo autocontenido, igual que hace `tests/test_preparado_chaqueta.py`).

- [ ] **Step 1: Confirmar que el archivo actual falla tras Task 3**

Run: `python -m pytest tests/test_preparacion_chaqueta.py -v`
Expected: FAIL — los 4 tests existentes asignan `p.step = 2` / `p.step = 4` y leen `p.step` después de `ejecutor()`, pero `preparacion_state` ya no tiene ese atributo (`AttributeError`).

- [ ] **Step 2: Reemplazar el archivo completo**

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.preparacion import preparacion_state


def _make_preparacion(vapor=1, presion_chaqueta=300.0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_di = {
        "paro_emergencia": 0,
        "vapor_suministro": vapor,
        "agua_bomba": 1, "agua_generador": 1, "aire_comprimido": 1,
        "agua_camara": 1,
    }
    estado.sensores_pres = {"pres_chaqueta": presion_chaqueta}
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda section, key: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
    }[key]
    config = MagicMock()
    p = preparacion_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_sin_vapor_retorna_true_sin_bloquear():
    p, alarm_mgr, set_do = _make_preparacion(vapor=0)
    assert p.suministrar_vapor_chaqueta() is True
    set_do.vapor_chaqueta_off.assert_called()


def test_sin_vapor_reporta_alarma_no_bloqueante():
    p, alarm_mgr, _ = _make_preparacion(vapor=0)
    p.suministrar_vapor_chaqueta()
    alarma = alarm_mgr.report.call_args.args[0]
    assert alarma.id == "SUMINISTRO_VAPOR"
    assert alarma.blocks_operation is False


def test_con_vapor_fuera_de_banda_retorna_false():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=100.0)
    assert p.suministrar_vapor_chaqueta() is False
    set_do.vapor_chaqueta_on.assert_called()


def test_vapor_vuelve_se_retoma_en_el_siguiente_tick():
    # Ya no hay step que "saltar": suministrar_vapor_chaqueta() se evalua
    # cada tick del ejecutor sin depender de las demas condiciones.
    p, alarm_mgr, set_do = _make_preparacion(vapor=0, presion_chaqueta=100.0)
    p.igualar_presion_camara = lambda: (True, False)
    p.drenar_camara = lambda: (True, False)
    p.verificar_temperatura_drenaje = lambda: True

    p.ejecutor()
    p.estado.sensores_di["vapor_suministro"] = 1
    p.ejecutor()

    set_do.vapor_chaqueta_on.assert_called()
```

- [ ] **Step 3: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_preparacion_chaqueta.py -v`
Expected: PASS (4 tests)

- [ ] **Step 4: Commit**

```bash
git add tests/test_preparacion_chaqueta.py
git commit -m "test: actualizar test_preparacion_chaqueta.py para el ejecutor paralelo sin self.step"
```

---

### Task 5: Verificación completa de la suite y de la spec

**Files:** ninguno (solo verificación)

**Interfaces:** ninguna nueva — confirma que todo lo de Tasks 1-4 convive correctamente con el resto del proyecto.

- [ ] **Step 1: Correr toda la suite de tests**

Run: `python -m pytest tests/ -q`
Expected: todos los tests pasan, incluyendo `tests/test_preparacion_suministro.py` y `tests/test_preparacion_alarm_wording.py` (no deberían haberse visto afectados, pero se confirma que no hay regresiones colaterales en `preparacion.py`).

- [ ] **Step 2: Revisar manualmente contra la spec**

Abrir `docs/superpowers/specs/2026-07-23-preparacion-paralela-design.md` y confirmar, leyendo el `preparacion.py` final:
- `self.step` ya no existe en ningún lado del archivo (`grep -n "self.step" src/autoclave/state_machine/states/preparacion.py` no debe devolver nada).
- `ejecutor()` llama las 4 condiciones sin condicionar una a la otra.
- `descompresion_rapida` se escribe una sola vez por tick, combinando `igualar_presion_camara` y `drenar_camara` con OR.
- El chequeo de `paro_emergencia` está al inicio de `run()`, antes de `supervisor()`.
- `verificar_sensores()`, `verificar_suministros()`, `suministrar_vapor_chaqueta()`, `verificar_temperatura_drenaje()` no cambiaron de contenido (mismo diff que Tasks 1-4 no debería tocarlos).

Run: `grep -n "self.step" src/autoclave/state_machine/states/preparacion.py`
Expected: sin resultados (exit code 1 de grep = "no matches").

- [ ] **Step 3: No requiere commit** (paso de verificación únicamente; si algo falla, volver a la task correspondiente y corregir ahí).

---

## Self-Review Notes

- **Cobertura de la spec:** estructura general (Task 3) ✓; conflicto de válvula resuelto por OR (Tasks 1, 2, 3) ✓; chequeo de emergencia movido (Task 3) ✓; eliminación de `self.step`/placeholders/reset (Task 3) ✓; funciones sin cambios explícitamente no tocadas (Tasks 1-4 no las modifican) ✓; tests nuevos y actualización de tests existentes (Tasks 1, 2, 3, 4) ✓.
- **Placeholders:** ninguno — cada step tiene código completo y comandos exactos.
- **Consistencia de tipos:** `igualar_presion_camara()` y `drenar_camara()` retornan `tuple[bool, bool]` de forma consistente entre Tasks 1, 2 y su consumo en Task 3; `ejecutor()`/`run()` mantienen `-> bool` en todas las tasks que las referencian.

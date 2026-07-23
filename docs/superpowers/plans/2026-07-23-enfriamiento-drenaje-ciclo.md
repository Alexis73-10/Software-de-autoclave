# Enfriamiento de drenaje no bloqueante durante CICLO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Durante `CICLO`, vigilar `temp_drenaje` continuamente y gestionar `agua_intercambiador` en consecuencia, sin bloquear el flujo del ciclo — mismo patrón que ya existe para la chaqueta (`_mantener_chaqueta`).

**Architecture:** Se elimina la duplicación de control de `agua_intercambiador` dentro de `PrevacioFase` (ya cubierta por `vacio_camara_on/off` en `set_io.py`), y se agrega `CicloState._mantener_drenaje()`, invocado en cada tick de `CICLO` sin excluir ninguna fase, con una alarma informativa no bloqueante.

**Tech Stack:** Python 3.14, pytest, `unittest.mock.MagicMock`.

## Global Constraints

- `agua_intercambiador` debe seguir acoplado a la bomba de vacío (`vacio_camara_on()`/`vacio_camara_off()` en `set_io.py`) en TODAS las fases que la usan (`PrevacioFase`, `SecadoFase`) — este acople NO se toca, confirmado por el usuario (ayuda a enfriar el fluido que entra a la bomba de vacío).
- `_mantener_drenaje()` se llama en cada tick de `CICLO`, **sin excluir ninguna fase** (a diferencia de `_mantener_chaqueta`, que excluye `SecadoFase`) — incluye explícitamente `PRE_VACIO`.
- Alarma: `alarm_id="TEMP_DRENAJE_ALTA"`, `alarm_type=AlarmType.ALERTA`, `source_state="CICLO"`, `blocks_operation=False`, `recoverable=True`. Se reporta cuando `temp_drenaje > temp_segura_drenaje`, se limpia (`alarm_manager.clear("TEMP_DRENAJE_ALTA")`) cuando vuelve a rango seguro.
- No bloqueante: el resultado del ciclo y el avance de fases nunca dependen de `_mantener_drenaje()`.
- Spec completa: `docs/superpowers/specs/2026-07-23-enfriamiento-drenaje-ciclo-design.md`.

---

### Task 1: Enfriamiento de drenaje en CicloState + limpieza en PrevacioFase

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/prevacio.py`
- Modify: `src/autoclave/state_machine/states/ciclo.py`
- Test: `tests/test_ciclo_drenaje.py` (crear)
- Test: `tests/test_prevacio_caps.py` (solo correr, no modificar)

**Interfaces:**
- Produces: `CicloState._mantener_drenaje() -> None` — nuevo método, llamado desde `run()` junto a `_mantener_chaqueta()`.
- No cambia ninguna firma pública existente.

- [ ] **Step 1: Escribir los tests de `_mantener_drenaje()` (fallarán porque el método no existe)**

Crear `tests/test_ciclo_drenaje.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState


def _make_ciclo(temp_drenaje=25.0, temp_segura=40.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_drenaje": temp_drenaje}
    estado.sensores_pres = {}
    estado.get_flag.return_value = False
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = temp_segura
    alarm_manager = MagicMock()
    ciclo = CicloState(estado, set_do, cycle, config, alarm_manager)
    return ciclo, set_do, alarm_manager, estado


def test_temp_alta_enciende_agua_y_reporta_alarma_no_bloqueante():
    ciclo, set_do, alarm_manager, _ = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_on.assert_called_once()
    alarma = alarm_manager.report.call_args.args[0]
    assert alarma.id == "TEMP_DRENAJE_ALTA"
    assert alarma.blocks_operation is False


def test_temp_segura_apaga_agua_y_limpia_alarma():
    ciclo, set_do, alarm_manager, _ = _make_ciclo(temp_drenaje=30.0, temp_segura=40.0)
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_off.assert_called_once()
    alarm_manager.clear.assert_any_call("TEMP_DRENAJE_ALTA")


def test_temp_drenaje_ausente_no_hace_nada():
    ciclo, set_do, alarm_manager, estado = _make_ciclo(temp_segura=40.0)
    estado.sensores_temp = {}
    ciclo._mantener_drenaje()
    set_do.agua_intercambiador_on.assert_not_called()
    set_do.agua_intercambiador_off.assert_not_called()
    alarm_manager.report.assert_not_called()
    alarm_manager.clear.assert_not_called()


def test_se_llama_en_run_sin_importar_la_fase_activa():
    ciclo, set_do, alarm_manager, estado = _make_ciclo(temp_drenaje=45.0, temp_segura=40.0)
    # temp_camara es sensor crítico (CicloState._SENSORES_TEMP_CRITICOS) y
    # debe estar presente o run() aborta el ciclo en el paso 4, antes de
    # llegar al paso 5 (_mantener_drenaje).
    estado.sensores_temp["temp_camara"] = 100.0
    estado.sensores_pres = {"pres_camara": 101.3, "pres_chaqueta": 300.0,
                             "pres_empaque_1": 300.0, "pres_empaque_2": 300.0}
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                           "vapor_suministro": 1}
    # cap.has_vacuum=False para que PrevacioFase.update() (paso 7, corre
    # DESPUÉS de _mantener_drenaje) se salte sin tocar más sensores/salidas.
    ciclo.cap = MagicMock()
    ciclo.cap.has_vacuum = False
    for fase in ciclo._fases:
        fase.cap = ciclo.cap
    # PrevacioFase está en índice 2 del pipeline (PRECALENTAMIENTO, PURGA, PRE_VACIO, ...)
    ciclo.reset()
    ciclo._fase_idx = 2
    ciclo.run()
    set_do.agua_intercambiador_on.assert_called()
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_ciclo_drenaje.py -v`
Expected: FAIL — `AttributeError: 'CicloState' object has no attribute '_mantener_drenaje'` (los primeros 3 tests); el 4to test puede fallar por la misma razón o por comportamiento distinto al esperado.

- [ ] **Step 3: Quitar las llamadas redundantes a `agua_intercambiador` en `prevacio.py`**

En `src/autoclave/state_machine/cycle_phases/prevacio.py`:

Dentro del paso `VACIO_BAJO` (bloque `if self._paso == _PASO_VACIO_BAJO:`), quitar la línea `self.set_do.agua_intercambiador_on()` que precede a `self.set_do.bomba_vacio_on()`. El bloque queda:

```python
            presion_baja = self.cycle.get_param("prevacio", f"presion_baja_pulso_{tipo}") or 15
            self.set_do.bomba_vacio_on()
            self.set_do.vacio_camara_on()
```

Dentro del paso `HOLD_BAJO` (bloque `if self._paso == _PASO_HOLD_BAJO:`), quitar la misma línea. El bloque queda:

```python
            tiempo_hold = self.cycle.get_param("prevacio", f"tiempo_adicional_bajo_{tipo}") or 0
            self.set_do.bomba_vacio_on()
            self.set_do.vacio_camara_on()
```

En `_apagar_vacio()`, quitar `self.set_do.agua_intercambiador_off()`. El método queda:

```python
    def _apagar_vacio(self):
        self.set_do.bomba_vacio_off()
        self.set_do.vacio_camara_off()
```

`vacio_camara_on()`/`vacio_camara_off()` (en `set_io.py`, sin cambios) siguen activando/desactivando `agua_intercambiador` internamente — este paso no cambia ningún comportamiento observable, solo quita la duplicación.

- [ ] **Step 4: Implementar `_mantener_drenaje()` en `ciclo.py`**

En `src/autoclave/state_machine/states/ciclo.py`, agregar el método nuevo inmediatamente después de `_mantener_chaqueta()` (antes de `_mantener_valvula_reposo()`):

```python
    def _mantener_drenaje(self):
        """Mantiene la temperatura de drenaje durante todas las fases del
        ciclo, sin bloquear el flujo del ciclo (alarma informativa)."""
        temp = self.estado.sensores_temp.get("temp_drenaje")
        if temp is None:
            return
        temp_segura = self.config.get("temp_segura_drenaje")
        if temp_segura is None:
            return

        if temp > temp_segura:
            self.set_do.agua_intercambiador_on()
            self.alarm_manager.report(Alarm(
                alarm_id="TEMP_DRENAJE_ALTA",
                alarm_type=AlarmType.ALERTA,
                source_state="CICLO",
                description="Temperatura de drenaje alta: enfriando.",
                recoverable=True,
                blocks_operation=False,
            ))
        else:
            self.set_do.agua_intercambiador_off()
            self.alarm_manager.clear("TEMP_DRENAJE_ALTA")
```

En `run()`, reemplazar:

```python
        # ── 5. Mantener presión de chaqueta ───────────────────────────
        self._mantener_chaqueta()
```

por:

```python
        # ── 5. Mantener presión de chaqueta y temperatura de drenaje ──
        self._mantener_chaqueta()
        self._mantener_drenaje()
```

- [ ] **Step 5: Verificar que los tests nuevos pasan**

Run: `python -m pytest tests/test_ciclo_drenaje.py -v`
Expected: 4 passed

- [ ] **Step 6: Correr `test_prevacio_caps.py` (no modificado, verificación de no-regresión)**

Run: `python -m pytest tests/test_prevacio_caps.py -v`
Expected: 3 passed (ninguno de esos tests llega a `VACIO_BAJO`/`HOLD_BAJO`/`_apagar_vacio`, así que no deberían verse afectados)

- [ ] **Step 7: Correr la suite completa de `tests/test_ciclo_*.py` (verificación de no-regresión de `run()`)**

Run: `python -m pytest tests/test_ciclo_sensores.py tests/test_ciclo_suministro.py tests/test_ciclo_desconexion.py tests/test_ciclo_chaqueta.py tests/test_ciclo_valvula_reposo.py -v`
Expected: todos passed

- [ ] **Step 8: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/prevacio.py src/autoclave/state_machine/states/ciclo.py tests/test_ciclo_drenaje.py
git commit -m "feat: enfriamiento de drenaje no bloqueante durante el ciclo"
```

---

### Task 2: Verificación final de la suite completa

**Files:**
- (sin cambios de código — sólo verificación)

- [ ] **Step 1: Correr toda la suite de tests**

Run: `python -m pytest tests/ -v`
Expected: todos passed, salvo las fallas preexistentes ya conocidas y no relacionadas en `tests/test_io_views.py` (ModuleNotFoundError).

- [ ] **Step 2: Si algo falla, diagnosticar antes de tocar código de producción**

Si una prueba preexistente falla, confirmar si es una regresión real de este cambio o algo fuera de alcance, contra `docs/superpowers/specs/2026-07-23-enfriamiento-drenaje-ciclo-design.md`. No usar `--no-verify` ni saltarse fallas.

- [ ] **Step 3: Commit final si hubo ajustes**

```bash
git add -A
git commit -m "test: verificacion final de la suite tras enfriamiento de drenaje"
```

(Omitir este paso si el Step 1 ya pasó limpio y no hubo cambios adicionales.)

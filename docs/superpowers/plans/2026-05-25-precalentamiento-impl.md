# Precalentamiento Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar la lógica de `PrecalentamientoFase` para calentar la chaqueta (`vapor_chaqueta`) hasta `presion_precalentamiento` y sostenerla por `tiempo_precalentamiento` con control bang-bang durante el sostenimiento.

**Architecture:** La fase hereda de `BaseFase` e implementa `update()` / `reset()`. Usa el sensor `pres_chaqueta` (disponible en `estado.sensores_pres`) y la salida `vapor_chaqueta` (disponible en `set_do`). El control durante el sostenimiento es bang-bang: válvula abre si presión cae, cierra si presión está en objetivo; el timer de sostenimiento nunca se reinicia.

**Tech Stack:** Python 3.14, pytest, `unittest.mock.MagicMock`

---

## Archivos afectados

| Archivo | Acción |
|---------|--------|
| `src/autoclave/state_machine/cycle_phases/precalentamiento.py` | Modificar — reemplazar lógica completa |
| `tests/test_precalentamiento_fase.py` | Crear — tests unitarios de la fase |

Los JSONs de ciclo (`bowe_dick.json`, `instrumental_134.json`) ya tienen los parámetros correctos (`presion_precalentamiento`, `tiempo_precalentamiento`, `timeout_precalentamiento`) — no requieren cambios.

---

## Task 1: Tests de PrecalentamientoFase

**Files:**
- Create: `tests/test_precalentamiento_fase.py`

### Contexto de los helpers de test

`PrecalentamientoFase` se construye con:
```python
PrecalentamientoFase(estado, set_do, cycle, config, alarm_manager)
```
- `cycle.get_param("precalentamiento", "tiempo_precalentamiento")` → float minutos → la fase multiplica por 60 para obtener segundos
- `cycle.get_param("precalentamiento", "presion_precalentamiento")` → float kPa
- `cycle.get_param("precalentamiento", "timeout_precalentamiento")` → float minutos → la fase multiplica por 60
- `estado.sensores_pres["pres_chaqueta"]` → float kPa (leído via `BaseFase._pres_chaqueta()` — ver nota abajo)
- `estado.fase_en_sostenimiento` → bool, escrito por la fase

> **Nota:** `BaseFase` tiene `_temp_camara()` y `_pres_camara()`. La nueva fase añade `_pres_chaqueta()`. Si en la implementación (Task 2) eliges leer `estado.sensores_pres.get("pres_chaqueta")` directamente en `update()` en lugar de un helper, ajusta el setup de los mocks.

- [ ] **Step 1: Crear `tests/test_precalentamiento_fase.py` con los tests en rojo**

```python
# tests/test_precalentamiento_fase.py
import time
from unittest.mock import MagicMock, patch
import pytest

from autoclave.state_machine.cycle_phases.precalentamiento import PrecalentamientoFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(tiempo_min=5, presion_obj=200.0, timeout_min=10):
    """Construye una PrecalentamientoFase con mocks configurados."""
    estado = MagicMock()
    estado.sensores_pres = {"pres_chaqueta": 0.0}
    estado.fase_en_sostenimiento = False

    set_do = MagicMock()

    cycle = MagicMock()
    def get_param(seccion, param, default=None):
        valores = {
            "tiempo_precalentamiento": tiempo_min,
            "presion_precalentamiento": presion_obj,
            "timeout_precalentamiento": timeout_min,
        }
        return valores.get(param, default)
    cycle.get_param.side_effect = get_param

    config  = MagicMock()
    alarms  = MagicMock()

    fase = PrecalentamientoFase(estado, set_do, cycle, config, alarms)
    fase.reset()
    return fase, estado, set_do


# ──────────────────────────────────────────────────────────────────────────────
# 1. Skip cuando tiempo == 0
# ──────────────────────────────────────────────────────────────────────────────

def test_skip_cuando_tiempo_es_cero():
    fase, estado, set_do = _make_fase(tiempo_min=0)
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_chaqueta_on.assert_not_called()
    set_do.vapor_chaqueta_off.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Aproximación: presión bajo objetivo → EN_CURSO, válvula abierta
# ──────────────────────────────────────────────────────────────────────────────

def test_aproximacion_valvula_on_y_en_curso():
    fase, estado, set_do = _make_fase(tiempo_min=1, presion_obj=200.0)
    estado.sensores_pres["pres_chaqueta"] = 100.0   # bajo objetivo
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_chaqueta_on.assert_called()
    set_do.vapor_chaqueta_off.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Al alcanzar la presión objetivo arranca el sostenimiento
# ──────────────────────────────────────────────────────────────────────────────

def test_sostenimiento_arranca_al_alcanzar_presion():
    fase, estado, set_do = _make_fase(tiempo_min=1, presion_obj=200.0)
    estado.sensores_pres["pres_chaqueta"] = 200.0   # igual al objetivo
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    assert estado.fase_en_sostenimiento == True


# ──────────────────────────────────────────────────────────────────────────────
# 4. Sostenimiento completo → COMPLETADO y válvula apagada
# ──────────────────────────────────────────────────────────────────────────────

def test_completado_tras_sostenimiento():
    fase, estado, set_do = _make_fase(tiempo_min=1, presion_obj=200.0)
    estado.sensores_pres["pres_chaqueta"] = 250.0   # por encima del objetivo

    # Primer update: alcanza presión, arranca timer
    fase.update()

    # Avanzar el timer de sostenimiento al pasado para simular tiempo cumplido
    fase._timer_sostenimiento -= 70   # 70 s > 1 min = 60 s

    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_chaqueta_off.assert_called()
    assert estado.fase_en_sostenimiento == False


# ──────────────────────────────────────────────────────────────────────────────
# 5. Timeout sin alcanzar presión → FALLO y válvula apagada
# ──────────────────────────────────────────────────────────────────────────────

def test_fallo_por_timeout():
    fase, estado, set_do = _make_fase(tiempo_min=1, presion_obj=200.0, timeout_min=1)
    estado.sensores_pres["pres_chaqueta"] = 50.0    # nunca llega al objetivo

    # Inicializar la fase
    fase.update()

    # Forzar expiración del timeout
    fase._timer_timeout_fin -= 100

    result = fase.update()
    assert result == FaseResult.FALLO
    set_do.vapor_chaqueta_off.assert_called()


# ──────────────────────────────────────────────────────────────────────────────
# 6. Durante sostenimiento: presión cae → válvula abre; timer no se reinicia
# ──────────────────────────────────────────────────────────────────────────────

def test_bang_bang_durante_sostenimiento():
    fase, estado, set_do = _make_fase(tiempo_min=5, presion_obj=200.0)

    # Llegar al sostenimiento
    estado.sensores_pres["pres_chaqueta"] = 210.0
    fase.update()
    assert estado.fase_en_sostenimiento == True
    timer_original = fase._timer_sostenimiento

    # Presión cae: debe abrir válvula, timer no cambia
    set_do.reset_mock()
    estado.sensores_pres["pres_chaqueta"] = 150.0
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_chaqueta_on.assert_called()
    assert fase._timer_sostenimiento == timer_original   # timer no se reinició


# ──────────────────────────────────────────────────────────────────────────────
# 7. Durante sostenimiento: presión OK → válvula cierra
# ──────────────────────────────────────────────────────────────────────────────

def test_valvula_cierra_cuando_presion_ok_en_sostenimiento():
    fase, estado, set_do = _make_fase(tiempo_min=5, presion_obj=200.0)

    estado.sensores_pres["pres_chaqueta"] = 210.0
    fase.update()   # entra en sostenimiento

    set_do.reset_mock()
    estado.sensores_pres["pres_chaqueta"] = 205.0   # sigue por encima del objetivo
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_chaqueta_off.assert_called()
    set_do.vapor_chaqueta_on.assert_not_called()
```

- [ ] **Step 2: Verificar que los tests fallan (fase aún no implementada)**

```
pytest tests/test_precalentamiento_fase.py -v
```

Resultado esperado: múltiples `FAILED` o `ERROR` — la fase actual usa `vapor_camara` y lógica de temperatura, no de presión de chaqueta. Tests 2 y 3 en particular deben fallar porque la implementación actual no toca `vapor_chaqueta`.

---

## Task 2: Implementar nueva PrecalentamientoFase

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/precalentamiento.py`

- [ ] **Step 1: Reemplazar el contenido del archivo**

Reemplaza **todo** el contenido de `precalentamiento.py` con:

```python
# state_machine/cycle_phases/precalentamiento.py
#
# FASE 1 — PRECALENTAMIENTO
#
# Calienta la chaqueta con vapor hasta alcanzar presion_precalentamiento,
# luego sostiene esa presión durante tiempo_precalentamiento.
# Control bang-bang durante sostenimiento: válvula abre si presión cae,
# cierra si presión está en objetivo; el timer de sostenimiento no se reinicia.
#
# Parámetros del ciclo (sección "precalentamiento"):
#   presion_precalentamiento  [kPa]  → presión objetivo de la chaqueta
#   tiempo_precalentamiento   [min]  → si == 0, fase saltada; duración del sostenimiento
#   timeout_precalentamiento  [min]  → timeout global; si expira antes → FALLO

import time
import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class PrecalentamientoFase(BaseFase):

    name = "PRECALENTAMIENTO"

    def reset(self):
        self._inicializado        = False
        self._timer_timeout_fin   = None
        self._timer_sostenimiento = None
        self.estado.fase_en_sostenimiento = False

    def _pres_chaqueta(self):
        return self.estado.sensores_pres.get("pres_chaqueta")

    def update(self) -> FaseResult:

        # ── 1. Parámetros ────────────────────────────────────────────────────
        tiempo_seg  = (self.cycle.get_param("precalentamiento", "tiempo_precalentamiento")  or 0) * 60
        presion_obj =  self.cycle.get_param("precalentamiento", "presion_precalentamiento") or 0
        timeout_seg = (self.cycle.get_param("precalentamiento", "timeout_precalentamiento") or 10) * 60

        # ── 2. Skip ──────────────────────────────────────────────────────────
        if tiempo_seg == 0:
            logger.info("Precalentamiento: tiempo=0, fase saltada")
            return FaseResult.COMPLETADO

        # ── 3. Inicialización ────────────────────────────────────────────────
        if not self._inicializado:
            self._timer_timeout_fin = time.time() + timeout_seg
            self._inicializado = True
            logger.info(
                "Precalentamiento: iniciando | obj %.1f kPa | sostenimiento %.0fs | timeout %.0fs",
                presion_obj, tiempo_seg, timeout_seg
            )

        # ── 4. Timeout global ────────────────────────────────────────────────
        if time.time() > self._timer_timeout_fin:
            logger.error(
                "Precalentamiento: TIMEOUT — no se alcanzó %.1f kPa en %.0f min",
                presion_obj, timeout_seg / 60
            )
            self.set_do.vapor_chaqueta_off()
            self.estado.fase_en_sostenimiento = False
            return FaseResult.FALLO

        # ── 5. Leer sensor ───────────────────────────────────────────────────
        pres = self._pres_chaqueta()
        if pres is None:
            logger.debug("Precalentamiento: pres_chaqueta no disponible, esperando...")
            return FaseResult.EN_CURSO

        # ── 6. Aproximación (aún no alcanzó objetivo) ────────────────────────
        if self._timer_sostenimiento is None:
            self.set_do.vapor_chaqueta_on()
            if pres >= presion_obj:
                self._timer_sostenimiento = time.time()
                self.estado.fase_en_sostenimiento = True
                logger.info(
                    "Precalentamiento: %.1f kPa alcanzados — sosteniendo %.0fs",
                    pres, tiempo_seg
                )
            return FaseResult.EN_CURSO

        # ── 7. Sostenimiento (bang-bang, timer no se reinicia) ───────────────
        if pres >= presion_obj:
            self.set_do.vapor_chaqueta_off()
        else:
            self.set_do.vapor_chaqueta_on()

        transcurrido = time.time() - self._timer_sostenimiento
        logger.debug(
            "Precalentamiento: sosteniendo %.1fs / %.1fs | %.1f kPa",
            transcurrido, tiempo_seg, pres
        )

        if transcurrido >= tiempo_seg:
            logger.info("Precalentamiento: COMPLETADO")
            self.set_do.vapor_chaqueta_off()
            self.estado.fase_en_sostenimiento = False
            return FaseResult.COMPLETADO

        return FaseResult.EN_CURSO
```

- [ ] **Step 2: Correr los tests y verificar que pasan**

```
pytest tests/test_precalentamiento_fase.py -v
```

Resultado esperado:
```
PASSED test_skip_cuando_tiempo_es_cero
PASSED test_aproximacion_valvula_on_y_en_curso
PASSED test_sostenimiento_arranca_al_alcanzar_presion
PASSED test_completado_tras_sostenimiento
PASSED test_fallo_por_timeout
PASSED test_bang_bang_durante_sostenimiento
PASSED test_valvula_cierra_cuando_presion_ok_en_sostenimiento

7 passed
```

- [ ] **Step 3: Correr toda la suite (excluyendo test_config.py que tiene un import roto pre-existente)**

```
pytest tests/ --ignore=tests/test_config.py -q
```

Resultado esperado: todos los tests pasan, sin regresiones.

- [ ] **Step 4: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/precalentamiento.py tests/test_precalentamiento_fase.py
git commit -m "feat: precalentamiento calienta chaqueta con control bang-bang"
```

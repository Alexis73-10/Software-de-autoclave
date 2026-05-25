# Purga Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar `PurgaFase` para abrir `vapor_camara` y `descompresion_rapida` simultáneamente durante `tiempo_purga` minutos, eliminando el aire seco de la cámara antes del prevacío.

**Architecture:** La fase hereda de `BaseFase` e implementa `update()` / `reset()`. No monitorea sensores — es puramente temporal. Abre ambas válvulas en el primer `update()` y las cierra al cumplirse el tiempo. No existe resultado FALLO.

**Tech Stack:** Python 3.14, pytest, `unittest.mock.MagicMock`

---

## Archivos afectados

| Archivo | Acción |
|---------|--------|
| `src/autoclave/state_machine/cycle_phases/purga.py` | Modificar — reemplazar lógica completa |
| `tests/test_purga_fase.py` | Crear — tests unitarios de la fase |
| `src/autoclave/cycles/factory/instrumental_134.json` | Modificar — eliminar `timeout_purga` |
| `src/autoclave/cycles/factory/bowe_dick.json` | Modificar — eliminar `timeout_purga` |

---

## Task 1: Tests de PurgaFase

**Files:**
- Create: `tests/test_purga_fase.py`

### Contexto de los helpers de test

`PurgaFase` se construye con:
```python
PurgaFase(estado, set_do, cycle, config, alarm_manager)
```
- `cycle.get_param("purga", "tiempo_purga")` → float minutos → la fase multiplica por 60
- No se usan sensores de `estado` (la fase no lee ningún sensor)
- `set_do.vapor_camara_on()` / `vapor_camara_off()` — válvula de vapor a cámara
- `set_do.descompresion_rapida_on()` / `descompresion_rapida_off()` — válvula de descompresión

- [ ] **Step 1: Crear `tests/test_purga_fase.py` con los tests en rojo**

```python
# tests/test_purga_fase.py
import time
from unittest.mock import MagicMock
import pytest

from autoclave.state_machine.cycle_phases.purga import PurgaFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(tiempo_min=5):
    """Construye una PurgaFase con mocks configurados."""
    estado = MagicMock()
    set_do = MagicMock()

    cycle = MagicMock()
    def get_param(seccion, param, default=None):
        return {"tiempo_purga": tiempo_min}.get(param, default)
    cycle.get_param.side_effect = get_param

    config = MagicMock()
    alarms = MagicMock()

    fase = PurgaFase(estado, set_do, cycle, config, alarms)
    fase.reset()
    return fase, estado, set_do


# ──────────────────────────────────────────────────────────────────────────────
# 1. Skip cuando tiempo == 0
# ──────────────────────────────────────────────────────────────────────────────

def test_skip_cuando_tiempo_es_cero():
    fase, _, set_do = _make_fase(tiempo_min=0)
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_on.assert_not_called()
    set_do.descompresion_rapida_on.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Primer update: abre ambas válvulas y retorna EN_CURSO
# ──────────────────────────────────────────────────────────────────────────────

def test_abre_ambas_valvulas_en_primer_update():
    fase, _, set_do = _make_fase(tiempo_min=5)
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Updates sucesivos: no reabre válvulas mientras el tiempo no se cumple
# ──────────────────────────────────────────────────────────────────────────────

def test_en_curso_y_no_reabre_valvulas():
    fase, _, set_do = _make_fase(tiempo_min=5)
    fase.update()         # inicializa, abre válvulas
    set_do.reset_mock()   # limpia contadores
    result = fase.update()
    assert result == FaseResult.EN_CURSO
    set_do.vapor_camara_on.assert_not_called()
    set_do.descompresion_rapida_on.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 4. Tiempo cumplido → COMPLETADO y ambas válvulas cerradas
# ──────────────────────────────────────────────────────────────────────────────

def test_completado_tras_tiempo_cumplido():
    fase, _, set_do = _make_fase(tiempo_min=1)   # 60 s
    fase.update()                                 # inicializa timer
    fase._timer_fin -= 70                         # 70 s > 60 s → expirado
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.vapor_camara_off.assert_called()
    set_do.descompresion_rapida_off.assert_called()
```

- [ ] **Step 2: Verificar que los tests fallan (stub actual no tiene lógica)**

```
pytest tests/test_purga_fase.py -v
```

Resultado esperado: tests 2, 3 y 4 deben fallar — el stub actual retorna `COMPLETADO` de inmediato sin tocar válvulas ni timers.

---

## Task 2: Implementar nueva PurgaFase

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/purga.py`

- [ ] **Step 1: Reemplazar el contenido del archivo**

Reemplaza **todo** el contenido de `purga.py` con:

```python
# state_machine/cycle_phases/purga.py
#
# FASE 2 — PURGA
#
# Abre vapor_camara y descompresion_rapida simultáneamente durante
# tiempo_purga para crear un flujo de vapor que desplaza el aire
# seco de la cámara antes del prevacío.
#
# Parámetros del ciclo (sección "purga"):
#   tiempo_purga  [min]  → si == 0, fase saltada; duración del flujo
#   presion_purga [kPa]  → presente en JSON, no usado en esta fase

import time
import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class PurgaFase(BaseFase):

    name = "PURGA"

    def reset(self):
        self._inicializado = False
        self._timer_fin    = None

    def update(self) -> FaseResult:

        # ── 1. Parámetros ────────────────────────────────────────────────────
        tiempo_seg = (self.cycle.get_param("purga", "tiempo_purga") or 0) * 60

        # ── 2. Skip ──────────────────────────────────────────────────────────
        if tiempo_seg == 0:
            logger.info("Purga: tiempo=0, fase saltada")
            return FaseResult.COMPLETADO

        # ── 3. Inicialización (solo en el primer update) ─────────────────────
        if not self._inicializado:
            self.set_do.vapor_camara_on()
            self.set_do.descompresion_rapida_on()
            self._timer_fin = time.time() + tiempo_seg
            self._inicializado = True
            logger.info("Purga: iniciando | %.0f s", tiempo_seg)

        # ── 4. Verificar tiempo ───────────────────────────────────────────────
        if time.time() >= self._timer_fin:
            logger.info("Purga: COMPLETADO")
            self.set_do.vapor_camara_off()
            self.set_do.descompresion_rapida_off()
            return FaseResult.COMPLETADO

        return FaseResult.EN_CURSO
```

- [ ] **Step 2: Correr los tests de purga y verificar que pasan**

```
pytest tests/test_purga_fase.py -v
```

Resultado esperado:
```
PASSED test_skip_cuando_tiempo_es_cero
PASSED test_abre_ambas_valvulas_en_primer_update
PASSED test_en_curso_y_no_reabre_valvulas
PASSED test_completado_tras_tiempo_cumplido

4 passed
```

- [ ] **Step 3: Correr toda la suite (excluyendo test_config.py que tiene un import roto pre-existente)**

```
pytest tests/ --ignore=tests/test_config.py -q
```

Resultado esperado: todos los tests pasan, sin regresiones.

- [ ] **Step 4: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/purga.py tests/test_purga_fase.py
git commit -m "feat: purga abre vapor_camara y descompresion_rapida durante tiempo_purga"
```

---

## Task 3: Limpiar JSONs (eliminar timeout_purga)

**Files:**
- Modify: `src/autoclave/cycles/factory/instrumental_134.json`
- Modify: `src/autoclave/cycles/factory/bowe_dick.json`

- [ ] **Step 1: Editar `instrumental_134.json` — sección `"purga"`**

Reemplazar la sección `"purga"` actual:
```json
"purga": {
    "tiempo_purga": { "value": 0, "type":"int", "unit": "min", "min": 0, "max": 3600 },
    "presion_purga": { "value": 300,"type":"int", "unit": "kPa", "min": 0, "max": 1000 },
    "timeout_purga": { "value": 10, "type":"int", "unit": "min", "min": 0, "max": 3600 }
},
```

Con:
```json
"purga": {
    "tiempo_purga": { "value": 0, "type":"int", "unit": "min", "min": 0, "max": 3600 },
    "presion_purga": { "value": 300, "type":"int", "unit": "kPa", "min": 0, "max": 1000 }
},
```

- [ ] **Step 2: Editar `bowe_dick.json` — sección `"purga"`**

Reemplazar la sección `"purga"` actual:
```json
"purga": {
    "tiempo_purga": { "value": 0, "type":"int", "unit": "min", "min": 0, "max": 3600 },
    "presion_purga": { "value": 300,"type":"int", "unit": "kPa", "min": 0, "max": 1000 },
    "timeout_purga": { "value": 10, "type":"int", "unit": "min", "min": 0, "max": 3600 }
},
```

Con:
```json
"purga": {
    "tiempo_purga": { "value": 0, "type":"int", "unit": "min", "min": 0, "max": 3600 },
    "presion_purga": { "value": 300, "type":"int", "unit": "kPa", "min": 0, "max": 1000 }
},
```

- [ ] **Step 3: Commit**

```bash
git add src/autoclave/cycles/factory/instrumental_134.json src/autoclave/cycles/factory/bowe_dick.json
git commit -m "chore: eliminar timeout_purga de JSONs de ciclo (parámetro no usado)"
```

# Fase SECADO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar `SecadoFase` al pipeline del ciclo con 3 modos (vacío, vacío+aire, pulsado vacío/aire), cada uno manteniendo la chaqueta a una presión propia del secado.

**Architecture:** `SecadoFase(BaseFase)` con sub-estado explícito para modo 3 (VACIO_BAJO / AIRE_ALTO), insertada entre `EsterilizacionFase` y `DescompresionFase`. `CicloState._mantener_chaqueta()` se suprime durante SECADO para que la fase controle la chaqueta de forma independiente. Los parámetros se unifican en una sección `"secado"` en el JSON de cada ciclo.

**Tech Stack:** Python 3.14, `unittest.mock`, pytest, FastAPI (backend), PySide6 + qfluentwidgets (UI).

## Global Constraints

- Patrón de fase: heredar `BaseFase`, implementar `reset()` y `update() → FaseResult`.
- `get_param(seccion, clave)` del `Cycle` navega `parameters[seccion][clave]["value"]`.
- Las salidas se activan llamando a métodos de `self.set_do` (ver `src/autoclave/devices/io/set_io.py`).
- `cap.has_vacuum` (bool) indica si el equipo tiene bomba de vacío; sin vacío la fase retorna COMPLETADO inmediato.
- Skip también si `tiempo_secado == 0`.
- Archivos JSON de ciclos: cuatro en total — `cycles/factory/instrumental_134.json`, `cycles/factory/bowe_dick.json`, `cycles/user/instrumental_134.json`, `cycles/user/bowe_dick.json`.
- Sección `"secado"` en bowe_dick ya existe (con `tiempo_secado` y `tipo_secado` obsoleto); en instrumental_134 los parámetros están en `"esterilizacion"` y deben moverse.
- No modificar `cycles/factory/*` con valores distintos a los especificados; los archivos `user` son copias con los mismos valores por defecto.

---

## File Map

| Archivo | Acción |
|---|---|
| `src/autoclave/state_machine/cycle_phases/secado.py` | Crear — `SecadoFase` |
| `src/autoclave/state_machine/states/ciclo.py` | Modificar — import, pipeline, suprimir chaqueta |
| `src/autoclave/cycles/factory/instrumental_134.json` | Modificar — mover params a sección `"secado"` |
| `src/autoclave/cycles/factory/bowe_dick.json` | Modificar — actualizar sección `"secado"` |
| `src/autoclave/cycles/user/instrumental_134.json` | Modificar — igual que factory |
| `src/autoclave/cycles/user/bowe_dick.json` | Modificar — igual que factory |
| `src/autoclave/backend/server.py` | Modificar — endpoint PATCH para sección `"secado"` |
| `src/autoclave/ui_pyside/views/secado.py` | Modificar — leer/guardar todos los params secado |
| `tests/test_secado_fase.py` | Crear — tests unitarios de `SecadoFase` |
| `tests/test_patch_cycle_parameters.py` | Modificar — actualizar datos de prueba |

---

## Task 1: SecadoFase — implementación + tests (TDD)

**Files:**
- Create: `src/autoclave/state_machine/cycle_phases/secado.py`
- Create: `tests/test_secado_fase.py`

**Interfaces:**
- Produces: `SecadoFase(estado, set_do, cycle, config, alarm_manager, cap)` con `name = "SECADO"`, `reset()`, `update() → FaseResult`.
- Produces: constantes `_PASO_VACIO_BAJO = "VACIO_BAJO"` y `_PASO_AIRE_ALTO = "AIRE_ALTO"` a nivel de módulo (usadas en tests).

- [ ] **Step 1.1: Escribir los tests**

Crear `tests/test_secado_fase.py` con el siguiente contenido completo:

```python
# tests/test_secado_fase.py
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.secado import (
    SecadoFase, _PASO_VACIO_BAJO, _PASO_AIRE_ALTO
)
from autoclave.state_machine.cycle_phases.base_fase import FaseResult


def _make_fase(
    modo=1, tiempo_min=5.0,
    presion_chaqueta=200, rango_chaqueta=30,
    presion_baja=20.0, presion_alta=80.0,
    timeout_pulso=10, has_vacuum=True,
    pres_camara=50.0, pres_chaqueta=200.0,
):
    estado = MagicMock()
    estado.sensores_pres = {
        "pres_camara": pres_camara,
        "pres_chaqueta": pres_chaqueta,
    }

    set_do = MagicMock()

    params = {
        "modo": modo,
        "tiempo_secado": tiempo_min,
        "presion_chaqueta_secado": presion_chaqueta,
        "rango_chaqueta_secado": rango_chaqueta,
        "presion_baja_secado": presion_baja,
        "presion_alta_secado": presion_alta,
        "timeout_pulso": timeout_pulso,
    }

    cycle = MagicMock()
    cycle.get_param.side_effect = lambda seccion, param, default=None: params.get(param, default)

    fase = SecadoFase(estado, set_do, cycle, MagicMock(), MagicMock(), MagicMock())
    fase.cap.has_vacuum = has_vacuum
    fase.reset()
    return fase, estado, set_do


# ── skip ─────────────────────────────────────────────────────────────────────

def test_skip_sin_vacío():
    fase, _, set_do = _make_fase(has_vacuum=False)
    assert fase.update() == FaseResult.COMPLETADO
    set_do.bomba_vacio_on.assert_not_called()


def test_skip_tiempo_cero():
    fase, _, set_do = _make_fase(tiempo_min=0)
    assert fase.update() == FaseResult.COMPLETADO
    set_do.bomba_vacio_on.assert_not_called()


# ── modo 1 ───────────────────────────────────────────────────────────────────

def test_modo1_activa_vacio_cada_tick():
    fase, _, set_do = _make_fase(modo=1)
    assert fase.update() == FaseResult.EN_CURSO
    set_do.bomba_vacio_on.assert_called()
    set_do.vacio_camara_on.assert_called()
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_modo1_completa_al_expirar_timer():
    fase, _, set_do = _make_fase(modo=1, tiempo_min=1)
    fase.update()            # inicializar
    fase._timer_fin -= 200   # simular tiempo transcurrido
    assert fase.update() == FaseResult.COMPLETADO
    set_do.bomba_vacio_off.assert_called()
    set_do.vacio_camara_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()


def test_modo1_chaqueta_on_cuando_presion_baja():
    fase, estado, set_do = _make_fase(modo=1, presion_chaqueta=200, rango_chaqueta=30)
    estado.sensores_pres["pres_chaqueta"] = 100.0   # muy por debajo
    fase.update()
    set_do.vapor_chaqueta_on.assert_called()


def test_modo1_chaqueta_off_cuando_presion_alta():
    fase, estado, set_do = _make_fase(modo=1, presion_chaqueta=200, rango_chaqueta=30)
    estado.sensores_pres["pres_chaqueta"] = 350.0   # muy por encima
    fase.update()
    set_do.vapor_chaqueta_off.assert_called()


# ── modo 2 ───────────────────────────────────────────────────────────────────

def test_modo2_activa_vacio_y_aire():
    fase, _, set_do = _make_fase(modo=2)
    assert fase.update() == FaseResult.EN_CURSO
    set_do.bomba_vacio_on.assert_called()
    set_do.vacio_camara_on.assert_called()
    set_do.aire_admosferico_camara_on.assert_called()


def test_modo2_apaga_aire_al_completar():
    fase, _, set_do = _make_fase(modo=2, tiempo_min=1)
    fase.update()
    fase._timer_fin -= 200
    assert fase.update() == FaseResult.COMPLETADO
    set_do.aire_admosferico_camara_off.assert_called()


# ── modo 3 ───────────────────────────────────────────────────────────────────

def test_modo3_inicia_en_vacio_bajo():
    fase, _, set_do = _make_fase(modo=3, pres_camara=50.0, presion_baja=20.0)
    assert fase.update() == FaseResult.EN_CURSO
    assert fase._sub_estado == _PASO_VACIO_BAJO
    set_do.bomba_vacio_on.assert_called()
    set_do.vacio_camara_on.assert_called()
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_modo3_transicion_a_aire_al_alcanzar_presion_baja():
    fase, estado, set_do = _make_fase(modo=3, pres_camara=50.0, presion_baja=20.0)
    fase.update()   # inicializar en VACIO_BAJO; pres=50 > 20, no transiciona
    estado.sensores_pres["pres_camara"] = 15.0   # ahora pres <= presion_baja
    set_do.reset_mock()
    fase.update()
    assert fase._sub_estado == _PASO_AIRE_ALTO
    set_do.vacio_camara_off.assert_called()
    set_do.bomba_vacio_off.assert_called()


def test_modo3_transicion_a_vacio_al_alcanzar_presion_alta():
    fase, estado, set_do = _make_fase(
        modo=3, pres_camara=15.0, presion_baja=20.0, presion_alta=80.0
    )
    fase.update()   # inicializar; pres=15 <= 20 → transiciona a AIRE_ALTO en este tick
    assert fase._sub_estado == _PASO_AIRE_ALTO
    estado.sensores_pres["pres_camara"] = 90.0   # pres >= presion_alta
    set_do.reset_mock()
    fase.update()
    assert fase._sub_estado == _PASO_VACIO_BAJO
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo3_fallo_timeout_vacio_bajo():
    fase, _, set_do = _make_fase(modo=3, pres_camara=50.0, presion_baja=20.0)
    fase.update()   # inicializar
    fase._timeout_pulso_fin -= 200   # simular timeout
    assert fase.update() == FaseResult.FALLO
    set_do.bomba_vacio_off.assert_called()
    set_do.vapor_chaqueta_off.assert_called()


def test_modo3_fallo_timeout_aire_alto():
    fase, estado, set_do = _make_fase(
        modo=3, pres_camara=15.0, presion_baja=20.0, presion_alta=80.0
    )
    fase.update()   # inicializar; transiciona a AIRE_ALTO
    assert fase._sub_estado == _PASO_AIRE_ALTO
    fase._timeout_pulso_fin -= 200
    assert fase.update() == FaseResult.FALLO
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo3_completa_cuando_expira_timer_fin():
    fase, _, set_do = _make_fase(modo=3, tiempo_min=1)
    fase.update()
    fase._timer_fin -= 200
    assert fase.update() == FaseResult.COMPLETADO
    set_do.bomba_vacio_off.assert_called()
```

- [ ] **Step 1.2: Ejecutar tests — verificar que fallan**

```
pytest tests/test_secado_fase.py -v
```
Esperado: `ImportError: cannot import name 'SecadoFase'`

- [ ] **Step 1.3: Crear `src/autoclave/state_machine/cycle_phases/secado.py`**

```python
# state_machine/cycle_phases/secado.py
import time
import logging
from .base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)

_PASO_VACIO_BAJO = "VACIO_BAJO"
_PASO_AIRE_ALTO  = "AIRE_ALTO"


class SecadoFase(BaseFase):
    name = "SECADO"

    def reset(self):
        self._inicializado      = False
        self._timer_fin         = None
        self._timeout_pulso_fin = None
        self._sub_estado        = None

    def update(self) -> FaseResult:
        if not self.cap.has_vacuum:
            logger.info("SecadoFase: sin bomba de vacío — fase saltada")
            return FaseResult.COMPLETADO

        tiempo_min = self.cycle.get_param("secado", "tiempo_secado") or 0
        if float(tiempo_min) == 0:
            logger.info("SecadoFase: tiempo_secado=0 — fase saltada")
            return FaseResult.COMPLETADO

        modo = int(self.cycle.get_param("secado", "modo") or 1)

        if not self._inicializado:
            self._timer_fin = time.time() + float(tiempo_min) * 60
            if modo == 3:
                timeout_min = self.cycle.get_param("secado", "timeout_pulso") or 10
                self._timeout_pulso_fin = time.time() + float(timeout_min) * 60
                self._sub_estado = _PASO_VACIO_BAJO
            self._inicializado = True
            logger.info("SecadoFase: modo %d | %.1f min", modo, float(tiempo_min))

        if modo == 1:
            return self._tick_modo_1()
        if modo == 2:
            return self._tick_modo_2()
        if modo == 3:
            return self._tick_modo_3()

        logger.error("SecadoFase: modo desconocido %d", modo)
        return FaseResult.EN_CURSO

    # ── helpers ─────────────────────────────────────────────────────────

    def _tick_chaqueta(self):
        pres = self.estado.sensores_pres.get("pres_chaqueta")
        if pres is None:
            return
        p_obj = float(self.cycle.get_param("secado", "presion_chaqueta_secado") or 200)
        rango = float(self.cycle.get_param("secado", "rango_chaqueta_secado") or 30)
        if pres < p_obj - rango:
            self.set_do.vapor_chaqueta_on()
        elif pres > p_obj + rango:
            self.set_do.vapor_chaqueta_off()

    def _apagar_todo(self):
        self.set_do.bomba_vacio_off()
        self.set_do.vacio_camara_off()
        self.set_do.aire_admosferico_camara_off()
        self.set_do.vapor_chaqueta_off()

    # ── modos ───────────────────────────────────────────────────────────

    def _tick_modo_1(self) -> FaseResult:
        if time.time() >= self._timer_fin:
            self._apagar_todo()
            logger.info("SecadoFase modo 1: COMPLETADO")
            return FaseResult.COMPLETADO
        self._tick_chaqueta()
        self.set_do.bomba_vacio_on()
        self.set_do.vacio_camara_on()
        return FaseResult.EN_CURSO

    def _tick_modo_2(self) -> FaseResult:
        if time.time() >= self._timer_fin:
            self._apagar_todo()
            logger.info("SecadoFase modo 2: COMPLETADO")
            return FaseResult.COMPLETADO
        self._tick_chaqueta()
        self.set_do.bomba_vacio_on()
        self.set_do.vacio_camara_on()
        self.set_do.aire_admosferico_camara_on()
        return FaseResult.EN_CURSO

    def _tick_modo_3(self) -> FaseResult:
        if time.time() >= self._timer_fin:
            self._apagar_todo()
            logger.info("SecadoFase modo 3: COMPLETADO")
            return FaseResult.COMPLETADO

        self._tick_chaqueta()
        pres = self._pres_camara()

        if self._sub_estado == _PASO_VACIO_BAJO:
            presion_baja = float(self.cycle.get_param("secado", "presion_baja_secado") or 20)
            self.set_do.bomba_vacio_on()
            self.set_do.vacio_camara_on()

            if time.time() > self._timeout_pulso_fin:
                logger.error("SecadoFase modo 3: TIMEOUT en VACIO_BAJO")
                self._apagar_todo()
                return FaseResult.FALLO

            if pres is not None and pres <= presion_baja:
                self.set_do.bomba_vacio_off()
                self.set_do.vacio_camara_off()
                timeout_min = self.cycle.get_param("secado", "timeout_pulso") or 10
                self._timeout_pulso_fin = time.time() + float(timeout_min) * 60
                self._sub_estado = _PASO_AIRE_ALTO
                logger.info("SecadoFase: %.1f kPa ≤ pres_baja → AIRE_ALTO", pres)

        elif self._sub_estado == _PASO_AIRE_ALTO:
            presion_alta = float(self.cycle.get_param("secado", "presion_alta_secado") or 80)
            self.set_do.aire_admosferico_camara_on()

            if time.time() > self._timeout_pulso_fin:
                logger.error("SecadoFase modo 3: TIMEOUT en AIRE_ALTO")
                self._apagar_todo()
                return FaseResult.FALLO

            if pres is not None and pres >= presion_alta:
                self.set_do.aire_admosferico_camara_off()
                timeout_min = self.cycle.get_param("secado", "timeout_pulso") or 10
                self._timeout_pulso_fin = time.time() + float(timeout_min) * 60
                self._sub_estado = _PASO_VACIO_BAJO
                logger.info("SecadoFase: %.1f kPa ≥ pres_alta → VACIO_BAJO", pres)

        return FaseResult.EN_CURSO
```

- [ ] **Step 1.4: Ejecutar tests — verificar que pasan**

```
pytest tests/test_secado_fase.py -v
```
Esperado: todos los tests en PASSED.

- [ ] **Step 1.5: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/secado.py tests/test_secado_fase.py
git commit -m "feat: SecadoFase — 3 modos de secado con chaqueta propia"
```

---

## Task 2: Migración de JSON de ciclos a sección `"secado"`

**Files:**
- Modify: `src/autoclave/cycles/factory/instrumental_134.json`
- Modify: `src/autoclave/cycles/factory/bowe_dick.json`
- Modify: `src/autoclave/cycles/user/instrumental_134.json`
- Modify: `src/autoclave/cycles/user/bowe_dick.json`

**Interfaces:**
- Produces: sección `"secado"` con claves: `modo`, `tiempo_secado`, `presion_chaqueta_secado`, `rango_chaqueta_secado`, `presion_baja_secado`, `presion_alta_secado`, `timeout_pulso`.
- `"esterilizacion"` ya no contiene `tiempo_secado` ni `tipo_secado`.

- [ ] **Step 2.1: Actualizar `cycles/factory/instrumental_134.json`**

En la sección `"esterilizacion"`, eliminar las líneas:
```json
"tiempo_secado":  { "value": 2.0, "type": "float", "unit": "min", "min": 0, "max": 1000 },
"tipo_secado":    { "value": 1,   "type": "int",   "unit": "",    "min": 1, "max": 4 },
```

Agregar después del cierre de `"esterilizacion"` y antes de `"descompresion"`, la nueva sección:
```json
"secado": {
    "modo":                    { "value": 1,   "type": "int",   "unit": "",    "min": 1, "max": 3 },
    "tiempo_secado":           { "value": 2.0, "type": "float", "unit": "min", "min": 0, "max": 120 },
    "presion_chaqueta_secado": { "value": 200, "type": "int",   "unit": "kPa", "min": 0, "max": 500 },
    "rango_chaqueta_secado":   { "value": 30,  "type": "int",   "unit": "kPa", "min": 0, "max": 100 },
    "presion_baja_secado":     { "value": 20,  "type": "int",   "unit": "kPa", "min": 0, "max": 200 },
    "presion_alta_secado":     { "value": 80,  "type": "int",   "unit": "kPa", "min": 0, "max": 300 },
    "timeout_pulso":           { "value": 10,  "type": "int",   "unit": "min", "min": 1, "max": 60 }
},
```

- [ ] **Step 2.2: Actualizar `cycles/factory/bowe_dick.json`**

En la sección `"secado"` existente, reemplazar el contenido completo:

Antes:
```json
"secado":{
    "tiempo_secado": { "value": 2.0, "type": "float", "unit": "min", "min": 0, "max": 1000 },
    "tipo_secado":   { "value": 1,   "type": "int",   "unit": "",    "min": 1, "max": 4 }
},
```

Después:
```json
"secado": {
    "modo":                    { "value": 1,   "type": "int",   "unit": "",    "min": 1, "max": 3 },
    "tiempo_secado":           { "value": 2.0, "type": "float", "unit": "min", "min": 0, "max": 120 },
    "presion_chaqueta_secado": { "value": 200, "type": "int",   "unit": "kPa", "min": 0, "max": 500 },
    "rango_chaqueta_secado":   { "value": 30,  "type": "int",   "unit": "kPa", "min": 0, "max": 100 },
    "presion_baja_secado":     { "value": 20,  "type": "int",   "unit": "kPa", "min": 0, "max": 200 },
    "presion_alta_secado":     { "value": 80,  "type": "int",   "unit": "kPa", "min": 0, "max": 300 },
    "timeout_pulso":           { "value": 10,  "type": "int",   "unit": "min", "min": 1, "max": 60 }
},
```

- [ ] **Step 2.3: Aplicar los mismos cambios a los archivos `user/`**

- `cycles/user/instrumental_134.json`: mismos cambios que el factory (eliminar de `"esterilizacion"`, agregar sección `"secado"`).
- `cycles/user/bowe_dick.json`: mismos cambios que el factory (reemplazar sección `"secado"`).

- [ ] **Step 2.4: Verificar que los JSON son válidos**

```
python -c "import json; json.load(open('src/autoclave/cycles/factory/instrumental_134.json'))"
python -c "import json; json.load(open('src/autoclave/cycles/factory/bowe_dick.json'))"
python -c "import json; json.load(open('src/autoclave/cycles/user/instrumental_134.json'))"
python -c "import json; json.load(open('src/autoclave/cycles/user/bowe_dick.json'))"
```
Esperado: sin salida (sin errores).

- [ ] **Step 2.5: Verificar que `Cycle.get_param` funciona con los nuevos datos**

```
python -c "
import json
from autoclave.core.cycle_manager import Cycle
data = json.load(open('src/autoclave/cycles/factory/instrumental_134.json'))
c = Cycle('x','x', data['parameters'])
print(c.get_param('secado','modo'))
print(c.get_param('secado','tiempo_secado'))
print(c.get_param('secado','presion_baja_secado'))
"
```
Esperado:
```
1
2.0
20
```

- [ ] **Step 2.6: Commit**

```bash
git add src/autoclave/cycles/
git commit -m "feat: migrar params secado a sección propia en todos los JSONs de ciclo"
```

---

## Task 3: Integrar `SecadoFase` en `CicloState`

**Files:**
- Modify: `src/autoclave/state_machine/states/ciclo.py` (líneas 22-28 y 64-74 y 132-153)

**Interfaces:**
- Consumes: `SecadoFase` del task 1.
- Produces: pipeline actualizado con `SecadoFase` en posición 7 (entre `EsterilizacionFase` e `DescompresionFase`). `_mantener_chaqueta()` no actúa durante SECADO.

- [ ] **Step 3.1: Agregar import de `SecadoFase`**

En `src/autoclave/state_machine/states/ciclo.py`, después de la línea:
```python
from autoclave.state_machine.cycle_phases.descompresion import DescompresionFase
```
Agregar:
```python
from autoclave.state_machine.cycle_phases.secado import SecadoFase
```

- [ ] **Step 3.2: Insertar `SecadoFase` en el pipeline**

Localizar en `__init__` de `CicloState` el bloque `self._fases = [...]` (líneas ~66-74). Cambiar de:
```python
        self._fases = [
            PrecalentamientoFase(*_args),
            PurgaFase(*_args),
            PrevacioFase(*_args),
            CalentamientoFase(*_args),
            EstabilizacionFase(*_args),
            EsterilizacionFase(*_args),
            DescompresionFase(*_args),
        ]
```
A:
```python
        self._fases = [
            PrecalentamientoFase(*_args),
            PurgaFase(*_args),
            PrevacioFase(*_args),
            CalentamientoFase(*_args),
            EstabilizacionFase(*_args),
            EsterilizacionFase(*_args),
            SecadoFase(*_args),
            DescompresionFase(*_args),
        ]
```

- [ ] **Step 3.3: Suprimir `_mantener_chaqueta()` durante SECADO**

Al inicio del método `_mantener_chaqueta(self)` (línea ~133), agregar:
```python
    def _mantener_chaqueta(self):
        if self._fase_idx < len(self._fases) and isinstance(self._fases[self._fase_idx], SecadoFase):
            return
        pres = self.estado.sensores_pres.get("pres_chaqueta")
        # ... resto del método sin cambios ...
```

- [ ] **Step 3.4: Ejecutar suite de tests existentes para verificar no-regresión**

```
pytest tests/ -v --tb=short -x
```
Esperado: todos los tests anteriores siguen en PASSED; los tests de `test_secado_fase.py` también pasan.

- [ ] **Step 3.5: Commit**

```bash
git add src/autoclave/state_machine/states/ciclo.py
git commit -m "feat: integrar SecadoFase en pipeline de CicloState"
```

---

## Task 4: Actualizar endpoint PATCH del backend

**Files:**
- Modify: `src/autoclave/backend/server.py` (líneas ~336-361)
- Modify: `tests/test_patch_cycle_parameters.py`

**Interfaces:**
- Consumes: sección `"secado"` en `cycle.parameters` (task 2).
- Produces: `PATCH /cycle/parameters` acepta y valida: `modo`, `tiempo_secado`, `presion_chaqueta_secado`, `rango_chaqueta_secado`, `presion_baja_secado`, `presion_alta_secado`, `timeout_pulso`.

- [ ] **Step 4.1: Actualizar el test existente de `test_patch_cycle_parameters`**

En `tests/test_patch_cycle_parameters.py`, función `test_cycle_manager_asigna_path_al_cargar`, cambiar `cycle_data` de:
```python
    cycle_data = {
        "cycle_id": "ciclo_test",
        "display_name": "Test",
        "parameters": {
            "esterilizacion": {
                "tiempo_secado": {
                    "value": 2.0, "type": "float", "unit": "min", "min": 0, "max": 120
                }
            }
        },
    }
```
A:
```python
    cycle_data = {
        "cycle_id": "ciclo_test",
        "display_name": "Test",
        "parameters": {
            "secado": {
                "tiempo_secado": {
                    "value": 2.0, "type": "float", "unit": "min", "min": 0, "max": 120
                }
            }
        },
    }
```

- [ ] **Step 4.2: Verificar que el test actualizado pasa**

```
pytest tests/test_patch_cycle_parameters.py -v
```
Esperado: PASSED.

- [ ] **Step 4.3: Reemplazar el handler PATCH en `server.py`**

Localizar y reemplazar completamente el bloque `@app.patch("/cycle/parameters")` (líneas ~336-361) con:

```python
@app.patch("/cycle/parameters")
def update_cycle_parameters(body: dict = Body(...)):
    """Actualiza parámetros de la sección 'secado' del ciclo activo y persiste si es user."""
    try:
        cycle = context.cycle_manager.get_selected_cycle()
    except Exception:
        raise HTTPException(status_code=503, detail="No hay ciclo activo seleccionado")

    _SECADO_PARAMS = {
        "modo":                    (int,   1,   3),
        "tiempo_secado":           (float, 0.0, 120.0),
        "presion_chaqueta_secado": (int,   0,   500),
        "rango_chaqueta_secado":   (int,   0,   100),
        "presion_baja_secado":     (int,   0,   200),
        "presion_alta_secado":     (int,   0,   300),
        "timeout_pulso":           (int,   1,   60),
    }

    secado = cycle.parameters.get("secado")
    if secado is None:
        raise HTTPException(status_code=422, detail="El ciclo no tiene sección 'secado'")

    for param, (tipo, v_min, v_max) in _SECADO_PARAMS.items():
        if param not in body:
            continue
        try:
            value = tipo(body[param])
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"{param} debe ser numérico")
        if not (v_min <= value <= v_max):
            raise HTTPException(
                status_code=422,
                detail=f"{param} fuera de rango ({v_min}-{v_max})",
            )
        if param not in secado:
            raise HTTPException(status_code=422, detail=f"Parámetro '{param}' no existe en 'secado'")
        secado[param]["value"] = value

    if getattr(cycle, "source", "") == "user" and hasattr(cycle, "_path"):
        _save_cycle_json(cycle)

    return {"ok": True}
```

- [ ] **Step 4.4: Ejecutar todos los tests**

```
pytest tests/ -v --tb=short -x
```
Esperado: todos en PASSED.

- [ ] **Step 4.5: Commit**

```bash
git add src/autoclave/backend/server.py tests/test_patch_cycle_parameters.py
git commit -m "feat: endpoint PATCH /cycle/parameters lee y valida sección secado"
```

---

## Task 5: Actualizar `SecadoView` — UI de configuración de secado

**Files:**
- Modify: `src/autoclave/ui_pyside/views/secado.py`

**Interfaces:**
- Consumes: `GET /cycle` → `data["parameters"]["secado"]` con claves `modo`, `tiempo_secado`, `presion_chaqueta_secado`, `presion_baja_secado`, `presion_alta_secado`.
- Consumes: `PATCH /cycle/parameters` del task 4.
- Produces: UI con selector de modo (1-3), campo de tiempo, campo de presión chaqueta, y campos modo-3 visibles solo cuando modo == 3.

- [ ] **Step 5.1: Reemplazar `src/autoclave/ui_pyside/views/secado.py` completo**

```python
# src/autoclave/ui_pyside/views/secado.py
import requests
from autoclave.ui.service_ui.backend_client import BackendClient
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    DoubleSpinBox,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    SubtitleLabel,
)


class SecadoView(QWidget):
    BACKEND_URL = "http://localhost:8000"

    def __init__(self, nav_callback):
        super().__init__()
        self._nav = nav_callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        header = QHBoxLayout()
        btn_back = PushButton("← Volver")
        btn_back.clicked.connect(lambda: self._nav("home"))
        header.addWidget(btn_back)
        header.addStretch()
        layout.addLayout(header)

        layout.addWidget(SubtitleLabel("Configuración de Secado"))

        # ── Modo ─────────────────────────────────────────────────────────
        modo_row = QHBoxLayout()
        modo_row.addWidget(BodyLabel("Modo (1=Vacío, 2=Vacío+Aire, 3=Pulsado):"))
        self._spin_modo = SpinBox()
        self._spin_modo.setRange(1, 3)
        self._spin_modo.setFixedWidth(100)
        self._spin_modo.valueChanged.connect(self._on_modo_changed)
        modo_row.addWidget(self._spin_modo)
        modo_row.addStretch()
        layout.addLayout(modo_row)

        # ── Tiempo ───────────────────────────────────────────────────────
        tiempo_row = QHBoxLayout()
        tiempo_row.addWidget(BodyLabel("Tiempo de secado (min):"))
        self._spin_tiempo = DoubleSpinBox()
        self._spin_tiempo.setRange(0.0, 120.0)
        self._spin_tiempo.setSingleStep(0.5)
        self._spin_tiempo.setDecimals(1)
        self._spin_tiempo.setFixedWidth(140)
        tiempo_row.addWidget(self._spin_tiempo)
        tiempo_row.addStretch()
        layout.addLayout(tiempo_row)

        # ── Presión chaqueta ─────────────────────────────────────────────
        chaqueta_row = QHBoxLayout()
        chaqueta_row.addWidget(BodyLabel("Presión chaqueta secado (kPa):"))
        self._spin_chaqueta = SpinBox()
        self._spin_chaqueta.setRange(0, 500)
        self._spin_chaqueta.setFixedWidth(120)
        chaqueta_row.addWidget(self._spin_chaqueta)
        chaqueta_row.addStretch()
        layout.addLayout(chaqueta_row)

        # ── Parámetros modo 3 (ocultos por defecto) ───────────────────────
        self._modo3_widget = QWidget()
        modo3_layout = QVBoxLayout(self._modo3_widget)
        modo3_layout.setContentsMargins(0, 0, 0, 0)
        modo3_layout.setSpacing(12)

        pres_baja_row = QHBoxLayout()
        pres_baja_row.addWidget(BodyLabel("Presión baja pulso (kPa):"))
        self._spin_pres_baja = SpinBox()
        self._spin_pres_baja.setRange(0, 200)
        self._spin_pres_baja.setFixedWidth(120)
        pres_baja_row.addWidget(self._spin_pres_baja)
        pres_baja_row.addStretch()
        modo3_layout.addLayout(pres_baja_row)

        pres_alta_row = QHBoxLayout()
        pres_alta_row.addWidget(BodyLabel("Presión alta pulso (kPa):"))
        self._spin_pres_alta = SpinBox()
        self._spin_pres_alta.setRange(0, 300)
        self._spin_pres_alta.setFixedWidth(120)
        pres_alta_row.addWidget(self._spin_pres_alta)
        pres_alta_row.addStretch()
        modo3_layout.addLayout(pres_alta_row)

        layout.addWidget(self._modo3_widget)
        self._modo3_widget.setVisible(False)

        # ── Guardar ──────────────────────────────────────────────────────
        btn_save = PrimaryPushButton("Guardar")
        btn_save.setFixedWidth(160)
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)

        layout.addStretch()

    def _on_modo_changed(self, value: int) -> None:
        self._modo3_widget.setVisible(value == 3)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._load_current()

    def _load_current(self) -> None:
        try:
            data = BackendClient(self.BACKEND_URL).get("/cycle")
            secado = data["parameters"]["secado"]
            self._spin_modo.setValue(int(secado["modo"]["value"]))
            self._spin_tiempo.setValue(float(secado["tiempo_secado"]["value"]))
            self._spin_chaqueta.setValue(int(secado["presion_chaqueta_secado"]["value"]))
            self._spin_pres_baja.setValue(int(secado["presion_baja_secado"]["value"]))
            self._spin_pres_alta.setValue(int(secado["presion_alta_secado"]["value"]))
            self._on_modo_changed(self._spin_modo.value())
        except Exception:
            pass

    def _save(self) -> None:
        payload = {
            "modo":                    self._spin_modo.value(),
            "tiempo_secado":           self._spin_tiempo.value(),
            "presion_chaqueta_secado": self._spin_chaqueta.value(),
            "presion_baja_secado":     self._spin_pres_baja.value(),
            "presion_alta_secado":     self._spin_pres_alta.value(),
        }
        try:
            BackendClient(self.BACKEND_URL).patch("/cycle/parameters", payload)
            InfoBar.success(
                title="Guardado",
                content=f"Configuración de secado actualizada",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
        except requests.HTTPError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            InfoBar.error(
                title="Error al guardar",
                content=detail,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self,
            )
        except Exception:
            InfoBar.warning(
                title="Sin conexión",
                content="No se pudo conectar al backend",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self,
            )
```

- [ ] **Step 5.2: Ejecutar suite de tests completa**

```
pytest tests/ -v --tb=short
```
Esperado: todos en PASSED.

- [ ] **Step 5.3: Commit**

```bash
git add src/autoclave/ui_pyside/views/secado.py
git commit -m "feat: SecadoView muestra modo, tiempo, chaqueta y params pulso modo 3"
```

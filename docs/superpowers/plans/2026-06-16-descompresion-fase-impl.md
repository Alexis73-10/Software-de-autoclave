# Fase de Descompresión — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar `DescompresionFase` con 6 modos de operación e integrarla al final del pipeline del ciclo de esterilización.

**Architecture:** Clase única `DescompresionFase(BaseFase)` con delegación por modo (`_tick_modo_N`). Estado interno para pre-espera, sub-etapas (modo 3/4/5) y control de pulsos de chaqueta y aire comprimido. Pipeline actualizado en `ciclo.py`. Parámetros anidados por modo en los 4 JSONs de ciclos.

**Tech Stack:** Python 3.14, pytest, `unittest.mock`.

---

## Mapa de archivos

| Archivo | Acción |
|---------|--------|
| `src/autoclave/state_machine/cycle_phases/descompresion.py` | Crear |
| `src/autoclave/state_machine/states/ciclo.py` | Modificar — agregar `DescompresionFase` al pipeline |
| `src/autoclave/cycles/factory/instrumental_134.json` | Modificar — agregar sección `"descompresion"` |
| `src/autoclave/cycles/factory/bowe_dick.json` | Modificar — agregar sección `"descompresion"` |
| `src/autoclave/cycles/user/instrumental_134.json` | Modificar — agregar sección `"descompresion"` |
| `src/autoclave/cycles/user/bowe_dick.json` | Modificar — agregar sección `"descompresion"` |
| `tests/test_descompresion_fase.py` | Crear |

---

## Task 1: Esqueleto + pre-espera + modo 0

**Files:**
- Create: `tests/test_descompresion_fase.py`
- Create: `src/autoclave/state_machine/cycle_phases/descompresion.py`

- [ ] **Step 1.1 — Crear test file con helper y primeros 4 tests**

Crear `tests/test_descompresion_fase.py`:

```python
import time as _time
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.descompresion import DescompresionFase
from autoclave.state_machine.cycle_phases.base_fase import FaseResult

_CONFIG = {
    "presion_admosferica": 101.3,
    "rango_presion_atm":   20.0,
}

_BASE_PARAMS = {
    ("descompresion", "tiempo_pre_despresurizacion"): 0,
    ("descompresion", "modo_1", "timeout"): 10,
    ("descompresion", "modo_2", "timeout"): 30,
    ("descompresion", "modo_3", "presion_cambio"): 150,
    ("descompresion", "modo_3", "timeout"): 30,
    ("descompresion", "modo_4", "presion_camara_enfriamiento"): 200,
    ("descompresion", "modo_4", "temperatura_enfriamiento"): 80.0,
    ("descompresion", "modo_4", "tiempo_apertura_chaqueta"): 5,
    ("descompresion", "modo_4", "tiempo_cierre_chaqueta"): 10,
    ("descompresion", "modo_4", "timeout"): 120,
    ("descompresion", "modo_5", "presion_camara_enfriamiento"): 200,
    ("descompresion", "modo_5", "temperatura_enfriamiento"): 80.0,
    ("descompresion", "modo_5", "tiempo_apertura_chaqueta"): 5,
    ("descompresion", "modo_5", "tiempo_cierre_chaqueta"): 10,
    ("descompresion", "modo_5", "timeout"): 120,
}


def _make_fase(modo=1, pres=300.0, temp=120.0, tiempo_pre=0, extra_params=None):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres}
    estado.sensores_temp = {"temp_camara": temp}

    set_do = MagicMock()

    config = MagicMock()
    config.get.side_effect = lambda k, *a: _CONFIG.get(k)

    params = dict(_BASE_PARAMS)
    params[("descompresion", "modo")] = modo
    params[("descompresion", "tiempo_pre_despresurizacion")] = tiempo_pre
    if extra_params:
        params.update(extra_params)

    cycle = MagicMock()
    cycle.get_param.side_effect = lambda *keys, default=None: params.get(keys, default)

    fase = DescompresionFase(estado, set_do, cycle, config, alarm_manager=None, cap=MagicMock())
    fase.reset()
    return fase, estado, set_do


# ── Pre-espera ────────────────────────────────────────────────────────────────

def test_pre_espera_mantiene_salidas_apagadas():
    fase, estado, set_do = _make_fase(modo=1, pres=300.0, tiempo_pre=5)
    fase.update()        # primera llamada: etapa = "pre_espera"
    set_do.reset_mock()
    fase.update()        # sigue en espera (< 5 s)
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_not_called()
    set_do.aire_comprimido_camara_on.assert_not_called()
    set_do.agua_chaqueta_on.assert_not_called()


def test_pre_espera_0_entra_directo_al_modo():
    fase, estado, set_do = _make_fase(modo=0, pres=300.0, tiempo_pre=0)
    fase.update()        # primera llamada: sin pre-espera → etapa = "modo"
    assert fase._etapa == "modo"


# ── Modo 0 ────────────────────────────────────────────────────────────────────

def test_modo_0_en_curso_con_pres_alta():
    # presion_admosferica=101.3 + rango=20 → umbral=121.3
    fase, estado, set_do = _make_fase(modo=0, pres=300.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.EN_CURSO


def test_modo_0_completa_al_alcanzar_presion_atm():
    fase, estado, set_do = _make_fase(modo=0, pres=121.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
```

- [ ] **Step 1.2 — Verificar que fallan (ImportError)**

```
pytest tests/test_descompresion_fase.py -v
```

Esperado: `ERROR` — `ModuleNotFoundError: No module named 'autoclave.state_machine.cycle_phases.descompresion'`

- [ ] **Step 1.3 — Crear `descompresion.py` con implementación completa**

Crear `src/autoclave/state_machine/cycle_phases/descompresion.py`:

```python
import time
import logging

from autoclave.state_machine.cycle_phases.base_fase import BaseFase, FaseResult

logger = logging.getLogger(__name__)


class DescompresionFase(BaseFase):
    name = "DESCOMPRESION"

    def reset(self):
        self._modo             = self.cycle.get_param("descompresion", "modo", default=0)
        self._etapa            = None
        self._sub_etapa        = None
        self._t_inicio         = None
        self._t_timeout        = None
        self._t_pulso_chaqueta = None
        self._chaqueta_abierta = False
        self._t_aire_comprimido = None

    def update(self) -> FaseResult:
        if self._etapa is None:
            self._apagar_todo()
            t_pre = self.cycle.get_param("descompresion", "tiempo_pre_despresurizacion", default=0)
            if t_pre and t_pre > 0:
                self._etapa    = "pre_espera"
                self._t_inicio = time.time()
            else:
                self._etapa = "modo"
                self._iniciar_modo()
            return FaseResult.EN_CURSO

        if self._etapa == "pre_espera":
            t_pre = self.cycle.get_param("descompresion", "tiempo_pre_despresurizacion", default=0)
            if time.time() - self._t_inicio >= t_pre:
                self._etapa = "modo"
                self._iniciar_modo()
            return FaseResult.EN_CURSO

        return self._tick_modo()

    def _iniciar_modo(self):
        self._t_inicio = time.time()
        if self._modo > 0:
            timeout_min     = self.cycle.get_param("descompresion", f"modo_{self._modo}", "timeout", default=60)
            self._t_timeout = self._t_inicio + (timeout_min or 60) * 60
        if self._modo == 3:
            self._sub_etapa = "lenta"
        elif self._modo in (4, 5):
            self._sub_etapa         = "enfriamiento"
            self._t_pulso_chaqueta  = None
            self._chaqueta_abierta  = False
            self._t_aire_comprimido = None

    def _tick_modo(self) -> FaseResult:
        if self._modo > 0 and self._t_timeout and time.time() > self._t_timeout:
            self._apagar_todo()
            logger.error("DescompresionFase: timeout en modo %d", self._modo)
            return FaseResult.FALLO

        _dispatch = {
            0: self._tick_modo_0,
            1: self._tick_modo_1,
            2: self._tick_modo_2,
            3: self._tick_modo_3,
            4: self._tick_modo_4,
            5: self._tick_modo_5,
        }
        handler = _dispatch.get(self._modo)
        if handler is None:
            logger.error("DescompresionFase: modo desconocido %d", self._modo)
            return FaseResult.EN_CURSO
        return handler()

    def _en_presion_atm(self) -> bool:
        p = self._pres_camara()
        return p is not None and p <= self._pres_atm() + self._rango_atm()

    def _apagar_todo(self):
        self.set_do.descompresion_rapida_off()
        self.set_do.descompresion_lenta_off()
        self.set_do.descompresion_chaqueta_off()
        self.set_do.aire_comprimido_camara_off()
        self.set_do.agua_chaqueta_off()

    def _tick_modo_0(self) -> FaseResult:
        if self._en_presion_atm():
            return FaseResult.COMPLETADO
        return FaseResult.EN_CURSO

    def _tick_modo_1(self) -> FaseResult:
        self.set_do.descompresion_rapida_on()
        if self._en_presion_atm():
            self._apagar_todo()
            return FaseResult.COMPLETADO
        return FaseResult.EN_CURSO

    def _tick_modo_2(self) -> FaseResult:
        self.set_do.descompresion_lenta_on()
        if self._en_presion_atm():
            self._apagar_todo()
            return FaseResult.COMPLETADO
        return FaseResult.EN_CURSO

    def _tick_modo_3(self) -> FaseResult:
        if self._sub_etapa == "lenta":
            presion_cambio = self.cycle.get_param("descompresion", "modo_3", "presion_cambio", default=150)
            self.set_do.descompresion_lenta_on()
            p = self._pres_camara()
            if p is not None and p <= presion_cambio:
                self.set_do.descompresion_lenta_off()
                self._sub_etapa = "rapida"
        else:
            self.set_do.descompresion_rapida_on()
            if self._en_presion_atm():
                self._apagar_todo()
                return FaseResult.COMPLETADO
        return FaseResult.EN_CURSO

    def _tick_modo_4(self) -> FaseResult:
        return self._tick_enfriamiento(modo_key="modo_4", use_lenta=False)

    def _tick_modo_5(self) -> FaseResult:
        return self._tick_enfriamiento(modo_key="modo_5", use_lenta=True)

    def _tick_enfriamiento(self, modo_key: str, use_lenta: bool) -> FaseResult:
        if self._sub_etapa == "enfriamiento":
            return self._tick_sub_enfriamiento(modo_key, use_lenta)
        return self._tick_sub_descompresion()

    def _tick_sub_enfriamiento(self, modo_key: str, use_lenta: bool) -> FaseResult:
        now = time.time()

        # Control aire comprimido cámara (pulso + 3 s de espera antes de re-evaluar)
        presion_obj = self.cycle.get_param("descompresion", modo_key, "presion_camara_enfriamiento", default=200)
        p = self._pres_camara()
        if p is not None and p < presion_obj:
            if self._t_aire_comprimido is None or now >= self._t_aire_comprimido:
                self.set_do.aire_comprimido_camara_on()
                self._t_aire_comprimido = now + 3.0
        else:
            self.set_do.aire_comprimido_camara_off()
            self._t_aire_comprimido = None

        # Agua chaqueta permanente
        self.set_do.agua_chaqueta_on()

        # Pulsos descompresion_chaqueta
        t_on  = self.cycle.get_param("descompresion", modo_key, "tiempo_apertura_chaqueta", default=5)
        t_off = self.cycle.get_param("descompresion", modo_key, "tiempo_cierre_chaqueta",   default=10)

        if t_off == 0:
            self.set_do.descompresion_chaqueta_on()
        else:
            if self._t_pulso_chaqueta is None:
                self._t_pulso_chaqueta = now
                self._chaqueta_abierta = True
                self.set_do.descompresion_chaqueta_on()
            else:
                elapsed = now - self._t_pulso_chaqueta
                if self._chaqueta_abierta and elapsed >= t_on:
                    self.set_do.descompresion_chaqueta_off()
                    self._chaqueta_abierta = False
                    self._t_pulso_chaqueta = now
                elif not self._chaqueta_abierta and elapsed >= t_off:
                    self.set_do.descompresion_chaqueta_on()
                    self._chaqueta_abierta = True
                    self._t_pulso_chaqueta = now

        if use_lenta:
            self.set_do.descompresion_lenta_on()

        # Verificar temperatura objetivo
        temp_obj = self.cycle.get_param("descompresion", modo_key, "temperatura_enfriamiento", default=80.0)
        t = self._temp_camara()
        if t is not None and t <= temp_obj:
            self.set_do.aire_comprimido_camara_off()
            self.set_do.agua_chaqueta_off()
            if use_lenta:
                self.set_do.descompresion_lenta_off()
            self.set_do.descompresion_chaqueta_on()
            self.set_do.descompresion_rapida_on()
            self._sub_etapa = "descompresion"

        return FaseResult.EN_CURSO

    def _tick_sub_descompresion(self) -> FaseResult:
        self.set_do.descompresion_chaqueta_on()
        self.set_do.descompresion_rapida_on()
        if self._en_presion_atm():
            self._apagar_todo()
            return FaseResult.COMPLETADO
        return FaseResult.EN_CURSO
```

- [ ] **Step 1.4 — Verificar que los 4 tests pasan**

```
pytest tests/test_descompresion_fase.py -v
```

Esperado: 4 passed.

- [ ] **Step 1.5 — Commit**

```
git add src/autoclave/state_machine/cycle_phases/descompresion.py tests/test_descompresion_fase.py
git commit -m "feat: DescompresionFase — pre-espera y modo 0"
```

---

## Task 2: Tests modos 1 y 2 + timeouts

**Files:**
- Modify: `tests/test_descompresion_fase.py`

- [ ] **Step 2.1 — Agregar 6 tests al final del archivo de tests**

Agregar al final de `tests/test_descompresion_fase.py`:

```python
# ── Modo 1 ────────────────────────────────────────────────────────────────────

def test_modo_1_activa_rapida():
    fase, estado, set_do = _make_fase(modo=1, pres=300.0)
    fase.update()
    fase.update()
    set_do.descompresion_rapida_on.assert_called()


def test_modo_1_completa_y_apaga_salidas():
    fase, estado, set_do = _make_fase(modo=1, pres=121.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_called()


# ── Modo 2 ────────────────────────────────────────────────────────────────────

def test_modo_2_activa_lenta():
    fase, estado, set_do = _make_fase(modo=2, pres=300.0)
    fase.update()
    fase.update()
    set_do.descompresion_lenta_on.assert_called()


def test_modo_2_completa_y_apaga_salidas():
    fase, estado, set_do = _make_fase(modo=2, pres=121.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_lenta_off.assert_called()


# ── Timeouts ──────────────────────────────────────────────────────────────────

def test_modo_1_timeout_retorna_fallo():
    fase, estado, set_do = _make_fase(modo=1, pres=300.0)
    fase.update()
    fase._t_timeout = _time.time() - 1  # expirado
    result = fase.update()
    assert result == FaseResult.FALLO


def test_apagar_todo_al_fallo_timeout():
    fase, estado, set_do = _make_fase(modo=1, pres=300.0)
    fase.update()
    fase._t_timeout = _time.time() - 1
    fase.update()
    set_do.descompresion_rapida_off.assert_called()
    set_do.descompresion_lenta_off.assert_called()
    set_do.aire_comprimido_camara_off.assert_called()
    set_do.agua_chaqueta_off.assert_called()
```

- [ ] **Step 2.2 — Verificar que pasan (ya implementados en Task 1)**

```
pytest tests/test_descompresion_fase.py -v
```

Esperado: 10 passed.

- [ ] **Step 2.3 — Commit**

```
git add tests/test_descompresion_fase.py
git commit -m "test: modos 1, 2 y timeouts de DescompresionFase"
```

---

## Task 3: Tests modo 3

**Files:**
- Modify: `tests/test_descompresion_fase.py`

- [ ] **Step 3.1 — Agregar 4 tests al final del archivo**

Agregar al final de `tests/test_descompresion_fase.py`:

```python
# ── Modo 3 ────────────────────────────────────────────────────────────────────

def test_modo_3_lenta_hasta_presion_cambio():
    # presion_cambio=150, pres=300 → sub-etapa lenta, rapida no activa
    fase, estado, set_do = _make_fase(modo=3, pres=300.0)
    fase.update()
    fase.update()
    set_do.descompresion_lenta_on.assert_called()
    set_do.descompresion_rapida_on.assert_not_called()


def test_modo_3_transicion_a_rapida():
    # pres=140 <= presion_cambio=150 → cierra lenta, sub-etapa = "rapida"
    fase, estado, set_do = _make_fase(modo=3, pres=140.0)
    fase.update()
    fase.update()
    set_do.descompresion_lenta_off.assert_called()
    assert fase._sub_etapa == "rapida"


def test_modo_3_completa_en_subetapa_rapida():
    # Forzar sub-etapa rapida con pres <= atm+rango
    fase, estado, set_do = _make_fase(modo=3, pres=121.0)
    fase.update()
    fase._sub_etapa = "rapida"
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_called()


def test_modo_3_timeout_retorna_fallo():
    fase, estado, set_do = _make_fase(modo=3, pres=300.0)
    fase.update()
    fase._t_timeout = _time.time() - 1
    result = fase.update()
    assert result == FaseResult.FALLO
```

- [ ] **Step 3.2 — Verificar que pasan**

```
pytest tests/test_descompresion_fase.py -v
```

Esperado: 14 passed.

- [ ] **Step 3.3 — Commit**

```
git add tests/test_descompresion_fase.py
git commit -m "test: modo 3 combinado de DescompresionFase"
```

---

## Task 4: Tests modos 4 y 5

**Files:**
- Modify: `tests/test_descompresion_fase.py`

- [ ] **Step 4.1 — Agregar 8 tests de modo 4 al final del archivo**

Agregar al final de `tests/test_descompresion_fase.py`:

```python
# ── Modo 4 ────────────────────────────────────────────────────────────────────

def test_modo_4_activa_agua_chaqueta():
    fase, estado, set_do = _make_fase(modo=4, pres=300.0, temp=120.0)
    fase.update()
    fase.update()
    set_do.agua_chaqueta_on.assert_called()


def test_modo_4_pulso_aire_cuando_pres_baja():
    # pres=100 < presion_camara_enfriamiento=200 → aire_on
    fase, estado, set_do = _make_fase(modo=4, pres=100.0, temp=120.0)
    fase.update()
    fase.update()
    set_do.aire_comprimido_camara_on.assert_called()


def test_modo_4_aire_espera_3s_entre_pulsos():
    # Segundo tick dentro de 3 s: no vuelve a pulsar
    fase, estado, set_do = _make_fase(modo=4, pres=100.0, temp=120.0)
    fase.update()
    fase.update()   # pulso → _t_aire = now + 3 s
    set_do.aire_comprimido_camara_on.reset_mock()
    fase.update()   # dentro de 3 s → sin nuevo pulso
    set_do.aire_comprimido_camara_on.assert_not_called()


def test_modo_4_chaqueta_siempre_abierta_si_cierre_0():
    fase, estado, set_do = _make_fase(
        modo=4, pres=300.0, temp=120.0,
        extra_params={("descompresion", "modo_4", "tiempo_cierre_chaqueta"): 0},
    )
    fase.update()
    fase.update()
    set_do.descompresion_chaqueta_on.assert_called()
    set_do.descompresion_chaqueta_off.assert_not_called()


def test_modo_4_chaqueta_pulso_on_off():
    fase, estado, set_do = _make_fase(
        modo=4, pres=300.0, temp=120.0,
        extra_params={
            ("descompresion", "modo_4", "tiempo_apertura_chaqueta"): 5,
            ("descompresion", "modo_4", "tiempo_cierre_chaqueta"): 10,
        },
    )
    fase.update()
    fase.update()   # primer tick: _t_pulso inicializado, chaqueta ON
    # Simular > 5 s transcurridos
    fase._t_pulso_chaqueta = _time.time() - 6
    fase._chaqueta_abierta = True
    set_do.reset_mock()
    fase.update()
    set_do.descompresion_chaqueta_off.assert_called()


def test_modo_4_transicion_a_descompresion_al_alcanzar_temp():
    fase, estado, set_do = _make_fase(modo=4, pres=300.0, temp=120.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 79.0   # <= temperatura_enfriamiento=80
    fase.update()
    set_do.agua_chaqueta_off.assert_called()
    set_do.aire_comprimido_camara_off.assert_called()
    set_do.descompresion_rapida_on.assert_called()
    set_do.descompresion_chaqueta_on.assert_called()
    assert fase._sub_etapa == "descompresion"


def test_modo_4_completa_al_alcanzar_presion_atm():
    # Forzar sub-etapa descompresion con pres <= atm+rango
    fase, estado, set_do = _make_fase(modo=4, pres=121.0, temp=120.0)
    fase.update()
    fase._sub_etapa = "descompresion"
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_called()
    set_do.descompresion_chaqueta_off.assert_called()


# ── Modo 5 ────────────────────────────────────────────────────────────────────

def test_modo_5_lenta_activa_durante_enfriamiento():
    fase, estado, set_do = _make_fase(modo=5, pres=300.0, temp=120.0)
    fase.update()
    fase.update()
    set_do.descompresion_lenta_on.assert_called()


def test_modo_5_lenta_apagada_al_transicionar():
    fase, estado, set_do = _make_fase(modo=5, pres=300.0, temp=120.0)
    fase.update()
    estado.sensores_temp["temp_camara"] = 79.0
    fase.update()
    set_do.descompresion_lenta_off.assert_called()
    set_do.descompresion_rapida_on.assert_called()
```

- [ ] **Step 4.2 — Verificar que pasan**

```
pytest tests/test_descompresion_fase.py -v
```

Esperado: 23 passed.

- [ ] **Step 4.3 — Verificar suite completa sin regresiones**

```
pytest tests/ -v
```

Esperado: todos pasan (incluyendo los 23 nuevos).

- [ ] **Step 4.4 — Commit**

```
git add tests/test_descompresion_fase.py
git commit -m "test: modos 4 y 5 de DescompresionFase (enfriamiento + descompresión)"
```

---

## Task 5: Integrar `DescompresionFase` en el pipeline de `ciclo.py`

**Files:**
- Modify: `src/autoclave/state_machine/states/ciclo.py`

- [ ] **Step 5.1 — Agregar import**

En `src/autoclave/state_machine/states/ciclo.py`, agregar al bloque de imports (después de `EsterilizacionFase`):

```python
from autoclave.state_machine.cycle_phases.descompresion import DescompresionFase
```

- [ ] **Step 5.2 — Agregar fase al pipeline**

En el método `__init__` de `CicloState`, localizar `self._fases = [...]` y agregar `DescompresionFase(*_args)` al final:

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

- [ ] **Step 5.3 — Verificar suite completa**

```
pytest tests/ -v
```

Esperado: todos pasan.

- [ ] **Step 5.4 — Commit**

```
git add src/autoclave/state_machine/states/ciclo.py
git commit -m "feat: DescompresionFase integrada al pipeline del ciclo"
```

---

## Task 6: Agregar parámetros `"descompresion"` a los JSONs de ciclos

**Files:**
- Modify: `src/autoclave/cycles/factory/instrumental_134.json`
- Modify: `src/autoclave/cycles/factory/bowe_dick.json`
- Modify: `src/autoclave/cycles/user/instrumental_134.json`
- Modify: `src/autoclave/cycles/user/bowe_dick.json`

El bloque JSON a agregar es el mismo en los 4 archivos. Insertarlo como última entrada dentro de `"parameters"`, antes del cierre `}` de ese objeto.

- [ ] **Step 6.1 — Agregar a `factory/instrumental_134.json`**

Localizar el cierre de `"esterilizacion": { ... }` y agregar una coma + el bloque nuevo:

```json
        "descompresion": {
            "modo": {
                "value": 1, "type": "int", "unit": "", "min": 0, "max": 5
            },
            "tiempo_pre_despresurizacion": {
                "value": 0, "type": "int", "unit": "sec", "min": 0, "max": 3600
            },
            "modo_1": {
                "timeout": { "value": 10,  "type": "int", "unit": "min", "min": 1, "max": 3600 }
            },
            "modo_2": {
                "timeout": { "value": 30,  "type": "int", "unit": "min", "min": 1, "max": 3600 }
            },
            "modo_3": {
                "presion_cambio": { "value": 150, "type": "int",   "unit": "kPa", "min": 0, "max": 500  },
                "timeout":        { "value": 30,  "type": "int",   "unit": "min", "min": 1, "max": 3600 }
            },
            "modo_4": {
                "presion_camara_enfriamiento": { "value": 200, "type": "int",   "unit": "kPa", "min": 0, "max": 500  },
                "temperatura_enfriamiento":    { "value": 80,  "type": "float", "unit": "°C",  "min": 0, "max": 150  },
                "tiempo_apertura_chaqueta":    { "value": 5,   "type": "int",   "unit": "sec", "min": 1, "max": 3600 },
                "tiempo_cierre_chaqueta":      { "value": 10,  "type": "int",   "unit": "sec", "min": 0, "max": 3600 },
                "timeout":                     { "value": 120, "type": "int",   "unit": "min", "min": 1, "max": 3600 }
            },
            "modo_5": {
                "presion_camara_enfriamiento": { "value": 200, "type": "int",   "unit": "kPa", "min": 0, "max": 500  },
                "temperatura_enfriamiento":    { "value": 80,  "type": "float", "unit": "°C",  "min": 0, "max": 150  },
                "tiempo_apertura_chaqueta":    { "value": 5,   "type": "int",   "unit": "sec", "min": 1, "max": 3600 },
                "tiempo_cierre_chaqueta":      { "value": 10,  "type": "int",   "unit": "sec", "min": 0, "max": 3600 },
                "timeout":                     { "value": 120, "type": "int",   "unit": "min", "min": 1, "max": 3600 }
            }
        }
```

- [ ] **Step 6.2 — Repetir para los otros 3 archivos JSON**

Hacer el mismo cambio en:
- `src/autoclave/cycles/factory/bowe_dick.json` (agregar después de `"secado": { ... }`)
- `src/autoclave/cycles/user/instrumental_134.json`
- `src/autoclave/cycles/user/bowe_dick.json`

- [ ] **Step 6.3 — Verificar JSON válido**

```
python -c "import json; [json.load(open(f)) for f in ['src/autoclave/cycles/factory/instrumental_134.json','src/autoclave/cycles/factory/bowe_dick.json','src/autoclave/cycles/user/instrumental_134.json','src/autoclave/cycles/user/bowe_dick.json']]; print('OK')"
```

Esperado: `OK`

- [ ] **Step 6.4 — Verificar suite completa**

```
pytest tests/ -v
```

Esperado: todos pasan.

- [ ] **Step 6.5 — Commit**

```
git add src/autoclave/cycles/factory/instrumental_134.json src/autoclave/cycles/factory/bowe_dick.json src/autoclave/cycles/user/instrumental_134.json src/autoclave/cycles/user/bowe_dick.json
git commit -m "feat: parámetros de descompresión agregados a los ciclos factory y user"
```

---

## Self-review

**Cobertura de spec:**
- ✅ Pre-espera con todas las salidas apagadas (Task 1)
- ✅ tiempo_pre=0 entra directo al modo (Task 1)
- ✅ Modo 0 — pasivo, sin timeout (Task 1)
- ✅ Modo 1 — descompresión rápida (Task 2)
- ✅ Modo 2 — descompresión lenta (Task 2)
- ✅ Timeout por modo con `_apagar_todo` + `FALLO` (Task 2)
- ✅ Modo 3 — combinada lenta→rapida (Task 3)
- ✅ Modo 4 — enfriamiento + descompresión final (Task 4)
- ✅ Modo 5 — igual a 4 + lenta durante enfriamiento (Task 4)
- ✅ Integración en pipeline `ciclo.py` (Task 5)
- ✅ Parámetros en 4 JSONs (Task 6)

**Tipos consistentes:**
- `cycle.get_param("descompresion", "modo_4", "timeout")` — mismo patrón de 3 claves en todos los usos ✅
- `_sub_etapa` usa los mismos literales `"lenta"/"rapida"` y `"enfriamiento"/"descompresion"` en implementación y tests ✅
- `_make_fase(extra_params=...)` permite sobrescribir parámetros individuales en los tests de modos 4/5 ✅

**Sin placeholders:** todo el código de implementación y tests está completo.

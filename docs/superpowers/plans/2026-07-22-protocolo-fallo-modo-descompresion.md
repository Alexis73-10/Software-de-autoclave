# Protocolo de Fallo con Modo de Descompresión — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cuando `ProtocoloFallo` detecta la cámara presurizada al momento de un fallo, debe despresurizar siguiendo la estrategia de válvulas del modo de descompresión configurado en el ciclo (0–5), en vez de forzar siempre `descompresion_lenta`. El caso Normal/Vacío no cambia.

**Architecture:** Se agrega el parámetro `cycle` al constructor de `ProtocoloFallo` (mismo patrón que usan las fases de `BaseFase`). Se introduce estado interno (`_modo`, `_sub_etapa`, `_t_timeout_descompresion`, `_escalado`, `_presurizado_al_disparo`) y dos métodos nuevos (`_calcular_timeout`, `_aplicar_paso_modo`) que replican la lógica de válvulas de `DescompresionFase` (sin la etapa de enfriamiento de los modos 4/5), con escalamiento a chaqueta+rápida si se agota el timeout del modo.

**Tech Stack:** Python 3.14, pytest, `unittest.mock.MagicMock`.

## Global Constraints

- El caso Normal/Vacío al disparo (`pres <= atm + rango`) no se modifica: sigue llamando exactamente `aire_admosferico_camara_on()`.
- No se modifica `DescompresionFase` ni ningún otro archivo fuera de los listados.
- Modos 4 y 5 en fallo omiten la etapa de enfriamiento: van directo a `descompresion_chaqueta_on()` + `descompresion_rapida_on()`.
- Modo 0 se fuerza a modo 2 (lenta) como salvaguarda; su timeout se toma de `modo_2.timeout` (no existe `modo_0.timeout`).
- Cada modo tiene su propio timeout (`cycle.get_param("descompresion", f"modo_{n}", "timeout")`); al agotarse sin llegar a presión atmosférica, se escala una sola vez a chaqueta+rápida.
- Referencia completa de comportamiento: `docs/superpowers/specs/2026-07-22-protocolo-fallo-modo-descompresion-design.md`.

---

### Task 1: Wire `cycle` into `ProtocoloFallo`

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`
- Modify: `src/autoclave/state_machine/states/ciclo.py:78`
- Modify: `tests/test_protocolo_fallo_reintento.py`

**Interfaces:**
- Produces: `ProtocoloFallo.__init__(self, estado, set_do, cycle, config)` — nuevo orden de parámetros (antes era `(self, estado, set_do, config)`). Nuevos atributos de instancia inicializados en `__init__` y `reset()`: `self._presurizado_al_disparo` (`bool`, default `False`), `self._modo` (`int | None`, default `None`), `self._sub_etapa` (`str | None`, default `None`), `self._t_timeout_descompresion` (`float | None`, default `None`), `self._escalado` (`bool`, default `False`).

- [ ] **Step 1: Actualizar el helper de test para el nuevo constructor**

En `tests/test_protocolo_fallo_reintento.py`, reemplazar `_make_protocolo`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo


def _make_protocolo(pres_camara=101.3):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres_camara}
    estado.sensores_temp = {"temp_camara": 25.0}
    config = MagicMock()
    config.get.return_value = None
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    return ProtocoloFallo(estado, set_do, cycle, config), set_do
```

(Los dos tests existentes en el archivo no cambian — solo el helper.)

- [ ] **Step 2: Ejecutar los tests y verificar que fallan**

Run: `python -m pytest tests/test_protocolo_fallo_reintento.py -v`
Expected: FAIL — `TypeError: ProtocoloFallo.__init__() takes 4 positional arguments but 5 were given` (el constructor actual solo acepta `estado, set_do, config`).

- [ ] **Step 3: Modificar el constructor y `reset()` de `ProtocoloFallo`**

En `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`, reemplazar:

```python
class ProtocoloFallo:

    def __init__(self, estado, set_do, config):
        self.estado  = estado
        self.set_do  = set_do
        self.config  = config
        self._ejecutado       = False
        self._buzzer_emitido  = False
        self._salidas_apagadas = False

    def reset(self):
        self._ejecutado       = False
        self._buzzer_emitido  = False
        self._salidas_apagadas = False
```

por:

```python
class ProtocoloFallo:

    def __init__(self, estado, set_do, cycle, config):
        self.estado  = estado
        self.set_do  = set_do
        self.cycle   = cycle
        self.config  = config
        self._ejecutado       = False
        self._buzzer_emitido  = False
        self._salidas_apagadas = False
        self._presurizado_al_disparo  = False
        self._modo                    = None
        self._sub_etapa                = None
        self._t_timeout_descompresion  = None
        self._escalado                 = False

    def reset(self):
        self._ejecutado       = False
        self._buzzer_emitido  = False
        self._salidas_apagadas = False
        self._presurizado_al_disparo  = False
        self._modo                    = None
        self._sub_etapa                = None
        self._t_timeout_descompresion  = None
        self._escalado                 = False
```

- [ ] **Step 4: Ejecutar los tests y verificar que pasan**

Run: `python -m pytest tests/test_protocolo_fallo_reintento.py -v`
Expected: `2 passed`

- [ ] **Step 5: Actualizar el llamador en `ciclo.py`**

En `src/autoclave/state_machine/states/ciclo.py:78`, reemplazar:

```python
        self._protocolo          = ProtocoloFallo(estado, set_do, config)
```

por:

```python
        self._protocolo          = ProtocoloFallo(estado, set_do, cycle, config)
```

- [ ] **Step 6: Ejecutar toda la suite para verificar que nada más se rompió**

Run: `python -m pytest tests/ -v -k "ciclo or protocolo_fallo"`
Expected: todos los tests existentes de `ciclo` y `protocolo_fallo` en PASSED (ningún FAIL nuevo).

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/protocolo_fallo.py src/autoclave/state_machine/states/ciclo.py tests/test_protocolo_fallo_reintento.py
git commit -m "refactor: pasar cycle a ProtocoloFallo para leer el modo de descompresion"
```

---

### Task 2: Dispatch inicial por modo en `ejecutar()`

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`
- Test: Create `tests/test_protocolo_fallo_modo_descompresion.py`

**Interfaces:**
- Consumes: `ProtocoloFallo.__init__(self, estado, set_do, cycle, config)` de la Task 1.
- Produces: `ProtocoloFallo._calcular_timeout(self) -> float` y `ProtocoloFallo._aplicar_paso_modo(self, pres: float) -> None`. Ambos son usados por `ejecutar()` en esta task y por `update()` en la Task 3.

- [ ] **Step 1: Escribir los tests fallidos para el dispatch inicial por modo**

Crear `tests/test_protocolo_fallo_modo_descompresion.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.protocolo_fallo import ProtocoloFallo


def _make_protocolo(modo, pres_camara=300.0, presion_cambio=150):
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres_camara}
    estado.sensores_temp = {"temp_camara": 25.0}
    config = MagicMock()
    config.get.return_value = None
    set_do = MagicMock()
    cycle = MagicMock()

    def get_param(*args, default=None):
        if args == ("descompresion", "modo"):
            return modo
        if args == ("descompresion", "modo_3", "presion_cambio"):
            return presion_cambio
        if len(args) == 3 and args[0] == "descompresion" and args[2] == "timeout":
            return 30
        return default

    cycle.get_param.side_effect = get_param
    return ProtocoloFallo(estado, set_do, cycle, config), set_do, cycle


def test_normal_vacio_sin_cambios():
    protocolo, set_do, cycle = _make_protocolo(modo=1, pres_camara=101.3)

    protocolo.ejecutar()

    set_do.aire_admosferico_camara_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_not_called()
    cycle.get_param.assert_not_called()


def test_modo_0_se_fuerza_a_lenta():
    protocolo, set_do, _ = _make_protocolo(modo=0)

    protocolo.ejecutar()

    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()


def test_modo_0_usa_timeout_de_modo_2():
    protocolo, set_do, cycle = _make_protocolo(modo=0)

    protocolo.ejecutar()

    cycle.get_param.assert_any_call("descompresion", "modo_2", "timeout", default=60)


def test_modo_1_activa_rapida():
    protocolo, set_do, _ = _make_protocolo(modo=1)

    protocolo.ejecutar()

    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_lenta_on.assert_not_called()


def test_modo_2_activa_lenta():
    protocolo, set_do, _ = _make_protocolo(modo=2)

    protocolo.ejecutar()

    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()


def test_modo_3_lenta_hasta_presion_cambio():
    protocolo, set_do, _ = _make_protocolo(modo=3, pres_camara=300.0, presion_cambio=150)

    protocolo.ejecutar()

    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()
    assert protocolo._sub_etapa == "lenta"


def test_modo_3_transicion_a_rapida():
    protocolo, set_do, _ = _make_protocolo(modo=3, pres_camara=140.0, presion_cambio=150)

    protocolo.ejecutar()

    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_lenta_off.assert_called_once()
    assert protocolo._sub_etapa == "rapida"


def test_modo_4_va_directo_a_final_sin_enfriamiento():
    protocolo, set_do, _ = _make_protocolo(modo=4)

    protocolo.ejecutar()

    set_do.descompresion_chaqueta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.agua_chaqueta_on.assert_not_called()
    set_do.aire_comprimido_camara_on.assert_not_called()


def test_modo_5_va_directo_a_final_sin_enfriamiento():
    protocolo, set_do, _ = _make_protocolo(modo=5)

    protocolo.ejecutar()

    set_do.descompresion_chaqueta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.agua_chaqueta_on.assert_not_called()
    set_do.aire_comprimido_camara_on.assert_not_called()
```

- [ ] **Step 2: Ejecutar los tests y verificar que fallan**

Run: `python -m pytest tests/test_protocolo_fallo_modo_descompresion.py -v`
Expected: FAIL en la mayoría — hoy `ejecutar()` siempre llama `descompresion_lenta_on()` en la rama presurizada sin importar el modo, y nunca llama `cycle.get_param`.

- [ ] **Step 3: Implementar `_calcular_timeout` y `_aplicar_paso_modo`, y usarlos en `ejecutar()`**

En `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`, reemplazar el bloque de la rama presurizada dentro de `ejecutar()`:

```python
        elif pres > atm + rango:
            # Cámara presurizada → descompresión lenta
            logger.warning(
                "Protocolo fallo: cámara presurizada (%.1f kPa) → descompresión lenta", pres
            )
            self.set_do.descompresion_lenta_on()
```

por:

```python
        elif pres > atm + rango:
            self._presurizado_al_disparo = True
            self._modo = self.cycle.get_param("descompresion", "modo", default=0) or 0
            self._sub_etapa = "lenta" if self._modo == 3 else None
            self._t_timeout_descompresion = self._calcular_timeout()
            logger.warning(
                "Protocolo fallo: cámara presurizada (%.1f kPa) → modo de descompresión %d",
                pres, self._modo
            )
            self._aplicar_paso_modo(pres)
```

Y agregar estos dos métodos nuevos a la clase (después de `ejecutar()`, antes de `update()`):

```python
    # ------------------------------------------------------------------
    # Estrategia de válvulas según el modo de descompresión del ciclo
    # ------------------------------------------------------------------

    def _calcular_timeout(self) -> float:
        timeout_key = "modo_2" if self._modo == 0 else f"modo_{self._modo}"
        timeout_min = self.cycle.get_param("descompresion", timeout_key, "timeout", default=60)
        return time.time() + (timeout_min or 60) * 60

    def _aplicar_paso_modo(self, pres: float) -> None:
        if self._escalado:
            self.set_do.descompresion_chaqueta_on()
            self.set_do.descompresion_rapida_on()
            return

        modo_efectivo = 2 if self._modo == 0 else self._modo

        if modo_efectivo == 1:
            self.set_do.descompresion_rapida_on()
        elif modo_efectivo == 2:
            self.set_do.descompresion_lenta_on()
        elif modo_efectivo == 3:
            if self._sub_etapa == "lenta":
                presion_cambio = self.cycle.get_param(
                    "descompresion", "modo_3", "presion_cambio", default=150
                )
                self.set_do.descompresion_lenta_on()
                if pres <= presion_cambio:
                    self.set_do.descompresion_lenta_off()
                    self._sub_etapa = "rapida"
            else:
                self.set_do.descompresion_rapida_on()
        elif modo_efectivo in (4, 5):
            self.set_do.descompresion_chaqueta_on()
            self.set_do.descompresion_rapida_on()
```

También agregar `import time` al inicio del archivo (junto a `import logging`), ya que `_calcular_timeout` lo usa:

```python
import time
import logging
```

- [ ] **Step 4: Ejecutar los tests y verificar que pasan**

Run: `python -m pytest tests/test_protocolo_fallo_modo_descompresion.py -v`
Expected: `9 passed`

- [ ] **Step 5: Ejecutar la suite completa de protocolo_fallo para verificar que no hay regresiones**

Run: `python -m pytest tests/test_protocolo_fallo_reintento.py tests/test_protocolo_fallo_modo_descompresion.py -v`
Expected: `11 passed`

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/protocolo_fallo.py tests/test_protocolo_fallo_modo_descompresion.py
git commit -m "feat: protocolo de fallo aplica el modo de descompresion del ciclo al disparo"
```

---

### Task 3: Ticking continuo por modo en `update()` y convergencia a aire atmosférico

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`
- Modify: `tests/test_protocolo_fallo_modo_descompresion.py`

**Interfaces:**
- Consumes: `_aplicar_paso_modo(self, pres)` y `_presurizado_al_disparo` de la Task 2/1.
- Produces: comportamiento completo de `update()` — sin nuevos métodos públicos.

- [ ] **Step 1: Escribir los tests fallidos para el ticking continuo**

Agregar a `tests/test_protocolo_fallo_modo_descompresion.py`:

```python
def test_modo_3_continua_transicion_en_update():
    # DescompresionFase (y esta réplica) apagan "lenta" y cambian de
    # sub-etapa en el tick en que se cruza presion_cambio, pero recién
    # activan "rapida" en el tick siguiente.
    protocolo, set_do, _ = _make_protocolo(modo=3, pres_camara=300.0, presion_cambio=150)
    protocolo.ejecutar()
    set_do.reset_mock()

    protocolo.estado.sensores_pres["pres_camara"] = 140.0
    protocolo.update()

    set_do.descompresion_lenta_off.assert_called_once()
    assert protocolo._sub_etapa == "rapida"

    set_do.reset_mock()
    protocolo.update()

    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_lenta_on.assert_not_called()


def test_transicion_a_presion_normal_apaga_valvulas_y_activa_atm():
    protocolo, set_do, _ = _make_protocolo(modo=1, pres_camara=300.0)
    protocolo.ejecutar()
    set_do.reset_mock()

    protocolo.estado.sensores_pres["pres_camara"] = 101.3
    protocolo.update()

    set_do.descompresion_rapida_off.assert_called_once()
    set_do.descompresion_lenta_off.assert_called_once()
    set_do.descompresion_chaqueta_off.assert_called_once()
    set_do.aire_admosferico_camara_on.assert_called_once()


def test_normal_vacio_al_disparo_update_sin_cambios():
    protocolo, set_do, _ = _make_protocolo(modo=1, pres_camara=101.3)
    protocolo.ejecutar()
    set_do.reset_mock()

    protocolo.update()

    set_do.descompresion_lenta_off.assert_not_called()
    set_do.aire_admosferico_camara_on.assert_called_once()


def test_buzzer_sin_cambios_tras_descompresion_por_modo():
    protocolo, set_do, _ = _make_protocolo(modo=1, pres_camara=300.0)
    protocolo.ejecutar()

    protocolo.estado.sensores_pres["pres_camara"] = 101.3
    protocolo.estado.sensores_temp["temp_camara"] = 25.0
    protocolo.update()

    set_do.buzer_fallo.assert_called_once()

    set_do.reset_mock()
    protocolo.update()
    set_do.buzer_fallo.assert_not_called()
```

- [ ] **Step 2: Ejecutar los tests y verificar que fallan**

Run: `python -m pytest tests/test_protocolo_fallo_modo_descompresion.py -v`
Expected: FAIL en `test_modo_3_continua_transicion_en_update` y `test_transicion_a_presion_normal_apaga_valvulas_y_activa_atm` — `update()` hoy siempre hace `descompresion_lenta_on()`/`aire_admosferico_camara_off()` o `descompresion_lenta_off()`/`aire_admosferico_camara_on()` fijo, sin considerar el modo ni apagar `rapida`/`chaqueta`.

- [ ] **Step 3: Reemplazar la gestión dinámica de presión en `update()`**

En `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`, reemplazar:

```python
        # ── Gestión dinámica de presión ───────────────────────────────
        if pres > atm + rango:
            # Sigue presurizada: mantener descompresión lenta
            self.set_do.descompresion_lenta_on()
            self.set_do.aire_admosferico_camara_off()
        else:
            # Dentro del rango normal o en vacío:
            # cerrar descompresión lenta y mantener aire atmosférico
            # para evitar caída de presión por enfriamiento
            self.set_do.descompresion_lenta_off()
            self.set_do.aire_admosferico_camara_on()
```

por:

```python
        # ── Gestión dinámica de presión ───────────────────────────────
        if pres > atm + rango:
            if self._presurizado_al_disparo:
                self._aplicar_paso_modo(pres)
            else:
                # Nunca estuvo presurizada al disparo pero subió después:
                # comportamiento heredado, sin cambios.
                self.set_do.descompresion_lenta_on()
                self.set_do.aire_admosferico_camara_off()
        else:
            # Dentro del rango normal o en vacío: cerrar todas las
            # válvulas de descompresión y mantener aire atmosférico
            # para evitar caída de presión por enfriamiento
            self.set_do.descompresion_rapida_off()
            self.set_do.descompresion_lenta_off()
            self.set_do.descompresion_chaqueta_off()
            self.set_do.aire_admosferico_camara_on()
```

- [ ] **Step 4: Ejecutar los tests y verificar que pasan**

Run: `python -m pytest tests/test_protocolo_fallo_modo_descompresion.py -v`
Expected: `13 passed`

- [ ] **Step 5: Ejecutar toda la suite de protocolo_fallo**

Run: `python -m pytest tests/test_protocolo_fallo_reintento.py tests/test_protocolo_fallo_modo_descompresion.py -v`
Expected: `15 passed`

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/protocolo_fallo.py tests/test_protocolo_fallo_modo_descompresion.py
git commit -m "feat: update() del protocolo de fallo aplica el modo de descompresion en cada tick"
```

---

### Task 4: Escalamiento por timeout

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`
- Modify: `tests/test_protocolo_fallo_modo_descompresion.py`

**Interfaces:**
- Consumes: `self._t_timeout_descompresion`, `self._escalado`, `_aplicar_paso_modo(self, pres)`.
- Produces: comportamiento final completo de `update()`.

- [ ] **Step 1: Escribir los tests fallidos para el escalamiento**

Agregar a `tests/test_protocolo_fallo_modo_descompresion.py` (usa `monkeypatch` sobre `time.time` del módulo `protocolo_fallo`):

```python
import time as time_module
import autoclave.state_machine.cycle_phases.protocolo_fallo as protocolo_fallo_module


def test_timeout_agotado_escala_a_rapida(monkeypatch):
    protocolo, set_do, _ = _make_protocolo(modo=2, pres_camara=300.0)

    t0 = 1_000_000.0
    monkeypatch.setattr(protocolo_fallo_module.time, "time", lambda: t0)
    protocolo.ejecutar()
    set_do.reset_mock()

    monkeypatch.setattr(protocolo_fallo_module.time, "time", lambda: t0 + 31 * 60)
    protocolo.update()

    assert protocolo._escalado is True
    set_do.descompresion_chaqueta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_called_once()


def test_timeout_no_agotado_no_escala():
    protocolo, set_do, _ = _make_protocolo(modo=2, pres_camara=300.0)
    protocolo.ejecutar()
    set_do.reset_mock()

    protocolo.update()

    assert protocolo._escalado is False
    set_do.descompresion_chaqueta_on.assert_not_called()
```

(`presion_cambio`/`timeout` en `_make_protocolo` ya devuelve `30` minutos para cualquier `modo_N.timeout`, ver Task 2 Step 1 — con `modo=2` el timeout es de 30 min.)

- [ ] **Step 2: Ejecutar los tests y verificar que fallan**

Run: `python -m pytest tests/test_protocolo_fallo_modo_descompresion.py::test_timeout_agotado_escala_a_rapida -v`
Expected: FAIL — `update()` hoy no comprueba `_t_timeout_descompresion` ni fija `_escalado`.

- [ ] **Step 3: Agregar la comprobación de timeout en `update()`**

En `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`, dentro del bloque `if pres > atm + rango: if self._presurizado_al_disparo:`, reemplazar:

```python
            if self._presurizado_al_disparo:
                self._aplicar_paso_modo(pres)
```

por:

```python
            if self._presurizado_al_disparo:
                if not self._escalado and time.time() > self._t_timeout_descompresion:
                    logger.error(
                        "Protocolo fallo: timeout del modo %d agotado, escalando a chaqueta+rápida",
                        self._modo,
                    )
                    self._escalado = True
                self._aplicar_paso_modo(pres)
```

- [ ] **Step 4: Ejecutar los tests y verificar que pasan**

Run: `python -m pytest tests/test_protocolo_fallo_modo_descompresion.py -v`
Expected: `15 passed`

- [ ] **Step 5: Ejecutar la suite completa del proyecto**

Run: `python -m pytest tests/ -v`
Expected: todos los tests PASSED (sin nuevos FAIL respecto al estado previo al plan).

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/protocolo_fallo.py tests/test_protocolo_fallo_modo_descompresion.py
git commit -m "feat: escalar a chaqueta+rapida si se agota el timeout del modo en protocolo de fallo"
```

---

## Resumen de archivos afectados

| Archivo | Acción |
|---------|--------|
| `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py` | Modificar (Tasks 1-4) |
| `src/autoclave/state_machine/states/ciclo.py` | Modificar (Task 1) |
| `tests/test_protocolo_fallo_reintento.py` | Modificar (Task 1) |
| `tests/test_protocolo_fallo_modo_descompresion.py` | Crear (Task 2), extender (Tasks 3-4) |

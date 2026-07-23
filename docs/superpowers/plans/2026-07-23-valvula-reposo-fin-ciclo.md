# Válvula de reposo al finalizar el ciclo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Al finalizar el ciclo (por cualquier razón: completado, cancelado, fallo, emergencia), dejar abierta la válvula de descompresión correspondiente al modo configurado, salvo que la cámara esté realmente en vacío, en cuyo caso se abre la válvula de aire atmosférico.

**Architecture:** Un módulo nuevo y puro (`valvula_reposo.py`) centraliza el mapeo modo→válvula. Se usa desde tres puntos: `DescompresionFase` (fin normal de ciclo), `ProtocoloFallo` (fallo/cancelación/emergencia — reutilizando su lógica existente `_aplicar_paso_modo` para el caso "rango normal"), y un método nuevo en `CicloState` que vigila continuamente la presión mientras se espera confirmación del operador tras un `COMPLETADO` limpio (el único camino de fin de ciclo que hoy no pasa por `ProtocoloFallo`).

**Tech Stack:** Python 3.14, pytest, `unittest.mock.MagicMock` para tests unitarios de la máquina de estados.

## Global Constraints

- Umbral de vacío real: `pres_camara < presion_admosferica - rango_presion_atm` (config `presion_admosferica` default 101.3, `rango_presion_atm` default 20.0 — mismos defaults usados en todo el proyecto).
- Mapeo modo → válvula de reposo (modo 0 se trata como modo 2, igual que ya hace `ProtocoloFallo._aplicar_paso_modo`): `1`→rápida, `2`→lenta, `3`→rápida, `4`/`5`→chaqueta+rápida.
- El estado `FALLA` (posterior a la confirmación de un fallo) queda **fuera de alcance**: no recibe vigilancia continua nueva.
- No se modifica la lógica de puertas, sensores críticos, buzzer, ni el resto del pipeline de fases.
- Spec completa: `docs/superpowers/specs/2026-07-23-valvula-reposo-fin-ciclo-design.md`.

---

### Task 1: Módulo `valvula_reposo.py`

**Files:**
- Create: `src/autoclave/state_machine/cycle_phases/valvula_reposo.py`
- Test: `tests/test_valvula_reposo.py`

**Interfaces:**
- Produces: `abrir_valvula_modo(set_do, modo: int) -> None` — abre la válvula correspondiente al modo (0 se trata como 2).
- Produces: `cerrar_valvulas_descompresion(set_do) -> None` — cierra rápida, lenta y chaqueta (no toca aire atmosférico ni aire comprimido/agua chaqueta).

- [ ] **Step 1: Escribir los tests (fallarán porque el módulo no existe)**

Crear `tests/test_valvula_reposo.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.cycle_phases.valvula_reposo import (
    abrir_valvula_modo,
    cerrar_valvulas_descompresion,
)


def test_abrir_valvula_modo_0_usa_lenta():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 0)
    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_chaqueta_on.assert_not_called()


def test_abrir_valvula_modo_1_usa_rapida():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 1)
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_lenta_on.assert_not_called()


def test_abrir_valvula_modo_2_usa_lenta():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 2)
    set_do.descompresion_lenta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()


def test_abrir_valvula_modo_3_usa_rapida():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 3)
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_lenta_on.assert_not_called()


def test_abrir_valvula_modo_4_usa_chaqueta_y_rapida():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 4)
    set_do.descompresion_chaqueta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_called_once()
    set_do.descompresion_lenta_on.assert_not_called()


def test_abrir_valvula_modo_5_usa_chaqueta_y_rapida():
    set_do = MagicMock()
    abrir_valvula_modo(set_do, 5)
    set_do.descompresion_chaqueta_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_called_once()


def test_cerrar_valvulas_descompresion_apaga_las_tres():
    set_do = MagicMock()
    cerrar_valvulas_descompresion(set_do)
    set_do.descompresion_rapida_off.assert_called_once()
    set_do.descompresion_lenta_off.assert_called_once()
    set_do.descompresion_chaqueta_off.assert_called_once()
    set_do.aire_admosferico_camara_on.assert_not_called()
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_valvula_reposo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'autoclave.state_machine.cycle_phases.valvula_reposo'`

- [ ] **Step 3: Crear el módulo**

Crear `src/autoclave/state_machine/cycle_phases/valvula_reposo.py`:

```python
# state_machine/cycle_phases/valvula_reposo.py
#
# Válvula de reposo al finalizar el ciclo: qué dejar abierto según el modo
# de descompresión configurado del ciclo (0 se trata como 2, igual que
# ProtocoloFallo._aplicar_paso_modo). No decide vacío vs. rango normal —
# eso lo resuelve cada llamador con su propia lectura de presión.


def abrir_valvula_modo(set_do, modo: int) -> None:
    modo_efectivo = 2 if modo == 0 else modo
    if modo_efectivo == 1:
        set_do.descompresion_rapida_on()
    elif modo_efectivo == 2:
        set_do.descompresion_lenta_on()
    elif modo_efectivo == 3:
        set_do.descompresion_rapida_on()
    elif modo_efectivo in (4, 5):
        set_do.descompresion_chaqueta_on()
        set_do.descompresion_rapida_on()


def cerrar_valvulas_descompresion(set_do) -> None:
    set_do.descompresion_rapida_off()
    set_do.descompresion_lenta_off()
    set_do.descompresion_chaqueta_off()
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_valvula_reposo.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/valvula_reposo.py tests/test_valvula_reposo.py
git commit -m "feat: agregar mapeo modo-valvula para el reposo de fin de ciclo"
```

---

### Task 2: `DescompresionFase` deja la válvula del modo abierta al completar

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/descompresion.py`
- Test: `tests/test_descompresion_fase.py`

**Interfaces:**
- Consumes: `abrir_valvula_modo(set_do, modo)` de Task 1 (`autoclave.state_machine.cycle_phases.valvula_reposo`).
- Produces: `DescompresionFase._finalizar() -> FaseResult` — nuevo método interno, usado por los seis `_tick_modo_*`/`_tick_sub_descompresion` en vez de `self._apagar_todo(); return FaseResult.COMPLETADO`.

Config de test ya usada en `tests/test_descompresion_fase.py`: `presion_admosferica=101.3`, `rango_presion_atm=20.0` → umbral vacío = `81.3`, umbral fin de fase = `121.3`. Los tests nuevos de vacío usan `pres=50.0` (< 81.3); los existentes que verifican "no vacío" usan `pres=121.0` (> 81.3, ya usado en el archivo).

- [ ] **Step 1: Escribir/actualizar los tests (fallarán contra el código actual)**

En `tests/test_descompresion_fase.py`, reemplazar `test_modo_1_completa_y_apaga_salidas` (líneas 99-104) por:

```python
def test_modo_1_completa_y_deja_rapida_abierta():
    fase, estado, set_do = _make_fase(modo=1, pres=121.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo_1_completa_en_vacio_cierra_rapida_y_abre_aire_atmosferico():
    fase, estado, set_do = _make_fase(modo=1, pres=50.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_called()
    set_do.aire_admosferico_camara_on.assert_called()
```

Reemplazar `test_modo_2_completa_y_apaga_salidas` (líneas 116-121) por:

```python
def test_modo_2_completa_y_deja_lenta_abierta():
    fase, estado, set_do = _make_fase(modo=2, pres=121.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_lenta_off.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo_2_completa_en_vacio_cierra_lenta_y_abre_aire_atmosferico():
    fase, estado, set_do = _make_fase(modo=2, pres=50.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_lenta_off.assert_called()
    set_do.aire_admosferico_camara_on.assert_called()
```

Después de `test_modo_0_completa_al_alcanzar_presion_atm` (línea 87), agregar:

```python
def test_modo_0_completa_fuerza_lenta_abierta():
    fase, estado, set_do = _make_fase(modo=0, pres=121.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_lenta_on.assert_called()


def test_modo_0_completa_en_vacio_abre_aire_atmosferico():
    fase, estado, set_do = _make_fase(modo=0, pres=50.0)
    fase.update()
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_lenta_on.assert_not_called()
    set_do.aire_admosferico_camara_on.assert_called()
```

Reemplazar `test_modo_3_completa_en_subetapa_rapida` (líneas 165-172) por:

```python
def test_modo_3_completa_en_subetapa_rapida():
    fase, estado, set_do = _make_fase(modo=3, pres=121.0)
    fase.update()
    fase._sub_etapa = "rapida"
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo_3_completa_en_vacio_abre_aire_atmosferico():
    fase, estado, set_do = _make_fase(modo=3, pres=50.0)
    fase.update()
    fase._sub_etapa = "rapida"
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_called()
    set_do.aire_admosferico_camara_on.assert_called()
```

Reemplazar `test_modo_4_completa_al_alcanzar_presion_atm` (líneas 252-260) por:

```python
def test_modo_4_completa_y_deja_chaqueta_rapida_abiertas():
    fase, estado, set_do = _make_fase(modo=4, pres=121.0, temp=120.0)
    fase.update()
    fase._sub_etapa = "descompresion"
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_not_called()
    set_do.descompresion_chaqueta_off.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo_4_completa_en_vacio_abre_aire_atmosferico():
    fase, estado, set_do = _make_fase(modo=4, pres=50.0, temp=120.0)
    fase.update()
    fase._sub_etapa = "descompresion"
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_called()
    set_do.descompresion_chaqueta_off.assert_called()
    set_do.aire_admosferico_camara_on.assert_called()
```

Al final del archivo (después de `test_modo_5_lenta_apagada_al_transicionar`, línea 279), agregar:

```python
def test_modo_5_completa_y_deja_chaqueta_rapida_abiertas():
    fase, estado, set_do = _make_fase(modo=5, pres=121.0, temp=120.0)
    fase.update()
    fase._sub_etapa = "descompresion"
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_not_called()
    set_do.aire_admosferico_camara_off.assert_called()


def test_modo_5_completa_en_vacio_abre_aire_atmosferico():
    fase, estado, set_do = _make_fase(modo=5, pres=50.0, temp=120.0)
    fase.update()
    fase._sub_etapa = "descompresion"
    result = fase.update()
    assert result == FaseResult.COMPLETADO
    set_do.descompresion_rapida_off.assert_called()
    set_do.aire_admosferico_camara_on.assert_called()
```

- [ ] **Step 2: Verificar que los tests nuevos/modificados fallan**

Run: `python -m pytest tests/test_descompresion_fase.py -v`
Expected: FAIL en los tests reemplazados/nuevos (siguen viendo `_apagar_todo()` cerrar todo, y `descompresion_lenta_on` nunca se llama para modo 0).

- [ ] **Step 3: Implementar `_finalizar()` y usarlo en los puntos de completado**

En `src/autoclave/state_machine/cycle_phases/descompresion.py`, agregar el import:

```python
from autoclave.state_machine.cycle_phases.base_fase import BaseFase, FaseResult
from autoclave.state_machine.cycle_phases.valvula_reposo import abrir_valvula_modo
```

Agregar el método nuevo, después de `_apagar_todo` (línea 85):

```python
    def _finalizar(self) -> FaseResult:
        p = self._pres_camara()
        if p is not None and p < self._pres_atm() - self._rango_atm():
            self._apagar_todo()
            self.set_do.aire_admosferico_camara_on()
        else:
            self.set_do.aire_admosferico_camara_off()
            abrir_valvula_modo(self.set_do, self._modo)
        return FaseResult.COMPLETADO
```

Reemplazar `_tick_modo_0` (líneas 87-90):

```python
    def _tick_modo_0(self) -> FaseResult:
        if self._en_presion_atm():
            return self._finalizar()
        return FaseResult.EN_CURSO
```

Reemplazar `_tick_modo_1` (líneas 92-97):

```python
    def _tick_modo_1(self) -> FaseResult:
        self.set_do.descompresion_rapida_on()
        if self._en_presion_atm():
            return self._finalizar()
        return FaseResult.EN_CURSO
```

Reemplazar `_tick_modo_2` (líneas 99-104):

```python
    def _tick_modo_2(self) -> FaseResult:
        self.set_do.descompresion_lenta_on()
        if self._en_presion_atm():
            return self._finalizar()
        return FaseResult.EN_CURSO
```

En `_tick_modo_3` (líneas 106-119), reemplazar el bloque `else`:

```python
        else:
            self.set_do.descompresion_rapida_on()
            if self._en_presion_atm():
                return self._finalizar()
        return FaseResult.EN_CURSO
```

En `_tick_sub_descompresion` (líneas 184-190, usada por modos 4 y 5), reemplazar:

```python
    def _tick_sub_descompresion(self) -> FaseResult:
        self.set_do.descompresion_chaqueta_on()
        self.set_do.descompresion_rapida_on()
        if self._en_presion_atm():
            return self._finalizar()
        return FaseResult.EN_CURSO
```

- [ ] **Step 4: Verificar que todos los tests del archivo pasan**

Run: `python -m pytest tests/test_descompresion_fase.py -v`
Expected: todos passed (incluye los tests preexistentes de timeout, que siguen usando `_apagar_todo()` directamente sin pasar por `_finalizar()` — no deben verse afectados)

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/descompresion.py tests/test_descompresion_fase.py
git commit -m "feat: dejar abierta la valvula del modo al completar la descompresion"
```

---

### Task 3: `ProtocoloFallo` distingue vacío real de rango normal

**Files:**
- Modify: `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`
- Test: `tests/test_protocolo_fallo_modo_descompresion.py`

**Interfaces:**
- Consumes: `_aplicar_paso_modo(pres)` (ya existente en la clase, sin cambios de firma) — se reutiliza para el caso "rango normal" tanto en `ejecutar()` como en `update()`.
- No cambia la firma pública de `ProtocoloFallo.__init__`, `ejecutar()`, ni `update()`.

Config de test ya usada en `tests/test_protocolo_fallo_modo_descompresion.py` (vía `config.get.return_value = None`, que hace caer en los defaults del código: `atm=101.3`, `rango=20.0`) → umbral vacío = `81.3`, umbral presurizado = `121.3`.

- [ ] **Step 1: Actualizar los tests (fallarán contra el código actual)**

En `tests/test_protocolo_fallo_modo_descompresion.py`, reemplazar `test_normal_vacio_sin_cambios` (líneas 29-37) por:

```python
def test_normal_sin_presion_abre_valvula_del_modo():
    protocolo, set_do, cycle = _make_protocolo(modo=1, pres_camara=101.3)

    protocolo.ejecutar()

    set_do.descompresion_rapida_on.assert_called_once()
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_vacio_real_al_disparo_abre_aire_atmosferico():
    protocolo, set_do, cycle = _make_protocolo(modo=1, pres_camara=50.0)

    protocolo.ejecutar()

    set_do.aire_admosferico_camara_on.assert_called_once()
    set_do.descompresion_rapida_on.assert_not_called()
    set_do.descompresion_lenta_on.assert_not_called()
```

Reemplazar `test_transicion_a_presion_normal_apaga_valvulas_y_activa_atm` (líneas 138-149) por:

```python
def test_transicion_a_presion_normal_deja_valvula_del_modo_abierta():
    protocolo, set_do, _ = _make_protocolo(modo=1, pres_camara=300.0)
    protocolo.ejecutar()
    set_do.reset_mock()

    protocolo.estado.sensores_pres["pres_camara"] = 101.3
    protocolo.update()

    set_do.descompresion_rapida_on.assert_called_once()
    set_do.aire_admosferico_camara_off.assert_called_once()
    set_do.aire_admosferico_camara_on.assert_not_called()


def test_transicion_a_vacio_real_cierra_valvulas_y_activa_atm():
    protocolo, set_do, _ = _make_protocolo(modo=1, pres_camara=300.0)
    protocolo.ejecutar()
    set_do.reset_mock()

    protocolo.estado.sensores_pres["pres_camara"] = 50.0
    protocolo.update()

    set_do.descompresion_rapida_off.assert_called_once()
    set_do.descompresion_lenta_off.assert_called_once()
    set_do.descompresion_chaqueta_off.assert_called_once()
    set_do.aire_admosferico_camara_on.assert_called_once()
```

Reemplazar `test_normal_vacio_al_disparo_update_sin_cambios` (líneas 152-161) por:

```python
def test_normal_sin_presion_al_disparo_update_mantiene_valvula_del_modo():
    protocolo, set_do, _ = _make_protocolo(modo=1, pres_camara=101.3)
    protocolo.ejecutar()
    set_do.reset_mock()

    protocolo.update()

    set_do.descompresion_rapida_on.assert_called_once()
    set_do.aire_admosferico_camara_on.assert_not_called()
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_protocolo_fallo_modo_descompresion.py -v`
Expected: FAIL en los tests reemplazados (el código actual todavía trata "normal" y "vacío" como un solo caso).

- [ ] **Step 3: Restructurar `ejecutar()` y `update()`**

En `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`, reemplazar el cuerpo de `ejecutar()` (líneas 58-94) completo por:

```python
    def ejecutar(self):
        if self._ejecutado:
            return

        logger.warning("Protocolo de fallo ejecutado — apagando todas las salidas")

        # 1. Todas las salidas a cero (si no hay enlace serial, esto puede no
        # confirmarse — se reintenta en update() hasta que se confirme).
        self._salidas_apagadas = self.set_do.reset_all_outputs()

        # 2. Válvula de seguridad inicial según estado de la cámara
        pres  = self.estado.sensores_pres.get("pres_camara")
        atm   = self.config.get("presion_admosferica") or 101.3
        rango = self.config.get("rango_presion_atm")   or 20.0

        if pres is None:
            logger.warning(
                "Protocolo fallo: presión desconocida — no se activa válvula de seguridad"
            )
        else:
            self._modo = self.cycle.get_param("descompresion", "modo", default=0) or 0
            self._sub_etapa = "lenta" if self._modo == 3 else None

            if pres > atm + rango:
                self._presurizado_al_disparo = True
                self._t_timeout_descompresion = self._calcular_timeout()
                logger.warning(
                    "Protocolo fallo: cámara presurizada (%.1f kPa) → modo de descompresión %d",
                    pres, self._modo
                )
                self._aplicar_paso_modo(pres)
            elif pres < atm - rango:
                # Vacío real → aire atmosférico, ninguna válvula de descompresión
                logger.warning(
                    "Protocolo fallo: cámara en vacío (%.1f kPa) → aire atmosférico", pres
                )
                self.set_do.aire_admosferico_camara_on()
            else:
                # Rango normal, sin presión que evacuar → deja la válvula
                # de descompresión del modo configurado
                logger.warning(
                    "Protocolo fallo: presión normal (%.1f kPa) → válvula del modo %d",
                    pres, self._modo
                )
                self._aplicar_paso_modo(pres)

        self._ejecutado = True
```

Reemplazar el bloque "Gestión dinámica de presión" dentro de `update()` (líneas 163-185) por:

```python
        # ── Gestión dinámica de presión ───────────────────────────────
        if pres > atm + rango:
            if self._presurizado_al_disparo:
                if not self._escalado and time.time() > self._t_timeout_descompresion:
                    logger.error(
                        "Protocolo fallo: timeout del modo %d agotado, escalando a chaqueta+rápida",
                        self._modo,
                    )
                    self._escalado = True
                self._aplicar_paso_modo(pres)
            else:
                # Nunca estuvo presurizada al disparo pero subió después:
                # comportamiento heredado, sin cambios.
                self.set_do.descompresion_lenta_on()
                self.set_do.aire_admosferico_camara_off()
        elif pres < atm - rango:
            # Vacío real → cerrar válvulas de descompresión, aire atmosférico
            self.set_do.descompresion_rapida_off()
            self.set_do.descompresion_lenta_off()
            self.set_do.descompresion_chaqueta_off()
            self.set_do.aire_admosferico_camara_on()
        else:
            # Rango normal → mantener la válvula de descompresión del modo,
            # aire atmosférico cerrado (evita cerrar en falso si la cámara
            # todavía tiene algo de presión residual, no vacío)
            self.set_do.aire_admosferico_camara_off()
            self._aplicar_paso_modo(pres)
```

- [ ] **Step 4: Verificar que todos los tests del archivo pasan**

Run: `python -m pytest tests/test_protocolo_fallo_modo_descompresion.py -v`
Expected: todos passed

- [ ] **Step 5: Correr también `test_protocolo_fallo_reintento.py` (no se modifica, pero comparte la clase)**

Run: `python -m pytest tests/test_protocolo_fallo_reintento.py -v`
Expected: todos passed sin cambios (esos tests sólo verifican el reintento de `reset_all_outputs`, no las válvulas)

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/cycle_phases/protocolo_fallo.py tests/test_protocolo_fallo_modo_descompresion.py
git commit -m "fix: protocolo de fallo distingue vacio real de rango normal al reposar"
```

---

### Task 4: `CicloState` vigila la presión mientras espera confirmación tras un COMPLETADO limpio

**Files:**
- Modify: `src/autoclave/state_machine/states/ciclo.py`
- Test: `tests/test_ciclo_valvula_reposo.py`

**Interfaces:**
- Consumes: `abrir_valvula_modo`, `cerrar_valvulas_descompresion` de Task 1.
- Produces: `CicloState._mantener_valvula_reposo() -> None` — nuevo método, invocado desde `run()` sólo cuando `self._resultado_pendiente == CicloResultado.COMPLETADO` y aún no se confirmó.

- [ ] **Step 1: Escribir los tests (fallarán porque el método no existe)**

Crear `tests/test_ciclo_valvula_reposo.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _make_ciclo():
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 25.0}
    estado.sensores_pres = {"pres_camara": 101.3}
    estado.get_flag.return_value = False

    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    alarms = MagicMock()

    ciclo = CicloState(estado, set_do, cycle, config, alarms)
    ciclo.reset()
    return ciclo, estado


def test_completado_pendiente_en_rango_normal_abre_valvula_del_modo():
    ciclo, estado = _make_ciclo()
    ciclo.cycle.get_param.side_effect = (
        lambda *a, default=None: 1 if a == ("descompresion", "modo") else default
    )
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    estado.sensores_pres["pres_camara"] = 101.3

    resultado = ciclo.run()

    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION
    ciclo.set_do.descompresion_rapida_on.assert_called()
    ciclo.set_do.aire_admosferico_camara_off.assert_called()
    ciclo.set_do.aire_admosferico_camara_on.assert_not_called()


def test_completado_pendiente_en_vacio_abre_aire_atmosferico():
    ciclo, estado = _make_ciclo()
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    estado.sensores_pres["pres_camara"] = 50.0  # < 101.3 - 20 = 81.3

    resultado = ciclo.run()

    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION
    ciclo.set_do.aire_admosferico_camara_on.assert_called()
    ciclo.set_do.descompresion_rapida_off.assert_called()
    ciclo.set_do.descompresion_lenta_off.assert_called()
    ciclo.set_do.descompresion_chaqueta_off.assert_called()


def test_fallo_pendiente_no_usa_mantener_valvula_reposo():
    ciclo, estado = _make_ciclo()
    ciclo._protocolo = MagicMock()
    ciclo._mantener_valvula_reposo = MagicMock()
    ciclo._resultado_pendiente = CicloResultado.FALLO

    resultado = ciclo.run()

    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION
    ciclo._protocolo.update.assert_called_once()
    ciclo._mantener_valvula_reposo.assert_not_called()


def test_cancelado_pendiente_no_usa_mantener_valvula_reposo():
    ciclo, estado = _make_ciclo()
    ciclo._protocolo = MagicMock()
    ciclo._mantener_valvula_reposo = MagicMock()
    ciclo._resultado_pendiente = CicloResultado.CANCELADO

    resultado = ciclo.run()

    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION
    ciclo._protocolo.update.assert_called_once()
    ciclo._mantener_valvula_reposo.assert_not_called()
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_ciclo_valvula_reposo.py -v`
Expected: FAIL — `AttributeError` (`_mantener_valvula_reposo` no existe) en los dos primeros tests; los dos últimos también fallan porque hoy `update()` del protocolo se llama siempre, pero `_mantener_valvula_reposo` no existe como atributo para reemplazar (el `MagicMock()` asignado nunca se verifica como "no llamado" correctamente sin la rama nueva — confirmarán la falta de la ramificación).

- [ ] **Step 3: Implementar el método y la ramificación en `run()`**

En `src/autoclave/state_machine/states/ciclo.py`, agregar el import junto a los existentes (línea 27, después de `from ...protocolo_fallo import ProtocoloFallo`):

```python
from autoclave.state_machine.cycle_phases.valvula_reposo import abrir_valvula_modo, cerrar_valvulas_descompresion
```

Agregar el método nuevo después de `_mantener_chaqueta` (después de la línea 167, antes del comentario `# Tick principal` de la línea 169):

```python
    def _mantener_valvula_reposo(self):
        """Mientras se espera confirmación tras un COMPLETADO limpio (sin
        ProtocoloFallo, que ya hace su propia gestión continua): si la
        cámara cae en vacío por enfriamiento, abre aire atmosférico; si no,
        mantiene la válvula de descompresión del modo configurado."""
        pres = self.estado.sensores_pres.get("pres_camara")
        if pres is None:
            return
        atm   = self.config.get("presion_admosferica") or 101.3
        rango = self.config.get("rango_presion_atm")   or 20.0

        if pres < atm - rango:
            cerrar_valvulas_descompresion(self.set_do)
            self.set_do.aire_admosferico_camara_on()
        else:
            self.set_do.aire_admosferico_camara_off()
            modo = self.cycle.get_param("descompresion", "modo", default=0) or 0
            abrir_valvula_modo(self.set_do, modo)
```

En `run()`, reemplazar el bloque (líneas 187-198):

```python
        if self._resultado_pendiente is not None:
            if self.estado.get_flag("CICLO_CONFIRMADO"):
                logger.info(
                    "CicloState: confirmación recibida → %s", self._resultado_pendiente
                )
                self.estado.set_flag("CICLO_CONFIRMADO", False)
                resultado_final = self._resultado_pendiente
                self._resultado_pendiente = None
                return resultado_final
            # Mantener el protocolo activo (gestión de presión + buzzer)
            self._protocolo.update()
            return CicloResultado.ESPERANDO_CONFIRMACION
```

por:

```python
        if self._resultado_pendiente is not None:
            if self.estado.get_flag("CICLO_CONFIRMADO"):
                logger.info(
                    "CicloState: confirmación recibida → %s", self._resultado_pendiente
                )
                self.estado.set_flag("CICLO_CONFIRMADO", False)
                resultado_final = self._resultado_pendiente
                self._resultado_pendiente = None
                return resultado_final
            # Mantener la válvula de reposo activa mientras se espera
            # confirmación: COMPLETADO limpio usa su propio monitor de
            # presión; el resto (FALLO/CANCELADO/emergencia) ya lo cubre
            # el protocolo de fallo, que corre continuamente.
            if self._resultado_pendiente == CicloResultado.COMPLETADO:
                self._mantener_valvula_reposo()
            else:
                self._protocolo.update()
            return CicloResultado.ESPERANDO_CONFIRMACION
```

- [ ] **Step 4: Verificar que todos los tests del archivo pasan**

Run: `python -m pytest tests/test_ciclo_valvula_reposo.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/ciclo.py tests/test_ciclo_valvula_reposo.py
git commit -m "feat: vigilar presion mientras se espera confirmacion tras un ciclo completado"
```

---

### Task 5: Verificación final de la suite completa

**Files:**
- (sin cambios de código — sólo verificación)

- [ ] **Step 1: Correr toda la suite de tests**

Run: `python -m pytest tests/ -v`
Expected: todos passed, sin regresiones en archivos no tocados (`test_ciclo_sensores.py`, `test_ciclo_suministro.py`, `test_ciclo_chaqueta.py`, `test_ciclos_print.py`, etc.)

- [ ] **Step 2: Si algo falla, diagnosticar antes de tocar código de producción**

Si una prueba preexistente falla, leer el mensaje completo y confirmar si es una regresión real introducida por las Tasks 1-4 o un test que asumía el comportamiento viejo y quedó fuera del alcance de esta spec (revisar contra `docs/superpowers/specs/2026-07-23-valvula-reposo-fin-ciclo-design.md`). No usar `--no-verify` ni saltarse fallas.

- [ ] **Step 3: Commit final si hubo ajustes**

```bash
git add -A
git commit -m "test: verificacion final de la suite tras valvula de reposo"
```

(Omitir este paso si el Step 1 ya pasó limpio y no hubo cambios adicionales.)

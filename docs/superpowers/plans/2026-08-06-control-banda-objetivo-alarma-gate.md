# Separar umbral de válvula, alarma y gate (chaqueta/drenaje) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que la válvula de chaqueta/drenaje reaccione al valor objetivo (no al borde de la banda), que la alarma bloqueante y el gate de listo/inicio de ciclo sigan usando la banda `objetivo±rango` sin cambiar esos umbrales, y agregar un debounce de 3 ticks para confirmar el apagado de `vapor_chaqueta`, `agua_intercambiador` y `aire_admosferico_camara`.

**Architecture:** Un módulo nuevo y puro (`control_banda.py`) con una función `evaluar_banda()` y una clase `ConfirmadorApagado()`, reusado por los 4 sitios que hoy duplican esta lógica (chaqueta/drenaje × `preparado.py`/`preparacion.py`), más el mismo patrón de debounce aplicado a `aire_admosferico_camara` en el control de presión de cámara.

**Tech Stack:** Python, pytest, unittest.mock (MagicMock).

## Global Constraints

- Válvula: reacciona al valor objetivo exacto, sin tolerancia (chaqueta: ON si `presión < objetivo`; drenaje: ON si `temp > objetivo` — sin cambios respecto a hoy).
- Alarma bloqueante y gate de listo/inicio: siguen usando la banda `objetivo ± rango`, sin cambiar esos valores de umbral.
- `rango_temp_drenaje` nuevo parámetro en `global_params.json`, valor por defecto `5` (°C).
- No hay alarma de "drenaje muy frío" — el lado bajo de la banda de drenaje solo participa del gate, nunca de una alarma.
- Debounce de apagado (3 ticks consecutivos) solo para `vapor_chaqueta`, `agua_intercambiador`, `aire_admosferico_camara`. El encendido sigue siendo inmediato. `descompresion_rapida`/`descompresion_lenta` no llevan debounce.
- No se toca `ciclo.py` (fase CICLO) ni `mantener_presion_camara()`/`igualar_presion_camara()` en cuanto a sus umbrales de banda — solo se les agrega el debounce de apagado del aire.
- Spec completa: `docs/superpowers/specs/2026-08-06-control-banda-objetivo-alarma-gate-design.md`

---

### Task 1: Módulo `control_banda.py` — `evaluar_banda()` y `ConfirmadorApagado`

**Files:**
- Create: `src/autoclave/state_machine/states/control_banda.py`
- Test: `tests/test_control_banda.py`

**Interfaces:**
- Produces: `evaluar_banda(actual: float, objetivo: float, rango: float, activar_si_bajo: bool) -> ResultadoBanda` donde `ResultadoBanda` tiene los campos `debe_activar: bool`, `fuera_por_debajo: bool`, `fuera_por_encima: bool`, `dentro_de_banda: bool`.
- Produces: `ConfirmadorApagado(ticks_requeridos: int = 3)` con métodos `.confirmar(debe_estar_apagado: bool) -> bool` y `.reset() -> None`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_control_banda.py`:

```python
from autoclave.state_machine.states.control_banda import evaluar_banda, ConfirmadorApagado


def test_evaluar_banda_activar_si_bajo_activa_bajo_objetivo():
    r = evaluar_banda(actual=95, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.debe_activar is True


def test_evaluar_banda_activar_si_bajo_no_activa_en_objetivo():
    r = evaluar_banda(actual=100, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.debe_activar is False


def test_evaluar_banda_activar_si_bajo_no_activa_sobre_objetivo():
    r = evaluar_banda(actual=105, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.debe_activar is False


def test_evaluar_banda_activar_si_bajo_fuera_por_debajo_estricto():
    r = evaluar_banda(actual=89, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.fuera_por_debajo is True
    assert r.dentro_de_banda is False


def test_evaluar_banda_activar_si_bajo_borde_inferior_no_es_fuera():
    r = evaluar_banda(actual=90, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.fuera_por_debajo is False
    assert r.dentro_de_banda is True


def test_evaluar_banda_activar_si_bajo_fuera_por_encima_estricto():
    r = evaluar_banda(actual=111, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.fuera_por_encima is True
    assert r.dentro_de_banda is False


def test_evaluar_banda_activar_si_bajo_borde_superior_no_es_fuera():
    r = evaluar_banda(actual=110, objetivo=100, rango=10, activar_si_bajo=True)
    assert r.fuera_por_encima is False
    assert r.dentro_de_banda is True


def test_evaluar_banda_activar_si_alto_activa_sobre_objetivo():
    r = evaluar_banda(actual=75, objetivo=70, rango=5, activar_si_bajo=False)
    assert r.debe_activar is True


def test_evaluar_banda_activar_si_alto_no_activa_en_objetivo():
    r = evaluar_banda(actual=70, objetivo=70, rango=5, activar_si_bajo=False)
    assert r.debe_activar is False


def test_evaluar_banda_activar_si_alto_no_activa_bajo_objetivo():
    r = evaluar_banda(actual=65, objetivo=70, rango=5, activar_si_bajo=False)
    assert r.debe_activar is False


def test_evaluar_banda_activar_si_alto_fuera_por_encima_estricto():
    r = evaluar_banda(actual=76, objetivo=70, rango=5, activar_si_bajo=False)
    assert r.fuera_por_encima is True
    assert r.dentro_de_banda is False


def test_evaluar_banda_activar_si_alto_fuera_por_debajo_estricto():
    r = evaluar_banda(actual=64, objetivo=70, rango=5, activar_si_bajo=False)
    assert r.fuera_por_debajo is True
    assert r.dentro_de_banda is False


def test_confirmador_no_confirma_en_tick_1_ni_2():
    c = ConfirmadorApagado()
    assert c.confirmar(True) is False
    assert c.confirmar(True) is False


def test_confirmador_confirma_en_tick_3():
    c = ConfirmadorApagado()
    c.confirmar(True)
    c.confirmar(True)
    assert c.confirmar(True) is True


def test_confirmador_se_resetea_si_condicion_cambia():
    c = ConfirmadorApagado()
    c.confirmar(True)
    c.confirmar(False)
    c.confirmar(True)
    assert c.confirmar(True) is False  # solo 2 consecutivos desde el reset


def test_confirmador_reset_explicito():
    c = ConfirmadorApagado()
    c.confirmar(True)
    c.confirmar(True)
    c.reset()
    assert c.confirmar(True) is False
    assert c.confirmar(True) is False


def test_confirmador_respeta_ticks_requeridos_custom():
    c = ConfirmadorApagado(ticks_requeridos=1)
    assert c.confirmar(True) is True
```

- [ ] **Step 2: Verificar que falla**

Run: `pytest tests/test_control_banda.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'autoclave.state_machine.states.control_banda'`

- [ ] **Step 3: Implementar**

Crear `src/autoclave/state_machine/states/control_banda.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ResultadoBanda:
    debe_activar: bool
    fuera_por_debajo: bool
    fuera_por_encima: bool
    dentro_de_banda: bool


def evaluar_banda(actual: float, objetivo: float, rango: float, activar_si_bajo: bool) -> ResultadoBanda:
    """Evalua un control de banda con el objetivo como umbral de valvula.

    activar_si_bajo=True  -> la valvula sube el valor (ej. vapor_chaqueta): enciende si actual < objetivo.
    activar_si_bajo=False -> la valvula baja el valor (ej. agua_intercambiador): enciende si actual > objetivo.
    """
    limite_inf = objetivo - rango
    limite_sup = objetivo + rango
    debe_activar = actual < objetivo if activar_si_bajo else actual > objetivo
    return ResultadoBanda(
        debe_activar=debe_activar,
        fuera_por_debajo=actual < limite_inf,
        fuera_por_encima=actual > limite_sup,
        dentro_de_banda=limite_inf <= actual <= limite_sup,
    )


class ConfirmadorApagado:
    """Exige N ticks consecutivos de 'debe estar apagado' antes de confirmar
    el apagado real de una salida. Solo cubre el apagado — el encendido
    reacciona de inmediato, sin pasar por aqui."""

    def __init__(self, ticks_requeridos: int = 3):
        self._ticks_requeridos = ticks_requeridos
        self._contador = 0

    def confirmar(self, debe_estar_apagado: bool) -> bool:
        if debe_estar_apagado:
            self._contador += 1
        else:
            self._contador = 0
        return self._contador >= self._ticks_requeridos

    def reset(self):
        self._contador = 0
```

- [ ] **Step 4: Verificar que pasa**

Run: `pytest tests/test_control_banda.py -v`
Expected: PASS (17 tests)

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/control_banda.py tests/test_control_banda.py
git commit -m "feat: agregar control_banda con umbral de objetivo y confirmador de apagado"
```

---

### Task 2: `preparado.py` — `mantener_chaqueta()` usa objetivo para la válvula, banda para alarma/gate

**Files:**
- Modify: `src/autoclave/state_machine/states/preparado.py`
- Test: `tests/test_preparado_chaqueta.py`

**Interfaces:**
- Consumes: `evaluar_banda`, `ConfirmadorApagado` de `autoclave.state_machine.states.control_banda` (Task 1).
- Produces: `preparado_state.mantener_chaqueta() -> bool` (sin cambio de firma; ahora significa "dentro de banda completa").

- [ ] **Step 1: Escribir el test que falla**

Reemplazar `tests/test_preparado_chaqueta.py` completo por:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.preparado import preparado_state


def _make_preparado(vapor=1, pres_chaqueta=300.0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_di = {"vapor_suministro": vapor}
    estado.sensores_pres = {"pres_chaqueta": pres_chaqueta}
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.side_effect = lambda section, key: {
        "presion_chaqueta": 300.0, "rango_presion_chaqueta": 20.0,
    }[key]
    config = MagicMock()
    config.get.return_value = 5
    p = preparado_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_sin_vapor_mantener_chaqueta_retorna_true():
    p, alarm_mgr, set_do = _make_preparado(vapor=0)
    assert p.mantener_chaqueta() is True
    set_do.vapor_chaqueta_off.assert_called()


def test_sin_vapor_alarma_no_bloqueante():
    p, alarm_mgr, _ = _make_preparado(vapor=0)
    p.mantener_chaqueta()
    alarma = alarm_mgr.report.call_args.args[0]
    assert alarma.id == "SUMINISTRO_VAPOR"
    assert alarma.blocks_operation is False


def test_con_vapor_fuera_de_banda_sigue_bloqueando():
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=100.0)
    assert p.mantener_chaqueta() is False
    set_do.vapor_chaqueta_on.assert_called()


def test_esta_preparado_true_sin_vapor_con_resto_ok():
    p, alarm_mgr, set_do = _make_preparado(vapor=0)
    p.mantener_presion_camara = lambda: True
    p.mantener_drenaje = lambda: True
    p.puertas_cerradas = lambda: True
    p.estado.get_flag.side_effect = lambda f: False
    assert p.esta_preparado() is True


def test_valvula_enciende_bajo_objetivo_sin_disparar_alarma():
    # objetivo=300, rango=20 -> limite_inf=280. 299 esta bajo el objetivo
    # pero dentro de la banda: la valvula debe reaccionar, la alarma no.
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=299.0)
    resultado = p.mantener_chaqueta()
    set_do.vapor_chaqueta_on.assert_called()
    alarm_mgr.clear.assert_any_call("CHAQUETA_FRIA")
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "CHAQUETA_FRIA" not in ids_reportados
    assert resultado is True


def test_valvula_no_enciende_en_objetivo():
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=300.0)
    p.mantener_chaqueta()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_alarma_chaqueta_fria_dispara_bajo_limite_inferior():
    # tiempo_estable_alarma=0 -> generar_alarma_temporizada dispara en la
    # primera llamada (no hay que esperar tiempo real).
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=270.0)
    p.tiempo_estable = 0
    p.mantener_chaqueta()
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "CHAQUETA_FRIA" in ids_reportados


def test_apagado_requiere_3_confirmaciones():
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=300.0)
    p.mantener_chaqueta()
    p.mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_not_called()
    p.mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()


def test_apagado_se_resetea_si_baja_antes_de_confirmar():
    p, alarm_mgr, set_do = _make_preparado(vapor=1, pres_chaqueta=300.0)
    p.mantener_chaqueta()
    p.mantener_chaqueta()
    p.estado.sensores_pres["pres_chaqueta"] = 299.0
    p.mantener_chaqueta()
    set_do.vapor_chaqueta_on.assert_called()
    p.estado.sensores_pres["pres_chaqueta"] = 300.0
    p.mantener_chaqueta()
    p.mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_not_called()
    p.mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()
```

- [ ] **Step 2: Verificar que falla**

Run: `pytest tests/test_preparado_chaqueta.py -v`
Expected: FAIL en `test_valvula_enciende_bajo_objetivo_sin_disparar_alarma` (hoy, a 299 con banda 280-320, la válvula se apaga por estar "dentro de banda" — no enciende hasta cruzar 280), `test_apagado_requiere_3_confirmaciones` y `test_apagado_se_resetea_si_baja_antes_de_confirmar` (hoy `vapor_chaqueta_off` se llama en cada tick dentro de la banda, sin confirmación). `test_valvula_no_enciende_en_objetivo` y `test_alarma_chaqueta_fria_dispara_bajo_limite_inferior` deben pasar ya (mismo umbral que hoy) — quedan como cobertura de regresión. Los demás deben seguir en PASS.

- [ ] **Step 3: Implementar**

En `src/autoclave/state_machine/states/preparado.py`, modificar el bloque de imports:

```python
from autoclave.state_machine.alarms.alarm import Alarm, AlarmType
from autoclave.state_machine.states.control_banda import evaluar_banda, ConfirmadorApagado
import logging
import time
```

En `__init__`, después de `self.timer_estabilidad = None`:

```python
        # Timer de estabilidad
        self.timer_estabilidad = None

        # Confirmadores de apagado (evitan chattering de valvula)
        self._confirmador_chaqueta = ConfirmadorApagado()
```

Reemplazar el método `mantener_chaqueta()` completo por:

```python
    def mantener_chaqueta(self):
        press_chaqueta = self.estado.sensores_pres["pres_chaqueta"]
        press_obj = self.cycle.get_param("globals", "presion_chaqueta")
        rango=self.cycle.get_param("globals","rango_presion_chaqueta")

        # Suministro. Sin vapor, no insistir en abrir la válvula: se deja
        # "pendiente", no bloqueante (no debe frenar esta_preparado()).
        if not self.estado.sensores_di["vapor_suministro"]:
            self.set_do.vapor_chaqueta_off()
            self._confirmador_chaqueta.reset()
            self.alarm("SUMINISTRO_VAPOR", AlarmType.ALERTA, blocks_operation=False)
            self.alarm_manager.clear("CHAQUETA_FRIA")
            self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")
            return True
        else:
            self.alarm_manager.clear("SUMINISTRO_VAPOR")

        r = evaluar_banda(press_chaqueta, press_obj, rango, activar_si_bajo=True)

        # Válvula: reacciona en el objetivo, sin esperar a cruzar la banda.
        if r.debe_activar:
            self.set_do.vapor_chaqueta_on()
            self._confirmador_chaqueta.reset()
        elif self._confirmador_chaqueta.confirmar(True):
            self.set_do.vapor_chaqueta_off()

        # Alarma bloqueante: solo al cruzar el borde de la banda.
        if r.fuera_por_debajo:
            self.generar_alarma_temporizada("CHAQUETA_FRIA")
        else:
            self.alarm_manager.clear("CHAQUETA_FRIA")

        if r.fuera_por_encima:
            self.generar_alarma_temporizada("CHAQUETA_SOBRECALENTADA")
        else:
            self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")

        return r.dentro_de_banda
```

- [ ] **Step 4: Verificar que pasa**

Run: `pytest tests/test_preparado_chaqueta.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/preparado.py tests/test_preparado_chaqueta.py
git commit -m "feat: separar umbral de valvula y alarma en mantener_chaqueta (preparado)"
```

---

### Task 3: `preparado.py` — `mantener_drenaje()` con banda nueva (`rango_temp_drenaje`)

**Files:**
- Modify: `src/autoclave/state_machine/states/preparado.py`
- Modify: `src/autoclave/config/global_params.json`
- Test: `tests/test_preparado_drenaje.py` (crear)

**Interfaces:**
- Consumes: `evaluar_banda`, `ConfirmadorApagado` (Task 1).
- Produces: `preparado_state.mantener_drenaje() -> bool` (sin cambio de firma; ahora significa "dentro de banda completa").

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_preparado_drenaje.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.preparado import preparado_state


def _make_preparado(temp_drenaje, temp_segura=70.0, rango=5.0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_temp = {"temp_drenaje": temp_drenaje}
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    config.get.side_effect = lambda key: {
        "temp_segura_drenaje": temp_segura,
        "rango_temp_drenaje": rango,
        "tiempo_estable_alarma": 5,
    }[key]
    p = preparado_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_valvula_no_enciende_en_objetivo():
    p, alarm_mgr, set_do = _make_preparado(temp_drenaje=70.0)
    p.mantener_drenaje()
    set_do.agua_intercambiador_on.assert_not_called()


def test_valvula_enciende_sobre_objetivo_sin_disparar_alarma():
    # objetivo=70, rango=5 -> limite_sup=75. 71 esta sobre el objetivo pero
    # dentro de la banda: la valvula debe reaccionar, la alarma no.
    p, alarm_mgr, set_do = _make_preparado(temp_drenaje=71.0)
    resultado = p.mantener_drenaje()
    set_do.agua_intercambiador_on.assert_called()
    alarm_mgr.clear.assert_any_call("TEMP_DRENAJE_ALTA")
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "TEMP_DRENAJE_ALTA" not in ids_reportados
    assert resultado is True


def test_alarma_dispara_sobre_limite_superior():
    p, alarm_mgr, set_do = _make_preparado(temp_drenaje=76.0)
    p.tiempo_estable = 0
    p.mantener_drenaje()
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "TEMP_DRENAJE_ALTA" in ids_reportados


def test_gate_false_bajo_limite_inferior_de_banda_sin_alarma():
    # objetivo=70, rango=5 -> limite_inf=65. Sin accion fisica de "muy frio",
    # pero el gate de listo/inicio si exige estar dentro de la banda completa.
    p, alarm_mgr, set_do = _make_preparado(temp_drenaje=60.0)
    resultado = p.mantener_drenaje()
    assert resultado is False
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "TEMP_DRENAJE_ALTA" not in ids_reportados


def test_apagado_requiere_3_confirmaciones():
    p, alarm_mgr, set_do = _make_preparado(temp_drenaje=70.0)
    p.mantener_drenaje()
    p.mantener_drenaje()
    set_do.agua_intercambiador_off.assert_not_called()
    p.mantener_drenaje()
    set_do.agua_intercambiador_off.assert_called_once()


def test_apagado_se_resetea_si_sube_antes_de_confirmar():
    p, alarm_mgr, set_do = _make_preparado(temp_drenaje=70.0)
    p.mantener_drenaje()
    p.mantener_drenaje()
    p.estado.sensores_temp["temp_drenaje"] = 71.0
    p.mantener_drenaje()
    set_do.agua_intercambiador_on.assert_called()
    p.estado.sensores_temp["temp_drenaje"] = 70.0
    p.mantener_drenaje()
    p.mantener_drenaje()
    set_do.agua_intercambiador_off.assert_not_called()
    p.mantener_drenaje()
    set_do.agua_intercambiador_off.assert_called_once()
```

- [ ] **Step 2: Verificar que falla**

Run: `pytest tests/test_preparado_drenaje.py -v`
Expected: FAIL en `test_valvula_enciende_sobre_objetivo_sin_disparar_alarma` (hoy no limpia la alarma en la rama de encendido y retorna `False` en vez de `True`), `test_gate_false_bajo_limite_inferior_de_banda_sin_alarma` (hoy no existe piso — `60.0 <= 70.0` retorna `True`), `test_apagado_requiere_3_confirmaciones` y `test_apagado_se_resetea_si_sube_antes_de_confirmar` (hoy `agua_intercambiador_off` se llama en cada tick sin confirmación). `test_valvula_no_enciende_en_objetivo` debe pasar ya. No hay `KeyError`: el código viejo simplemente no consulta `rango_temp_drenaje` todavía, así que la clave de más en el fixture es inofensiva.

- [ ] **Step 3: Implementar**

En `src/autoclave/config/global_params.json`, agregar después de `"temp_segura_drenaje"`:

```json
    "temp_segura_drenaje": {"value":70, "type":"int", "unit":"°C"},
    "rango_temp_drenaje": {"value":5, "type":"int", "unit":"°C"},
```

En `src/autoclave/state_machine/states/preparado.py`, en `__init__`, después de `self._confirmador_chaqueta = ConfirmadorApagado()`:

```python
        self._confirmador_chaqueta = ConfirmadorApagado()
        self._confirmador_drenaje = ConfirmadorApagado()
```

Reemplazar el método `mantener_drenaje()` completo por:

```python
    def mantener_drenaje(self):
        temp = self.estado.sensores_temp["temp_drenaje"]
        temp_obj = self.config.get("temp_segura_drenaje")
        rango = self.config.get("rango_temp_drenaje")

        r = evaluar_banda(temp, temp_obj, rango, activar_si_bajo=False)

        # Válvula: reacciona en el objetivo, sin esperar a cruzar la banda.
        if r.debe_activar:
            self.set_do.agua_intercambiador_on()
            self._confirmador_drenaje.reset()
        elif self._confirmador_drenaje.confirmar(True):
            self.set_do.agua_intercambiador_off()

        # Alarma bloqueante: solo al cruzar el borde superior de la banda.
        # No hay alarma de lado bajo: no existe accion fisica para "drenaje
        # muy frio" (no hay calefactor), pero el lado bajo si participa del
        # gate de listo/inicio via dentro_de_banda.
        if r.fuera_por_encima:
            self.generar_alarma_temporizada("TEMP_DRENAJE_ALTA")
        else:
            self.alarm_manager.clear("TEMP_DRENAJE_ALTA")

        return r.dentro_de_banda
```

- [ ] **Step 4: Verificar que pasa**

Run: `pytest tests/test_preparado_drenaje.py -v`
Expected: PASS (6 tests)

También correr la suite completa de `preparado` para confirmar que nada más se rompió:

Run: `pytest tests/test_preparado_chaqueta.py tests/test_preparado_suministro.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/preparado.py src/autoclave/config/global_params.json tests/test_preparado_drenaje.py
git commit -m "feat: agregar banda a mantener_drenaje (preparado) con rango_temp_drenaje"
```

---

### Task 4: `preparado.py` — debounce de apagado en `mantener_presion_camara()`

**Files:**
- Modify: `src/autoclave/state_machine/states/preparado.py`
- Test: `tests/test_preparado_presion_camara.py` (crear)

**Interfaces:**
- Consumes: `ConfirmadorApagado` (Task 1).
- Produces: `preparado_state.mantener_presion_camara() -> bool` (sin cambio de firma ni de umbrales de banda).

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_preparado_presion_camara.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.preparado import preparado_state


def _make_preparado(pres_camara, presion_admosferica=1013.0, rango=5.0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_pres = {"pres_camara": pres_camara}
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    config.get.side_effect = lambda key: {
        "presion_admosferica": presion_admosferica,
        "rango_presion_atm": rango,
        "tiempo_estable_alarma": 5,
    }[key]
    p = preparado_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_presion_en_banda_retorna_true():
    p, alarm_mgr, set_do = _make_preparado(pres_camara=1013.0)
    assert p.mantener_presion_camara() is True


def test_presion_baja_enciende_aire_de_inmediato():
    p, alarm_mgr, set_do = _make_preparado(pres_camara=1000.0)
    assert p.mantener_presion_camara() is False
    set_do.aire_admosferico_camara_on.assert_called_once()


def test_apagado_aire_requiere_3_confirmaciones():
    p, alarm_mgr, set_do = _make_preparado(pres_camara=1013.0)
    p.mantener_presion_camara()
    p.mantener_presion_camara()
    set_do.aire_admosferico_camara_off.assert_not_called()
    p.mantener_presion_camara()
    set_do.aire_admosferico_camara_off.assert_called_once()


def test_apagado_aire_se_resetea_si_baja_antes_de_confirmar():
    p, alarm_mgr, set_do = _make_preparado(pres_camara=1013.0)
    p.mantener_presion_camara()
    p.mantener_presion_camara()
    p.estado.sensores_pres["pres_camara"] = 1000.0
    p.mantener_presion_camara()
    set_do.aire_admosferico_camara_on.assert_called()
    p.estado.sensores_pres["pres_camara"] = 1013.0
    p.mantener_presion_camara()
    p.mantener_presion_camara()
    set_do.aire_admosferico_camara_off.assert_not_called()
    p.mantener_presion_camara()
    set_do.aire_admosferico_camara_off.assert_called_once()
```

- [ ] **Step 2: Verificar que falla**

Run: `pytest tests/test_preparado_presion_camara.py -v`
Expected: FAIL en `test_apagado_aire_requiere_3_confirmaciones` y `test_apagado_aire_se_resetea_si_baja_antes_de_confirmar` (hoy `aire_admosferico_camara_off` se llama en cada tick, sin confirmación).

- [ ] **Step 3: Implementar**

En `src/autoclave/state_machine/states/preparado.py`, en `__init__`, después de `self._confirmador_drenaje = ConfirmadorApagado()`:

```python
        self._confirmador_drenaje = ConfirmadorApagado()
        self._confirmador_aire_camara = ConfirmadorApagado()
```

Reemplazar el método `mantener_presion_camara()` completo por:

```python
    def mantener_presion_camara(self):
        presion_camara = self.estado.sensores_pres["pres_camara"]
        pres_atm = self.config.get("presion_admosferica")
        rango = self.config.get("rango_presion_atm")

        min_p = pres_atm - rango
        max_p = pres_atm + rango

        if min_p <= presion_camara <= max_p:
            if self._confirmador_aire_camara.confirmar(True):
                self.set_do.aire_admosferico_camara_off()
            self.set_do.descompresion_rapida_off()
            self.alarm_manager.clear("PRESION_CAMARA_BAJA")
            self.alarm_manager.clear("PRESION_CAMARA_ALTA")
            return True

        if presion_camara < min_p:
            self.set_do.aire_admosferico_camara_on()
            self._confirmador_aire_camara.reset()
            self.set_do.descompresion_rapida_off()
            self.generar_alarma_temporizada("PRESION_CAMARA_BAJA")

        elif presion_camara > max_p:
            self.set_do.aire_admosferico_camara_off()
            self._confirmador_aire_camara.reset()
            self.set_do.descompresion_rapida_on()
            self.generar_alarma_temporizada("PRESION_CAMARA_ALTA")

        return False
```

- [ ] **Step 4: Verificar que pasa**

Run: `pytest tests/test_preparado_presion_camara.py -v`
Expected: PASS (4 tests)

Correr toda la suite de `preparado` una vez más:

Run: `pytest tests/test_preparado_chaqueta.py tests/test_preparado_drenaje.py tests/test_preparado_suministro.py tests/test_preparado_presion_camara.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/preparado.py tests/test_preparado_presion_camara.py
git commit -m "feat: debounce de apagado para aire_admosferico_camara (preparado)"
```

---

### Task 5: `preparacion.py` — `suministrar_vapor_chaqueta()` usa objetivo para la válvula, banda para alarma/gate

**Files:**
- Modify: `src/autoclave/state_machine/states/preparacion.py`
- Test: `tests/test_preparacion_chaqueta.py`

**Interfaces:**
- Consumes: `evaluar_banda`, `ConfirmadorApagado` (Task 1).
- Produces: `preparacion_state.suministrar_vapor_chaqueta() -> bool` (sin cambio de firma).

- [ ] **Step 1: Escribir el test que falla**

Reemplazar `tests/test_preparacion_chaqueta.py` completo por:

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


def test_valvula_enciende_bajo_objetivo_sin_disparar_alarma():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=299.0)
    resultado = p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_on.assert_called()
    alarm_mgr.clear.assert_any_call("CHAQUETA_FRIA")
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "CHAQUETA_FRIA" not in ids_reportados
    assert resultado is True


def test_valvula_no_enciende_en_objetivo():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=300.0)
    p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_on.assert_not_called()


def test_alarma_chaqueta_fria_dispara_bajo_limite_inferior():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=270.0)
    p.suministrar_vapor_chaqueta()
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "CHAQUETA_FRIA" in ids_reportados


def test_apagado_requiere_3_confirmaciones():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=300.0)
    p.suministrar_vapor_chaqueta()
    p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_off.assert_not_called()
    p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()


def test_apagado_se_resetea_si_baja_antes_de_confirmar():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=300.0)
    p.suministrar_vapor_chaqueta()
    p.suministrar_vapor_chaqueta()
    p.estado.sensores_pres["pres_chaqueta"] = 299.0
    p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_on.assert_called()
    p.estado.sensores_pres["pres_chaqueta"] = 300.0
    p.suministrar_vapor_chaqueta()
    p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_off.assert_not_called()
    p.suministrar_vapor_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()
```

- [ ] **Step 2: Verificar que falla**

Run: `pytest tests/test_preparacion_chaqueta.py -v`
Expected: FAIL en `test_valvula_enciende_bajo_objetivo_sin_disparar_alarma` (hoy, dentro de la banda 280-320, la válvula se apaga en vez de encender), `test_apagado_requiere_3_confirmaciones` y `test_apagado_se_resetea_si_baja_antes_de_confirmar` (hoy `vapor_chaqueta_off` se llama en cada tick sin confirmación). `test_valvula_no_enciende_en_objetivo` y `test_alarma_chaqueta_fria_dispara_bajo_limite_inferior` deben pasar ya (mismo umbral que hoy). Los demás deben seguir en PASS.

- [ ] **Step 3: Implementar**

En `src/autoclave/state_machine/states/preparacion.py`, modificar el bloque de imports:

```python
from autoclave.state_machine.machine.parametros_globales import parametros_globales
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType 
from autoclave.state_machine.states.control_banda import evaluar_banda, ConfirmadorApagado
import logging
```

En `__init__`, agregar después de `self.config = config`:

```python
class preparacion_state:
    def __init__(self, alarm_manager, estado, set_do, cycle, config):
        self.alarm_manager = alarm_manager
        self.estado = estado
        self.set_do = set_do
        self.cycle = cycle
        self.config = config

        # Confirmadores de apagado (evitan chattering de valvula)
        self._confirmador_chaqueta = ConfirmadorApagado()
```

Reemplazar el método `suministrar_vapor_chaqueta()` completo por:

```python
    def suministrar_vapor_chaqueta(self):
            presion = self.estado.sensores_pres["pres_chaqueta"]
            pres_obj=self.cycle.get_param("globals","presion_chaqueta")
            rango=self.cycle.get_param("globals","rango_presion_chaqueta")

            # Verificar suministro. Si no hay vapor, no insistir en abrir la
            # válvula (generaría vapor demasiado húmedo por baja presión de
            # línea): se deja "pendiente", no bloqueante.
            if not self.estado.sensores_di["vapor_suministro"]:
                self.set_do.vapor_chaqueta_off()
                self._confirmador_chaqueta.reset()
                self.alarm("SUMINISTRO_VAPOR", AlarmType.ALERTA, blocks_operation=False)
                self.alarm_manager.clear("CHAQUETA_FRIA")
                self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")
                return True
            else:
                self.alarm_manager.clear("SUMINISTRO_VAPOR")

            r = evaluar_banda(presion, pres_obj, rango, activar_si_bajo=True)

            # Válvula: reacciona en el objetivo, sin esperar a cruzar la banda.
            if r.debe_activar:
                self.set_do.vapor_chaqueta_on()
                self._confirmador_chaqueta.reset()
            elif self._confirmador_chaqueta.confirmar(True):
                self.set_do.vapor_chaqueta_off()

            # Alarma bloqueante: solo al cruzar el borde de la banda.
            if r.fuera_por_debajo:
                alarm_id = "CHAQUETA_FRIA"
                self.alarm(alarm_id, AlarmType.ALERTA)
            else:
                self.alarm_manager.clear("CHAQUETA_FRIA")

            if r.fuera_por_encima:
                alarm_id = "CHAQUETA_SOBRECALENTADA"
                self.alarm(alarm_id, AlarmType.ALERTA)
            else:
                self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")

            return r.dentro_de_banda
```

- [ ] **Step 4: Verificar que pasa**

Run: `pytest tests/test_preparacion_chaqueta.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/preparacion.py tests/test_preparacion_chaqueta.py
git commit -m "feat: separar umbral de valvula y alarma en suministrar_vapor_chaqueta (preparacion)"
```

---

### Task 6: `preparacion.py` — `verificar_temperatura_drenaje()` con banda nueva

**Files:**
- Modify: `src/autoclave/state_machine/states/preparacion.py`
- Modify: `tests/test_preparacion_ejecutor_paralelo.py` (agregar `rango_temp_drenaje` al fixture existente)
- Test: `tests/test_preparacion_temperatura_drenaje.py` (crear)

**Interfaces:**
- Consumes: `evaluar_banda`, `ConfirmadorApagado` (Task 1).
- Produces: `preparacion_state.verificar_temperatura_drenaje() -> bool` (sin cambio de firma).

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_preparacion_temperatura_drenaje.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.preparacion import preparacion_state


def _make_preparacion(temp_drenaje, temp_segura=70.0, rango=5.0):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_temp = {"temp_drenaje": temp_drenaje}
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    config.get.side_effect = lambda key: {
        "temp_segura_drenaje": temp_segura,
        "rango_temp_drenaje": rango,
    }[key]
    p = preparacion_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager, set_do


def test_valvula_no_enciende_en_objetivo():
    p, alarm_mgr, set_do = _make_preparacion(temp_drenaje=70.0)
    p.verificar_temperatura_drenaje()
    set_do.agua_intercambiador_on.assert_not_called()


def test_valvula_enciende_sobre_objetivo_sin_disparar_alarma():
    p, alarm_mgr, set_do = _make_preparacion(temp_drenaje=71.0)
    resultado = p.verificar_temperatura_drenaje()
    set_do.agua_intercambiador_on.assert_called()
    alarm_mgr.clear.assert_any_call("TEMPERATURA_DRENAJE_ALTA")
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "TEMPERATURA_DRENAJE_ALTA" not in ids_reportados
    assert resultado is True


def test_alarma_dispara_sobre_limite_superior():
    p, alarm_mgr, set_do = _make_preparacion(temp_drenaje=76.0)
    p.verificar_temperatura_drenaje()
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "TEMPERATURA_DRENAJE_ALTA" in ids_reportados


def test_gate_false_bajo_limite_inferior_de_banda_sin_alarma():
    p, alarm_mgr, set_do = _make_preparacion(temp_drenaje=60.0)
    resultado = p.verificar_temperatura_drenaje()
    assert resultado is False
    ids_reportados = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "TEMPERATURA_DRENAJE_ALTA" not in ids_reportados


def test_apagado_requiere_3_confirmaciones():
    p, alarm_mgr, set_do = _make_preparacion(temp_drenaje=70.0)
    p.verificar_temperatura_drenaje()
    p.verificar_temperatura_drenaje()
    set_do.agua_intercambiador_off.assert_not_called()
    p.verificar_temperatura_drenaje()
    set_do.agua_intercambiador_off.assert_called_once()


def test_apagado_se_resetea_si_sube_antes_de_confirmar():
    p, alarm_mgr, set_do = _make_preparacion(temp_drenaje=70.0)
    p.verificar_temperatura_drenaje()
    p.verificar_temperatura_drenaje()
    p.estado.sensores_temp["temp_drenaje"] = 71.0
    p.verificar_temperatura_drenaje()
    set_do.agua_intercambiador_on.assert_called()
    p.estado.sensores_temp["temp_drenaje"] = 70.0
    p.verificar_temperatura_drenaje()
    p.verificar_temperatura_drenaje()
    set_do.agua_intercambiador_off.assert_not_called()
    p.verificar_temperatura_drenaje()
    set_do.agua_intercambiador_off.assert_called_once()
```

En `tests/test_preparacion_ejecutor_paralelo.py`, en `test_valvula_abre_con_funciones_reales_presion_alta_sin_agua_residual`, el `config.get.side_effect` no incluye `rango_temp_drenaje` — hay que agregarlo para que no reviente con `KeyError` (esa prueba llama a `verificar_temperatura_drenaje()` real, sin mockear):

```python
    config.get.side_effect = lambda key: {
        "presion_admosferica": 1013.0,
        "rango_presion_atm": 5.0,
        "temp_segura_drenaje": 40.0,
        "rango_temp_drenaje": 5.0,
    }[key]
```

- [ ] **Step 2: Verificar que falla**

Run: `pytest tests/test_preparacion_temperatura_drenaje.py tests/test_preparacion_ejecutor_paralelo.py -v`
Expected: FAIL en `test_valvula_enciende_sobre_objetivo_sin_disparar_alarma` (hoy no limpia la alarma en la rama de encendido, la reporta de inmediato sin tolerancia de banda, y retorna `False` en vez de `True`), `test_gate_false_bajo_limite_inferior_de_banda_sin_alarma` (hoy no existe piso — `60.0 <= 70.0` retorna `True`), `test_apagado_requiere_3_confirmaciones` y `test_apagado_se_resetea_si_sube_antes_de_confirmar` (hoy `agua_intercambiador_off` se llama en cada tick sin confirmación). `test_valvula_no_enciende_en_objetivo` y `test_alarma_dispara_sobre_limite_superior` deben pasar ya. `test_preparacion_ejecutor_paralelo.py` debe seguir en PASS completo (el fixture ya trae la clave nueva, y el código viejo tampoco la consulta, así que no hay `KeyError`).

- [ ] **Step 3: Implementar**

En `src/autoclave/state_machine/states/preparacion.py`, en `__init__`, después de `self._confirmador_chaqueta = ConfirmadorApagado()`:

```python
        self._confirmador_chaqueta = ConfirmadorApagado()
        self._confirmador_drenaje = ConfirmadorApagado()
```

Reemplazar el método `verificar_temperatura_drenaje()` completo por:

```python
    def verificar_temperatura_drenaje(self):
            temp_drenaje = self.estado.sensores_temp["temp_drenaje"]
            temp_obj = self.config.get("temp_segura_drenaje")
            rango = self.config.get("rango_temp_drenaje")

            r = evaluar_banda(temp_drenaje, temp_obj, rango, activar_si_bajo=False)

            # Válvula: reacciona en el objetivo, sin esperar a cruzar la banda.
            if r.debe_activar:
                self.set_do.agua_intercambiador_on()
                self._confirmador_drenaje.reset()
            elif self._confirmador_drenaje.confirmar(True):
                self.set_do.agua_intercambiador_off()

            # Alarma bloqueante: solo al cruzar el borde superior de la banda.
            # No hay alarma de lado bajo: no existe accion fisica para
            # "drenaje muy frio", pero el lado bajo si participa del gate de
            # listo/inicio via dentro_de_banda.
            if r.fuera_por_encima:
                alarm_id = "TEMPERATURA_DRENAJE_ALTA"
                self.alarm(alarm_id, AlarmType.ALERTA)
            else:
                self.alarm_manager.clear("TEMPERATURA_DRENAJE_ALTA")

            return r.dentro_de_banda
```

- [ ] **Step 4: Verificar que pasa**

Run: `pytest tests/test_preparacion_temperatura_drenaje.py tests/test_preparacion_ejecutor_paralelo.py tests/test_preparacion_chaqueta.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/preparacion.py tests/test_preparacion_temperatura_drenaje.py tests/test_preparacion_ejecutor_paralelo.py
git commit -m "feat: agregar banda a verificar_temperatura_drenaje (preparacion)"
```

---

### Task 7: `preparacion.py` — debounce de apagado en `igualar_presion_camara()`

**Files:**
- Modify: `src/autoclave/state_machine/states/preparacion.py`
- Modify: `tests/test_preparacion_presion_camara.py`

**Interfaces:**
- Consumes: `ConfirmadorApagado` (Task 1).
- Produces: `preparacion_state.igualar_presion_camara() -> tuple[bool, bool]` (sin cambio de firma ni de umbrales de banda).

- [ ] **Step 1: Escribir el test que falla**

Reemplazar `tests/test_preparacion_presion_camara.py` completo por:

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
    p.igualar_presion_camara()
    p.igualar_presion_camara()
    ok, quiere_rapida = p.igualar_presion_camara()
    assert ok is True
    assert quiere_rapida is False
    set_do.aire_admosferico_camara_off.assert_called_once()
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


def test_apagado_aire_requiere_3_confirmaciones():
    p, alarm_mgr, set_do = _make_preparacion(pres_camara=1013.0)
    p.igualar_presion_camara()
    p.igualar_presion_camara()
    set_do.aire_admosferico_camara_off.assert_not_called()
    p.igualar_presion_camara()
    set_do.aire_admosferico_camara_off.assert_called_once()


def test_apagado_aire_se_resetea_si_baja_antes_de_confirmar():
    p, alarm_mgr, set_do = _make_preparacion(pres_camara=1013.0)
    p.igualar_presion_camara()
    p.igualar_presion_camara()
    p.estado.sensores_pres["pres_camara"] = 1000.0
    p.igualar_presion_camara()
    set_do.aire_admosferico_camara_on.assert_called()
    p.estado.sensores_pres["pres_camara"] = 1013.0
    p.igualar_presion_camara()
    p.igualar_presion_camara()
    set_do.aire_admosferico_camara_off.assert_not_called()
    p.igualar_presion_camara()
    set_do.aire_admosferico_camara_off.assert_called_once()
```

- [ ] **Step 2: Verificar que falla**

Run: `pytest tests/test_preparacion_presion_camara.py -v`
Expected: FAIL en `test_presion_en_banda_ok_sin_pedir_rapida` (hoy llama a `aire_admosferico_camara_off` en cada tick, la nueva aserción `assert_called_once()` tras 3 llamadas fallaría por exceso de llamadas) y en `test_apagado_aire_requiere_3_confirmaciones`/`test_apagado_aire_se_resetea_si_baja_antes_de_confirmar` (sin confirmación todavía).

- [ ] **Step 3: Implementar**

En `src/autoclave/state_machine/states/preparacion.py`, en `__init__`, después de `self._confirmador_drenaje = ConfirmadorApagado()`:

```python
        self._confirmador_drenaje = ConfirmadorApagado()
        self._confirmador_aire_camara = ConfirmadorApagado()
```

Reemplazar el método `igualar_presion_camara()` completo por:

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
                if self._confirmador_aire_camara.confirmar(True):
                    self.set_do.aire_admosferico_camara_off()
                self.set_do.descompresion_lenta_off()
                self.alarm_manager.clear("PRESION_CAMARA_BAJA")
                self.alarm_manager.clear("PRESION_CAMARA_ALTA")
                return True, False

            if presion_camara < pres_cam_min:
                # Abrir entrada de aire comprimido a la camara
                self.set_do.aire_admosferico_camara_on()
                self._confirmador_aire_camara.reset()
                alarm_id = "PRESION_CAMARA_BAJA"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False, False

            # presion_camara > pres_cam_max: requiere venteo/vacío
            self.set_do.aire_admosferico_camara_off()
            self._confirmador_aire_camara.reset()
            alarm_id = "PRESION_CAMARA_ALTA"
            self.alarm(alarm_id, AlarmType.ALERTA)
            return False, True
```

- [ ] **Step 4: Verificar que pasa**

Run: `pytest tests/test_preparacion_presion_camara.py -v`
Expected: PASS (5 tests)

Correr toda la suite de `preparacion` y `preparado` para confirmar que nada se rompió:

Run: `pytest tests/test_preparacion_chaqueta.py tests/test_preparacion_temperatura_drenaje.py tests/test_preparacion_presion_camara.py tests/test_preparacion_drenaje.py tests/test_preparacion_suministro.py tests/test_preparacion_alarm_wording.py tests/test_preparacion_ejecutor_paralelo.py tests/test_preparado_chaqueta.py tests/test_preparado_drenaje.py tests/test_preparado_presion_camara.py tests/test_preparado_suministro.py tests/test_control_banda.py -v`
Expected: PASS (toda la suite tocada por este plan)

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/preparacion.py tests/test_preparacion_presion_camara.py
git commit -m "feat: debounce de apagado para aire_admosferico_camara (preparacion)"
```

---

### Task 8: Documentar en CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Ninguna (solo documentación).

- [ ] **Step 1: Agregar sección al CLAUDE.md**

Insertar, después del bloque `Fases y su estado de diseño` (antes de la sección `## ESTERILIZACION`), una nueva sección:

```markdown
---

## PREPARADO / PREPARACION — separación válvula / alarma / gate (2026-08-06)

El control de presión de chaqueta (`presion_chaqueta`/`rango_presion_chaqueta`) y temperatura de drenaje (`temp_segura_drenaje`/`rango_temp_drenaje`, nuevo) en `preparado.py` y `preparacion.py` usaba un único umbral (borde de la banda `objetivo±rango`, o techo único en drenaje) tanto para accionar la válvula como para disparar la alarma bloqueante y decidir si el equipo está "listo". Esto hacía que la alarma bloqueante (`CHAQUETA_FRIA`, `TEMP_DRENAJE_ALTA`/`TEMPERATURA_DRENAJE_ALTA`) disparara casi en cada arranque en frío, porque la válvula no reaccionaba hasta que ya se había cruzado el borde tolerado.

Separado en `control_banda.py` (`evaluar_banda()`): la válvula reacciona al **objetivo** exacto, sin tolerancia (chaqueta: ON si `presión < objetivo`; drenaje: ON si `temp > objetivo`, sin cambios respecto al drenaje anterior). La alarma bloqueante y el gate de listo/inicio de ciclo siguen usando la **banda** `objetivo±rango`, sin cambiar esos umbrales — solo se separan de la válvula. Drenaje no tiene alarma de lado bajo (no existe acción física para "muy frío"), pero el lado bajo de su banda sí participa del gate.

`control_banda.py` también expone `ConfirmadorApagado`: exige 3 ticks consecutivos de "debe estar apagado" antes de cortar `vapor_chaqueta`, `agua_intercambiador` o `aire_admosferico_camara` — el encendido sigue siendo inmediato. Necesario porque, al mover el umbral de encendido al objetivo exacto (sin histéresis), es más fácil que la válvula oscile justo en ese punto.

Ver spec: `docs/superpowers/specs/2026-08-06-control-banda-objetivo-alarma-gate-design.md`.

---
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: documentar separacion valvula/alarma/gate de chaqueta y drenaje en CLAUDE.md"
```

# Apertura automática de puerta al finalizar el ciclo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cuando `finalizacion.apertura_automatica` es `true` y el ciclo termina en `COMPLETADO`, el sistema abre solo la puerta de descarga y confirma el ciclo, sin esperar al operador — implementando los 4 parámetros de `finalizacion` que hoy existen en los perfiles JSON pero no los usa ningún código.

**Architecture:** Nuevo método `CicloState._mantener_apertura_automatica()`, llamado junto a `_mantener_valvula_reposo()` en la rama `COMPLETADO` del bloque `ESPERANDO_CONFIRMACION` de `run()`. Requiere inyectar `ServicioPuertas` (ya existe, se llama `door_service`) hasta `CicloState`, que hoy no tiene acceso a él — se propaga como parámetro opcional a través de `StateMachine` y `ControlLoop`.

**Tech Stack:** Python 3.14, pytest, unittest.mock (MagicMock, monkeypatch).

## Global Constraints

- Solo aplica cuando `_resultado_pendiente == CicloResultado.COMPLETADO` — nunca en FALLO/CANCELADO/emergencia.
- Puerta de descarga: `"Puerta 2"` si `"Puerta 2" in door_service.doors`, si no `"Puerta 1"`.
- Secuencia: espera fija `tiempo_espera_apertura` (seg) → chequeo `temp_camara <= temp_max_apertura` (°C, de `finalizacion`, NO el global) → si tarda más de `timeout_temperatura` (min) en cumplirse, una alarma `ALERTA` de una sola vez (no repetida) → al cumplirse, `door_service.request_open(puerta)` y si tiene éxito, `estado.set_flag("CICLO_CONFIRMADO", True)`.
- Tras la alarma de timeout, se sigue esperando en automático indefinidamente — no hay caída a modo manual ni límite adicional.
- Si `request_open` falla (interlock/presión), se reintenta en el siguiente tick sin alarma nueva.
- `door_service=None` (default) debe dejar el comportamiento actual intacto — no romper ningún test ni construcción existente de `CicloState`/`StateMachine`.
- No se modifica el flujo manual (botón CONFIRMAR, botón de abrir puerta) ni `ServicioPuertas`/`_can_open_physical`.

---

### Task 1: Propagar `door_service` hasta `CicloState`

**Files:**
- Modify: `src/autoclave/state_machine/states/ciclo.py:58` (`CicloState.__init__`)
- Modify: `src/autoclave/state_machine/state_machine.py:15,26` (`StateMachine.__init__`)
- Modify: `src/autoclave/services/domain/loop/control_loop.py:52-55,255-258` (las dos construcciones de `StateMachine`)
- Test: Create `tests/test_ciclo_apertura_automatica.py`
- Test: Modify `tests/test_control_loop_connectivity_ticket.py` (agregar un test de wiring; `_make_loop` ya pasa `door_service=MagicMock()` a `ControlLoop`, no requiere cambios)

**Interfaces:**
- Consumes: nada nuevo — `ServicioPuertas` ya existe (`src/autoclave/services/domain/puertas/ser_puertas.py`), `ControlLoop.door_service` ya existe (`control_loop.py:36`).
- Produces: `CicloState.door_service` (atributo de instancia, `None` por defecto) — lo consume el método de Task 2. `StateMachine.__init__` gana el parámetro opcional `door_service=None`.

- [ ] **Step 1: Escribir el test de wiring en `CicloState`**

Crear `tests/test_ciclo_apertura_automatica.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _make_ciclo(door_service=None, apertura_automatica=False,
                 tiempo_espera=60, temp_max=80.0, timeout_min=30,
                 temp_camara=25.0):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": temp_camara}
    estado.sensores_pres = {"pres_camara": 101.3}
    estado.get_flag.return_value = False

    set_do = MagicMock()
    cycle = MagicMock()

    def _get_param(seccion, nombre, default=None):
        valores = {
            ("finalizacion", "apertura_automatica"): apertura_automatica,
            ("finalizacion", "tiempo_espera_apertura"): tiempo_espera,
            ("finalizacion", "temp_max_apertura"): temp_max,
            ("finalizacion", "timeout_temperatura"): timeout_min,
        }
        return valores.get((seccion, nombre), default)

    cycle.get_param.side_effect = _get_param
    config = MagicMock()
    config.get.return_value = None
    alarm_manager = MagicMock()

    ciclo = CicloState(estado, set_do, cycle, config, alarm_manager,
                        cap=None, door_service=door_service)
    ciclo.reset()
    ciclo._resultado_pendiente = CicloResultado.COMPLETADO
    return ciclo, estado, set_do, alarm_manager


def test_door_service_none_por_defecto():
    ciclo, *_ = _make_ciclo()
    assert ciclo.door_service is None


def test_door_service_se_guarda_si_se_pasa():
    door_service = MagicMock()
    ciclo, *_ = _make_ciclo(door_service=door_service)
    assert ciclo.door_service is door_service


def test_door_service_none_no_rompe_run(monkeypatch):
    ciclo, *_ = _make_ciclo(door_service=None, apertura_automatica=True)
    resultado = ciclo.run()
    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `pytest tests/test_ciclo_apertura_automatica.py -v`
Expected: FAIL — `CicloState.__init__()` todavía no acepta `door_service`.

- [ ] **Step 3: Agregar el parámetro a `CicloState.__init__`**

En `ciclo.py`, modificar la firma y el cuerpo de `__init__` (línea 58 en adelante):

```python
    def __init__(self, estado, set_do, cycle, config, alarm_manager, cap=None, door_service=None):
        self.estado        = estado
        self.set_do        = set_do
        self.cycle         = cycle
        self.config        = config
        self.alarm_manager = alarm_manager
        self.cap           = cap
        self.door_service  = door_service
        self._contador_drenaje_alta = 0
        self._contador_drenaje_baja = 0
```

(El resto de `__init__` no cambia.)

- [ ] **Step 4: Propagar el parámetro en `StateMachine.__init__`**

En `state_machine.py`:

```python
class StateMachine:
    def __init__(self, io, estado, set_do, cycle, config, cap=None, door_service=None):
        self.io            = io
        self.estado        = estado
        self.set_do        = set_do
        self.cycle         = cycle
        self.config        = config

        self.alarm_manager = AlarmManager(estado)

        self.preparacion = preparacion_state(self.alarm_manager, estado, set_do, cycle, config)
        self.preparado   = preparado_state(self.alarm_manager, estado, set_do, cycle, config)
        self.ciclo       = CicloState(estado, set_do, cycle, config, self.alarm_manager, cap, door_service)
        self.falla       = FallaState(estado, set_do, self.alarm_manager)
        self.hibernacion = Hibernacion(estado, set_do, self.alarm_manager)

        self.prev_state  = None
```

- [ ] **Step 5: Pasar `door_service` desde `ControlLoop` en las dos construcciones de `StateMachine`**

En `control_loop.py`, constructor (línea 52-55):

```python
        self.state_machine     = StateMachine(
            io=self.link, estado=self.estado, set_do=set_do,
            cycle=self.cycle, config=self.config_manager, cap=cap,
            door_service=door_service,
        )
```

Y en `set_active_cycle` (línea 255-258):

```python
            self.state_machine = StateMachine(
                io=self.link, estado=self.estado, set_do=self.set_do,
                cycle=cycle, config=self.config_manager, cap=self.cap,
                door_service=self.door_service,
            )
```

- [ ] **Step 6: Correr los tests de `CicloState` para verificar que pasan**

Run: `pytest tests/test_ciclo_apertura_automatica.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Escribir el test de wiring en `ControlLoop`**

En `tests/test_control_loop_connectivity_ticket.py`, agregar al final del archivo:

```python
def test_control_loop_pasa_door_service_a_state_machine():
    from unittest.mock import patch
    from autoclave.services.domain.loop.control_loop import ControlLoop

    cycle_manager = MagicMock()
    cycle_manager.get_selected_cycle.return_value = MagicMock()
    door_service = MagicMock()

    with patch("autoclave.services.domain.loop.control_loop.StateMachine") as MockSM:
        ControlLoop(
            units=MagicMock(),
            door_service=door_service,
            doors=[],
            estado=_FakeEstado(),
            link=MagicMock(),
            set_do=MagicMock(),
            alarm_manager=MagicMock(),
            cycle_manager=cycle_manager,
            config_manager=MagicMock(),
        )

    _, kwargs = MockSM.call_args
    assert kwargs["door_service"] is door_service
```

(`MagicMock` y `_FakeEstado` ya están importados/definidos en ese archivo — usar los existentes, no duplicar imports.)

- [ ] **Step 8: Correr el test de wiring para verificar que pasa**

Run: `pytest tests/test_control_loop_connectivity_ticket.py -v`
Expected: PASS, incluyendo el test nuevo.

- [ ] **Step 9: Correr toda la suite**

Run: `pytest tests/ -v`
Expected: PASS — ningún test existente construye `CicloState`/`StateMachine` pasando `cap` o un séptimo argumento posicional, así que el parámetro nuevo con default no rompe nada.

- [ ] **Step 10: Commit**

```bash
git add src/autoclave/state_machine/states/ciclo.py src/autoclave/state_machine/state_machine.py src/autoclave/services/domain/loop/control_loop.py tests/test_ciclo_apertura_automatica.py tests/test_control_loop_connectivity_ticket.py
git commit -m "$(cat <<'EOF'
feat: propagar ServicioPuertas hasta CicloState

CicloState no tenia acceso a ServicioPuertas para poder abrir puertas
por su cuenta. Se agrega como parametro opcional (door_service=None)
propagado desde ControlLoop -> StateMachine -> CicloState, sin romper
ninguna construccion existente.
EOF
)"
```

---

### Task 2: Implementar `_mantener_apertura_automatica()`

**Files:**
- Modify: `src/autoclave/state_machine/states/ciclo.py` (import `time`, atributos en `__init__`/`reset()`, nuevo método)
- Test: Modify `tests/test_ciclo_apertura_automatica.py` (agregar tests, mismo archivo de Task 1)

**Interfaces:**
- Consumes: `CicloState.door_service` (de Task 1), `Alarm`/`AlarmType` (ya importados en `ciclo.py`), `self.cycle.get_param("finalizacion", nombre, default=...)`, `self.estado.sensores_temp.get("temp_camara")`, `self.estado.set_flag("CICLO_CONFIRMADO", True)`, `self.door_service.doors` (dict, claves = nombres de puerta), `self.door_service.request_open(nombre) -> (bool, str)`.
- Produces: `CicloState._mantener_apertura_automatica()` (sin argumentos, sin retorno) — lo consume Task 3 desde `run()`. Atributos `_apertura_auto_t_inicio` (float|None) y `_apertura_auto_alarmado` (bool), reseteados en `reset()` (Task 3 también los verifica).

- [ ] **Step 1: Agregar el import de `time` y los atributos nuevos**

En `ciclo.py`, agregar el import al inicio del archivo (junto a `import logging`):

```python
import logging
import time
```

En `__init__` (después de `self.door_service = door_service`):

```python
        self.door_service  = door_service
        self._apertura_auto_t_inicio = None
        self._apertura_auto_alarmado = False
        self._contador_drenaje_alta = 0
        self._contador_drenaje_baja = 0
```

En `reset()` (junto a `self._contador_drenaje_alta = 0`):

```python
        self._contador_drenaje_alta = 0
        self._contador_drenaje_baja = 0
        self._apertura_auto_t_inicio = None
        self._apertura_auto_alarmado = False
```

- [ ] **Step 2: Escribir los tests del método (llamándolo directo, sin pasar por `run()`)**

Agregar a `tests/test_ciclo_apertura_automatica.py`:

```python
def test_apertura_automatica_false_no_hace_nada():
    door_service = MagicMock()
    door_service.doors = {"Puerta 1": MagicMock(), "Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=False)

    ciclo._mantener_apertura_automatica()
    ciclo._mantener_apertura_automatica()

    door_service.request_open.assert_not_called()
    estado.set_flag.assert_not_called()


def test_espera_fija_antes_de_intentar_abrir(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 1": MagicMock(), "Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=60, temp_max=80.0, temp_camara=25.0)

    t0 = 1_000_000.0
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0)
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_not_called()

    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 59)
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_not_called()

    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 60)
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_called_once_with("Puerta 2")


def test_abre_puerta_2_si_existe(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 1": MagicMock(), "Puerta 2": MagicMock()}
    door_service.request_open.return_value = (True, "")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 2_000_000.0)
    ciclo._mantener_apertura_automatica()

    door_service.request_open.assert_called_once_with("Puerta 2")


def test_abre_puerta_1_si_es_equipo_de_una_puerta(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 1": MagicMock()}
    door_service.request_open.return_value = (True, "")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 2_000_000.0)
    ciclo._mantener_apertura_automatica()

    door_service.request_open.assert_called_once_with("Puerta 1")


def test_espera_temperatura_antes_de_abrir(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 1": MagicMock(), "Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=95.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 3_000_000.0)
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_not_called()

    estado.sensores_temp["temp_camara"] = 75.0
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_called_once_with("Puerta 2")


def test_confirma_solo_al_abrir_con_exito(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    door_service.request_open.return_value = (True, "")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 4_000_000.0)
    ciclo._mantener_apertura_automatica()

    estado.set_flag.assert_called_once_with("CICLO_CONFIRMADO", True)


def test_no_confirma_si_abrir_falla(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    door_service.request_open.return_value = (False, "Puerta 1 no esta cerrada")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 5_000_000.0)
    ciclo._mantener_apertura_automatica()
    estado.set_flag.assert_not_called()
    alarm_manager.report.assert_not_called()

    # reintenta en el siguiente tick
    door_service.request_open.return_value = (True, "")
    ciclo._mantener_apertura_automatica()
    estado.set_flag.assert_called_once_with("CICLO_CONFIRMADO", True)


def test_alarma_timeout_temperatura_una_sola_vez(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=60, temp_max=80.0, timeout_min=30, temp_camara=95.0)

    t0 = 6_000_000.0
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0)
    ciclo._mantener_apertura_automatica()  # fija _apertura_auto_t_inicio = t0

    # tiempo_espera (60s) + timeout_temperatura (30min = 1800s) + margen
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 60 + 1801)
    ciclo._mantener_apertura_automatica()
    alarm_manager.report.assert_called_once()
    alarma = alarm_manager.report.call_args.args[0]
    assert alarma.id == "TIMEOUT_APERTURA_AUTOMATICA"
    assert alarma.blocks_operation is False

    # sigue en temperatura alta: no debe repetir la alarma
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 60 + 2000)
    ciclo._mantener_apertura_automatica()
    alarm_manager.report.assert_called_once()


def test_sigue_esperando_tras_alarma_timeout_hasta_que_baja_temp(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    door_service.request_open.return_value = (True, "")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=60, temp_max=80.0, timeout_min=30, temp_camara=95.0)

    t0 = 7_000_000.0
    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0)
    ciclo._mantener_apertura_automatica()

    monkeypatch.setattr(ciclo_module.time, "time", lambda: t0 + 60 + 1801)
    ciclo._mantener_apertura_automatica()
    alarm_manager.report.assert_called_once()

    estado.sensores_temp["temp_camara"] = 75.0
    ciclo._mantener_apertura_automatica()
    door_service.request_open.assert_called_once_with("Puerta 2")
    estado.set_flag.assert_called_once_with("CICLO_CONFIRMADO", True)
    alarm_manager.clear.assert_called_once_with("TIMEOUT_APERTURA_AUTOMATICA")


def test_sensor_ausente_no_avanza_ni_rompe(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0)
    estado.sensores_temp = {}

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 8_000_000.0)
    ciclo._mantener_apertura_automatica()

    door_service.request_open.assert_not_called()
    estado.set_flag.assert_not_called()
```

- [ ] **Step 3: Correr los tests para verificar que fallan**

Run: `pytest tests/test_ciclo_apertura_automatica.py -v`
Expected: FAIL — `_mantener_apertura_automatica` todavía no existe (`AttributeError`).

- [ ] **Step 4: Implementar `_mantener_apertura_automatica()`**

Agregar el método en `ciclo.py`, junto a `_mantener_valvula_reposo()`:

```python
    def _mantener_apertura_automatica(self):
        """Si finalizacion.apertura_automatica está activo, abre la puerta de
        descarga y confirma el ciclo sin esperar al operador. Solo se llama
        mientras _resultado_pendiente == COMPLETADO. Secuencia: espera fija
        (tiempo_espera_apertura) → espera a que temp_camara baje a
        temp_max_apertura (avisando por alarma no bloqueante si tarda más de
        timeout_temperatura, sin dejar de esperar) → abrir puerta + confirmar."""
        if self.door_service is None:
            return
        if not self.cycle.get_param("finalizacion", "apertura_automatica", default=False):
            return

        if self._apertura_auto_t_inicio is None:
            self._apertura_auto_t_inicio = time.time()

        tiempo_espera = self.cycle.get_param("finalizacion", "tiempo_espera_apertura", default=60)
        elapsed = time.time() - self._apertura_auto_t_inicio
        if elapsed < tiempo_espera:
            return

        temp = self.estado.sensores_temp.get("temp_camara")
        if temp is None:
            return

        temp_max = self.cycle.get_param("finalizacion", "temp_max_apertura", default=80.0)
        if temp > temp_max:
            timeout_seg = self.cycle.get_param("finalizacion", "timeout_temperatura", default=30) * 60
            if not self._apertura_auto_alarmado and (elapsed - tiempo_espera) > timeout_seg:
                self._apertura_auto_alarmado = True
                self.alarm_manager.report(Alarm(
                    alarm_id="TIMEOUT_APERTURA_AUTOMATICA",
                    alarm_type=AlarmType.ALERTA,
                    source_state="CICLO",
                    description="Apertura automática: la cámara tarda más de lo esperado en enfriar.",
                    recoverable=True,
                    blocks_operation=False,
                ))
            return

        puerta = "Puerta 2" if "Puerta 2" in self.door_service.doors else "Puerta 1"
        ok, _motivo = self.door_service.request_open(puerta)
        if ok:
            if self._apertura_auto_alarmado:
                self.alarm_manager.clear("TIMEOUT_APERTURA_AUTOMATICA")
            self.estado.set_flag("CICLO_CONFIRMADO", True)
```

- [ ] **Step 5: Correr los tests para verificar que pasan**

Run: `pytest tests/test_ciclo_apertura_automatica.py -v`
Expected: PASS (14 tests: 3 de Task 1 + 11 de este step)

- [ ] **Step 6: Correr toda la suite**

Run: `pytest tests/ -v`
Expected: PASS — el método nuevo no se llama todavía desde `run()` (eso es Task 3), así que no puede afectar ningún test existente.

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/state_machine/states/ciclo.py tests/test_ciclo_apertura_automatica.py
git commit -m "$(cat <<'EOF'
feat: implementar _mantener_apertura_automatica en CicloState

Implementa los 4 parametros de finalizacion (tiempo_espera_apertura,
temp_max_apertura, timeout_temperatura, apertura_automatica) que
existian sin uso en los perfiles JSON. Todavia no se llama desde
run() -- eso queda para la siguiente tarea.
EOF
)"
```

---

### Task 3: Llamar `_mantener_apertura_automatica()` desde `run()`

**Files:**
- Modify: `src/autoclave/state_machine/states/ciclo.py:263-268` (bloque `COMPLETADO` dentro de `run()`)
- Test: Modify `tests/test_ciclo_apertura_automatica.py` (agregar tests de integración vía `run()`)

**Interfaces:**
- Consumes: `CicloState._mantener_apertura_automatica()` (de Task 2), `CicloState._mantener_valvula_reposo()` (ya existente, sin cambios).
- Produces: nada nuevo consumido por otras tareas — es el cierre del plan.

- [ ] **Step 1: Escribir los tests de integración**

Agregar a `tests/test_ciclo_apertura_automatica.py`:

```python
def test_run_llama_apertura_automatica_en_completado(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    door_service.request_open.return_value = (True, "")
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 9_000_000.0)
    resultado = ciclo.run()

    assert resultado == CicloResultado.ESPERANDO_CONFIRMACION
    door_service.request_open.assert_called_once_with("Puerta 2")


def test_run_no_llama_apertura_automatica_en_fallo():
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)
    ciclo._resultado_pendiente = CicloResultado.FALLO
    ciclo._protocolo = MagicMock()

    ciclo.run()

    door_service.request_open.assert_not_called()


def test_run_no_llama_apertura_automatica_en_cancelado():
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=0, temp_max=80.0, temp_camara=25.0)
    ciclo._resultado_pendiente = CicloResultado.CANCELADO
    ciclo._protocolo = MagicMock()

    ciclo.run()

    door_service.request_open.assert_not_called()


def test_reset_reinicia_temporizador_de_apertura_automatica(monkeypatch):
    import autoclave.state_machine.states.ciclo as ciclo_module
    door_service = MagicMock()
    door_service.doors = {"Puerta 2": MagicMock()}
    ciclo, estado, set_do, alarm_manager = _make_ciclo(
        door_service=door_service, apertura_automatica=True,
        tiempo_espera=60, temp_max=80.0, temp_camara=95.0)

    monkeypatch.setattr(ciclo_module.time, "time", lambda: 10_000_000.0)
    ciclo._mantener_apertura_automatica()
    assert ciclo._apertura_auto_t_inicio is not None

    ciclo.reset()

    assert ciclo._apertura_auto_t_inicio is None
    assert ciclo._apertura_auto_alarmado is False
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run: `pytest tests/test_ciclo_apertura_automatica.py -v`
Expected: FAIL en `test_run_llama_apertura_automatica_en_completado` — `run()` todavía no llama `_mantener_apertura_automatica()`. Los tests de FALLO/CANCELADO y de `reset()` ya pasan (no dependen del cambio de este task), pero se agregan igual para dejar la protección explícita.

- [ ] **Step 3: Agregar la llamada en `run()`**

En `ciclo.py`, dentro del bloque `if self._resultado_pendiente is not None:` (líneas 263-268):

```python
            if self._resultado_pendiente == CicloResultado.COMPLETADO:
                self._mantener_valvula_reposo()
                self._mantener_apertura_automatica()
            else:
                self._protocolo.update()
            self._mantener_drenaje()
            return CicloResultado.ESPERANDO_CONFIRMACION
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run: `pytest tests/test_ciclo_apertura_automatica.py -v`
Expected: PASS (18 tests en total)

- [ ] **Step 5: Correr toda la suite completa**

Run: `pytest tests/ -v`
Expected: PASS — en particular `tests/test_ciclo_valvula_reposo.py` y `tests/test_ciclo_drenaje_espera_confirmacion.py` (misma rama de `run()`), y `tests/test_control_loop_connectivity_ticket.py`.

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/states/ciclo.py tests/test_ciclo_apertura_automatica.py
git commit -m "$(cat <<'EOF'
feat: apertura automatica de puerta al finalizar ciclo con exito

Cuando finalizacion.apertura_automatica esta activo y el ciclo
termina en COMPLETADO, se abre la puerta de descarga y se confirma
el ciclo sin esperar al operador, respetando la espera fija y el
tope de temperatura por ciclo ya definidos en el JSON.
EOF
)"
```

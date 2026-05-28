# suministro_electrico — Modo Seguro por Corte Eléctrico

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detectar pérdida de suministro eléctrico (DI `suministro_electrico` = 0) y ejecutar un protocolo de seguridad: bloquear ciclo y bomba fuera de ciclo; abortar y descomprimir sin bomba durante ciclo; puertas avanzadas operan en modo seguro sin bomba.

**Architecture:** Sigue el patrón `EmergencyStop` / flag. Un device `SuministroElectrico` setea el flag `FALLO_SUMINISTRO_ELECTRICO` en `EstadoAutoclave`; ese flag es leído por `VacuumPump`, `preparado_state`, `CicloState` y `AdvancedDoor`. La UI refleja el estado en el footer.

**Tech Stack:** Python 3.14, pytest + unittest.mock, tkinter/customtkinter.

---

## Mapa de archivos

| Archivo | Acción |
|---------|--------|
| `src/autoclave/devices/suministro_electrico/__init__.py` | Crear (vacío) |
| `src/autoclave/devices/suministro_electrico/suministro_electrico.py` | **Nuevo device** |
| `src/autoclave/core/status.py` | Agregar flag `FALLO_SUMINISTRO_ELECTRICO` |
| `src/autoclave/devices/pump/pump.py` | Bloquear bomba si flag activo |
| `src/autoclave/services/domain/loop/control_loop.py` | Instanciar + llamar update |
| `src/autoclave/state_machine/states/preparado.py` | Verificar suministro + bloquear listo |
| `src/autoclave/state_machine/states/ciclo.py` | Detectar flag → abortar |
| `src/autoclave/devices/puertas/advanced_door.py` | Modo seguro + alarm_manager |
| `src/autoclave/devices/puertas/door_factory.py` | Pasar alarm_manager |
| `src/autoclave/backend/context.py` | Incluir alarm_manager al crear puertas |
| `src/autoclave/ui/window/main_window.py` | Indicador en footer |
| `tests/test_suministro_electrico.py` | **Nuevo** |
| `tests/test_pump.py` | **Nuevo** |
| `tests/test_ciclo_suministro.py` | **Nuevo** |
| `tests/test_advanced_door_safe_mode.py` | **Nuevo** |

---

## Task 1: Device SuministroElectrico + flag en EstadoAutoclave

**Files:**
- Create: `src/autoclave/devices/suministro_electrico/__init__.py`
- Create: `src/autoclave/devices/suministro_electrico/suministro_electrico.py`
- Modify: `src/autoclave/core/status.py`
- Test: `tests/test_suministro_electrico.py`

- [ ] **Step 1: Crear test que falla**

```python
# tests/test_suministro_electrico.py
from unittest.mock import MagicMock
from autoclave.devices.suministro_electrico.suministro_electrico import SuministroElectrico


def _make_device():
    estado = MagicMock()
    set_do = MagicMock()
    device = SuministroElectrico(estado, set_do)
    return device, estado, set_do


def test_flag_inactivo_cuando_suministro_presente():
    device, estado, _ = _make_device()
    device.update(True)
    estado.set_flag.assert_called_with("FALLO_SUMINISTRO_ELECTRICO", False)


def test_flag_activo_cuando_suministro_cortado():
    device, estado, _ = _make_device()
    device.update(False)
    estado.set_flag.assert_called_with("FALLO_SUMINISTRO_ELECTRICO", True)


def test_bomba_apagada_en_flanco_bajante():
    device, estado, set_do = _make_device()
    device.update(True)   # estado normal
    set_do.reset_mock()
    device.update(False)  # corte
    set_do.bomba_vacio_off.assert_called_once()


def test_bomba_no_apagada_si_ya_habia_fallo():
    device, estado, set_do = _make_device()
    device.update(False)  # primer corte
    set_do.reset_mock()
    device.update(False)  # sigue cortado
    set_do.bomba_vacio_off.assert_not_called()


def test_restauracion_limpia_flag():
    device, estado, _ = _make_device()
    device.update(False)  # corte
    device.update(True)   # restaurar
    assert estado.set_flag.call_args == (("FALLO_SUMINISTRO_ELECTRICO", False),)
```

- [ ] **Step 2: Ejecutar — verificar que falla**

```
pytest tests/test_suministro_electrico.py -v
```
Esperado: `ModuleNotFoundError: No module named 'autoclave.devices.suministro_electrico'`

- [ ] **Step 3: Crear `__init__.py` vacío**

```
# src/autoclave/devices/suministro_electrico/__init__.py
(vacío)
```

- [ ] **Step 4: Crear el device**

```python
# src/autoclave/devices/suministro_electrico/suministro_electrico.py
import logging

logger = logging.getLogger(__name__)


class SuministroElectrico:
    def __init__(self, estado, set_do, flag_name="FALLO_SUMINISTRO_ELECTRICO"):
        self.estado = estado
        self.set_do = set_do
        self.flag_name = flag_name
        self.active = False   # True = fallo (sin suministro)
        self._last = False

    def update(self, value: bool):
        """value=True → suministro presente. value=False → corte eléctrico."""
        self._last = self.active
        self.active = not bool(value)

        self.estado.set_flag(self.flag_name, self.active)

        if self.active and not self._last:
            logger.error("Suministro eléctrico: CORTE DETECTADO")
            self.set_do.bomba_vacio_off()
        elif not self.active and self._last:
            logger.info("Suministro eléctrico: RESTAURADO")

    def __repr__(self):
        return f"<SuministroElectrico fallo={self.active}>"
```

- [ ] **Step 5: Agregar flag a `status.py`**

En `src/autoclave/core/status.py`, en `_flags_map`, agregar al final:

```python
_flags_map = {
    "LISTO_PARA_CICLO":             0,
    "START_CICLO":                  1,
    "FALLO_GENERAL":                2,
    "PARO_EMERGENCIA":              3,
    "CICLO_CANCELADO":              4,
    "CICLO_CONFIRMADO":             5,
    "RESET_FALLA":                  6,
    "FALLO_SUMINISTRO_ELECTRICO":   7,   # corte de energía
}
```

- [ ] **Step 6: Ejecutar tests — deben pasar**

```
pytest tests/test_suministro_electrico.py -v
```
Esperado: `5 passed`

- [ ] **Step 7: Commit**

```
git add src/autoclave/devices/suministro_electrico/ src/autoclave/core/status.py tests/test_suministro_electrico.py
git commit -m "feat: SuministroElectrico device y flag FALLO_SUMINISTRO_ELECTRICO"
```

---

## Task 2: VacuumPump — bloquear si hay fallo de suministro

**Files:**
- Modify: `src/autoclave/devices/pump/pump.py`
- Test: `tests/test_pump.py`

- [ ] **Step 1: Crear test que falla**

```python
# tests/test_pump.py
from unittest.mock import MagicMock
from autoclave.devices.pump.pump import VacuumPump


def _make_pump(agua_bomba=1, bomba_vacio=0, fallo_suministro=False):
    estado = MagicMock()
    estado.sensores_di = {"agua_bomba": agua_bomba}
    estado.salidas_do  = {"bomba_vacio": bomba_vacio}
    estado.get_flag.side_effect = (
        lambda f: fallo_suministro if f == "FALLO_SUMINISTRO_ELECTRICO" else False
    )
    return VacuumPump(estado)


def test_puede_activar_con_agua_y_sin_fallo():
    pump = _make_pump(agua_bomba=1, bomba_vacio=0, fallo_suministro=False)
    assert pump.puede_activar() is True


def test_no_puede_activar_sin_agua():
    pump = _make_pump(agua_bomba=0, fallo_suministro=False)
    assert pump.puede_activar() is False


def test_no_puede_activar_con_fallo_suministro():
    pump = _make_pump(agua_bomba=1, bomba_vacio=0, fallo_suministro=True)
    assert pump.puede_activar() is False
```

- [ ] **Step 2: Ejecutar — verificar que falla**

```
pytest tests/test_pump.py::test_no_puede_activar_con_fallo_suministro -v
```
Esperado: `FAILED` (la bomba sí puede activar actualmente con fallo de suministro)

- [ ] **Step 3: Modificar `pump.py`**

Reemplazar `puede_activar()` completo:

```python
def puede_activar(self):
    if self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO"):
        logger.warning("Bomba bloqueada: fallo de suministro eléctrico.")
        return False

    if not self.agua_bomba():
        logger.warning("Advertencia: No hay agua en la bomba de vacío.")
        return False

    if not self.bomba_vacio() and self.agua_bomba():
        logger.info("Activando bomba de vacío.")
        return True
    else:
        return False
```

- [ ] **Step 4: Ejecutar — deben pasar**

```
pytest tests/test_pump.py -v
```
Esperado: `3 passed`

- [ ] **Step 5: Commit**

```
git add src/autoclave/devices/pump/pump.py tests/test_pump.py
git commit -m "feat: VacuumPump bloquea si FALLO_SUMINISTRO_ELECTRICO activo"
```

---

## Task 3: ControlLoop — instanciar device y llamar update

**Files:**
- Modify: `src/autoclave/services/domain/loop/control_loop.py`

No hay test unitario para ControlLoop (depende de hilos y hardware). La integración se verifica en tasks posteriores cuando se corre el sistema.

- [ ] **Step 1: Agregar import en `control_loop.py`**

Al inicio del archivo, después de los imports existentes:

```python
from autoclave.devices.suministro_electrico.suministro_electrico import SuministroElectrico
```

- [ ] **Step 2: Instanciar en `__init__`**

En `ControlLoop.__init__`, después de `self.paro_emergencia = EmergencyStop(estado)`:

```python
self.suministro_electrico = SuministroElectrico(estado, set_do)
```

- [ ] **Step 3: Llamar update en `run()`**

En `ControlLoop.run()`, después de la línea `self.paro_emergencia.update(...)`:

```python
# 2b. Suministro eléctrico → actualiza flag en estado
self.suministro_electrico.update(
    bool(self.estado.sensores_di.get("suministro_electrico", 1))
)
```

El default `1` evita disparar el fallo antes de la primera lectura del hardware.

- [ ] **Step 4: Verificar que los tests anteriores siguen verdes**

```
pytest tests/test_suministro_electrico.py tests/test_pump.py -v
```
Esperado: `8 passed`

- [ ] **Step 5: Commit**

```
git add src/autoclave/services/domain/loop/control_loop.py
git commit -m "feat: ControlLoop integra SuministroElectrico en el loop principal"
```

---

## Task 4: Estado PREPARADO — verificar suministro y bloquear listo

**Files:**
- Modify: `src/autoclave/state_machine/states/preparado.py`

- [ ] **Step 1: Crear test que falla**

Agregar a un archivo nuevo `tests/test_preparado_suministro.py`:

```python
# tests/test_preparado_suministro.py
from unittest.mock import MagicMock, patch
from autoclave.state_machine.states.preparado import preparado_state
from autoclave.state_machine.alarms.alarm_types import AlarmType


def _make_preparado(suministro_electrico=1, fallo_suministro=False):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_pres = {
        "pres_camara": 101.0, "pres_chaqueta": 300.0,
        "pres_empaque_1": 101.0, "pres_empaque_2": 101.0,
    }
    estado.sensores_temp = {
        "temp_camara": 25.0, "temp_2_camara": 25.0, "temp_ref": 25.0,
        "temp_chaqueta": 25.0, "temp_drenaje_cam": 25.0, "temp_drenaje": 25.0,
    }
    estado.sensores_di = {
        "vapor_suministro": 1, "agua_bomba": 1,
        "agua_generador": 1, "aire_comprimido": 1,
        "suministro_electrico": suministro_electrico,
        "puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
    }
    estado.get_flag.side_effect = (
        lambda f: fallo_suministro if f == "FALLO_SUMINISTRO_ELECTRICO" else False
    )
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = 300
    config = MagicMock()
    config.get.side_effect = lambda k: {
        "presion_admosferica": 101.3, "rango_presion_atm": 20.0,
        "temp_segura_drenaje": 60.0, "tiempo_estable_alarma": 5,
    }.get(k, 0)
    p = preparado_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager


def test_suministro_off_genera_alarma():
    p, alarm_mgr = _make_preparado(suministro_electrico=0, fallo_suministro=True)
    p.verificar_suministros()
    ids = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "SUMINISTRO_ELECTRICO" in ids


def test_suministro_ok_limpia_alarma():
    p, alarm_mgr = _make_preparado(suministro_electrico=1, fallo_suministro=False)
    p.verificar_suministros()
    alarm_mgr.clear.assert_any_call("SUMINISTRO_ELECTRICO")


def test_esta_preparado_false_con_fallo_suministro():
    p, _ = _make_preparado(suministro_electrico=0, fallo_suministro=True)
    # Parchear los métodos de control para que devuelvan True
    p.mantener_chaqueta = lambda: True
    p.mantener_presion_camara = lambda: True
    p.mantener_drenaje = lambda: True
    p.puertas_cerradas = lambda: True
    assert p.esta_preparado() is False
```

- [ ] **Step 2: Ejecutar — verificar que falla**

```
pytest tests/test_preparado_suministro.py -v
```
Esperado: al menos `test_suministro_off_genera_alarma` y `test_esta_preparado_false_con_fallo_suministro` fallan.

- [ ] **Step 3: Modificar `verificar_suministros()` en `preparado.py`**

Al final del método, antes del `return ok`, agregar:

```python
# Suministro eléctrico
if not self.estado.sensores_di.get("suministro_electrico", 1):
    self.alarm("SUMINISTRO_ELECTRICO", AlarmType.ALERTA)
    ok = False
else:
    self.alarm_manager.clear("SUMINISTRO_ELECTRICO")
```

- [ ] **Step 4: Modificar `esta_preparado()` en `preparado.py`**

Reemplazar el bloque `condiciones`:

```python
def esta_preparado(self):
    condiciones = (
        self.puertas_cerradas() and
        self.mantener_chaqueta() and
        self.mantener_presion_camara() and
        self.mantener_drenaje() and
        not self.estado.get_flag("PARO_EMERGENCIA") and
        not self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO")
    )

    if condiciones:
        self.timer_estabilidad = None
        return True

    return False
```

- [ ] **Step 5: Ejecutar — deben pasar**

```
pytest tests/test_preparado_suministro.py -v
```
Esperado: `3 passed`

- [ ] **Step 6: Commit**

```
git add src/autoclave/state_machine/states/preparado.py tests/test_preparado_suministro.py
git commit -m "feat: preparado_state bloquea ciclo y genera alarma ante fallo de suministro"
```

---

## Task 5: Estado CICLO — abortar ante fallo de suministro

**Files:**
- Modify: `src/autoclave/state_machine/states/ciclo.py`
- Test: `tests/test_ciclo_suministro.py`

- [ ] **Step 1: Crear test que falla**

```python
# tests/test_ciclo_suministro.py
from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState, CicloResultado


def _make_ciclo(fallo_suministro=False):
    estado = MagicMock()
    estado.sensores_temp = {"temp_camara": 100.0}
    estado.sensores_pres = {
        "pres_camara": 200.0, "pres_chaqueta": 300.0,
        "pres_empaque_1": 300.0, "pres_empaque_2": 300.0,
    }
    estado.sensores_di = {"puerta_1_cerrada": 1, "puerta_2_cerrada": 1,
                          "vapor_suministro": 1}

    def flag_side(flag):
        if flag == "FALLO_SUMINISTRO_ELECTRICO":
            return fallo_suministro
        return False

    estado.get_flag.side_effect = flag_side

    set_do = MagicMock()
    cycle  = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    alarms = MagicMock()

    ciclo = CicloState(estado, set_do, cycle, config, alarms)
    ciclo.reset()
    return ciclo, estado


def test_fallo_suministro_aborta_ciclo():
    ciclo, estado = _make_ciclo(fallo_suministro=True)
    result = ciclo.run()
    assert result == CicloResultado.ESPERANDO_CONFIRMACION
    assert estado.fase_ciclo == "FALLO_SUMINISTRO"


def test_fallo_suministro_reporta_alarma_emergencia():
    ciclo, estado = _make_ciclo(fallo_suministro=True)
    ciclo.run()
    ciclo.alarm_manager.report.assert_called_once()
    alarma = ciclo.alarm_manager.report.call_args[0][0]
    assert alarma.id == "FALLO_SUMINISTRO_ELECTRICO"


def test_fallo_suministro_ejecuta_protocolo():
    ciclo, estado = _make_ciclo(fallo_suministro=True)
    ciclo._protocolo = MagicMock()
    ciclo.run()
    ciclo._protocolo.ejecutar.assert_called_once()


def test_sin_fallo_suministro_ciclo_continua():
    ciclo, estado = _make_ciclo(fallo_suministro=False)
    result = ciclo.run()
    assert result != CicloResultado.ESPERANDO_CONFIRMACION or estado.fase_ciclo != "FALLO_SUMINISTRO"
```

- [ ] **Step 2: Ejecutar — verificar que falla**

```
pytest tests/test_ciclo_suministro.py -v
```
Esperado: `test_fallo_suministro_aborta_ciclo` y otros fallan.

- [ ] **Step 3: Agregar bloque en `ciclo.py`**

En `CicloState.run()`, después del bloque `# ── 2. ¿Paro de emergencia?` (aproximadamente línea 191), agregar:

```python
# ── 2b. ¿Fallo de suministro eléctrico? ──────────────────────
if self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO"):
    logger.error("CicloState: ABORTADO por fallo de suministro eléctrico")
    self.estado.fase_ciclo = "FALLO_SUMINISTRO"
    self.alarm_manager.report(Alarm(
        alarm_id="FALLO_SUMINISTRO_ELECTRICO",
        alarm_type=AlarmType.EMERGENCIA,
        source_state="CICLO",
        description="Pérdida de suministro eléctrico durante el ciclo.",
        recoverable=False,
    ))
    self._protocolo.ejecutar()
    self._resultado_pendiente = CicloResultado.FALLO
    return CicloResultado.ESPERANDO_CONFIRMACION
```

Los imports `Alarm` y `AlarmType` ya están presentes en `ciclo.py`.

- [ ] **Step 4: Ejecutar — deben pasar**

```
pytest tests/test_ciclo_suministro.py -v
```
Esperado: `4 passed`

- [ ] **Step 5: Regresión — tests previos del ciclo**

```
pytest tests/test_ciclo_sensores.py tests/test_ciclo_suministro.py -v
```
Esperado: todos green.

- [ ] **Step 6: Commit**

```
git add src/autoclave/state_machine/states/ciclo.py tests/test_ciclo_suministro.py
git commit -m "feat: CicloState aborta y descomprime ante fallo de suministro eléctrico"
```

---

## Task 6: AdvancedDoor — modo seguro sin bomba

**Files:**
- Modify: `src/autoclave/devices/puertas/advanced_door.py`
- Test: `tests/test_advanced_door_safe_mode.py`

- [ ] **Step 1: Crear test que falla**

```python
# tests/test_advanced_door_safe_mode.py
from unittest.mock import MagicMock, call
from autoclave.devices.puertas.advanced_door import AdvancedDoor
from autoclave.devices.puertas.enum_doors import DoorState


def _make_door(fallo_suministro=False):
    estado = MagicMock()
    estado.get_flag.side_effect = (
        lambda f: fallo_suministro if f == "FALLO_SUMINISTRO_ELECTRICO" else False
    )
    estado.sensores_di = {
        "puerta_1_abierta": 0, "puerta_1_cerrada": 0, "atrapamiento_puerta_1": 0,
    }
    estado.sensores_pres = {"pres_empaque_1": 200.0}
    estado.get_door_state.return_value = DoorState.ABRIENDO

    set_do = MagicMock()
    config = MagicMock()
    config.get.side_effect = lambda k: {
        "timeout_puerta": 30,
        "vacio_empaque": 30.0,
        "presion_empaque": 300.0,
        "presion_admosferica": 101.3,
        "rango_presion_atm": 20.0,
    }.get(k, 0)

    alarm_manager = MagicMock()

    door = AdvancedDoor(
        name="Puerta 1",
        di={"abierta": "puerta_1_abierta", "cerrada": "puerta_1_cerrada",
            "atrapamiento": "atrapamiento_puerta_1"},
        do={"abrir": 20, "cerrar": 22, "desbloquear": 9, "bloquear": 11},
        ai={"presion_empaque": "pres_empaque_1"},
        estado=estado,
        setdo=set_do,
        config=config,
        alarm_manager=alarm_manager,
    )
    return door, set_do, alarm_manager, config


def test_modo_normal_activa_bomba_al_abrir():
    door, set_do, alarm_mgr, _ = _make_door(fallo_suministro=False)
    door._from_abriendo()
    set_do.bomba_vacio_on.assert_called()
    alarm_mgr.report.assert_not_called()


def test_modo_seguro_no_activa_bomba_al_abrir():
    door, set_do, alarm_mgr, _ = _make_door(fallo_suministro=True)
    door._from_abriendo()
    set_do.bomba_vacio_on.assert_not_called()


def test_modo_seguro_genera_alarma_no_bloqueante():
    door, set_do, alarm_mgr, _ = _make_door(fallo_suministro=True)
    door._from_abriendo()
    alarm_mgr.report.assert_called_once()
    alarma = alarm_mgr.report.call_args[0][0]
    assert alarma.id == "ABRIENDO_MODO_SEGURO"
    assert alarma.recoverable is True


def test_modo_seguro_usa_umbral_atmosferico():
    """Con safe mode, debe activar actuador de apertura cuando presión <= atm + rango (121.3 kPa).
    En modo normal no abriría porque presión (200 kPa) > vacio_empaque (30 kPa) NO se cumple
    de la misma forma — aquí chequeamos que en safe mode sí se llega al umbral correcto."""
    door, set_do, alarm_mgr, _ = _make_door(fallo_suministro=True)
    # Simular segundo tick (timer ya iniciado)
    import time
    door.timer_start = time.time() + 30
    door._pulso_desbloqueo_enviado = True
    # presion_empaque = 200 kPa que es > 30 (vacio normal) pero > 121.3 (atm+rango)
    # → NO debe activar abrir_on
    door._from_abriendo()
    set_do.set_output.assert_not_called()  # abrir_on no fue llamado (presión muy alta)


def test_modo_seguro_activa_abrir_cuando_presion_baja():
    door, set_do, alarm_mgr, _ = _make_door(fallo_suministro=True)
    import time
    door.timer_start = time.time() + 30
    door._pulso_desbloqueo_enviado = True
    # Presión por debajo del umbral atmosférico (atm + rango = 121.3 kPa)
    door.estado.sensores_pres["pres_empaque_1"] = 100.0
    door._from_abriendo()
    set_do.set_output.assert_any_call(20, True)  # abrir_on
```

- [ ] **Step 2: Ejecutar — verificar que falla**

```
pytest tests/test_advanced_door_safe_mode.py -v
```
Esperado: `TypeError` o `FAILED` porque `AdvancedDoor` no acepta `alarm_manager`.

- [ ] **Step 3: Modificar `__init__` de `AdvancedDoor`**

```python
from autoclave.state_machine.alarms.alarm import Alarm
from autoclave.state_machine.alarms.alarm_types import AlarmType

class AdvancedDoor(Door):
    def __init__(self, name, di, do, ai, estado, setdo, config, alarm_manager):
        self.config = config
        self.name = name
        self.di = di
        self.do = do
        self.ai = ai
        self.estado = estado
        self.set_do = setdo
        self.alarm_manager = alarm_manager          # <-- nuevo

        self.timer_start = None
        self._estabilizacion_start = None
        self._pulso_bloqueo_enviado = False
        self._pulso_desbloqueo_enviado = False
```

- [ ] **Step 4: Reemplazar `_from_abriendo()` completo**

```python
def _from_abriendo(self):
    safe_mode = self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO")

    if self.timer_start is None:
        self.timer_start = time.time() + self.config.get("timeout_puerta")
        self._pulso_desbloqueo_enviado = False
        self.bloquear_off()
        self.cerrar_off()
        if safe_mode:
            self.alarm_manager.report(Alarm(
                alarm_id="ABRIENDO_MODO_SEGURO",
                alarm_type=AlarmType.ALERTA,
                source_state="PUERTA",
                description=f"Puerta {self.name}: abriendo en modo seguro (sin bomba de vacío).",
                recoverable=True,
            ))
        else:
            self.vacio_on()
        self.desbloquear_on()
        logger.info("Iniciando apertura de puerta%s.", " (modo seguro)" if safe_mode else "")
        return

    if not self._pulso_desbloqueo_enviado:
        self.desbloquear_off()
        self._pulso_desbloqueo_enviado = True

    umbral = (
        (self.config.get("presion_admosferica") or 101.3) +
        (self.config.get("rango_presion_atm") or 20.0)
        if safe_mode
        else self.config.get("vacio_empaque")
    )

    if self.presion_empaque() <= umbral:
        self.abrir_on()

    if self.puerta_abierta() and not self.puerta_cerrada():
        self.abrir_off()
        self.vacio_off()
        self.alarm_manager.clear("ABRIENDO_MODO_SEGURO")
        self.timer_start = None
        self._pulso_desbloqueo_enviado = False
        self.set_state(DoorState.ABIERTO)
        logger.info("Puerta abierta correctamente.")
        return

    if time.time() > self.timer_start:
        self.abrir_off()
        self.vacio_off()
        self.alarm_manager.clear("ABRIENDO_MODO_SEGURO")
        self.timer_start = None
        self._pulso_desbloqueo_enviado = False
        self.set_state(DoorState.ERROR)
        logger.error("Error: Tiempo de apertura agotado.")
```

- [ ] **Step 5: Reemplazar `_from_cerrando()` completo**

```python
def _from_cerrando(self):
    safe_mode = self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO")

    if self.timer_start is None:
        self.timer_start = time.time() + self.config.get("timeout_puerta")
        self._pulso_bloqueo_enviado = False
        self._pulso_desbloqueo_enviado = False
        if safe_mode:
            self.alarm_manager.report(Alarm(
                alarm_id="ABRIENDO_MODO_SEGURO",
                alarm_type=AlarmType.ALERTA,
                source_state="PUERTA",
                description=f"Puerta {self.name}: cerrando en modo seguro (sin bomba de vacío).",
                recoverable=True,
            ))
        else:
            self.vacio_on()
        self.desbloquear_on()
        logger.info("Iniciando cierre de puerta%s.", " (modo seguro)" if safe_mode else "")

    if not self._pulso_desbloqueo_enviado:
        self.desbloquear_on()
        self._pulso_desbloqueo_enviado = True

    if self.atrapamiento() == 1:
        self.cerrar_off()
        self.alarm_manager.clear("ABRIENDO_MODO_SEGURO")
        self.timer_start = None
        self._pulso_bloqueo_enviado = False
        self._pulso_desbloqueo_enviado = False
        self.set_state(DoorState.ATRAPADA)
        return

    umbral = (
        (self.config.get("presion_admosferica") or 101.3) +
        (self.config.get("rango_presion_atm") or 20.0)
        if safe_mode
        else self.config.get("vacio_empaque")
    )

    if self.presion_empaque() <= umbral and not self.puerta_cerrada():
        self.cerrar_on()

    if self.puerta_cerrada() and not self.puerta_abierta():
        self.desbloquear_off()
        self.vacio_off()
        self.bloquear_on()

        if self.presion_empaque() >= self.config.get("presion_empaque"):
            self.bloquear_off()
            self.alarm_manager.clear("ABRIENDO_MODO_SEGURO")
            self.timer_start = None
            self.set_state(DoorState.CERRADO)
            logger.info("Puerta cerrada correctamente.")
            return

    if time.time() > self.timer_start:
        self.cerrar_off()
        self.vacio_off()
        self.desbloquear_off()
        self.bloquear_off()
        self.alarm_manager.clear("ABRIENDO_MODO_SEGURO")
        self._pulso_bloqueo_enviado = False
        self.timer_start = None
        self.set_state(DoorState.ERROR)
        logger.error("Error: Tiempo de cierre agotado.")
```

- [ ] **Step 6: Ejecutar — deben pasar**

```
pytest tests/test_advanced_door_safe_mode.py -v
```
Esperado: `5 passed`

- [ ] **Step 7: Regresión puertas**

```
pytest tests/test_door_from_profile.py tests/test_advanced_door_safe_mode.py -v
```
Esperado: todos green.

- [ ] **Step 8: Commit**

```
git add src/autoclave/devices/puertas/advanced_door.py tests/test_advanced_door_safe_mode.py
git commit -m "feat: AdvancedDoor modo seguro — abre/cierra sin bomba cuando hay fallo de suministro"
```

---

## Task 7: Wiring — door_factory y context pasan alarm_manager

**Files:**
- Modify: `src/autoclave/devices/puertas/door_factory.py`
- Modify: `src/autoclave/backend/context.py`

No hay tests unitarios para el wiring (depende de hardware). Se verifica en Task 8 cuando el sistema arranca.

- [ ] **Step 1: Modificar `door_factory.py`**

Reemplazar el bloque `elif door_type == 2`:

```python
elif door_type == 2:
    return AdvancedDoor(
        name=cfg["name"],
        di=cfg["di"],
        do=cfg["do"],
        ai=cfg["ai"],
        estado=estado,
        setdo=setdo,
        config=config,
        alarm_manager=io["alarm_manager"],
    )
```

- [ ] **Step 2: Modificar `context.py`**

En `BackendContext.__init__`, reemplazar la list-comprehension de `self.doors`:

```python
self.doors = [
    create_door(
        config=self.config_manager,
        io={
            "cfg":           cfg,
            "estado":        self.estado,
            "setdo":         self.setdo,
            "alarm_manager": self.alarm_manager,
        }
    )
    for cfg in doors_cfg
]
```

- [ ] **Step 3: Verificar que SimpleDoor no se rompe**

`SimpleDoor` no usa `alarm_manager`. Revisar `door_factory.py` — el `io["alarm_manager"]` solo se accede en el bloque `door_type == 2`. `SimpleDoor` (type 1) no lo usa, así que no hay problema.

- [ ] **Step 4: Correr suite completa de tests**

```
pytest tests/ -v --ignore=tests/Interfaz.py --ignore=tests/ventana_emergente.py
```
Esperado: todos green (sin contar tests de hardware/serial que requieren dispositivo).

- [ ] **Step 5: Commit**

```
git add src/autoclave/devices/puertas/door_factory.py src/autoclave/backend/context.py
git commit -m "feat: inyectar alarm_manager en AdvancedDoor via door_factory y context"
```

---

## Task 8: UI — indicador de suministro eléctrico en footer

**Files:**
- Modify: `src/autoclave/ui/window/main_window.py`

No hay tests automáticos de UI. Verificar visualmente al correr la app.

- [ ] **Step 1: Agregar `_lbl_suministro` en `_build_footer()`**

En `main_window.py`, dentro de `_build_footer()`, después de la línea que crea `self._lbl_conexion`:

```python
self._lbl_suministro = tk.Label(
    footer,
    text="⚡ Suministro: OK",
    font=("Segoe UI", 12),
    bg=CLR_BG,
    fg="#7FFF7F",
)
self._lbl_suministro.place(relx=0.17, rely=0.5, anchor="w")
```

- [ ] **Step 2: Agregar método `_upd_suministro()`**

En la sección de helpers de actualización, agregar:

```python
def _upd_suministro(self):
    di = self.ui_service.get_sensores_di()
    ok = bool(di.get("suministro_electrico", 1))
    if ok:
        self._lbl_suministro.configure(text="⚡ Suministro: OK", fg="#7FFF7F")
    else:
        self._lbl_suministro.configure(text="⚡ Sin suministro", fg="#FF7F7F")
```

- [ ] **Step 3: Llamar `_upd_suministro()` en el loop**

En `_update_ui()`, dentro del bloque `if self._tick % 2 == 0:`, después de `self._upd_listo()`:

```python
self._upd_suministro()
```

- [ ] **Step 4: Verificar en app (si hay hardware disponible)**

Arrancar la UI y confirmar:
- Indicador verde "⚡ Suministro: OK" visible en el footer junto al indicador de conexión.
- Al simular `suministro_electrico = 0` (o desconectar la DI), el indicador cambia a rojo "⚡ Sin suministro".

- [ ] **Step 5: Commit**

```
git add src/autoclave/ui/window/main_window.py
git commit -m "feat: indicador de suministro eléctrico en footer de la UI"
```

---

## Task 9: Suite final y regresión

- [ ] **Step 1: Correr todos los tests**

```
pytest tests/ -v --ignore=tests/Interfaz.py --ignore=tests/ventana_emergente.py
```
Esperado: todos green.

- [ ] **Step 2: Verificar criterios de aceptación manualmente (si hay hardware)**

1. `suministro_electrico = 0` + PREPARADO → botón inicio deshabilitado, alarma en panel izquierdo.
2. `suministro_electrico = 0` durante ciclo → ciclo aborta, cámara descomprime, estado FALLA.
3. Puerta avanzada con flag → abre sin bomba, alarma "ABRIENDO_MODO_SEGURO" visible.
4. Restaurar `suministro_electrico = 1` → flag limpio, sistema vuelve a permitir ciclos.

- [ ] **Step 3: Eliminar handoff.md si fue resuelto el issue original**

El `handoff.md` en raíz documenta un crash distinto (`CalentamientoFase`). No eliminarlo aún — ese issue sigue pendiente.

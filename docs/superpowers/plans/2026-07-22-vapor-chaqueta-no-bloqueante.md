# Vapor de chaqueta no bloqueante — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que la falta de suministro de vapor deje de bloquear PREPARACION y PREPARADO — el acondicionamiento de la chaqueta queda "pendiente" (sin abrir la válvula, con alarma informativa no bloqueante) hasta que el vapor regrese, sin frenar el resto de la secuencia.

**Architecture:** Se saca `vapor_suministro` de las listas de suministros "duros" en `preparacion.py` y `preparado.py`. La lógica de chaqueta (`suministrar_vapor_chaqueta()` / `mantener_chaqueta()`) pasa a tratar la falta de vapor como un caso "pendiente" que retorna `True` (no bloqueante) en vez de `False`, reportando una alarma con `blocks_operation=False` (mecanismo ya existente en `Alarm`, usado hoy en `advanced_door.py`). En PREPARACION, la función de chaqueta se desacopla del secuenciador de pasos para que siga reintentando en cada tick una vez alcanzado el paso 2, igual que ya hace `ciclo.py` con las fases. En CICLO no cambia el flujo de control (ya es no bloqueante), solo se añade la misma alarma informativa.

**Tech Stack:** Python 3.14, pytest, unittest.mock.

## Global Constraints

- Solo `vapor_suministro` deja de ser bloqueante. `agua_bomba`, `agua_generador`, `aire_comprimido` y `suministro_electrico` **no cambian** — siguen bloqueando exactamente igual que hoy en las tres funciones tocadas.
- Reutilizar `blocks_operation=False` de `Alarm` (ya existe en `state_machine/alarms/alarm.py:12`) para las alarmas informativas — no crear un mecanismo nuevo ni un flag nuevo en `EstadoAutoclave`.
- Cuando hay vapor pero la presión de chaqueta está fuera de banda, el comportamiento bloqueante **no cambia** en ningún estado (PREPARACION step 2, PREPARADO `esta_preparado()`).
- No se agrega timeout nuevo a PREPARACION ni PREPARADO.
- Spec completo: `docs/superpowers/specs/2026-07-22-vapor-chaqueta-no-bloqueante-design.md`.

---

### Task 1: PREPARACION — sacar `vapor_suministro` de `verificar_suministros()`

**Files:**
- Modify: `src/autoclave/state_machine/states/preparacion.py:156-174`
- Test: `tests/test_preparacion_suministro.py` (crear)

**Interfaces:**
- Consumes: `preparacion_state(alarm_manager, estado, set_do, cycle, config)` (constructor ya existente, sin cambios de firma)
- Produces: `verificar_suministros()` sigue retornando `bool`; ahora solo depende de `agua_bomba`, `agua_generador`, `aire_comprimido`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_preparacion_suministro.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.preparacion import preparacion_state


def _make_preparacion(vapor=1, agua_bomba=1, agua_generador=1, aire_comprimido=1):
    alarm_manager = MagicMock()
    estado = MagicMock()
    estado.sensores_di = {
        "vapor_suministro": vapor,
        "agua_bomba": agua_bomba,
        "agua_generador": agua_generador,
        "aire_comprimido": aire_comprimido,
    }
    set_do = MagicMock()
    cycle = MagicMock()
    config = MagicMock()
    p = preparacion_state(alarm_manager, estado, set_do, cycle, config)
    return p, alarm_manager


def test_falta_vapor_no_bloquea_verificar_suministros():
    p, alarm_mgr = _make_preparacion(vapor=0)
    assert p.verificar_suministros() is True
    ids = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert not any("VAPOR" in i for i in ids)


def test_falta_agua_bomba_sigue_bloqueando():
    p, alarm_mgr = _make_preparacion(agua_bomba=0)
    assert p.verificar_suministros() is False
    ids = [call.args[0].id for call in alarm_mgr.report.call_args_list]
    assert "SUMINISTRO_AGUA_BOMBA" in ids
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `python -m pytest tests/test_preparacion_suministro.py -v`
Expected: `test_falta_vapor_no_bloquea_verificar_suministros` FALLA (hoy `verificar_suministros()` retorna `False` con vapor=0, y reporta `SUMINISTRO_VAPOR_SUMINISTRO`).

- [ ] **Step 3: Implementar el cambio mínimo**

En `src/autoclave/state_machine/states/preparacion.py`, función `verificar_suministros()` (líneas 156-174), cambiar:

```python
    def verificar_suministros(self):
        suministros = [
            "vapor_suministro",
            "agua_bomba",
            "agua_generador",
            "aire_comprimido",
        ]
```

por:

```python
    def verificar_suministros(self):
        suministros = [
            "agua_bomba",
            "agua_generador",
            "aire_comprimido",
        ]
```

- [ ] **Step 4: Ejecutar y verificar que pasa**

Run: `python -m pytest tests/test_preparacion_suministro.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/preparacion.py tests/test_preparacion_suministro.py
git commit -m "fix: vapor de chaqueta ya no bloquea verificar_suministros en PREPARACION"
```

---

### Task 2: PREPARACION — chaqueta no bloqueante y continua desde el paso 2

**Files:**
- Modify: `src/autoclave/state_machine/states/preparacion.py:48-57` (helper `alarm()`), `:78-113` (`ejecutor()`), `:185-220` (`suministrar_vapor_chaqueta()`)
- Test: `tests/test_preparacion_chaqueta.py` (crear)

**Interfaces:**
- Consumes: `Alarm(alarm_id, alarm_type, source_state, description, recoverable, blocks_operation)` de `state_machine/alarms/alarm.py` (el parámetro `blocks_operation` ya existe en `Alarm.__init__`, default `True`).
- Produces: `self.alarm(alarm_id, alarm_type, blocks_operation=True)` — nuevo parámetro opcional en el helper de `preparacion_state`. `suministrar_vapor_chaqueta()` sigue retornando `bool`, ahora `True` también cuando falta vapor (pendiente).

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_preparacion_chaqueta.py`:

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


def test_sin_vapor_avanza_step_sin_bloquear():
    p, alarm_mgr, set_do = _make_preparacion(vapor=0)
    p.step = 2
    p.ejecutor()
    assert p.step == 3
    set_do.vapor_chaqueta_off.assert_called()


def test_sin_vapor_reporta_alarma_no_bloqueante():
    p, alarm_mgr, _ = _make_preparacion(vapor=0)
    p.step = 2
    p.ejecutor()
    alarma = alarm_mgr.report.call_args.args[0]
    assert alarma.id == "SUMINISTRO_VAPOR"
    assert alarma.blocks_operation is False


def test_con_vapor_fuera_de_banda_no_avanza():
    p, alarm_mgr, set_do = _make_preparacion(vapor=1, presion_chaqueta=100.0)
    p.step = 2
    p.ejecutor()
    assert p.step == 2
    set_do.vapor_chaqueta_on.assert_called()


def test_vapor_vuelve_despues_de_avanzar_retoma_chaqueta():
    p, alarm_mgr, set_do = _make_preparacion(vapor=0, presion_chaqueta=100.0)
    p.step = 4
    p.ejecutor()
    p.estado.sensores_di["vapor_suministro"] = 1
    p.ejecutor()
    set_do.vapor_chaqueta_on.assert_called()
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `python -m pytest tests/test_preparacion_chaqueta.py -v`
Expected: FAIL — hoy con `vapor=0` el step queda en 2 (no avanza a 3) y `suministrar_vapor_chaqueta()` no se llama en step 4.

- [ ] **Step 3: Implementar el cambio mínimo**

En `src/autoclave/state_machine/states/preparacion.py`, el helper `alarm()` (líneas 48-57):

```python
    def alarm (self, alarm_id, alarm_type):
        nivel = _NIVEL_TXT.get(alarm_type, "Alerta")
        alarm = Alarm(
            alarm_id=alarm_id,
            alarm_type=alarm_type,
            source_state="PREPARACION",
            description=f"{nivel}: {alarm_id} en PREPARACION.",
            recoverable=True
        )
        self.alarm_manager.report(alarm)
```

por:

```python
    def alarm (self, alarm_id, alarm_type, blocks_operation=True):
        nivel = _NIVEL_TXT.get(alarm_type, "Alerta")
        alarm = Alarm(
            alarm_id=alarm_id,
            alarm_type=alarm_type,
            source_state="PREPARACION",
            description=f"{nivel}: {alarm_id} en PREPARACION.",
            recoverable=True,
            blocks_operation=blocks_operation,
        )
        self.alarm_manager.report(alarm)
```

`ejecutor()` (líneas 78-113), cambiar:

```python
    def ejecutor(self):
        logger.info(f"Ejecución del estado PREPARACION, paso {self.step}")
        if self.estado.sensores_di["paro_emergencia"]:
            self.set_do.reset_all_outputs()
            self.alarm("PARO_EMERGENCIA", AlarmType.EMERGENCIA)
            self.set_do.buzer_emergencia()
            return

        else:
            self.set_do.buzer_off()
            self.alarm_manager.clear("PARO_EMERGENCIA")


        if self.step == 0:
                self.step = 1
        
        elif self.step == 1:
                self.step = 2
        
        elif self.step == 2:
            if self.suministrar_vapor_chaqueta():
                self.step = 3
                
        elif self.step == 3:
            if self.igualar_presion_camara():
                self.step = 4
                
        elif self.step == 4:
            if self.drenar_camara():
                self.step = 5
                
        elif self.step == 5:
            if self.verificar_temperatura_drenaje():
                return True  # Indica que la preparación ha finalizado
            
        return False
```

por:

```python
    def ejecutor(self):
        logger.info(f"Ejecución del estado PREPARACION, paso {self.step}")
        if self.estado.sensores_di["paro_emergencia"]:
            self.set_do.reset_all_outputs()
            self.alarm("PARO_EMERGENCIA", AlarmType.EMERGENCIA)
            self.set_do.buzer_emergencia()
            return

        else:
            self.set_do.buzer_off()
            self.alarm_manager.clear("PARO_EMERGENCIA")

        # Desde el paso 2 en adelante, la chaqueta se acondiciona en cada
        # tick sin importar el paso actual: si el vapor vuelve después de
        # que el secuenciador ya avanzó, retoma sola sin bloquear nada.
        chaqueta_lista = None
        if self.step >= 2:
            chaqueta_lista = self.suministrar_vapor_chaqueta()

        if self.step == 0:
                self.step = 1
        
        elif self.step == 1:
                self.step = 2
        
        elif self.step == 2:
            if chaqueta_lista:
                self.step = 3
                
        elif self.step == 3:
            if self.igualar_presion_camara():
                self.step = 4
                
        elif self.step == 4:
            if self.drenar_camara():
                self.step = 5
                
        elif self.step == 5:
            if self.verificar_temperatura_drenaje():
                return True  # Indica que la preparación ha finalizado
            
        return False
```

`suministrar_vapor_chaqueta()` (líneas 185-220), cambiar:

```python
    def suministrar_vapor_chaqueta(self):
            presion = self.estado.sensores_pres["pres_chaqueta"]
            pres_obj=self.cycle.get_param("globals","presion_chaqueta")
            rango=self.cycle.get_param("globals","rango_presion_chaqueta")

            limite_inf = pres_obj - rango
            limite_sup = pres_obj + rango

            # Verificar suministro
            if not self.estado.sensores_di["vapor_suministro"]:
                alarm_id = "SUMINISTRO_VAPOR"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False
            else:
                self.alarm_manager.clear("SUMINISTRO_VAPOR")

            # Presión dentro de rango → listo
            if limite_inf <= presion <= limite_sup:
                self.set_do.vapor_chaqueta_off()
                self.alarm_manager.clear("CHAQUETA_FRIA")
                self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")
                return True

            # Presión baja → abrir vapor
            if presion < limite_inf:
                self.set_do.vapor_chaqueta_on()
                alarm_id = "CHAQUETA_FRIA"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False

            # Presión alta → cerrar vapor
            elif presion >= limite_sup:
                self.set_do.vapor_chaqueta_off()
                alarm_id = "CHAQUETA_SOBRECALENTADA"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False
```

por:

```python
    def suministrar_vapor_chaqueta(self):
            presion = self.estado.sensores_pres["pres_chaqueta"]
            pres_obj=self.cycle.get_param("globals","presion_chaqueta")
            rango=self.cycle.get_param("globals","rango_presion_chaqueta")

            limite_inf = pres_obj - rango
            limite_sup = pres_obj + rango

            # Verificar suministro. Si no hay vapor, no insistir en abrir la
            # válvula (generaría vapor demasiado húmedo por baja presión de
            # línea): se deja "pendiente", no bloqueante.
            if not self.estado.sensores_di["vapor_suministro"]:
                self.set_do.vapor_chaqueta_off()
                self.alarm("SUMINISTRO_VAPOR", AlarmType.ALERTA, blocks_operation=False)
                self.alarm_manager.clear("CHAQUETA_FRIA")
                self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")
                return True
            else:
                self.alarm_manager.clear("SUMINISTRO_VAPOR")

            # Presión dentro de rango → listo
            if limite_inf <= presion <= limite_sup:
                self.set_do.vapor_chaqueta_off()
                self.alarm_manager.clear("CHAQUETA_FRIA")
                self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")
                return True

            # Presión baja → abrir vapor
            if presion < limite_inf:
                self.set_do.vapor_chaqueta_on()
                alarm_id = "CHAQUETA_FRIA"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False

            # Presión alta → cerrar vapor
            elif presion >= limite_sup:
                self.set_do.vapor_chaqueta_off()
                alarm_id = "CHAQUETA_SOBRECALENTADA"
                self.alarm(alarm_id, AlarmType.ALERTA)
                return False
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `python -m pytest tests/test_preparacion_chaqueta.py -v`
Expected: 4 passed

- [ ] **Step 5: Ejecutar el test de wording existente para confirmar que no se rompió**

Run: `python -m pytest tests/test_preparacion_alarm_wording.py -v`
Expected: 3 passed (la firma nueva de `alarm()` con `blocks_operation=True` por default es compatible con las llamadas de 2 argumentos posicionales que usa ese test).

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/states/preparacion.py tests/test_preparacion_chaqueta.py
git commit -m "feat: chaqueta no bloqueante y continua en PREPARACION ante falta de vapor"
```

---

### Task 3: PREPARADO — sacar `vapor_suministro` de `verificar_suministros()`

**Files:**
- Modify: `src/autoclave/state_machine/states/preparado.py:239-249`
- Test: `tests/test_preparado_suministro.py` (modificar — agregar test)

**Interfaces:**
- Consumes: `preparado_state(alarm_manager, estado, set_do, cycle, config)` (sin cambios de firma)
- Produces: `verificar_suministros()` sigue retornando `bool`; ahora solo depende de `agua_bomba`, `agua_generador`, `aire_comprimido`, `suministro_electrico`.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `tests/test_preparado_suministro.py` (al final del archivo):

```python
def test_falta_vapor_no_bloquea_verificar_suministros():
    p, alarm_mgr = _make_preparado()
    p.estado.sensores_di["vapor_suministro"] = 0
    assert p.verificar_suministros() is True
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `python -m pytest tests/test_preparado_suministro.py -v`
Expected: `test_falta_vapor_no_bloquea_verificar_suministros` FALLA (hoy retorna `False`).

- [ ] **Step 3: Implementar el cambio mínimo**

En `src/autoclave/state_machine/states/preparado.py`, función `verificar_suministros()` (líneas 239-249), cambiar:

```python
    def verificar_suministros(self):
        ok = True

        for suministro, estado in self.estado.sensores_di.items():
            if suministro in ["vapor_suministro", "agua_bomba", "agua_generador", "aire_comprimido"]:
                if not estado:
                    self.alarm(f"SUMINISTRO_{suministro.upper()}", AlarmType.ALERTA)
                    ok = False
                else:
                    self.alarm_manager.clear(f"SUMINISTRO_{suministro.upper()}")
```

por:

```python
    def verificar_suministros(self):
        ok = True

        for suministro, estado in self.estado.sensores_di.items():
            if suministro in ["agua_bomba", "agua_generador", "aire_comprimido"]:
                if not estado:
                    self.alarm(f"SUMINISTRO_{suministro.upper()}", AlarmType.ALERTA)
                    ok = False
                else:
                    self.alarm_manager.clear(f"SUMINISTRO_{suministro.upper()}")
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `python -m pytest tests/test_preparado_suministro.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/state_machine/states/preparado.py tests/test_preparado_suministro.py
git commit -m "fix: vapor de chaqueta ya no bloquea verificar_suministros en PREPARADO"
```

---

### Task 4: PREPARADO — `mantener_chaqueta()` no bloquea `esta_preparado()` sin vapor

**Files:**
- Modify: `src/autoclave/state_machine/states/preparado.py:25-33` (helper `alarm()`), `:86-118` (`mantener_chaqueta()`)
- Test: `tests/test_preparado_chaqueta.py` (crear)

**Interfaces:**
- Consumes: `Alarm(..., blocks_operation=...)` (ya existe, ver Task 2)
- Produces: `self.alarm(alarm_id, alarm_type, blocks_operation=True)` — nuevo parámetro opcional en el helper de `preparado_state`. `mantener_chaqueta()` sigue retornando `bool`, ahora `True` también cuando falta vapor (pendiente); `esta_preparado()` no cambia (sigue siendo el AND de las 6 condiciones).

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_preparado_chaqueta.py`:

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
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `python -m pytest tests/test_preparado_chaqueta.py -v`
Expected: FAIL en `test_sin_vapor_mantener_chaqueta_retorna_true`, `test_sin_vapor_alarma_no_bloqueante` y `test_esta_preparado_true_sin_vapor_con_resto_ok` (hoy `mantener_chaqueta()` retorna `False` sin vapor).

- [ ] **Step 3: Implementar el cambio mínimo**

En `src/autoclave/state_machine/states/preparado.py`, helper `alarm()` (líneas 25-33):

```python
    def alarm(self, alarm_id, alarm_type):
        alarm = Alarm(
            alarm_id=alarm_id,
            alarm_type=alarm_type,
            source_state="PREPARADO",
            description=f"Error {alarm_id} en estado PREPARADO",
            recoverable=True
        )
        self.alarm_manager.report(alarm)
```

por:

```python
    def alarm(self, alarm_id, alarm_type, blocks_operation=True):
        alarm = Alarm(
            alarm_id=alarm_id,
            alarm_type=alarm_type,
            source_state="PREPARADO",
            description=f"Error {alarm_id} en estado PREPARADO",
            recoverable=True,
            blocks_operation=blocks_operation,
        )
        self.alarm_manager.report(alarm)
```

`mantener_chaqueta()` (líneas 86-118), cambiar:

```python
    def mantener_chaqueta(self):
        press_chaqueta = self.estado.sensores_pres["pres_chaqueta"]
        press_obj = self.cycle.get_param("globals", "presion_chaqueta")
        rango=self.cycle.get_param("globals","rango_presion_chaqueta")


        limite_inf = press_obj - rango
        limite_sup = press_obj + rango

        # Suministro
        if not self.estado.sensores_di["vapor_suministro"]:
            self.alarm("SUMINISTRO_VAPOR", AlarmType.ALERTA)
            return False
        else:
            self.alarm_manager.clear("SUMINISTRO_VAPOR")
```

por:

```python
    def mantener_chaqueta(self):
        press_chaqueta = self.estado.sensores_pres["pres_chaqueta"]
        press_obj = self.cycle.get_param("globals", "presion_chaqueta")
        rango=self.cycle.get_param("globals","rango_presion_chaqueta")


        limite_inf = press_obj - rango
        limite_sup = press_obj + rango

        # Suministro. Sin vapor, no insistir en abrir la válvula: se deja
        # "pendiente", no bloqueante (no debe frenar esta_preparado()).
        if not self.estado.sensores_di["vapor_suministro"]:
            self.set_do.vapor_chaqueta_off()
            self.alarm("SUMINISTRO_VAPOR", AlarmType.ALERTA, blocks_operation=False)
            self.alarm_manager.clear("CHAQUETA_FRIA")
            self.alarm_manager.clear("CHAQUETA_SOBRECALENTADA")
            return True
        else:
            self.alarm_manager.clear("SUMINISTRO_VAPOR")
```

(El resto de la función —bloque "Dentro de rango" / "Fuera de rango"— no cambia.)

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `python -m pytest tests/test_preparado_chaqueta.py -v`
Expected: 4 passed

- [ ] **Step 5: Ejecutar el resto de tests de PREPARADO para confirmar que no se rompió nada**

Run: `python -m pytest tests/test_preparado_suministro.py -v`
Expected: 4 passed (incluye el test del Task 3)

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/states/preparado.py tests/test_preparado_chaqueta.py
git commit -m "feat: chaqueta no bloqueante en PREPARADO ante falta de vapor"
```

---

### Task 5: CICLO — alarma informativa no bloqueante en `_mantener_chaqueta()`

**Files:**
- Modify: `src/autoclave/state_machine/states/ciclo.py:143-146`
- Test: `tests/test_ciclo_chaqueta.py` (crear)

**Interfaces:**
- Consumes: `Alarm`, `AlarmType` (ya importados en `ciclo.py:18-19`); `CicloState(estado, set_do, cycle, config, alarm_manager, cap=None)` (constructor existente, sin cambios de firma)
- Produces: `_mantener_chaqueta()` no cambia su tipo de retorno (`None`); solo agrega el reporte/limpieza de la alarma `SUMINISTRO_VAPOR` con `blocks_operation=False`. No se toca el flujo de `run()` ni el resultado del ciclo.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_ciclo_chaqueta.py`:

```python
from unittest.mock import MagicMock
from autoclave.state_machine.states.ciclo import CicloState


def _make_ciclo(vapor=1, pres_chaqueta=300.0):
    estado = MagicMock()
    estado.sensores_pres = {"pres_chaqueta": pres_chaqueta}
    estado.sensores_di = {"vapor_suministro": vapor}
    set_do = MagicMock()
    cycle = MagicMock()
    cycle.get_param.return_value = None
    config = MagicMock()
    config.get.return_value = None
    alarm_manager = MagicMock()
    ciclo = CicloState(estado, set_do, cycle, config, alarm_manager)
    return ciclo, set_do, alarm_manager


def test_sin_vapor_apaga_valvula_y_reporta_alarma_no_bloqueante():
    ciclo, set_do, alarm_manager = _make_ciclo(vapor=0)
    ciclo._mantener_chaqueta()
    set_do.vapor_chaqueta_off.assert_called_once()
    alarma = alarm_manager.report.call_args.args[0]
    assert alarma.id == "SUMINISTRO_VAPOR"
    assert alarma.blocks_operation is False


def test_con_vapor_limpia_alarma():
    ciclo, set_do, alarm_manager = _make_ciclo(vapor=1, pres_chaqueta=300.0)
    ciclo._mantener_chaqueta()
    alarm_manager.clear.assert_any_call("SUMINISTRO_VAPOR")
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `python -m pytest tests/test_ciclo_chaqueta.py -v`
Expected: `test_sin_vapor_apaga_valvula_y_reporta_alarma_no_bloqueante` FALLA (hoy `alarm_manager.report` no se llama).

- [ ] **Step 3: Implementar el cambio mínimo**

En `src/autoclave/state_machine/states/ciclo.py`, función `_mantener_chaqueta()` (líneas 135-157), cambiar:

```python
        # Si no hay suministro de vapor, no intentar compensar
        if not self.estado.sensores_di.get("vapor_suministro", 0):
            self.set_do.vapor_chaqueta_off()
            return
```

por:

```python
        # Si no hay suministro de vapor, no intentar compensar
        if not self.estado.sensores_di.get("vapor_suministro", 0):
            self.set_do.vapor_chaqueta_off()
            self.alarm_manager.report(Alarm(
                alarm_id="SUMINISTRO_VAPOR",
                alarm_type=AlarmType.ALERTA,
                source_state="CICLO",
                description="Sin suministro de vapor: chaqueta pendiente hasta que regrese.",
                recoverable=True,
                blocks_operation=False,
            ))
            return
        else:
            self.alarm_manager.clear("SUMINISTRO_VAPOR")
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `python -m pytest tests/test_ciclo_chaqueta.py -v`
Expected: 2 passed

- [ ] **Step 5: Ejecutar la suite completa de CICLO para confirmar que no se rompió nada**

Run: `python -m pytest tests/test_ciclo_suministro.py tests/test_ciclo_sensores.py -v`
Expected: todos passed (el manejo de `FALLO_SUMINISTRO_ELECTRICO` no se toca; es un flag distinto de `vapor_suministro`)

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/state_machine/states/ciclo.py tests/test_ciclo_chaqueta.py
git commit -m "feat: alarma informativa no bloqueante para falta de vapor durante CICLO"
```

---

### Task 6: Suite completa

**Files:** ninguno (solo verificación)

- [ ] **Step 1: Ejecutar toda la suite de tests**

Run: `python -m pytest tests/ -v`
Expected: todos passed, sin regresiones en ningún archivo de test existente.

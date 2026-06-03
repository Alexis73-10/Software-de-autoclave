# Door Lock / Decomp Modes / Generador Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar 5 mejoras identificadas en pruebas: desbloqueo sostenido de empaque, límite de modos de descompresión por clase de equipo, bloqueo de apertura por sensor en puertas motorizadas, historial de generación de códigos con lógica de reinstalación, y eliminación de perfil bloqueado antes de reinstalar.

**Architecture:** Cada tarea es independiente. Items 1–4 tocan el proyecto principal (`src/`). Item 5 es la mini-app `tools/generador/`. El generador gana un módulo `db.py` separado de `app.py` para que la lógica de BD sea testeable sin FastAPI.

**Tech Stack:** Python 3.14, pytest, SQLite (`sqlite3` stdlib), FastAPI (generador), Tkinter (wizard).

---

## Mapa de archivos

| Archivo | Acción | Tarea |
|---------|--------|-------|
| `src/autoclave/installation/equipment.py` | Modificar — agregar `cooling_mode_max` | 1 |
| `src/autoclave/installation/storage.py` | Modificar — agregar `delete()` | 2 |
| `src/autoclave/installation/wizard.py` | Modificar — llamar `storage.delete()` antes de `save()` | 2 |
| `src/autoclave/devices/factory/factory.py` | Modificar — agregar `di["bloqueo"]` para MOTORIZED | 3 |
| `src/autoclave/devices/puertas/advanced_door.py` | Modificar — `cmd_abrir()` + `_from_abriendo()` | 3, 4 |
| `tools/generador/db.py` | Crear — helpers de BD | 5 |
| `tools/generador/app.py` | Modificar — historial + reinstalación | 6 |
| `tests/test_equipment.py` | Modificar — agregar test `cooling_mode_max` | 1 |
| `tests/test_storage.py` | Crear — tests de `delete()` | 2 |
| `tests/test_advanced_door.py` | Crear — tests items 3 y 4 | 3, 4 |
| `tests/test_generador_db.py` | Crear — tests DB del generador | 5 |

---

## Task 1: EquipmentCapabilities — cooling_mode_max

**Files:**
- Modify: `src/autoclave/installation/equipment.py`
- Modify: `tests/test_equipment.py`

- [ ] **Step 1.1 — Escribir el test que falla**

Agregar al final de `tests/test_equipment.py`:

```python
def test_cooling_mode_max_por_clase():
    assert get_capabilities(EquipmentClass.MESA_N).cooling_mode_max == 1
    assert get_capabilities(EquipmentClass.MESA_B).cooling_mode_max == 3
    assert get_capabilities(EquipmentClass.MESA_B_LAB).cooling_mode_max == 5
    assert get_capabilities(EquipmentClass.PISO).cooling_mode_max == 3
    assert get_capabilities(EquipmentClass.PISO_LAB).cooling_mode_max == 5
```

- [ ] **Step 1.2 — Verificar que falla**

```
pytest tests/test_equipment.py::test_cooling_mode_max_por_clase -v
```

Esperado: `FAILED` — `AttributeError: 'EquipmentCapabilities' object has no attribute 'cooling_mode_max'`

- [ ] **Step 1.3 — Implementar**

En `src/autoclave/installation/equipment.py`, agregar el campo al dataclass y los valores al dict `_CAPABILITIES`. El archivo completo queda así:

```python
from dataclasses import dataclass
from enum import Enum


class EquipmentClass(Enum):
    MESA_N     = "mesa_n"
    MESA_B     = "mesa_b"
    MESA_B_LAB = "mesa_b_lab"
    PISO       = "piso"
    PISO_LAB   = "piso_lab"


@dataclass(frozen=True)
class EquipmentCapabilities:
    has_vacuum:        bool
    has_full_jacket:   bool
    door_count_max:    int
    cooling_level_max: int
    has_liquids:       bool
    has_liquid_sensor: bool
    bleve_protection:  bool
    cooling_mode_max:  int


_CAPABILITIES: dict[EquipmentClass, EquipmentCapabilities] = {
    EquipmentClass.MESA_N: EquipmentCapabilities(
        has_vacuum=False, has_full_jacket=False, door_count_max=1,
        cooling_level_max=0, has_liquids=False, has_liquid_sensor=False,
        bleve_protection=False, cooling_mode_max=1,
    ),
    EquipmentClass.MESA_B: EquipmentCapabilities(
        has_vacuum=True, has_full_jacket=False, door_count_max=1,
        cooling_level_max=0, has_liquids=False, has_liquid_sensor=False,
        bleve_protection=False, cooling_mode_max=3,
    ),
    EquipmentClass.MESA_B_LAB: EquipmentCapabilities(
        has_vacuum=True, has_full_jacket=False, door_count_max=1,
        cooling_level_max=0, has_liquids=True, has_liquid_sensor=True,
        bleve_protection=True, cooling_mode_max=5,
    ),
    EquipmentClass.PISO: EquipmentCapabilities(
        has_vacuum=True, has_full_jacket=True, door_count_max=2,
        cooling_level_max=4, has_liquids=False, has_liquid_sensor=False,
        bleve_protection=False, cooling_mode_max=3,
    ),
    EquipmentClass.PISO_LAB: EquipmentCapabilities(
        has_vacuum=True, has_full_jacket=True, door_count_max=2,
        cooling_level_max=4, has_liquids=True, has_liquid_sensor=True,
        bleve_protection=True, cooling_mode_max=5,
    ),
}


def get_capabilities(equipment_class: EquipmentClass) -> EquipmentCapabilities:
    return _CAPABILITIES[equipment_class]
```

- [ ] **Step 1.4 — Verificar que pasa**

```
pytest tests/test_equipment.py -v
```

Esperado: todos los tests pasan.

- [ ] **Step 1.5 — Commit**

```
git add src/autoclave/installation/equipment.py tests/test_equipment.py
git commit -m "feat: EquipmentCapabilities agrega cooling_mode_max por clase de equipo"
```

---

## Task 2: storage.delete() + wizard reinstalación

**Files:**
- Modify: `src/autoclave/installation/storage.py`
- Modify: `src/autoclave/installation/wizard.py`
- Create: `tests/test_storage.py`

- [ ] **Step 2.1 — Escribir tests que fallan**

Crear `tests/test_storage.py`:

```python
import json
import pytest
from autoclave.installation import storage
from autoclave.installation.storage import delete


def _write_fake_profile(path):
    path.write_text(json.dumps({"locked": True}), encoding="utf-8")


def test_delete_elimina_archivo_existente(tmp_path, monkeypatch):
    fake = tmp_path / "installation_profile.json"
    _write_fake_profile(fake)
    monkeypatch.setattr(storage, "INSTALLATION_FILE", fake)

    assert fake.exists()
    delete()
    assert not fake.exists()


def test_delete_sin_archivo_no_lanza_excepcion(tmp_path, monkeypatch):
    fake = tmp_path / "installation_profile.json"
    monkeypatch.setattr(storage, "INSTALLATION_FILE", fake)

    assert not fake.exists()
    delete()  # no debe lanzar


def test_save_falla_si_bloqueado_y_existe(tmp_path, monkeypatch):
    """Documenta el comportamiento existente: save lanza si locked=True y el archivo existe."""
    from autoclave.installation.storage import save
    from autoclave.installation.profile import InstallationProfile, Role
    from autoclave.installation.equipment import EquipmentClass
    from autoclave.devices.puertas.door_type import DoorType
    from datetime import datetime

    fake = tmp_path / "installation_profile.json"
    _write_fake_profile(fake)
    monkeypatch.setattr(storage, "INSTALLATION_FILE", fake)

    profile = InstallationProfile(
        machine_id="X", model_id="M", serial_number="S",
        equipment_class=EquipmentClass.MESA_B,
        door_count=1, door_type=DoorType.SIMPLE,
        cooling_level=0, door_id=1,
        role=Role.OPERATOR_FRONT,
        created_at=datetime.utcnow(),
        locked=True,
    )
    with pytest.raises(RuntimeError, match="bloqueado"):
        save(profile)


def test_delete_luego_save_funciona(tmp_path, monkeypatch):
    """Después de delete(), save() puede guardar aunque locked=True."""
    from autoclave.installation.storage import save
    from autoclave.installation.profile import InstallationProfile, Role
    from autoclave.installation.equipment import EquipmentClass
    from autoclave.devices.puertas.door_type import DoorType
    from datetime import datetime

    fake = tmp_path / "installation_profile.json"
    _write_fake_profile(fake)
    monkeypatch.setattr(storage, "INSTALLATION_FILE", fake)

    profile = InstallationProfile(
        machine_id="X", model_id="M", serial_number="SN001",
        equipment_class=EquipmentClass.MESA_B,
        door_count=1, door_type=DoorType.SIMPLE,
        cooling_level=0, door_id=1,
        role=Role.OPERATOR_FRONT,
        created_at=datetime.utcnow(),
        locked=True,
    )
    delete()
    save(profile)  # no debe lanzar
    assert fake.exists()
```

- [ ] **Step 2.2 — Verificar que fallan**

```
pytest tests/test_storage.py -v
```

Esperado: `test_delete_*` fallan con `AttributeError` (función no existe aún).

- [ ] **Step 2.3 — Agregar `delete()` a storage.py**

Agregar al final de `src/autoclave/installation/storage.py`:

```python
def delete():
    INSTALLATION_FILE.unlink(missing_ok=True)
```

- [ ] **Step 2.4 — Verificar que los tests pasan**

```
pytest tests/test_storage.py -v
```

Esperado: todos pasan.

- [ ] **Step 2.5 — Actualizar wizard.py**

En `src/autoclave/installation/wizard.py`, en la función `instalar()`, localizar la llamada a `save(profile)` y agregar `storage.delete()` justo antes:

Cambiar el import al inicio del archivo — agregar `storage` al import existente:
```python
from .storage import save, delete as delete_profile
```

Luego en `instalar()`, reemplazar:
```python
        try:
            save(profile)
```
por:
```python
        try:
            delete_profile()
            save(profile)
```

- [ ] **Step 2.6 — Verificar suite completa**

```
pytest tests/test_storage.py tests/test_profile_validation.py -v
```

Esperado: todos pasan.

- [ ] **Step 2.7 — Commit**

```
git add src/autoclave/installation/storage.py src/autoclave/installation/wizard.py tests/test_storage.py
git commit -m "feat: storage.delete() + wizard borra perfil bloqueado antes de reinstalar"
```

---

## Task 3: Puerta motorizada — bloquear apertura por sensor

**Files:**
- Modify: `src/autoclave/devices/factory/factory.py`
- Modify: `src/autoclave/devices/puertas/advanced_door.py`
- Create: `tests/test_advanced_door.py`

- [ ] **Step 3.1 — Escribir tests que fallan**

Crear `tests/test_advanced_door.py`:

```python
import pytest
from unittest.mock import MagicMock
from autoclave.devices.puertas.advanced_door import AdvancedDoor, DoorState
from autoclave.devices.factory.factory import _build_door_cfg
from autoclave.devices.puertas.door_type import DoorType


_CONFIG = {
    "vacio_empaque": 30,
    "timeout_puerta": 60,
    "presion_empaque": 300,
    "presion_admosferica": 74.5,
    "rango_presion_atm": 20,
}


def _make_door(di_extra=None, bloqueo_sensor_val=0):
    estado = MagicMock()
    estado.get_door_state.return_value = DoorState.CERRADO
    estado.get_flag.return_value = False
    estado.sensores_di.get.return_value = bloqueo_sensor_val
    estado.sensores_pres.get.return_value = 300.0

    di = {"abierta": "puerta_1_abierta", "cerrada": "puerta_1_cerrada"}
    if di_extra:
        di.update(di_extra)

    door = AdvancedDoor(
        name="Puerta 1",
        di=di,
        do={"abrir": 19, "cerrar": 21},
        ai={},
        estado=estado,
        setdo=MagicMock(),
        config=_CONFIG,
        alarm_manager=None,
    )
    return door


# ── Tests de factory ──────────────────────────────────────────────────────────

def test_motorized_cfg_tiene_sensor_bloqueo():
    cfg = _build_door_cfg(1, DoorType.MOTORIZED)
    assert "bloqueo" in cfg["di"]
    assert cfg["di"]["bloqueo"] == "bloqueo_puerta_1"


def test_motorized_locking_cfg_tiene_sensor_bloqueo():
    cfg = _build_door_cfg(1, DoorType.MOTORIZED_LOCKING)
    assert "bloqueo" in cfg["di"]
    assert cfg["di"]["bloqueo"] == "bloqueo_puerta_1"


def test_advanced_cfg_no_tiene_sensor_bloqueo():
    cfg = _build_door_cfg(1, DoorType.ADVANCED)
    assert "bloqueo" not in cfg["di"]


def test_simple_cfg_no_tiene_sensor_bloqueo():
    cfg = _build_door_cfg(1, DoorType.SIMPLE)
    assert "bloqueo" not in cfg["di"]


# ── Tests de cmd_abrir ────────────────────────────────────────────────────────

def test_cmd_abrir_bloqueada_no_transiciona():
    door = _make_door(di_extra={"bloqueo": "bloqueo_puerta_1"}, bloqueo_sensor_val=1)
    door.cmd_abrir()
    door.estado.update_door_state.assert_not_called()


def test_cmd_abrir_desbloqueada_transiciona():
    door = _make_door(di_extra={"bloqueo": "bloqueo_puerta_1"}, bloqueo_sensor_val=0)
    door.cmd_abrir()
    door.estado.update_door_state.assert_called_once_with("Puerta 1", DoorState.ABRIENDO)


def test_cmd_abrir_sin_sensor_bloqueo_siempre_transiciona():
    """ADVANCED no tiene di['bloqueo'], siempre permite apertura desde este método."""
    door = _make_door()
    door.cmd_abrir()
    door.estado.update_door_state.assert_called_once_with("Puerta 1", DoorState.ABRIENDO)
```

- [ ] **Step 3.2 — Verificar que fallan**

```
pytest tests/test_advanced_door.py -v
```

Esperado: los tests de factory fallan (sin `di["bloqueo"]`) y los de `cmd_abrir` fallan (sin la verificación).

- [ ] **Step 3.3 — Actualizar factory.py**

En `src/autoclave/devices/factory/factory.py`, dentro de `_build_door_cfg()`, agregar después del bloque `if has_sensor:`:

```python
    has_mech_lock_sensor = door_type in (DoorType.MOTORIZED, DoorType.MOTORIZED_LOCKING)
    if has_mech_lock_sensor:
        cfg["di"]["bloqueo"] = f"bloqueo_puerta_{n}"
```

El archivo completo queda:

```python
from autoclave.hal.units import Units
from autoclave.protocols.serial_link import SerialLink
from autoclave.utils.resources import resource_path
from autoclave.devices.puertas.door_type import DoorType

_DOOR_DO_CHANNELS = {
    1: {"abrir": 20, "cerrar": 22, "desbloquear": 9,  "bloquear": 11},
    2: {"abrir": 21, "cerrar": 23, "desbloquear": 10, "bloquear": 12},
}


def _build_door_cfg(n: int, door_type: DoorType) -> dict:
    do_ch = _DOOR_DO_CHANNELS[n]
    cfg = {
        "name": f"Puerta {n}",
        "type": door_type,
        "di": {
            "abierta": f"puerta_{n}_abierta",
            "cerrada": f"puerta_{n}_cerrada",
        },
    }

    has_motor  = door_type in (DoorType.MOTORIZED, DoorType.MOTORIZED_LOCKING, DoorType.ADVANCED)
    has_lock   = door_type in (DoorType.LOCKING, DoorType.MOTORIZED_LOCKING, DoorType.ADVANCED)
    has_sensor = door_type == DoorType.ADVANCED
    has_mech_lock_sensor = door_type in (DoorType.MOTORIZED, DoorType.MOTORIZED_LOCKING)

    if has_motor or has_lock:
        do = {}
        if has_motor:
            do["abrir"]  = do_ch["abrir"]
            do["cerrar"] = do_ch["cerrar"]
        if has_lock:
            do["desbloquear"] = do_ch["desbloquear"]
            do["bloquear"]    = do_ch["bloquear"]
        cfg["do"] = do

    if has_sensor:
        cfg["di"]["atrapamiento"] = f"atrapamiento_puerta_{n}"
        cfg["ai"] = {"presion_empaque": f"pres_empaque_{n}"}

    if has_mech_lock_sensor:
        cfg["di"]["bloqueo"] = f"bloqueo_puerta_{n}"

    return cfg


def build_hardware(profile):
    units = Units(resource_path("autoclave/config/calibration.yaml"))
    serial = SerialLink(on_update=lambda data: units.update_from_serial(data))
    serial._scan_ports()
    serial.start()

    doors_cfg = [_build_door_cfg(n + 1, profile.door_type) for n in range(profile.door_count)]
    return units, serial, doors_cfg
```

- [ ] **Step 3.4 — Actualizar cmd_abrir() en advanced_door.py**

En `src/autoclave/devices/puertas/advanced_door.py`, reemplazar el método `cmd_abrir()`:

```python
    def cmd_abrir(self):
        if "bloqueo" in self.di:
            if self.estado.sensores_di.get(self.di["bloqueo"]):
                logger.warning("Puerta %s: bloqueada mecánicamente, apertura denegada", self.name)
                return
        self.set_state(DoorState.ABRIENDO)
```

- [ ] **Step 3.5 — Verificar que los tests pasan**

```
pytest tests/test_advanced_door.py -v
```

Esperado: todos pasan.

- [ ] **Step 3.6 — Verificar que la suite no regresiona**

```
pytest tests/ -v --ignore=tests/Interfaz.py --ignore=tests/ventana_emergente.py
```

Esperado: todos pasan (excepto el fallo pre-existente de checkpoints de CalentamientoFase).

- [ ] **Step 3.7 — Commit**

```
git add src/autoclave/devices/factory/factory.py src/autoclave/devices/puertas/advanced_door.py tests/test_advanced_door.py
git commit -m "feat: puertas MOTORIZED/MOTORIZED_LOCKING bloquean apertura si sensor activo"
```

---

## Task 4: AdvancedDoor — desbloqueo sostenido hasta vacío de empaque

**Files:**
- Modify: `src/autoclave/devices/puertas/advanced_door.py` (solo `_from_abriendo()`)
- Modify: `tests/test_advanced_door.py`

- [ ] **Step 4.1 — Agregar tests que fallan a test_advanced_door.py**

Agregar al final de `tests/test_advanced_door.py`:

```python
import time as _time


def _make_abriendo_door(presion_empaque_val: float):
    estado = MagicMock()
    estado.get_flag.return_value = False          # sin safe_mode
    estado.sensores_pres.get.return_value = presion_empaque_val
    estado.sensores_di.get.return_value = 0       # puerta no abierta ni cerrada

    set_do = MagicMock()
    door = AdvancedDoor(
        name="Puerta 1",
        di={"abierta": "puerta_1_abierta", "cerrada": "puerta_1_cerrada"},
        do={"abrir": 19, "cerrar": 21, "desbloquear": 8},
        ai={"presion_empaque": "pres_empaque_1"},
        estado=estado,
        setdo=set_do,
        config=_CONFIG,
        alarm_manager=None,
    )
    door.timer_start = _time.time() + 60   # saltar el bloque de inicialización
    return door, set_do


def test_desbloquear_se_mantiene_con_presion_alta():
    """Con presión de empaque sobre vacio_empaque, desbloquear debe permanecer activo."""
    door, set_do = _make_abriendo_door(presion_empaque_val=200.0)   # > 30 kPa
    door._from_abriendo()
    # desbloquear_on → set_output(8, True) debe llamarse
    set_do.set_output.assert_any_call(8, True)
    # desbloquear_off → set_output(8, False) NO debe llamarse
    assert (8, False) not in [tuple(c.args) for c in set_do.set_output.call_args_list]


def test_desbloquear_se_apaga_con_presion_baja():
    """Con presión de empaque bajo vacio_empaque, desbloquear debe apagarse."""
    door, set_do = _make_abriendo_door(presion_empaque_val=15.0)    # < 30 kPa
    door._from_abriendo()
    # desbloquear_off → set_output(8, False) debe llamarse
    set_do.set_output.assert_any_call(8, False)
```

- [ ] **Step 4.2 — Verificar que fallan**

```
pytest tests/test_advanced_door.py::test_desbloquear_se_mantiene_con_presion_alta tests/test_advanced_door.py::test_desbloquear_se_apaga_con_presion_baja -v
```

Esperado: `FAILED` — con la lógica actual, `desbloquear_off` se llama en el segundo ciclo independiente de la presión.

- [ ] **Step 4.3 — Reemplazar `_from_abriendo()` en advanced_door.py**

Reemplazar el método completo `_from_abriendo()` en `src/autoclave/devices/puertas/advanced_door.py`:

```python
    def _from_abriendo(self):
        safe_mode = self.estado.get_flag("FALLO_SUMINISTRO_ELECTRICO")

        if self.timer_start is None:
            self.timer_start = time.time() + self.config.get("timeout_puerta")
            self.bloquear_off()
            self.cerrar_off()
            if safe_mode:
                self._alarm_report(Alarm(
                    alarm_id=f"ABRIENDO_MODO_SEGURO_{self.name}",
                    alarm_type=AlarmType.ALERTA,
                    source_state="PUERTA",
                    description=f"Puerta {self.name}: abriendo en modo seguro (sin bomba de vacío).",
                    recoverable=True,
                    blocks_operation=False,
                ))
            else:
                self.vacio_on()
            self.desbloquear_on()
            logger.info("Iniciando apertura de puerta%s.", " (modo seguro)" if safe_mode else "")
            return

        # Mantener desbloquear activo hasta que el empaque alcance vacío
        if self.presion_empaque() > self.config.get("vacio_empaque"):
            self.desbloquear_on()
        else:
            self.desbloquear_off()

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
            self._alarm_clear(f"ABRIENDO_MODO_SEGURO_{self.name}")
            self.timer_start = None
            self._pulso_desbloqueo_enviado = False
            self.set_state(DoorState.ABIERTO)
            logger.info("Puerta abierta correctamente.")
            return

        if time.time() > self.timer_start:
            self.abrir_off()
            self.vacio_off()
            self._alarm_clear(f"ABRIENDO_MODO_SEGURO_{self.name}")
            self.timer_start = None
            self._pulso_desbloqueo_enviado = False
            self.set_state(DoorState.ERROR)
            logger.error("Error: Tiempo de apertura agotado.")
```

Nota: `_pulso_desbloqueo_enviado` se conserva en el `__init__` y se sigue reseteando al completar la apertura, porque `_from_cerrando()` lo usa.

- [ ] **Step 4.4 — Verificar que los tests pasan**

```
pytest tests/test_advanced_door.py -v
```

Esperado: todos pasan.

- [ ] **Step 4.5 — Verificar suite completa sin regresiones**

```
pytest tests/ -v --ignore=tests/Interfaz.py --ignore=tests/ventana_emergente.py
```

Esperado: todos pasan (excepto fallo pre-existente de checkpoints).

- [ ] **Step 4.6 — Commit**

```
git add src/autoclave/devices/puertas/advanced_door.py tests/test_advanced_door.py
git commit -m "feat: AdvancedDoor mantiene desbloquear activo hasta vacio de empaque"
```

---

## Task 5: Generador — módulo de base de datos

**Files:**
- Create: `tools/generador/db.py`
- Create: `tests/test_generador_db.py`

- [ ] **Step 5.1 — Escribir tests que fallan**

Crear `tests/test_generador_db.py`:

```python
import sys
import os
import pytest
from datetime import date

# Agregar tools/generador al path para importar db directamente
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "generador"))
import db as generador_db


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(generador_db, "DB_PATH", tmp_path / "test.db")
    generador_db.init_db()


def test_fue_instalado_falso_sin_registros():
    assert not generador_db.fue_instalado("SN001")


def test_fue_instalado_verdadero_con_instalacion():
    generador_db.log_codigo("SN001", "instalacion", "admin")
    assert generador_db.fue_instalado("SN001")


def test_fue_instalado_verdadero_con_reinstalacion():
    generador_db.log_codigo("SN001", "reinstalacion", "admin")
    assert generador_db.fue_instalado("SN001")


def test_fue_instalado_falso_con_solo_fabrica():
    generador_db.log_codigo("SN001", "fabrica", "admin")
    assert not generador_db.fue_instalado("SN001")


def test_get_history_vacio():
    assert generador_db.get_history("SN001") == []


def test_get_history_contiene_registros_correctos():
    generador_db.log_codigo("SN001", "instalacion", "user1", date(2026, 1, 1))
    generador_db.log_codigo("SN001", "fabrica",     "user2", date(2026, 2, 1))
    hist = generador_db.get_history("SN001")
    assert len(hist) == 2
    assert hist[0]["tipo"] == "fabrica"       # más reciente primero
    assert hist[0]["usuario"] == "user2"
    assert hist[1]["tipo"] == "instalacion"


def test_get_history_solo_para_el_serial_dado():
    generador_db.log_codigo("SN001", "instalacion", "user1")
    generador_db.log_codigo("SN002", "instalacion", "user2")
    hist = generador_db.get_history("SN001")
    assert len(hist) == 1
    assert hist[0]["usuario"] == "user1"


def test_log_codigo_usa_fecha_hoy_por_defecto():
    generador_db.log_codigo("SN001", "fabrica", "admin")
    hist = generador_db.get_history("SN001")
    assert hist[0]["fecha"] == date.today().isoformat()
```

- [ ] **Step 5.2 — Verificar que fallan**

```
pytest tests/test_generador_db.py -v
```

Esperado: `FAILED` — `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 5.3 — Crear tools/generador/db.py**

```python
# tools/generador/db.py
import sqlite3
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).parent / "generador.db"


def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS codigos_generados (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                serial  TEXT NOT NULL,
                tipo    TEXT NOT NULL,
                fecha   TEXT NOT NULL,
                usuario TEXT NOT NULL
            )
        """)
        con.commit()


def fue_instalado(serial: str) -> bool:
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute(
            "SELECT 1 FROM codigos_generados "
            "WHERE serial = ? AND tipo IN ('instalacion', 'reinstalacion') LIMIT 1",
            (serial,)
        ).fetchone()
    return row is not None


def log_codigo(serial: str, tipo: str, usuario: str, day: date | None = None):
    fecha = (day or date.today()).isoformat()
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO codigos_generados (serial, tipo, fecha, usuario) VALUES (?, ?, ?, ?)",
            (serial, tipo, fecha, usuario)
        )
        con.commit()


def get_history(serial: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT tipo, fecha, usuario FROM codigos_generados "
            "WHERE serial = ? ORDER BY fecha DESC, id DESC",
            (serial,)
        ).fetchall()
    return [{"tipo": r[0], "fecha": r[1], "usuario": r[2]} for r in rows]
```

- [ ] **Step 5.4 — Verificar que los tests pasan**

```
pytest tests/test_generador_db.py -v
```

Esperado: todos pasan.

- [ ] **Step 5.5 — Commit**

```
git add tools/generador/db.py tests/test_generador_db.py
git commit -m "feat: generador — módulo db.py con historial de códigos generados"
```

---

## Task 6: Generador — lógica de generación con historial y reinstalación

**Files:**
- Modify: `tools/generador/app.py`

Esta tarea no tiene tests unitarios automatizados — la lógica de rutas FastAPI se verifica manualmente. Sí tiene tests de smoke a mano documentados abajo.

- [ ] **Step 6.1 — Reemplazar app.py completo**

El archivo `tools/generador/app.py` queda así. Los cambios clave respecto al original:
1. `_sessions` cambia de `set` a `dict` (token → usuario) para poder recuperar el username.
2. Se importa `db` y se llama `db.init_db()` al iniciar.
3. `generar_post` consulta `db.fue_instalado()` para decidir qué mostrar.
4. Nueva ruta `POST /reinstalar`.
5. `_dashboard()` acepta `history` y `ya_instalado` para mostrar historial y botón de reinstalación.

```python
# tools/generador/app.py
"""
Generador interno de códigos de instalación y claves de fábrica.

Correr:
    python tools/generador/app.py

Acceso local:    http://localhost:8080
Desde otra PC:   http://<ip-de-tu-maquina>:8080

Variables de entorno (opcionales):
    GENERADOR_USER  — usuario (default: especifika)
    GENERADOR_PASS  — contraseña (default: cambiar_esto_2026)
    GENERADOR_HOST  — host de escucha (default: 0.0.0.0)
    GENERADOR_PORT  — puerto (default: 8080)
"""
import html
import os
import sys
import secrets
from datetime import date

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from autoclave.installation.activation import generate_installation_code, generate_factory_key
import db as generador_db

# ── Configuración ────────────────────────────────────────────────────────────
_USER = os.environ.get("GENERADOR_USER", "especifika")
_PASS = os.environ.get("GENERADOR_PASS", "cambiar_esto_2026")
_HOST = os.environ.get("GENERADOR_HOST", "0.0.0.0")
_PORT = int(os.environ.get("GENERADOR_PORT", "8080"))

app = FastAPI(docs_url=None, redoc_url=None)
_sessions: dict[str, str] = {}   # token → username

_CSS = """
body{font-family:sans-serif;max-width:560px;margin:60px auto;padding:0 20px;background:#f5f5f5}
.card{background:#fff;border-radius:8px;padding:32px;box-shadow:0 2px 8px rgba(0,0,0,.1)}
h1{margin-top:0;font-size:1.3rem;color:#2c3e50}
label{display:block;margin:14px 0 4px;font-size:.9rem;color:#555}
input[type=text],input[type=password]{width:100%;box-sizing:border-box;padding:10px;
  border:1px solid #ccc;border-radius:4px;font-size:1rem}
button{width:100%;margin-top:18px;padding:12px;background:#27ae60;color:#fff;
  border:none;border-radius:4px;font-size:1rem;cursor:pointer}
button:hover{background:#219653}
button.warning{background:#e67e22}
button.warning:hover{background:#ca6f1e}
.error{color:#e74c3c;font-size:.9rem;margin-top:10px}
.result{margin-top:22px;padding:18px;background:#eaf6f0;border-radius:6px}
.chip-label{font-size:.75rem;color:#888;text-transform:uppercase;letter-spacing:.06em;margin:10px 0 2px}
.code{font-family:monospace;font-size:1.25rem;letter-spacing:.12em;color:#2c3e50;font-weight:bold}
.date-note{font-size:.8rem;color:#888;margin-top:8px}
.logout{margin-top:20px;text-align:right}
.logout a{color:#aaa;font-size:.82rem;text-decoration:none}
.logout a:hover{color:#888}
table{width:100%;border-collapse:collapse;font-size:.82rem;margin-top:6px}
th{text-align:left;color:#888;font-weight:normal;padding:2px 6px}
td{padding:3px 6px;border-top:1px solid #eee}
"""


def _is_authenticated(request: Request) -> bool:
    return request.cookies.get("session", "") in _sessions


def _get_usuario(request: Request) -> str:
    return _sessions.get(request.cookies.get("session", ""), "desconocido")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse("/generar" if _is_authenticated(request) else "/login")


@app.get("/login", response_class=HTMLResponse)
async def login_get(error: str = ""):
    err = f'<p class="error">{html.escape(error)}</p>' if error else ""
    return HTMLResponse(f"""<!DOCTYPE html><html><head><title>Generador — Login</title>
<style>{_CSS}</style></head><body><div class="card">
<h1>Generador de Códigos</h1>
<form method="POST" action="/login">
  <label>Usuario</label><input name="username" type="text" autofocus>
  <label>Contraseña</label><input name="password" type="password">
  <button type="submit">Entrar</button>
</form>{err}</div></body></html>""")


@app.post("/login")
async def login_post(username: str = Form(default=""), password: str = Form(default="")):
    if not username or not password:
        return RedirectResponse("/login?error=Ingrese+usuario+y+contraseña", status_code=303)
    if username == _USER and password == _PASS:
        token = secrets.token_hex(32)
        _sessions[token] = username
        resp = RedirectResponse("/generar", status_code=303)
        resp.set_cookie("session", token, httponly=True, samesite="strict")
        return resp
    return RedirectResponse("/login?error=Usuario+o+contraseña+incorrectos", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    _sessions.pop(request.cookies.get("session", ""), None)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session")
    return resp


@app.get("/generar", response_class=HTMLResponse)
async def generar_get(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse("/login")
    return HTMLResponse(_dashboard("", "", "", ya_instalado=False))


@app.post("/generar", response_class=HTMLResponse)
async def generar_post(request: Request, serial: str = Form(...)):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    serial = serial.strip().upper()
    usuario = _get_usuario(request)

    if not serial:
        return HTMLResponse(_dashboard("", "", "", error="El serial no puede estar vacío", ya_instalado=False))

    ya_instalado = generador_db.fue_instalado(serial)
    factory_key  = generate_factory_key(serial)
    history      = generador_db.get_history(serial)

    if ya_instalado:
        generador_db.log_codigo(serial, "fabrica", usuario)
        return HTMLResponse(_dashboard(serial, "", factory_key,
                                       ya_instalado=True, history=history))
    else:
        install_code = generate_installation_code(serial)
        generador_db.log_codigo(serial, "instalacion", usuario)
        return HTMLResponse(_dashboard(serial, install_code, factory_key,
                                       ya_instalado=False, history=history))


@app.post("/reinstalar", response_class=HTMLResponse)
async def reinstalar_post(request: Request, serial: str = Form(...)):
    if not _is_authenticated(request):
        return RedirectResponse("/login")

    serial  = serial.strip().upper()
    usuario = _get_usuario(request)

    install_code = generate_installation_code(serial)
    generador_db.log_codigo(serial, "reinstalacion", usuario)
    history = generador_db.get_history(serial)

    return HTMLResponse(_dashboard(serial, install_code, "", ya_instalado=True,
                                   history=history, reinstalacion=True))


def _render_history(history: list[dict]) -> str:
    if not history:
        return ""
    rows = "".join(
        f"<tr><td>{html.escape(h['tipo'])}</td>"
        f"<td>{html.escape(h['fecha'])}</td>"
        f"<td>{html.escape(h['usuario'])}</td></tr>"
        for h in history
    )
    return (
        '<div class="result"><div class="chip-label">Historial</div>'
        "<table><tr><th>Tipo</th><th>Fecha</th><th>Usuario</th></tr>"
        f"{rows}</table></div>"
    )


def _dashboard(
    serial: str,
    install_code: str,
    factory_key: str,
    error: str = "",
    history: list[dict] | None = None,
    ya_instalado: bool = False,
    reinstalacion: bool = False,
) -> str:
    today        = date.today().isoformat()
    safe_serial  = html.escape(serial)
    safe_error   = html.escape(error)
    result       = ""
    reinstall_form = ""

    if install_code or factory_key:
        codes_html = ""
        if reinstalacion:
            codes_html += (
                '<div class="chip-label">Código de reinstalación</div>'
                f'<div class="code">{install_code}</div>'
            )
        elif not ya_instalado and install_code:
            codes_html += (
                '<div class="chip-label">Código de instalación</div>'
                f'<div class="code">{install_code}</div>'
            )
        if factory_key:
            codes_html += (
                '<div class="chip-label">Clave de fábrica</div>'
                f'<div class="code">{factory_key}</div>'
            )
        result = (
            f'<div class="result">'
            f'<div class="chip-label">Serial</div><div class="code">{safe_serial}</div>'
            f"{codes_html}"
            f'<div class="date-note">Válidos solo el día de hoy: {today}</div>'
            f"</div>"
        )

    if ya_instalado and not reinstalacion:
        reinstall_form = (
            f'<form method="POST" action="/reinstalar" style="margin-top:8px">'
            f'<input type="hidden" name="serial" value="{safe_serial}">'
            f'<button class="warning" type="submit">Solicitar reinstalación</button>'
            f"</form>"
        )

    err        = f'<p class="error">{safe_error}</p>' if error else ""
    hist_html  = _render_history(history or [])

    return (
        f'<!DOCTYPE html><html><head><title>Generador</title>'
        f"<style>{_CSS}</style></head><body><div class=\"card\">"
        f"<h1>Generador de Códigos</h1>"
        f'<form method="POST" action="/generar">'
        f"  <label>Número de serie del equipo</label>"
        f'  <input name="serial" type="text" value="{safe_serial}" placeholder="SN123456" autofocus>'
        f'  <button type="submit">Generar</button>'
        f"</form>{err}{result}{reinstall_form}{hist_html}"
        f'<div class="logout"><a href="/logout">Cerrar sesión</a></div>'
        f"</div></body></html>"
    )


if __name__ == "__main__":
    generador_db.init_db()
    print(f"\nGenerador corriendo en http://localhost:{_PORT}")
    print(f"Desde otra máquina: http://<ip-de-esta-PC>:{_PORT}\n")
    uvicorn.run(app, host=_HOST, port=_PORT, log_level="warning")
```

- [ ] **Step 6.2 — Verificar arranque**

```
python tools/generador/app.py
```

Esperado: el servidor arranca sin errores y crea `tools/generador/generador.db`.

- [ ] **Step 6.3 — Prueba manual: primera instalación**

1. Abrir `http://localhost:8080`, hacer login.
2. Ingresar serial `TEST001` → debe mostrar **código de instalación + clave de fábrica**.
3. Revisar historial: debe aparecer `instalacion` con fecha de hoy.

- [ ] **Step 6.4 — Prueba manual: segunda consulta**

1. Volver a ingresar `TEST001` → debe mostrar **solo clave de fábrica** + botón "Solicitar reinstalación".
2. Revisar historial: debe aparecer `fabrica` encima de `instalacion`.

- [ ] **Step 6.5 — Prueba manual: reinstalación**

1. Click en "Solicitar reinstalación" → debe mostrar **código de reinstalación**.
2. Historial debe mostrar `reinstalacion`, `fabrica`, `instalacion` en orden descendente.

- [ ] **Step 6.6 — Commit**

```
git add tools/generador/app.py
git commit -m "feat: generador con historial de códigos y lógica de reinstalación"
```

---

## Self-review

**Cobertura de spec:**
- ✅ Item 1 (desbloqueo sostenido): Task 4
- ✅ Item 2 (cooling_mode_max): Task 1
- ✅ Item 3 (bloqueo apertura motorizada): Task 3
- ✅ Item 4 (historial + reinstalación): Tasks 5 + 6
- ✅ Item 5 (delete perfil): Task 2

**Tipos y firmas consistentes:**
- `generador_db.fue_instalado(serial: str) → bool` usada en Task 6 ✅
- `generador_db.log_codigo(serial, tipo, usuario, day?)` usada correctamente ✅
- `generador_db.get_history(serial) → list[dict]` con keys `tipo`, `fecha`, `usuario` ✅
- `storage.delete()` sin parámetros, importada como `delete_profile` en wizard ✅
- `_build_door_cfg` accesible desde tests via import directo ✅

**Sin placeholders:** todas las funciones, tests y comandos están completos.

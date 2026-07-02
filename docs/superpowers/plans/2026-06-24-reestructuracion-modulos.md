# Reestructuración de módulos en subcarpetas — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mover archivos sueltos de 4 módulos a subcarpetas semánticas y actualizar todos los imports afectados sin cambiar ningún comportamiento.

**Architecture:** Cada módulo recibe subcarpetas por grupo funcional. Todos los imports en `src/` y `tests/` se actualizan a las nuevas rutas. Se usan `git mv` para preservar historial.

**Tech Stack:** Python 3.11+, pytest, setuptools

## Global Constraints

- No modificar lógica ni comportamiento — solo mover archivos y actualizar imports
- Usar `git mv` para mover archivos (preserva historial git)
- Cada subcarpeta nueva necesita un `__init__.py` vacío
- Comando para correr tests: `pytest tests/ -v` (desde la raíz del proyecto)
- Los `__pycache__` no se mueven; se regeneran solos

---

### Task 1: Reestructurar `hal/` → `hal/measures/`

**Files:**
- Move: `src/autoclave/hal/converters.py` → `src/autoclave/hal/measures/converters.py`
- Move: `src/autoclave/hal/units.py` → `src/autoclave/hal/measures/units.py`
- Create: `src/autoclave/hal/measures/__init__.py`
- Modify: `src/autoclave/hal/measures/units.py` (import interno)
- Modify: `src/autoclave/devices/factory/factory.py`
- Modify: `tests/test_converters_realistic.py`
- Modify: `tests/test_flujo_unidades.py`

**Interfaces:**
- Produce: `autoclave.hal.measures.units.Units`, `autoclave.hal.measures.converters`

- [ ] **Paso 1: Crear directorio y mover archivos**

```bash
mkdir src/autoclave/hal/measures
git mv src/autoclave/hal/converters.py src/autoclave/hal/measures/converters.py
git mv src/autoclave/hal/units.py src/autoclave/hal/measures/units.py
```

- [ ] **Paso 2: Crear `__init__.py`**

Crear `src/autoclave/hal/measures/__init__.py` con contenido vacío (solo el archivo, sin contenido).

- [ ] **Paso 3: Corregir import interno en `units.py`**

En `src/autoclave/hal/measures/units.py`, línea que dice:
```python
from autoclave.hal import converters
```
Cambiar a:
```python
from autoclave.hal.measures import converters
```

- [ ] **Paso 4: Corregir import en `factory.py`**

En `src/autoclave/devices/factory/factory.py`, línea 1:
```python
# Antes
from autoclave.hal.units import Units
# Después
from autoclave.hal.measures.units import Units
```

- [ ] **Paso 5: Corregir import en `test_converters_realistic.py`**

En `tests/test_converters_realistic.py`, línea 1:
```python
# Antes
from autoclave.hal import converters
# Después
from autoclave.hal.measures import converters
```

- [ ] **Paso 6: Corregir import en `test_flujo_unidades.py`**

En `tests/test_flujo_unidades.py`, línea 4:
```python
# Antes
from autoclave.hal.units import Units
# Después
from autoclave.hal.measures.units import Units
```

- [ ] **Paso 7: Verificar con tests**

```bash
pytest tests/test_flujo_unidades.py tests/test_converters_realistic.py -v
```
Esperado: todos PASS (nota: `test_flujo_unidades.py` está en `--ignore` de pytest.ini, ejecutarlo explícitamente lo fuerza a correr)

- [ ] **Paso 8: Commit**

```bash
git add src/autoclave/hal/measures/ src/autoclave/devices/factory/factory.py tests/test_converters_realistic.py tests/test_flujo_unidades.py
git commit -m "refactor: mover hal/converters y hal/units a hal/measures/"
```

---

### Task 2: Reestructurar `core/` → `core/managers/` + `core/runtime/`

**Files:**
- Move: `src/autoclave/core/cycle_manager.py` → `src/autoclave/core/managers/cycle_manager.py`
- Move: `src/autoclave/core/config_manager.py` → `src/autoclave/core/managers/config_manager.py`
- Move: `src/autoclave/core/status.py` → `src/autoclave/core/runtime/status.py`
- Move: `src/autoclave/core/steam.py` → `src/autoclave/core/runtime/steam.py`
- Create: `src/autoclave/core/managers/__init__.py`
- Create: `src/autoclave/core/runtime/__init__.py`
- Modify: `src/autoclave/backend/context.py`
- Modify: `src/autoclave/backend/server.py`
- Modify: `src/autoclave/state_machine/cycle_phases/base_fase.py`
- Modify: `src/autoclave/state_machine/cycle_phases/calentamiento.py`
- Modify: `src/autoclave/state_machine/cycle_phases/esterilizacion.py`
- Modify: `src/autoclave/ui_pyside/views/entrdas_salidas/io_di.py`
- Modify: `src/autoclave/ui_pyside/views/entrdas_salidas/io_do.py`
- Modify: `src/autoclave/ui_pyside/views/entrdas_salidas/io_pres.py`
- Modify: `src/autoclave/ui_pyside/views/entrdas_salidas/io_temp.py`
- Modify: `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py`
- Modify: `tests/test_calentamiento_fase.py`
- Modify: `tests/test_estabilizacion_fase.py`
- Modify: `tests/test_esterilizacion_caps.py`
- Modify: `tests/test_esterilizacion_fase.py`
- Modify: `tests/test_steam.py`
- Modify: `tests/test_patch_cycle_parameters.py`

**Interfaces:**
- Consume: (ninguna tarea anterior)
- Produce: `autoclave.core.managers.cycle_manager.CycleManager`, `autoclave.core.managers.config_manager.ConfigManager`, `autoclave.core.runtime.status.EstadoAutoclave`, `autoclave.core.runtime.steam.p_saturacion_kpa`

- [ ] **Paso 1: Crear directorios y mover archivos**

```bash
mkdir src/autoclave/core/managers
mkdir src/autoclave/core/runtime
git mv src/autoclave/core/cycle_manager.py src/autoclave/core/managers/cycle_manager.py
git mv src/autoclave/core/config_manager.py src/autoclave/core/managers/config_manager.py
git mv src/autoclave/core/status.py src/autoclave/core/runtime/status.py
git mv src/autoclave/core/steam.py src/autoclave/core/runtime/steam.py
```

- [ ] **Paso 2: Crear `__init__.py`**

Crear `src/autoclave/core/managers/__init__.py` vacío.  
Crear `src/autoclave/core/runtime/__init__.py` vacío.

- [ ] **Paso 3: Corregir imports en `backend/context.py`**

En `src/autoclave/backend/context.py`, las líneas 3, 13, 14:
```python
# Antes
from autoclave.core.status import EstadoAutoclave
from autoclave.core.cycle_manager import CycleManager
from autoclave.core.config_manager import ConfigManager
# Después
from autoclave.core.runtime.status import EstadoAutoclave
from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.core.managers.config_manager import ConfigManager
```

- [ ] **Paso 4: Corregir import en `backend/server.py`**

En `src/autoclave/backend/server.py`, línea 11:
```python
# Antes
from autoclave.core.status import EstadoAutoclave
# Después
from autoclave.core.runtime.status import EstadoAutoclave
```

- [ ] **Paso 5: Corregir imports en `cycle_phases/`**

En `src/autoclave/state_machine/cycle_phases/base_fase.py`:
```python
# Antes
from autoclave.core.steam import p_saturacion_kpa
# Después
from autoclave.core.runtime.steam import p_saturacion_kpa
```

En `src/autoclave/state_machine/cycle_phases/calentamiento.py`:
```python
# Antes
from autoclave.core.steam import p_saturacion_kpa
# Después
from autoclave.core.runtime.steam import p_saturacion_kpa
```

En `src/autoclave/state_machine/cycle_phases/esterilizacion.py`:
```python
# Antes
from autoclave.core.steam import p_saturacion_kpa
# Después
from autoclave.core.runtime.steam import p_saturacion_kpa
```

- [ ] **Paso 6: Corregir imports en `entrdas_salidas/`**

En cada uno de estos 4 archivos, cambiar la misma línea:
```python
# Antes
from autoclave.core.status import EstadoAutoclave
# Después
from autoclave.core.runtime.status import EstadoAutoclave
```
- `src/autoclave/ui_pyside/views/entrdas_salidas/io_di.py` (línea 4)
- `src/autoclave/ui_pyside/views/entrdas_salidas/io_do.py` (línea 16)
- `src/autoclave/ui_pyside/views/entrdas_salidas/io_pres.py` (línea 4)
- `src/autoclave/ui_pyside/views/entrdas_salidas/io_temp.py` (línea 5)

- [ ] **Paso 7: Corregir import en `params_ciclo.py`**

En `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py`, línea ~405 (import inline dentro de función):
```python
# Antes
from autoclave.core.cycle_manager import CycleManager
# Después
from autoclave.core.managers.cycle_manager import CycleManager
```

- [ ] **Paso 8: Corregir imports en tests**

En `tests/test_steam.py`:
```python
# Antes
from autoclave.core.steam import p_saturacion_kpa
# Después
from autoclave.core.runtime.steam import p_saturacion_kpa
```

En `tests/test_calentamiento_fase.py` (hay 2 apariciones — línea ~1 y línea ~98):
```python
# Antes
from autoclave.core.steam import p_saturacion_kpa
# Después
from autoclave.core.runtime.steam import p_saturacion_kpa
```

En `tests/test_estabilizacion_fase.py` (líneas 3 y 73):
```python
# Antes
from autoclave.core.steam import p_saturacion_kpa
# Después
from autoclave.core.runtime.steam import p_saturacion_kpa
```

En `tests/test_esterilizacion_caps.py` (línea 2):
```python
# Antes
from autoclave.core.steam import p_saturacion_kpa
# Después
from autoclave.core.runtime.steam import p_saturacion_kpa
```

En `tests/test_esterilizacion_fase.py` (línea 3):
```python
# Antes
from autoclave.core.steam import p_saturacion_kpa
# Después
from autoclave.core.runtime.steam import p_saturacion_kpa
```

En `tests/test_patch_cycle_parameters.py` (línea 5):
```python
# Antes
from autoclave.core.cycle_manager import CycleManager
# Después
from autoclave.core.managers.cycle_manager import CycleManager
```

- [ ] **Paso 9: Verificar con tests**

```bash
pytest tests/test_steam.py tests/test_calentamiento_fase.py tests/test_estabilizacion_fase.py tests/test_esterilizacion_caps.py tests/test_esterilizacion_fase.py tests/test_patch_cycle_parameters.py -v
```
Esperado: todos PASS

- [ ] **Paso 10: Commit**

```bash
git add src/autoclave/core/ src/autoclave/backend/context.py src/autoclave/backend/server.py src/autoclave/state_machine/cycle_phases/ src/autoclave/ui_pyside/views/entrdas_salidas/ src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py tests/test_steam.py tests/test_calentamiento_fase.py tests/test_estabilizacion_fase.py tests/test_esterilizacion_caps.py tests/test_esterilizacion_fase.py tests/test_patch_cycle_parameters.py
git commit -m "refactor: mover core/ en subcarpetas managers/ y runtime/"
```

---

### Task 3: Reestructurar `installation/` → 4 subcarpetas

**Files:**
- Move: `src/autoclave/installation/wizard.py` → `src/autoclave/installation/ui/wizard.py`
- Move: `src/autoclave/installation/factory_dialog.py` → `src/autoclave/installation/ui/factory_dialog.py`
- Move: `src/autoclave/installation/activation.py` → `src/autoclave/installation/security/activation.py`
- Move: `src/autoclave/installation/clock_guard.py` → `src/autoclave/installation/security/clock_guard.py`
- Move: `src/autoclave/installation/profile.py` → `src/autoclave/installation/data/profile.py`
- Move: `src/autoclave/installation/storage.py` → `src/autoclave/installation/data/storage.py`
- Move: `src/autoclave/installation/bootstrap.py` → `src/autoclave/installation/setup/bootstrap.py`
- Move: `src/autoclave/installation/equipment.py` → `src/autoclave/installation/setup/equipment.py`
- Create: `src/autoclave/installation/ui/__init__.py`
- Create: `src/autoclave/installation/security/__init__.py`
- Create: `src/autoclave/installation/data/__init__.py`
- Create: `src/autoclave/installation/setup/__init__.py`
- Modify (imports internos): `wizard.py`, `bootstrap.py`, `factory_dialog.py`, `storage.py`, `profile.py`
- Modify (imports externos): `backend/context.py`, `main.py`, `ui/main.py`, `services/domain/puertas/permissions.py`
- Modify (tests): múltiples

**Interfaces:**
- Consume: (ninguna tarea anterior)
- Produce: `autoclave.installation.setup.bootstrap.get_installation_profile`, `autoclave.installation.setup.equipment.EquipmentClass`, `autoclave.installation.setup.equipment.get_capabilities`, `autoclave.installation.data.profile.InstallationProfile`, `autoclave.installation.data.profile.Role`, `autoclave.installation.data.storage`, `autoclave.installation.security.activation.validate_installation_code`, `autoclave.installation.security.clock_guard.ClockTamperedError`, `autoclave.installation.ui.wizard.launch_installation_wizard`

- [ ] **Paso 1: Crear directorios y mover archivos**

```bash
mkdir src/autoclave/installation/ui
mkdir src/autoclave/installation/security
mkdir src/autoclave/installation/data
mkdir src/autoclave/installation/setup
git mv src/autoclave/installation/wizard.py src/autoclave/installation/ui/wizard.py
git mv src/autoclave/installation/factory_dialog.py src/autoclave/installation/ui/factory_dialog.py
git mv src/autoclave/installation/activation.py src/autoclave/installation/security/activation.py
git mv src/autoclave/installation/clock_guard.py src/autoclave/installation/security/clock_guard.py
git mv src/autoclave/installation/profile.py src/autoclave/installation/data/profile.py
git mv src/autoclave/installation/storage.py src/autoclave/installation/data/storage.py
git mv src/autoclave/installation/bootstrap.py src/autoclave/installation/setup/bootstrap.py
git mv src/autoclave/installation/equipment.py src/autoclave/installation/setup/equipment.py
```

- [ ] **Paso 2: Crear `__init__.py` en las 4 subcarpetas**

Crear vacíos:
- `src/autoclave/installation/ui/__init__.py`
- `src/autoclave/installation/security/__init__.py`
- `src/autoclave/installation/data/__init__.py`
- `src/autoclave/installation/setup/__init__.py`

- [ ] **Paso 3: Corregir imports internos en `data/profile.py`**

En `src/autoclave/installation/data/profile.py`:
```python
# Antes (línea 4)
from autoclave.installation.equipment import EquipmentClass
# Después
from autoclave.installation.setup.equipment import EquipmentClass
```
Y si hay import condicional (línea ~54):
```python
# Antes
from autoclave.installation.equipment import get_capabilities
# Después
from autoclave.installation.setup.equipment import get_capabilities
```

- [ ] **Paso 4: Corregir imports internos en `data/storage.py`**

En `src/autoclave/installation/data/storage.py`:
```python
# Antes (línea 5)
from autoclave.installation.equipment import EquipmentClass
# Después
from autoclave.installation.setup.equipment import EquipmentClass
```
La línea `from .profile import ...` queda igual (ambos siguen en `data/`). ✓

- [ ] **Paso 5: Corregir imports internos en `setup/bootstrap.py`**

En `src/autoclave/installation/setup/bootstrap.py`:
```python
# Antes
from .storage import exists, load
from .profile import ProfileValidationError
from .clock_guard import check_system_clock, ClockTamperedError
# Después
from autoclave.installation.data.storage import exists, load
from autoclave.installation.data.profile import ProfileValidationError
from autoclave.installation.security.clock_guard import check_system_clock, ClockTamperedError
```

- [ ] **Paso 6: Corregir imports internos en `ui/wizard.py`**

En `src/autoclave/installation/ui/wizard.py`:
```python
# Antes
from .profile import InstallationProfile, Role
from .equipment import EquipmentClass, get_capabilities
from .storage import save, delete as delete_profile
from .activation import validate_installation_code
# Después
from autoclave.installation.data.profile import InstallationProfile, Role
from autoclave.installation.setup.equipment import EquipmentClass, get_capabilities
from autoclave.installation.data.storage import save, delete as delete_profile
from autoclave.installation.security.activation import validate_installation_code
```

- [ ] **Paso 7: Corregir import interno en `ui/factory_dialog.py`**

En `src/autoclave/installation/ui/factory_dialog.py`:
```python
# Antes
from .activation import validate_factory_key
# Después
from autoclave.installation.security.activation import validate_factory_key
```

- [ ] **Paso 8: Corregir imports en `backend/context.py`**

En `src/autoclave/backend/context.py`, líneas 5–6 (las de installation, las de core ya se actualizaron en Task 2):
```python
# Antes
from autoclave.installation.bootstrap import get_installation_profile
from autoclave.installation.equipment import get_capabilities
# Después
from autoclave.installation.setup.bootstrap import get_installation_profile
from autoclave.installation.setup.equipment import get_capabilities
```

- [ ] **Paso 9: Corregir imports en `main.py`**

En `src/autoclave/main.py`, líneas 11–13:
```python
# Antes
from autoclave.installation.bootstrap import get_installation_profile
from autoclave.installation.wizard import launch_installation_wizard
from autoclave.installation.clock_guard import ClockTamperedError
# Después
from autoclave.installation.setup.bootstrap import get_installation_profile
from autoclave.installation.ui.wizard import launch_installation_wizard
from autoclave.installation.security.clock_guard import ClockTamperedError
```

- [ ] **Paso 10: Corregir imports en `ui/main.py`**

En `src/autoclave/ui/main.py`, líneas 8–10:
```python
# Antes
from autoclave.installation.bootstrap import get_installation_profile
from autoclave.installation.wizard import launch_installation_wizard
from autoclave.installation.clock_guard import ClockTamperedError
# Después
from autoclave.installation.setup.bootstrap import get_installation_profile
from autoclave.installation.ui.wizard import launch_installation_wizard
from autoclave.installation.security.clock_guard import ClockTamperedError
```

- [ ] **Paso 11: Corregir import en `permissions.py`**

En `src/autoclave/services/domain/puertas/permissions.py`, línea 3:
```python
# Antes
from autoclave.installation.profile import Role
# Después
from autoclave.installation.data.profile import Role
```

- [ ] **Paso 12: Corregir imports en tests**

En `tests/test_activation.py`:
```python
# Antes
from autoclave.installation.activation import (
# Después
from autoclave.installation.security.activation import (
```

En `tests/test_clock_guard.py`:
```python
# Antes
from autoclave.installation.clock_guard import check_system_clock, ClockTamperedError
# Después
from autoclave.installation.security.clock_guard import check_system_clock, ClockTamperedError
```

En `tests/test_door_from_profile.py`:
```python
# Antes
from autoclave.installation.profile import InstallationProfile, Role
from autoclave.installation.equipment import EquipmentClass
# Después
from autoclave.installation.data.profile import InstallationProfile, Role
from autoclave.installation.setup.equipment import EquipmentClass
```

En `tests/test_equipment.py`:
```python
# Antes
from autoclave.installation.equipment import EquipmentClass, EquipmentCapabilities, get_capabilities
# Después
from autoclave.installation.setup.equipment import EquipmentClass, EquipmentCapabilities, get_capabilities
```

En `tests/test_profile_validation.py`:
```python
# Antes
from autoclave.installation.profile import validate_profile_data, ProfileValidationError
# Después
from autoclave.installation.data.profile import validate_profile_data, ProfileValidationError
```

En `tests/test_storage.py` (hay 4 imports que cambiar: líneas 3, 4, y los inline en ~31–33 y ~56–58):
```python
# Antes (líneas 3–4)
from autoclave.installation import storage
from autoclave.installation.storage import delete
# Después
from autoclave.installation.data import storage
from autoclave.installation.data.storage import delete

# Antes (inline ~línea 31)
from autoclave.installation.storage import save
from autoclave.installation.profile import InstallationProfile, Role
from autoclave.installation.equipment import EquipmentClass
# Después
from autoclave.installation.data.storage import save
from autoclave.installation.data.profile import InstallationProfile, Role
from autoclave.installation.setup.equipment import EquipmentClass

# Antes (inline ~línea 56, mismas 3 líneas)
# Después: mismo cambio que arriba
```

- [ ] **Paso 13: Verificar con tests**

```bash
pytest tests/test_activation.py tests/test_clock_guard.py tests/test_door_from_profile.py tests/test_equipment.py tests/test_profile_validation.py tests/test_storage.py -v
```
Esperado: todos PASS

- [ ] **Paso 14: Commit**

```bash
git add src/autoclave/installation/ src/autoclave/backend/context.py src/autoclave/main.py src/autoclave/ui/main.py src/autoclave/services/domain/puertas/permissions.py tests/test_activation.py tests/test_clock_guard.py tests/test_door_from_profile.py tests/test_equipment.py tests/test_profile_validation.py tests/test_storage.py
git commit -m "refactor: mover installation/ en subcarpetas ui/, security/, data/, setup/"
```

---

### Task 4: Reestructurar `ui_pyside/views/` → 5 subcarpetas de vistas

**Files:**
- Move: `src/autoclave/ui_pyside/views/home.py` → `src/autoclave/ui_pyside/views/home/home.py`
- Move: `src/autoclave/ui_pyside/views/login.py` → `src/autoclave/ui_pyside/views/login/login.py`
- Move: `src/autoclave/ui_pyside/views/admin_menu.py` → `src/autoclave/ui_pyside/views/admin/admin_menu.py`
- Move: `src/autoclave/ui_pyside/views/ciclos.py` → `src/autoclave/ui_pyside/views/ciclos/ciclos.py`
- Move: `src/autoclave/ui_pyside/views/secado.py` → `src/autoclave/ui_pyside/views/secado/secado.py`
- Create: `__init__.py` en cada subcarpeta nueva
- Modify: `src/autoclave/ui_pyside/main_window.py`

**Interfaces:**
- Consume: (ninguna tarea anterior)
- Produce: `autoclave.ui_pyside.views.home.home.HomeView`, `autoclave.ui_pyside.views.login.login.LoginView`, `autoclave.ui_pyside.views.admin.admin_menu.AdminMenuView`, `autoclave.ui_pyside.views.ciclos.ciclos.CiclosView`, `autoclave.ui_pyside.views.secado.secado.SecadoView`

- [ ] **Paso 1: Crear directorios y mover archivos**

```bash
mkdir src/autoclave/ui_pyside/views/home
mkdir src/autoclave/ui_pyside/views/login
mkdir src/autoclave/ui_pyside/views/admin
mkdir src/autoclave/ui_pyside/views/ciclos
mkdir src/autoclave/ui_pyside/views/secado
git mv src/autoclave/ui_pyside/views/home.py src/autoclave/ui_pyside/views/home/home.py
git mv src/autoclave/ui_pyside/views/login.py src/autoclave/ui_pyside/views/login/login.py
git mv src/autoclave/ui_pyside/views/admin_menu.py src/autoclave/ui_pyside/views/admin/admin_menu.py
git mv src/autoclave/ui_pyside/views/ciclos.py src/autoclave/ui_pyside/views/ciclos/ciclos.py
git mv src/autoclave/ui_pyside/views/secado.py src/autoclave/ui_pyside/views/secado/secado.py
```

- [ ] **Paso 2: Crear `__init__.py` en las 5 subcarpetas**

Crear vacíos:
- `src/autoclave/ui_pyside/views/home/__init__.py`
- `src/autoclave/ui_pyside/views/login/__init__.py`
- `src/autoclave/ui_pyside/views/admin/__init__.py`
- `src/autoclave/ui_pyside/views/ciclos/__init__.py`
- `src/autoclave/ui_pyside/views/secado/__init__.py`

- [ ] **Paso 3: Corregir imports en `main_window.py`**

En `src/autoclave/ui_pyside/main_window.py`, líneas 40–44:
```python
# Antes
from autoclave.ui_pyside.views.home       import HomeView
from autoclave.ui_pyside.views.secado     import SecadoView
from autoclave.ui_pyside.views.login      import LoginView
from autoclave.ui_pyside.views.ciclos     import CiclosView
from autoclave.ui_pyside.views.admin_menu import AdminMenuView
# Después
from autoclave.ui_pyside.views.home.home         import HomeView
from autoclave.ui_pyside.views.secado.secado     import SecadoView
from autoclave.ui_pyside.views.login.login       import LoginView
from autoclave.ui_pyside.views.ciclos.ciclos     import CiclosView
from autoclave.ui_pyside.views.admin.admin_menu  import AdminMenuView
```

- [ ] **Paso 4: Verificar que no hay tests de UI rotos**

```bash
pytest tests/ -v --ignore=tests/Interfaz.py --ignore=tests/ventana_emergente.py
```
Esperado: todos PASS (los tests de UI no están en la suite estándar)

- [ ] **Paso 5: Commit**

```bash
git add src/autoclave/ui_pyside/views/ src/autoclave/ui_pyside/main_window.py
git commit -m "refactor: mover vistas sueltas de ui_pyside/views/ a subcarpetas individuales"
```

---

## Verificación final

Después de completar las 4 tareas:

- [ ] Correr la suite completa de tests:
```bash
pytest tests/ -v
```
Esperado: mismos tests pasan que antes de la reestructuración.

- [ ] Verificar que no quedan imports con las rutas antiguas:
```bash
grep -rn "from autoclave.hal.units\|from autoclave.hal import converters" src/ tests/ --include="*.py"
grep -rn "from autoclave.core.status\|from autoclave.core.steam\|from autoclave.core.cycle_manager\|from autoclave.core.config_manager" src/ tests/ --include="*.py"
grep -rn "from autoclave.installation.bootstrap\|from autoclave.installation.wizard\|from autoclave.installation.clock_guard\|from autoclave.installation.activation\|from autoclave.installation.equipment\|from autoclave.installation.profile\|from autoclave.installation.storage" src/ tests/ --include="*.py"
grep -rn "from autoclave.ui_pyside.views.home import\|from autoclave.ui_pyside.views.login import\|from autoclave.ui_pyside.views.ciclos import\|from autoclave.ui_pyside.views.secado import\|from autoclave.ui_pyside.views.admin_menu import" src/ tests/ --include="*.py"
```
Esperado: sin resultados en ninguno de los cuatro comandos.

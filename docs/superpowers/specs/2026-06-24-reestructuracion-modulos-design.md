# Diseño: Reestructuración de módulos en subcarpetas

**Fecha:** 2026-06-24  
**Branch:** dev  

## Objetivo

Organizar los archivos sueltos de cuatro módulos en subcarpetas semánticas para facilitar el mantenimiento. Se actualiza también cada import afectado en el resto del código.

## Módulos afectados

### 1. `installation/` — 4 subcarpetas

| Subcarpeta | Archivos |
|---|---|
| `ui/` | `wizard.py`, `factory_dialog.py` |
| `security/` | `activation.py`, `clock_guard.py` |
| `data/` | `profile.py`, `storage.py` |
| `setup/` | `bootstrap.py`, `equipment.py` |

**Ruta final:** `src/autoclave/installation/<subcarpeta>/<archivo>.py`

### 2. `core/` — 2 subcarpetas

| Subcarpeta | Archivos | Razón |
|---|---|---|
| `managers/` | `cycle_manager.py`, `config_manager.py` | Gestionan datos y ciclos |
| `runtime/` | `status.py`, `steam.py` | Estado en tiempo real y física del vapor |

**Ruta final:** `src/autoclave/core/<subcarpeta>/<archivo>.py`

### 3. `hal/` — 1 subcarpeta

| Subcarpeta | Archivos | Razón |
|---|---|---|
| `measures/` | `converters.py`, `units.py` | Inseparables: estado físico + calibración |

**Ruta final:** `src/autoclave/hal/measures/<archivo>.py`

### 4. `ui_pyside/views/` — 5 subcarpetas (una por vista)

| Subcarpeta | Archivo |
|---|---|
| `home/` | `home.py` |
| `login/` | `login.py` |
| `admin/` | `admin_menu.py` |
| `ciclos/` | `ciclos.py` |
| `secado/` | `secado.py` |

Consistente con las subcarpetas existentes `entrdas_salidas/` y `params_ciclo/`.

**Ruta final:** `src/autoclave/ui_pyside/views/<subcarpeta>/<archivo>.py`

## Cambios de imports

Cada archivo movido cambia su ruta de paquete. Todos los módulos del proyecto que importen desde estas rutas deben actualizarse.

Ejemplos de cambio:

```python
# Antes
from autoclave.installation.wizard import InstallWizard
from autoclave.core.cycle_manager import CycleManager
from autoclave.hal.converters import SensorConverter
from autoclave.ui_pyside.views.home import HomeView

# Después
from autoclave.installation.ui.wizard import InstallWizard
from autoclave.core.managers.cycle_manager import CycleManager
from autoclave.hal.measures.converters import SensorConverter
from autoclave.ui_pyside.views.home.home import HomeView
```

## Archivos nuevos necesarios

Cada subcarpeta nueva requiere un `__init__.py` vacío para ser un paquete Python válido.

## Restricciones

- No se modifica lógica ni comportamiento, solo se mueven archivos y se actualizan imports.
- Se usan movimientos de git (`git mv`) para preservar el historial.
- Los `__pycache__` no se mueven; se regeneran automáticamente.

## Módulos NO afectados

- `backend/` — 3 archivos tightly coupled (server, context, main), no vale la pena dividirlos.
- `state_machine/` — ya bien organizado con subcarpetas.
- `services/domain/` — ya bien organizado con subcarpetas.
- `devices/` — cada dispositivo ya tiene su propia carpeta.

# Spec: Vista de Parámetros del Ciclo

**Fecha:** 2026-06-22  
**Rama:** dev  
**Alcance:** UI de parámetros del ciclo (lectura + edición con auditoría), fase Finalización (JSON + pestaña UI), integración en main_window.

---

## 1. Objetivo

Construir la vista "Parámetros del ciclo" accesible desde `AdminMenuView`. Permite al técnico revisar los parámetros de cada fase del ciclo activo y editar los valores del ciclo de usuario con trazabilidad completa (quién cambió qué y cuándo).

---

## 2. Componentes

### 2.1 `ParametrosCicloView`
**Archivo:** `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py`

Vista principal con:
- Header: botón ← (navega a `admin_menu`) + título "PARÁMETROS DEL CICLO" + nombre del ciclo activo
- `QTabWidget` con 10 pestañas (texto compacto, sin íconos):

| Pestaña        | Sección JSON      |
|----------------|-------------------|
| Pre-calentamiento | `precalentamiento` |
| Purga          | `purga`           |
| Crear pulso    | `prevacio`        |
| Calentamiento  | `calentamiento`   |
| Estabilización | `calentamiento`   |

> **Nota:** Calentamiento y Estabilización comparten la sección `calentamiento` del JSON. La pestaña **Calentamiento** muestra: `temperatura_calentamiento`, `tasa_calentamiento`, `timeout_calentamiento`, `rango_presion_calentamiento`. La pestaña **Estabilización** muestra: `tiempo_estable_preesterilizacion`, `rango_temp_estabilizacion`, `timeout_recuperacion_estabilizacion`, `presion_add_calentamiento`.
>
> `presion_add_calentamiento` está referenciado en `estabilizacion.py` pero **no existe aún en los JSONs** (cae al default 9.0). Debe agregarse a todos los archivos de ciclo como parte de esta tarea: `{ "value": 9.0, "type": "float", "unit": "kPa", "min": 0, "max": 50 }`.
| Esterilización | `esterilizacion`  |
| Escape         | `descompresion`   |
| Secado         | `secado`          |
| Finalización   | `finalizacion`    |
| Global         | `globals`         |

Cada pestaña contiene un `QScrollArea` con un `QGridLayout` de tarjetas `_ParamCard` (3 columnas).

### 2.2 `_ParamCard`
Tarjeta de solo lectura (QFrame):
- Nombre del parámetro (formateado: `_` → espacio, capitalizado)
- Valor actual + unidad en negrita
- Cursor de mano; clic abre `_ParamEditDialog`
- Hover con borde azul para indicar que es clicable
- Si el ciclo activo es de fábrica (`source == "factory"`), las tarjetas no son clicables y muestran ícono de candado

### 2.3 `_ParamEditDialog`
Diálogo modal (QDialog) al hacer clic en una tarjeta:

```
┌─────────────────────────────────────┐
│ [nombre del parámetro]              │
├─────────────────────────────────────┤
│ Valor:   [SpinBox / CheckBox]       │
│ Mínimo:  X  unidad                  │
│ Máximo:  X  unidad                  │
│ Por defecto: X  unidad (fábrica)    │
├─────────────────────────────────────┤
│ Última modificación:                │
│   Usuario: nombre                   │
│   Fecha:   YYYY-MM-DD HH:MM         │
│   (Sin modificaciones previas)      │
├─────────────────────────────────────┤
│          [Cancelar]  [Guardar]      │
└─────────────────────────────────────┘
```

Widget de entrada según `type`:
- `int` → `QSpinBox` con `min`/`max` del JSON
- `float` → `QDoubleSpinBox` con `min`/`max` del JSON, 1 decimal
- `bool` → `QCheckBox`

### 2.4 `CycleParamsAuditDB`
**Archivo:** `src/autoclave/services/domain/logging/cycle_params_audit.py`

Gestiona la tabla SQLite de auditoría:

```sql
CREATE TABLE IF NOT EXISTS cycle_params_audit (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id       TEXT    NOT NULL,
    fase           TEXT    NOT NULL,
    param          TEXT    NOT NULL,
    valor_anterior TEXT,
    valor_nuevo    TEXT    NOT NULL,
    usuario        TEXT    NOT NULL,
    timestamp      TEXT    NOT NULL   -- ISO 8601 UTC
);
```

Métodos:
- `log_change(cycle_id, fase, param, valor_anterior, valor_nuevo, usuario)` → inserta fila con timestamp UTC
- `get_last_change(cycle_id, fase, param) -> dict | None` → devuelve `{usuario, timestamp}` o `None`

Usa la misma ruta de BD que `db_manager.py` (`data/autoclave.db`).

---

## 3. Flujo de datos

### Al abrir la vista
1. `CycleManager.get_selected_cycle()` → ciclo de usuario activo
2. Carga ciclo de fábrica desde `cycles/factory/<mismo filename>` → referencia de defaults
3. Para cada parámetro visible: `CycleParamsAuditDB.get_last_change(...)` → usuario + timestamp

### Al hacer clic en una tarjeta
- Abre `_ParamEditDialog` con: valor actual, min, max, default (factory), último editor + fecha (o "Sin modificaciones previas")

### Al guardar
1. Actualiza `parameters[fase][param]["value"]` en el dict en memoria
2. Serializa y sobreescribe `cycles/user/<archivo>.json` — solo el campo `value`, estructura intacta
3. Inserta fila en `cycle_params_audit` con `SessionManager.current_user["nombre"]`
4. Actualiza la `_ParamCard` en pantalla (sin recargar toda la vista)

### Restricciones
- Solo se editan ciclos en `cycles/user/` — ciclos `source == "factory"` son de solo lectura
- El SpinBox respeta `min` y `max` del JSON como límites duros
- Si el usuario activo no tiene sesión iniciada, el botón Guardar está deshabilitado

---

## 4. Fase Finalización (nueva)

### 4.1 Sección JSON
Agregar a **todos** los archivos de ciclo (factory y user) en `parameters`:

```json
"finalizacion": {
    "tiempo_espera_apertura": { "value": 60,   "type": "int",   "unit": "seg", "min": 0, "max": 3600 },
    "temp_max_apertura":      { "value": 80.0, "type": "float", "unit": "°C",  "min": 0, "max": 150  },
    "timeout_temperatura":    { "value": 30,   "type": "int",   "unit": "min", "min": 1, "max": 120  },
    "apertura_automatica":    { "value": false, "type": "bool",  "unit": ""                           }
}
```

**Semántica:**
- `tiempo_espera_apertura`: segundos fijos de espera antes de habilitar apertura de puerta
- `temp_max_apertura`: temperatura máxima de cámara para permitir apertura
- `timeout_temperatura`: tiempo máximo para que la cámara baje a `temp_max_apertura`; si expira → alarma (no fallo crítico)
- `apertura_automatica`: si `true`, abre puerta automáticamente al cumplir condiciones

### 4.2 Alcance de esta tarea
Solo la sección JSON y la pestaña en la UI. La lógica de la state machine para `FinalizacionFase` queda fuera de este spec.

---

## 5. Integración en la app

### `main_window.py`
```python
from autoclave.ui_pyside.views.params_ciclo.params_ciclo import ParametrosCicloView

self._params_ciclo = ParametrosCicloView(nav_callback=self.navigate_to)
# agregar al stack y al dict de navigate_to con clave "params_ciclo"
```

### `admin_menu.py`
```python
_OPTION_ROUTES = {
    "Parámetros del ciclo": "params_ciclo",
    "Entradas / Salidas":   "io_menu",
}
```

---

## 6. Archivos afectados

| Acción  | Archivo |
|---------|---------|
| Crear   | `src/autoclave/ui_pyside/views/params_ciclo/__init__.py` |
| Crear   | `src/autoclave/ui_pyside/views/params_ciclo/params_ciclo.py` |
| Crear   | `src/autoclave/services/domain/logging/cycle_params_audit.py` |
| Modificar | `src/autoclave/ui_pyside/main_window.py` |
| Modificar | `src/autoclave/ui_pyside/views/admin_menu.py` |
| Modificar | `src/autoclave/cycles/factory/instrumental_134.json` |
| Modificar | `src/autoclave/cycles/factory/bowe_dick.json` |
| Modificar | `src/autoclave/cycles/user/instrumental_134.json` |
| Modificar | `src/autoclave/cycles/user/bowe_dick.json` |

---

## 7. Fuera de alcance

- Lógica de la state machine para `FinalizacionFase`
- Historial completo de cambios (solo se muestra la última modificación)
- Edición de ciclos de fábrica
- Creación o clonación de ciclos nuevos

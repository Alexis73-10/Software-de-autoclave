# Handoff — Estado al 2026-06-01

**Rama activa:** `dev`  
**PR abierto:** [#16 — feat: UI responsive a orientación — layout portrait + font scaling](https://github.com/Alexis73-10/Software-de-autoclave/pull/16)  
**PR anterior (pendiente de merge):** [#15 — feat: suministro_electrico modo seguro](https://github.com/Alexis73-10/Software-de-autoclave/pull/15)

---

## Qué se hizo hoy (2026-06-01) — Diseño de perfiles de equipo

### Resultado

Se definió y aprobó el diseño completo para que el software soporte 5 tipos de equipo distintos. El diseño está documentado en:

**`docs/superpowers/specs/2026-06-01-equipment-profiles-design.md`** (commit `e8aac80`)

**No se tocó código aún** — hoy fue puramente diseño/spec.

---

### Los 5 perfiles de equipo

| # | Perfil | Enum key |
|---|--------|----------|
| 1 | Mesa Clase N | `MESA_N` |
| 2 | Mesa Clase B | `MESA_B` |
| 3 | Mesa Clase B Laboratorio | `MESA_B_LAB` |
| 4 | Piso | `PISO` |
| 5 | Piso Laboratorio | `PISO_LAB` |

**Reglas importantes:**
- Mesa Clase N **no tiene** variante laboratorio
- Equipos de piso son **siempre Clase B** (vacío implícito)
- Mesa usa serpentín de cobre (pseudo-chaqueta), Piso usa chaqueta de vapor real

### Tabla de capacidades aprobada

| Perfil | vacuum | jacket | doors_max | cooling_max | liquids | liq_sensor | bleve |
|--------|--------|--------|-----------|-------------|---------|------------|-------|
| Mesa N | ✗ | ✗ | 1 | 0 | ✗ | ✗ | ✗ |
| Mesa B | ✓ | ✗ | 1 | 0 | ✗ | ✗ | ✗ |
| Mesa B Lab | ✓ | ✗ | 1 | 0 | ✓ | ✓ | ✓ |
| Piso | ✓ | ✓ | 2 | 4 | ✗ | ✗ | ✗ |
| Piso Lab | ✓ | ✓ | 2 | 4 | ✓ | ✓ | ✓ |

- `cooling_max`: nivel máximo de enfriamiento (0=ninguno, 1-4 modos por definir — agua/aire)
- `liq_sensor`: sensor `temp_2_camara` (sumergido en líquido)
- `bleve`: escape controlado anti-BLEVE en descompresión

### Los 5 tipos de puerta

| Tipo | DI posición | DO apertura/cierre | DO bloqueo | AI presión empaque | Atrapamiento |
|------|-------------|-------------------|------------|-------------------|--------------|
| `SIMPLE` | ✓ | ✗ | ✗ | ✗ | ✗ |
| `MOTORIZED` | ✓ | ✓ | ✗ | ✗ | ✗ |
| `LOCKING` | ✓ | ✗ | ✓ | ✗ | ✗ |
| `MOTORIZED_LOCKING` | ✓ | ✓ | ✓ | ✗ | ✗ |
| `ADVANCED` | ✓ | ✓ | ✓ | ✓ | ✓ |

- Solo `ADVANCED` tiene sensor de presión de empaque y sensor de atrapamiento
- Un equipo tiene **un solo** `DoorType` para todas sus puertas
- Cualquier perfil puede tener cualquier tipo de puerta

### Cambios aprobados en `InstallationProfile`

**Campos nuevos:** `equipment_class: EquipmentClass`, `cooling_level: int`  
**Campo modificado:** `door_type: str` → `door_type: DoorType` (enum de 5 valores)  
**Campos eliminados:** `drying_type` (se deriva de `cap.has_vacuum`), `equipment_type` (no controla comportamiento)

### Arquitectura central (opción B aprobada)

- `EquipmentClass` (enum 5 valores) se guarda en `InstallationProfile` en disco
- `EquipmentCapabilities` (dataclass frozen con flags) se **deriva en memoria** al arrancar via `get_capabilities(profile.equipment_class)` — nunca se serializa
- El resto del código usa **solo los flags**, nunca el enum directamente
- Todo vive en un nuevo archivo: `src/autoclave/installation/equipment.py`

### Fases del ciclo y sus condiciones

| Fase | Condición | Cambio |
|------|-----------|--------|
| `Prevacio` | `cap.has_vacuum` | Se omite si no hay bomba |
| `Precalentamiento` | ciclo define `is_liquid` | Rampa más lenta para líquidos |
| `Calentamiento` | `cap.has_liquid_sensor` | Usa `temp_camara` + `temp_2_camara` |
| `Estabilizacion` | — | Sin cambios |
| `Esterilizacion` | `cap.has_liquid_sensor` | Ambos sensores deben alcanzar setpoint |
| `Descompresion` | `cap.bleve_protection` / `cap.cooling_level` | Escape controlado + enfriamiento |
| `Secado` | — | Basado en tiempo; 4 modos por definir |
| `Finalizando` / `Finalizado` | — | Sin cambios |

**Nota:** el operador elige el ciclo; el ciclo ya trae `is_liquid` en su config. No hay selección de tipo de carga en runtime.

---

## Qué sigue mañana

### Paso inmediato: plan de implementación

El diseño está aprobado. El siguiente paso es invocar `writing-plans` para crear el plan de implementación detallado antes de tocar código. Punto de partida: spec en `docs/superpowers/specs/2026-06-01-equipment-profiles-design.md`.

### Orden sugerido de implementación

1. **`src/autoclave/installation/equipment.py`** — crear `EquipmentClass`, `EquipmentCapabilities`, `get_capabilities()` + tests
2. **`src/autoclave/installation/profile.py`** — actualizar `InstallationProfile` y validación
3. **`src/autoclave/devices/puertas/`** — `DoorType` enum + actualizar `AdvancedDoor` + `door_factory.py`
4. **`src/autoclave/devices/factory/factory.py`** — IO condicional por capacidades
5. **`src/autoclave/installation/wizard.py`** — 3 pasos nuevos (perfil, puertas, enfriamiento)
6. **`src/autoclave/state_machine/cycle_phases/base_fase.py`** — agregar `cap` al constructor
7. **Fases con lógica condicional** — `prevacio`, `precalentamiento`, `calentamiento`, `esterilizacion`, `descompresion`

### Pendiente fuera de alcance del plan de hoy

- Definición de los 4 modos de enfriamiento (cooling_level 1-4)
- Definición de los 4 modos de secado
- Relación entre `model_id` y perfiles de equipo

---

## Issue pendiente anterior: CalentamientoFase crash en producción

**Este issue existía antes y NO fue resuelto. Se debe atender después de implementar los perfiles.**

### Crash observado

```
TypeError: '<=' not supported between instances of 'float' and 'NoneType'
  File "calentamiento.py", line 89 in update
    if self._verificar_vapor_saturado(temp, pres, tolerancia):
  File "base_fase.py", line 71 in _verificar_vapor_saturado
    return abs(p_real_kpa - p_saturacion_kpa(t_celsius)) <= tolerancia_kpa
```

`tolerancia_kpa` llega como `None` → el ciclo Bowe & Dick no tiene el parámetro que el código busca.

### Estado actual de `calentamiento.py`

El archivo tiene cambios **sin commitear** en el working tree:

| Línea | Problema |
|-------|----------|
| 36 | `t_obj = get_param(...)` — sin fallback `or 134.0` |
| 37 | `tasa_seg = (get_param(...)) / 60` — sin fallback, crash si None |
| 38 | `timeout_seg = (get_param(...)) * 60` — sin fallback, crash si None |
| 39 | `tolerancia = get_param("calentamiento", "rango_presion_calentamiento")` — sin fallback `or 9.0` |
| 49 | `self._checkpoints = [0.80 * t_obj, 0.97 * t_obj]` — spec dice 0.50/0.90 |

### Conflicto de nombres de parámetros

| Ciclo | Clave JSON | Sección |
|-------|-----------|---------|
| `instrumental_134` | `presion_add_calentamiento` | `calentamiento` |
| `bowe_dick` | `rango_presion_calentamiento` | `calentamiento` |

El código (línea 39) usa `rango_presion_calentamiento`, pero `instrumental_134.json` tiene `presion_add_calentamiento` → ese ciclo queda con `tolerancia = None`.

### Opciones para resolver

**A.** Unificar en `rango_presion_calentamiento` — renombrar en `instrumental_134.json` + fallback `or 9.0`.  
**B.** Buscar con fallback entre las dos claves — más flexible.  
**C.** Unificar en `presion_add_calentamiento` — renombrar en `bowe_dick.json`.

### Qué falta

1. Elegir estrategia (A, B o C).
2. Actualizar los JSONs afectados.
3. Restaurar defaults `or X` en líneas 36-39 de `calentamiento.py`.
4. Decidir si checkpoints van a 0.50/0.90 (spec) o 0.80/0.97. El test `test_checkpoint_entra_en_sostenimiento` falla por este motivo.
5. Commitear `calentamiento.py`.
6. `pytest tests/test_calentamiento_fase.py -v` para verificar.

---

## Historial de sesiones anteriores

### 2026-05-28 — UI responsive a orientación

La UI detecta flips landscape ↔ portrait en ambos monitores y reconstruye el layout sin perder estado del ciclo. Font scaling, layout portrait para `InterfazPrincipal` y `CycleWindow`, fix multi-monitor con `winfo_width/height`. 20 tests nuevos. Commits `d20e14b` → `3e62ed3`.

### 2026-05-27 — `suministro_electrico` modo seguro (PR #15)

Flag `FALLO_SUMINISTRO_ELECTRICO` bloquea inicio de ciclo y bomba. En ciclo activo aborta y descomprime sin bomba. Puertas avanzadas con apertura sin bomba. Indicador en footer UI.

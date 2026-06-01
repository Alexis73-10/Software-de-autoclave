# Diseño: Perfiles de Equipo

**Fecha:** 2026-06-01  
**Estado:** Aprobado  

---

## Contexto

El software de control de autoclave debe funcionar en 5 tipos distintos de equipo. Cada tipo tiene diferente hardware (IO), comportamiento de puertas y lógica de ciclo. El objetivo es que una sola base de código soporte todos los equipos sin condicionales dispersos por nombre de modelo.

---

## Perfiles de equipo

Cinco perfiles fijos, seleccionados por el técnico durante la instalación:

| # | Nombre | Enum key |
|---|--------|----------|
| 1 | Mesa Clase N | `MESA_N` |
| 2 | Mesa Clase B | `MESA_B` |
| 3 | Mesa Clase B Laboratorio | `MESA_B_LAB` |
| 4 | Piso | `PISO` |
| 5 | Piso Laboratorio | `PISO_LAB` |

**Mesa clase N** no tiene variante laboratorio.  
**Equipos de piso** son siempre Clase B (vacío implícito).

---

## Capacidades por perfil

| Perfil | vacuum | jacket | doors_max | cooling_max | liquids | liq_sensor | bleve |
|--------|--------|--------|-----------|-------------|---------|------------|-------|
| Mesa N | ✗ | ✗ | 1 | 0 | ✗ | ✗ | ✗ |
| Mesa B | ✓ | ✗ | 1 | 0 | ✗ | ✗ | ✗ |
| Mesa B Lab | ✓ | ✗ | 1 | 0 | ✓ | ✓ | ✓ |
| Piso | ✓ | ✓ | 2 | 4 | ✗ | ✗ | ✗ |
| Piso Lab | ✓ | ✓ | 2 | 4 | ✓ | ✓ | ✓ |

**Glosario de flags:**
- `vacuum` — bomba de vacío presente
- `jacket` — chaqueta de vapor real (False = serpentín de cobre)
- `doors_max` — máximo de puertas configurables en ese equipo
- `cooling_max` — nivel máximo de enfriamiento soportado (0 = sin enfriamiento; modos 1–4 por definir)
- `liquids` — el equipo puede ejecutar ciclos de líquidos
- `liq_sensor` — sensor de temperatura sumergido (`temp_2_camara`)
- `bleve` — protección anti-BLEVE en la fase de purga/descompresión

---

## Tipos de puerta

Cinco tipos. Un equipo tiene un único `DoorType` para todas sus puertas.

| Tipo | DI posición | DO apertura/cierre | DO bloqueo | AI presión empaque | Atrapamiento DI |
|------|-------------|-------------------|------------|-------------------|-----------------|
| `SIMPLE` | ✓ | ✗ | ✗ | ✗ | ✗ |
| `MOTORIZED` | ✓ | ✓ | ✗ | ✗ | ✗ |
| `LOCKING` | ✓ | ✗ | ✓ | ✗ | ✗ |
| `MOTORIZED_LOCKING` | ✓ | ✓ | ✓ | ✗ | ✗ |
| `ADVANCED` | ✓ | ✓ | ✓ | ✓ | ✓ |

Solo `ADVANCED` tiene sensor de presión de empaque y sensor de atrapamiento.  
Cualquier perfil de equipo puede usar cualquier tipo de puerta.

---

## `InstallationProfile` actualizado

```python
@dataclass
class InstallationProfile:
    machine_id:      str
    model_id:        str
    serial_number:   str
    equipment_class: EquipmentClass   # nuevo
    door_count:      int              # 1 o 2, <= cap.door_count_max
    door_type:       DoorType         # nuevo (reemplaza door_type: str)
    cooling_level:   int              # nuevo, 0 <= cooling_level <= cap.cooling_level_max
    door_id:         int
    role:            Role
    created_at:      datetime
    locked:          bool = True
```

**Campos eliminados:**
- `drying_type` — derivado de `cap.has_vacuum`
- `equipment_type` — no controla ningún comportamiento

**Validaciones nuevas:**
- `door_count <= cap.door_count_max`
- `cooling_level <= cap.cooling_level_max`

---

## Wizard — pasos nuevos

Se agregan 3 pasos antes de los existentes:

1. **Selección de perfil** — listado de los 5 perfiles con descripción de capacidades
2. **Configuración de puertas** — cantidad (solo editable si `cap.door_count_max == 2`) + tipo de puerta
3. **Configuración de enfriamiento** — selector 0–`cap.cooling_level_max`; oculto si `cap.cooling_level_max == 0`

---

## Factory y dispositivos

### `factory.py` — `build_hardware`

Construye el IO condicionalmente según capacidades:

```python
cap = get_capabilities(profile.equipment_class)

# Señales condicionales
if cap.has_vacuum:         # agrega bomba_vacio DO, vacio_camara DO
if cap.has_full_jacket:    # agrega pres_chaqueta AI, vapor_chaqueta DO, descompresion_chaqueta DO
if cap.cooling_level > 0:  # agrega señales de enfriamiento según nivel
if cap.has_liquid_sensor:  # agrega temp_2_camara AI
```

La config de puerta incluye solo las claves `di`/`do`/`ai` que el `DoorType` realmente tiene.

### `door_factory.py`

Mapea `DoorType` → instancia de puerta. `SimpleDoor` para `SIMPLE`. `AdvancedDoor` para los 4 restantes, con `do` y `ai` opcionales según tipo:

| DoorType | `do` open/close | `do` lock | `ai` presión |
|----------|-----------------|-----------|--------------|
| `MOTORIZED` | ✓ | — | — |
| `LOCKING` | — | ✓ | — |
| `MOTORIZED_LOCKING` | ✓ | ✓ | — |
| `ADVANCED` | ✓ | ✓ | ✓ |

`AdvancedDoor` no crea clases nuevas — maneja claves ausentes sin fallar.

---

## Fases del ciclo

`EquipmentCapabilities` se agrega como parámetro a `BaseFase.__init__` y queda disponible como `self.cap` en todas las fases.

| Fase | Condición | Comportamiento |
|------|-----------|----------------|
| `Prevacio` | `cap.has_vacuum` | Se omite si no hay bomba |
| `Precalentamiento` | ciclo define `is_liquid` | Rampa más lenta para líquidos |
| `Calentamiento` | `cap.has_liquid_sensor` | Monitorea `temp_camara` + `temp_2_camara` |
| `Estabilizacion` | — | Sin cambios |
| `Esterilizacion` | `cap.has_liquid_sensor` | Ambos sensores deben alcanzar setpoint |
| `Descompresion` | `cap.bleve_protection` / `cap.cooling_level` | Escape controlado; enfriamiento según nivel |
| `Secado` | — | Basado en tiempo; modos por definir |
| `Finalizando` | — | Sin cambios |
| `Finalizado` | — | Sin cambios |

El operador selecciona un ciclo; el ciclo ya tiene configurado si es para líquidos (`is_liquid`) o sólidos. Los flags de capacidad determinan qué ciclos están disponibles para seleccionar.

---

## Flujo de datos en arranque

```
Wizard
  └─ selecciona EquipmentClass, DoorType, door_count, cooling_level
       └─ InstallationProfile (persiste en disco)
            └─ bootstrap.py → carga perfil → get_capabilities()
                 └─ EquipmentCapabilities (solo en memoria, derivado cada arranque)
                      ├─ factory.py → build_hardware() con IO condicional
                      ├─ door_factory.py → crea puertas según DoorType
                      └─ context.py → inyecta caps en state_machine
                           └─ BaseFase.cap → lógica condicional por fase
```

`EquipmentCapabilities` nunca se serializa. Se deriva siempre de `equipment_class` al arrancar, lo que garantiza consistencia si la tabla de capacidades cambia.

---

## Archivos afectados

**Nuevo:**
- `src/autoclave/installation/equipment.py` — `EquipmentClass`, `EquipmentCapabilities`, `get_capabilities()`

**Modificados:**
- `src/autoclave/installation/profile.py`
- `src/autoclave/installation/wizard.py`
- `src/autoclave/devices/factory/factory.py`
- `src/autoclave/devices/puertas/door_factory.py`
- `src/autoclave/devices/puertas/advanced_door.py`
- `src/autoclave/state_machine/cycle_phases/base_fase.py`
- Fases con comportamiento condicional: `prevacio.py`, `precalentamiento.py`, `calentamiento.py`, `esterilizacion.py`, `purga.py` (o `descompresion.py`)

---

## Fuera de alcance

- Definición de los 4 modos de secado
- Definición de los 4 modos de enfriamiento (1–4)
- Relación entre `model_id` y perfiles de equipo

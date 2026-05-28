# Diseño: Tipo y cantidad de puertas desde InstallationProfile

**Fecha:** 2026-05-25  
**Estado:** Aprobado

## Contexto

`factory.py` hardcodea `"type": 2` (AdvancedDoor) y siempre crea 2 puertas, ignorando el perfil de instalación. `create_door()` lee el tipo de puerta desde `ConfigManager` en lugar del perfil. El perfil ya está disponible en `BackendContext` antes de llamar a `build_hardware()` pero nunca se le pasa.

## Comportamiento nuevo

### Parámetros del perfil usados

| Campo | Tipo | Valores | Efecto |
|-------|------|---------|--------|
| `door_type` | str | `"simple"` / `"advanced"` | Determina la clase de puerta instanciada |
| `door_count` | int | `1` / `2` | Cuántas puertas se crean |

### Flujo de datos

```
InstallationProfile
    ↓
build_hardware(profile)
    → mapea door_type: "simple"→1, "advanced"→2
    → devuelve doors_cfg[:door_count]  (solo las puertas que corresponden)
    → cada cfg incluye "type" resuelto desde el perfil

BackendContext
    → pasa self.profile a build_hardware(profile)

create_door(config, io)
    → lee io["cfg"]["type"]   ← antes leía config.get("tipo_puerta")
    → instancia SimpleDoor (type=1) o AdvancedDoor (type=2)
```

### Mapeo door_type → entero

| `profile.door_type` | `cfg["type"]` | Clase instanciada |
|--------------------|--------------|-------------------|
| `"simple"` | `1` | `SimpleDoor` |
| `"advanced"` | `2` | `AdvancedDoor` |

## Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `src/autoclave/devices/factory/factory.py` | `build_hardware(profile)` — recibe perfil, mapea `door_type` a entero, filtra `doors_cfg` por `door_count` |
| `src/autoclave/devices/puertas/door_factory.py` | Leer `cfg["type"]` en lugar de `config.get("tipo_puerta")` |
| `src/autoclave/backend/context.py` | Pasar `self.profile` a `build_hardware()` |

## Lo que NO cambia

- Estructura interna de `doors_cfg` (campos `name`, `di`, `do`, `ai`)
- Clases `SimpleDoor` y `AdvancedDoor`
- `ServicioPuertas` y el resto del backend
- El perfil sigue validando `door_type` en `{"simple", "advanced"}` y `door_count` en `{1, 2}`

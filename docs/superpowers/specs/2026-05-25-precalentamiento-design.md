# Diseño: Fase Precalentamiento (rediseño)

**Fecha:** 2026-05-25  
**Estado:** Aprobado

## Contexto

La fase de precalentamiento existente calentaba la cámara (`vapor_camara`) verificando temperatura y presión de cámara. El nuevo comportamiento apunta a la chaqueta: calentar la chaqueta hasta presión objetivo y mantenerla un tiempo configurable antes de continuar con la purga.

## Comportamiento nuevo

### Parámetros JSON (sección `"precalentamiento"`)

| Parámetro | Tipo | Unidad | Descripción |
|-----------|------|--------|-------------|
| `presion_precalentamiento` | float | kPa | Presión objetivo de la chaqueta |
| `tiempo_precalentamiento` | float | min | Tiempo de sostenimiento; `0` = saltar fase |
| `timeout_precalentamiento` | float | min | Tiempo máximo total antes de FALLO |

El parámetro `temperatura_precalentamiento` queda obsoleto y se elimina de la lógica (puede permanecer en el JSON sin efecto).

### Sensor y salida

- **Sensor:** `pres_chaqueta` (`estado.sensores_pres["pres_chaqueta"]`)
- **Salida:** `vapor_chaqueta` (`set_do.vapor_chaqueta_on/off()`)

### Flujo de estados

```
tiempo == 0
    → COMPLETADO (skip)

tiempo > 0:
    Inicializar: timer_timeout = now + timeout_seg

    Loop (cada ciclo):

        1. Timeout check
               time.time() > timer_timeout
               → vapor_chaqueta_off() → FALLO

        2. Leer pres_chaqueta
               None → EN_CURSO (esperar sensor)

        3. Aproximación (timer_sostenimiento is None)
               vapor_chaqueta_on()
               pres_chaqueta >= presion_obj
               → timer_sostenimiento = now, fase_en_sostenimiento = True

        4. Sostenimiento (timer_sostenimiento is not None)
               pres_chaqueta >= presion_obj → vapor_chaqueta_off()
               pres_chaqueta <  presion_obj → vapor_chaqueta_on()
               elapsed >= tiempo_seg
               → vapor_chaqueta_off(), fase_en_sostenimiento = False → COMPLETADO
```

### Control de válvula durante sostenimiento

Bang-bang simple: válvula cierra cuando presión ≥ objetivo, abre cuando cae por debajo. El timer de sostenimiento **no se reinicia** si la presión cae — sigue contando mientras la válvula recupera la presión.

### Salidas al terminar

| Resultado | `vapor_chaqueta` | `fase_en_sostenimiento` |
|-----------|-----------------|------------------------|
| COMPLETADO | OFF | False |
| FALLO | OFF | False |

## Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `src/autoclave/state_machine/cycle_phases/precalentamiento.py` | Reemplazar lógica completa |
| `src/autoclave/cycles/factory/instrumental_134.json` | Verificar/agregar parámetros `precalentamiento` |
| `src/autoclave/cycles/factory/bowe_dick.json` | Verificar/agregar parámetros `precalentamiento` |

## Lo que NO cambia

- Interfaz `BaseFase` (`update()` / `reset()`)
- Nombre de la fase (`name = "PRECALENTAMIENTO"`)
- Integración con `CicloState` (sin cambios de orquestación)
- Parámetro `tiempo == 0` → skip (comportamiento existente conservado)

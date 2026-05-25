# Diseño: Fase Purga (implementación)

**Fecha:** 2026-05-25  
**Estado:** Aprobado

## Contexto

La fase de purga existente era un stub que retornaba `COMPLETADO` inmediatamente. El nuevo comportamiento abre dos válvulas simultáneamente (`vapor_camara` y `descompresion_rapida`) durante `tiempo_purga` minutos para crear un flujo de vapor que desplaza el aire seco de la cámara antes de la etapa de prevacío.

## Comportamiento nuevo

### Parámetros JSON (sección `"purga"`)

| Parámetro | Tipo | Unidad | Descripción |
|-----------|------|--------|-------------|
| `tiempo_purga` | int | min | Duración del flujo; `0` = saltar fase |
| `presion_purga` | int | kPa | Permanece en el JSON pero no se usa en esta implementación |

El parámetro `timeout_purga` se elimina de ambos JSONs de ciclo — no aplica a una fase puramente temporal.

### Sensor y salidas

- **Sensor:** ninguno — la fase no monitorea sensores durante la purga.
- **Salidas:**
  - `set_do.vapor_camara_on()` / `vapor_camara_off()`
  - `set_do.descompresion_rapida_on()` / `descompresion_rapida_off()`

### Flujo de estados

```
tiempo == 0
    → COMPLETADO (skip, sin activar válvulas)

tiempo > 0:
    Primer update():
        vapor_camara_on()
        descompresion_rapida_on()
        _timer_fin = time.time() + tiempo_seg

    Loop (cada ciclo):
        time.time() >= _timer_fin
            → vapor_camara_off()
            → descompresion_rapida_off()
            → COMPLETADO

        (sino) → EN_CURSO
```

### Salidas al terminar

| Resultado | `vapor_camara` | `descompresion_rapida` |
|-----------|---------------|----------------------|
| COMPLETADO | OFF | OFF |

No existe resultado FALLO — la fase siempre termina en COMPLETADO cuando se cumple el tiempo.

## Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `src/autoclave/state_machine/cycle_phases/purga.py` | Reemplazar lógica completa |
| `src/autoclave/cycles/factory/instrumental_134.json` | Eliminar `timeout_purga` |
| `src/autoclave/cycles/factory/bowe_dick.json` | Eliminar `timeout_purga` |

## Lo que NO cambia

- Interfaz `BaseFase` (`update()` / `reset()`)
- Nombre de la fase (`name = "PURGA"`)
- Integración con `CicloState` (sin cambios de orquestación)
- Parámetro `tiempo == 0` → skip (comportamiento existente conservado)

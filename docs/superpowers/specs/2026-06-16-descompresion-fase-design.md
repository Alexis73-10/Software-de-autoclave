# Spec — Fase de Descompresión / Despresurización (6 modos)
**Fecha:** 2026-06-16

## Alcance

Implementar `DescompresionFase`, la fase que sigue a `EsterilizacionFase` en el pipeline del ciclo. La fase gestiona la bajada de presión de la cámara desde presión de esterilización hasta presión atmosférica, con soporte para 6 modos de operación y un tiempo de espera previo configurable.

---

## Pipeline actualizado

```
PRECALENTAMIENTO → PURGA → PRE_VACIO → CALENTAMIENTO → ESTABILIZACION → ESTERILIZACION → DESCOMPRESION
```

---

## Arquitectura

**Patrón:** Clase única `DescompresionFase(BaseFase)`, mismo patrón que las demás fases. Un archivo nuevo: `src/autoclave/state_machine/cycle_phases/descompresion.py`.

**Integración en `ciclo.py`:** Importar y agregar `DescompresionFase(*_args)` al final del pipeline `self._fases`.

### Estado interno

| Variable | Tipo | Propósito |
|----------|------|-----------|
| `_modo` | `int` | Modo seleccionado (0–5), leído en `reset()` |
| `_etapa` | `str \| None` | `None` → `"pre_espera"` → `"modo"` |
| `_sub_etapa` | `str \| None` | Modo 3: `"lenta"/"rapida"`. Modos 4/5: `"enfriamiento"/"descompresion"` |
| `_t_inicio` | `float \| None` | Timestamp de inicio de la etapa actual |
| `_t_timeout` | `float \| None` | Timestamp límite del modo (None para modo 0) |
| `_t_pulso_chaqueta` | `float \| None` | Timestamp de inicio del pulso actual de `descompresion_chaqueta` |
| `_chaqueta_abierta` | `bool` | Estado actual del pulso de chaqueta |
| `_t_aire_comprimido` | `float \| None` | Timestamp hasta el que se espera tras pulso de `aire_comprimido_camara` |

### Flujo de `update()`

1. **Primera llamada** (`_etapa is None`): `_apagar_todo()`, leer `tiempo_pre_despresurizacion`.
   - Si > 0: `_etapa = "pre_espera"`, guardar timestamp.
   - Si == 0: `_etapa = "modo"`, llamar `_iniciar_modo()`.
2. **`"pre_espera"`**: esperar los segundos configurados con todas las salidas apagadas. Al expirar: `_etapa = "modo"`, llamar `_iniciar_modo()`.
3. **`"modo"`**: verificar timeout (modos 1–5), despachar a `_tick_modo_N()`.

### `_iniciar_modo()`

- Para modos 1–5: calcular `_t_timeout = now + timeout_min * 60`.
- Para modo 0: `_t_timeout = None`.
- Para modo 3: `_sub_etapa = "lenta"`.
- Para modos 4/5: `_sub_etapa = "enfriamiento"`, inicializar variables de pulso.

### `_apagar_todo()`

Apaga las 5 salidas relevantes: `descompresion_rapida_off()`, `descompresion_lenta_off()`, `descompresion_chaqueta_off()`, `aire_comprimido_camara_off()`, `agua_chaqueta_off()`.

Llamado al: entrar a `"pre_espera"`, completar cualquier modo, y al detectar timeout (antes de retornar `FALLO`).

### Condición de presión atmosférica

```
pres_camara <= presion_admosferica + rango_presion_atm
```

Usando helpers existentes `_pres_atm()` y `_rango_atm()` de `BaseFase`.

---

## Modos de operación

### Modo 0 — Pasivo

Sin salidas activas. La presión cae por enfriamiento natural del equipo (transferencia térmica al ambiente). Sin timeout.

- **Condición de fin:** `pres_camara <= presion_atm + rango_atm` → `COMPLETADO`.

### Modo 1 — Descompresión rápida

- Activa `descompresion_rapida_on()` en cada tick.
- **Condición de fin:** presión atm → `_apagar_todo()` → `COMPLETADO`.
- **Timeout:** `FALLO` + `_apagar_todo()`.

### Modo 2 — Descompresión lenta

- Activa `descompresion_lenta_on()` en cada tick.
- **Condición de fin:** presión atm → `_apagar_todo()` → `COMPLETADO`.
- **Timeout:** `FALLO` + `_apagar_todo()`.

### Modo 3 — Descompresión combinada

`_sub_etapa = "lenta"`:
- `descompresion_lenta_on()` hasta que `pres_camara <= presion_cambio`.
- Al alcanzar `presion_cambio`: `descompresion_lenta_off()`, `descompresion_rapida_on()`, `_sub_etapa = "rapida"`.

`_sub_etapa = "rapida"`:
- `descompresion_rapida_on()` hasta presión atm → `_apagar_todo()` → `COMPLETADO`.

Timeout único para todo el modo. Si expira en cualquier sub-etapa: `_apagar_todo()` → `FALLO`.

### Modo 4 — Descompresión + enfriamiento 1

`_sub_etapa = "enfriamiento"`:
- `agua_chaqueta_on()` permanente.
- `aire_comprimido_camara`: si `pres_camara < presion_camara_enfriamiento` → pulso on + registrar `_t_aire_comprimido = now + 3s`. Mientras `now < _t_aire_comprimido`, no volver a pulsar. Si `pres >= objetivo` → `aire_comprimido_camara_off()`.
- `descompresion_chaqueta`: pulsos alternando on/off con `tiempo_apertura_chaqueta` / `tiempo_cierre_chaqueta`. Si `tiempo_cierre_chaqueta == 0` → siempre activa sin alternancia.
- Al alcanzar `temp_camara <= temperatura_enfriamiento`:
  - `aire_comprimido_camara_off()`, `agua_chaqueta_off()`
  - `descompresion_chaqueta_on()` (se mantiene)
  - `descompresion_rapida_on()`
  - `_sub_etapa = "descompresion"`

`_sub_etapa = "descompresion"`:
- Mantiene `descompresion_chaqueta_on()` + `descompresion_rapida_on()` en cada tick.
- Al alcanzar presión atm → `_apagar_todo()` → `COMPLETADO`.
- **Timeout:** aplica sobre el modo completo (enfriamiento + descompresión final). Si expira: `_apagar_todo()` → `FALLO`.

### Modo 5 — Descompresión + enfriamiento 2

Idéntico al modo 4 con dos diferencias en `_sub_etapa = "enfriamiento"`:
1. Activa adicionalmente `descompresion_lenta_on()` durante todo el enfriamiento.
2. Al transicionar a `"descompresion"`: ejecuta `descompresion_lenta_off()` antes de activar `descompresion_rapida_on()`.

`_sub_etapa = "descompresion"`: igual que modo 4.

### Resumen de salidas activas

| Modo / etapa | rapida | lenta | chaqueta | aire_camara | agua_chaqueta |
|---|---|---|---|---|---|
| 0 | — | — | — | — | — |
| 1 | ✓ | — | — | — | — |
| 2 | — | ✓ | — | — | — |
| 3 lenta | — | ✓ | — | — | — |
| 3 rapida | ✓ | — | — | — | — |
| 4 enfriamiento | — | — | pulsos | pulso+3s | ✓ |
| 4 descompresion | ✓ | — | ✓ | — | — |
| 5 enfriamiento | — | ✓ | pulsos | pulso+3s | ✓ |
| 5 descompresion | ✓ | — | ✓ | — | — |

---

## Parámetros JSON

Se agrega la sección `"descompresion"` en ambos archivos de ciclos:
- `src/autoclave/cycles/factory/instrumental_134.json`
- `src/autoclave/cycles/factory/bowe_dick.json`
- `src/autoclave/cycles/user/instrumental_134.json`
- `src/autoclave/cycles/user/bowe_dick.json`

```json
"descompresion": {
    "modo": {
        "value": 1, "type": "int", "unit": "", "min": 0, "max": 5
    },
    "tiempo_pre_despresurizacion": {
        "value": 0, "type": "int", "unit": "sec", "min": 0, "max": 3600
    },
    "modo_1": {
        "timeout": { "value": 10,  "type": "int", "unit": "min", "min": 1, "max": 3600 }
    },
    "modo_2": {
        "timeout": { "value": 30,  "type": "int", "unit": "min", "min": 1, "max": 3600 }
    },
    "modo_3": {
        "presion_cambio": { "value": 150, "type": "int",   "unit": "kPa", "min": 0, "max": 500  },
        "timeout":        { "value": 30,  "type": "int",   "unit": "min", "min": 1, "max": 3600 }
    },
    "modo_4": {
        "presion_camara_enfriamiento": { "value": 200, "type": "int",   "unit": "kPa", "min": 0, "max": 500  },
        "temperatura_enfriamiento":    { "value": 80,  "type": "float", "unit": "°C",  "min": 0, "max": 150  },
        "tiempo_apertura_chaqueta":    { "value": 5,   "type": "int",   "unit": "sec", "min": 1, "max": 3600 },
        "tiempo_cierre_chaqueta":      { "value": 10,  "type": "int",   "unit": "sec", "min": 0, "max": 3600 },
        "timeout":                     { "value": 120, "type": "int",   "unit": "min", "min": 1, "max": 3600 }
    },
    "modo_5": {
        "presion_camara_enfriamiento": { "value": 200, "type": "int",   "unit": "kPa", "min": 0, "max": 500  },
        "temperatura_enfriamiento":    { "value": 80,  "type": "float", "unit": "°C",  "min": 0, "max": 150  },
        "tiempo_apertura_chaqueta":    { "value": 5,   "type": "int",   "unit": "sec", "min": 1, "max": 3600 },
        "tiempo_cierre_chaqueta":      { "value": 10,  "type": "int",   "unit": "sec", "min": 0, "max": 3600 },
        "timeout":                     { "value": 120, "type": "int",   "unit": "min", "min": 1, "max": 3600 }
    }
}
```

**Acceso desde el código:** `cycle.get_param("descompresion", "modo_4", "timeout")` → `120`. Compatible con la implementación actual de `Cycle.get_param()` sin modificaciones.

**`modo_0`** no tiene entrada — sin parámetros ni timeout.

**`tiempo_cierre_chaqueta = 0`** → `descompresion_chaqueta` siempre abierta durante enfriamiento (sin pulsos).

**Validación de `cooling_mode_max`:** la UI/wizard impide configurar un modo fuera del rango soportado por el equipo. La fase no valida esto en runtime.

---

## Tests

**Archivo:** `tests/test_descompresion_fase.py`

**Helper `_make_fase(modo, pres, temp, ...)`** — `MagicMock` para estado, `set_do`, `config` y `cycle`. `cycle.get_param` con `side_effect` por claves para devolver valores según modo.

| Test | Qué verifica |
|------|-------------|
| `test_pre_espera_mantiene_salidas_apagadas` | Con `tiempo_pre > 0`, primer tick no activa salidas |
| `test_pre_espera_0_entra_directo_al_modo` | Con `tiempo_pre = 0`, entra al modo en primer tick |
| `test_modo_0_en_curso_con_pres_alta` | Retorna `EN_CURSO` mientras `pres > atm+rango` |
| `test_modo_0_completa_al_alcanzar_presion_atm` | Retorna `COMPLETADO` cuando `pres <= atm+rango` |
| `test_modo_1_activa_rapida` | `descompresion_rapida_on` llamado en tick activo |
| `test_modo_1_completa_y_apaga_salidas` | Al alcanzar presión atm → `rapida_off` + `COMPLETADO` |
| `test_modo_2_activa_lenta` | `descompresion_lenta_on` llamado en tick activo |
| `test_modo_2_completa_y_apaga_salidas` | Al alcanzar presión atm → `lenta_off` + `COMPLETADO` |
| `test_modo_3_lenta_hasta_presion_cambio` | Con `pres > presion_cambio` → `lenta_on`, sin `rapida` |
| `test_modo_3_transicion_a_rapida` | Con `pres <= presion_cambio` → `lenta_off` + `rapida_on` |
| `test_modo_3_completa_en_subetapa_rapida` | Desde sub-etapa rapida + presión atm → `COMPLETADO` |
| `test_modo_1_timeout_retorna_fallo` | Timeout expirado → `FALLO` + salidas apagadas |
| `test_modo_3_timeout_retorna_fallo` | Timeout en sub-etapa lenta → `FALLO` |
| `test_modo_4_activa_agua_chaqueta` | `agua_chaqueta_on` presente en enfriamiento |
| `test_modo_4_pulso_aire_cuando_pres_baja` | Con `pres < objetivo` → `aire_comprimido_camara_on` |
| `test_modo_4_aire_espera_3s_entre_pulsos` | Segundo tick dentro de 3s no vuelve a pulsar |
| `test_modo_4_chaqueta_pulso_on_off` | Alterna `descompresion_chaqueta_on/off` según tiempos |
| `test_modo_4_chaqueta_siempre_abierta_si_cierre_0` | Con `tiempo_cierre = 0` → siempre on, sin alternancia |
| `test_modo_4_transicion_a_descompresion_al_alcanzar_temp` | Al `temp <= temp_obj` → `agua_off`, `aire_off`, `rapida_on`, `chaqueta_on` |
| `test_modo_4_completa_al_alcanzar_presion_atm` | Desde sub-etapa `"descompresion"` + presión atm → `COMPLETADO` |
| `test_modo_5_lenta_activa_durante_enfriamiento` | `descompresion_lenta_on` presente en `"enfriamiento"` |
| `test_modo_5_lenta_apagada_al_transicionar` | Al llegar a `temp_obj` → `lenta_off` antes de activar `rapida` |

**Total: 22 tests.**

---

## Archivos afectados

| Archivo | Acción |
|---------|--------|
| `src/autoclave/state_machine/cycle_phases/descompresion.py` | Crear |
| `src/autoclave/state_machine/states/ciclo.py` | Modificar — agregar `DescompresionFase` al pipeline |
| `src/autoclave/cycles/factory/instrumental_134.json` | Modificar — agregar sección `"descompresion"` |
| `src/autoclave/cycles/factory/bowe_dick.json` | Modificar — agregar sección `"descompresion"` |
| `src/autoclave/cycles/user/instrumental_134.json` | Modificar — agregar sección `"descompresion"` |
| `src/autoclave/cycles/user/bowe_dick.json` | Modificar — agregar sección `"descompresion"` |
| `tests/test_descompresion_fase.py` | Crear |

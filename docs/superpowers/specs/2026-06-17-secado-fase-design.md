# Diseño: Fase SECADO del ciclo de autoclave

**Fecha:** 2026-06-17  
**Estado:** Aprobado

---

## Contexto

El ciclo de esterilización actualmente termina en `DescompresionFase`. Se agrega una nueva fase `SecadoFase` que se ejecuta **entre `EsterilizacionFase` y `DescompresionFase`**, implementando tres modos de secado diferenciados.

Los parámetros `tiempo_secado` y `tipo_secado` que hoy viven en la sección `"esterilizacion"` del JSON de ciclo son obsoletos y se reemplazarán por la sección `"secado"` con la parametrización completa.

---

## Arquitectura

### Posición en el pipeline

```
PrecalentamientoFase → PurgaFase → PrevacioFase →
CalentamientoFase → EstabilizacionFase → EsterilizacionFase →
**SecadoFase** → DescompresionFase
```

### Condiciones de skip

- `cap.has_vacuum == False` → COMPLETADO inmediato (no hay vacío en el equipo)
- `tiempo_secado == 0` → COMPLETADO inmediato (operador deshabilitó el secado)

### Control de chaqueta

`SecadoFase` controla la chaqueta de vapor de forma independiente usando `presion_chaqueta_secado` ± `rango_chaqueta_secado`. Para evitar conflicto, `CicloState._mantener_chaqueta()` se suprime cuando la fase activa es `SecadoFase` (verificado con `isinstance`).

---

## Parámetros JSON — sección `"secado"`

Nueva sección en todos los archivos de ciclo. Los campos `tiempo_secado` y `tipo_secado` se **eliminan** de `"esterilizacion"`.

| Parámetro | Tipo | Default | Unidad | Aplica a |
|---|---|---|---|---|
| `modo` | int | 1 | — | todos |
| `tiempo_secado` | float | 2.0 | min | todos |
| `presion_chaqueta_secado` | int | 200 | kPa | todos |
| `rango_chaqueta_secado` | int | 30 | kPa | todos |
| `presion_baja_secado` | int | 20 | kPa | modo 3 |
| `presion_alta_secado` | int | 80 | kPa | modo 3 |
| `timeout_pulso` | int | 10 | min | modo 3 |

`modo` puede ser 1, 2 o 3. Los parámetros de modo 3 se ignoran en modos 1 y 2.

---

## Flujo por modo

### Helper compartido: `_tick_chaqueta()`

Bang-bang sobre `pres_chaqueta`:
- `pres < presion_chaqueta_secado - rango_chaqueta_secado` → `vapor_chaqueta_on()`
- `pres > presion_chaqueta_secado + rango_chaqueta_secado` → `vapor_chaqueta_off()`
- Dentro del rango → sin cambio

Llamado al inicio del `update()` de cada tick en todos los modos.

---

### Modo 1 — Vacío con chaqueta

**Inicialización** (`reset()`):
- `_timer_fin = None`, `_inicializado = False`

**Cada tick** (`update()`):
1. Si no inicializado: `_timer_fin = now + tiempo_secado_seg`, `_inicializado = True`
2. `_tick_chaqueta()`
3. `bomba_vacio_on()`, `vacio_camara_on()`
4. Si `now >= _timer_fin` → `_apagar_todo()` → `COMPLETADO`
5. Retorna `EN_CURSO`

---

### Modo 2 — Vacío + aire atmosférico con chaqueta

Igual que Modo 1, más:
- Paso 3 también llama `aire_admosferico_camara_on()`
- `_apagar_todo()` también llama `aire_admosferico_camara_off()`

---

### Modo 3 — Pulsos vacío/aire con chaqueta

**Sub-estados:** `VACIO_BAJO` y `AIRE_ALTO`

**Inicialización** (`reset()`):
- `_sub_estado = None`, `_timer_fin = None`, `_timeout_pulso_fin = None`, `_inicializado = False`

**Cada tick** (`update()`):

```
Si no inicializado:
  _timer_fin = now + tiempo_secado_seg
  _sub_estado = VACIO_BAJO
  _timeout_pulso_fin = now + timeout_pulso_seg
  _inicializado = True

_tick_chaqueta()

Si now >= _timer_fin → _apagar_todo() → COMPLETADO  ← check primero

Si _sub_estado == VACIO_BAJO:
  bomba_vacio_on(), vacio_camara_on()
  Si now > _timeout_pulso_fin → _apagar_todo() → FALLO
  Si pres_camara <= presion_baja_secado:
    bomba_vacio_off(), vacio_camara_off()
    _sub_estado = AIRE_ALTO
    _timeout_pulso_fin = now + timeout_pulso_seg

Si _sub_estado == AIRE_ALTO:
  aire_admosferico_camara_on()
  Si now > _timeout_pulso_fin → _apagar_todo() → FALLO
  Si pres_camara >= presion_alta_secado:
    aire_admosferico_camara_off()
    _sub_estado = VACIO_BAJO
    _timeout_pulso_fin = now + timeout_pulso_seg

Retorna EN_CURSO
```

---

### `_apagar_todo()`

```python
self.set_do.bomba_vacio_off()
self.set_do.vacio_camara_off()
self.set_do.aire_admosferico_camara_off()
self.set_do.vapor_chaqueta_off()
```

---

## Cambios en archivos existentes

### `states/ciclo.py`

1. Import `SecadoFase`
2. Agregar a `self._fases` entre `EsterilizacionFase` y `DescompresionFase`
3. Modificar `_mantener_chaqueta()`:
   ```python
   fase_actual = self._fases[self._fase_idx] if self._fase_idx < len(self._fases) else None
   if isinstance(fase_actual, SecadoFase):
       return
   ```

### `cycles/factory/instrumental_134.json` y `bowe_dick.json`

- Eliminar `tiempo_secado` y `tipo_secado` de sección `"esterilizacion"`
- Agregar sección `"secado"` con todos los parámetros

### `cycles/user/*.json`

Mismos cambios que factory.

### `backend/server.py`

Actualizar el endpoint PATCH `/cycle/parameters` que hoy escribe en `["esterilizacion"]["tiempo_secado"]` para escribir en `["secado"]["tiempo_secado"]`. Agregar manejo de `modo`, `presion_chaqueta_secado`, `rango_chaqueta_secado`, `presion_baja_secado`, `presion_alta_secado`, `timeout_pulso`.

### `ui_pyside/views/secado.py`

- Leer `tiempo_secado` y `modo` desde `parameters["secado"]`
- Mostrar selector de modo (1/2/3)
- Para modo 3, mostrar campos de `presion_baja_secado` y `presion_alta_secado`
- Enviar los parámetros actualizados al backend

---

## Testing

- Test modo 1: verifica que `bomba_vacio_on` y `vacio_camara_on` se llaman en cada tick hasta completar
- Test modo 2: igual + `aire_admosferico_camara_on`
- Test modo 3: verifica la alternancia VACIO_BAJO → AIRE_ALTO → VACIO_BAJO y la condición de timeout
- Test skip: `tiempo_secado=0` y `cap.has_vacuum=False` → COMPLETADO inmediato
- Test timeout modo 3: si pres no alcanza `presion_baja` en `timeout_pulso` → FALLO

---

## Decisiones de diseño

- **`_apagar_todo()` apaga la bomba de vacío durante fase AIRE en modo 3**: por consistencia con PrevacioFase y seguridad de la bomba.
- **Chaqueta se apaga en `_apagar_todo()`**: al terminar secado (COMPLETADO o FALLO), la chaqueta se desactiva y el control vuelve a `_mantener_chaqueta()` de CicloState para la DescompresionFase.
- **`timeout_pulso` aplica a cada semi-pulso por separado**, no al ciclo de pulsos completo.

# Spec — Control de drenaje durante esperas de confirmación + debounce de válvula

**Fecha:** 2026-08-05

## Alcance

`CicloState._mantener_drenaje()` (enciende/apaga `agua_intercambiador` según `temp_drenaje` vs. `temp_segura_drenaje`) hoy solo corre en el paso 5 de `run()`, que se salta por completo mientras el ciclo está en `ESPERANDO_CONFIRMACION` — sin importar la causa (COMPLETADO limpio, FALLO, CANCELADO, emergencia). Esta spec:

1. Hace que `_mantener_drenaje()` corra en **todas** las esperas de confirmación, no solo durante `ProtocoloFallo`.
2. Agrega debounce simétrico de 3 lecturas consecutivas antes de cambiar el estado de la válvula, para evitar activaciones/desactivaciones por oscilaciones de `temp_drenaje` cerca del umbral.

**Fuera de alcance:** no se toca `_mantener_chaqueta()`, ni la lógica de `ProtocoloFallo` o `_mantener_valvula_reposo()` (presión de cámara), ni el resto del pipeline de fases. No se agrega un parámetro configurable para el número de lecturas — se usa una constante, igual que `_DEBOUNCE_LECTURAS` en `esterilizacion.py`.

---

## Decisiones de diseño

1. **Una sola llamada nueva, fuera del `if/else` de `_resultado_pendiente`.** En `run()`, dentro del bloque `if self._resultado_pendiente is not None:`, se agrega `self._mantener_drenaje()` antes de la rama que distingue COMPLETADO de FALLO/CANCELADO/emergencia. Así corre en ambos casos con un solo punto de cambio.

2. **Debounce simétrico con dos contadores independientes**, mismo patrón que `esterilizacion.py` (`_contador_temp_alta`, etc.): un contador para lecturas por encima del umbral y otro para lecturas en o por debajo. Cada tick, uno se incrementa y el otro se resetea a 0 según la lectura actual. La válvula solo cambia de estado cuando el contador correspondiente alcanza `_DEBOUNCE_LECTURAS_DRENAJE = 3`. Mientras ningún contador llegue a 3 (incluyendo oscilaciones que resetean el contador antes de llegar), la válvula se mantiene en su último estado confirmado — no hay acción ni log.

3. **Sensor ausente no toca los contadores.** Igual que hoy, si `temp_drenaje` es `None` la función retorna de inmediato. Los contadores quedan en su valor previo (no se resetean) — una caída breve del sensor no descarta el progreso de debounce ya acumulado.

4. **La alarma `TEMP_DRENAJE_ALTA` se reporta/limpia junto con el cambio de válvula**, no en cada tick — se mueve dentro de las mismas ramas que llaman a `agua_intercambiador_on()`/`_off()`, disparadas solo cuando el contador correspondiente cruza el umbral.

---

## Arquitectura

### `ciclo.py` — constante de módulo

```python
_DEBOUNCE_LECTURAS_DRENAJE = 3
```

### `CicloState.__init__` / `reset()`

Agregar junto a los demás contadores de estado del ciclo:

```python
self._contador_drenaje_alta = 0
self._contador_drenaje_baja = 0
```

(reseteados a 0 en `reset()`, igual que el resto del estado del ciclo)

### `_mantener_drenaje()` (reemplaza la versión actual)

```python
def _mantener_drenaje(self):
    """Mantiene la temperatura de drenaje durante todo el ciclo, incluyendo
    las esperas de confirmación (COMPLETADO/FALLO/CANCELADO/emergencia).
    Debounce simétrico de _DEBOUNCE_LECTURAS_DRENAJE lecturas antes de
    cambiar el estado de la válvula, para evitar activarla por oscilaciones
    de temp_drenaje cerca del umbral."""
    temp = self.estado.sensores_temp.get("temp_drenaje")
    if temp is None:
        return
    temp_segura = self.config.get("temp_segura_drenaje")
    if temp_segura is None:
        return

    if temp > temp_segura:
        self._contador_drenaje_alta += 1
        self._contador_drenaje_baja = 0
    else:
        self._contador_drenaje_baja += 1
        self._contador_drenaje_alta = 0

    if self._contador_drenaje_alta >= _DEBOUNCE_LECTURAS_DRENAJE:
        self.set_do.agua_intercambiador_on()
        self.alarm_manager.report(Alarm(
            alarm_id="TEMP_DRENAJE_ALTA",
            alarm_type=AlarmType.ALERTA,
            source_state="CICLO",
            description="Temperatura de drenaje alta: enfriando.",
            recoverable=True,
            blocks_operation=False,
        ))
    elif self._contador_drenaje_baja >= _DEBOUNCE_LECTURAS_DRENAJE:
        self.set_do.agua_intercambiador_off()
        self.alarm_manager.clear("TEMP_DRENAJE_ALTA")
```

### `run()` — punto de llamada en la espera de confirmación

```python
if self._resultado_pendiente is not None:
    if self.estado.get_flag("CICLO_CONFIRMADO"):
        ...
        return resultado_final

    self._mantener_drenaje()
    if self._resultado_pendiente == CicloResultado.COMPLETADO:
        self._mantener_valvula_reposo()
    else:
        self._protocolo.update()
    return CicloResultado.ESPERANDO_CONFIRMACION
```

(El paso 5 del flujo normal, `self._mantener_drenaje()` en la línea ~330, no cambia — sigue llamándose ahí también.)

---

## Tests

**`tests/test_ciclo_drenaje.py`** — se reescribe para el debounce:

- `test_temp_alta_no_activa_agua_antes_de_3_lecturas`: 1 y 2 llamadas con `temp > temp_segura` → `agua_intercambiador_on` no llamado.
- `test_temp_alta_activa_agua_al_llegar_a_3_lecturas`: 3 llamadas consecutivas → `agua_intercambiador_on` llamado (una vez, en la 3ra) + alarma reportada.
- `test_temp_segura_apaga_agua_al_llegar_a_3_lecturas`: partiendo de contador_alta ya en 3 (válvula encendida), 3 llamadas con `temp <= temp_segura` → `agua_intercambiador_off` + alarma limpiada.
- `test_oscilacion_resetea_contador_sin_falso_positivo`: alta, alta, baja, alta, alta → nunca llega a 3 consecutivas → ninguna acción.
- `test_temp_drenaje_ausente_no_hace_nada` (existente) — sin cambios, pero verificar que tampoco resetea contadores (llamar una vez con temp ausente entre dos lecturas altas no reinicia el conteo).
- `test_se_llama_en_run_sin_importar_la_fase_activa` (existente) — ajustar para llamar `ciclo.run()` 3 veces consecutivas antes de aserir `agua_intercambiador_on`.

**Nuevo: `tests/test_ciclo_drenaje_espera_confirmacion.py`**
- `_resultado_pendiente = COMPLETADO`, 3 ticks de `run()` con `temp_drenaje > temp_segura` → `agua_intercambiador_on` llamado (además de `_mantener_valvula_reposo` corriendo normalmente).
- `_resultado_pendiente = FALLO`, 3 ticks de `run()` con `temp_drenaje > temp_segura` → `agua_intercambiador_on` llamado (además de `_protocolo.update()` corriendo normalmente).
- `_resultado_pendiente = CANCELADO`, mismo caso → mismo resultado.

---

## Archivos afectados

| Archivo | Acción |
|---------|--------|
| `src/autoclave/state_machine/states/ciclo.py` | Modificar — constante `_DEBOUNCE_LECTURAS_DRENAJE`, contadores en `__init__`/`reset()`, reescribir `_mantener_drenaje()`, llamada nueva en `run()` |
| `tests/test_ciclo_drenaje.py` | Modificar — reescribir para debounce |
| `tests/test_ciclo_drenaje_espera_confirmacion.py` | Crear |

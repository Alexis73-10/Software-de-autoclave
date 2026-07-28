# Spec — Enfriamiento de drenaje activo durante CICLO (no bloqueante)

**Fecha:** 2026-07-23

## Alcance

Hoy el enfriamiento de drenaje (`agua_intercambiador` según `temp_drenaje` vs.
`temp_segura_drenaje`) solo se gestiona en `PREPARACION`
(`preparacion.py::verificar_temperatura_drenaje`, bloqueante — paso 5 del
secuenciador) y `PREPARADO` (`preparado.py::mantener_drenaje`, bloqueante para
`esta_preparado()`). Durante `CICLO`, nadie vigila `temp_drenaje`: la única
vía por la que `agua_intercambiador` se activa en esa ventana es como efecto
secundario de la bomba de vacío (`vacio_camara_on()`/`vacio_camara_off()` en
`set_io.py`, usado por `PrevacioFase` y `SecadoFase`), que no tiene relación
con la temperatura del drenaje.

Este cambio agrega vigilancia continua de `temp_drenaje` durante todo
`CICLO`, igual que ya existe para la chaqueta (`_mantener_chaqueta`), y **no
bloqueante**: solo gestiona la válvula y reporta una alarma informativa, sin
afectar el resultado del ciclo ni el avance de fases.

**Fuera de alcance:** no se toca `preparacion.py` ni `preparado.py` (su
lógica de drenaje ya es correcta y bloqueante por diseño ahí). No se agrega
ningún mecanismo de coordinación/latch entre el nuevo control por
temperatura y el control existente ligado a la bomba de vacío — se resuelve
con el mismo patrón "última llamada en el tick gana" que ya usa el resto del
proyecto (ver Decisión 2).

## Decisiones de diseño

1. **Limpieza en `prevacio.py`**: se eliminan las llamadas directas a
   `self.set_do.agua_intercambiador_on()` (líneas 131 y 147, dentro de
   `VACIO_BAJO`/`HOLD_BAJO`) y `self.set_do.agua_intercambiador_off()`
   (línea 240, dentro de `_apagar_vacio()`). Son redundantes:
   `vacio_camara_on()`/`vacio_camara_off()` (llamadas en las mismas líneas
   inmediatamente después/antes) ya activan/desactivan `agua_intercambiador`
   internamente en `set_io.py`. El usuario confirmó que ese acople bomba↔agua
   de intercambiador debe permanecer intacto siempre (también en `SecadoFase`,
   que usa el mismo mecanismo) — ayuda a bajar la temperatura del fluido que
   entra a la bomba de vacío. Esta limpieza no cambia ningún comportamiento
   observable; solo elimina una duplicación de código.

2. **Nuevo `CicloState._mantener_drenaje()`**, mismo patrón que
   `_mantener_chaqueta()`: lee `temp_drenaje` y `temp_segura_drenaje`
   (config), enciende `agua_intercambiador` si `temp_drenaje > temp_segura`,
   lo apaga si no. Se llama **en cada tick de `CICLO`, sin excluir ninguna
   fase** (a diferencia de `_mantener_chaqueta`, que excluye `SecadoFase`) —
   confirmado explícitamente por el usuario, incluyendo `PRE_VACIO`.

   Esto significa que durante `PRE_VACIO`/`SecadoFase`, en el mismo tick,
   `_mantener_drenaje()` corre primero (paso 5 de `run()`, junto a
   `_mantener_chaqueta()`) y la fase activa corre después (paso 7): si esa
   fase llama `vacio_camara_on()`/`vacio_camara_off()` ese mismo tick (lo que
   ocurre en la mayoría de sus pasos activos), su decisión —ligada a la
   bomba— prevalece para ese tick. `_mantener_drenaje()` tiene efecto pleno
   en el resto de fases y en las ventanas de `PRE_VACIO`/`SECADO` donde la
   fase no toca esa salida en ese tick. Mismo patrón "última llamada gana"
   que ya coexiste en el proyecto (p. ej. `vapor_camara` entre fases).

3. **No bloqueante**: se reporta `Alarm(alarm_id="TEMP_DRENAJE_ALTA",
   alarm_type=AlarmType.ALERTA, source_state="CICLO", blocks_operation=False,
   recoverable=True)` cuando `temp_drenaje > temp_segura`, y se limpia
   (`alarm_manager.clear("TEMP_DRENAJE_ALTA")`) cuando vuelve a rango seguro.
   Mismo `alarm_id` ya usado por `preparado.py`/`preparacion.py` (alarmas
   duplicadas por id se descartan vía `AlarmManager.report`, no hay
   conflicto). No se agrega temporizador de estabilidad (a diferencia de
   `preparado.py`'s `generar_alarma_temporizada`) — se reporta de inmediato,
   igual que el patrón ya usado para `SUMINISTRO_VAPOR` en
   `_mantener_chaqueta`.

## Arquitectura

### `prevacio.py` — quitar 3 líneas

```python
# VACIO_BAJO (antes línea 131)
presion_baja = self.cycle.get_param("prevacio", f"presion_baja_pulso_{tipo}") or 15
self.set_do.bomba_vacio_on()
self.set_do.vacio_camara_on()
```

```python
# HOLD_BAJO (antes línea 147)
tiempo_hold = self.cycle.get_param("prevacio", f"tiempo_adicional_bajo_{tipo}") or 0
self.set_do.bomba_vacio_on()
self.set_do.vacio_camara_on()
```

```python
# _apagar_vacio() (antes línea 240)
def _apagar_vacio(self):
    self.set_do.bomba_vacio_off()
    self.set_do.vacio_camara_off()
```

### `ciclo.py` — nuevo método

```python
def _mantener_drenaje(self):
    """Mantiene la temperatura de drenaje durante todas las fases del
    ciclo, sin bloquear el flujo del ciclo (alarma informativa)."""
    temp = self.estado.sensores_temp.get("temp_drenaje")
    if temp is None:
        return
    temp_segura = self.config.get("temp_segura_drenaje")
    if temp_segura is None:
        return

    if temp > temp_segura:
        self.set_do.agua_intercambiador_on()
        self.alarm_manager.report(Alarm(
            alarm_id="TEMP_DRENAJE_ALTA",
            alarm_type=AlarmType.ALERTA,
            source_state="CICLO",
            description="Temperatura de drenaje alta: enfriando.",
            recoverable=True,
            blocks_operation=False,
        ))
    else:
        self.set_do.agua_intercambiador_off()
        self.alarm_manager.clear("TEMP_DRENAJE_ALTA")
```

Se llama junto a `_mantener_chaqueta()` en el paso 5 de `run()`:

```python
        # ── 5. Mantener presión de chaqueta y temperatura de drenaje ──
        self._mantener_chaqueta()
        self._mantener_drenaje()
```

## Tests

**`tests/test_ciclo_drenaje.py`** (nuevo, mismo patrón que
`tests/test_ciclo_chaqueta.py`):

- Temp por encima de `temp_segura_drenaje` → `agua_intercambiador_on()`
  llamado, se reporta `Alarm` con `id="TEMP_DRENAJE_ALTA"` y
  `blocks_operation=False`.
- Temp por debajo/igual a `temp_segura_drenaje` → `agua_intercambiador_off()`
  llamado, `alarm_manager.clear("TEMP_DRENAJE_ALTA")` llamado.
- `temp_drenaje` ausente (`None`) → no llama ninguna salida, no reporta ni
  limpia alarma (retorno temprano, igual que `_mantener_chaqueta` con
  `pres_chaqueta`).
- `_mantener_drenaje()` se invoca en `run()` sin importar la fase activa
  (a diferencia de `_mantener_chaqueta`, que se salta durante `SecadoFase`) —
  test que fija `self._fase_idx` en el índice de `PrevacioFase` (o cualquier
  otra) y confirma que igual se llama.

**`tests/test_prevacio_caps.py`**: no requiere cambios — ningún test llega a
`VACIO_BAJO`/`HOLD_BAJO`/`_apagar_vacio()` (todos los conteos de pulso están
en 0 en esos tests). Correrlos igual como verificación de no-regresión.

No existe un archivo de test dedicado a la máquina de pasos completa de
`PrevacioFase` (`VACIO_BAJO`/`HOLD_BAJO`/etc.) hoy — no se crea uno como
parte de este cambio (fuera de alcance; el cambio en `prevacio.py` es
puramente una eliminación de líneas redundantes sin efecto observable,
cubierto indirectamente por cualquier test que ya ejercite `vacio_camara_on`/
`vacio_camara_off` en esos pasos, si existiera).

## Archivos afectados

| Archivo | Acción |
|---------|--------|
| `src/autoclave/state_machine/cycle_phases/prevacio.py` | Modificar — quitar 3 llamadas redundantes a `agua_intercambiador_on/off` |
| `src/autoclave/state_machine/states/ciclo.py` | Modificar — nuevo `_mantener_drenaje()`, llamada en `run()` paso 5 |
| `tests/test_ciclo_drenaje.py` | Crear |

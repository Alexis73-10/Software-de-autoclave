# Spec — Apertura automática de puerta al finalizar el ciclo

**Fecha:** 2026-08-06

## Alcance

La sección `finalizacion` de cada perfil JSON de ciclo (`src/autoclave/cycles/{factory,user}/*.json`) ya define 4 parámetros que hoy no lee ningún código — quedaron reservados desde el spec de `params_ciclo` (2026-06-22), que explícitamente dejó la lógica de la state machine fuera de su alcance:

- `tiempo_espera_apertura` (seg) — espera fija antes de habilitar la apertura.
- `temp_max_apertura` (°C) — tope de temperatura de cámara para permitir la apertura (propio del ciclo).
- `timeout_temperatura` (min) — máximo a esperar a que la cámara baje a `temp_max_apertura` antes de avisar por alarma.
- `apertura_automatica` (bool) — si `true`, el equipo debe abrir la puerta de descarga solo, sin esperar al operador.

Hoy, al terminar el ciclo, `CicloState` entra en `ESPERANDO_CONFIRMACION` y se queda ahí hasta que el operador presiona CONFIRMAR (`POST /cycle/acknowledge` → flag `CICLO_CONFIRMADO`). Confirmar **no abre ninguna puerta** — es una acción completamente independiente de abrir la puerta de descarga (`POST /doors/{door_name}/open` → `ServicioPuertas.request_open`). Esta spec implementa los 4 parámetros para que, cuando `apertura_automatica=true` y el ciclo termina en `COMPLETADO`, el sistema abra la puerta de descarga y confirme el ciclo automáticamente, sin intervención del operador.

**Fuera de alcance:**
- No cambia el flujo manual existente (botón CONFIRMAR, botón de abrir puerta) cuando `apertura_automatica=false` — sigue exactamente igual.
- No aplica a `FALLO`, `CANCELADO` ni emergencia — solo a `COMPLETADO` (cierre exitoso del ciclo).
- No toca la validación de seguridad física de `ServicioPuertas` (`_can_open_physical`: presión atmosférica, temperatura tope global, interlock de la puerta contraria) — se reutiliza tal cual.
- No corrige la inconsistencia entre `finalizacion.temp_max_apertura` (por ciclo) y `temp_max_apertura` global salvo para esta ruta automática nueva — el botón CONFIRMAR de la UI sigue usando el valor global, sin cambios.

---

## Decisiones de diseño

1. **Aplica a equipos de 1 y 2 puertas.** La puerta de descarga es `"Puerta 2"` si el equipo la tiene (`"Puerta 2" in door_service.doors`), si no `"Puerta 1"` (equipo de una sola puerta, donde carga y descarga son la misma).

2. **Secuencia temporal de tres tramos**, evaluada solo cuando `_resultado_pendiente == COMPLETADO` y `apertura_automatica` es `true`:
   - **Espera fija:** desde que se entra a `ESPERANDO_CONFIRMACION`, no se intenta nada durante `tiempo_espera_apertura` segundos.
   - **Espera de temperatura:** pasada la espera fija, cada tick compara `temp_camara` contra `finalizacion.temp_max_apertura` (por ciclo). Mientras `temp_camara > temp_max_apertura`, sigue esperando.
   - **Aviso de timeout (no bloqueante):** si la espera de temperatura supera `timeout_temperatura` minutos, se reporta una alarma `ALERTA` de una sola vez (no se repite en cada tick) como aviso al operador. Después del aviso, el sistema **sigue esperando en automático indefinidamente** — no hay límite adicional ni caída a modo manual; en cuanto la temperatura baje, continúa la secuencia normal.

3. **Apertura + confirmación en un solo paso.** Cumplida la condición de temperatura, se llama `door_service.request_open(puerta_descarga)`:
   - Si devuelve `(True, "")`: se limpia la alarma de timeout si estaba activa y se pone `estado.set_flag("CICLO_CONFIRMADO", True)`. El siguiente tick de `run()` toma el camino ya existente en el paso 0 (`_resultado_pendiente is not None` + `CICLO_CONFIRMADO`) y transiciona igual que una confirmación manual — sin duplicar esa lógica.
   - Si devuelve `(False, motivo)` (p.ej. la puerta contraria no está cerrada, o presión fuera de rango atmosférico): no se hace nada especial, se reintenta en el siguiente tick. No se agrega una alarma nueva para este caso — la denegación ya queda en el log de `ServicioPuertas` (`logger.warning`), y son condiciones transitorias que la propia validación física ya cubre.

4. **`door_service` inyectado, opcional.** `CicloState` no tiene hoy acceso a `ServicioPuertas` — solo a `estado`, `set_do`, `cycle`, `config`, `alarm_manager`, `cap`. Se agrega como parámetro opcional (`door_service=None`) en `CicloState.__init__` y se propaga igual en `StateMachine.__init__`. Si es `None` (p.ej. algún test que construye `CicloState` directo sin pasarlo), `_mantener_apertura_automatica()` no hace nada — se preserva el comportamiento actual sin romper nada.

---

## Arquitectura

### `ciclo.py` — nuevos atributos de instancia

`__init__` gana un parámetro opcional al final, sin tocar el orden de los existentes:

```python
def __init__(self, estado, set_do, cycle, config, alarm_manager, cap=None, door_service=None):
```

En `__init__` y `reset()`, junto a los demás contadores de estado del ciclo:

```python
self.door_service = door_service           # solo en __init__, no se resetea
self._apertura_auto_t_inicio = None        # time.time() del primer tick en espera
self._apertura_auto_alarmado = False       # evita repetir la alarma de timeout
```

(`_apertura_auto_t_inicio` y `_apertura_auto_alarmado` sí se reinician a `None`/`False` en `reset()`, igual que `_resultado_pendiente`.)

### `_mantener_apertura_automatica()` (nuevo método)

```python
def _mantener_apertura_automatica(self):
    """Si finalizacion.apertura_automatica está activo, abre la puerta de
    descarga y confirma el ciclo sin esperar al operador. Solo corre
    mientras _resultado_pendiente == COMPLETADO. Secuencia: espera fija
    (tiempo_espera_apertura) → espera a que temp_camara baje a
    temp_max_apertura (avisando por alarma no bloqueante si tarda más de
    timeout_temperatura, sin dejar de esperar) → abrir puerta + confirmar."""
    if self.door_service is None:
        return
    if not self.cycle.get_param("finalizacion", "apertura_automatica", default=False):
        return

    if self._apertura_auto_t_inicio is None:
        self._apertura_auto_t_inicio = time.time()

    tiempo_espera = self.cycle.get_param("finalizacion", "tiempo_espera_apertura", default=60)
    elapsed = time.time() - self._apertura_auto_t_inicio
    if elapsed < tiempo_espera:
        return

    temp = self.estado.sensores_temp.get("temp_camara")
    if temp is None:
        return

    temp_max = self.cycle.get_param("finalizacion", "temp_max_apertura", default=80.0)
    if temp > temp_max:
        timeout_seg = self.cycle.get_param("finalizacion", "timeout_temperatura", default=30) * 60
        if not self._apertura_auto_alarmado and (elapsed - tiempo_espera) > timeout_seg:
            self._apertura_auto_alarmado = True
            self.alarm_manager.report(Alarm(
                alarm_id="TIMEOUT_APERTURA_AUTOMATICA",
                alarm_type=AlarmType.ALERTA,
                source_state="CICLO",
                description="Apertura automática: la cámara tarda más de lo esperado en enfriar.",
                recoverable=True,
                blocks_operation=False,
            ))
        return

    puerta = "Puerta 2" if "Puerta 2" in self.door_service.doors else "Puerta 1"
    ok, _motivo = self.door_service.request_open(puerta)
    if ok:
        if self._apertura_auto_alarmado:
            self.alarm_manager.clear("TIMEOUT_APERTURA_AUTOMATICA")
        self.estado.set_flag("CICLO_CONFIRMADO", True)
```

### `run()` — punto de llamada

En el bloque `if self._resultado_pendiente is not None:`, junto a `_mantener_valvula_reposo()`:

```python
if self._resultado_pendiente == CicloResultado.COMPLETADO:
    self._mantener_valvula_reposo()
    self._mantener_apertura_automatica()
else:
    self._protocolo.update()
self._mantener_drenaje()
return CicloResultado.ESPERANDO_CONFIRMACION
```

`_mantener_apertura_automatica()` corre después de `_mantener_valvula_reposo()` para dejar la válvula/aire atmosférico en el estado correcto antes de decidir si se abre la puerta — mismo orden lógico que la nota ya existente sobre `_mantener_drenaje()` corriendo al final.

### `state_machine.py`

```python
def __init__(self, io, estado, set_do, cycle, config, cap=None, door_service=None):
    ...
    self.ciclo = CicloState(estado, set_do, cycle, config, self.alarm_manager, cap, door_service)
```

### `control_loop.py`

Los dos sitios donde se construye `StateMachine` (constructor inicial y el que corre al cambiar de ciclo) pasan `door_service=self.door_service`.

### Import nuevo en `ciclo.py`

```python
import time
```
(ya se usa `time.time()` como patrón estándar de timers en `esterilizacion.py`, `descompresion.py`, `calentamiento.py`, `prevacio.py` — no hay una utilidad de timer compartida, cada fase mantiene su propio `_t_inicio`.)

---

## Tests

**Nuevo: `tests/test_ciclo_apertura_automatica.py`**

- `test_apertura_automatica_false_no_hace_nada`: `apertura_automatica=False` (o ausente) → `door_service.request_open` nunca se llama, `CICLO_CONFIRMADO` nunca se pone, sin importar cuántos ticks pasen.
- `test_door_service_none_no_rompe`: `CicloState` construido con `door_service=None` y `apertura_automatica=True` → `run()` no lanza excepción, se comporta como si estuviera desactivado.
- `test_espera_fija_antes_de_intentar_abrir`: `apertura_automatica=True`, `tiempo_espera_apertura=60`, temperatura ya por debajo de `temp_max_apertura` desde el primer tick → `request_open` no se llama hasta que `elapsed >= 60` (mockear `time.time()`).
- `test_abre_puerta_2_si_existe`: `door_service.doors` incluye `"Puerta 2"` → se llama `request_open("Puerta 2")`.
- `test_abre_puerta_1_si_es_equipo_de_una_puerta`: `door_service.doors` solo tiene `"Puerta 1"` → se llama `request_open("Puerta 1")`.
- `test_espera_temperatura_antes_de_abrir`: pasada la espera fija, `temp_camara > temp_max_apertura` → `request_open` no se llama; al bajar la temperatura en un tick posterior, sí se llama.
- `test_confirma_solo_al_abrir_con_exito`: `request_open` devuelve `(True, "")` → `estado.get_flag("CICLO_CONFIRMADO")` queda en `True` tras el tick.
- `test_no_confirma_si_abrir_falla`: `request_open` devuelve `(False, "motivo")` → `CICLO_CONFIRMADO` no se activa, no se lanza alarma nueva, y en el siguiente tick se reintenta (se vuelve a llamar `request_open`).
- `test_alarma_timeout_temperatura_una_sola_vez`: temperatura se mantiene alta más allá de `tiempo_espera_apertura + timeout_temperatura*60` durante varios ticks → `alarm_manager.report` se llama una sola vez con `alarm_id="TIMEOUT_APERTURA_AUTOMATICA"`, no en cada tick.
- `test_sigue_esperando_tras_alarma_timeout_hasta_que_baja_temp`: tras la alarma de timeout, la temperatura eventualmente baja → se abre la puerta y se confirma igual, y se limpia la alarma (`alarm_manager.clear` llamado con ese `alarm_id`).
- `test_sensor_ausente_no_avanza_ni_rompe`: `temp_camara is None` en cualquier punto → `run()` no lanza excepción, no se intenta abrir, no se resetea `_apertura_auto_t_inicio`.
- `test_no_aplica_a_fallo_ni_cancelado`: `_resultado_pendiente = FALLO` (o `CANCELADO`) con `apertura_automatica=True` → `_mantener_apertura_automatica()` nunca se invoca, `request_open` nunca se llama.
- `test_reset_reinicia_temporizador`: tras un ciclo completo con `_apertura_auto_t_inicio` ya seteado, llamar `reset()` → vuelve a `None`, y un `apertura_automatica=False` seguido de `True` en el mismo objeto no arrastra estado del ciclo anterior.

**Modificar `tests/test_control_loop.py` (o el archivo que construya `StateMachine`/`ControlLoop` en tests)**: verificar que `door_service` llega hasta `CicloState` — al menos un test de integración liviano que construya `ControlLoop` con un `door_service` mock y confirme `control_loop.state_machine.ciclo.door_service is door_service`.

---

## Archivos afectados

| Archivo | Acción |
|---------|--------|
| `src/autoclave/state_machine/states/ciclo.py` | Modificar — import `time`, parámetro `door_service` en `__init__`/`reset()`, nuevo método `_mantener_apertura_automatica()`, llamada nueva en `run()` |
| `src/autoclave/state_machine/state_machine.py` | Modificar — parámetro `door_service=None` propagado a `CicloState` |
| `src/autoclave/services/domain/loop/control_loop.py` | Modificar — pasar `door_service=self.door_service` en las dos construcciones de `StateMachine` |
| `tests/test_ciclo_apertura_automatica.py` | Crear |
| `tests/test_control_loop.py` (o equivalente) | Modificar — test de wiring de `door_service` |

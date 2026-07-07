# Impresión de eventos de conectividad (tarjeta y backend)

## Problema

La impresora ya emite tickets de ciclo en tiempo real y un ticket de arranque
(`RealtimePrinter`, `startup_ticket.py`). Pero si durante la operación normal
(no solo al arrancar) la tarjeta ESP32 se desconecta y luego reconecta, o el
proceso backend deja de responder y luego se recupera, nada se imprime — el
único rastro es un log y, para la tarjeta, la alarma `NO_HAY_CONEXION` en la
UI. El operador no tiene un registro en papel de estos eventos.

Se requiere que cualquier cambio de estado de conectividad, tanto de la
tarjeta como del backend, durante toda la sesión (no solo en el arranque),
se imprima automáticamente — incluyendo el caso de que algo falle en el
arranque y luego se recupere.

## Alcance

Cubre únicamente eventos de conectividad:
- Tarjeta (placa ESP32, enlace serial): conectada ↔ desconectada.
- Backend (proceso FastAPI de este software): responde ↔ no responde a la UI.

Explícitamente fuera de alcance: cualquier otra alarma del sistema (puertas,
sensores, paro de emergencia, etc.) — esas no generan impresión como parte de
este trabajo.

## Arquitectura

Dos observadores independientes, cada uno viviendo en el proceso que
efectivamente puede detectar la falla correspondiente:

### 1. Tarjeta — observado desde el proceso backend

`ControlLoop.run()` (`src/autoclave/services/domain/loop/control_loop.py:60-78`)
ya contiene lógica de flanco sobre `link.is_connected()`:

```python
connected = self.link.is_connected()
if not connected and self.link_was_connected:
    self.alarm_manager.report(Alarm(alarm_id="NO_HAY_CONEXION", ...))
elif connected and not self.link_was_connected:
    self.alarm_manager.clear("NO_HAY_CONEXION")
self.link_was_connected = connected
```

Se añade, en cada una de las dos ramas, una llamada a
`self.realtime_printer.enqueue(...)` con el ticket correspondiente
(desconexión o reconexión), sin alterar la lógica de alarma existente.

`self.link_was_connected` ya arranca en `True`, por lo que si la tarjeta no
está conectada en el primer ciclo del loop, el evento de desconexión se
imprime de inmediato — cubriendo el caso "algo falla en el arranque" sin
lógica adicional.

**Cambios:**
- `ControlLoop.__init__` recibe un nuevo parámetro `realtime_printer=None`.
- `BackendContext` (`context.py:83-95`) pasa `realtime_printer=self.realtime_printer`
  al construir `ControlLoop` (la instancia ya existe en la línea 73).
- Si `realtime_printer` es `None` (p. ej. en tests que no lo necesiten), no se
  imprime nada — no debe romper nada existente.

### 2. Backend — observado desde el proceso UI

El backend es un proceso HTTP separado (`localhost:8000`). Si el proceso
backend se cae o se cuelga, nada dentro de él puede avisar de su propia
caída — solo quien lo está consultando por HTTP lo nota.

`UIServiceBackend._loop()` (`src/autoclave/ui/service_ui/ui_service_backend.py:38-45`)
ya sondea `/status` cada 200 ms en un hilo de fondo y actualiza
`self.connected` en `_fetch_status()` (línea 47-57). Se añade seguimiento de
flanco sobre ese mismo flag:

```python
self._was_connected = True   # backend ya confirmado vivo antes de este punto
...
def _fetch_status(self):
    try:
        cache = self.backend.get_status()
        with self._lock:
            self._cache = cache
            self.connected = True
    except Exception as e:
        with self._lock:
            self.connected = False
        logger.warning(...)
    finally:
        if self.connected != self._was_connected:
            self._printer.enqueue(format_connectivity_ticket("BACKEND", self.connected, datetime.now()))
            self._was_connected = self.connected
```

`_was_connected` arranca en `True` (no en `False`) porque `main.py:94`
(`wait_for_backend`) ya bloquea hasta confirmar que el backend responde
*antes* de instanciar `UIServiceBackend` — así que en el arranque normal no
hay falso positivo. Si el backend PC 2 (`main.py:96-99`) arranca sin backend
disponible, o si el backend se cae más tarde, el primer fallo dispara el
aviso de inmediato, igual que en el caso de la tarjeta.

**Cambios:**
- `UIServiceBackend.__init__` crea su propia instancia de `RealtimePrinter`
  (mismo patrón que usa `BackendContext` para el backend). No requiere tocar
  `main.py`.
- `UIServiceBackend.stop()` ya se llama antes de terminar el proceso backend
  en `on_close()` (`main.py:118-122`), así que el cierre normal de la
  aplicación no dispara un falso "BACKEND SIN RESPUESTA" — el hilo de
  polling se detiene antes de que el backend sea terminado.

### Formato del ticket

Nuevo módulo `src/autoclave/devices/printer/connectivity_ticket.py`, con una
función `format_connectivity_ticket(subsystem: str, ok: bool, when: datetime) -> str`,
reutilizando el estilo de caja fijo (ancho 48, `=`/`-`) ya usado en
`ticket_formatter.py` y `startup_ticket.py`:

```
================================================
       ESPECIFIKA -- AUTOCLAVE MX-500
================================================
 TARJETA: DESCONECTADA
 2026-07-07 14:32:10
================================================
```

Mapeo de mensajes:
- `subsystem="TARJETA"`, `ok=False` → `"TARJETA: DESCONECTADA"`
- `subsystem="TARJETA"`, `ok=True`  → `"TARJETA: RECONECTADA"`
- `subsystem="BACKEND"`, `ok=False` → `"BACKEND: SIN RESPUESTA"`
- `subsystem="BACKEND"`, `ok=True`  → `"BACKEND: RECONECTADO"`

## Manejo de errores

- `RealtimePrinter.enqueue()` ya nunca bloquea ni lanza excepción (encola y
  retorna); es seguro llamarlo desde el loop de control (backend, cada
  0.5 s) y desde el hilo de polling de la UI (cada 0.2 s).
- Si la impresora física no está disponible, `print_raw` registra un warning
  y descarta la línea — comportamiento ya existente, sin cambios. Los
  tickets de conectividad son best-effort, igual que los de ciclo.
- No hay debounce adicional más allá del que ya existe en cada capa: el
  enlace serial ya tiene `DATA_TIMEOUT=3.0s` antes de considerar la tarjeta
  desconectada (`serial_link.py`), y las peticiones HTTP de la UI ya tienen
  `timeout=0.8s` (`backend_client.py`). No se introduce lógica de reintentos
  o umbrales nuevos — se reutiliza el mismo estado de conectividad que la
  UI ya usa para todo lo demás (evita divergencia entre lo que ve el
  operador en pantalla y lo que se imprime).

## Testing

- Backend: test sobre `ControlLoop` (mock de `link.is_connected()` alternando
  `True`/`False`) verificando que `realtime_printer.enqueue` se llama con el
  texto esperado en cada transición, y que NO se llama si el estado no
  cambió entre iteraciones. Reutiliza patrones de mocking ya presentes en
  `tests/test_control_loop_test_mode.py`.
- UI: test sobre `UIServiceBackend` con un `backend_client` falso que
  alterna entre lanzar excepción y responder OK, verificando llamadas a
  `enqueue` solo en las transiciones. Reutiliza el patrón de
  `tests/test_realtime_printer.py` (monkeypatch de `print_raw`, `queue.join()`
  para sincronizar).
- Verificación manual: desconectar/reconectar físicamente el cable USB de la
  tarjeta durante una sesión activa y confirmar dos tickets impresos; matar
  y reiniciar el proceso backend (`autoclave.backend.main`) manualmente y
  confirmar los tickets correspondientes desde el lado UI.

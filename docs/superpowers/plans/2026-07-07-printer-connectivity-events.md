# Impresión de eventos de conectividad (tarjeta/backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Imprimir un ticket automáticamente cada vez que cambie el estado de conectividad de la tarjeta (ESP32) o del backend, durante toda la sesión, incluyendo el caso de que algo falle en el arranque y luego se recupere.

**Architecture:** Dos observadores de flanco independientes, cada uno en el proceso donde puede detectar la falla: `ControlLoop` (proceso backend) ya rastrea conexión de la tarjeta vía `link.is_connected()` y ahora también imprime; `UIServiceBackend` (proceso UI) ya sondea `/status` cada 200ms y ahora también imprime cuando deja/vuelve a responder. Ambos reutilizan una función de formato compartida y el patrón `RealtimePrinter.enqueue()` ya existente (no bloqueante, no lanza excepciones).

**Tech Stack:** Python 3.14, pytest, unittest.mock (MagicMock/patch), threading.

## Global Constraints

- Ancho de ticket fijo `_W = 48`, separador `"="*_W`, mismo estilo que `ticket_formatter.py` y `startup_ticket.py` — no introducir un formato distinto.
- Textos exactos: `"TARJETA: DESCONECTADA"`, `"TARJETA: RECONECTADA"`, `"BACKEND: SIN RESPUESTA"`, `"BACKEND: RECONECTADO"` — copiados literalmente del spec, no parafrasear.
- Alcance limitado a conectividad de TARJETA y BACKEND. No enganchar otras alarmas del sistema (puertas, sensores, paro de emergencia) a este mecanismo.
- No agregar debounce/reintentos nuevos — reutilizar los timeouts ya existentes (`DATA_TIMEOUT=3.0s` en `serial_link.py`, `timeout=0.8s` en `backend_client.py`) y el mismo flag de conectividad que cada proceso ya mantiene.
- `RealtimePrinter.enqueue()` nunca debe bloquear ni lanzar excepción — preservar esa propiedad en todos los call sites nuevos.
- Estado inicial "primado" en `True` en ambos observadores (`ControlLoop.link_was_connected` ya es `True` por defecto; `UIServiceBackend._was_connected` debe inicializarse igual) para no imprimir falsos positivos en el arranque normal.

---

## Task 1: Función de formato del ticket de conectividad

**Files:**
- Create: `src/autoclave/devices/printer/connectivity_ticket.py`
- Test: `tests/test_connectivity_ticket.py`

**Interfaces:**
- Produces: `format_connectivity_ticket(subsystem: str, ok: bool, when: datetime) -> str`, donde `subsystem` es `"TARJETA"` o `"BACKEND"` y `ok` es `True` (conectado/responde) o `False` (desconectado/sin respuesta). Devuelve el texto completo del ticket, listo para pasar a `RealtimePrinter.enqueue()`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_connectivity_ticket.py`:

```python
from datetime import datetime

from autoclave.devices.printer.connectivity_ticket import format_connectivity_ticket


def test_tarjeta_desconectada():
    texto = format_connectivity_ticket("TARJETA", False, datetime(2026, 7, 7, 14, 32, 10))
    assert "TARJETA: DESCONECTADA" in texto
    assert "2026-07-07 14:32:10" in texto


def test_tarjeta_reconectada():
    texto = format_connectivity_ticket("TARJETA", True, datetime(2026, 7, 7, 14, 33, 0))
    assert "TARJETA: RECONECTADA" in texto


def test_backend_sin_respuesta():
    texto = format_connectivity_ticket("BACKEND", False, datetime(2026, 7, 7, 14, 34, 0))
    assert "BACKEND: SIN RESPUESTA" in texto


def test_backend_reconectado():
    texto = format_connectivity_ticket("BACKEND", True, datetime(2026, 7, 7, 14, 35, 0))
    assert "BACKEND: RECONECTADO" in texto


def test_ticket_usa_ancho_48_y_separador():
    texto = format_connectivity_ticket("TARJETA", False, datetime(2026, 7, 7, 14, 32, 10))
    lineas = texto.split("\n")
    assert lineas[0] == "=" * 48
    assert lineas[2] == "=" * 48
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `pytest tests/test_connectivity_ticket.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'autoclave.devices.printer.connectivity_ticket'`

- [ ] **Step 3: Implementar la función**

Crear `src/autoclave/devices/printer/connectivity_ticket.py`:

```python
from datetime import datetime

_W   = 48
_SEP = "=" * _W

_MENSAJES = {
    ("TARJETA", False): "TARJETA: DESCONECTADA",
    ("TARJETA", True):  "TARJETA: RECONECTADA",
    ("BACKEND", False): "BACKEND: SIN RESPUESTA",
    ("BACKEND", True):  "BACKEND: RECONECTADO",
}


def format_connectivity_ticket(subsystem: str, ok: bool, when: datetime) -> str:
    mensaje = _MENSAJES[(subsystem, ok)]
    lines = [
        _SEP,
        "ESPECIFIKA -- AUTOCLAVE".center(_W),
        _SEP,
        f" {mensaje}",
        f" {when.strftime('%Y-%m-%d %H:%M:%S')}",
        _SEP,
        "",
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `pytest tests/test_connectivity_ticket.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/autoclave/devices/printer/connectivity_ticket.py tests/test_connectivity_ticket.py
git commit -m "feat: agregar formato de ticket de conectividad tarjeta/backend"
```

---

## Task 2: `ControlLoop` imprime al cambiar la conexión de la tarjeta

**Files:**
- Modify: `src/autoclave/services/domain/loop/control_loop.py`
- Modify: `src/autoclave/backend/context.py`
- Test: `tests/test_control_loop_connectivity_ticket.py`

**Interfaces:**
- Consumes: `format_connectivity_ticket(subsystem: str, ok: bool, when: datetime) -> str` (Task 1).
- Consumes: `RealtimePrinter.enqueue(text: str) -> None` (ya existente en `src/autoclave/devices/printer/realtime_printer.py`).
- Produces: `ControlLoop.__init__` gana el parámetro opcional `realtime_printer=None`. Cuando no es `None`, `ControlLoop.run()` llama a `realtime_printer.enqueue(...)` en cada transición de `link.is_connected()`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_control_loop_connectivity_ticket.py`:

```python
from unittest.mock import MagicMock, patch


class _FakeEstado:
    def __init__(self):
        self._flags = {"PARO_EMERGENCIA": False, "FALLO_SUMINISTRO_ELECTRICO": False}
        self.sensores_di = {"paro_emergencia": 0, "suministro_electrico": 1}

    def get_machine_state(self):
        from autoclave.state_machine.machine.enum_global import GlobalState
        return GlobalState.PREPARACION

    def get_flag(self, name):
        return self._flags.get(name, False)

    def update(self, data):
        pass


def _make_loop(realtime_printer=None):
    from autoclave.services.domain.loop.control_loop import ControlLoop

    cycle_manager = MagicMock()
    cycle_manager.get_selected_cycle.return_value = MagicMock()

    with patch("autoclave.services.domain.loop.control_loop.StateMachine"):
        loop = ControlLoop(
            units=MagicMock(),
            door_service=MagicMock(),
            doors=[],
            estado=_FakeEstado(),
            link=MagicMock(),
            set_do=MagicMock(),
            alarm_manager=MagicMock(),
            cycle_manager=cycle_manager,
            config_manager=MagicMock(),
            realtime_printer=realtime_printer,
        )
    return loop


def _run_one_tick(loop, connected):
    loop.link.is_connected.return_value = connected
    loop._running.set()

    def _stop(*_a, **_k):
        loop._running.clear()

    with patch("time.sleep", side_effect=_stop):
        loop.run()


def test_desconexion_imprime_ticket():
    printer = MagicMock()
    loop = _make_loop(realtime_printer=printer)
    assert loop.link_was_connected is True  # estado primado

    _run_one_tick(loop, connected=False)

    printer.enqueue.assert_called_once()
    texto = printer.enqueue.call_args.args[0]
    assert "TARJETA: DESCONECTADA" in texto


def test_reconexion_imprime_ticket():
    printer = MagicMock()
    loop = _make_loop(realtime_printer=printer)
    loop.link_was_connected = False  # simula que ya estaba desconectada

    _run_one_tick(loop, connected=True)

    printer.enqueue.assert_called_once()
    texto = printer.enqueue.call_args.args[0]
    assert "TARJETA: RECONECTADA" in texto


def test_conexion_estable_no_imprime():
    printer = MagicMock()
    loop = _make_loop(realtime_printer=printer)
    assert loop.link_was_connected is True

    _run_one_tick(loop, connected=True)

    printer.enqueue.assert_not_called()


def test_sin_realtime_printer_no_rompe():
    loop = _make_loop(realtime_printer=None)

    _run_one_tick(loop, connected=False)  # no debe lanzar excepción
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `pytest tests/test_control_loop_connectivity_ticket.py -v`
Expected: FAIL con `TypeError: ControlLoop.__init__() got an unexpected keyword argument 'realtime_printer'`

- [ ] **Step 3: Modificar `ControlLoop`**

En `src/autoclave/services/domain/loop/control_loop.py`, agregar el import al inicio del archivo (después de la línea 10, `from autoclave.devices.suministro_electrico...`):

```python
from datetime import datetime
from autoclave.devices.printer.connectivity_ticket import format_connectivity_ticket
```

Modificar la firma de `__init__` (línea 25-27):

```python
    def __init__(self, units, door_service, doors, estado, link, set_do,
                 alarm_manager, cycle_manager, config_manager,
                 cycle_logger=None, interval=0.5, cap=None, realtime_printer=None):
```

Y agregar la asignación junto a las demás (después de la línea 40, `self.cycle_logger = cycle_logger`):

```python
        self.realtime_printer = realtime_printer
```

Modificar el bloque de flanco en `run()` (líneas 62-78):

```python
            connected = self.link.is_connected()

            if not connected and self.link_was_connected:
                self.alarm_manager.report(
                    Alarm(
                        alarm_id="NO_HAY_CONEXION",
                        alarm_type=AlarmType.FALLA,
                        source_state="CONTROL_LOOP",
                        description="No hay comunicación con el hardware.",
                        recoverable=True,
                        blocks_operation=True,
                    )
                )
                if self.realtime_printer is not None:
                    self.realtime_printer.enqueue(
                        format_connectivity_ticket("TARJETA", False, datetime.now())
                    )
            elif connected and not self.link_was_connected:
                self.alarm_manager.clear("NO_HAY_CONEXION")
                if self.realtime_printer is not None:
                    self.realtime_printer.enqueue(
                        format_connectivity_ticket("TARJETA", True, datetime.now())
                    )

            self.link_was_connected = connected
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `pytest tests/test_control_loop_connectivity_ticket.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Conectar `realtime_printer` en `BackendContext`**

En `src/autoclave/backend/context.py`, dentro de la construcción de `ControlLoop` (líneas 83-95), agregar el parámetro:

```python
        self.control_loop = ControlLoop(
            units=self.units,
            door_service=self.servicio_puertas,
            doors=self.doors,
            estado=self.estado,
            link=self.serial,
            set_do=self.setdo,
            alarm_manager=self.alarm_manager,
            cycle_manager=self.cycle_manager,
            config_manager=self.config_manager,
            cycle_logger=self.cycle_logger,
            cap=cap,
            realtime_printer=self.realtime_printer,
        )
```

- [ ] **Step 6: Correr toda la suite para verificar que nada se rompió**

Run: `pytest tests/ -v`
Expected: PASS (todos los tests existentes siguen pasando; ningún test construye `BackendContext` de verdad, así que este cambio no debería afectar otros tests — confirmar en la salida que no hay nuevos fallos).

- [ ] **Step 7: Commit**

```bash
git add src/autoclave/services/domain/loop/control_loop.py src/autoclave/backend/context.py tests/test_control_loop_connectivity_ticket.py
git commit -m "feat: imprimir ticket al conectar/desconectar la tarjeta"
```

---

## Task 3: `UIServiceBackend` imprime al perder/recuperar respuesta del backend

**Files:**
- Modify: `src/autoclave/ui/service_ui/ui_service_backend.py`
- Test: `tests/test_ui_service_backend_connectivity_ticket.py`

**Interfaces:**
- Consumes: `format_connectivity_ticket(subsystem: str, ok: bool, when: datetime) -> str` (Task 1).
- Consumes: `RealtimePrinter` (clase, `src/autoclave/devices/printer/realtime_printer.py`), instanciada internamente.
- Produces: `UIServiceBackend` gana el atributo `self._printer` (instancia de `RealtimePrinter`) y `self._was_connected` (bool). `_fetch_status()` llama a `self._printer.enqueue(...)` en cada transición de `self.connected`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_ui_service_backend_connectivity_ticket.py`:

```python
from unittest.mock import MagicMock


class _NoOpThread:
    """Evita que arranque el hilo de fondo real — los tests llaman
    _fetch_status() directamente para controlar el orden de las llamadas."""
    def __init__(self, *a, **k):
        pass

    def start(self):
        pass


class _FakeBackendClient:
    def __init__(self, resultados):
        self._resultados = list(resultados)

    def get_status(self):
        resultado = self._resultados.pop(0)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


def _make_service(monkeypatch, resultados, impresiones):
    monkeypatch.setattr(
        "autoclave.ui.service_ui.ui_service_backend.threading.Thread", _NoOpThread
    )
    monkeypatch.setattr(
        "autoclave.devices.printer.realtime_printer.print_raw",
        lambda text, printer_name: impresiones.append(text) or True,
    )
    from autoclave.ui.service_ui.ui_service_backend import UIServiceBackend

    return UIServiceBackend(_FakeBackendClient(resultados))


def test_arranque_normal_no_imprime(monkeypatch):
    impresiones = []
    servicio = _make_service(monkeypatch, [{"ok": True}], impresiones)

    servicio._fetch_status()
    servicio._printer._queue.join()

    assert impresiones == []


def test_backend_deja_de_responder_imprime(monkeypatch):
    impresiones = []
    servicio = _make_service(
        monkeypatch, [{"ok": True}, ConnectionError("caido")], impresiones
    )

    servicio._fetch_status()  # OK, no imprime (estado primado en True)
    servicio._fetch_status()  # falla -> transición
    servicio._printer._queue.join()

    assert len(impresiones) == 1
    assert "BACKEND: SIN RESPUESTA" in impresiones[0]


def test_backend_se_recupera_imprime(monkeypatch):
    impresiones = []
    servicio = _make_service(
        monkeypatch,
        [{"ok": True}, ConnectionError("caido"), {"ok": True}],
        impresiones,
    )

    servicio._fetch_status()
    servicio._fetch_status()
    servicio._fetch_status()
    servicio._printer._queue.join()

    assert len(impresiones) == 2
    assert "BACKEND: SIN RESPUESTA" in impresiones[0]
    assert "BACKEND: RECONECTADO" in impresiones[1]


def test_falla_desde_el_arranque_imprime_de_inmediato(monkeypatch):
    impresiones = []
    servicio = _make_service(
        monkeypatch, [ConnectionError("no disponible")], impresiones
    )

    servicio._fetch_status()
    servicio._printer._queue.join()

    assert len(impresiones) == 1
    assert "BACKEND: SIN RESPUESTA" in impresiones[0]
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `pytest tests/test_ui_service_backend_connectivity_ticket.py -v`
Expected: FAIL — `test_backend_deja_de_responder_imprime` y similares fallan porque `impresiones` queda vacío (todavía no existe la lógica de impresión).

- [ ] **Step 3: Modificar `UIServiceBackend`**

En `src/autoclave/ui/service_ui/ui_service_backend.py`, agregar imports al inicio del archivo (después de la línea 4, `import logging`):

```python
from datetime import datetime

from autoclave.devices.printer.connectivity_ticket import format_connectivity_ticket
from autoclave.devices.printer.realtime_printer import RealtimePrinter
```

Modificar `__init__` (líneas 21-32), agregando `self._printer` y `self._was_connected` junto a `self.connected`:

```python
    def __init__(self, backend_client):
        self.backend   = backend_client
        self._lock     = threading.Lock()
        self._cache    = {}
        self._config   = {}
        self._cycle    = {}
        self.connected = False
        self._was_connected = True   # primado: main.py ya confirmó el backend vivo
        self._printer  = RealtimePrinter()

        # Hilo de actualización en segundo plano
        self._stop   = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
```

Modificar `_fetch_status()` (líneas 47-57) para detectar el flanco y encolar el ticket:

```python
    def _fetch_status(self):
        """Obtiene /status (sensores, estado, fases) — alta frecuencia."""
        try:
            cache = self.backend.get_status()
            with self._lock:
                self._cache    = cache
                self.connected = True
        except Exception as e:
            with self._lock:
                self.connected = False
            logger.warning("⚠️ Backend no disponible: %s", e)

        if self.connected != self._was_connected:
            self._printer.enqueue(
                format_connectivity_ticket("BACKEND", self.connected, datetime.now())
            )
            self._was_connected = self.connected
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `pytest tests/test_ui_service_backend_connectivity_ticket.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Correr toda la suite para verificar que nada se rompió**

Run: `pytest tests/ -v`
Expected: PASS (todos los tests existentes y los nuevos pasan)

- [ ] **Step 6: Commit**

```bash
git add src/autoclave/ui/service_ui/ui_service_backend.py tests/test_ui_service_backend_connectivity_ticket.py
git commit -m "feat: imprimir ticket cuando el backend deja de responder o se recupera"
```

---

## Task 4: Verificación manual end-to-end

**Files:** Ninguno (solo verificación, sin cambios de código).

- [ ] **Step 1: Levantar la aplicación completa**

Run: `python -m autoclave.main` (o el comando habitual de arranque de este proyecto)
Expected: la UI arranca, el ticket de arranque se imprime como hasta ahora (sin cambios en ese flujo).

- [ ] **Step 2: Verificar evento de tarjeta**

Desconectar físicamente el cable USB/serial de la tarjeta ESP32 mientras la aplicación está corriendo, esperar unos segundos, y volver a conectarlo.
Expected: se imprimen dos tickets nuevos — uno con "TARJETA: DESCONECTADA" al desconectar, otro con "TARJETA: RECONECTADA" al reconectar. La alarma `NO_HAY_CONEXION` en la UI sigue apareciendo/desapareciendo como antes (no debe haberse roto ese comportamiento).

- [ ] **Step 3: Verificar evento de backend**

Con la UI corriendo, terminar manualmente el proceso backend (`autoclave.backend.main`, por ejemplo desde el Administrador de tareas o `taskkill`), esperar unos segundos, y volver a iniciarlo manualmente (`python -m autoclave.backend.main`).
Expected: se imprime un ticket "BACKEND: SIN RESPUESTA" poco después de matar el proceso, y "BACKEND: RECONECTADO" poco después de reiniciarlo. La UI debe seguir funcionando (mostrando datos obsoletos o vacíos mientras el backend está caído) sin crashear.

- [ ] **Step 4: Verificar cierre normal no imprime falsos positivos**

Cerrar la aplicación normalmente desde la UI (botón de cierre / `WM_DELETE_WINDOW`).
Expected: NO se imprime ningún ticket de "BACKEND: SIN RESPUESTA" durante el cierre — `ui_service.stop()` debe detener el sondeo antes de que el backend se termine.

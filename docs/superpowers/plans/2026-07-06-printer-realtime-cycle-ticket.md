# Impresión en tiempo real del ticket de ciclo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cuando el autoclave está en ciclo, cada lectura que `CycleLogger` ya registra en la DB (según `intervalo_impresion` / `intervalo_imprecion_esterilizacion` de `global_params.json`, o en cada cambio de fase) se envía también, en ese mismo instante, a la impresora térmica física.

**Architecture:** `CycleLogger` encola texto en un `RealtimePrinter` (cola + hilo worker dedicado) que llama a `win32_printer.print_raw()` ya existente. `ticket_formatter.py` se refactoriza para exponer `format_header` / `format_row` / `format_footer` reutilizables tanto por el ticket bajo demanda (sin cambios de comportamiento) como por la impresión en vivo.

**Tech Stack:** Python 3.14, `queue`/`threading` de stdlib, `pytest` + `monkeypatch`/`caplog`.

## Global Constraints

- No modificar el formato visual del ticket: `format_ticket()` debe seguir devolviendo byte a byte el mismo texto que hoy.
- Ningún fallo de impresión puede bloquear ni propagar excepciones al hilo del control loop (best-effort, sin reintentos).
- `CycleLogger` debe seguir funcionando igual que hoy cuando se instancia sin impresora (`printer=None`) — comportamiento por defecto en tests y en cualquier entorno sin hardware de impresión.
- Spec de referencia: `docs/superpowers/specs/2026-07-06-printer-realtime-cycle-ticket-design.md`.

---

## Contexto de archivos existentes (léelo antes de tocar nada)

- `src/autoclave/services/domain/logging/ticket_formatter.py` — formateador actual, monolítico.
- `src/autoclave/services/domain/logging/cycle_logger.py` — detecta inicio/fin de ciclo y registra lecturas; corre en el hilo del control loop.
- `src/autoclave/devices/printer/win32_printer.py` — ya expone `print_raw(text: str, printer_name: str = PRINTER_NAME) -> bool` y `PRINTER_NAME = "Impresora_Termica"`. Nunca lanza — atrapa sus propias excepciones y devuelve `False` logueando un warning.
- `src/autoclave/backend/context.py` — arma `CycleLogger` con sus dependencias.
- `src/autoclave/state_machine/machine/enum_global.py` — `GlobalState.CICLO`, `GlobalState.PREPARADO`, etc.

---

### Task 1: Refactorizar `ticket_formatter.py` en piezas reutilizables

**Files:**
- Modify: `src/autoclave/services/domain/logging/ticket_formatter.py` (reemplazo completo)
- Test: `tests/test_ticket_formatter.py` (nuevo)

**Interfaces:**
- Produces: `format_header(meta: dict) -> str`, `format_row(lectura: dict) -> str`, `format_footer(resultado: str, fecha_fin: str) -> str`. `format_ticket(ciclo, lecturas) -> str` sigue existiendo con la misma firma.
  - `meta` para `format_header`: `numero_ciclo`, `serie`, `nombre_ciclo`, `tipo_ciclo`, `operador`, `temp_esterilizacion`, `tiempo_esterilizacion`, `fecha_inicio`.
  - `lectura` para `format_row`: `fase_codigo`, `timestamp_rel`, `temp_camara`, `pres_camara`.

- [x] **Step 1: Escribir el test de equivalencia y los tests unitarios (deben fallar)**

Crear `tests/test_ticket_formatter.py`:

```python
from autoclave.services.domain.logging.ticket_formatter import (
    format_footer,
    format_header,
    format_row,
    format_ticket,
)


def _ciclo():
    return {
        "numero_ciclo": 7,
        "serie": "SN-001",
        "nombre_ciclo": "Bowie-Dick",
        "tipo_ciclo": "bowe_dick",
        "operador": "Juan",
        "temp_esterilizacion": 134.0,
        "tiempo_esterilizacion": 3.5,
        "fecha_inicio": "2026-07-06T08:00:00",
        "fecha_fin": "2026-07-06T08:45:00",
        "resultado": "COMPLETADO",
    }


def _lecturas():
    return [
        {"fase_codigo": "PH", "timestamp_rel": "00:00:00", "temp_camara": 25.0, "pres_camara": 74.5},
        {"fase_codigo": "S", "timestamp_rel": "00:20:00", "temp_camara": 134.2, "pres_camara": 210.0},
        {"fase_codigo": "E", "timestamp_rel": "00:45:00", "temp_camara": 60.0, "pres_camara": 75.0},
    ]


def test_format_header_incluye_numero_de_ciclo_y_serie():
    meta = _ciclo()
    header = format_header(meta)
    assert "00007" in header
    assert "SN-001" in header
    assert "ESPECIFIKA -- AUTOCLAVE MX-500" in header


def test_format_header_usa_tipo_ciclo_si_no_hay_nombre():
    meta = _ciclo()
    meta["nombre_ciclo"] = ""
    header = format_header(meta)
    assert "bowe_dick" in header


def test_format_row_formatea_una_lectura():
    row = format_row({"fase_codigo": "S", "timestamp_rel": "00:20:00", "temp_camara": 134.2, "pres_camara": 210.0})
    assert row == f"  {'00:20:00':<10}{'Esteriliz.':<12}{'134.2':>8}  {'210.0':>9}"


def test_format_row_maneja_valores_none():
    row = format_row({"fase_codigo": "F", "timestamp_rel": "00:05:00", "temp_camara": None, "pres_camara": None})
    assert "--" in row


def test_format_footer_incluye_resultado_y_fin():
    footer = format_footer("COMPLETADO", "2026-07-06T08:45:00")
    assert "Resultado:   COMPLETADO" in footer
    assert "2026-07-06 08:45:00" in footer


def test_header_filas_pie_equivalen_a_format_ticket():
    ciclo = _ciclo()
    lecturas = _lecturas()

    meta = {
        "numero_ciclo": ciclo["numero_ciclo"],
        "serie": ciclo["serie"],
        "nombre_ciclo": ciclo["nombre_ciclo"],
        "tipo_ciclo": ciclo["tipo_ciclo"],
        "operador": ciclo["operador"],
        "temp_esterilizacion": ciclo["temp_esterilizacion"],
        "tiempo_esterilizacion": ciclo["tiempo_esterilizacion"],
        "fecha_inicio": ciclo["fecha_inicio"],
    }
    ensamblado = "\n".join(
        [format_header(meta)]
        + [format_row(r) for r in lecturas]
        + [format_footer(ciclo["resultado"], ciclo["fecha_fin"])]
    )

    assert ensamblado == format_ticket(ciclo, lecturas)
```

- [x] **Step 2: Correr los tests para verificar que fallan**

Run: `pytest tests/test_ticket_formatter.py -v`
Expected: `ImportError: cannot import name 'format_header'` (las tres funciones nuevas no existen todavía).

- [x] **Step 3: Reemplazar el contenido de `ticket_formatter.py`**

Reemplazar el archivo completo por:

```python
# services/domain/logging/ticket_formatter.py
from datetime import datetime

_FASE = {
    "PH": "Pre-calent.",
    "PG": "Purga",
    "PV": "Pre-vacío",
    "H":  "Calentam.",
    "E":  "Estabiliz.",
    "S":  "Esteriliz.",
    "F":  "Fallo",
}

_W   = 48
_SEP = "=" * _W
_DIV = "-" * _W


def _hdr(lbl, val, lbl2, val2):
    return f"{lbl:<13}{val:<15}{lbl2:<10}{val2}"


def format_header(meta: dict) -> str:
    """Encabezado del ticket (todo lo previo a las filas de lecturas)."""
    numero   = meta["numero_ciclo"]
    serie    = meta.get("serie") or "--"
    nombre   = meta.get("nombre_ciclo") or meta.get("tipo_ciclo") or "--"
    operador = meta.get("operador") or "--"
    temp     = meta.get("temp_esterilizacion")
    tiempo   = meta.get("tiempo_esterilizacion")
    fi       = meta.get("fecha_inicio") or ""

    try:
        dt      = datetime.fromisoformat(fi)
        fecha_s = dt.strftime("%Y-%m-%d")
        hora_s  = dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        fecha_s = fi[:10]
        hora_s  = fi[11:19]

    temp_s   = f"{temp:.1f} C" if temp is not None else "--"
    tiempo_s = f"{int(tiempo)} min" if tiempo is not None else "--"

    lines = [
        _SEP,
        "ESPECIFIKA -- AUTOCLAVE MX-500".center(_W),
        _SEP,
        _hdr("Serie:",       serie,    "Ciclo N°:", f"{numero:05d}"),
        _hdr("Fecha:",       fecha_s,  "Hora:",     hora_s),
        _hdr("Tipo:",        nombre,   "Operador:", operador),
        _hdr("Temp. ester:", temp_s,   "Tiempo:",   tiempo_s),
        _DIV,
        f"  {'HORA':<10}{'FASE':<12}{'TEMP(C)':>8}  {'PRES(kPa)':>9}",
        _DIV,
    ]
    return "\n".join(lines)


def format_row(lectura: dict) -> str:
    """Una fila HORA/FASE/TEMP/PRES."""
    label = _FASE.get(lectura["fase_codigo"], lectura["fase_codigo"])
    tv    = lectura["temp_camara"]
    pv    = lectura["pres_camara"]
    t_s   = f"{tv:.1f}" if tv is not None else "--"
    p_s   = f"{pv:.1f}" if pv is not None else "--"
    return f"  {lectura['timestamp_rel']:<10}{label:<12}{t_s:>8}  {p_s:>9}"


def format_footer(resultado: str, fecha_fin: str) -> str:
    """Pie del ticket (todo lo posterior a las filas de lecturas)."""
    try:
        fin_s = datetime.fromisoformat(fecha_fin).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        fin_s = fecha_fin or "--"

    lines = [
        _DIV,
        f"Resultado:   {resultado or '--'}",
        f"Fin:         {fin_s}",
        _SEP,
        "",
    ]
    return "\n".join(lines)


def format_ticket(ciclo, lecturas) -> str:
    """Format cycle data as plain-text print ticket."""
    meta = {
        "numero_ciclo":          ciclo["numero_ciclo"],
        "serie":                 ciclo["serie"],
        "nombre_ciclo":          ciclo["nombre_ciclo"],
        "tipo_ciclo":            ciclo["tipo_ciclo"],
        "operador":              ciclo["operador"],
        "temp_esterilizacion":   ciclo["temp_esterilizacion"],
        "tiempo_esterilizacion": ciclo["tiempo_esterilizacion"],
        "fecha_inicio":          ciclo["fecha_inicio"],
    }
    parts = [format_header(meta)]
    parts += [format_row(r) for r in lecturas]
    parts.append(format_footer(ciclo["resultado"], ciclo["fecha_fin"]))
    return "\n".join(parts)
```

- [x] **Step 4: Correr los tests para verificar que pasan**

Run: `pytest tests/test_ticket_formatter.py -v`
Expected: 6 passed.

- [x] **Step 5: Commit**

```bash
git add src/autoclave/services/domain/logging/ticket_formatter.py tests/test_ticket_formatter.py
git commit -m "refactor: exponer format_header/format_row/format_footer en ticket_formatter"
```

---

### Task 2: `RealtimePrinter` — cola + hilo worker

**Files:**
- Create: `src/autoclave/devices/printer/realtime_printer.py`
- Test: `tests/test_realtime_printer.py` (nuevo)

**Interfaces:**
- Consumes: `autoclave.devices.printer.win32_printer.print_raw(text: str, printer_name: str) -> bool`, `PRINTER_NAME: str`.
- Produces: `RealtimePrinter(printer_name: str = PRINTER_NAME)` con método `enqueue(text: str) -> None` (no bloqueante, nunca lanza).

- [x] **Step 1: Escribir los tests (deben fallar)**

Crear `tests/test_realtime_printer.py`:

```python
import logging


def test_enqueue_envia_texto_a_print_raw(monkeypatch):
    llamadas = []

    def fake_print_raw(text, printer_name):
        llamadas.append((text, printer_name))
        return True

    monkeypatch.setattr(
        "autoclave.devices.printer.realtime_printer.print_raw", fake_print_raw
    )
    from autoclave.devices.printer.realtime_printer import RealtimePrinter

    rp = RealtimePrinter(printer_name="Impresora_Test")
    rp.enqueue("linea 1")
    rp._queue.join()

    assert llamadas == [("linea 1", "Impresora_Test")]


def test_excepcion_en_print_raw_no_detiene_el_worker(monkeypatch, caplog):
    llamadas = []

    def fake_print_raw(text, printer_name):
        llamadas.append(text)
        if text == "falla":
            raise RuntimeError("impresora desconectada")
        return True

    monkeypatch.setattr(
        "autoclave.devices.printer.realtime_printer.print_raw", fake_print_raw
    )
    from autoclave.devices.printer.realtime_printer import RealtimePrinter

    rp = RealtimePrinter()
    with caplog.at_level(logging.WARNING, logger="autoclave.devices.printer.realtime_printer"):
        rp.enqueue("falla")
        rp.enqueue("linea despues del fallo")
        rp._queue.join()

    assert llamadas == ["falla", "linea despues del fallo"]
    assert "error inesperado al imprimir" in caplog.text


def test_print_raw_false_loguea_warning_y_continua(monkeypatch, caplog):
    monkeypatch.setattr(
        "autoclave.devices.printer.realtime_printer.print_raw",
        lambda text, printer_name: False,
    )
    from autoclave.devices.printer.realtime_printer import RealtimePrinter

    rp = RealtimePrinter()
    with caplog.at_level(logging.WARNING, logger="autoclave.devices.printer.realtime_printer"):
        rp.enqueue("linea")
        rp._queue.join()

    assert "print_raw devolvió False" in caplog.text
```

- [x] **Step 2: Correr los tests para verificar que fallan**

Run: `pytest tests/test_realtime_printer.py -v`
Expected: `ModuleNotFoundError: No module named 'autoclave.devices.printer.realtime_printer'`

- [x] **Step 3: Crear `realtime_printer.py`**

```python
import logging
import queue
import threading

from autoclave.devices.printer.win32_printer import PRINTER_NAME, print_raw

logger = logging.getLogger(__name__)


class RealtimePrinter:
    """Imprime líneas de texto en orden, en un hilo dedicado, sin bloquear al llamador."""

    def __init__(self, printer_name: str = PRINTER_NAME):
        self._printer_name = printer_name
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def enqueue(self, text: str) -> None:
        """Encola texto para impresión. No bloquea ni lanza excepciones."""
        self._queue.put(text)

    def _worker(self):
        while True:
            text = self._queue.get()
            try:
                if not print_raw(text, self._printer_name):
                    logger.warning("RealtimePrinter: print_raw devolvió False, línea descartada")
            except Exception as exc:
                logger.warning("RealtimePrinter: error inesperado al imprimir: %s", exc)
            finally:
                self._queue.task_done()
```

- [x] **Step 4: Correr los tests para verificar que pasan**

Run: `pytest tests/test_realtime_printer.py -v`
Expected: 3 passed.

- [x] **Step 5: Commit**

```bash
git add src/autoclave/devices/printer/realtime_printer.py tests/test_realtime_printer.py
git commit -m "feat: agregar RealtimePrinter (cola + hilo worker) para impresion en vivo"
```

---

### Task 3: Integrar `RealtimePrinter` en `CycleLogger`

**Files:**
- Modify: `src/autoclave/services/domain/logging/cycle_logger.py`
- Test: `tests/test_cycle_logger_printer.py` (nuevo)

**Interfaces:**
- Consumes: `format_header`, `format_row`, `format_footer` (Task 1); cualquier objeto con `.enqueue(text: str) -> None` (Task 2 lo cumple; los tests usan un doble).
- Produces: `CycleLogger(db, estado, config, profile, cycle_manager, printer=None)` — nuevo parámetro opcional `printer`, sin cambios de comportamiento cuando es `None`.

- [x] **Step 1: Escribir los tests (deben fallar)**

Crear `tests/test_cycle_logger_printer.py`:

```python
import time as time_module
from types import SimpleNamespace

from autoclave.services.domain.logging.cycle_logger import CycleLogger
from autoclave.state_machine.machine.enum_global import GlobalState


class FakeDb:
    def __init__(self):
        self._next_id = 1
        self.cerrados = []

    def siguiente_numero_ciclo(self):
        return 7

    def crear_ciclo(self, **kwargs):
        cid = self._next_id
        self._next_id += 1
        return cid

    def insertar_lectura(self, **kwargs):
        pass

    def cerrar_ciclo(self, ciclo_id, resultado):
        self.cerrados.append((ciclo_id, resultado))


class FakeCycle:
    id = "bowe_dick"
    name = "Bowie-Dick"

    def get_param(self, *keys, default=None):
        valores = {"temperatura_esterilizacion": 134, "tiempo_esterilizacion": 3.5}
        return valores.get(keys[0], default)


class FakeCycleManager:
    def get_selected_cycle(self):
        return FakeCycle()


class FakeConfig:
    def __init__(self, intervalo=99999):
        self.intervalo = intervalo

    def get(self, *keys, default=None):
        return self.intervalo


class FakeEstado:
    def __init__(self):
        self.machine_state = GlobalState.CICLO
        self.fase_ciclo = "PRECALENTAMIENTO"
        self.sensores_temp = {"temp_camara": 25.0}
        self.sensores_pres = {"pres_camara": 74.5}

    def get_machine_state(self):
        return self.machine_state


class FakePrinter:
    def __init__(self):
        self.calls = []

    def enqueue(self, text):
        self.calls.append(text)


def _build_logger(printer, config=None):
    return CycleLogger(
        db=FakeDb(),
        estado=FakeEstado(),
        config=config or FakeConfig(),
        profile=SimpleNamespace(serial_number="SN-001", model_id="MX-500"),
        cycle_manager=FakeCycleManager(),
        printer=printer,
    )


def test_inicio_de_ciclo_encola_encabezado():
    printer = FakePrinter()
    cl = _build_logger(printer)

    cl.update()   # transición → CICLO: dispara _on_inicio

    assert len(printer.calls) == 1
    assert "ESPECIFIKA" in printer.calls[0]
    assert "00007" in printer.calls[0]


def test_cambio_de_fase_encola_una_fila():
    printer = FakePrinter()
    cl = _build_logger(printer)

    cl.update()   # header
    cl.update()   # cambio de fase None -> "PH" -> fila

    assert len(printer.calls) == 2
    assert "Pre-calent." in printer.calls[1]


def test_sin_cambio_de_fase_ni_intervalo_no_encola_nada_nuevo():
    printer = FakePrinter()
    cl = _build_logger(printer)

    cl.update()   # header
    cl.update()   # fila por cambio de fase
    cl.update()   # misma fase, intervalo (99999s) no cumplido

    assert len(printer.calls) == 2


def test_intervalo_cumplido_encola_fila_periodica(monkeypatch):
    printer = FakePrinter()
    cl = _build_logger(printer, config=FakeConfig(intervalo=1))
    cl.estado.fase_ciclo = "CALENTAMIENTO"   # código "H" -> usa intervalo_impresion

    tiempo_actual = [1000.0]
    monkeypatch.setattr(time_module, "time", lambda: tiempo_actual[0])

    cl.update()   # header
    cl.update()   # cambio de fase None -> "H" -> fila 1

    tiempo_actual[0] += 2.0   # supera el intervalo de 1s
    cl.update()   # misma fase, intervalo cumplido -> fila 2

    assert len(printer.calls) == 3


def test_fin_de_ciclo_encola_fila_final_y_pie():
    printer = FakePrinter()
    cl = _build_logger(printer)

    cl.update()   # header
    cl.update()   # fila por cambio de fase
    cl.estado.machine_state = GlobalState.PREPARADO
    cl.update()   # _on_fin: fila "E" + pie

    assert len(printer.calls) == 4
    assert "Resultado:" in printer.calls[3]
    assert "Fin:" in printer.calls[3]


def test_sin_printer_no_falla():
    cl = _build_logger(printer=None)

    cl.update()
    cl.update()
    cl.estado.machine_state = GlobalState.PREPARADO
    cl.update()
```

- [x] **Step 2: Correr los tests para verificar que fallan**

Run: `pytest tests/test_cycle_logger_printer.py -v`
Expected: `TypeError: CycleLogger.__init__() got an unexpected keyword argument 'printer'`

- [x] **Step 3: Modificar `cycle_logger.py`**

Agregar el import de las funciones de formateo justo debajo del import existente de `GlobalState` (línea 23):

```python
from autoclave.state_machine.machine.enum_global import GlobalState
from autoclave.services.domain.logging.ticket_formatter import (
    format_footer,
    format_header,
    format_row,
)
```

Reemplazar el `__init__` (líneas 70-82) por:

```python
    def __init__(self, db, estado, config, profile, cycle_manager, printer=None):
        self.db            = db
        self.estado        = estado
        self.config        = config
        self.profile       = profile
        self.cycle_manager = cycle_manager
        self.printer       = printer

        # Estado interno
        self._activo            = False
        self._ciclo_id: int | None = None
        self._ciclo_inicio      = None    # time.time() al iniciar
        self._ultimo_log        = 0.0     # time.time() del último registro
        self._ultima_fase_codigo = None   # para detectar cambio de fase
```

Reemplazar `_on_inicio` (líneas 118-153) por:

```python
    def _on_inicio(self):
        numero = self.db.siguiente_numero_ciclo()

        # Leer metadatos del ciclo seleccionado
        tipo   = ""
        nombre = ""
        temp_e = None
        t_e    = None
        try:
            cycle  = self.cycle_manager.get_selected_cycle()
            tipo   = cycle.id
            nombre = cycle.name
            temp_e = cycle.get_param("temperatura_esterilizacion")
            t_e    = cycle.get_param("tiempo_esterilizacion")
        except Exception as exc:
            logger.warning("CycleLogger: no se pudo leer el ciclo: %s", exc)

        serie = getattr(self.profile, "serial_number", "")

        self._ciclo_id = self.db.crear_ciclo(
            numero      = numero,
            tipo        = tipo,
            nombre      = nombre,
            temp_ester  = temp_e,
            tiempo_ester= t_e,
            modelo      = getattr(self.profile, "model_id",      ""),
            serie       = serie,
            version_sw  = VERSION_SW,
        )
        self._ciclo_inicio       = time.time()
        self._ultimo_log         = 0.0    # primera lectura se hace inmediatamente
        self._ultima_fase_codigo = None
        self._activo             = True

        if self.printer is not None:
            meta = {
                "numero_ciclo":          numero,
                "serie":                 serie,
                "nombre_ciclo":          nombre,
                "tipo_ciclo":            tipo,
                "operador":              "",
                "temp_esterilizacion":   temp_e,
                "tiempo_esterilizacion": t_e,
                "fecha_inicio":          datetime.now().isoformat(),
            }
            self.printer.enqueue(format_header(meta))

        logger.info(
            "CycleLogger: ciclo #%05d iniciado → DB id=%d | %s",
            numero, self._ciclo_id, nombre
        )
```

Reemplazar `_on_fin` (líneas 155-167) por:

```python
    def _on_fin(self, resultado: str):
        if self._ciclo_id is not None:
            # Última lectura con código E
            self._registrar_lectura("E", para_imprimir=True)
            self.db.cerrar_ciclo(self._ciclo_id, resultado)

            if self.printer is not None:
                self.printer.enqueue(format_footer(resultado, datetime.now().isoformat()))

            logger.info(
                "CycleLogger: ciclo id=%d cerrado → %s", self._ciclo_id, resultado
            )

        self._activo            = False
        self._ciclo_id          = None
        self._ciclo_inicio      = None
        self._ultima_fase_codigo = None
```

Reemplazar `_registrar_lectura` (líneas 200-228) por:

```python
    def _registrar_lectura(self, fase_codigo: str, para_imprimir: bool = False):
        if self._ciclo_id is None:
            return

        ahora   = time.time()
        elapsed = ahora - (self._ciclo_inicio or ahora)
        timestamp_rel = _fmt_elapsed(elapsed)

        temp = self.estado.sensores_temp.get("temp_camara")
        pres = self.estado.sensores_pres.get("pres_camara")

        self.db.insertar_lectura(
            ciclo_id      = self._ciclo_id,
            timestamp_rel = timestamp_rel,
            timestamp_abs = datetime.now().isoformat(),
            fase_codigo   = fase_codigo,
            temp          = temp,
            pres          = pres,
            para_imprimir = para_imprimir,
        )
        self._ultimo_log = ahora

        if para_imprimir and self.printer is not None:
            self.printer.enqueue(format_row({
                "fase_codigo":   fase_codigo,
                "timestamp_rel": timestamp_rel,
                "temp_camara":   temp,
                "pres_camara":   pres,
            }))

        logger.debug(
            "LOG [%s] %s  %.1f°C  %.1f kPa  imprimir=%s",
            fase_codigo,
            timestamp_rel,
            temp or 0.0,
            pres or 0.0,
            para_imprimir,
        )
```

- [x] **Step 4: Correr los tests para verificar que pasan**

Run: `pytest tests/test_cycle_logger_printer.py -v`
Expected: 6 passed.

- [x] **Step 5: Correr toda la suite de tests para verificar que no se rompió nada**

Run: `pytest tests/ -v`
Expected: todos los tests existentes siguen pasando (en particular `test_win32_printer.py`, `test_startup_ticket.py`, y cualquier test que ya cubra `CycleLogger`/`ticket_formatter` indirectamente).

- [x] **Step 6: Commit**

```bash
git add src/autoclave/services/domain/logging/cycle_logger.py tests/test_cycle_logger_printer.py
git commit -m "feat: imprimir ticket de ciclo en tiempo real desde CycleLogger"
```

---

### Task 4: Conectar `RealtimePrinter` en `BackendContext`

**Files:**
- Modify: `src/autoclave/backend/context.py`

**Interfaces:**
- Consumes: `RealtimePrinter` (Task 2), `CycleLogger(..., printer=...)` (Task 3).

- [x] **Step 1: Agregar el import**

En `src/autoclave/backend/context.py`, junto a los demás imports de `autoclave.services.domain.logging` (línea 16), agregar:

```python
from autoclave.devices.printer.realtime_printer import RealtimePrinter
```

- [x] **Step 2: Instanciar el printer y pasarlo a `CycleLogger`**

Reemplazar el bloque actual (líneas 70-78):

```python
        # Data logger (SQLite)
        self.db          = DbManager()
        self.cycle_logger = CycleLogger(
            db            = self.db,
            estado        = self.estado,
            config        = self.config_manager,
            profile       = self.profile,
            cycle_manager = self.cycle_manager,
        )
```

por:

```python
        # Data logger (SQLite) + impresión en tiempo real
        self.db               = DbManager()
        self.realtime_printer = RealtimePrinter()
        self.cycle_logger = CycleLogger(
            db            = self.db,
            estado        = self.estado,
            config        = self.config_manager,
            profile       = self.profile,
            cycle_manager = self.cycle_manager,
            printer       = self.realtime_printer,
        )
```

- [x] **Step 3: Verificar que el backend sigue arrancando**

Run: `python -c "import autoclave.backend.context"`
Expected: no lanza `ImportError` ni `SyntaxError` (verificación estática; `RealtimePrinter()` abre un hilo daemon inofensivo aunque no exista la impresora física — `print_raw` ya maneja ese caso con un warning).

Run: `pytest tests/ -v`
Expected: todos los tests siguen pasando (este archivo no tiene tests dedicados porque instancia hardware real; se cubre por los tests de `RealtimePrinter` y `CycleLogger` de las tasks anteriores).

- [x] **Step 4: Commit**

```bash
git add src/autoclave/backend/context.py
git commit -m "feat: conectar RealtimePrinter en BackendContext"
```

---

## Verificación manual (fuera del alcance automatizable)

Con la impresora térmica "Impresora_Termica" instalada en Windows y un ciclo real o simulado:

1. Arrancar el backend e iniciar un ciclo.
2. Confirmar que al entrar en ciclo se imprime el encabezado inmediatamente.
3. Confirmar que durante `CALENTAMIENTO`/`ESTABILIZACION` se imprime una fila cada `intervalo_impresion` segundos (180 s por defecto) y durante `ESTERILIZACION` cada `intervalo_imprecion_esterilizacion` segundos (60 s por defecto) — o antes, si cambia de fase.
4. Confirmar que al finalizar el ciclo se imprime la fila final y el pie con resultado y hora de fin.
5. Apagar/desconectar la impresora a mitad de ciclo y confirmar (por el log) que el ciclo continúa sin errores ni caídas.

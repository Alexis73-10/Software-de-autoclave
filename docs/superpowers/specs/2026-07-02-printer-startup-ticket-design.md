# Diseño: Ticket de arranque en impresora térmica

**Fecha:** 2026-07-02
**Alcance:** Impresión automática al arranque del sistema (fase 1 de 2)
**Fase 2 (fuera de alcance aquí):** impresión en tiempo real durante ciclos

---

## Contexto

El autoclave cuenta con una impresora térmica de 58 mm configurada en Windows como
"Generic / Text Only" en puerto USB 005, formato RAW. Al encender el equipo mediante
el interruptor eléctrico (sin cierre graceful del software), el sistema debe imprimir
automáticamente un ticket con los datos del equipo y las horas de apagado y encendido.

---

## Arquitectura

### Nuevo paquete

```
src/autoclave/devices/printer/
├── __init__.py
├── heartbeat.py        # Hilo daemon: persiste timestamp cada 30 s
├── startup_ticket.py   # Formateador puro del ticket de arranque
└── win32_printer.py    # Envío RAW a impresora Windows (win32print)
```

### Archivo de estado

```
data/last_shutdown.json     # {"timestamp": "2026-07-02T10:35:00.123456"}
```

### Nueva dependencia

`pywin32` agregado a `[project.dependencies]` en `pyproject.toml`.

---

## Componentes

### `heartbeat.py`

- Expone `start(interval: int = 30) -> None`
- Lanza un `threading.Timer` recursivo en modo daemon
- Cada tick escribe `datetime.now().isoformat()` en `data/last_shutdown.json`
- Si falla la escritura, el error se loguea y el timer se reprograma en `finally`
- No conoce el profile ni la impresora

### `startup_ticket.py`

- Función pura: `format_startup_ticket(profile, version, last_shutdown, startup_time) -> str`
- `profile`: `InstallationProfile` (model_id, serial_number, equipment_class)
- `version`: string obtenido de `importlib.metadata.version("autoclave")`
- `last_shutdown`: `datetime | None` (None → primer arranque)
- `startup_time`: `datetime.now()` capturado al momento de imprimir
- Ancho fijo 48 caracteres, misma estética que `ticket_formatter.py`

### `win32_printer.py`

- Función: `print_raw(text: str, printer_name: str = "Generic / Text Only") -> None`
- Abre el spooler con `win32print.OpenPrinter`
- Envía job tipo RAW con `win32print.WritePrinter`
- Codificación: `cp437` (compatible con impresoras térmicas DOS/texto)
- Cierra siempre el handle en `finally`
- Lanza excepción si `win32print` no está instalado o la impresora no existe;
  el llamador la captura y loguea

---

## Flujo de integración

```
main() en main.py
 ├── get_installation_profile()       → profile
 ├── wait_for_backend()               → backend listo
 ├── heartbeat.start(interval=30)     → hilo daemon arranca
 └── InterfazPrincipal(...)           → ventana visible
       └── root.after(500, _on_ready)
             ├── lee data/last_shutdown.json  → last_shutdown (o None)
             ├── importlib.metadata.version("autoclave")  → version
             ├── format_startup_ticket(...)   → texto
             └── print_raw(texto)             → impresora
```

El `after(500)` permite que la ventana termine de renderizarse antes de llamar
al spooler, evitando que el hilo principal se bloquee durante la impresión inicial.

---

## Formato del ticket

```
================================================
         ESPECIFIKA -- AUTOCLAVE
================================================
Modelo:         MESA_B
Serie:          AUT-2024-001
Clase:          mesa_b
Software:       v0.4.0
------------------------------------------------
ENCENDIDO       2026-07-02  10:47:23
APAGADO         2026-07-02  10:15:08
------------------------------------------------
         Sistema listo
================================================

```

- Último apagado `None` → la línea APAGADO muestra `"Primer encendido"`
- Línea en blanco final para que el papel avance y pueda arrancarse

---

## Manejo de errores

| Situación | Comportamiento |
|---|---|
| Impresora apagada / desconectada | `logger.warning`, la app continúa |
| `last_shutdown.json` corrupto o ausente | Trata como `None` (primer encendido) |
| Heartbeat falla un tick | Loguea el error, el timer se reprograma |
| `pywin32` no instalado | `logger.warning`, la app continúa |

**Política:** la impresora es periférico auxiliar. Ningún error de impresión
interrumpe el arranque ni el control del autoclave.

---

## Testing

- **`tests/test_startup_ticket.py`** — función pura, tests unitarios:
  - El texto contiene model_id, serial_number, version
  - Ninguna línea supera 48 caracteres
  - `last_shutdown=None` produce `"Primer encendido"` en el output
- **`heartbeat.py`** y **`win32_printer.py`** — validación manual en el equipo real
  (dependen de sistema de archivos, threads y hardware Windows)

---

## Fuera de alcance (fase 2)

- Impresión en tiempo real durante ciclos según intervalos configurados
- Sección de errores de software/Windows en el ticket de arranque

# Diseño: Impresión en tiempo real del ticket de ciclo

**Fecha:** 2026-07-06
**Alcance:** Impresión automática, en vivo, de los datos del ciclo de esterilización
(fase 2 de 2 — continúa el trabajo de `2026-07-02-printer-startup-ticket-design.md`)

---

## Contexto

`CycleLogger` (`src/autoclave/services/domain/logging/cycle_logger.py`) ya detecta
inicio/fin de ciclo y registra lecturas en SQLite según los intervalos configurados en
`src/autoclave/config/global_params.json`:

- `intervalo_impresion` (fases W/H, warming/heating) — 180 s por defecto
- `intervalo_imprecion_esterilizacion` (fase S, esterilización) — 60 s por defecto
- además, cada cambio de fase fuerza un registro inmediato

Cada lectura registrada ya se marca `para_imprimir=1` en la DB. Hoy esa marca solo se
usa para construir un ticket bajo demanda vía
`GET /cycle/history/{id}/ticket.txt` (`ticket_formatter.format_ticket`). No existe
ningún envío a la impresora física durante el ciclo — el equipo no imprime nada hasta
que alguien pide el ticket por HTTP.

Esta fase conecta ambos lados: cuando `CycleLogger` decide que una lectura se registra,
esa misma línea se envía a la impresora térmica física en tiempo real, respetando los
intervalos ya configurados.

---

## Arquitectura

```
CycleLogger (hilo del control loop — no debe bloquearse)
   │ printer.enqueue(texto)
   ▼
RealtimePrinter (cola + hilo worker dedicado)
   │ print_raw(texto)   [win32_printer.py, ya existente]
   ▼
Impresora térmica física (PRINTER_NAME = "Impresora_Termica")
```

Ningún componente nuevo mantiene el handle de la impresora abierto entre eventos:
cada línea es su propio trabajo `StartDocPrinter` / `EndDocPrinter` (reutilizando
`print_raw` tal cual existe hoy). Esto evita mantener un handle abierto durante horas
y hace que un fallo puntual no comprometa el resto del ciclo.

---

## Componentes

### `src/autoclave/devices/printer/realtime_printer.py` (nuevo)

```python
class RealtimePrinter:
    def __init__(self, printer_name: str = PRINTER_NAME): ...
    def enqueue(self, text: str) -> None: ...   # no bloqueante
```

- Cola interna `queue.Queue`.
- Un hilo daemon arrancado en `__init__` consume la cola en orden (FIFO) y llama a
  `win32_printer.print_raw(text, printer_name)`.
- Si `print_raw` devuelve `False` o lanza, se loguea un warning y el worker sigue con
  el siguiente ítem — sin reintentos (best-effort, según lo acordado).
- Vive mientras viva el proceso; no expone `stop()` (mismo patrón que otros hilos
  daemon del proyecto, p. ej. el heartbeat de impresora).

### `src/autoclave/services/domain/logging/ticket_formatter.py` (refactor, sin romper compatibilidad)

Se extraen tres funciones puras a partir del `format_ticket` actual:

```python
def format_header(meta: dict) -> str: ...   # SEP, título, SEP, 4 renglones hdr(), DIV, col-header, DIV
def format_row(lectura: dict) -> str: ...   # una fila HORA/FASE/TEMP/PRES
def format_footer(resultado: str, fecha_fin: str) -> str: ...  # DIV, resultado, fin, SEP, ""
```

`format_ticket(ciclo, lecturas)` pasa a ser:

```python
"\n".join([format_header(meta_desde(ciclo))]
          + [format_row(r) for r in lecturas]
          + [format_footer(ciclo["resultado"], ciclo["fecha_fin"])])
```

Debe producir **byte a byte el mismo texto** que la implementación actual (se cubre
con un test de equivalencia). El endpoint `/cycle/history/{id}/ticket.txt` no cambia.

`meta` para `format_header` necesita: `numero_ciclo`, `serie`, `nombre_ciclo` (o
`tipo_ciclo`), `operador`, `temp_esterilizacion`, `tiempo_esterilizacion`,
`fecha_inicio`. `format_row` necesita: `fase_codigo`, `timestamp_rel`, `temp_camara`,
`pres_camara`.

### `src/autoclave/services/domain/logging/cycle_logger.py` (modificado)

- Constructor: nuevo parámetro opcional `printer=None`. Si es `None`, el
  comportamiento actual (solo DB) no cambia — usado en tests y en cualquier entorno
  sin impresora configurada.
- `_on_inicio()`: tras crear el registro en DB, si `self.printer` está seteado,
  construye el `meta` dict con los datos ya disponibles (numero, serie, tipo, nombre,
  temp_e, t_e, fecha_inicio=ahora, operador="") y hace
  `self.printer.enqueue(format_header(meta))`.
- `_registrar_lectura()`: tras el insert en DB, si `para_imprimir` y `self.printer`,
  construye la fila y hace `self.printer.enqueue(format_row(row))`.
- `_on_fin()`: tras `db.cerrar_ciclo(...)`, si `self.printer`, hace
  `self.printer.enqueue(format_footer(resultado, fecha_fin))` usando un
  `datetime.now()` capturado en ese momento (no se modifica `db_manager` para
  devolver el timestamp exacto; una diferencia de milisegundos entre el valor de DB y
  el impreso es aceptable).

### `src/autoclave/backend/context.py` (modificado)

```python
from autoclave.devices.printer.realtime_printer import RealtimePrinter
...
self.realtime_printer = RealtimePrinter()
self.cycle_logger = CycleLogger(
    db=self.db, estado=self.estado, config=self.config_manager,
    profile=self.profile, cycle_manager=self.cycle_manager,
    printer=self.realtime_printer,
)
```

---

## Flujo de datos

Sin cambios en la lógica de *cuándo* registrar (ya existente en `_tick`): cambio de
fase → registro inmediato; si no, cuando `ahora - ultimo_log >= intervalo` (leído de
`global_params.json` vía `ConfigManager`). Lo único nuevo es que cada registro que
hoy se escribe en SQLite con `para_imprimir=1` ahora **también** se encola para
impresión física, en el momento en que ocurre (tiempo real), no al pedir el ticket
después.

---

## Manejo de errores

- Impresora apagada/sin papel/offline en el momento de una línea → `print_raw` ya
  loguea warning y devuelve `False`; el worker de `RealtimePrinter` lo registra y
  continúa con el siguiente ítem de la cola. El ciclo y la DB no se ven afectados.
- Sin reintentos: la línea perdida sigue disponible en la DB y puede reimprimirse
  completa después vía `/cycle/history/{id}/ticket.txt`.
- Ningún error de impresión debe poder propagarse al hilo del control loop — por eso
  `enqueue()` es la única superficie que toca `CycleLogger`, y nunca lanza.

---

## Testing

- `tests/test_realtime_printer.py`: `enqueue` + worker llama a `print_raw`; un fallo
  de `print_raw` (excepción o `False`) no detiene el worker ni pierde los siguientes
  ítems de la cola.
- `tests/test_ticket_formatter.py`: `format_header` + filas + `format_footer`
  concatenados con `"\n".join(...)` producen exactamente el mismo texto que
  `format_ticket(ciclo, lecturas)` para un caso de ejemplo (test de equivalencia).
- Extensión de tests de `CycleLogger` (nuevo `tests/test_cycle_logger_printer.py`):
  con un printer doble (fake con `.enqueue` que solo acumula en una lista), verificar
  que `_on_inicio` encola un header, `_tick`/`_registrar_lectura` encola una fila
  cuando corresponde, y `_on_fin` encola un footer. Verificar también que con
  `printer=None` no hay ningún intento de llamar nada (no rompe el flujo actual).

---

## Fuera de alcance

- Cambios al formato visual del ticket (columnas, ancho, idioma).
- Reintentos automáticos de líneas fallidas.
- Alarmas/avisos en la UI ante fallos de impresión.
- Botón manual de "reimprimir ticket completo" (ya existe el endpoint HTTP; una UI
  para consumirlo queda fuera de esta fase).

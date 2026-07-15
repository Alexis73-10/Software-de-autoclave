# Impresión General: submenú + impresión de alarmas activas

**Fecha:** 2026-07-10

## Contexto

El menú principal (`HomeView`) tiene una tarjeta "🖨 Imprimir Ciclos" que navega directo a `CiclosView`. Se necesita:

1. Convertir esa tarjeta en una entrada genérica "Impresión General" que abra un submenú.
2. Dentro del submenú, mover la opción actual de ciclos y agregar una nueva opción "Imprimir Alarmas" que imprima todas las alarmas activas del sistema en ese momento.

El proyecto ya tiene un patrón establecido para submenús de este tipo: `EntradasSalidasMenuView` (`src/autoclave/ui_pyside/views/entrdas_salidas/io_menu.py`) — tarjeta blanca centrada con botón "←" de retorno y una lista vertical de botones que navegan por `view_name`.

El backend (`src/autoclave/backend/server.py`, endpoint `GET /status`) ya expone las alarmas activas (`estado.Alarmas_activas`, gestionadas por `AlarmManager`) pero solo serializa `id` y `level`; le faltan `description` y `source_state`, que sí existen en el objeto `Alarm` (`src/autoclave/state_machine/alarms/alarm.py`).

## Alcance

- Renombrar la tarjeta del home y crear el submenú "Impresión General".
- Mover la navegación de "Imprimir Ciclos" bajo ese submenú (la vista `CiclosView` no cambia funcionalmente, solo su botón de "Volver").
- Agregar la acción "Imprimir Alarmas": imprime un ticket con las alarmas activas actuales vía diálogo de impresión del sistema (igual mecanismo que "Imprimir seleccionados" en Ciclos).
- Extender `GET /status` para incluir `description` y `source_state` por alarma.

Fuera de alcance: no se crea una pantalla de listado/tabla de alarmas en la UI (la impresión es una acción directa desde el submenú), no se agrega timestamp a `Alarm` (no solicitado), no se modifica el acceso rápido del footer (sigue apuntando directo a `ciclos`).

## Diseño

### 1. Menú principal (`views/home.py`)

Cambiar la entrada de `cards_data`:

```python
(
    "🖨  Impresión General",
    "Imprime ciclos, alarmas y más",
    "impresion_menu",
),
```

### 2. Nuevo submenú (`views/impresion_menu.py`)

Nueva clase `ImpresionMenuView`, construida siguiendo el mismo patrón visual y estructural que `EntradasSalidasMenuView` (tarjeta blanca, botón "←" que navega a `home`, título, lista de opciones).

Lista de opciones (pensada para crecer con futuras impresiones):

```python
_PRINT_OPTIONS = [
    ("📋", "Imprimir Ciclos",  "ciclos"),   # navega a otra vista
    ("🚨", "Imprimir Alarmas", None),        # acción directa, no navega
]
```

- La opción "Imprimir Ciclos" conserva el comportamiento actual: navega a la vista `ciclos` (`self._nav("ciclos")`).
- La opción "Imprimir Alarmas" NO navega; su botón está conectado a un método `_print_alarms()` propio de `ImpresionMenuView` que ejecuta la acción de impresión en el momento (ver sección 4).

### 3. Vista de Ciclos (`views/ciclos.py`)

Único cambio: el botón "← Volver" pasa de `self._nav("home")` a `self._nav("impresion_menu")`, igual que hacen las vistas hijas de `io_menu` (`io_di`, `io_temp`, `io_pres`, `io_do`) respecto a su propio submenú.

### 4. Impresión de alarmas activas

En `ImpresionMenuView._print_alarms()`:

1. Instanciar `BackendClient` (mismo patrón que `_io_base.py`, `BACKEND_URL = "http://localhost:8000"`) y llamar `get_status()`.
2. Si la llamada falla (backend no disponible) o `status["alarms"]` viene vacío → `QMessageBox.information(self, "Alarmas", "No hay alarmas activas.")` y no se abre nada más. (Se unifica "sin alarmas" y "backend no disponible" en el mismo mensaje informativo, sin distinguir causa — no hay alarmas que mostrar en ambos casos).
3. Si hay alarmas → construir líneas de ticket y abrir `QPrintDialog` + `QPainter`, reusando las mismas constantes de papel térmico que `ciclos.py` (`_PAPER_W_MM = 55.0`, márgenes, `Courier New` 7pt), pero definidas/duplicadas localmente en `impresion_menu.py` (no se modifica `ciclos.py`).

Formato del ticket (texto plano, un bloque por alarma):

```
------------------------
ALARMAS ACTIVAS
Fecha: DD/MES/YYYY
Hora:  HH:MM:SS
------------------------
ID: <alarm.id>
Nivel: <ALERTA|FALLA|EMERGENCIA>
Origen: <source_state>
<description>
------------------------
... (repetido por cada alarma)
Total: N alarma(s)
------------------------
```

### 5. Backend (`server.py`)

Extender el bloque de alarmas en `GET /status`:

```python
alarms = [
    {
        "id": alarma.id,
        "level": alarma.type.name,
        "description": alarma.description,
        "source_state": alarma.source_state,
    }
    for alarma in estado.Alarmas_activas
]
```

Cambio aditivo y retrocompatible: no se elimina ni renombra ningún campo existente.

### 6. Registro de la vista (`main_window.py`)

- Importar `ImpresionMenuView`.
- Instanciar `self._impresion_menu = ImpresionMenuView(nav_callback=self.navigate_to)`.
- Agregar al `for view in (...)` que puebla el `QStackedWidget`.
- Agregar `"impresion_menu": self._impresion_menu` al diccionario de `navigate_to`.

## Errores y casos límite

- Sin alarmas activas → aviso informativo, no se abre diálogo de impresión (decisión confirmada con el usuario).
- Backend no disponible al pulsar "Imprimir Alarmas" → mismo aviso que "sin alarmas" (no se distingue la causa en el mensaje).
- Usuario cancela el `QPrintDialog` → no se imprime nada, sin mensajes adicionales (igual que en `ciclos.py`).

## Testing

Manual, vía skill `/verify`:
1. Levantar backend + UI.
2. Home → confirmar tarjeta "Impresión General".
3. Entrar al submenú → confirmar botón "← " vuelve a Home, y las dos opciones aparecen.
4. "Imprimir Ciclos" → confirmar que navega a la vista de ciclos existente y que su botón "Volver" regresa al submenú (no a Home).
5. "Imprimir Alarmas" sin alarmas activas → confirmar aviso, sin diálogo de impresión.
6. Forzar/generar una alarma activa (si es posible en el entorno de pruebas) → "Imprimir Alarmas" → confirmar que se abre el diálogo de impresión y el contenido del ticket incluye ID, nivel, origen y descripción.

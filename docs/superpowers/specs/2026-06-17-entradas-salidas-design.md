# Diseño: Menú Entradas / Salidas

**Fecha:** 2026-06-17  
**Rama:** dev  
**Estado:** Aprobado

---

## Contexto

El `AdminMenuView` tiene un botón "Entradas / Salidas" que actualmente muestra "próximamente". Este diseño define el submenu y las 4 vistas de diagnóstico que se abren desde él.

Datos disponibles en `GET /status`:
- `digital_inputs`: 14 canales nombrados (de `EstadoAutoclave.map_di`)
- `digital_outputs`: 24 canales nombrados (de `EstadoAutoclave.map_do`)
- `temperature`: 6 sensores (temp_camara, temp_2_camara, temp_ref, temp_chaqueta, temp_drenaje_cam, temp_drenaje)
- `pressure`: 4 sensores (pres_camara, pres_chaqueta, pres_empaque_1, pres_empaque_2)

---

## Arquitectura

### Archivos nuevos

| Archivo | Clase | Descripción |
|---|---|---|
| `views/io_menu.py` | `EntradasSalidasMenuView` | Submenú con 4 botones, estilo card blanca igual a AdminMenuView |
| `views/io_di.py` | `EntradasDigitalesView` | Grid de 14 entradas digitales, solo lectura |
| `views/io_temp.py` | `TemperaturasView` | Grid de 6 sensores de temperatura, solo lectura |
| `views/io_pres.py` | `PresionesView` | Grid de 4 sensores de presión, solo lectura |
| `views/io_do.py` | `SalidasDigitalesView` | Grid de 24 salidas + modo prueba interactivo |

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `main_window.py` | Registrar 5 vistas nuevas en `QStackedWidget` + 5 entradas en `navigate_to()` |
| `views/admin_menu.py` | `_option_clicked("Entradas / Salidas")` navega a `"io_menu"` en lugar de InfoBar |
| `backend/server.py` | 2 endpoints nuevos para modo prueba |

### Flujo de navegación

```
AdminMenuView
  └─ [Entradas / Salidas] ──► EntradasSalidasMenuView
                                  ├─ [Verificación ent. digitales] ──► EntradasDigitalesView
                                  ├─ [Sensores de temperatura]     ──► TemperaturasView
                                  ├─ [Sensores de presión]         ──► PresionesView
                                  └─ [Salidas digitales]           ──► SalidasDigitalesView
```

Todas las sub-vistas tienen `←` que regresa a `"io_menu"`.  
`EntradasSalidasMenuView` tiene `←` que regresa a `"admin_menu"`.

---

## Endpoints backend nuevos

### `POST /io/test/reset_all`
Apaga todas las salidas llamando a `context.setdo.reset_all_outputs()`.  
Respuesta: `{"ok": true}`

### `PATCH /io/test/output/{name}`
Body: `{"value": true | false}`  
Activa o desactiva una salida por nombre usando `EstadoAutoclave.map_do[name]` para obtener el índice y llamar a `context.setdo.set_output(index, value)`.  
Respuesta: `{"ok": true, "name": name, "value": value}`  
Error 404 si `name` no existe en `map_do`.

Estos endpoints solo están disponibles para uso diagnóstico (modo prueba). No se exponen en modo de ciclo activo (validación futura opcional).

---

## Sección 1: EntradasSalidasMenuView

Misma estructura visual que `AdminMenuView`: fondo degradado azul, card blanca centrada.

Opciones del menú:
```python
[
    ("🔍", "Verificación de entradas digitales"),
    ("🌡️", "Sensores de temperatura"),
    ("📊", "Sensores de presión"),
    ("⚡", "Salidas digitales"),
]
```

Cada botón navega a su vista correspondiente:  
`"io_di"`, `"io_temp"`, `"io_pres"`, `"io_do"`

---

## Sección 2: Vistas de monitoreo (DI, Temperaturas, Presiones)

### Patrón común

```
┌─ [←] TÍTULO ─────────────────────────────────────────┐
│                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ Nombre       │  │ Nombre       │  │ Nombre      │ │
│  │  ● ACTIVO    │  │  ○ INACTIVO  │  │  23.4 °C    │ │
│  └──────────────┘  └──────────────┘  └─────────────┘ │
│  ... grid 2-3 columnas                                 │
│                                                        │
│  ● Conectado  /  ○ Sin datos del backend               │
└────────────────────────────────────────────────────────┘
```

- **Poll**: `QTimer(interval=2000)`, arranca en `showEvent`, para en `hideEvent`.
- **Datos**: `BackendClient.get_status()` → clave correspondiente.
- **Error de conexión**: muestra indicador "Sin datos" sin romper la UI.

### EntradasDigitalesView
- 14 tarjetas en grid 2 columnas.
- Nombre: snake_case → Title Case (`"aire_comprimido"` → `"Aire comprimido"`).
- Indicador: círculo verde + "ACTIVO" si valor `1`, gris + "INACTIVO" si `0`.
- Fuente de datos: `status["sensors"]["digital_inputs"]`.

### TemperaturasView
- 6 tarjetas en grid 2 columnas.
- Valor en `°C` con 1 decimal: `"23.4 °C"`.
- Si valor es `None`: muestra `"---"` en color naranja (sensor desconectado).
- Fuente de datos: `status["sensors"]["temperature"]`.

### PresionesView
- 4 tarjetas en grid 2 columnas.
- Valor en `bar` con 2 decimales: `"1.23 bar"`.
- Fuente de datos: `status["sensors"]["pressure"]`.

---

## Sección 3: SalidasDigitalesView

### Modo normal (por defecto)

```
┌─ [←] SALIDAS DIGITALES ────────────── [🔧 Habilitar modo prueba] ─┐
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │
│  │ Vapor generador│  │ Vapor caldera  │  │ Vapor chaqueta │        │
│  │   ● ON         │  │   ○ OFF        │  │   ○ OFF        │        │
│  │ [ Activar ]    │  │ [ Activar ]    │  │ [ Activar ]    │        │
│  │ (deshabilitado)│  │ (deshabilitado)│  │ (deshabilitado)│        │
│  └────────────────┘  └────────────────┘  └────────────────┘        │
│  ... 24 tarjetas en grid 3 columnas                                  │
└──────────────────────────────────────────────────────────────────────┘
```

- Poll de 2s (igual que vistas de monitoreo).
- Los botones de toggle son visibles pero deshabilitados.
- Fuente de datos: `status["sensors"]["digital_outputs"]`.

### Activación del modo prueba

1. Usuario pulsa **"Habilitar modo prueba"**.
2. `QMessageBox.warning` con mensaje:
   > **"MODO PRUEBA — PRECAUCIÓN"**  
   > Esta función apaga todas las salidas activas y permite control manual de cada una.  
   > Use únicamente con conocimiento del sistema y personal capacitado.  
   > **¿Desea continuar?**"
3. Si acepta:
   - `POST /io/test/reset_all`
   - Banner en la parte superior cambia a fondo naranja oscuro: **"⚠ MODO PRUEBA ACTIVO"**
   - Botones de toggle se habilitan.
   - El botón cambia a **"Salir del modo prueba"** (rojo).

### En modo prueba activo

- Cada botón alterna ON/OFF al pulsar → `PATCH /io/test/output/{name}` con `{"value": true/false}`.
- El indicador de cada tarjeta se actualiza localmente inmediatamente (optimistic update) y luego el poll de 2s confirma el estado real.
- Poll de 2s sigue activo para reflejar cambios externos.

### Salir del modo prueba

- Pulsar "Salir del modo prueba" → `POST /io/test/reset_all` → vuelve a modo normal.
- Navegar fuera de la vista (`hideEvent`) mientras modo prueba está activo → automáticamente ejecuta `POST /io/test/reset_all` antes de ocultar.

---

## Consideraciones de implementación

- `BackendClient` ya existe en `autoclave.ui.service_ui.backend_client`. El re-export en `ui_pyside/services/backend_client.py` lo hace disponible para las vistas.
- Las 5 vistas nuevas se instancian en `MainWindowFluent.__init__` igual que las existentes.
- Los nombres de los canales (snake_case) se convierten a legibles con `.replace("_", " ").title()`.
- El `QTimer` en cada vista se conecta a `timeout` → método `_refresh()` que llama al backend en el hilo principal (llamadas síncronas de `requests` con timeout 0.8s ya definido en `BackendClient`).

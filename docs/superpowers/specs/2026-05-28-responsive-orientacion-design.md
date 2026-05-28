# Diseño: UI Responsive a Orientación y Relación de Aspecto

**Fecha:** 2026-05-28  
**Estado:** Aprobado — pendiente de plan de implementación  

---

## Contexto

El software de autoclave corre en pantalla completa sobre Windows. Hay dos tipos de pantalla en uso:

- **13" — 1920×1080** — orientación cambia vía Windows Settings (Configuración → Pantalla → Orientación)
- **8" — 1280×800** — puede rotar físicamente entre landscape y portrait

Ambos casos generan un evento `<Configure>` de Tkinter con las nuevas dimensiones. El mecanismo de respuesta es idéntico para los dos monitores.

El frontend actual (Tkinter + CustomTkinter) ya usa `place(relx, rely, relwidth, relheight)` en toda la UI, lo que lo hace ~60% responsive. Lo que falta: escalado de fuentes, alturas de header/footer relativas, y layouts alternativos para orientación portrait.

---

## Enfoque elegido: Dos métodos de layout dentro de la misma clase

Cada ventana (`InterfazPrincipal`, `CycleWindow`) tiene `_build_body_landscape()` y `_build_body_portrait()`. Al detectar un cambio de orientación, se destruyen los widgets internos y se llama al método correcto — la ventana sobrevive y el estado del ciclo no se pierde.

---

## Archivo nuevo: `src/autoclave/ui/layout.py`

Tres funciones sin estado, sin dependencias de Tkinter, compartidas por ambas ventanas:

```python
def is_portrait(w: int, h: int) -> bool:
    return h > w

def font_scale(w: int, h: int) -> float:
    # Referencia: min(1920, 1080) = 1080 → escala 1.0
    return min(w, h) / 1080

def scaled_font(base: int, scale: float) -> int:
    return max(8, int(base * scale))
```

### Tabla de escalas por pantalla

| Pantalla | Resolución | min(w,h) | scale | Fuente 90pt | Fuente 22pt | Fuente 14pt |
|---|---|---|---|---|---|---|
| 13" portrait | 1080×1920 | 1080 | 1.00 | 90pt | 22pt | 14pt |
| PC actual landscape | 1920×1080 | 1080 | 1.00 | 90pt | 22pt | 14pt |
| 8" landscape | 1280×800 | 800 | 0.74 | 67pt | 16pt | 10pt |
| 8" portrait | 800×1280 | 800 | 0.74 | 67pt | 16pt | 10pt |

---

## Header y Footer — alturas relativas

Reemplazan los valores fijos actuales (`height=58` y `height=90`):

| Elemento | Antes | Después | En 1920h | En 1280h |
|---|---|---|---|---|
| Header | 58 px fijos | `int(sh × 0.04)` | 77 px | 51 px |
| Footer | 90 px fijos | `int(sh × 0.065)` | 125 px | 83 px |

---

## `InterfazPrincipal` — estructura actualizada

```python
class InterfazPrincipal(tk.Tk):

    def __init__(self, ...):
        # setup existente sin cambios...
        self._current_portrait = None
        self._update_job = None
        self._resize_job = None
        self._build_ui()
        self.bind("<Configure>", self._on_configure)

    def _build_ui(self):
        w = self.winfo_screenwidth()
        h = self.winfo_screenheight()
        scale = font_scale(w, h)
        self._build_header(scale)
        if is_portrait(w, h):
            self._build_body_portrait(w, h, scale)
        else:
            self._build_body_landscape(w, h, scale)   # ≈ código actual
        self._build_footer(scale)

    def _on_configure(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(
            150, lambda: self._check_orientation(event.width, event.height)
        )

    def _check_orientation(self, w, h):
        if w < 100 or h < 100:
            return
        portrait = h > w
        if self._current_portrait is None:
            self._current_portrait = portrait
            return
        if portrait != self._current_portrait:
            self._current_portrait = portrait
            self._rebuild_layout()

    def _rebuild_layout(self):
        if self._update_job:
            self.after_cancel(self._update_job)
            self._update_job = None
        for child in self.winfo_children():
            child.destroy()
        self._build_ui()
        self._load_action_images()
        self._schedule_update()
```

---

## Layout Portrait de `InterfazPrincipal` — Opción A

Tres zonas apiladas verticalmente dentro de la tarjeta blanca (`relwidth=0.96, relheight=0.94`):

### Zona 1 — Banda de estado (oscura)

`place(relx=0.02, rely=0.03, relwidth=0.96, relheight=0.22)`

| Elemento | Posición | Fuente base |
|---|---|---|
| Nº ciclo "01" | relx=0.12, rely=0.5, anchor=center | `scaled_font(90, scale)` |
| Separador vertical | relx=0.27, rely=0.1, relwidth=0.003, relheight=0.8 | — |
| Nombre ciclo | relx=0.63, rely=0.22, anchor=center | `scaled_font(30, scale)` |
| Estado máquina | relx=0.63, rely=0.52, anchor=center | `scaled_font(22, scale)` |
| Condiciones ×3 | relx=0.63, rely=0.70 + i×0.065 | `scaled_font(14, scale)` |

Con 22% de altura (vs 18% propuesto inicialmente), el lado derecho tiene espacio para:
- Nombre del ciclo en fuente más grande (`scaled_font(30, scale)` — subida de 26→30)
- Hasta **3 condiciones/alarmas** visibles (vs 2 anteriores)

### Zona 2 — Grid de pills 2×3

`place(relx=0.02, rely=0.27, relwidth=0.96, relheight=0.34)`

6 pills en grid de 2 columnas, 3 filas:

| Columna izquierda (parámetros ciclo) | Columna derecha (sensores en vivo) |
|---|---|
| Temp. Esterilización | Temp. Cámara |
| Tiempo Esterilización | Temp. Referencia |
| Tiempo Secado | Presión Cámara |

Cada pill: `relwidth=0.485`, `relheight=0.30` dentro de la zona, gaps de 0.03.  
Fuentes: label `scaled_font(18, scale)`, valor `scaled_font(20, scale)`, unidad `scaled_font(15, scale)`.

### Zona 3 — Acción

`place(relx=0.02, rely=0.63, relwidth=0.96, relheight=0.28)`

Dos botones grandes de ancho igual (`relwidth=0.46` cada uno):
- **Puerta**: imagen `open_door_N.png` / `close_door_N.png` + etiqueta "PUERTA"
- **Iniciar / Reset Falla**: imagen `start_cycle.png` + etiqueta "INICIAR"

Altura de botón en 13" portrait: ~323 px. En 8" portrait: ~215 px. Ambos táctiles con guantes.

### Suma de zonas

```
Banda estado   0.22
Gaps + sep.    0.04
Grid pills     0.34
Zona acción    0.28
Padding inf.   0.09
─────────────  0.97  ✅
```

---

## `CycleWindow` — Layout Portrait

Zonas apiladas verticalmente dentro de la tarjeta:

| Zona | rely | relheight | Detalle |
|---|---|---|---|
| Nombre ciclo | 0.02 | 0.06 | `scaled_font(34, scale)`, texto centrado |
| Pill de fase | 0.10 | 0.10 | Nombre fase izq + timer/temp der, `scaled_font(20, scale)` |
| **LiveGraph** | **0.22** | **0.44** | Ancho completo de la tarjeta — sin cambios en `live_graph.py` |
| Sensores ×3 | 0.68 | 0.13 | 3 pills en fila horizontal, `scaled_font(18/20, scale)` |
| Puertas + acción | 0.83 | 0.14 | Iconos puertas izq + botón Abortar/Confirmar ocupa ancho restante |

**La gráfica en portrait es más ancha que en landscape** (100% del ancho de la tarjeta vs. 62% en landscape) — el operador tiene más resolución horizontal en la curva T/P.

`LiveGraph` no requiere cambios: ya usa `pack(fill=tk.BOTH, expand=True)`.

---

## `CycleWindow` — Footer actualizado (landscape y portrait)

El footer de `CycleWindow` pasa de tener solo el label de estado a tener la misma estructura que `InterfazPrincipal`:

```
[ ℹ️  ⚙️ ]  [  Ciclo en progreso...  ]  [ — ]
  pill izq        pill central (flex)      derecha libre
```

Los botones ℹ️ y ⚙️ quedan accesibles durante el ciclo a pesar del `grab_set()`.

Implementación en `_build_footer(scale)`:
- `pill_left`: `place(relx=0.01, rely=0.5, anchor="w", relwidth=0.20, relheight=0.82)` con los dos botones
- `pill_center`: `place(relx=0.5, rely=0.5, anchor="center", relwidth=0.52, relheight=0.82)` con `_lbl_estado`

Los iconos (`_img_info`, `_img_settings`) se cargan en `CycleWindow._load_images()`. Para evitar duplicar código, se extraen a `load_footer_icons(scale)` en `layout.py`.

---

## Detección de orientación — mecanismo unificado

El mismo código maneja ambos monitores:

| Monitor | Cómo rota | Efecto en Tkinter |
|---|---|---|
| 13" 1920×1080 | Windows Settings → Orientación | `<Configure>` con 1080×1920 |
| 8" 1280×800 | Rotación física | `<Configure>` con 800×1280 |

### Flujo

```
OS cambia resolución
  → Tkinter dispara <Configure> en la ventana fullscreen
  → _on_configure: filtrar eventos de widgets hijos, debounce 150ms
  → _check_orientation: comparar h > w con _current_portrait anterior
  → si cambió: _rebuild_layout()
    → cancelar _update_job
    → destruir widgets hijos (no la ventana)
    → _build_ui() con nuevas dimensiones
    → _load_action_images()
    → _schedule_update()
```

El debounce de 150ms absorbe los múltiples `<Configure>` que el OS puede enviar durante la transición.

### Estado que sobrevive al rebuild

**`InterfazPrincipal`**: `ui_service`, `door_commands`, `_source_door`, `_door_name`, `_on_shutdown`, referencia a `CycleWindow`, `_current_portrait`.

**`CycleWindow`**: `_buffer` (todos los puntos T/P), `_ciclo_activo_detectado`, `_ciclo_terminado`, `_hold_start_time`, `_fase_temp_targets`. El `grab_set()` se re-aplica tras el rebuild.

---

## Notas de implementación

- **`_build_body_landscape`** es el `_build_body()` actual renombrado, con `scale` añadido como parámetro y todas las fuentes reemplazadas por `scaled_font(base, scale)`. El contenido de los paneles no cambia.
- **`_schedule_update()`** es un nuevo método auxiliar que reemplaza el `self.after(500, self._update_ui)` actual, devolviendo el job handle para poder cancelarlo en `_rebuild_layout`. El loop de polling en sí no cambia.
- **`load_footer_icons(scale)`** en `layout.py` carga los `CTkImage` de ℹ️ y ⚙️ con tamaño `(scaled_font(46, scale), scaled_font(40, scale))`, igual que hace `InterfazPrincipal._build_footer` hoy, pero compartido con `CycleWindow`.

---

## Archivos afectados

| Archivo | Tipo de cambio |
|---|---|
| `src/autoclave/ui/layout.py` | **Nuevo** — `is_portrait`, `font_scale`, `scaled_font`, `load_footer_icons` |
| `src/autoclave/ui/window/main_window.py` | Principal — añadir métodos de layout, `<Configure>`, alturas relativas |
| `src/autoclave/ui/cycle/cycle_window.py` | Secundario — layout portrait, footer con info/settings, `<Configure>` |
| `src/autoclave/ui/cycle/widgets/phase_indicator.py` | Menor — aceptar `font_size` como parámetro |
| `src/autoclave/ui/cycle/widgets/live_graph.py` | **Sin cambios** |

---

## Lo que ya funciona sin cambios

- `place(relx, rely, relwidth, relheight)` en toda la UI — las zonas se escalan solas
- `LiveGraph` — usa `pack(fill=BOTH, expand=True)`, se adapta solo
- Imágenes de botones — ya calculadas con `int(sw × 0.085)` y `int(sh × 0.15)`
- Pill del footer — ya usa `relwidth=0.52`

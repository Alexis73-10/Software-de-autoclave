# UI Responsive a Orientación y Relación de Aspecto — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que la UI de autoclave se adapte automáticamente entre orientación landscape y portrait en monitores de 13" (1920×1080) y 8" (1280×800), con fuentes escaladas y layouts distintos por orientación.

**Architecture:** Se añade un archivo `layout.py` con helpers puros (escalado de fuentes, detección de orientación). Cada ventana (`InterfazPrincipal`, `CycleWindow`) gana dos métodos de construcción de body (`_build_body_landscape`, `_build_body_portrait`) y un handler de evento `<Configure>` que detecta flips y reconstruye la UI sin destruir la ventana ni perder datos del ciclo.

**Tech Stack:** Python 3.14, Tkinter, CustomTkinter, PIL/Pillow, matplotlib (ya en uso)

**Spec:** `docs/superpowers/specs/2026-05-28-responsive-orientacion-design.md`

---

## Mapa de archivos

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `src/autoclave/ui/layout.py` | **Crear** | Helpers puros: font_scale, is_portrait, scaled_font, check_orientation_changed, load_footer_icons |
| `src/autoclave/ui/window/main_window.py` | **Modificar** | Layout portrait + landscape, _build_ui, <Configure>, header/footer relativos |
| `src/autoclave/ui/cycle/cycle_window.py` | **Modificar** | Layout portrait, footer con info/settings, <Configure> |
| `src/autoclave/ui/cycle/widgets/phase_indicator.py` | **Modificar** | Aceptar font_size como parámetro |
| `tests/test_ui_layout.py` | **Crear** | Tests de helpers puros y PhaseIndicator |

`live_graph.py` no requiere cambios.

---

## Task 1: Crear `layout.py` con helpers puros

**Files:**
- Create: `src/autoclave/ui/layout.py`
- Test: `tests/test_ui_layout.py`

- [ ] **Step 1.1: Escribir los tests primero**

Crear `tests/test_ui_layout.py`:

```python
import pytest
from autoclave.ui.layout import (
    is_portrait, font_scale, scaled_font, check_orientation_changed
)


def test_is_portrait_landscape():
    assert is_portrait(1920, 1080) is False


def test_is_portrait_portrait():
    assert is_portrait(1080, 1920) is True


def test_is_portrait_square():
    assert is_portrait(1000, 1000) is False


def test_font_scale_reference_landscape():
    assert font_scale(1920, 1080) == pytest.approx(1.0)


def test_font_scale_reference_portrait_13():
    # 13" girado: min sigue siendo 1080
    assert font_scale(1080, 1920) == pytest.approx(1.0)


def test_font_scale_8inch_landscape():
    assert font_scale(1280, 800) == pytest.approx(800 / 1080)


def test_font_scale_8inch_portrait():
    # misma escala en ambas orientaciones del 8"
    assert font_scale(800, 1280) == pytest.approx(800 / 1080)


def test_scaled_font_scale_1():
    assert scaled_font(90, 1.0) == 90


def test_scaled_font_scaled_down():
    assert scaled_font(90, 0.74) == int(90 * 0.74)


def test_scaled_font_minimum():
    assert scaled_font(14, 0.1) == 8


# check_orientation_changed(w, h, current) → (new_portrait, should_rebuild)

def test_check_first_call_landscape():
    portrait, rebuild = check_orientation_changed(1920, 1080, None)
    assert portrait is False
    assert rebuild is False  # primer llamado: solo registrar, no rebuild


def test_check_first_call_portrait():
    portrait, rebuild = check_orientation_changed(1080, 1920, None)
    assert portrait is True
    assert rebuild is False


def test_check_same_orientation():
    portrait, rebuild = check_orientation_changed(1920, 1080, False)
    assert portrait is False
    assert rebuild is False  # sin cambio


def test_check_flip_to_portrait():
    portrait, rebuild = check_orientation_changed(1080, 1920, False)
    assert portrait is True
    assert rebuild is True  # flip → rebuild


def test_check_flip_to_landscape():
    portrait, rebuild = check_orientation_changed(1920, 1080, True)
    assert portrait is False
    assert rebuild is True


def test_check_too_small_dimensions():
    portrait, rebuild = check_orientation_changed(50, 50, False)
    assert rebuild is False  # ignorar dimensiones transitorias
```

- [ ] **Step 1.2: Correr los tests — verificar que fallan**

```
pytest tests/test_ui_layout.py -v
```

Resultado esperado: `ModuleNotFoundError: No module named 'autoclave.ui.layout'`

- [ ] **Step 1.3: Crear `src/autoclave/ui/layout.py`**

```python
from __future__ import annotations
import PIL.Image as Image
import customtkinter as ctk
from autoclave.utils.resources import resource_path


def is_portrait(w: int, h: int) -> bool:
    return h > w


def font_scale(w: int, h: int) -> float:
    return min(w, h) / 1080


def scaled_font(base: int, scale: float) -> int:
    return max(8, int(base * scale))


def check_orientation_changed(
    w: int, h: int, current_portrait: bool | None
) -> tuple[bool | None, bool]:
    """
    Retorna (new_portrait, should_rebuild).
    should_rebuild es True solo cuando la orientación cambió respecto a current_portrait.
    """
    if w < 100 or h < 100:
        return current_portrait, False
    portrait = h > w
    if current_portrait is None:
        return portrait, False
    return portrait, portrait != current_portrait


def load_footer_icons(scale: float) -> dict:
    """Carga CTkImage para los iconos del footer (info y settings)."""
    w = scaled_font(46, scale)
    h = scaled_font(40, scale)
    size = (w, h)

    def _ico(name):
        img = Image.open(resource_path(f"autoclave/images/{name}"))
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)

    return {
        "info": _ico("info_icon.png"),
        "settings": _ico("settings_icon.png"),
    }
```

- [ ] **Step 1.4: Correr los tests — verificar que pasan**

```
pytest tests/test_ui_layout.py -v
```

Resultado esperado: todos los tests en verde (`PASSED`).

- [ ] **Step 1.5: Commit**

```bash
git add src/autoclave/ui/layout.py tests/test_ui_layout.py
git commit -m "feat: layout.py — helpers de escala de fuente y detección de orientación"
```

---

## Task 2: Actualizar `PhaseIndicator` para aceptar tamaños de fuente

**Files:**
- Modify: `src/autoclave/ui/cycle/widgets/phase_indicator.py`
- Test: `tests/test_ui_layout.py` (ampliar)

- [ ] **Step 2.1: Añadir test de PhaseIndicator al archivo de tests**

Añadir al final de `tests/test_ui_layout.py`:

```python
import tkinter as tk
from autoclave.ui.cycle.widgets.phase_indicator import PhaseIndicator


def test_phase_indicator_default_fonts():
    root = tk.Tk()
    root.withdraw()
    try:
        ind = PhaseIndicator(root)
        root.update()
        # Verificar que los defaults son 22 y 20
        assert ind._font_size_label == 22
        assert ind._font_size_timer == 20
    finally:
        root.destroy()


def test_phase_indicator_custom_fonts():
    root = tk.Tk()
    root.withdraw()
    try:
        ind = PhaseIndicator(root, font_size_label=16, font_size_timer=14)
        root.update()
        assert ind._font_size_label == 16
        assert ind._font_size_timer == 14
    finally:
        root.destroy()


def test_phase_indicator_update_no_crash():
    root = tk.Tk()
    root.withdraw()
    try:
        ind = PhaseIndicator(root, font_size_label=16, font_size_timer=14)
        ind.update("ESTERILIZACION", 2.0, 4.0)
        ind.update_approach("CALENTAMIENTO", 87.0, 134.0, "°C")
        ind.update_info("PRE_VACIO", "A 1/4")
        root.update()
    finally:
        root.destroy()
```

- [ ] **Step 2.2: Correr tests — verificar que fallan**

```
pytest tests/test_ui_layout.py::test_phase_indicator_default_fonts -v
```

Resultado esperado: `AttributeError: 'PhaseIndicator' object has no attribute '_font_size_label'`

- [ ] **Step 2.3: Modificar `phase_indicator.py`**

Cambiar el `__init__` de `PhaseIndicator` en `src/autoclave/ui/cycle/widgets/phase_indicator.py`:

```python
def __init__(self, parent, bg_color: str = "#ffffff",
             font_size_label: int = 22, font_size_timer: int = 20, **kwargs):
    super().__init__(
        parent,
        corner_radius=30,
        fg_color=CLR_DARK,
        bg_color=bg_color,
        **kwargs,
    )
    self._font_size_label = font_size_label
    self._font_size_timer = font_size_timer

    self._lbl_fase = ctk.CTkLabel(
        self,
        text="---",
        font=("Segoe UI", font_size_label, "bold"),
        text_color=CLR_W,
        fg_color="transparent",
        anchor="w",
    )
    self._lbl_fase.pack(side="left", padx=24, pady=0, fill="y")

    self._lbl_timer = ctk.CTkLabel(
        self,
        text="",
        font=("Segoe UI", font_size_timer),
        text_color=CLR_W,
        fg_color="transparent",
        anchor="e",
    )
    self._lbl_timer.pack(side="right", padx=24, pady=0, fill="y")
```

El resto de los métodos (`update`, `update_info`, `update_approach`) no cambian.

- [ ] **Step 2.4: Correr todos los tests de layout**

```
pytest tests/test_ui_layout.py -v
```

Resultado esperado: todos en verde.

- [ ] **Step 2.5: Commit**

```bash
git add src/autoclave/ui/cycle/widgets/phase_indicator.py tests/test_ui_layout.py
git commit -m "feat: PhaseIndicator acepta font_size_label y font_size_timer como parámetros"
```

---

## Task 3: Refactorizar `InterfazPrincipal` — font scaling + header/footer relativos + `_build_ui()`

Este task convierte el código existente para usar `scaled_font` e introduce `_build_ui()` como punto de entrada único. No cambia el layout landscape — solo aplica la escala.

**Files:**
- Modify: `src/autoclave/ui/window/main_window.py`

- [ ] **Step 3.1: Añadir imports en `main_window.py`**

Al inicio del archivo, después de los imports existentes, añadir:

```python
from autoclave.ui.layout import (
    is_portrait, font_scale, scaled_font,
    check_orientation_changed, load_footer_icons,
)
```

- [ ] **Step 3.2: Añadir atributos de control en `__init__`**

En `InterfazPrincipal.__init__`, antes del bloque `# ── construir UI ──`, añadir:

```python
self._scale          = 1.0   # factor de escala de fuente, calculado en _build_ui
self._current_portrait = None  # None = no determinado todavía
self._update_job     = None  # handle del after() del loop de polling
self._resize_job     = None  # handle del debounce de <Configure>
```

- [ ] **Step 3.3: Reemplazar las llamadas de construcción en `__init__`**

Sustituir el bloque actual:

```python
        # ── construir UI ──────────────────────────────────────────────────────
        self._build_header()
        self._build_body()
        self._build_footer()

        # ── arrancar loop ─────────────────────────────────────────────────────
        self.after(300, self._load_action_images)   # cargar imágenes después de fullscreen
        self.after(500, self._update_ui)
```

Por:

```python
        # ── construir UI ──────────────────────────────────────────────────────
        self._build_ui()

        # ── arrancar loop e imagen ────────────────────────────────────────────
        self.after(300, self._load_action_images)
        self._schedule_update()

        # ── detección de orientación (para ambos monitores) ───────────────────
        self.bind("<Configure>", self._on_configure)
```

- [ ] **Step 3.4: Añadir `_build_ui()` y `_schedule_update()`**

Añadir justo después del bloque `__init__`, antes de `_build_header`:

```python
    # ══════════════════════════════════════════════════════════════════════════
    # PUNTO DE ENTRADA DE CONSTRUCCIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self._scale = font_scale(sw, sh)
        self._build_header(sh)
        if is_portrait(sw, sh):
            self._build_body_portrait(sw, sh)
        else:
            self._build_body_landscape(sw, sh)
        self._build_footer(sh)

    def _schedule_update(self):
        self._update_job = self.after(500, self._run_update)

    def _run_update(self):
        self._update_ui()
        self._update_job = self.after(500, self._run_update)
```

- [ ] **Step 3.5: Actualizar `_build_header` para recibir `sh` y usar escala**

Cambiar la firma y el contenido de `_build_header`:

```python
    def _build_header(self, sh: int):
        hdr = tk.Frame(self, bg=CLR_DARK, height=int(sh * 0.04))
        hdr.pack(fill=tk.X, side=tk.TOP)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="ESPECIFIKA S.A.S",
                 font=("Segoe UI", scaled_font(14, self._scale), "italic"),
                 bg=CLR_DARK, fg=CLR_W).pack(side=tk.LEFT, padx=20)

        self._lbl_modelo = tk.Label(hdr, text="AUTOCLAVE",
                                     font=("Segoe UI", scaled_font(16, self._scale), "bold"),
                                     bg=CLR_DARK, fg=CLR_W)
        self._lbl_modelo.pack(side=tk.LEFT, expand=True)

        self._lbl_hora = tk.Label(hdr, text="",
                                   font=("Segoe UI", scaled_font(14, self._scale)),
                                   bg=CLR_DARK, fg=CLR_W)
        self._lbl_hora.pack(side=tk.RIGHT, padx=20)
        self._tick_hora()
```

- [ ] **Step 3.6: Renombrar `_build_body` → `_build_body_landscape` y añadir parámetros**

Cambiar la firma de `_build_body` a `_build_body_landscape(self, sw: int, sh: int)` y actualizar todos los `font=("Segoe UI", N, ...)` dentro de ella usando `scaled_font(N, self._scale)`:

En `_build_body_landscape`, los cambios son:
- `_lbl_n_ciclo`: `font=("Segoe UI", scaled_font(90, self._scale), "bold")`
- `_lbl_estado`: `font=("Segoe UI", scaled_font(22, self._scale), "bold")`, `wraplength=int(sw * 0.10)`
- `_lbl_cond` (cada uno): `font=("Segoe UI", scaled_font(16, self._scale))`
- `_lbl_ciclo_nombre`: `font=("Segoe UI", scaled_font(46, self._scale), "bold")`

Añadir también al final de `_build_body_landscape`, antes de `self._panel_der = pnl`:
```python
        # Guardar coordenadas "home" del botón iniciar para _upd_panel_izquierdo
        self._boton_iniciar_pos  = dict(relx=0.79, rely=0.76, relwidth=0.16, relheight=0.21)
        self._btn_reset_falla_pos = dict(relx=0.30, rely=0.76, relwidth=0.65, relheight=0.21)
```

- [ ] **Step 3.7: Actualizar `_pill` para usar `self._scale`**

Cambiar la firma de `_pill` y reemplazar los `font=` internos:

```python
    def _pill(self, parent, label, value, unit, relx, rely, relwidth, relheight):
        frame = ctk.CTkFrame(parent, corner_radius=30,
                            fg_color=CLR_DARK, bg_color=CLR_CARD)
        frame.place(relx=relx, rely=rely, relwidth=relwidth, relheight=relheight)

        ctk.CTkLabel(frame, text=label,
                     font=("Segoe UI", scaled_font(18, self._scale), "bold"),
                     text_color=CLR_W, fg_color="transparent",
                     anchor="w").place(relx=0.05, rely=0.5, anchor="w")

        ctk.CTkLabel(frame, text=unit,
                     font=("Segoe UI", scaled_font(15, self._scale)),
                     text_color=CLR_W, fg_color="transparent",
                     anchor="e").place(relx=0.97, rely=0.5, anchor="e")

        lbl_val = ctk.CTkLabel(frame, text=value,
                                font=("Segoe UI", scaled_font(20, self._scale), "bold"),
                                text_color=CLR_W, fg_color="transparent",
                                anchor="e")
        lbl_val.place(relx=0.74, rely=0.5, anchor="e")
        return lbl_val
```

- [ ] **Step 3.8: Actualizar `_build_footer` para recibir `sh` y usar escala**

```python
    def _build_footer(self, sh: int):
        footer = tk.Frame(self, bg=CLR_BG, height=int(sh * 0.065))
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        pill = ctk.CTkFrame(footer, corner_radius=45,
                             fg_color=CLR_FOOTER, bg_color=CLR_BG)
        pill.place(relx=0.5, rely=0.5, anchor="center",
                   relwidth=0.52, relheight=0.82)

        icons = load_footer_icons(self._scale)

        ctk.CTkButton(pill, text="", image=icons["info"],
                      fg_color="transparent", hover_color="#406080",
                      width=scaled_font(56, self._scale)).pack(side=tk.LEFT, padx=18)

        ctk.CTkButton(pill, text="", image=icons["settings"],
                      fg_color="transparent", hover_color="#406080",
                      width=scaled_font(56, self._scale)).pack(side=tk.LEFT, padx=8)

        img_off = load_footer_icons(self._scale)   # carga power icon separado
        _img_off_raw = __import__('PIL').Image.open(
            __import__('autoclave.utils.resources', fromlist=['resource_path']).resource_path(
                "autoclave/images/power_icon.png"))
        self._img_OFF = ctk.CTkImage(
            light_image=_img_off_raw, dark_image=_img_off_raw,
            size=(scaled_font(46, self._scale), scaled_font(40, self._scale)))

        ctk.CTkButton(pill, text="", image=self._img_OFF,
                      fg_color="transparent", hover_color="#406080",
                      command=self.apagar_equipo,
                      width=scaled_font(56, self._scale)).pack(side=tk.RIGHT, padx=18)

        self._lbl_conexion = tk.Label(footer, text="⚪ Conectando...",
                                       font=("Segoe UI", scaled_font(12, self._scale)),
                                       bg=CLR_BG, fg="white")
        self._lbl_conexion.place(relx=0.01, rely=0.5, anchor="w")

        self._lbl_suministro = tk.Label(
            footer,
            text="⚡ Suministro: OK",
            font=("Segoe UI", scaled_font(12, self._scale)),
            bg=CLR_BG,
            fg="#7FFF7F",
        )
        self._lbl_suministro.place(relx=0.17, rely=0.5, anchor="w")
```

> **Nota:** El power icon se carga aquí directamente. En una segunda pasada se puede refactorizar `load_footer_icons` para incluirlo también, pero por ahora es suficiente para hacer funcionar el código.

- [ ] **Step 3.9: Actualizar `_upd_panel_izquierdo` para usar `_boton_iniciar_pos`**

Reemplazar las dos ocurrencias de `place()` dentro de `_upd_panel_izquierdo`:

```python
        en_falla = (estado == "FALLA")
        if en_falla:
            self._boton_iniciar.place_forget()
            self._btn_reset_falla.place(**self._btn_reset_falla_pos)
        else:
            self._btn_reset_falla.place_forget()
            self._boton_iniciar.place(**self._boton_iniciar_pos)
```

- [ ] **Step 3.10: Arrancar la app y verificar que landscape funciona igual**

```
python -m autoclave.ui.main
```

La pantalla landscape debe verse igual que antes. Verificar:
- Fuentes del mismo tamaño visual (escala 1.0 en 1920×1080)
- Header y footer proporcionales
- Pills, botones y labels sin cortes

- [ ] **Step 3.11: Commit**

```bash
git add src/autoclave/ui/window/main_window.py src/autoclave/ui/layout.py
git commit -m "refactor: InterfazPrincipal usa font scaling y alturas relativas — landscape sin cambio visual"
```

---

## Task 4: Añadir `_build_body_portrait` a `InterfazPrincipal`

**Files:**
- Modify: `src/autoclave/ui/window/main_window.py`

- [ ] **Step 4.1: Añadir `_build_body_portrait` después de `_build_body_landscape`**

```python
    # ══════════════════════════════════════════════════════════════════════════
    # BODY PORTRAIT  (banda estado + grid pills + zona acción)
    # ══════════════════════════════════════════════════════════════════════════

    def _build_body_portrait(self, sw: int, sh: int):
        self._body_bg = tk.Frame(self, bg=CLR_BG)
        self._body_bg.pack(fill=tk.BOTH, expand=True)

        self._card = ctk.CTkFrame(self._body_bg, corner_radius=28,
                                   fg_color=CLR_CARD, bg_color=CLR_BG)
        self._card.place(relx=0.02, rely=0.03, relwidth=0.96, relheight=0.94)

        # ── Banda de estado (22%) ─────────────────────────────────────────────
        band = ctk.CTkFrame(self._card, corner_radius=16,
                            fg_color=CLR_DARK, bg_color=CLR_CARD)
        band.place(relx=0.02, rely=0.03, relwidth=0.96, relheight=0.22)

        self._lbl_n_ciclo = ctk.CTkLabel(
            band, text="01",
            font=("Segoe UI", scaled_font(90, self._scale), "bold"),
            text_color=CLR_W, fg_color="transparent")
        self._lbl_n_ciclo.place(relx=0.12, rely=0.5, anchor="center")

        ctk.CTkFrame(band, fg_color="#ffffff", corner_radius=0,
                     bg_color=CLR_DARK).place(
            relx=0.27, rely=0.1, relwidth=0.003, relheight=0.8)

        self._lbl_ciclo_nombre = ctk.CTkLabel(
            band, text=self.cycle_name.upper(),
            font=("Segoe UI", scaled_font(30, self._scale), "bold"),
            text_color=CLR_W, fg_color="transparent")
        self._lbl_ciclo_nombre.place(relx=0.63, rely=0.22, anchor="center")

        self._lbl_estado = ctk.CTkLabel(
            band, text="Cargando...",
            font=("Segoe UI", scaled_font(22, self._scale), "bold"),
            text_color=CLR_W, fg_color="transparent",
            wraplength=int(sw * 0.55))
        self._lbl_estado.place(relx=0.63, rely=0.52, anchor="center")

        self._lbl_cond = []
        for i in range(_MAX_COND):
            lbl = ctk.CTkLabel(
                band, text="",
                font=("Segoe UI", scaled_font(14, self._scale)),
                text_color=CLR_W, fg_color="transparent")
            lbl.place(relx=0.63, rely=0.70 + i * 0.065, anchor="center")
            self._lbl_cond.append(lbl)

        # ── Grid de pills 2×3 (34%) ───────────────────────────────────────────
        pills_zone = ctk.CTkFrame(self._card, corner_radius=0,
                                   fg_color=CLR_CARD, bg_color=CLR_CARD)
        pills_zone.place(relx=0.02, rely=0.27, relwidth=0.96, relheight=0.34)

        PW, PH = 0.485, 0.30
        cols = [0.0, 0.515]
        rows = [0.02, 0.36, 0.68]

        self._val_temp_ester   = self._pill(pills_zone, "Temp. Ester",   "---", "°C",  cols[0], rows[0], PW, PH)
        self._val_tiempo_ester = self._pill(pills_zone, "Tiempo Ester",  "---", "min", cols[0], rows[1], PW, PH)
        self._val_tiempo_sec   = self._pill(pills_zone, "Tiempo Sec",    "---", "min", cols[0], rows[2], PW, PH)
        self._val_temp_cam     = self._pill(pills_zone, "Temp.",         "---", "°C",  cols[1], rows[0], PW, PH)
        self._val_temp_ref     = self._pill(pills_zone, "Temp. 1",       "---", "°C",  cols[1], rows[1], PW, PH)
        self._val_pres_cam     = self._pill(pills_zone, "Presión",       "---", "kPa", cols[1], rows[2], PW, PH)

        # ── Zona de acción (28%) ──────────────────────────────────────────────
        action_zone = ctk.CTkFrame(self._card, corner_radius=0,
                                    fg_color=CLR_CARD, bg_color=CLR_CARD)
        action_zone.place(relx=0.02, rely=0.63, relwidth=0.96, relheight=0.28)
        self._panel_der = action_zone

        self._boton_puerta = tk.Label(action_zone, bg=CLR_CARD, cursor="hand2")
        self._boton_puerta.bind("<Button-1>", lambda e: self._accion_puerta_1())
        self._boton_puerta.bind("<Enter>", lambda e: self._boton_puerta.configure(bg=CLR_BG))
        self._boton_puerta.bind("<Leave>", lambda e: self._boton_puerta.configure(bg=CLR_CARD))
        self._boton_puerta.place(relx=0.04, rely=0.15, relwidth=0.42, relheight=0.75)

        self._boton_iniciar = tk.Label(action_zone, bg=CLR_CARD, cursor="")
        self._boton_iniciar.bind("<Enter>", lambda e: self._boton_iniciar.configure(bg=CLR_BG) if self._inicio_habilitado else None)
        self._boton_iniciar.bind("<Leave>", lambda e: self._boton_iniciar.configure(bg=CLR_CARD))
        self._boton_iniciar.place(relx=0.54, rely=0.15, relwidth=0.42, relheight=0.75)
        self._inicio_habilitado = False

        self._btn_reset_falla = ctk.CTkButton(
            action_zone,
            text="RECONOCER\nFALLA",
            font=("Segoe UI", scaled_font(14, self._scale), "bold"),
            fg_color="#c0392b", hover_color="#922b21",
            text_color=CLR_W, corner_radius=14,
            command=self._do_reset_falla,
        )

        self._boton_iniciar_pos   = dict(relx=0.54, rely=0.15, relwidth=0.42, relheight=0.75)
        self._btn_reset_falla_pos = dict(relx=0.04, rely=0.15, relwidth=0.92, relheight=0.75)
```

- [ ] **Step 4.2: Probar temporalmente el layout portrait**

En `_build_ui`, forzar portrait temporalmente para verificar:

```python
    def _build_ui(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self._scale = font_scale(sw, sh)
        self._build_header(sh)
        self._build_body_portrait(sw, sh)   # ← forzar portrait para test
        self._build_footer(sh)
```

Arrancar:
```
python -m autoclave.ui.main
```

Verificar: banda de estado + grid 2×3 + zona acción. Si se ve correcto, revertir a la lógica condicional:

```python
    def _build_ui(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self._scale = font_scale(sw, sh)
        self._build_header(sh)
        if is_portrait(sw, sh):
            self._build_body_portrait(sw, sh)
        else:
            self._build_body_landscape(sw, sh)
        self._build_footer(sh)
```

- [ ] **Step 4.3: Commit**

```bash
git add src/autoclave/ui/window/main_window.py
git commit -m "feat: InterfazPrincipal — layout portrait (banda estado + grid pills + zona acción)"
```

---

## Task 5: Añadir `<Configure>` handler a `InterfazPrincipal`

**Files:**
- Modify: `src/autoclave/ui/window/main_window.py`

- [ ] **Step 5.1: Añadir `_on_configure`, `_check_orientation` y `_rebuild_layout`**

Añadir los tres métodos después de `_schedule_update`:

```python
    # ══════════════════════════════════════════════════════════════════════════
    # DETECCIÓN DE ORIENTACIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def _on_configure(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(
            150, lambda: self._check_orientation(event.width, event.height)
        )

    def _check_orientation(self, w: int, h: int):
        new_portrait, should_rebuild = check_orientation_changed(
            w, h, self._current_portrait
        )
        self._current_portrait = new_portrait
        if should_rebuild:
            self._rebuild_layout()

    def _rebuild_layout(self):
        if self._update_job:
            self.after_cancel(self._update_job)
            self._update_job = None
        for child in self.winfo_children():
            child.destroy()
        self._build_ui()
        self.after(300, self._load_action_images)
        self._schedule_update()
```

- [ ] **Step 5.2: Verificar que el primer `<Configure>` registra la orientación inicial sin rebuild**

En `_rebuild_layout`, añadir temporalmente un log para confirmar:
```python
    def _rebuild_layout(self):
        logger.info("Rebuilding layout — orientación cambió")
        ...
```

Arrancar la app y verificar en los logs que `"Rebuilding layout"` NO aparece al inicio (solo aparecería si la orientación cambia).

- [ ] **Step 5.3: Probar flip de orientación vía Windows Settings**

Con la app corriendo en fullscreen, ir a Configuración → Pantalla → Orientación y cambiar. Verificar:
- La UI se reconstruye con el layout correcto
- La conexión al backend sigue activa tras el rebuild
- El label de estado y los sensores vuelven a actualizarse

- [ ] **Step 5.4: Commit**

```bash
git add src/autoclave/ui/window/main_window.py
git commit -m "feat: InterfazPrincipal detecta cambios de orientación vía <Configure> y reconstruye el layout"
```

---

## Task 6: Actualizar footer de `CycleWindow` — añadir botones info/settings

Este cambio aplica a **ambas orientaciones** de `CycleWindow`.

**Files:**
- Modify: `src/autoclave/ui/cycle/cycle_window.py`

- [ ] **Step 6.1: Añadir imports en `cycle_window.py`**

```python
from autoclave.ui.layout import font_scale, scaled_font, load_footer_icons
```

- [ ] **Step 6.2: Calcular y almacenar `_scale` en `__init__` de `CycleWindow`**

Después de `self.grab_set()` y antes de `self._build_header()`:

```python
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self._scale = font_scale(sw, sh)
        self._sh    = sh
```

Y cambiar las llamadas de construcción a:
```python
        self._build_header()
        self._build_body()
        self._build_footer()      # sin cambio de firma aquí aún
```

- [ ] **Step 6.3: Reemplazar `_build_footer` con la versión que incluye los botones**

```python
    def _build_footer(self):
        footer = tk.Frame(self, bg=CLR_BG, height=int(self._sh * 0.065))
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        # Pill izquierda: info + settings
        icons = load_footer_icons(self._scale)
        self._img_info_cw     = icons["info"]
        self._img_settings_cw = icons["settings"]

        pill_left = ctk.CTkFrame(footer, corner_radius=30,
                                  fg_color=CLR_FOOTER, bg_color=CLR_BG)
        pill_left.place(relx=0.01, rely=0.5, anchor="w",
                        relwidth=0.20, relheight=0.82)

        ctk.CTkButton(pill_left, text="", image=self._img_info_cw,
                      fg_color="transparent", hover_color="#406080",
                      width=scaled_font(56, self._scale)).pack(side=tk.LEFT, padx=12)

        ctk.CTkButton(pill_left, text="", image=self._img_settings_cw,
                      fg_color="transparent", hover_color="#406080",
                      width=scaled_font(56, self._scale)).pack(side=tk.LEFT, padx=8)

        # Pill central: estado del ciclo
        pill = ctk.CTkFrame(footer, corner_radius=45,
                            fg_color=CLR_FOOTER, bg_color=CLR_BG)
        pill.place(relx=0.5, rely=0.5, anchor="center",
                   relwidth=0.52, relheight=0.82)

        self._lbl_estado = ctk.CTkLabel(
            pill, text="Ciclo en progreso...",
            font=("Segoe UI", scaled_font(16, self._scale)),
            text_color=CLR_W, fg_color="transparent",
        )
        self._lbl_estado.pack(expand=True)
```

- [ ] **Step 6.4: Arrancar un ciclo y verificar el footer**

```
python -m autoclave.ui.main
```

Iniciar un ciclo. Verificar que el footer de `CycleWindow` muestra los botones ℹ️ y ⚙️ a la izquierda y el estado en la pill central.

- [ ] **Step 6.5: Commit**

```bash
git add src/autoclave/ui/cycle/cycle_window.py
git commit -m "feat: CycleWindow footer — botones info y settings accesibles durante el ciclo"
```

---

## Task 7: Añadir layout portrait a `CycleWindow`

**Files:**
- Modify: `src/autoclave/ui/cycle/cycle_window.py`

- [ ] **Step 7.1: Añadir atributos de control en `__init__` de `CycleWindow`**

Después de `self._scale = font_scale(sw, sh)`:

```python
        self._current_portrait = None
        self._update_job_cw    = None
        self._resize_job_cw    = None
        self._sh               = sh
```

- [ ] **Step 7.2: Renombrar `_build_body` a `_build_body_landscape` y añadir `_build_ui`**

Añadir:

```python
    def _build_ui_cw(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self._scale = font_scale(sw, sh)
        self._sh    = sh
        self._build_header()
        if is_portrait(sw, sh):
            self._build_body_portrait_cw(sw, sh)
        else:
            self._build_body_landscape()   # ← renombrado del _build_body actual
        self._build_footer()
```

Cambiar el `__init__` para llamar `self._build_ui_cw()` en lugar de los tres métodos separados.

- [ ] **Step 7.3: Añadir `_build_body_portrait_cw`**

```python
    # ══════════════════════════════════════════════════════════════════════════
    # BODY PORTRAIT — CycleWindow
    # ══════════════════════════════════════════════════════════════════════════

    def _build_body_portrait_cw(self, sw: int, sh: int):
        body = tk.Frame(self, bg=CLR_BG)
        body.pack(fill=tk.BOTH, expand=True)

        card = ctk.CTkFrame(body, corner_radius=28,
                            fg_color=CLR_CARD, bg_color=CLR_BG)
        card.place(relx=0.02, rely=0.03, relwidth=0.96, relheight=0.94)
        self._card = card

        # Nombre del ciclo
        nombre = (self.ui_service.get_cycle_param("name") or "CICLO").upper()
        self._lbl_nombre = ctk.CTkLabel(
            card, text=nombre,
            font=("Segoe UI", scaled_font(34, self._scale), "bold"),
            text_color=CLR_B, fg_color="transparent",
        )
        self._lbl_nombre.place(relx=0.5, rely=0.04, anchor="center")

        # Separador
        ctk.CTkFrame(card, fg_color="#cccccc", corner_radius=0,
                    bg_color=CLR_CARD).place(
            relx=0.01, rely=0.10, relwidth=0.98, relheight=0.003)

        # Pill de fase
        self._phase_ind = PhaseIndicator(
            card, bg_color=CLR_CARD,
            font_size_label=scaled_font(20, self._scale),
            font_size_timer=scaled_font(18, self._scale),
        )
        self._phase_ind.place(relx=0.01, rely=0.11, relwidth=0.98, relheight=0.10)

        # Gráfica (zona dominante)
        graph_frame = tk.Frame(card, bg=CLR_CARD)
        graph_frame.place(relx=0.01, rely=0.23, relwidth=0.98, relheight=0.44)
        self._graph = LiveGraph(graph_frame, bg=CLR_CARD)
        self._graph.pack(fill=tk.BOTH, expand=True)

        # Separador
        ctk.CTkFrame(card, fg_color="#cccccc", corner_radius=0,
                    bg_color=CLR_CARD).place(
            relx=0.01, rely=0.68, relwidth=0.98, relheight=0.003)

        # Sensores en fila horizontal
        self._val_temp  = self._pill(card, "Temp.",   "---", "°C",  0.01, 0.69, 0.32, 0.13)
        self._val_temp2 = self._pill(card, "Temp. 1", "---", "°C",  0.34, 0.69, 0.32, 0.13)
        self._val_pres  = self._pill(card, "Presión", "---", "kPa", 0.67, 0.69, 0.32, 0.13)

        # Separador
        ctk.CTkFrame(card, fg_color="#cccccc", corner_radius=0,
                    bg_color=CLR_CARD).place(
            relx=0.01, rely=0.83, relwidth=0.98, relheight=0.003)

        # Puertas + botón acción
        doors_frame = tk.Frame(card, bg=CLR_CARD)
        doors_frame.place(relx=0.01, rely=0.84, relwidth=0.35, relheight=0.13)

        self._lbl_puerta1 = tk.Label(doors_frame, bg=CLR_CARD)
        self._lbl_puerta1.pack(side=tk.LEFT, padx=6)

        self._lbl_puerta2 = tk.Label(doors_frame, bg=CLR_CARD)
        self._lbl_puerta2.pack(side=tk.LEFT, padx=6)

        self._btn_abort = tk.Label(card, bg=CLR_CARD, cursor="hand2")
        self._btn_abort.bind("<Button-1>", lambda e: self._confirmar_abort())
        self._btn_abort.bind("<Enter>",    lambda e: self._btn_abort.configure(bg=CLR_BG))
        self._btn_abort.bind("<Leave>",    lambda e: self._btn_abort.configure(bg=CLR_CARD))
        self._btn_abort.place(relx=0.37, rely=0.84, relwidth=0.62, relheight=0.13)

        self._btn_confirm = ctk.CTkButton(
            card,
            text="CONFIRMAR",
            font=("Segoe UI", scaled_font(15, self._scale), "bold"),
            fg_color=CLR_OK, hover_color="#155d32",
            text_color=CLR_W, corner_radius=14,
            state="disabled",
            command=self._do_confirm,
        )
```

- [ ] **Step 7.4: Verificar que `_on_ciclo_fin` usa coordenadas correctas en portrait**

En `_on_ciclo_fin`, el botón CONFIRMAR se posiciona con:
```python
self._btn_confirm.place(relx=0.65, rely=0.56, relwidth=0.35, relheight=0.26)
```
Estas son coordenadas del panel derecho en landscape. En portrait, el botón CONFIRMAR reemplaza al botón ABORTAR en la misma posición, así que hay que usar las coordenadas de `_btn_abort` en portrait:

Modificar `_on_ciclo_fin` para que use coordenadas relativas al parent real de `_btn_abort`:

```python
    def _on_ciclo_fin(self, fase_terminal: str):
        ...
        try:
            self._btn_abort.place_forget()
            # Posicionar confirm en el mismo lugar que abort
            info = self._btn_abort.place_info()
            self._btn_confirm.place(
                relx=float(info.get("relx", 0.65)),
                rely=float(info.get("rely", 0.56)),
                relwidth=float(info.get("relwidth", 0.35)),
                relheight=float(info.get("relheight", 0.26)),
                in_=self._btn_abort.master,
            )
        except tk.TclError:
            pass
```

> **Alternativa más simple**: almacenar `self._btn_abort_pos` y `self._btn_abort_parent` al crear el botón en cada layout, y usarlos en `_on_ciclo_fin`. Esto evita el `place_info()` dinámico.

Usar la alternativa simple — añadir al final de cada `_build_body_*`:
```python
        self._btn_abort_parent = card  # o pnl en landscape
```

Y en `_on_ciclo_fin`:
```python
        self._btn_confirm.place(
            relx=float(self._btn_abort.place_info().get("relx", 0.65)),
            rely=float(self._btn_abort.place_info().get("rely", 0.56)),
            relwidth=float(self._btn_abort.place_info().get("relwidth", 0.35)),
            relheight=float(self._btn_abort.place_info().get("relheight", 0.26)),
        )
```

- [ ] **Step 7.5: Probar portrait forzado en CycleWindow**

En `_build_ui_cw`, forzar portrait temporalmente, arrancar la app e iniciar un ciclo. Verificar:
- Gráfica ocupa el área central
- Sensores en fila horizontal debajo
- Botón ABORTAR visible

Revertir al condicional tras verificar.

- [ ] **Step 7.6: Commit**

```bash
git add src/autoclave/ui/cycle/cycle_window.py
git commit -m "feat: CycleWindow — layout portrait con gráfica prominente"
```

---

## Task 8: Añadir `<Configure>` handler a `CycleWindow`

**Files:**
- Modify: `src/autoclave/ui/cycle/cycle_window.py`

- [ ] **Step 8.1: Añadir `_schedule_update_cw`, `_on_configure_cw`, `_check_orientation_cw` y `_rebuild_layout_cw`**

```python
    def _schedule_update_cw(self):
        self._update_job_cw = self.after(1000, self._run_update_cw)

    def _run_update_cw(self):
        if self._closing:
            return
        self._update_loop_body()     # ← extraer el contenido actual de _update_loop aquí
        self._update_job_cw = self.after(1000, self._run_update_cw)

    def _on_configure_cw(self, event):
        if event.widget is not self:
            return
        if self._resize_job_cw:
            self.after_cancel(self._resize_job_cw)
        self._resize_job_cw = self.after(
            150, lambda: self._check_orientation_cw(event.width, event.height)
        )

    def _check_orientation_cw(self, w: int, h: int):
        new_portrait, should_rebuild = check_orientation_changed(
            w, h, self._current_portrait
        )
        self._current_portrait = new_portrait
        if should_rebuild:
            self._rebuild_layout_cw()

    def _rebuild_layout_cw(self):
        if self._update_job_cw:
            self.after_cancel(self._update_job_cw)
            self._update_job_cw = None
        for child in self.winfo_children():
            child.destroy()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self._scale = font_scale(sw, sh)
        self._sh    = sh
        self._build_header()
        if is_portrait(sw, sh):
            self._build_body_portrait_cw(sw, sh)
        else:
            self._build_body_landscape()
        self._build_footer()
        self.grab_set()              # re-aplicar grab modal
        self.after(350, self._load_images)
        self._schedule_update_cw()
```

- [ ] **Step 8.2: Refactorizar `_update_loop` para extraer el cuerpo a `_update_loop_body`**

El `_update_loop` actual se convierte en:

```python
    def _update_loop(self):
        if self._closing:
            return
        self._tick += 1
        try:
            self._update_loop_body()
        except Exception as e:
            logger.warning("CycleWindow update error: %s", e)
        self.after(1000, self._update_loop)

    def _update_loop_body(self):
        self._upd_sensores()
        self._upd_fase()

        if self._tick % _GRAPH_TICKS == 0:
            self._graph.update_data(
                self._buffer.points,
                self._buffer.phase_boundaries,
            )

        if self._tick % 4 == 0:
            self._upd_puertas()

        machine_state = self.ui_service.get_estado_global()
        fase_actual   = self.ui_service.get_fase_ciclo()

        if not self._ciclo_activo_detectado:
            if machine_state == "CICLO" and not _es_fase_terminal(fase_actual):
                self._ciclo_activo_detectado = True

        if self._ciclo_activo_detectado and not self._ciclo_terminado:
            if _es_fase_terminal(fase_actual):
                self._on_ciclo_fin(fase_actual)

        if self._ciclo_terminado:
            self._upd_confirm_safety()
```

- [ ] **Step 8.3: Vincular el evento en `__init__` de `CycleWindow`**

Al final del `__init__`, después de `self.after(1000, self._update_loop)`:

```python
        self.bind("<Configure>", self._on_configure_cw)
```

- [ ] **Step 8.4: Probar flip de orientación durante un ciclo activo**

Con la app corriendo y un ciclo en curso en el monitor de 8":
1. Cambiar la orientación vía Windows Settings
2. Verificar que `CycleWindow` se reconstruye en el nuevo layout
3. Verificar que la gráfica mantiene todos los puntos anteriores (el buffer sobrevive)
4. Verificar que `grab_set()` sigue activo (el diálogo de abort aún funciona)

- [ ] **Step 8.5: Añadir `.superpowers/` a `.gitignore`**

```bash
echo ".superpowers/" >> .gitignore
git add .gitignore
```

- [ ] **Step 8.6: Commit final**

```bash
git add src/autoclave/ui/cycle/cycle_window.py .gitignore
git commit -m "feat: CycleWindow detecta cambios de orientación y reconstruye el layout preservando datos del ciclo"
```

---

## Verificación final

- [ ] Arrancar en resolución landscape (1920×1080): layout landscape sin cambios visuales respecto al estado anterior
- [ ] Cambiar orientación a portrait vía Windows Settings: layout portrait se aplica
- [ ] Volver a landscape: layout landscape se restaura
- [ ] Iniciar ciclo en portrait: `CycleWindow` en portrait con gráfica prominente y botones ℹ️ ⚙️ en footer
- [ ] Rotar durante ciclo activo: `CycleWindow` se reconstruye, datos de gráfica preservados
- [ ] Escala 8" (1280×800): fuentes al 74% — visualmente más pequeñas pero legibles
- [ ] Fuente del log NO muestra "Rebuilding layout" al arrancar (primer `<Configure>` solo registra orientación)

```
pytest tests/test_ui_layout.py -v
```

Todos en verde.

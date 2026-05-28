# Handoff — Estado al 2026-05-28

**Rama activa:** `dev`  
**PR abierto:** [#16 — feat: UI responsive a orientación — layout portrait + font scaling](https://github.com/Alexis73-10/Software-de-autoclave/pull/16)  
**PR anterior (pendiente de merge):** [#15 — feat: suministro_electrico modo seguro](https://github.com/Alexis73-10/Software-de-autoclave/pull/15)

---

## Qué se hizo hoy

### Feature completa: UI responsive a orientación y relación de aspecto

La UI de autoclave ahora detecta flips landscape ↔ portrait en ambos monitores (13" 1920×1080 y 8" 1280×800) y reconstruye el layout sin perder estado del ciclo.

**Comportamiento implementado:**

- **Detección:** evento `<Configure>` de Tkinter con debounce 150ms en `InterfazPrincipal` y `CycleWindow`. Solo dispara rebuild cuando realmente cambia la orientación (`h > w`).
- **Font scaling:** `font_scale(w, h) = min(w, h) / 1080` — escala 1.0 en 1080p, 0.74 en 800p. Fuentes de toda la UI pasan por `scaled_font(base, scale)`.
- **Header/footer:** alturas relativas (`0.04 × sh` y `0.065 × sh`) en lugar de píxeles fijos.
- **Layout portrait de `InterfazPrincipal`:** banda de estado (22%) + grid de pills 2×3 (34%) + zona de acción (28%).
- **Layout portrait de `CycleWindow`:** gráfica T/P prominente (44% ancho completo), sensores en fila horizontal, puertas + botón acción al pie.
- **Footer de `CycleWindow`:** botones ℹ️ y ⚙️ ahora accesibles durante el ciclo (antes solo en ventana principal).
- **Multi-monitor:** fix para Windows — `winfo_width/height()` en lugar de `winfo_screenwidth/height()` (que siempre devuelve el monitor principal), con fallback al primer render.

**Invariantes garantizadas tras rebuild:**

- `_buffer` (puntos T/P), `_ciclo_activo_detectado`, `_ciclo_terminado`, `_hold_start_time`, `_fase_temp_targets` sobreviven intactos en `CycleWindow`.
- `InterfazPrincipal` no destruye la `CycleWindow` hija.
- Un único loop de actualización activo por ventana en todo momento (`_update_job_cw` cancela el anterior antes de reiniciar).
- `grab_set()` re-aplicado tras cada rebuild de `CycleWindow`.
- Chain de `_tick_hora` garantizado único (handle cancelado antes de rebuild).
- `_toast_widget` puesto a `None` tras el loop de destrucción.

**Archivos creados/modificados:**

| Archivo | Cambio |
|---------|--------|
| `src/autoclave/ui/layout.py` | **Nuevo** — `is_portrait`, `font_scale`, `scaled_font`, `check_orientation_changed`, `load_footer_icons` |
| `tests/test_ui_layout.py` | **Nuevo** — 20 tests (helpers puros + PhaseIndicator), fixture module-scoped |
| `ui/cycle/widgets/phase_indicator.py` | Añade `font_size_label` y `font_size_timer` como parámetros |
| `ui/window/main_window.py` | Font scaling, alturas relativas, `_build_body_landscape/portrait`, `<Configure>` handler |
| `ui/cycle/cycle_window.py` | Layout portrait, footer con info/settings, `<Configure>` handler, unificación de loops |

**Tests:** 20 nuevos, todos green.

**Commits relevantes (más reciente primero):**
```
d20e14b  fix: usar winfo_width/height en _build_ui para soporte multi-monitor
9b54a67  test: usar fixture module-scoped para tests de PhaseIndicator
b00ff82  fix: cancelar _tick_hora antes de rebuild y limpiar _toast_widget
53eba85  fix: CycleWindow — unificar loop de actualización, guards _closing
b9d9fad  feat: CycleWindow detecta cambios de orientación (rebuild preservando datos)
b7f39bd  feat: CycleWindow — layout portrait con gráfica prominente
c4b862b  feat: CycleWindow footer — botones info y settings accesibles durante ciclo
a2618dd  fix: orientation rebuild — preservar CycleWindow, limpiar resize_job
cfb873e  feat: InterfazPrincipal detecta cambios de orientación y reconstruye layout
d82338f  feat: InterfazPrincipal — layout portrait (banda estado + grid pills + acción)
b16ffc4  fix: _tick_hora resiliente a TclError tras rebuild
d8ce807  refactor: InterfazPrincipal usa font scaling e alturas relativas
2e371e7  feat: PhaseIndicator acepta font_size_label y font_size_timer
3e62ed3  feat: layout.py — helpers de escala de fuente y detección de orientación
```

---

## Feature anterior: `suministro_electrico` — modo seguro (2026-05-27)

**PR #15** — pendiente de merge a `main`.

**Comportamiento implementado:**

- **Fuera de ciclo (PREPARADO):** flag `FALLO_SUMINISTRO_ELECTRICO` bloquea el botón de inicio y la bomba de vacío; genera alarma `ALERTA` recuperable `"SUMINISTRO_ELECTRICO"`.
- **En ciclo (CICLO):** ciclo abortado inmediatamente, `ProtocoloFallo` descomprime sin bomba, transición a FALLA requiere confirmación del operador.
- **Puertas avanzadas (modo seguro):** apertura/cierre sin bomba, solo válvula de empaque (`desbloquear_on`), umbral de presión atmosférica, alarma no bloqueante única por puerta.
- **UI:** indicador `⚡ Suministro: OK` (verde) / `⚡ Sin suministro` (rojo) en el footer.

**Archivos principales:** `devices/suministro_electrico/`, `core/status.py`, `devices/pump/pump.py`, `devices/puertas/advanced_door.py`, `state_machine/states/preparado.py`, `state_machine/states/ciclo.py`.

---

## Issue pendiente: CalentamientoFase crash en producción

**Este issue existía antes de ayer y NO fue resuelto.**

### Crash observado

```
TypeError: '<=' not supported between instances of 'float' and 'NoneType'
  File "calentamiento.py", line 89 in update
    if self._verificar_vapor_saturado(temp, pres, tolerancia):
  File "base_fase.py", line 71 in _verificar_vapor_saturado
    return abs(p_real_kpa - p_saturacion_kpa(t_celsius)) <= tolerancia_kpa
```

`tolerancia_kpa` llega como `None` → el ciclo Bowe & Dick no tiene el parámetro que el código busca.

### Estado actual de `calentamiento.py`

El archivo tiene cambios **sin commitear** en el working tree:

| Línea | Problema |
|-------|----------|
| 36 | `t_obj = get_param(...)` — sin fallback `or 134.0` |
| 37 | `tasa_seg = (get_param(...)) / 60` — sin fallback, crash si None |
| 38 | `timeout_seg = (get_param(...)) * 60` — sin fallback, crash si None |
| 39 | `tolerancia = get_param("calentamiento", "rango_presion_calentamiento")` — sin fallback `or 9.0` |
| 49 | `self._checkpoints = [0.80 * t_obj, 0.97 * t_obj]` — spec dice 0.50/0.90 |

### Conflicto de nombres de parámetros

| Ciclo | Clave JSON | Sección |
|-------|-----------|---------|
| `instrumental_134` | `presion_add_calentamiento` | `calentamiento` |
| `bowe_dick` | `rango_presion_calentamiento` | `calentamiento` |

El código (línea 39) usa `rango_presion_calentamiento`, pero `instrumental_134.json` tiene `presion_add_calentamiento` → ese ciclo queda con `tolerancia = None`.

### Opciones para resolver

**A. Unificar en `rango_presion_calentamiento`** — renombrar en `instrumental_134.json` + `or 9.0` de fallback.  
**B. Buscar con fallback entre las dos claves** — código prueba una, luego la otra. Más flexible.  
**C. Unificar en `presion_add_calentamiento`** — renombrar en `bowe_dick.json`.

### Qué falta

1. Elegir estrategia (A, B o C).
2. Actualizar los JSONs afectados.
3. Restaurar defaults `or X` en líneas 36-39 de `calentamiento.py`.
4. Decidir si checkpoints van a 0.50/0.90 (spec) o 0.80/0.97 (cambio del fix subagent). El test `test_checkpoint_entra_en_sostenimiento` falla por este motivo.
5. Commitear `calentamiento.py`.
6. `pytest tests/test_calentamiento_fase.py -v` para verificar.

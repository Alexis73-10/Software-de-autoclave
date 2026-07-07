# Handoff 2026-06-17 — Menú Entradas/Salidas

## Estado al interrumpir

Rama: `dev`. Ejecución SDD del plan `docs/superpowers/plans/2026-06-17-entradas-salidas.md` interrumpida después de Task 3.

## Tareas completadas hoy

| Task | Descripción | Commits | Tests | Review |
|------|-------------|---------|-------|--------|
| 1 | Backend endpoints `POST /io/test/reset_all` + `PATCH /io/test/output/{name}` | `bbd4972..a34ab3f` | 5/5 | ✅ clean |
| 2 | `_io_base.py` — `_format_name()` + `_MonitorBase` (timer/poll/showEvent/hideEvent) | `a34ab3f..76afe6b` | 3/3 | ✅ clean |
| 3 | `io_menu.py` (EntradasSalidasMenuView) + wiring `admin_menu.py` + `main_window.py` | `76afe6b..76d52cb` | 5/5 | ⚠️ pendiente de review |

## Punto exacto de reanudación

**Próximo paso inmediato:** revisar Task 3 antes de avanzar.

```
# Generar paquete de review para Task 3:
bash scripts/review-package 76afe6b HEAD

# Dispatcher review con brief + report + diff:
# brief: .git/sdd/task-3-brief.md
# report: .git/sdd/task-3-report.md
# diff: .git/sdd/review-76afe6b..76d52cb.diff
```

Luego continuar con Tasks 4–7 en orden:

| Task | Descripción | Base commit |
|------|-------------|-------------|
| 4 | `EntradasDigitalesView` — 14 DI cards | `76d52cb` (o HEAD tras review) |
| 5 | `TemperaturasView` — 6 sensores temperatura | tras Task 4 |
| 6 | `PresionesView` — 4 sensores presión | tras Task 5 |
| 7 | `SalidasDigitalesView` — 24 DO + modo prueba | tras Task 6 |

## Archivos clave

- **Plan completo:** `docs/superpowers/plans/2026-06-17-entradas-salidas.md`
- **Spec:** `docs/superpowers/specs/2026-06-17-entradas-salidas-design.md`
- **Ledger SDD:** `.git/sdd/progress.md`
- **Briefs/reports:** `.git/sdd/task-N-brief.md` / `task-N-report.md`

## Archivos creados en esta sesión

```
src/autoclave/backend/server.py          — 2 endpoints nuevos al final
src/autoclave/ui_pyside/views/_io_base.py — _format_name + _MonitorBase
src/autoclave/ui_pyside/views/io_menu.py  — EntradasSalidasMenuView
src/autoclave/ui_pyside/views/admin_menu.py — _OPTION_ROUTES + _option_clicked
src/autoclave/ui_pyside/main_window.py   — io_menu registrado en stack
tests/test_io_endpoints.py               — 5 tests backend endpoints
tests/test_io_views.py                   — 5 tests base + menu
```

## Archivos pendientes (Tasks 4–7)

```
src/autoclave/ui_pyside/views/io_di.py   — Task 4
src/autoclave/ui_pyside/views/io_temp.py — Task 5
src/autoclave/ui_pyside/views/io_pres.py — Task 6
src/autoclave/ui_pyside/views/io_do.py   — Task 7
```

## Datos clave del backend

- `GET /status` → `status["sensors"]["digital_inputs"]` (14 DI nombradas)
- `GET /status` → `status["sensors"]["digital_outputs"]` (24 DO nombradas)
- `GET /status` → `status["sensors"]["temperature"]` (claves: camara, camara_2, ref, chaqueta, drenaje_camara, drenaje)
- `GET /status` → `status["sensors"]["pressure"]` (claves: camara, chaqueta, empaque_1, empaque_2)

**Nota sobre temperaturas:** `EstadoAutoclave.map_temp` usa claves largas (`temp_camara`) pero el backend retorna claves cortas (`camara`). El plan Task 5 incluye un `name_map` para la traducción.

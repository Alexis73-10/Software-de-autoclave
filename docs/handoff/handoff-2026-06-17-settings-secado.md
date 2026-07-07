# Handoff — 2026-06-17

## Sesión actual: Botón Settings + CiclosView mejorada + Fase SECADO

### Lo que se hizo hoy

#### 1. Corrección de arquitectura — botón settings abre PySide6 on-demand

Se detectó que el menú PySide6 arrancaba al iniciar la app (incorrecto). Se rediseñó:

- **`src/autoclave/main.py`** — revertido a lanzar tkinter `InterfazPrincipal` como ventana principal
- **`src/autoclave/ui_pyside/app.py`** — nuevo entry point standalone PySide6 fullscreen frameless
- **`src/autoclave/ui_pyside/main_window.py`** — eliminado `tkinter_proc`, `_open_monitor()`, botón Monitor
- **`src/autoclave/ui/window/main_window.py`** — botón settings cablea `_open_settings()` + `_poll_settings()`:
  - `withdraw()` al abrir, `deiconify()` al cerrar
  - `subprocess.Popen([sys.executable, "-m", "autoclave.ui_pyside.app"])`
  - Polling cada 500ms con `self.after()`
  - Guard doble-click, OSError→deiconify, cleanup en `on_close()`

Plan: `docs/superpowers/plans/2026-06-17-settings-button-pyside6-impl.md`
Spec: `docs/superpowers/specs/2026-06-17-settings-button-pyside6-design.md`

#### 2. CiclosView — impresión por ciclo en formato ticket

- Checkbox por fila + "Seleccionar todos" para elegir ciclos a imprimir
- **Bug corregido**: reemplazado `QTextDocument+<pre>` por `QPainter` directo — elimina el bug de "una línea por página" con múltiples ciclos
- Papel 55mm: `QPageSize(QSizeF(55, 297), QPageSize.Unit.Millimeter)`, Courier New 7pt, wrap automático
- Formato ticket por ciclo: idéntico al `.txt` de referencia (`cycle_NNNNNN.txt` de Tuttnauer):
  cabecera (fecha, serie, modelo, versión SW, número ciclo, programa), log de lecturas
  (fase/tiempo/°C/kPa de `para_imprimir=1`), resultado y firma de operador
- Page-break con `printer.newPage()` entre ciclos

#### 3. CiclosView — envío por correo

- Botón "Enviar por correo" habilitado solo si hay internet (`socket.create_connection`)
- Genera un PDF por ciclo con `QPrinter(PdfFormat)` + altura calculada dinámicamente
- Empaqueta en ZIP (`ciclos_autoclave.zip`) y envía por SMTP+STARTTLS
- **Contraseña guardada en Windows Credential Manager** (`keyring.WinVaultKeyring`):
  - Primera vez: ingresa App Password → se guarda
  - Siguiente vez: campo pre-cargado con "✓ Contraseña guardada"
  - Botón "Olvidar contraseña" elimina del Credential Manager
- `QSettings("Especifika", "Autoclave")` guarda: remitente, servidor SMTP, puerto (no contraseña)
- Feedback: `QMessageBox` de éxito o error tras el envío

**Nota Gmail**: requiere App Password (no contraseña normal). Generarla en:
Cuenta Google → Seguridad → Verificación en 2 pasos → Contraseñas de aplicaciones.

#### 4. Fase SECADO — 3 modos de secado

Se implementó `SecadoFase` completa, insertada entre `EsterilizacionFase` y `DescompresionFase` en el pipeline de `CicloState`.

**Modos:**
- **Modo 1**: activa `bomba_vacio` + `vacio_camara` + mantiene chaqueta a `presion_chaqueta_secado` durante `tiempo_secado`
- **Modo 2**: igual que modo 1 + `aire_admosferico_camara` (circulación de aire seco)
- **Modo 3 (pulsado)**: cicla VACIO_BAJO → AIRE_ALTO por presiones configuradas hasta agotar `tiempo_secado`. Timeout por semi-pulso (`timeout_pulso` en segundos) → FALLO si no alcanza la presión objetivo

**Decisión de diseño clave**: `timeout_pulso` se almacena en segundos (no minutos) porque los tests son la spec ejecutable (`_timeout_pulso_fin -= 200`). JSON usa `"unit": "seg"`, `"max": 600`.

**Chaqueta independiente**: `SecadoFase._tick_chaqueta()` hace bang-bang con `presion_chaqueta_secado` ± `rango_chaqueta_secado`. `CicloState._mantener_chaqueta()` se suprime durante SECADO vía `isinstance(fase, SecadoFase)`.

Archivos afectados:
- `src/autoclave/state_machine/cycle_phases/secado.py` — **Nuevo**
- `src/autoclave/state_machine/states/ciclo.py` — import, pipeline, guard chaqueta
- `src/autoclave/cycles/factory/instrumental_134.json` — sección `"secado"` nueva (removido de `"esterilizacion"`)
- `src/autoclave/cycles/factory/bowe_dick.json` — sección `"secado"` reemplazada con 7 params
- `src/autoclave/cycles/user/instrumental_134.json` — idem factory
- `src/autoclave/cycles/user/bowe_dick.json` — idem factory
- `src/autoclave/backend/server.py` — endpoint PATCH valida los 7 params de `"secado"`
- `src/autoclave/ui_pyside/views/secado.py` — selector modo, chaqueta, campos modo-3 condicionales
- `tests/test_secado_fase.py` — **Nuevo** — 14 tests

Spec: `docs/superpowers/specs/2026-06-17-secado-fase-design.md`
Plan: `docs/superpowers/plans/2026-06-17-secado-fase.md`
PR: #21 (rama `dev` → `main`)

### Estado del repo

- Rama activa: `dev`
- `main` local y remoto: `d270995` (merge commit del PR #20)
- `dev` local: `9a75aa9` — PR #21 abierto (fase SECADO)
- Tests: **235 pasan**

### Archivos clave modificados en esta sesión

| Archivo | Cambio |
|---|---|
| `src/autoclave/main.py` | Tkinter como UI principal, cleanup `_settings_proc` |
| `src/autoclave/ui/window/main_window.py` | `_open_settings`, `_poll_settings`, botón settings cableado |
| `src/autoclave/ui_pyside/app.py` | **Nuevo** — entry point PySide6 standalone fullscreen |
| `src/autoclave/ui_pyside/main_window.py` | Eliminado subprocess/monitor |
| `src/autoclave/ui_pyside/views/ciclos.py` | QPainter, 55mm, checkboxes, email+keyring |
| `src/autoclave/ui_pyside/views/secado.py` | Reescrito — modo selector + campos modo 3 condicionales |
| `src/autoclave/state_machine/cycle_phases/secado.py` | **Nuevo** — SecadoFase 3 modos |
| `src/autoclave/state_machine/states/ciclo.py` | SecadoFase en pipeline + guard chaqueta |
| `src/autoclave/cycles/factory/instrumental_134.json` | Sección `"secado"` nueva |
| `src/autoclave/cycles/factory/bowe_dick.json` | Sección `"secado"` completada |
| `src/autoclave/cycles/user/instrumental_134.json` | Idem factory |
| `src/autoclave/cycles/user/bowe_dick.json` | Idem factory |
| `src/autoclave/backend/server.py` | PATCH endpoint para sección `"secado"` |
| `tests/test_secado_fase.py` | **Nuevo** — 14 tests unitarios |
| `pyproject.toml` | Agregado `keyring` a dependencias |

### Dependencias agregadas

```
keyring  — Windows Credential Manager para App Password de email
```

Instalar: `pip install keyring` (ya en pyproject.toml)

### Para continuar

- PR #21 abierto — mergearlo cuando esté listo
- Próximas fases del ciclo pendientes (ciclo completo actual: PRECALENTAMIENTO → PURGA → PRE_VACIO → CALENTAMIENTO → ESTABILIZACION → ESTERILIZACION → **SECADO** → DESCOMPRESION)
- `SecadoView` no expone `timeout_pulso` ni `rango_chaqueta_secado` desde la UI — se pueden editar directamente en el JSON user si es necesario

### Contexto técnico clave

- **Impresión**: usar siempre `QPainter` + `printer.newPage()` — nunca `QTextDocument+<pre>` para múltiples páginas
- **Email Gmail**: App Password de 16 chars, SMTP smtp.gmail.com:587 STARTTLS
- **Credenciales**: `keyring.get/set_password("Especifika-Autoclave-Email", from_addr, pw)`
- **PDF por ciclo**: `QPrinter(PdfFormat)` + altura calculada = `n_lines * 3.6 + 10` mm
- **Merge local con archivos bloqueados**: usar `git branch -f main origin/main` en lugar de checkout
- **timeout_pulso en SECADO**: almacenado en segundos (no minutos). JSON `"unit": "seg"`, `"max": 600`, default `10`

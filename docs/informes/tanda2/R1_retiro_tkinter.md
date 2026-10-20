# R1 — Retiro de tkinter y punto de entrada de producción

Instrucción: `instruccion_claude_code_tanda_2.md` §2 R1 y decisión 3.

## 1. Inventario (antes de retirar)

| Elemento | Qué era | Quién lo usaba | Destino |
|---|---|---|---|
| `src/autoclave/main.py` | Entrada tkinter: perfil y reloj, asistente tkinter, arranque del backend, espera de la tarjeta, **latido de impresora**, ventana `InterfazPrincipal` | `AutoclaveUI.spec`, `tests/test_main_hardware_wait.py` | **Retirado** |
| `src/autoclave/ui/main.py` | Entrada tkinter alternativa | nadie | **Retirado** |
| `src/autoclave/ui/window/main_window.py` | Ventana tkinter; imprimía el **ticket de arranque** | `main.py`, `ui/main.py` | **Retirado** |
| `src/autoclave/ui/cycle/` (`cycle_window`, `widgets/live_graph`, `widgets/phase_indicator`, `data/cycle_buffer`) | Pantalla de ciclo tkinter | `main_window.py`, `tests/test_ui_layout.py` | **Retirado** |
| `src/autoclave/ui/components/components.py`, `src/autoclave/ui/layout.py` | Componentes y layout tkinter | `main_window.py`, `cycle_window.py`, `tests/test_ui_layout.py` | **Retirado** |
| `src/autoclave/installation/wizard.py`, `factory_dialog.py` | Asistente de instalación tkinter (no escribía `vapor_source`, T9 SAF-02) | `main.py`, `ui/main.py` | **Retirado** (el asistente QML de T9 es el único) |
| `AutoclaveUI.spec` | Ejecutable viejo de `main.py` (tkinter, sin `ui_qml/assets`) | `dist/*.bat` | **Retirado** |
| `dist/Iniciar_Doble_Pantalla.bat`, `Iniciar_Puerta1.bat`, `Iniciar_Puerta2.bat` | Lanzaban `AutoclaveUI.exe` | operación manual | **Retirados** (versionados en git; el `.exe` viejo de `dist/` no está versionado y no se tocó) |
| `tests/test_ui_layout.py`, `test_main_hardware_wait.py`, `Interfaz.py`, `ventana_emergente.py` | Pruebas y prototipos tkinter | pytest (los dos últimos ya estaban excluidos) | **Retirados** |
| `src/autoclave/ui/service_ui/` (`backend_client`, `session_manager`, `ui_service_backend`) | Cliente del backend | **la UI QML** | **Se conserva** |
| Vistas PySide (`ui_pyside/`) | Menú de ajustes | engranaje | **Se conservan** (la Fase 5 de Opciones está fuera de alcance) |
| `AutoclaveBackend.spec`, `AutoclaveSettings.spec` | Ejecutables por separado (backend y PySide) | `lanzador_ajustes.py` fuera del exe único | Se conservan |

Retirados con `git rm` en el commit de R1 (reversible con `git revert`).

## 2. Funciones que solo hacía la ruta tkinter

Se migraron antes de retirarla:
- **Latido de apagado** (`heartbeat`, `data/last_shutdown.json`).
- **Ticket de arranque** (modelo, serie, versión, encendido/apagado, estado de backend y tarjeta).

Ahora los hace el **backend** (`backend/main.py` → `latido_y_ticket`, nuevo módulo `devices/printer/arranque_equipo.py`). Es el proceso de larga vida con cualquier lanzador y hay uno solo por equipo, así que no se duplican:
- espera a que el arranque deje el contexto operable;
- lee el último apagado **antes** de que el latido lo pise;
- arranca el latido;
- imprime el ticket en segundo plano;
- sin perfil, solo arranca el latido.

Prueba: `tests/test_r1_arranque_equipo.py` (6).

El resto de lo que hacía `main.py` ya lo cubre la ruta QML:
- **reloj** (`ClockTamperedError`): en `backend/context.py` y `puente_instalacion.py`;
- **asistente:** QML;
- **arranque del backend y PID** (`backend_guard`): en el lanzador del ejecutable único;
- **espera de la tarjeta:** barra de arranque y `/status`.

## 3. Punto de entrada único de producción

**`src/autoclave/exe_unico.py` + `Autoclave.spec` → `dist\Autoclave.exe`**, escritos por la sesión de Cristian el 19-oct. Están **sin commit por decisión de Cristian**; R1 no los modifica ni los commitea. Hace esto:
- un `.exe` onefile que se relanza con `--rol`;
- sin perfil, primero el asistente QML; al terminar, el arranque normal;
- **backend como subproceso supervisado:** `backend_guard`, PID, espera de 60 s y, al cerrar, `/outputs/reset` sin matar un ciclo en curso;
- **las 2 pantallas QML** vigiladas con relanzamiento (D-04) y la barra de tareas oculta;
- `--una-pantalla`;
- menú de ajustes PySide (`--rol ajustes`);
- instalación en `%ProgramFiles%` y datos en `%ProgramData%`.

Para desarrollo sigue `python -m autoclave.ui_qml.lanzar simulador|real` (en modo `real` no arranca el backend). `pyproject.toml` `[project.scripts] autoclave` apuntaba a un módulo inexistente (`autoclave.app`); ahora apunta a `autoclave.ui_qml.lanzar:main`.

### Cómo compilar (Cristian, en el PC industrial)

1. Entorno con las dependencias del proyecto (`pip install -e .` y `pyinstaller`).
2. `pyinstaller --noconfirm Autoclave.spec` → `dist\Autoclave.exe`.
3. **No** compilar `AutoclaveUI.spec` (retirado).

### Cómo probarlo

1. En un PC sin `installation_profile.json`: doble clic en `Autoclave.exe`. Ofrece instalarse en `%ProgramFiles%\Especifika\Autoclave`, abre el asistente QML y, al terminar, arranca el backend y las dos pantallas.
2. Con el perfil: arranca el backend, las pantallas de la puerta 1 y la 2 y el **ticket de arranque** impreso (Backend OK, Tarjeta OK).
3. Cerrar las dos pantallas fuera de ciclo: salidas apagadas y backend detenido. Con un ciclo en curso, el backend sigue.
4. Matar una pantalla con el Administrador de tareas: se relanza (hasta 3 veces).
5. Engranaje → menú de ajustes PySide.
6. Hoja de banco: A-01, A-02, C-03.

## 4. Pruebas

- Suite completa: ver `estado.md`. Antes: 3413 + G1 (30), con U4 de la otra sesión sin commitear en el mismo árbol.
- `grep tkinter` en `src`, `tests`, `tools`, `.spec` y `pyproject.toml`: sin resultados, **salvo**:
  - `src/autoclave/ui_qml/bridge/ui_bridge.py` y `lanzador_ajustes.py`: comentarios históricos en archivos que la otra sesión está editando en U4; PENDIENTE limpiarlos al cerrar U4;
  - `GeneradorCodigos.spec`: `excludes=['tkinter', ...]`, una exclusión funcional, no un uso.
- La documentación histórica (`docs/mis_plans`, `docs/informes`) conserva sus menciones.

## 5. DECISIONES SIN CONFIRMAR

- **D-R1-1:** el latido y el ticket de arranque pasan al backend en vez del lanzador. Así funcionan igual con `exe_unico` y con `ui_qml/lanzar.py`, sin tocar el archivo de la otra sesión.
- **D-R1-2:** se retiran también `dist/*.bat`. Con `Autoclave.exe` sobran: abre las dos pantallas solo.
- **D-R1-3:** el `.spec` de producción es el de la otra sesión (`Autoclave.spec`). R1 no crea otro para no duplicar.

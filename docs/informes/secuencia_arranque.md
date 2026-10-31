# Secuencia de arranque actual (2026-10-02)

Informe de solo lectura: no se modificó código. Cubre las tres formas de arrancar que existen hoy:

- **Ruta A — ejecutable de producción** `AutoclaveUI.exe` (`AutoclaveUI.spec:5` → `src/autoclave/main.py`): UI tkinter que lanza el backend ella misma. Procesos 1 y 2.
- **Ruta B — backend actual en desarrollo**, `python -m autoclave.backend.main` lanzado a mano en una terminal. Mismo código que el Proceso 2, con las diferencias de la sección "Backend lanzado a mano".
- **Ruta C — UI QML** (`python -m autoclave.ui_qml.app`, o sus lanzadores `ui_qml/lanzar.py` y `ui_qml/doble_pantalla.py`), que se conecta a un backend ya corriendo (el real de la Ruta B o el simulador) y termina en la pantalla de espera QML `Arranque.qml`.

Rutas relativas a `src/autoclave/` salvo que se indique otra cosa. Los tiempos marcados como **medido** se tomaron en este PC (Python de desarrollo, sin tarjeta conectada, base de datos copiada a la carpeta temporal); los marcados como **estimado** salen de leer el código (esperas, timeouts, intervalos) y no se midieron con el programa completo corriendo. El análisis es sobre la copia de trabajo actual, que tiene cambios sin commit en `services/domain/logging/db_manager.py` (migración de columnas de auditoría de usuarios).

## Resumen

Hay dos procesos. El de la UI (`main.py`) verifica el perfil de instalación, lanza el backend como subproceso, espera a que responda por HTTP, espera a que la tarjeta esté conectada, arranca el heartbeat de apagado y construye la ventana tkinter. El backend (`backend/main.py`) arranca uvicorn, y al importar `backend/server.py` construye `BackendContext`, que inicializa en orden: estado, alarmas, ciclos, parámetros globales, perfil, calibración, enlace serial (dos hilos), salidas, puertas, SQLite, auditoría de calibración, impresora en tiempo real (un hilo), registrador de ciclos y el hilo `ControlLoop`. Todo eso ocurre **antes** de que uvicorn abra el puerto 8000.

Tiempo típico con todo bien y tarjeta conectada: unos 3 a 6 s hasta ver la ventana principal. Peor caso realista (backend cae al arrancar, o la tarjeta no está): unos 45 a 90 s antes de que aparezca la ventana, por las dos esperas de 40 s encadenadas más 5 s de mensaje.

La UI QML hace mucho menos: no verifica perfil ni reloj, no lanza ni espera al backend, no espera a la tarjeta, no arranca el heartbeat ni imprime ticket. Abre la ventana en pantalla completa en ~0,7 s (medido sin pantalla física) y se queda en la pantalla de espera `Arranque` (reloj y logo) hasta que alguien toque la pantalla, o hasta que el backend reporte `CICLO`, `FALLA` o `EMERGENCIA`.

## Ruta A, Proceso 1 — UI tkinter (`main.py`)

| # | Archivo:línea / función | Recurso que inicializa | Si falla | Tiempo |
|---|---|---|---|---|
| U0 | `main.py:12-19` (importación del módulo) | `logging.basicConfig(INFO)`; importa `requests`, instalación, `heartbeat` | Error de importación → el proceso muere con traceback (en el .exe sin consola, sin rastro) | < 0,3 s (estimado) |
| U1 | `main.py:159` `_parse_args()` | Argumento opcional `--door {1,2}` | argparse imprime error y sale con código 2 | despreciable |
| U2 | `main.py:160` → `_configurar_logging_archivo()` (`main.py:24-38`) | Solo en .exe: archivo `data/ui.log` (o `ui_puerta{N}.log`) | Sin protección: si no se puede crear `data/` o el archivo, excepción y el proceso muere antes de dejar log | ms |
| U3 | `main.py:163-172` → `installation/bootstrap.py:11-28` `get_installation_profile()` | Lee `installation_profile.json` en `app_root()` (`installation/storage.py:11,18-36`), valida tipos y rangos (`installation/profile.py:53-104`) y comprueba el reloj (`installation/clock_guard.py:13-19`) | Archivo ausente → `None`. JSON corrupto o inválido → `logger.warning` y `None`. Reloj anterior a la fecha de instalación → `ClockTamperedError` → messagebox "Error de sistema" y `sys.exit(1)` | ms |
| U4 | `main.py:174-192` → `installation/wizard.py:23` `launch_installation_wizard()` | Solo si U3 dio `None`: asistente tkinter (número de serie, código de activación, modelo, puertas, enfriamiento) | Si el usuario no lo completa → `sys.exit(1)`. Si tras el asistente el perfil sigue inválido → `sys.exit(1)`. Reloj alterado → igual que U3 | Interactivo (lo que tarde el técnico) |
| U5 | `main.py:194-205` | Calcula `INSTALL_DOOR`, `SOURCE_DOOR`, modo doble pantalla y si esta ventana es secundaria | — | despreciable |
| U6 | `main.py:216` `is_backend_alive()` (`main.py:86-91`) | `GET http://127.0.0.1:8000/status` con timeout 1 s | Cualquier error de red → `False` (silencioso) | ~10 ms si no hay nada escuchando; hasta 1 s si algo acepta la conexión y no responde |
| U7 | `main.py:219` → `installation/backend_guard.py:46-54` `cleanup_stale_backend()` | Lee `data/backend.pid`; si existe, consulta la línea de comandos del PID con PowerShell/CIM (`backend_guard.py:24-36`) y, si es un backend, lo mata con `taskkill /F` | PID ilegible → `None`, no hace nada. Error de PowerShell → `False`, no mata nada. Error de `taskkill` → `warning`. Nunca detiene el arranque | 0 s sin PID; ~0,75 s **medido** con PID (consulta PowerShell), tope 5 s + 5 s |
| U8 | `main.py:221-227` | Lanza el backend con `subprocess.Popen` (`_backend_command()`, `main.py:72-83`: `AutoclaveBackend.exe` junto al .exe, o `python -m autoclave.backend.main` en desarrollo); `stdout` → DEVNULL; quita `_MEIPASS2` del entorno (`main.py:56-69`). Escribe el PID (`backend_guard.py:9-14`) | Si el .exe no existe, `Popen` lanza `FileNotFoundError` **sin capturar** → la UI muere. Error al escribir el PID → `warning` | ms |
| U9 | `main.py:228` → `wait_for_backend()` (`main.py:94-106`) | Sondea `/status` cada 0,5 s hasta 40 s | Si el subproceso termina (`poll()`), corta de inmediato y devuelve `False`. Si agota 40 s, `False`. En ambos casos solo `logger.error("…la UI arrancará sin datos")` y **sigue** | Lo que tarde el backend en abrir el puerto (ver Proceso 2): ~2-4 s típico (estimado); tope 40 s |
| U10 | `main.py:230` → `wait_for_hardware_connection()` (`main.py:109-155`) | Comprueba que `/status` no traiga la alarma `NO_HAY_CONEXION`. Si la trae, abre una ventanita tkinter "Conectando con la tarjeta..." que sondea cada 1 s | Agotados 40 s muestra "No se pudo establecer comunicación con la tarjeta…" durante 5 s y se cierra; **el arranque continúa igual**. El valor devuelto no se usa | 0 s si ya hay tarjeta; si no, ≥ 1 s (primer sondeo) hasta 45 s |
| U10b | `main.py:211-214` / `231-234` | Ventana secundaria (`--door` distinto al perfil) o PC de puerta 2: no lanza backend, solo `wait_for_backend(40)` | Si no responde, `warning` y continúa | hasta 40 s |
| U11 | `main.py:243` → `devices/printer/heartbeat.py:21-26` `read_last_shutdown()` | Lee `data/last_shutdown.json` (para el ticket de arranque) | Cualquier error → `None` (silencioso) | ms |
| U12 | `main.py:244` → `heartbeat.py:29-41` `start(30)` | Escribe `data/last_shutdown.json` ahora y cada 30 s con `threading.Timer` daemon | Error de escritura → `warning`, se reprograma igual | ms |
| U13 | `main.py:247-254` | Importa la UI tkinter y crea `BackendClient` (`ui/service_ui/backend_client.py:6-8`, sin E/S), `UIServiceBackend` (`ui/service_ui/ui_service_backend.py:22-37`) y `DoorCommandService` (`services/domain/puertas/door_command_service.py:5-7`, sin E/S) | Error de importación → muere. `UIServiceBackend` arranca un hilo daemon que pide `/status` cada 200 ms y `/global_params` + `/cycle` cada 5 s (`ui_service_backend.py:43-74`); si falla, `connected=False` y `logger.warning` en **cada** sondeo (5 por segundo con el backend caído) | Importación ~1,1 s **medido** (`ui.window.main_window`, incluye customtkinter y PIL) |
| U14 | `main.py:283-292` → `ui/window/main_window.py:39-95` `InterfazPrincipal.__init__` | Ventana `tk.Tk` en pantalla completa (`:65`) o posicionada en un monitor con `win32api` si hay `--door` (`:101-137`); construye cabecera, cuerpo y pie (`:143-157`) | Error al posicionar → `warning` y cae a pantalla completa. Error dentro de `_build_ui` no está capturado → la UI muere | ~0,2-0,5 s (estimado) |
| U15 | `main_window.py:87` → `:540-574` `_load_action_images()` (a los 300 ms) | Carga `open_door_N.png`, `close_door_N.png`, `start_cycle.png` | `logger.error` y los botones quedan sin imagen; la UI sigue | +0,3 s diferido |
| U16 | `main_window.py:88` → `:159-160`, `:216-218`, `:699-742` (cada 500 ms) | Refresco de pantalla desde la caché de `UIServiceBackend`: conexión, sensores; cada 1 s nombre y parámetros del ciclo, panel izquierdo, botón INICIAR (`_upd_listo`, `:816-827`, habilitado solo con `LISTO_PARA_CICLO`) | Excepción dentro del bloque → `warning` y sigue al siguiente tick | primer refresco a los 0,5 s |
| U17 | `main_window.py:89-90` → `:162-214` `_do_print_startup_ticket()` (hilo, a los 500 ms) | Ticket de arranque: sondea `/status` cada 0,5 s hasta 15 s esperando `card_connected`, arma el texto y lo manda a la impresora | Todo dentro de `try/except Exception` → `warning`. No bloquea la UI. Solo lo hace la ventana dueña del backend | 0-15 s en segundo plano |
| U18 | `main.py:293-295` | `protocol("WM_DELETE_WINDOW", on_close)` y `mainloop()` — la pantalla de espera ya está visible | — | — |

La "pantalla de espera" es la propia ventana principal mientras el backend está en `PREPARACION` (estado inicial, `state_machine/machine/enum_global.py:4`) o `PREPARADO`. No hay una pantalla de espera separada.

## Ruta A, Proceso 2 — Backend (`backend/main.py`)

| # | Archivo:línea / función | Recurso que inicializa | Si falla | Tiempo |
|---|---|---|---|---|
| B0 | `backend/main.py:10-22` `_configurar_logging_archivo()` | Solo en .exe: `data/backend.log` | Sin protección: excepción y el backend muere sin log | ms |
| B1 | `backend/main.py:27-32` `uvicorn.run("autoclave.backend.server:app", host="0.0.0.0", port=8000)` | Uvicorn importa `backend/server.py` | Cualquier excepción en B2-B17 se propaga aquí y el proceso termina; la UI lo detecta en U9 por `poll()` | importar fastapi/uvicorn/pydantic ~0,5 s **medido** |
| B2 | `backend/server.py:20, 26, 29, 31` (nivel de módulo) | Ruta de tickets; `context = BackendContext()`; `ActividadUI()`; `CALIBRATION_PATH = calibration_path()` | Todo B3-B17 corre aquí, **al importar el módulo y antes de abrir el puerto** | — |
| B3 | `backend/context.py:27` `EstadoAutoclave()` | Estado compartido en memoria | Excepción → backend muere | despreciable |
| B4 | `context.py:28` `AlarmManager(estado)` | Gestor de alarmas | Ídem | despreciable |
| B5 | `context.py:31,33` → `core/managers/cycle_manager.py:79-132` `load_all_cycles()` | Lee todos los `.json` de `cycles/factory` y luego `cycles/user` (los de usuario pisan a los de fábrica con el mismo `cycle_id`); descarta números de ciclo repetidos | Carpeta ausente → `print("❌ No existe la carpeta")` y sigue. JSON corrupto → `print("⚠️ Error cargando …")` y se salta ese ciclo. Ambos con `print`, no con `logger`: en el .exe el `stdout` del backend va a DEVNULL (U8), así que **se pierden** | ~40 ms **medido** junto con B6 |
| B6 | `context.py:32,34` → `core/managers/config_manager.py:10-14` `load_config()` | Lee `config/global_params.json` | Sin protección: archivo ausente o JSON inválido → backend muere | (incluido arriba) |
| B7 | `context.py:36` → `cycle_manager.py:134-139` `set_default_cycle("bowe_dick")` | Selecciona el ciclo inicial, fijo en código | Si no existe `bowe_dick` → `Exception` → backend muere. Hoy existe en `cycles/factory` y `cycles/user` | despreciable |
| B8 | `context.py:39-41` `get_installation_profile()` | Vuelve a leer y validar el perfil (igual que U3) | `None` → `RuntimeError("Backend sin InstallationProfile")`; reloj alterado → `ClockTamperedError`; ambos matan el backend | ms |
| B9 | `context.py:42` `get_capabilities(...)` | Capacidades del equipo según su clase | Excepción → backend muere | despreciable |
| B10 | `context.py:47` → `devices/factory/factory.py:49` `Units(calibration_path())` → `hal/measures/units.py:24-36`, `config/__init__.py:8-21` | Calibración: lee y valida `calibration.yaml` con pydantic (`AppConfig`). En .exe, `utils/paths.py:25-42` copia la de fábrica a `data/calibration.yaml` la primera vez | Archivo ausente, YAML inválido o validación fallida → excepción → backend muere. No hay respaldo a valores por defecto en esta ruta (el `AppConfig()` por defecto solo se usa si no se pasa ruta) | ~0,2 s **medido** (incluye importar pydantic/yaml) |
| B11 | `factory.py:50-52` → `protocols/serial_link.py:35-68`, `:74-89` | Crea `SerialLink` (115200 baudios) y arranca dos hilos daemon: lectura (`:176-192`) y vigilancia (`:194-207`). La llamada `serial._scan_ports()` de `factory.py:51` descarta su resultado: no conecta nada | `start()` no lanza. Sin puerto ESP32/CP210/CH340 → `_connect()` devuelve `False` **sin ningún log** y reintenta cada 3 s para siempre. Error al abrir → `warning`; tras 5 errores de "dispositivo no funcional" intenta un reset PnP una vez por episodio (`:128-147`). Sin datos 3 s → desconecta y vuelve a escanear | Escaneo ~25 ms **medido**; primer intento de conexión inmediato en el hilo de vigilancia; la conexión se considera viva al llegar la primera trama (`:243`) |
| B12 | `factory.py:54`, `:12-45` | Configuración de puertas (canales DO/DI/AI) según `door_count` y `door_type` | — | despreciable |
| B13 | `context.py:49` → `devices/io/set_io.py:10-13` `SetOutput` | Salidas digitales, bomba de vacío y `BuzzerPlayer` (`devices/buzer/buzer.py:4-14`). El buzzer no tiene hilo ni audio propio: es una salida digital secuenciada desde el `ControlLoop` (paso 7 del tick). No hay inicialización de audio por tarjeta de sonido en esta ruta | Excepción → backend muere | despreciable |
| B14 | `context.py:51-62` → `devices/puertas/door_factory.py:6-29` | `SimpleDoor` o `AdvancedDoor` por cada puerta | Ídem | despreciable |
| B15 | `context.py:65-71` `ServicioPuertas(...)` | Servicio de dominio de puertas | Ídem | despreciable |
| B16 | `context.py:74` → `services/domain/logging/db_manager.py:123-134` `DbManager()` | SQLite `data/autoclave.db` (crea `data/` si falta), conexión única con `check_same_thread=False` protegida por `Lock`; aplica el esquema (`:140-144`), migraciones aditivas (`:146-165`) y siembra el usuario `admin`/`admin1234` si la tabla está vacía (`:416-431`) | Migración que ya existe → `OperationalError` ignorado a propósito. Cualquier otro error (archivo bloqueado, disco lleno, base corrupta) → excepción → backend muere | ~12 ms **medido** (copia de la base actual y base nueva) |
| B17 | `context.py:75` → `services/domain/logging/sensor_calibration_audit.py:28-31` | Segunda conexión a la **misma** `data/autoclave.db`, crea la tabla de auditoría de calibración y cierra | Excepción → backend muere | ms |
| B18 | `context.py:76` → `devices/printer/realtime_printer.py:13-17` `RealtimePrinter()` | Cola + hilo daemon de impresión en tiempo real | La creación no falla; cada impresión fallida → `warning` y se descarta | despreciable |
| B19 | `context.py:77-84` → `services/domain/logging/cycle_logger.py:99-124` `CycleLogger(...)` | Registrador de ciclos (solo estado en memoria) | Excepción → backend muere | despreciable |
| B20 | `context.py:86-99` → `services/domain/loop/control_loop.py:39-78` `ControlLoop(...)` | Toma el ciclo seleccionado (`get_selected_cycle()`); construye `StateMachine` (`state_machine/state_machine.py:15-30`, que crea **su propio** `AlarmManager` y los estados PREPARACION, PREPARADO, CICLO, FALLA, HIBERNACION), `EmergencyStop` y `SuministroElectrico` | Excepción → backend muere | despreciable |
| B21 | `context.py:100` → `control_loop.py:237-244` `start()` | Hilo daemon `ControlLoop`, periodo 0,5 s (`:84-90`) | Cada excepción en un tick → `warning` y sigue en el siguiente. Primer tick inmediato: como `link_was_connected` arranca en `True` y aún no hay tarjeta, reporta enseguida la alarma `NO_HAY_CONEXION` (`:96-108`), sin imprimir ticket porque nunca hubo conexión (`:112`). Sin conexión, el tick sale temprano (`:140-141`); con conexión publica el estado y la `StateMachine` entra en `PREPARACION` (`state_machine.py:36-38`) | tick cada 0,5 s |
| B22 | Uvicorn abre `0.0.0.0:8000` | Servidor HTTP | Puerto ocupado → uvicorn registra el error y el proceso termina, **con el serial ya abierto y el `ControlLoop` ya corriendo** hasta que el proceso sale | ~ms tras terminar la importación |

Tiempo del backend hasta responder `/status`: ~1 a 2 s de importaciones e inicialización con Python de desarrollo (medido por partes: 0,5 + 0,2 + 0,06 s más importaciones restantes); en el .exe de un solo archivo hay que sumar la extracción de PyInstaller, que no se midió. La tarjeta pasa a "conectada" cuando llega la primera trama, normalmente en menos de 1 s tras abrir el puerto (estimado).

## Línea de tiempo típica (tarjeta conectada, sin perfil nuevo)

1. 0 s — arranca `AutoclaveUI`, lee perfil (U0-U5).
2. ~0,1-1 s — limpieza de backend huérfano y lanzamiento del backend (U6-U8).
3. ~1-4 s — el backend importa, inicializa todo y abre el puerto; `wait_for_backend` lo detecta en el siguiente sondeo de 0,5 s (U9, B0-B22).
4. ~0-1 s más — `wait_for_hardware_connection` ve que ya no está `NO_HAY_CONEXION` y no abre la ventanita (U10).
5. ~1-1,5 s más — importa la UI tkinter y construye la ventana (U13-U14).
6. Ventana visible en pantalla completa; a los 0,3 s aparecen las imágenes de botones y a los 0,5 s el primer refresco de datos (U15-U16). El ticket de arranque sale en segundo plano.

Total: unos 3 a 6 s. Si falta la tarjeta: +40 s de ventanita y +5 s de mensaje antes de la ventana principal. Si el backend no arranca: U9 corta rápido (el proceso hijo murió), pero U10 igual espera 45 s, porque `_hardware_connected()` da `False` sin backend.

## Ruta B — Backend lanzado a mano (`python -m autoclave.backend.main`)

Es la forma actual de levantar el backend real para la UI QML (lo indican `ui_qml/app.py:10`, `ui_qml/doble_pantalla.py:8-9` y el aviso de `ui_qml/lanzar.py:107-109`). Ejecuta exactamente los pasos B0-B22 de arriba, con estas diferencias respecto a cuando lo lanza `AutoclaveUI.exe`:

| Aspecto | Lanzado por `main.py` (Ruta A) | Lanzado a mano (Ruta B) |
|---|---|---|
| Log a archivo (B0) | `data/backend.log` solo si es .exe | No hay archivo: todo sale por la consola, incluidos los `print` de la carga de ciclos (B5), que aquí sí se ven |
| `data/` (perfil, BD, PID, último apagado) | Junto al .exe | Raíz del repo (`utils/paths.py:22`) |
| Calibración (B10) | Copia en `data/calibration.yaml` | El archivo del repo `src/autoclave/config/calibration.yaml` (`utils/paths.py:34-36`); cada recalibración lo sobreescribe y hace commit automático (`backend/server.py:92`) |
| Perfil / reloj | Ya verificado antes por la UI (U3); el asistente puede haberlo creado | Solo B8: si el perfil falta o el reloj está atrasado, el backend muere con `RuntimeError`/`ClockTamperedError` y traceback en consola. No lanza el asistente |
| Backend huérfano / PID (U7, U8) | Limpia el huérfano y escribe `data/backend.pid` | Nada de eso. Si ya hay otro backend en el 8000, este inicializa todo (abre el serial si está libre, arranca el `ControlLoop`) y luego uvicorn falla al abrir el puerto y el proceso termina |
| Espera a tarjeta (U10) | Sí, hasta 45 s | No aplica: el backend arranca igual y reporta `NO_HAY_CONEXION` hasta que llegue la primera trama |
| Heartbeat y ticket de arranque (U11-U12, U17) | Sí | No: los hace la UI tkinter, no el backend. Con la UI QML no se escribe `last_shutdown.json` ni se imprime ticket de arranque |
| Apagado de salidas al cerrar | `on_close` llama `/outputs/reset` y termina el backend (`main.py:256-281`) | Ctrl+C mata el proceso; la UI QML nunca toca salidas al salir (`ui_qml/app.py:122-127`) |

Tiempo hasta responder `/status`: ~1-2 s con Python de desarrollo (mismas mediciones que el Proceso 2).

## Ruta C — UI QML

### C.1 Lanzadores

| Comando | Archivo:línea | Qué hace | Si falla | Tiempo |
|---|---|---|---|---|
| `python -m autoclave.ui_qml.lanzar real [--una-pantalla] [--door N]` | `ui_qml/lanzar.py:90-122` | Sondea `http://127.0.0.1:8000/status` durante 1 s (`esperar_backend`, `:36-46`, timeout 0,8 s por intento, cada 0,3 s). Quita `AUTOCLAVE_BACKEND_URL` del entorno (`:71-76`) y lanza uno o dos procesos `ui_qml.app` (`--door 1 --screen 0` y `--door 2 --screen 1`, comandos de `doble_pantalla.py:34-39`) con `cwd` en la raíz del repo | Si el backend no responde, solo `warning` ("arráncalo en otra terminal…") y lanza las pantallas igual. No arranca el backend | ~1 s de sondeo como máximo + arranque de cada pantalla |
| `python -m autoclave.ui_qml.lanzar simulador [--velocidad 10]` | `ui_qml/lanzar.py:95-104` | Lanza `python -m autoclave.simulador --puerto 8001` y espera hasta 20 s a que responda; luego lanza las pantallas con `AUTOCLAVE_BACKEND_URL=http://127.0.0.1:8001` | Si el simulador no responde en 20 s: `error`, lo termina y sale con código 1 sin abrir pantallas. Al cerrar las pantallas detiene el simulador (`:118-121`) | ~1 s típico (estimado: import de fastapi/uvicorn 0,5 s **medido** + carga del ciclo 12 ms **medido**) |
| `python -m autoclave.ui_qml.doble_pantalla` | `ui_qml/doble_pantalla.py:42-57` | Lanza los dos procesos `ui_qml.app` (puerta 1 y 2) sin comprobar nada | Si una pantalla se cierra, la otra sigue. Ctrl+C termina ambas | despreciable |
| `python -m autoclave.ui_qml.app --door N --screen I` (o `ui_qml.main`, alias en `ui_qml/main.py:5`) | `ui_qml/app.py:102-163` | Una sola pantalla; ver C.2 | — | ~0,7 s |

### C.1b Simulador (`python -m autoclave.simulador`)

| # | Archivo:línea | Recurso | Si falla | Tiempo |
|---|---|---|---|---|
| S1 | `simulador/__main__.py:41` → `simulador/repeticion.py:38-63` `cargar_ciclo()` | Abre `data/autoclave.db` en **solo lectura** (`?mode=ro`) y toma el último ciclo `COMPLETADO` con lecturas suficientes (o `--ciclo`) | Sin ciclo apto → `LookupError` sin capturar → el simulador muere (y `lanzar simulador` sale tras 20 s de espera). BD inexistente → error de SQLite, igual | 12 ms **medido** |
| S2 | `simulador/__main__.py:44-54` | `CycleManager.load_all_cycles()` y `ConfigManager.load_config()` (mismos que B5-B6) | Programa del ciclo no encontrado → `warning` y usa el primero disponible. `global_params.json` inválido → muere | ~40 ms **medido** |
| S3 | `simulador/__main__.py:59-60` → `simulador/servidor.py:56-201` | FastAPI con los endpoints que usa la UI, en `127.0.0.1` (no `0.0.0.0`). No usa tarjeta, serial, `ControlLoop`, máquina de estados ni escribe en la BD | Puerto ocupado → uvicorn termina | ~0,5 s de importaciones **medido** |

### C.2 Proceso de una pantalla QML (`ui_qml/app.py:102-163`)

| # | Archivo:línea / función | Recurso que inicializa | Si falla | Tiempo |
|---|---|---|---|---|
| Q0 | `ui_qml/app.py:14-54` (importación) | PySide6, `BackendClient`/`UIServiceBackend` (los mismos de tkinter), puentes, controladores de teclado y de login (al importarse se registran en QML con `qmlRegisterType`; `ui_qml/controllers/__init__.py` importa `login_controller`). Resuelve `QML_DIR`, `FUENTES_DIR`, `TEXTOS_ES` con `resource_path` | Error de importación → muere con traceback | 0,4 s **medido** |
| Q1 | `app.py:103-104` → `parse_args()` (`:57-68`) | `--door` (sin él: `warning` y puerta 1) y `--screen` | argparse sale con código 2 | despreciable |
| Q2 | `app.py:106-108` | `QGuiApplication`; fuerza tema claro (`:94-99`); registra las fuentes `.otf` (`:85-91`) | Carpeta de fuentes ausente → `warning` y sigue con las del sistema | ms |
| Q3 | `app.py:110` → `url_backend()` (`:48-50`) | `AUTOCLAVE_BACKEND_URL` si existe, si no `http://127.0.0.1:8000` | — | despreciable |
| Q4 | `app.py:111` → `ui/service_ui/ui_service_backend.py:22-37` | Hilo daemon que pide `/status` cada 200 ms y `/global_params` + `/cycle` cada 5 s | Sin backend: `connected=False` y `warning` en cada sondeo (5 por segundo); reintenta para siempre y se conecta solo cuando el backend aparece | — |
| Q5 | `app.py:112` → `ui_qml/bridge/ui_bridge.py:135-152` `UiBridge` | `QTimer` de 500 ms que copia la caché de `UIServiceBackend` a propiedades QML (sin red), con un primer refresco inmediato | Sin datos: estado `DESCONOCIDO`, valores congelados | — |
| Q6 | `app.py:113-115` | `ComandosPuerta` (`bridge/comandos_puerta.py:31-44`), `ComandoIniciarCiclo` (`bridge/comandos_ciclo.py:28-34`): solo objetos, sin E/S hasta que se pulsa algo | — | despreciable |
| Q7 | `app.py:116` → `bridge/info_equipo.py:24-39`, `:104-113` | Lee `installation_profile.json` **solo para mostrar** (sin validar reloj ni lanzar asistente) y la versión del paquete | Perfil ilegible → `warning`, `None` (modelo/serie vacíos). Versión no encontrada → `None` (aquí sí se captura `PackageNotFoundError`) | ms |
| Q8 | `app.py:117` → `bridge/lanzador_ajustes.py:41-49` | Lanzador del menú de ajustes PySide (`AutoclaveSettings.exe` o `python -m autoclave.ui_pyside.app`); solo crea un `QTimer`, no lanza nada al arrancar | — | despreciable |
| Q9 | `app.py:118` → `bridge/standby.py:68-92` | `Standby`: arranca con `activo=True` (pantalla de espera), `QTimer` de 500 ms; periodo de gracia de 10 s (`GRACIA_ARRANQUE_S`, `:35`) en el que los cambios de estado/alarmas del equipo no despiertan la pantalla. Usa `time.monotonic()` | Sin backend: decide solo con la actividad local | — |
| Q10 | `app.py:119-120` → `bridge/progreso_ciclo.py:35-51`, `bridge/comandos_ciclo_en_curso.py:32-39` | Progreso del ciclo (`QTimer` de 1 s que solo arranca al entrar en ciclo, `:108-109`) y comandos cancelar/confirmar | — | despreciable |
| Q11 | `app.py:131-143` | `QQmlApplicationEngine`, ruta de importación del módulo `Tema`, propiedades iniciales y `textosJson` = `assets/textos/es.json` (`:80-82`) | `es.json` ausente o inválido → excepción **sin capturar** → la pantalla muere | ms |
| Q12 | `app.py:144-148` → `qml/Main.qml` | Carga `Main.qml`; el `StackView` arranca en `esperaComp` = `Pantallas/Arranque.qml` (`Main.qml:99-105`, `:117-128`) | Si no hay objetos raíz → `error`, detiene timers e hilo y sale con código 1. Errores de QML no fatales solo salen en consola | ~0,3 s **medido** junto con Q13 (sin pantalla física; con GPU real puede variar) |
| Q13 | `app.py:150-162` | Elige el monitor (`elegir_pantalla`, `:71-77`), pantalla completa, foco solo en la puerta 1, filtro de eventos del standby | Monitor inexistente → `warning` y usa el primario | (incluido arriba) |
| Q14 | `app.py:163` `app.exec()` | Bucle de eventos. Pantalla de espera visible: `Arranque.qml` (reloj con `Timer` de 1 s y logo, sin dependencias de backend, `Pantallas/Arranque.qml:4,25`) | — | — |

**Salida de la pantalla de espera** (`Main.qml:45-77`, `bridge/standby.py:49-58`, `:126-150`):

- Si el backend reporta `CICLO`, `FALLA` o `EMERGENCIA` (`ESTADOS_SIN_STANDBY`, `standby.py:36`), el standby se desactiva y la UI va directo a la pantalla principal. Si ya estaba en `CICLO` al cargar, `Main.qml:77` la lleva a `PantallaCicloEnCurso` sin esperar el toque.
- En cualquier otro estado (incluidos `PREPARACION`/`PREPARADO`, o sin backend), se queda en `Arranque` hasta que alguien toca la pantalla: el filtro de eventos registra la actividad, avisa al backend con `POST /ui/activity` (para que la otra pantalla también despierte) y el standby pasa a `False` → `PantallaPreciclo`. Vuelve a `Arranque` tras `tiempo_standby` minutos sin actividad (5 por defecto, `config/global_params.json:15`).
- El login (`Login.qml`) solo se abre desde el avatar. Su controlador abre `data/autoclave.db` con `DbManager` la primera vez que se usa (`ui_qml/controllers/login_controller.py:26-46`), no al arrancar.

## Hallazgos que conviene revisar (no corregidos)

1. **Todo el backend se inicializa al importar `server.py`** (`server.py:26`), antes de que uvicorn abra el puerto. Si el puerto 8000 está ocupado, el serial ya se abrió y el `ControlLoop` ya arrancó antes de que el proceso termine.
2. **Doble espera de 40 s encadenada** (U9 + U10): con el backend caído la UI tarda unos 45 s de más en aparecer, y `wait_for_hardware_connection` muestra "No se pudo establecer comunicación con la tarjeta" aunque el problema real sea el backend.
3. **Errores de carga de ciclos se pierden en el .exe**: `cycle_manager.py:106,132` usan `print`, y el `stdout` del backend va a DEVNULL (`main.py:223`). Un JSON de ciclo corrupto desaparece de la lista sin dejar rastro en `backend.log`.
4. **Sin log cuando no hay puerto serial**: `serial_link.py:108-110` devuelve `False` sin registrar nada; el único síntoma es la alarma `NO_HAY_CONEXION`.
5. **`FileNotFoundError` sin capturar** si falta `AutoclaveBackend.exe` junto al .exe de la UI (`main.py:221`): la UI muere sin mensaje en pantalla (sí queda en `ui.log`).
6. **Ticket de arranque probablemente no se imprime en el .exe**: `main_window.py:205` usa `importlib.metadata.version("autoclave")`, y `AutoclaveUI.spec` no copia los metadatos del paquete (`copy_metadata`). Si lanza `PackageNotFoundError`, el `except` general lo deja solo como `warning`. No verificado con un build real.
7. **Usuario `admin`/`admin1234` sembrado por defecto** en una base vacía (`db_manager.py:416-431`).
8. **Ciclo inicial fijo en código**: `set_default_cycle("bowe_dick")` (`context.py:36`) mata el backend si ese ciclo falta o se renombra.
9. **Dos `AlarmManager`**: uno en `BackendContext` (`context.py:28`) y otro dentro de `StateMachine` (`state_machine.py:22`). Ambos escriben sobre el mismo `estado`, pero conviene confirmar que no dupliquen ni pierdan alarmas.
10. **Spam de log con backend caído**: `ui_service_backend.py:63` registra un `warning` en cada sondeo de 200 ms.
11. **Detalle de temporización**: el `_watchdog_loop` de `serial_link.py:198`, `_check_timeout` (`:213`) y `BuzzerPlayer` (`buzer.py:23,37`) miden intervalos con `time.time()`/`datetime.now()`, no con `time.monotonic()` como pide la convención del proyecto para temporizadores de proceso. Un salto del reloj de pared puede adelantar o retrasar el reescaneo, el timeout de datos de 3 s o el patrón del buzzer.

### Hallazgos propios de las rutas B y C

12. **Con la UI QML nadie hace la verificación de instalación ni el arranque supervisado**: no se valida el reloj ni se lanza el asistente (Q7 solo lee el perfil para mostrarlo), no se limpia un backend huérfano, no se escribe `last_shutdown.json` ni se imprime el ticket de arranque, y al cerrar no se apagan salidas. Hoy todo eso vive solo en `main.py` (tkinter); cuando la UI QML reemplace a tkinter habrá que decidir dónde queda.
13. **`es.json` sin protección** (`ui_qml/app.py:80-82`, `:143`): si falta o está mal formado, la pantalla QML muere con traceback antes de mostrar nada.
14. **Dos procesos escriben en `data/autoclave.db`** cuando se usa el login QML: el backend (B16-B17) y cada pantalla QML (`login_controller.py:26-28`), que además corre el esquema, las migraciones y la siembra del `admin` desde su propio proceso. SQLite lo tolera, pero un bloqueo momentáneo daría `database is locked` sin reintento en `DbManager`.
15. **Backend de la Ruta B con el puerto ocupado**: como en el hallazgo 1, inicializa serial y `ControlLoop` antes de fallar al abrir el 8000. Lanzar el backend dos veces por error (fácil en desarrollo, porque nada lo impide) no deja rastro claro: el segundo muere con un error de uvicorn tras haber corrido toda la inicialización.
16. **`lanzar real` solo espera 1 s** al backend y no lo arranca; si el backend está iniciando, la pantalla queda en `Arranque` con `connected=False` y se conecta sola después (comportamiento correcto, solo genera un `warning` y el spam de log del hallazgo 10 hasta que responde).

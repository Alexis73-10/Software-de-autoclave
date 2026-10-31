# Planeación — Migración total de la UI de tkinter a QML

Proyecto: Software-de-autoclave (Especifika S.A.S.)
Ubicación sugerida: `docs/mis_plans/planeacion_migracion_qml.md`
Estado: BORRADOR v0.3 — F1 y F2 arrancan de inmediato; la reubicación de `service_ui` pasa a ser paso previo de F6; verificaciones restantes en sección 9
Referencias: `planeacion_ui_dual_pantalla.md`, `planeacion_menu_principal.md`, IEC 62304 (Clase C), ISO 14971, IEC 62366-1, IEC 60601-1-8

Cambios v0.2: MIG-01 reconocido (ejecución solo en PC de desarrollo); MIG-02 aprobado; login QML pospuesto (se usa el login de PySide); MIG-03 reclasificado; MIG-04(a) confirmado; se agregan MIG-10 y V-MIG-11/12.
Cambios v0.3: F0 queda solo como inventario de solo lectura y corre en paralelo (no bloquea); F1 y F2 se ejecutan juntos en la primera instrucción, con el puente ya en modo lectura; los comandos (puerta, iniciar ciclo, avatar) se conectan en una segunda instrucción; la reubicación de `service_ui` se mueve al paso 1 de F6.

---

## 1. Objetivo

Reemplazar por completo la interfaz tkinter/CustomTkinter por una interfaz PySide6/QML. Al terminar, no queda código tkinter en ejecución ni en el repositorio. La migración arranca con las pantallas de espera y de ciclo (previa al inicio). La pantalla de login QML ya existe pero por ahora no se conecta: el login se resuelve con el de PySide.

Flujo de esta fase:

    espera --(toque)--> ciclo
    ciclo --(avatar)--> subproceso PySide de configuración (login y menús PySide)

La pantalla de ciclo debe reaccionar al estado del backend en tiempo real.

Entorno de ejecución de esta fase: solo PC de desarrollo, para validar el flujo backend ↔ QML. No se instala en equipos de campo.

## 2. Decisiones vigentes (confirmadas por Cristian)

1. Pantallas QML existentes: espera, ciclo (previa al inicio) y login. En esta fase se conectan espera y ciclo.
2. La pantalla de espera es la misma de arranque: solo muestra el reloj. Al tocarla cambia a la pantalla de ciclo.
3. Migración total y sin coexistencia: tkinter y QML no conviven; se retira tkinter por completo (F6).
4. Dos UI independientes, una por monitor (arquitectura de `planeacion_ui_dual_pantalla.md`).
5. La pantalla de ciclo de esta fase es la previa al inicio. La pantalla de "ciclo en curso" aún no existe. Los estados terminales (COMPLETADO, CANCELADO, EMERGENCIA, FALLO_*) y su confirmación por el operador no se migran hasta que existan esas pantallas; se definirán entonces.
6. Canal de datos: polling (ver 4.3).
7. El ticket de arranque se mantiene. El apagado de equipo desaparece: el apagado será por corte de energía. Todas las salidas tienen estado seguro al perder alimentación (confirmado).
8. Las vistas PySide6 de configuración coexisten temporalmente hasta que se rehagan en QML. Por ahora se usa el login de PySide.
9. Contenido de la pantalla de ciclo (mockup-01): sin gráfica, sin barra de fases, sin tiempo transcurrido; espacio liberado para el listado de alarmas o avisos; botón único abrir/cerrar puerta; botón "Iniciar ciclo"; avatar de usuario en la barra inferior.
10. MIG-01 reconocido: esta fase no se ejecutará en un equipo, solo en PC para ver el flujo backend ↔ QML.
11. Reubicación de `service_ui` a un paquete neutral aprobada. Nombre elegido: `autoclave/ui_common/`. Se ejecuta como paso 1 de F6; no bloquea el arranque de QML (mientras tanto el puente importa desde `autoclave.ui.service_ui`).

## 3. Estado actual (evidencia en código)

- `autoclave/ui/window/main_window.py` — `InterfazPrincipal(tk.Tk)`: un proceso por puerta (`source_door` 1|2). Lee del caché de `UIServiceBackend` cada 500 ms (sensores) y cada 1 s (nombre de ciclo, parámetros, panel izquierdo, "listo", suministro). Acciones: puerta (open/close vía `door_commands`), `start_cycle`, reset de falla, apagado, ticket de arranque, lanzamiento de settings PySide6 por `subprocess` (oculta la ventana con `withdraw` y la restaura al terminar el proceso), detección de orientación.
- `autoclave/ui/cycle/cycle_window.py` — `CycleWindow(tk.Toplevel)`: ciclo en curso con fase, gráfica (`LiveGraph`, matplotlib), `CycleBuffer`, abortar con confirmación y confirmación de fin de ciclo. NO se migra en esta fase.
- `autoclave/ui/service_ui/` — `BackendClient` (requests, timeout 0.8 s) y `UIServiceBackend` (hilo propio de polling con caché protegido por lock; expone `start_cycle`, `abort_cycle`, `acknowledge_cycle`, `reset_fault`, `reset_outputs`, `list_user_cycles`, `select_cycle`, `get_estado_puerta`, etc.).
- `autoclave/ui_pyside/` — `app.py` abre `MainWindowFluent` en pantalla completa sin marco, en la vista `home`. El login es una vista (`login`) accesible desde el pie de página o la tarjeta "Login" de home; tras un login válido navega a `admin_menu`. `SessionManager` guarda la sesión en memoria del proceso PySide. El botón "Salir" cierra la aplicación PySide y devuelve el control al proceso que la lanzó. Existe otro `BackendClient` en `ui_pyside/services/backend_client.py`, además de la copia en `ui/service_ui/` (V-MIG-12).
- `autoclave/ui_qml/assets/textos/es.json` — textos ya existentes para QML.
- Puntos de entrada: `autoclave/main.py` y `autoclave/ui/main.py` (V-MIG-02). Ambos usan tkinter; `autoclave/main.py` incluye `wait_for_hardware_connection()` con ventana tkinter.

## 4. Arquitectura destino

### 4.1 Procesos

- Un proceso QML por monitor/puerta, con argumento de puerta. Supervisión por el launcher definido en `planeacion_ui_dual_pantalla.md` (verificar contra el código actual, V-MIG-02).
- Cada proceso selecciona su monitor mediante `QScreen` y abre en pantalla completa.
- Motor: `QQmlApplicationEngine` con `StackView` para navegación. Sin componentes SOUP nuevos: PySide6 ya está en el proyecto.
- Avatar: lanza `python -m autoclave.ui_pyside.app` como subproceso (mismo mecanismo que hoy en tkinter). Mientras el subproceso corre, la ventana QML se oculta o se baja; al terminar el proceso se restaura. Esta fase no muestra usuario en el avatar: la sesión vive y muere dentro del subproceso PySide (MIG-03).

### 4.2 Capas

- QML (presentación): solo muestra estado y emite intenciones del operador. No contiene lógica de enclavamiento ni reglas de habilitación propias.
- Puente Python `UiBridge(QObject)` en `autoclave/ui_qml/bridge/`: propiedades con señal de cambio (NOTIFY) y slots de acciones.
- Servicios existentes (`UIServiceBackend`, `DoorCommandService`) reutilizados sin duplicar lógica. Se importan desde `autoclave.ui.service_ui` hasta la reubicación a `autoclave/ui_common/` (F6, paso 1).

### 4.3 Canal de datos

`UIServiceBackend` ya corre un hilo de polling con caché y lock. El puente NO abre un segundo polling HTTP: un `QTimer` en el hilo de la GUI lee los getters del caché (500 ms) y emite señales solo cuando el valor cambia. Sin cambios en el backend.

Justificación: evita duplicar tráfico HTTP por proceso y mantiene el hilo de la GUI libre de red.

### 4.4 Comandos

`BackendClient` bloquea hasta 0.8 s por llamada. Los comandos (`door_commands.open/close`, `start_cycle`) se ejecutan en un hilo de trabajo (`QThreadPool`/`QRunnable`) y devuelven el resultado por señal. Nunca se invocan desde el hilo de la GUI, para no congelar la interfaz durante un timeout.

### 4.5 Propiedades y slots iniciales del puente (propuesta)

Propiedades:
- `connected` (bool) — derivada de la alarma `NO_HAY_CONEXION` de `/status` y del estado de `UIServiceBackend`.
- `machineState` (str) — `machine_state` de `/status`.
- `doorState` (str) — estado de la puerta propia (`get_estado_puerta`).
- `alarms` — `QAbstractListModel` con id, nivel, descripción y estado de origen (campos de `/status`).
- `canStartCycle` (bool) — misma condición que hoy evalúa `_upd_listo` (V-MIG-06).

Slots:
- `toggleDoor()`, `startCycle()`, `openSettings()`.
- Señal `toast(str)` para el motivo devuelto por el backend cuando un comando es rechazado.

### 4.6 Reglas de comportamiento de la pantalla de ciclo (reacción al backend)

- La UI refleja el estado que reporta el backend; no lo infiere ni lo predice.
- Si `connected` es falso: botones deshabilitados y aviso de `sistema.sin_conexion` (ya en `es.json`); no se muestran valores como vigentes.
- El botón de puerta cambia ícono y acción según `doorState`. Si el backend rechaza el comando (enclavamiento), se muestra el motivo recibido.
- "Iniciar ciclo" solo se habilita cuando `canStartCycle` es verdadero. La decisión es del backend; la UI no replica reglas.
- El listado de alarmas se actualiza al cambiar `alarms`. Colores y prioridades conforme a IEC 60601-1-8. Los assets SVG deben cumplir SVG Tiny 1.2 (restricción del renderizador SVG de Qt).

## 5. Fases de migración

### F0 — Inventario (solo lectura, en paralelo, no bloquea)
- Claude Code inventaría los `.qml` existentes y responde V-MIG-01, 02, 06, 12, MIG-04 (b) y (c) y MIG-07. No modifica nada.
- Se ejecuta dentro de la primera instrucción, antes de construir F1/F2.
- Salida: reporte en texto plano.

### F1 — Infraestructura QML
- Punto de entrada QML con argumento de puerta y selección de monitor.
- `UiBridge`, modelo de alarmas, carga de textos desde `es.json`, `StackView` de navegación.
- Se ejecuta junto con F2 en la primera instrucción. El puente arranca en modo lectura: `connected`, `machineState`, `doorState` y `alarms`. Los slots de comandos no se conectan todavía.
- Salida: app QML arranca en el monitor indicado por argumento y muestra la pantalla de espera.

### F2 — Pantalla de espera
- Reloj en vivo (hora del sistema). Toque en cualquier zona navega a ciclo.
- Comportamiento definido para arranque sin conexión y para estados de máquina distintos de reposo (MIG-09, V-MIG-05).
- Salida: navegación espera → ciclo verificada visualmente en ambos monitores.

### F3 — Pantalla de ciclo (previa al inicio)
- Primera instrucción (lectura): ícono de puerta según `doorState`, listado de alarmas y deshabilitación de botones según `connected`. Los botones son visibles pero sin acción.
- Segunda instrucción (comandos): botón de puerta, "Iniciar ciclo" y avatar, con hilo de trabajo (4.4). Antes de escribirla se confirma si el backend de la PC de desarrollo corre con la tarjeta conectada o simulado (los comandos pueden actuar sobre salidas reales).
- Manejo de rechazo del backend con `toast` y de pérdida de conexión (4.6).
- Salida: reacción correcta a cambios de puerta, alarmas, conexión y habilitación de inicio, probada contra backend real y contra simulación de fallos.

### F4 — Integración con configuración PySide
- Avatar lanza el subproceso PySide y restaura la ventana QML al terminar.
- Sin migración del login: se usa el de PySide (decisión 8). La pantalla de login QML queda sin conectar.
- Salida: ida y vuelta QML → PySide → QML verificada, incluyendo cierre con "Salir".

### F5 — Arranque, ticket y ciclo de vida
- Ticket de arranque desde el nuevo entry point, con un único responsable de impresión entre las dos UI (MIG-06).
- Reemplazo de `wait_for_hardware_connection()` (tkinter) por la pantalla de espera/arranque (V-MIG-05, MIG-07).
- Ciclo de vida sin apagado por UI (MIG-04).
- Salida: arranque en frío completo en PC de desarrollo con ambos monitores.

### F6 — Retirada de tkinter
- Paso 1: reubicar `autoclave/ui/service_ui/` a `autoclave/ui_common/` con `git mv` y actualizar imports (tkinter mientras exista, `ui_pyside`, puente QML, `tests/`, entry points). Sin cambios funcionales; `pytest` antes y después con el mismo resultado (MIG-02).
- Eliminar `autoclave/ui/` (ventanas, `CycleWindow`, `LiveGraph`, `CycleBuffer`, `layout`), entry points antiguos y dependencias no usadas (customtkinter, y matplotlib/Pillow solo si no las usa nada más).
- `requirements.lock.txt` está en UTF-16: decodificar antes de editar.
- Actualizar inventario SOUP (IEC 62304) y ejecutar `pip-audit`.
- Etiquetar (tag) el último commit con tkinter antes de retirar, como punto de retorno.
- Compuerta de liberación a campo: ver MIG-01.

## 6. Pruebas

- Puente: pruebas unitarias con `pytest` y backend simulado (`MagicMock`), en la línea de `tests/test_ui_service_backend_cycle_select.py`. Cubrir: conexión perdida/recuperada, rechazo de comando, cambio de puerta, alarmas.
- QML: verificación visual en la PC de desarrollo antes de cada commit (los commits se hacen tras confirmación visual). Añadir `qmllint` como comprobación estática.
- Ejecución sin pantalla con `QT_QPA_PLATFORM=offscreen` para las pruebas del puente.

## 7. Hallazgos

MIG-01 — CRÍTICO — RECONOCIDO, compuerta vigente — Sin pantalla de ciclo en curso, la UI QML no puede mostrar la fase ni abortar un ciclo iniciado. Hoy `CycleWindow` ofrece abortar con confirmación, fase y confirmación de fin de ciclo. Estado: esta fase corre solo en PC de desarrollo. Condición para cualquier instalación futura en equipo de campo: incluir como mínimo fase, alarmas, abortar con confirmación y confirmación de estados terminales. Registrar el peligro en el archivo de gestión de riesgos (ISO 14971) cuando se acerque una liberación.

MIG-02 — ALTO — APROBADO, F6 paso 1 — `ui_pyside` importa `autoclave.ui.service_ui.backend_client`; por eso `autoclave/ui/` no puede borrarse completo sin reubicar `service_ui`. Destino: `autoclave/ui_common/`. Se pospone para no bloquear el arranque de QML.

MIG-03 — BAJO (antes ALTO) — Con el login de PySide, la sesión (`SessionManager`, en memoria) nace y muere dentro del subproceso PySide. Consecuencias: el operador debe iniciar sesión cada vez que entra a configuración y el avatar QML no puede mostrar usuario. Se reabre como ALTO cuando se migre el login a QML (habrá que definir el traspaso de sesión entre procesos).

MIG-04 — ALTO — PARCIALMENTE RESUELTO — Al desaparecer el apagado por UI se pierden acciones que hoy se ejecutan en `apagar_equipo()` y `on_close`: `reset_outputs()`, detención ordenada del backend (proceso de puerta 1) y `ui_service.stop()`.
  (a) Estado seguro de salidas al perder alimentación: confirmado por Cristian.
  (b) Que `last_shutdown` y `clock_guard` no dependan de un apagado ordenado: pendiente (F0-A).
  (c) Integridad de SQLite ante corte durante escritura: pendiente (F0-A).
  Futuro, fuera de alcance: protocolo de apagado seguro en el que el equipo ejecuta la secuencia y avisa cuando es seguro apagar.

MIG-05 — MEDIO — `UIServiceBackend.start_cycle()` devuelve solo bool; la UI actual solo registra "Backend rechazó el inicio". Sin motivo, el operador no sabe por qué no inicia. Propuesta: devolver `(ok, motivo)` como ya hace `select_cycle`.

MIG-06 — MEDIO — `_print_startup_ticket` se ejecuta en cada proceso de UI. Con dos UI existe riesgo de ticket duplicado. Definir un único responsable.

MIG-07 — MEDIO — `wait_for_hardware_connection()` usa tkinter en `autoclave/main.py`; el asistente de instalación (`launch_installation_wizard`) debe verificarse. Ambos caen bajo la retirada de tkinter.

MIG-08 — BAJO — `es.json` conserva claves obsoletas (`grafica`, `tiempo_transcurrido`, `pausar`, `continuar`, `cancelar`) tras las decisiones del mockup-01. Limpiar en F3.

MIG-09 — MEDIO — Si una UI arranca o se reinicia con la máquina en estado distinto de reposo (ciclo, falla, emergencia), espera → ciclo (previa al inicio) induciría a error. Además, el reset de falla (`/fault/reset`, hoy `_do_reset_falla`) no está en ninguna de las pantallas. Definir el comportamiento para estos estados en F2/F3.

MIG-10 — BAJO (fuera de alcance, se registra) — `login.py` verifica contraseñas con `hashlib.sha256` directo, sin sal ni función de derivación de clave (KDF). Se reutiliza tal cual en esta fase. Evaluar antes de migrar el login a QML y antes de habilitar funciones de red (ver H-03).

## 8. Fuera de alcance de esta fase

- Pantalla de ciclo en curso y estados terminales (se definirán al agregarlas; ver MIG-01).
- Migración de las vistas PySide de configuración y del login a QML.
- Gráfica de ciclo (`LiveGraph`/`CycleBuffer`), eliminada por decisión del mockup-01.
- Apagado de equipo por UI (eliminado) y protocolo de apagado seguro (futuro).
- Cambios en el backend.
- Ejecución en equipos de campo.

## 9. Verificaciones y preguntas abiertas

Delegadas a Claude Code (F0-A, solo lectura):
- V-MIG-01 — Inventario de los `.qml` existentes (rutas, componentes raíz, propiedades, assets, datos simulados). Los archivos están en el repo; el conocimiento del chat solo indexa `.py` y `.json`.
- V-MIG-02 — Punto de entrada vigente (`autoclave/main.py` o `autoclave/ui/main.py`) y si el launcher de dos pantallas ya existe en el código.
- V-MIG-06 — Condición exacta de `_upd_listo` que habilita "Iniciar ciclo", y ubicación/firma de `DoorCommandService`.
- V-MIG-12 — Diferencias entre `ui_pyside/services/backend_client.py` y `ui/service_ui/backend_client.py` (solo reportar).
- MIG-04 (b) y (c), MIG-07 — lógica de `last_shutdown`/`clock_guard`/`backend_guard`, modo de journal de SQLite y toolkit del asistente de instalación.

Pendientes de Cristian:
- V-MIG-03 — Confirmar el flujo del avatar: lanza el subproceso PySide, que abre en `home` (login por pie de página o tarjeta). ¿Es aceptable en esta fase que el avatar no muestre usuario?
- V-MIG-04 — ¿La pantalla de ciclo vuelve sola a espera tras un periodo de inactividad? Si sí, tiempo.
- V-MIG-05 — Comportamiento de la pantalla de espera al arrancar sin conexión con la tarjeta (reemplazo de `wait_for_hardware_connection`).
- V-MIG-07 — ¿La pantalla de ciclo previa al inicio muestra nombre del ciclo/programa o selector (`list_user_cycles`, `select_cycle`)? Hoy existe `_cycle_selector_habilitado`.
- V-MIG-09 — Si ambas UI muestran "Iniciar ciclo": comportamiento ante pulsación desde las dos pantallas (el backend debe rechazar la segunda; confirmar).
- V-MIG-10 — Orientación: ¿ambos monitores vertical fijo? Si es así se elimina la lógica de rotación (`is_portrait`, `font_scale`).
- V-MIG-11 — El subproceso PySide abre en pantalla completa: ¿en qué monitor debe abrir según la UI que lo lanza? ¿Qué muestra el otro monitor mientras tanto?

Diferida:
- V-MIG-08 — Modelo de autenticación del login QML (usuarios con contraseña y/o operadores por nombre, según `planeacion_menu_principal.md`): se define cuando se migre el login.

# Informe de contexto: pantalla OPCIONES y flujo posterior al login (capa PySide/QML)

Fecha del análisis: 2026-10-01, entre 21:55 y 22:06 (hora local). Modo solo lectura: el único archivo creado es este informe. No se ejecutó código de la aplicación, no se escribió en la base de datos, en configuración ni en hardware, y no se hizo commit.

Fuente del mockup: el mensaje no traía la imagen. Se usó la del repositorio, `docs/diseno/referencias/pantallas_1080x1920/pantalla_05_opciones_1080x1920.png` [COMMITEADO, commit f28ca36], que corresponde a la pantalla "OPCIONES" descrita. Si el mockup que usted tiene es distinto a ese archivo, las secciones B, C y G deben revisarse contra su versión.

Aviso sobre documentación: usted indicó que no existe especificación. En el repositorio sí hay un documento del diseñador, `docs/diseno/especificacion_ui_autoclave_v1.pdf` [COMMITEADO], además de planes internos en `docs/mis_plans/`. No se usan como fuente de verdad sobre lo implementado; solo se citan donde aclaran la intención (marcados como "PLANEADO EN DOCUMENTO"). Datos relevantes del PDF: la página 21 lista la pantalla "4 · Menú de administrador (Opciones)" como "Diseñada" con la nota "8 secciones; solo General está resuelta. Faltan las otras 7". La página 20 define la barra inferior como "salir, reportes, servicio, inicio". La página 22 ubica "Opciones generales" como subpantalla de "Administrador".

Convención de etiquetas de origen:
- [COMMITEADO]: el contenido citado está en HEAD (f5ece46).
- [MODIFICADO SIN COMMIT]: el contenido citado es un cambio local sobre un archivo versionado.
- [NUEVO SIN TRACKEAR]: el archivo no está en git.
- [COMMITEADO, archivo con cambios locales ajenos]: lo citado está en HEAD, pero el archivo tiene otros cambios sin commit que no afectan lo citado.

---

## 0. Estado del repositorio

### 0.1 Rama, stashes y ramas locales

- `git branch --show-current`: `dev`, 3 commits por delante de `origin/dev`.
- `git stash list`:
  - `stash@{0}: On feat/brecha-presion-y-tolerancia-desconexion: uncommitted work ... before merging PR chain to dev`: base de datos, logs, `.pyc` y `protocolo_fallo.py`. No tiene relación con esta pantalla.
  - `stash@{1}: WIP on dev: 488b1cd ...`: incluye `src/autoclave/config/global_params.json`, `server.py`, perfiles de ciclo y `CLAUDE.md`. Toca el archivo de parámetros globales, pero su contenido no se mezcló con este análisis. Conviene revisar si guarda valores de `global_params.json` que deban conservarse.
  - `stash@{2}: On dev: runtime files before merge to main`: archivos de ejecución y perfiles. No tiene relación con esta pantalla.
- Ramas locales con trabajo relacionado (resumen de una línea, sin mezclar con el estado actual):
  - `worktree-anuncios-voz` (786c735, worktree en `.claude/worktrees/anuncios-voz`): agrega `src/autoclave/config/preferences.py`, un almacén escribible de preferencias en `data/preferences.json` con escritura atómica (tempfile + reemplazo), y la vista PySide `views/audio_config.py` (volumen y activación de audio). Es el único mecanismo de "preferencias de usuario escribibles" que existe en el repositorio, y no está en `dev`.
  - `feature/roles-sensor-temperatura` (87fca2f, worktree en `.worktrees/roles-sensor-temperatura`): cambia la ruta de "Parámetros del ciclo" en `admin_menu.py` a `params_ciclo_menu` y agrega vistas de sensores. Toca el menú de administración PySide.
  - `claude/competent-morse-801d88` (remoto eliminado): modifica `global_params.json`.
  - `fix/orden-descompresion-secado`: no toca la UI de configuración.

### 0.2 `git status` (instantánea final, 22:06:04)

Modificados sin commit:
- `.claude/settings.local.json`
- `src/autoclave/backend/server.py`: el único cambio es la línea `"fase_ui": progreso_ciclo.fase_ui(r["fase"])` en `/cycle/current/graph`. No afecta esta pantalla.
- `src/autoclave/services/domain/logging/db_manager.py`: columnas de auditoría de creación de usuarios y `existe_usuario()` (ver F).
- `src/autoclave/ui_qml/prueba_ciclo_en_curso.py`
- `src/autoclave/ui_qml/qml/Componentes/GraficaCiclo.qml`
- `src/autoclave/ui_qml/qml/Pantallas/PantallaCicloEnCurso.qml`
- `src/autoclave/ui_qml/qml/Tema/Colores.qml`: agrega los colores `menu*` y `bordeDivisor`.
- `tests/test_backend_ciclo_en_curso_endpoints.py`
- `tests/test_pantalla_ciclo_en_curso_qml.py`
- `tests/test_usuarios_db.py`

Sin trackear:
- `.claude/agents/` (safety-reviewer.md, sensor-role-auditor.md, timing-auditor.md)
- `docs/mis_plans/nuevo_usuario.png`, `planeacion_menu_principal_ui_qml.md`, `planeacion_migracion_qml.md`, `planeacion_nuevo_usuario.md`, `planeacion_pantalla_ciclo_en_curso.md`
- `src/autoclave/images/IconoEjecucion.qml`, `flechas.svg`, `nuevo_usuario.png`, `nuevo_usuario_sin_codigo.png`, `pantalla_ciclo_con_grafica_editada.png`
- `src/autoclave/ui_pyside/services/roles.py`, `src/autoclave/ui_pyside/services/validacion_usuario.py`, `src/autoclave/ui_pyside/views/nuevo_usuario/` (`__init__.py`, `puente.py`)
- `src/autoclave/ui_qml/assets/iconos/{color,mono}/ciclos_totales.svg`
- `src/autoclave/ui_qml/bridge/progreso_ciclo.py`, `src/autoclave/ui_qml/domain/ciclo_en_curso.py`, `src/autoclave/ui_qml/prueba_menu_principal.py`
- `src/autoclave/ui_qml/qml/Componentes/BarraInferiorMenu.qml`, `DetalleUltimoCiclo.qml`, `EncabezadoMenu.qml`, `IconoColor.qml`, `TarjetaMenu.qml`, `TarjetaResumen.qml`
- `src/autoclave/ui_qml/qml/Pruebas/GaleriaMenuPrincipal.qml`, `PruebaCicloEnCursoBackend.qml`
- `tests/test_ciclo_en_curso_dominio.py`, `test_menu_principal_componentes_qml.py`, `test_nuevo_usuario_puente.py`, `test_progreso_ciclo_bridge.py`

### 0.3 El árbol de trabajo cambió durante el análisis

Hay otro proceso trabajando en paralelo sobre "Nuevo usuario". La instantánea de git al inicio de la sesión no incluía `db_manager.py` ni `tests/test_usuarios_db.py` como modificados. Durante el análisis aparecieron:
- `db_manager.py` (modificado a las 22:02:08)
- `tests/test_usuarios_db.py` (22:01:54)
- `roles.py` y `validacion_usuario.py` (22:03:46–47)
- `views/nuevo_usuario/puente.py` (22:03:47)
- `tests/test_nuevo_usuario_puente.py`

Lo que este informe dice de esos archivos refleja su contenido hacia las 22:05 y puede no coincidir con su estado final.

---

## A. Flujo posterior al login

### A.1 Hay dos interfaces y dos logins

1. UI QML (`python -m autoclave.ui_qml.app`), la interfaz de operador a pantalla completa, una ventana por puerta [COMMITEADO].
2. UI PySide Widgets (`python -m autoclave.ui_pyside.app`, o `AutoclaveSettings.exe` en el build), que hoy hace de "menú de configuración". La UI QML la lanza como subproceso [COMMITEADO].

El único login que autentica es el de PySide. El login QML es solo visual.

### A.2 Navegación QML (Main.qml)

Mecanismo: un `StackView` (`id: pila`) en `src/autoclave/ui_qml/qml/Main.qml:67-73` [COMMITEADO] con tres componentes: `esperaComp` (Arranque), `cicloComp` (Ciclo) y `loginComp` (Login), en `Main.qml:85-124`.

Secuencia:
1. Arranque (`initialItem: esperaComp`, `Main.qml:70`). Pasa a Ciclo cuando el standby se desactiva (`aplicarStandby()`, `Main.qml:31-41`) o al tocar si no hay standby (`Main.qml:93`).
2. Ciclo (`Pantallas/Ciclo.qml`). Desde aquí:
   - el avatar (`Ciclo.qml:660`, señal `avatarPulsado`) hace `pila.push(loginComp)` (`Main.qml:110`). El avatar se deshabilita sin conexión (`Ciclo.qml:648`). En el código la señal está comentada como "destino indefinido (PC-05)" (`Ciclo.qml:71`).
   - el engranaje (`Ciclo.qml:264`, `ajustesPulsado`) llama a `ventana.ajustes?.abrir()` (`Main.qml:109`), que lanza el subproceso PySide (A.3). El engranaje no se deshabilita sin conexión ni durante un ciclo: no tiene `enabled` condicionado.
   - la casa (`Ciclo.qml:671`, `inicioPulsado`) no está conectada en `Main.qml`; no hace nada.
3. Login QML (`Pantallas/Login.qml`):
   - el botón "INICIAR SESIÓN" tiene un `MouseArea` vacío (`Login.qml:322-323`, `// TODO: conectar con backend cuando se resuelva el canal`). Los comentarios de cabecera lo confirman (`Login.qml:13-15`).
   - la casa de la barra inferior hace `pila.pop()` y vuelve a Ciclo (`Login.qml:349`, `Main.qml:121`).
   - los botones `salir_sesion`, `historial` y `mantenimiento` están declarados con `activo: false` y sin `accion` (`Login.qml:346-348`). `BarraInferior.qml` ignora la propiedad `activo` (`BarraInferior.qml:36-39`, comentario en `:7-8`), así que se ven iguales a la casa pero no responden.

Conclusión: en QML no existe ninguna pantalla posterior al login. La pantalla Opciones QML está NO IMPLEMENTADA, y también la transición login → Opciones.

Pantallas QML que existen pero no están en la navegación de producción (no las referencia `Main.qml`):
- `Pantallas/PantallaCicloEnCurso.qml` [MODIFICADO SIN COMMIT]: solo la cargan `Pruebas/PruebaCicloEnCurso.qml` y `Pruebas/PruebaCicloEnCursoBackend.qml`.
- Los componentes del Menú Principal, todos [NUEVO SIN TRACKEAR] (`EncabezadoMenu.qml`, `TarjetaMenu.qml`, `TarjetaResumen.qml`, `DetalleUltimoCiclo.qml`, `BarraInferiorMenu.qml`, `IconoColor.qml`): solo los usa `Pruebas/GaleriaMenuPrincipal.qml`, cargada por `prueba_menu_principal.py`. No existe `MenuPrincipal.qml`.

### A.3 Navegación PySide (el flujo post-login que sí autentica)

Lanzamiento: `LanzadorAjustes.abrir()` en `src/autoclave/ui_qml/bridge/lanzador_ajustes.py:52-64` [COMMITEADO] ejecuta `[sys.executable, "-m", "autoclave.ui_pyside.app"]` en desarrollo o `AutoclaveSettings.exe` congelado (`:22-27`). Oculta la ventana QML (`:62`), vigila el proceso cada 500 ms (`_vigilar`, `:66-75`) y restaura la ventana QML en pantalla completa cuando el proceso termina. Ignora un segundo toque mientras el proceso está abierto (`:53-54`).

Mecanismo: un `QStackedWidget` en `src/autoclave/ui_pyside/main_window.py:35`, con rutas por nombre en `navigate_to()` (`:178-198`) [COMMITEADO]. Vista inicial: `home` (`:74`).

Secuencia:
1. `HomeView` (`views/home.py`) con tres tarjetas: "Tiempo de Secado" → `secado`, "Impresión General" → `impresion_menu`, "Login" → `login` (`home.py:19-35`). No exige sesión.
2. Pie de página fijo (`main_window.py:142-147`): PEOPLE → `login`, HISTORY → `ciclos`, DEVELOPER_TOOLS deshabilitado con tooltip "Próximamente", HOME → `home`. Disponible en todas las vistas, con o sin sesión.
3. `LoginView._do_login()` (`views/login.py:216-261`). Si el login es válido llama a `SessionManager.login(user)` y navega a `admin_menu` (`:259-261`), sin importar el rol (hallazgo NU-09 de `planeacion_nuevo_usuario.md`).
4. `AdminMenuView` (`views/admin_menu.py`), título "ADMINISTRACIÓN". Es el equivalente funcional más cercano a "Opciones" (detalle en B.2).
5. El botón "✕ Salir" del encabezado (`main_window.py:110-122`) llama a `QApplication.instance().quit()`. Cierra el proceso PySide sin cerrar sesión explícitamente; la sesión se pierde porque vive en memoria. La UI QML reaparece.

### A.4 Gestión de sesión

- Dónde vive: `SessionManager` en `src/autoclave/ui_pyside/services/session_manager.py:8-34` [COMMITEADO], con un atributo de clase `_current_user` en memoria del proceso PySide. Guarda `id`, `nombre`, `usuario` y `rol` (`:12-18`).
- Rol y nivel de acceso: solo existe `rol` (columna `usuarios.rol`). "Nivel de acceso" NO IMPLEMENTADO: no hay columna en BD ni campo en sesión. `planeacion_nuevo_usuario.md` D-01 lo elimina explícitamente [NUEVO SIN TRACKEAR].
- Exposición a QML: NO IMPLEMENTADO en producción. Ningún objeto de sesión se inyecta al motor QML (`ui_qml/app.py:118-126` solo inyecta `puente`, `comandosPuerta`, `comandoCiclo`, `infoEquipo`, `ajustes`, `standby` y `textosJson`). Además, la sesión vive en otro proceso. En curso, sin integrar: `NuevoUsuarioBridge` expone `usuarioActual` y `puedeCrear()` leyendo `SessionManager` (`ui_pyside/views/nuevo_usuario/puente.py:68-84`) [NUEVO SIN TRACKEAR, en escritura].
- Timeout de sesión: NO IMPLEMENTADO. `SessionManager` no tiene temporizador (brecha B-07 de `planeacion_menu_principal.md` [COMMITEADO]).
- Cierre de sesión:
  - `AdminMenuView._do_logout()` (`admin_menu.py:171-174`) llama a `SessionManager.logout()` y navega a `login`.
  - `NuevoUsuarioBridge.salir()` (`puente.py:124-129`) [NUEVO SIN TRACKEAR] hace lo mismo.
  - Cerrar el proceso PySide destruye la sesión.
  - En QML, el botón Salir de `BarraInferiorMenu.qml` está deshabilitado por defecto (`salirHabilitado: false`, `:15-16`, comentario `TODO(MP-03)`) [NUEVO SIN TRACKEAR].
- Defecto real: `AdminMenuView.showEvent()` (`admin_menu.py:147-154`) llama a `SessionManager.is_logged_in()`, que no existe (el método es `is_authenticated`), y luego `SessionManager.current_user["nombre"]`, que indexa un método. La excepción se traga en `except Exception: pass` (`:153-154`). Resultado: la etiqueta siempre dice "Administrador" (`:102`), sea quien sea el usuario.
- "Recordar usuario":
  - QML: PARCIAL, solo visual. `recordarUsuario.marcado` cambia con un toque (`Login.qml:256`, `:283`). No se persiste ni se lee.
  - PySide: IMPLEMENTADO. Lee al construir la vista (`login.py:170-173`) y escribe tras un login válido (`:251-257`) en `QSettings("Especifika", "Autoclave")`, claves `login/remember` (bool) y `login/last_user` (str). Solo recuerda el nombre de usuario, no la contraseña. Ubicación física: el código no la fija. Por el comportamiento estándar de Qt en Windows sería el registro `HKCU\Software\Especifika\Autoclave`; NO DETERMINADO en el equipo.

### A.5 "Tiempo de espera de pantalla" y sesión

El código no tiene ningún parámetro con ese nombre. Lo más cercano es `tiempo_standby`:
- Definición: `src/autoclave/config/global_params.json:15` [COMMITEADO], con `value: 5`, `unit: "min"`, `min: 1`, `max: 60`.
- Efecto: `Standby` (`ui_qml/bridge/standby.py`) [COMMITEADO]. Tras `tiempo_standby` minutos sin actividad en ninguna de las dos pantallas, ambas vuelven a la pantalla de Arranque (`Main.qml:35-37`, `pila.pop(null)`).
- Reglas que aplica:
  - nunca entra en standby en `CICLO`, `FALLA` o `EMERGENCIA` (`standby.py:36`, `:52-53`);
  - un cambio de estado o una alarma nueva cuenta como actividad;
  - mientras el subproceso PySide está abierto se considera actividad (`app.py:106`, `standby.py:135-136`);
  - si el valor es inválido o falta, usa el defecto de 5 min (`standby.py:34`, `:42-46`).
- Efecto sobre la sesión: ninguno. No hace logout ni bloqueo, porque QML no tiene sesión. Mientras PySide está abierto, el standby nunca se activa, así que una sesión PySide abierta no caduca jamás.
- Planeado, sin implementar: cierre de sesión por 5 min de inactividad fuera de los menús de rol (`planeacion_menu_principal.md` §11.1, punto 2). PLANEADO EN DOCUMENTO.

Pregunta abierta: no está determinado si "Tiempo de espera de pantalla" del mockup es `tiempo_standby` u otra cosa (atenuar o apagar la retroiluminación).

### A.6 Barra inferior dentro de Opciones

Opciones QML no existe, así que el comportamiento de su barra inferior está NO IMPLEMENTADO. Componentes disponibles:
- `Componentes/BarraInferior.qml` [COMMITEADO]: genérica. Recibe `[{icono, activo, accion}]` y llama a `accion` si existe (`:36-39`). No distingue activo de inactivo y no tiene separadores.
- `Componentes/BarraInferiorMenu.qml` [NUEVO SIN TRACKEAR]: fija, con solo Salir (izquierda) e Inicio (derecha), dos separadores y celda central vacía. Expone las señales `salirPulsado` e `inicioPulsado`; Salir viene deshabilitado por defecto. No tiene botones de reportes ni de mantenimiento, que el mockup sí muestra.

El equivalente PySide (`main_window.py:142-147`) tiene login, historial ("ciclos"), herramientas (deshabilitado) e inicio. No valida sesión ni estado del equipo.

Los cuatro iconos del mockup (salir, documento con reloj, llave, casa) tienen recurso: `salir_sesion.svg`, `reportes.svg` o `historial.svg`, `mantenimiento.svg` y `casa.svg` en `ui_qml/assets/iconos/`. Cuál de `reportes.svg` e `historial.svg` es el del mockup: NO DETERMINADO (no se comparó gráficamente).

---

## B. Pantalla Opciones: estructura

### B.1 QML

NO IMPLEMENTADO. No existe ningún archivo QML de Opciones, ni modelo de navegación lateral, ni componente de pestaña o sección, ni ComboBox, Slider o desplegable propio. La búsqueda de "opciones", "OPCIONES" y "pantalla_05" en `src/` y `tests/` no devuelve código QML ni Python asociado.

Lo único reutilizable que ya existe:
- Textos en `assets/textos/es.json` [COMMITEADO]: `acciones.guardar = "Guardar cambios"` (`:97`) y `acciones.restablecer = "Restablecer valores"` (`:100`). No existen claves para "OPCIONES", los nombres de las 8 secciones ni las etiquetas "Idioma", "Unidad de medida", "Brillo de pantalla", "Tiempo de espera de pantalla" o "Tema de color".
- Iconos para las secciones: `engranaje`, `reloj`, `reportes`/`historial`, `impresion`, `conectividad`, `usuarios`, `mantenimiento` e `informacion`, más `guardar`, `chevron_izquierda` y `chevron_abajo`, todos en `ui_qml/assets/iconos/{color,mono}/` [COMMITEADO].
- Estilo tipográfico `titulo_pantalla` (36 px, Bold), listado para "LOGIN, OPCIONES, NUEVO USUARIO" en `docs/diseno/estilos_de_texto.csv:5` [COMMITEADO].
- Encabezado con campana y engranaje: inline en `Ciclo.qml` y copiado en `EncabezadoMenu.qml` [NUEVO SIN TRACKEAR]. `BarraSuperior.qml` [COMMITEADO] no tiene campana ni engranaje (`:1-57`).
- `PanelTeclado` (teclados numérico y alfanumérico), útil para editar valores.

### B.2 PySide (equivalente funcional existente)

`AdminMenuView` (`ui_pyside/views/admin_menu.py`) [COMMITEADO] es una lista vertical de cinco botones, no una navegación lateral con panel de detalle:
- `_OPTIONS` (`:14-20`): "Parámetros del ciclo", "Parámetros del equipo", "Entradas / Salidas", "Mantenimiento" y "Opciones avanzadas".
- `_OPTION_ROUTES` (`:22-25`): solo "Parámetros del ciclo" → `params_ciclo` y "Entradas / Salidas" → `io_menu` tienen destino. Las otras tres muestran `InfoBar` "Esta sección estará disponible próximamente." (`:156-169`).
- Botón "←" → `home` (`:95-99`) y botón "Cerrar sesión" (`:108-112`).

### B.3 Estado de cada sección del mockup

1. General: NO IMPLEMENTADO en QML y en PySide. Sus cinco controles se detallan en C. "Parámetros del equipo" de PySide es un stub sin ruta (`admin_menu.py:16`).
2. Fecha y hora: NO IMPLEMENTADO. No hay código que ajuste el reloj del sistema. Lo relacionado:
   - visualización del reloj en `BarraSuperior.qml:13-55` y en `Ciclo.qml`;
   - `installation/clock_guard.py:13-17` [COMMITEADO], que solo verifica que el reloj no sea anterior a la fecha de instalación (`ClockTamperedError`).
3. Documentos: NO IMPLEMENTADO como sección de configuración. No está determinado qué se configuraría ahí. Funciones relacionadas en PySide [COMMITEADO]: `views/ciclos.py` (impresión de ciclos por rango y envío por correo con SMTP configurable vía `QSettings` `email/smtp_server`, `email/smtp_port`, `:99-100`, `:140`, `:208`) y `views/_email_dialog.py`.
4. Impresión: NO IMPLEMENTADO como configuración. Lo que existe en código:
   - `devices/printer/win32_printer.py:6`: `PRINTER_NAME = "Impresora_Termica"`, nombre fijo en código, y perfil "TM-T88III" (`:19`);
   - `global_params.json:12-13`: `intervalo_impresion` (60 s, rango 0–3600) e `intervalo_imprecion_esterilizacion` (30 s, rango 0–3600; la clave tiene el error ortográfico "imprecion");
   - `views/impresion_menu.py:20-23`, con acciones "Imprimir Ciclos" e "Imprimir Alarmas" (no es configuración).
5. Redes: NO IMPLEMENTADO. No hay código de WiFi, IP ni Ethernet. El backend escucha en `0.0.0.0:8000` (`backend/main.py:29-30`) [COMMITEADO]. `planeacion_menu_principal.md` §13 H-03 justifica eliminar Conectividad de V1.0 [COMMITEADO].
6. Usuarios: PARCIAL, en curso y fuera de Opciones.
   - Hay alta de usuario en lógica: `NuevoUsuarioBridge.guardar()` con validación (`puente.py:91-116`, `validacion_usuario.py:34-75`), roles (`roles.py:10-19`) y `DbManager.crear_usuario`/`existe_usuario` [NUEVO SIN TRACKEAR / MODIFICADO SIN COMMIT]. Su pantalla QML no existe todavía en el árbol.
   - Listado, edición, desactivación, borrado y cambio de contraseña: NO IMPLEMENTADO. No hay método en `DbManager` para listar ni actualizar usuarios.
7. Mantenimiento: NO IMPLEMENTADO. Stub "Mantenimiento" en `admin_menu.py:18`, sin ruta. Sin fuente de datos del último o próximo mantenimiento: `InfoEquipo` lo muestra como "No disponible" (`ui_qml/bridge/info_equipo.py:11-12`), y existe la brecha B-03 de `planeacion_menu_principal.md`.
8. Acerca de: NO IMPLEMENTADO como sección de Opciones. Existe un equivalente provisional: `PanelEquipo` (QML), que se abre al tocar el recuadro modelo/serie de `Ciclo.qml` (`:637-643`), alimentado por `InfoEquipo.filas` (`info_equipo.py:61-94`, `:151-153`). Muestra modelo, serie, ID de máquina, clase, puertas, tipo de puerta, puerta de esta pantalla, enfriamiento, fecha de instalación, ciclos realizados, último ciclo, último mantenimiento ("No disponible"), versión de software y versión de tarjeta ("No disponible"). Claves en `es.json:129-146`.

Resumen: de las 8 secciones del mockup no hay ninguna implementada como sección de Opciones. Usuarios y Acerca de tienen piezas aprovechables fuera de esta pantalla.

---

## C. Parámetros, uno por uno

### C.1 General

1. Idioma (desplegable, "Español")
   - Control, valores, defecto, persistencia y aplicación: NO IMPLEMENTADO.
   - Estado real: los textos QML salen de un único archivo, `assets/textos/es.json`, cargado una vez al arrancar (`ui_qml/app.py:42`, `:68-70`, `:125`) e inyectado como la propiedad `textosJson`. Las pantallas lo consultan con `tx(seccion, clave)`. No hay `QTranslator`, `qsTr()` ni otros archivos de idioma.
   - Hay textos fijos en QML que no pasan por `es.json`, por ejemplo `"LOGIN"` (`Login.qml:94`), `"Inicie sesión para continuar"` (`:119`), `"Recordar Usuario"` (`:276`), `"INICIAR SESIÓN"` (`:315`) y `"¿Olvidó su contraseña?"` (`:328`). Los nombres de mes están duplicados como literales en `BarraSuperior.qml:13` además de `es.json:51`. Toda la UI PySide tiene textos fijos.
   - Aplicación en caliente: NO DETERMINADO, no existe mecanismo. Técnicamente `textosJson` es una propiedad del `Window` raíz enlazada por binding, así que reemplazarla podría propagarse sin recargar el motor, pero ningún código lo hace ni está probado.
   - Impresiones y tickets: `ticket_formatter.py` tiene textos propios; no se analizó su internacionalización.

2. Unidad de medida (desplegable, "Métrico")
   - NO IMPLEMENTADO. No existe ninguna función de conversión de unidades en `src/` (búsqueda de "fahrenheit", "psi", "convert_unit": sin resultados en código de aplicación).
   - Unidad base: el control, los perfiles de ciclo y `global_params.json` usan °C, kPa, seg y min (campo `unit` en `global_params.json:2-15`). Las etiquetas QML salen de `es.json:45-49` (`°C`, `min`, `kPa`).
   - Alcance de un cambio futuro (lógica, registros, tickets): NO DETERMINADO, porque no existe la función. Es una decisión suya (ver preguntas).

3. Brillo de pantalla (slider, 70 %)
   - NO IMPLEMENTADO. No hay código de brillo ni de retroiluminación (búsqueda de "brillo", "brightness" y "backlight": solo aparece `MultiEffect.brightness`, que aclara iconos, en `Login.qml:310`, `Ciclo.qml:569` y `PantallaCicloEnCurso.qml:331`).
   - Mecanismo de hardware disponible en el equipo: NO DETERMINADO. Depende del monitor o panel del cliente (DDC/CI, WMI o GPIO); no hay evidencia en el repositorio.

4. Tiempo de espera de pantalla (desplegable, "5 min")
   - Existe como parámetro `tiempo_standby` (`global_params.json:15`): entero, minutos, rango 1–60 declarado en el JSON, defecto 5. El código tiene un defecto propio duplicado, `MINUTOS_DEFECTO = 5` (`standby.py:34`).
   - Control de edición: NO IMPLEMENTADO en QML y en PySide. El mockup usa un desplegable de valores discretos; el JSON declara un rango continuo. Lista de opciones NO DETERMINADA.
   - Persistencia: archivo `src/autoclave/config/global_params.json`, formato `{"value", "type", "unit", "min", "max"}`. No hay ruta de escritura (ver C.3).
   - Lectura y aplicación:
     - el backend lo carga una vez al arrancar (`backend/context.py:32-34`, `ConfigManager.load_config`) y lo sirve en `GET /global_params` (`server.py:187-189`) [COMMITEADO, archivo con cambios locales ajenos];
     - la UI lo refresca cada 5 s (`ui_service_backend.py:20`, `:66-71`) y `Standby.evaluar()` lo lee en cada evaluación (`standby.py:143`);
     - un cambio en disco requiere reiniciar el backend. Un cambio en el backend en memoria, si existiera, llegaría a la UI en 5 s o menos.
   - Validación: solo `minutos_standby()` (`standby.py:42-46`), que rechaza no numéricos, booleanos y valores ≤ 0. No aplica los límites `min`/`max` del JSON.
   - Efecto: ver A.5. No afecta la sesión ni el registro del ciclo.

5. Tema de color (desplegable, "Claro")
   - NO IMPLEMENTADO. La UI fuerza el tema claro: `forzar_tema_claro()` (`ui_qml/app.py:82-87`, `setColorScheme(Qt.ColorScheme.Light)`) y `setTheme(Theme.LIGHT)` en PySide (`ui_pyside/main_window.py:23`).
   - `Tema/Colores.qml` es un singleton con propiedades `readonly` (`:1-54`) [COMMITEADO + MODIFICADO SIN COMMIT]. No hay variante oscura. Además hay colores fijos fuera del singleton, por ejemplo la `paleta` inline de `Ciclo.qml` ("PENDIENTE: promover a Tema/Colores.qml", `:105`), `#E6E6E6` en `Login.qml:105`, y `#F5F5F5`, `#BEBEBE` y `#8F8F8F` en `BarraInferiorMenu.qml`.
   - Aplicación en caliente: NO DETERMINADO. Las propiedades `readonly` del singleton impiden cambiarlas en ejecución, así que el diseño actual no lo admite sin modificar `Colores.qml`.
   - Restricción a considerar: los colores de alarma están reservados por IEC 60601-1-8 (`Colores.qml:29-32`). Un tema oscuro debe conservarlos.

### C.2 Resto de secciones

No tienen parámetros implementados en el sentido del mockup (ver B.3). Parámetros globales que existen en `global_params.json` [COMMITEADO] y que podrían caer en alguna sección, sin UI de edición en ninguna capa:
- `temp_max` (134 °C)
- `presion_admosferica` (75 kPa)
- `rango_presion_atm` (5 kPa)
- `temp_max_apertura` (120 °C)
- `presion_empaque` (300 kPa)
- `vacio_empaque` (30 kPa)
- `timeout_puerta` (60 s, 0–3600)
- `tipo_puerta` (2, 0–10)
- `temp_segura_drenaje` (70 °C)
- `rango_temp_drenaje` (5 °C)
- `intervalo_impresion` (60 s, 0–3600)
- `intervalo_imprecion_esterilizacion` (30 s, 0–3600)
- `tiempo_estable_alarma` (5 s, 0–3600)
- `tiempo_standby` (5 min, 1–60)

Varios afectan la seguridad (C.3 y E.3). La mayoría no declara `min`/`max`.

### C.3 Persistencia de parámetros globales: limitación técnica de fondo

- `ConfigManager` (`core/managers/config_manager.py:6-25`) [COMMITEADO] solo tiene `load_config()` y `get()`. No existe `set` ni `save`. Tampoco hay endpoint de escritura de parámetros globales en `server.py`.
- La ruta se resuelve con `resource_path()` (`utils/resources.py:4-12`):
  - en desarrollo es relativa al directorio de trabajo (`os.path.abspath("src")`);
  - en el build congelado es `sys._MEIPASS`. `AutoclaveBackend.spec:19` y `AutoclaveSettings.spec:10` empaquetan `src/autoclave/config` dentro de un EXE de un solo archivo (`EXE(... a.datas ...)` sin `COLLECT`, `AutoclaveBackend.spec:43-47`). En producción el archivo se extrae a una carpeta temporal en cada arranque: cualquier escritura se perdería y los valores efectivos son los del momento del build.
- Las preferencias de UI escritas hoy van a `QSettings` (login y SMTP). El almacén escribible y atómico `data/preferences.json` existe solo en la rama `worktree-anuncios-voz` (sección 0.1).

---

## D. "Guardar cambios" y "Restablecer valores"

- Guardar cambios: NO IMPLEMENTADO. Solo existe el texto `acciones.guardar` (`es.json:97`) y el icono `guardar.svg`. No hay validación, escritura, atomicidad ni manejo de errores para parámetros de Opciones.
- Restablecer valores: NO IMPLEMENTADO. Solo existe el texto `acciones.restablecer` (`es.json:100`).
  - No hay valores "de fábrica" de parámetros globales: hay un solo `global_params.json`, sin copia de fábrica.
  - Para ciclos sí existe la separación `cycles/factory/*.json` frente a `cycles/user/*.json`, pero `planeacion_menu_principal.md` B-12 y B-13 [COMMITEADO] indican que no hay comparación usuario/fábrica por parámetro.
  - No hay diálogo de confirmación implementado. El PDF de diseño, página 20, define la anatomía del diálogo de confirmación (PLANEADO EN DOCUMENTO).
- Salir con cambios sin guardar: NO IMPLEMENTADO en Opciones. Existe como regla planeada para Nuevo usuario (`planeacion_nuevo_usuario.md` P-06 y líneas 118-119) [NUEVO SIN TRACKEAR].
- Auditoría de cambios de configuración global: NO IMPLEMENTADO. Patrones existentes reutilizables:
  - tabla `cycle_params_audit` (`cycle_id`, `fase`, `param`, `valor_anterior`, `valor_nuevo`, `usuario`, `timestamp`; `services/domain/logging/cycle_params_audit.py:8-19`) [COMMITEADO], que registra los cambios de parámetros de ciclo hechos desde PySide (`params_ciclo.py:345-348` toma el nombre de `SessionManager`);
  - tabla `sensor_calibration_audit` (`sensor_calibration_audit.py:9`) para calibración;
  - auditoría de creación de usuarios: columnas `creado_por`, `creado_en` y `codigo_creacion` (`db_manager.py:104-107`, `:156-164`) [MODIFICADO SIN COMMIT].

---

## E. Permisos, restricciones y limitaciones

### E.1 Roles y verificación

- Roles presentes en código:
  - `operador`, defecto de la columna (`db_manager.py:102`);
  - `admin`, usuario semilla (`db_manager.py:416-431`);
  - `tecnico`, en `_ROLES_PERMITIDOS = ("admin", "tecnico")` de `calibracion_sensor.py:37`;
  - `admin`, `tecnico`, `biomedico` e `ingeniero` como constante única en `ui_pyside/services/roles.py:10-19` [NUEVO SIN TRACKEAR, en escritura]. `operador` no está en esa lista aunque es el defecto de la tabla.
- Verificaciones de rol que existen:
  - calibración de sensores (`calibracion_sensor.py:177-179`), solo en la vista PySide;
  - creación de usuarios (`puente.py:82-84`, `:93-95`) [NUEVO SIN TRACKEAR], en el puente Python.
- Sin verificación de rol:
  - el acceso al menú de administración (`login.py:261`);
  - "Parámetros del ciclo" (`params_ciclo.py`, solo usa la sesión para el nombre de auditoría);
  - "Entradas / Salidas";
  - todas las vistas PySide accesibles desde el pie de página sin sesión (`main_window.py:142-147`): `ciclos`, `home`, `secado`, `impresion_menu`.
- Backend: ningún endpoint verifica identidad ni rol. No hay autenticación HTTP y el backend escucha en `0.0.0.0` (`backend/main.py:29`). Toda restricción actual es de UI (visual o de la vista PySide), no forzada en el backend. Hallazgo H-03 en `planeacion_menu_principal.md` §13 [COMMITEADO].
- Matriz de permisos por sección y parámetro de Opciones: NO IMPLEMENTADA y no definida. `planeacion_menu_principal.md` §11.2 la remite a un "plan aparte". PLANEADO EN DOCUMENTO: admin gestiona usuarios y no accede a Mantenimiento.

### E.2 Bloqueos por estado del equipo

- Opciones: NO IMPLEMENTADO (no existe la pantalla).
- Estado actual del acceso a configuración:
  - el engranaje de `Ciclo.qml` (`:262-265`) no se deshabilita en CICLO, FALLA, EMERGENCIA, con alarma activa, con puerta abierta ni sin conexión;
  - durante un ciclo se puede abrir el subproceso PySide, y `LanzadorAjustes` oculta la ventana QML de ciclo mientras PySide está abierto (`lanzador_ajustes.py:61-62`).
  - Si la UI PySide muestra o no alarmas activas: NO DETERMINADO (no se analizó cada vista).
- El standby no actúa en CICLO, FALLA ni EMERGENCIA (`standby.py:36`). Es la única regla dependiente del estado del equipo en la capa de presentación de sesión y pantalla.
- Edición de parámetros de ciclo durante un ciclo: `PATCH /cycle/parameter` (`server.py:578-602`, función en `:579`) no verifica el estado de la máquina (no se encontró ninguna comprobación de `CICLO` en el cuerpo). No es parte de Opciones, pero es el mismo tipo de riesgo.

### E.3 Parámetros con impacto en seguridad o en el registro del ciclo (IEC 62304 Clase C)

- De los cinco de General:
  - `tiempo_standby` no afecta el control. Afecta la visibilidad: no entra en standby en estados críticos, y un evento de equipo despierta las pantallas.
  - La unidad de medida afectaría la interpretación de valores y registros si llegara a la lógica o a los tickets.
  - Idioma, brillo y tema afectan la legibilidad de alarmas. El tema debe preservar los colores de alarma de IEC 60601-1-8.
- Globales con impacto directo en seguridad, hoy no editables en ninguna capa y sin protección de rol ni auditoría si se agregara edición: `temp_max_apertura` (habilita la apertura de puerta), `presion_admosferica` y `rango_presion_atm` (condición segura de presión), `temp_segura_drenaje` y `rango_temp_drenaje` (alarma bloqueante y gate de inicio), `timeout_puerta`, `tipo_puerta` y `tiempo_estable_alarma`.
- Fecha y hora: los timers de proceso usan `time.monotonic()` (regla de `CLAUDE.md`), así que un ajuste de reloj no altera la duración del ciclo. Sí altera los sellos de tiempo de registros, auditoría y tickets (`datetime.now()`, por ejemplo `db_manager.py:202` en el registro de ciclos). Además, `clock_guard.py` bloquea el arranque si el reloj queda antes de la fecha de instalación.

### E.4 TODO, FIXME, stubs, código comentado y huérfanos relevantes

- `Login.qml:9-15` (PENDIENTE de textos y autenticación), `:248-249` (sin icono de casilla vacía), `:322` (TODO conectar backend).
- `BarraInferiorMenu.qml:15` TODO(MP-03) [NUEVO SIN TRACKEAR].
- `Ciclo.qml:23-24` PENDIENTE PC-04/PC-03; `:71` avatar "destino indefinido (PC-05)"; `:105` colores por promover.
- `admin_menu.py:16`, `:18` y `:19`: stubs "Parámetros del equipo", "Mantenimiento" y "Opciones avanzadas".
- `main_window.py:145`: botón DEVELOPER_TOOLS deshabilitado, "Próximamente".
- `info_equipo.py:11-12`: último mantenimiento y versión de tarjeta sin fuente.
- QML no alcanzables desde `Main.qml` (huérfanos de producción, solo usados por arneses de prueba):
  - `PantallaCicloEnCurso.qml` [MODIFICADO SIN COMMIT]
  - `EncabezadoMenu.qml`, `TarjetaMenu.qml`, `TarjetaResumen.qml`, `DetalleUltimoCiclo.qml`, `BarraInferiorMenu.qml`, `IconoColor.qml` [NUEVO SIN TRACKEAR]
  - `src/autoclave/images/IconoEjecucion.qml` [NUEVO SIN TRACKEAR], solo lo importa `PantallaCicloEnCurso.qml:5`
- Sin código comentado (bloques desactivados) relevante a esta pantalla en `ui_qml/` ni `ui_pyside/`.
- Dependencias pendientes de migración (código de la UI tkinter usado por la capa QML/PySide):
  - `ui_qml/app.py:21-22` importa `BackendClient` y `UIServiceBackend` desde `autoclave/ui/service_ui/`, paquete de la UI tkinter. Esos dos módulos no importan tkinter, pero viven en ese árbol.
  - `ui_pyside/services/backend_client.py` reexporta el mismo `BackendClient` (V-MIG-12 en `planeacion_migracion_qml.md`).
  - `lanzador_ajustes.py` replica la lógica `_settings_command` de `ui/window/main_window.py` (tkinter) para no importarla (`:9-11`).

### E.5 Casos borde sin manejar

- Login PySide sin límite de intentos ni bloqueo; un intento fallido no queda registrado.
- `DbManager()` se instancia en cada intento de login (`login.py:235`), y cada instancia repite el esquema, la migración y la siembra.
- Dos procesos de UI (puerta 1 y puerta 2) pueden abrir cada uno su PySide con sesiones independientes. Es el comportamiento planeado (`planeacion_menu_principal.md` §10).
- Ciclo arrancado desde la otra pantalla con PySide abierto en esta: la ventana QML sigue oculta. El cierre de sesión al iniciar un ciclo (§11.1 punto 3 del plan) NO IMPLEMENTADO.

---

## F. Persistencia y esquema de datos

- Base de datos: SQLite en `<app_root>/data/autoclave.db` (`db_manager.py:26`). `app_root()` es la carpeta del ejecutable congelado o la raíz del repositorio (`utils/paths.py:8-22`).
- Tabla `usuarios` (`db_manager.py:98-108`): `id INTEGER PK AUTOINCREMENT`, `nombre TEXT NOT NULL`, `usuario TEXT UNIQUE NOT NULL`, `hash_pw TEXT NOT NULL`, `rol TEXT DEFAULT 'operador'`, `activo INTEGER DEFAULT 1` [COMMITEADO], más `creado_por`, `creado_en` y `codigo_creacion` (todas `TEXT DEFAULT ''`) [MODIFICADO SIN COMMIT].
  - `UNIQUE` de SQLite distingue mayúsculas. `existe_usuario()` compara con `casefold()` en Python (`:399-406`) [MODIFICADO SIN COMMIT].
  - `get_usuario_by_username()` (`:408-414`) busca con coincidencia exacta y `activo=1`.
- Tablas de sesión: no existen; la sesión es solo memoria del proceso. Tabla de configuración: no existe; los parámetros globales están en JSON (C.3). Preferencias de UI: `QSettings("Especifika", "Autoclave")` (login y correo).
- Contraseñas: SHA-256 hexadecimal de UTF-8, sin sal, sin iteraciones ni pepper.
  - Funciones duplicadas: `hash_password()` en `session_manager.py:4-5` y `_hash_pw()` en `login.py:19-20`.
  - Verificación por comparación de cadenas `!=` (`login.py:238`), sin comparación en tiempo constante.
  - Usuario semilla `admin` con contraseña `admin1234` si la tabla está vacía (`db_manager.py:416-431`). No se fuerza el cambio en el primer acceso.
  - Es el hallazgo UI-08 (severidad alta) de `planeacion_menu_principal.md` §13 [COMMITEADO].
- Migraciones y versionado: no hay versión de esquema ni tabla de migraciones. `_migrate()` (`db_manager.py:146-164`) ejecuta `ALTER TABLE ... ADD COLUMN` dentro de `try/except sqlite3.OperationalError` en cada arranque, solo de forma aditiva. `global_params.json` no tiene campo de versión.

---

## G. Brecha mockup vs código

### G.1 En el mockup y no en el código

- La pantalla OPCIONES completa en QML: título con chevron atrás, navegación lateral de 8 secciones con resaltado de la seleccionada, panel de detalle "GENERAL".
- Los controles de General:
  - desplegables de Idioma, Unidad de medida, Tiempo de espera y Tema;
  - slider de brillo con porcentaje;
  - el separador horizontal entre brillo y tiempo de espera.
- Los botones "Restablecer valores" y "Guardar cambios" con icono de disquete, más su lógica.
- Las funciones de idioma, unidades, brillo y tema.
- Las secciones Fecha y hora, Documentos, Impresión, Redes, Usuarios, Mantenimiento y Acerca de (como secciones).
- Encabezado con campana (insignia "2") y engranaje en esta pantalla. Existe en `Ciclo.qml` y `EncabezadoMenu.qml`, no en `BarraSuperior.qml`.
- Barra inferior de 4 acciones (salir, reportes/documentos, mantenimiento, inicio) con comportamiento. Hoy solo hay variantes inertes o de 2 acciones.
- Login QML funcional que lleve a esta pantalla.
- Desplegable o selector táctil genérico, y slider con el estilo del diseño: no existen componentes.

### G.2 En el código y no en el mockup

- Menú PySide "ADMINISTRACIÓN" con "Parámetros del ciclo", "Parámetros del equipo", "Entradas / Salidas", "Mantenimiento" y "Opciones avanzadas" (`admin_menu.py:14-20`). Parámetros de ciclo, E/S (entradas digitales, temperaturas, presiones, salidas digitales) y calibración de sensores no aparecen entre las 8 secciones del mockup. El PDF, página 22, los ubica como hermanos de "Opciones generales" bajo "Administrador".
- Botón "Cerrar sesión" en la cabecera del menú PySide y botón "✕ Salir" que cierra el proceso.
- Configuración de correo SMTP (`ciclos.py`, `_email_dialog.py`).
- Parámetros globales de seguridad y proceso (C.2) que no tienen sección asignada en el mockup.
- Rama no integrada: configuración de audio (volumen y activación), sin sección en el mockup.

### G.3 Inconsistencias de nombres, etiquetas y flujo

- "Tiempo de espera de pantalla" (mockup) frente a `tiempo_standby` (código). Además, el mockup ofrece una lista y el JSON declara un rango continuo de 1 a 60.
- "Opciones" (mockup y PDF), "Menú de administrador" (PDF pág. 21), "Administrador / Opciones generales" (PDF pág. 22), "ADMINISTRACIÓN" (`admin_menu.py:122`) y "Menú de rol" (`planeacion_menu_principal.md`): cinco nombres para la misma zona.
- Barra inferior: el PDF, página 20, dice "salir, reportes, servicio, inicio"; el mockup muestra un icono de llave (¿servicio o mantenimiento?); `planeacion_nuevo_usuario.md` D-10 y `BarraInferiorMenu.qml` dejan solo salir e inicio; `Login.qml:345-350` usa `historial` en vez de `reportes`.
- La sección "Usuarios" (mockup) frente al plan de Nuevo Usuario, cuyo punto de entrada es "una nueva opción en el menú de administración PySide, visible solo para rol admin" (`planeacion_nuevo_usuario.md` D-05), no una sección de Opciones.
- Flujo: el mockup implica login → Opciones. El código PySide lleva a "ADMINISTRACIÓN" a cualquier rol, y el plan (`planeacion_menu_principal.md` §11.1) dice "menú del rol del usuario".
- El mockup muestra el engranaje en la cabecera de Opciones; no está definido a dónde lleva estando ya en Opciones.
- La clave `intervalo_imprecion_esterilizacion` tiene un error ortográfico en el código.

---

## Cierre

### (1) Preguntas abiertas

1. ¿Es `pantalla_05_opciones_1080x1920.png` del repositorio el mockup que usted adjuntó, o hay una versión más reciente?
2. ¿Opciones reemplaza al menú PySide "ADMINISTRACIÓN" o convive con él? ¿Dónde quedan Parámetros del ciclo, Entradas/Salidas y Calibración, que no están entre las 8 secciones?
3. ¿El login QML se implementa antes que Opciones? ¿O Opciones se aloja dentro de PySide (`QQuickWidget`, como decidió `planeacion_nuevo_usuario.md` G0) y hereda su `SessionManager`?
4. ¿Qué rol o roles ven Opciones y cada una de sus secciones? ¿La restricción debe forzarse también en el backend?
5. ¿"Tiempo de espera de pantalla" es `tiempo_standby` (volver a Arranque) o una función distinta (atenuar o apagar la pantalla)? ¿Debe cerrar la sesión? ¿Qué valores ofrece la lista?
6. Unidad de medida: ¿solo presentación en pantalla, o también tickets, reportes y entrada de parámetros? ¿Qué sistemas (Métrico/Imperial, °F, psi, bar)? ¿El almacenamiento sigue siempre en °C/kPa?
7. Idioma: ¿qué idiomas? ¿Se traducen también tickets e impresiones? ¿Se acepta recargar la interfaz al cambiarlo?
8. Brillo: ¿qué hardware y monitor tiene el equipo, y por qué interfaz se controla? ¿Hay mínimo de seguridad para que las alarmas sigan visibles?
9. Tema: ¿se requiere tema oscuro en V1.0? ¿Quién entrega su paleta, conservando los colores de alarma?
10. ¿Dónde deben persistir estos ajustes (SQLite, `data/preferences.json` como en la rama de audio, o `global_params.json`)? ¿Son por equipo o por usuario?
11. ¿"Restablecer valores" restaura los valores de fábrica de toda la sección o de toda la pantalla? ¿De dónde salen los de fábrica? ¿Pide confirmación?
12. ¿Los cambios de Opciones deben auditarse (usuario, fecha, valor anterior y nuevo), como `cycle_params_audit`?
13. ¿Qué se configura en "Documentos"? ¿Y en "Impresión" (nombre o modelo de impresora, intervalos, ancho de papel)?
14. "Redes": ¿entra en V1.0 a pesar de H-03 (backend sin autenticación en `0.0.0.0`)?
15. ¿Opciones debe bloquearse o ser de solo lectura durante CICLO, FALLA, EMERGENCIA o con alarma activa? ¿Y el engranaje de la pantalla de ciclo?
16. ¿Qué hacen los cuatro botones de la barra inferior en Opciones, y es la llave "servicio" o "mantenimiento"?
17. ¿"Fecha y hora" debe cambiar el reloj de Windows? ¿Con qué permisos del sistema operativo? ¿Cómo convive con `clock_guard`?
18. ¿El flujo debe advertir cambios sin guardar al cambiar de sección dentro de Opciones, o solo al salir de la pantalla?

### (2) Riesgos detectados, por severidad

Alta:
- El backend no tiene autenticación y escucha en `0.0.0.0:8000` (`backend/main.py:29`). Toda restricción de rol es de UI y se puede evitar.
- Contraseñas en SHA-256 sin sal y usuario semilla `admin`/`admin1234` (`db_manager.py:416-431`, `session_manager.py:4-5`, `login.py:19-20`).
- Cualquier usuario autenticado llega al menú de administración sin verificar su rol (`login.py:261`). Las vistas PySide de pie de página no exigen sesión.
- Los parámetros globales no tienen ruta de escritura ni persistencia válida en producción: un EXE de un solo archivo extrae `global_params.json` a una carpeta temporal (C.3). Cualquier "Guardar cambios" diseñado sobre ese archivo fallaría en silencio.
- El engranaje está disponible durante un ciclo y oculta la ventana QML de ciclo mientras PySide está abierto (`Ciclo.qml:262-265`, `lanzador_ajustes.py:61-62`). NO DETERMINADO si las alarmas siguen visibles en ese lapso.

Media:
- La sesión PySide no caduca y, mientras está abierta, inhibe el standby (`app.py:106`). No se cierra la sesión al iniciar un ciclo.
- `AdminMenuView.showEvent` llama métodos inexistentes y traga la excepción (`admin_menu.py:147-154`): el nombre de usuario mostrado es siempre "Administrador", lo que confunde la atribución.
- No hay auditoría de cambios de configuración global ni de inicios de sesión (IEC 62304 Clase C exige trazabilidad).
- `resource_path()` en desarrollo depende del directorio de trabajo (`utils/resources.py:10`).
- No hay versionado del esquema SQLite (`_migrate` aditivo sin versión).

Baja:
- El rol `operador` (defecto de la tabla) no figura en `roles.py`.
- Login sin límite de intentos y sin registro de fallos.
- Textos fijos fuera de `es.json` impedirán la internacionalización.
- Colores fijos fuera de `Colores.qml` impedirán el tema.
- Archivos de usuarios en escritura concurrente durante este análisis (0.3): la foto de esos archivos puede no ser la final.
- Error ortográfico en la clave `intervalo_imprecion_esterilizacion`.

### (3) Archivos que debe revisar directamente

- `docs/diseno/referencias/pantallas_1080x1920/pantalla_05_opciones_1080x1920.png` y `docs/diseno/especificacion_ui_autoclave_v1.pdf` (págs. 20, 21 y 22)
- `src/autoclave/ui_qml/qml/Main.qml`
- `src/autoclave/ui_qml/qml/Pantallas/Login.qml`
- `src/autoclave/ui_qml/qml/Pantallas/Ciclo.qml` (encabezado, `:234-265`; barra inferior, `:630-680`)
- `src/autoclave/ui_qml/app.py`
- `src/autoclave/ui_qml/bridge/lanzador_ajustes.py`
- `src/autoclave/ui_qml/bridge/standby.py`
- `src/autoclave/ui_qml/assets/textos/es.json`
- `src/autoclave/ui_qml/qml/Tema/Colores.qml`
- `src/autoclave/ui_qml/qml/Componentes/BarraInferior.qml`, `BarraInferiorMenu.qml`, `EncabezadoMenu.qml`, `BarraSuperior.qml`
- `src/autoclave/ui_pyside/main_window.py`
- `src/autoclave/ui_pyside/views/login.py`
- `src/autoclave/ui_pyside/views/admin_menu.py`
- `src/autoclave/ui_pyside/services/session_manager.py`
- `src/autoclave/ui_pyside/services/roles.py`, `validacion_usuario.py` y `views/nuevo_usuario/puente.py` (en escritura)
- `src/autoclave/services/domain/logging/db_manager.py` (`:98-108`, `:146-164`, `:376-431`)
- `src/autoclave/services/domain/logging/cycle_params_audit.py`
- `src/autoclave/config/global_params.json`
- `src/autoclave/core/managers/config_manager.py`
- `src/autoclave/utils/resources.py`
- `AutoclaveBackend.spec` y `AutoclaveSettings.spec`
- `src/autoclave/backend/server.py` (`:179-189`) y `src/autoclave/backend/main.py` (`:27-30`)
- `src/autoclave/ui/service_ui/ui_service_backend.py` (`:159-173`)
- `docs/mis_plans/planeacion_menu_principal.md` (§11, §12, §13), `planeacion_menu_principal_ui_qml.md`, `planeacion_nuevo_usuario.md` y `planeacion_migracion_qml.md`
- Rama `worktree-anuncios-voz`: `src/autoclave/config/preferences.py` y `src/autoclave/ui_pyside/views/audio_config.py`

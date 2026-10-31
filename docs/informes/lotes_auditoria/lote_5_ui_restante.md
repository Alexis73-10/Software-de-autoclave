# Auditoría planes vs. código — LOTE 5 (UI restante)

- **Fecha:** 2026-10-08
- **Norma:** NTC-IEC 62304:2019 (IEC 62304:2006), Clase C — cláusulas 5.2.6, 5.4.4, 8.2.3, 7.4.
- **Base auditada:** rama `audit/62304-snapshot`, commit **8d1884c** (2026-10-07 21:37, = `dev` e7bccf2 + cambios sin commit). Todas las citas `ruta:línea` se refieren a 8d1884c, salvo las marcadas con el nombre de otra rama.
- **Alcance:**
  - `docs/mis_plans/planeacion_nuevo_usuario.md`
  - `docs/mis_plans/planeacion_teclados_qml.md`
  - `docs/mis_plans/planeacion_migracion_qml.md`
  - `docs/mis_plans/planeacion_ui_dual_pantalla.md`
  - `docs/mis_plans/planeacion_reorganizacion_y_andamiaje_ui.md`
  - `docs/mis_plans/planeacion_anuncios_voz.md`
- **Modo:** solo lectura. No se corrige ni se propone; no se decide quién tiene razón.

## Diferencias e7bccf2 → 8d1884c en rutas del lote

```
docs/mis_plans/planeacion_migracion_qml.md         | 198 ++++++
docs/mis_plans/planeacion_nuevo_usuario.md         | 256 ++++++++
src/autoclave/ui_pyside/main_window.py             |  16 +-
src/autoclave/ui_pyside/services/roles.py          |  20 +-
.../ui_pyside/services/session_manager.py          |   2 +
.../ui_pyside/services/validacion_usuario.py       |  62 ++
src/autoclave/ui_pyside/views/admin_menu.py        |  27 +-
.../ui_pyside/views/nuevo_usuario/__init__.py      |   0
.../ui_pyside/views/nuevo_usuario/puente.py        | 160 +++++
.../ui_pyside/views/nuevo_usuario/vista.py         |  69 +++
.../ui_qml/controllers/login_controller.py         |  12 +-
src/autoclave/ui_qml/domain/permisos_opciones.py   |   6 +-
.../ui_qml/qml/Componentes/BarraSuperior.qml       |  64 +-
src/autoclave/ui_qml/qml/NuevoUsuarioHost.qml      |  52 ++
.../ui_qml/qml/Pantallas/NuevoUsuario.qml          | 675 +++++++++++++++++++++
15 files changed, 1599 insertions(+), 20 deletions(-)
```

---

## planeacion_nuevo_usuario (v1.1) (código @ 8d1884c)

**Estado:**
- Fecha: no versionado en `dev`; solo existe en 8d1884c. Modificación del archivo: 2026-10-01 23:06.
- Commits que lo citan: ninguno por nombre.
- Otra rama: no.
- Commits posteriores en el área: 8d1884c (puente, validación, vista, roles y menú PySide: todo sin commit en e7bccf2).
- Partes del plan quedaron reemplazadas por `planeacion_backend_autenticacion.md` (D4, D25-D27).

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×13:**<ul><li>sin "Nivel de acceso" (D-01);</li><li>avatar estático sin "+" (D-02);</li><li>validaciones obligatorias, mínimo 8, confirmación y rol (D-07);</li><li>longitudes nombre 50, usuario 3-30 sin espacios, clave 8-64 (P-04);</li><li>duplicado sin distinguir mayúsculas e incluyendo inactivos, con `IntegrityError` como defensa (P-05, NU-04);</li><li>columnas `creado_por`/`creado_en` (D-08);</li><li>interruptor Activo (D-11);</li><li>opción "Nuevo usuario" en el menú PySide solo para admin (D-05);</li><li>alojamiento `QQuickWidget` en la pila PySide (P-08);</li><li>Salir = logout y login (P-01);</li><li>el puente vuelve a verificar la sesión antes de guardar (NU-05);</li><li>NU-12 sigue vigente (`cerrar()` no vacía el controlador);</li><li>el log no registra la contraseña.</li></ul> | COINCIDE | validacion_usuario.py:12-62; db_manager.py:101-112, 592-599; server.py:312-348; admin_menu.py:20-31, 168-170; main_window.py:55-75, 197; puente.py:92-131, 155-160; PanelTeclado.qml:63-67; NuevoUsuario.qml:7-10 | — | — |
| 1 | D-03: hash SHA-256 de `SessionManager.hash_password` | DIFIERE | El backend guarda PBKDF2 (server.py:339; contrasenas.py:14-28) | plan desactualizado probable (auth D4) | SEGURIDAD |
| 2 | D-04: el puente escribe con `DbManager`; está prohibido un endpoint | DIFIERE | El puente crea por `POST /usuarios` con token (puente.py:1-10, 34-43, 114-122) | plan desactualizado probable (auth D26) | SEGURIDAD |
| 3 | D-12: campo "Código" obligatorio | DIFIERE | Eliminado de la pantalla y de la validación (validacion_usuario.py:7-8; NuevoUsuario.qml:440-441) | plan desactualizado probable | FUNCIONAL |
| 4 | P-03: roles `admin`, `tecnico`, `biomedico`, `ingeniero` | DIFIERE | Sin biomédico (roles.py:10-23) | plan desactualizado probable (D25) | FUNCIONAL |
| 5 | NU-05/§8: solo admin crea usuarios | DIFIERE | El puente y el backend permiten crear también al ingeniero (puente.py:62-64, 92-95; roles.py:28-31). El menú PySide sigue mostrando la opción solo a admin (admin_menu.py:31, 168-170) | indeterminado | SEGURIDAD |
| 6 | NU-01/NU-03: SHA-256 sin sal y semilla `admin1234` | DIFIERE | PBKDF2 y semillas con cambio obligatorio (contrasenas.py; db_manager.py:115-126) | plan desactualizado probable | SEGURIDAD |
| 7 | — | SIN DOCUMENTAR | El flujo de F4 (admin crea un usuario e inicia sesión con él) no puede completarse. El login PySide sigue con SHA-256 (login.py:20, 236), así que nunca valida contra hashes PBKDF2, y no obtiene token. El puente exige token (puente.py:114-117). En QML, la sección "Usuarios" de OPCIONES muestra "Próximamente" (permisos_opciones.py:41; Opciones.qml:191-194) | — | FUNCIONAL |
| 8 | §11: conformidad visual y flujo completo de F4 | NO VERIFICADO | No se ejecutó | — | — |

**Resumen:** 21 afirmaciones: COINCIDE 13 · DIFIERE 6 · SIN DOCUMENTAR 1 · NO VERIFICADO 1.

---

## planeacion_teclados_qml (v2.1) (código @ 8d1884c)

**Estado:**
- Fecha: un solo commit, e195e1f (2026-10-01).
- Commits que lo citan: e195e1f (Pasos 1-3) y a01dfc5 (Paso 4), ambos del 2026-10-01.
- Otra rama: la copia antigua con coma en `.worktrees/roles-sensor-temperatura`, excluida por el propio plan.
- Commits posteriores en el área: 8d1884c (`BarraSuperior.qml`).

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×14:**<ul><li>lógica en `domain/` con pruebas y controladores QObject (§3);</li><li>componentes `Tecla`, `TecladoNumerico`, `TecladoAlfanumerico` y `PanelTeclado`;</li><li>sin Qt Virtual Keyboard;</li><li>`PanelTeclado` en `Main.qml` después del `StackView`, inyectado como `teclado`;</li><li>numérico con punto, signo y sin coma (TEC-D02, D-14);</li><li>presionado visible 90 ms o más (TEC-D04);</li><li>panel de 400 ms con `cubic-bezier(0.2,0,0,1)`, alto máximo 45 %, `alturaOcupada` y `posicion` (TEC-D06);</li><li>Confirmar inválido no entrega (TEC-D08);</li><li>`longitudMaxima` (TEC-D09);</li><li>tecla 96×88, radio 12, separación 14 (TEC-D11);</li><li>borrado total a los 600 ms como función pura con marcas monotónicas (TEC-D12);</li><li>Aa de un solo uso, armada con el campo vacío (TEC-D05, con la precisión de 2026-09-30).</li></ul> | COINCIDE | domain/teclado_numerico.py:17, 28-76; domain/teclado_alfanumerico.py:58-80; domain/borrado_tecla.py:5-39; Tema/Teclado.qml:9-17; PanelTeclado.qml:8, 32, 39, 104, 116-118; Main.qml:132-138 | — | — |
| 1 | TEC-D03: tres capas (letras, 123, @._) | DIFIERE | Dos capas: letras y "?123" con dígitos y símbolos juntos (teclado_alfanumerico.py:8-12, 30-40) | indeterminado (decisión 2026-10-01 anotada en el código, no en el plan) | FUNCIONAL |
| 2 | TEC-D03: 11 símbolos `@ . _ - ( ) ? + * / =` | DIFIERE | 17: se agregan `¿ ¡ ! : " '` (teclado_alfanumerico.py:23-26) | indeterminado | COSMÉTICO |
| 3 | §6 y TEC-D07: "El teclado no modifica ningún valor hasta que Confirmar lo entrega. Cancelar no entrega nada" | DIFIERE | Al abrir otro campo sin Confirmar se entrega lo escrito al campo anterior (`_guardarPendiente`, también un número válido); Cancelar en el alfanumérico entrega `""` al campo (PanelTeclado.qml:48-56, 70-79, 93-99) | indeterminado | SEGURIDAD |
| 4 | — | SIN DOCUMENTAR | Parámetro `siguiente`: Confirmar abre el campo siguiente sin cerrar el panel (PanelTeclado.qml:80-92) | — | FUNCIONAL |
| 5 | §10: casos de verificación en pantalla real (regla física, 90 ms, dedo desnudo) y PROV-03 | NO VERIFICADO | No se ejecutó | — | — |

**Resumen:** 19 afirmaciones: COINCIDE 14 · DIFIERE 3 · SIN DOCUMENTAR 1 · NO VERIFICADO 1.

---

## planeacion_migracion_qml (v0.3) (código @ 8d1884c)

**Estado:**
- Fecha: no versionado en `dev`; solo existe en 8d1884c. Modificación del archivo: 2026-09-29 19:05.
- Commits que lo citan: 2242a63 (2026-09-29).
- Otra rama: no.
- Commits posteriores en el área:
  - 12ad6b5, 6ba2bf0, bdc9bde (2026-10-01, ciclo en curso)
  - 723bfef (2026-10-06)
  - 2d4ffa8 (2026-10-07, login QML)
  - 8d1884c

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×12:**<ul><li>entrada QML con `--door` y `--screen` (§4.1, F1);</li><li>`UiBridge` en `ui_qml/bridge/`;</li><li>`QTimer` de 500 ms que lee el caché de `UIServiceBackend`, sin segundo polling HTTP (§4.3);</li><li>comandos en hilo de trabajo (§4.4);</li><li>`StackView`;</li><li>espera = reloj, el toque lleva a la pantalla principal (F2);</li><li>sin conexión: botones deshabilitados y `sistema.sin_conexion` (§4.6);</li><li>botón de puerta según el estado, con el motivo de rechazo visible;</li><li>Iniciar solo con el equipo listo;</li><li>colores de alarma IEC 60601-1-8;</li><li>MIG-05 vigente: `start_cycle()` devuelve solo bool;</li><li>MIG-09 vigente: no hay reset de falla en las pantallas QML.</li></ul> | COINCIDE | app.py:3-5, 65-66; ui_bridge.py:27, 135, 149; comandos_puerta.py:47-77; comandos_ciclo.py:20-58; Main.qml:39-114; PantallaPreciclo.qml:456-510, 531-533, 614-618 | — | — |
| 1 | §1/§4.1/F4: el avatar lanza el subproceso PySide de configuración | DIFIERE | El avatar abre el login QML u OPCIONES (Main.qml:167, 185). `LanzadorAjustes` se instancia (app.py:121) pero ninguna pantalla lo llama | plan desactualizado probable (2d4ffa8) | FUNCIONAL |
| 2 | Decisión 5 / MIG-01 (CRÍTICO): no existe pantalla de ciclo en curso; sin abortar ni confirmar desde QML | DIFIERE | Existen `PantallaCicloEnCurso` con cancelación y confirmación (LOTE 4) | plan desactualizado probable (12ad6b5, 6ba2bf0) | SEGURIDAD |
| 3 | Decisión 1/F4: la pantalla de login QML no se conecta | DIFIERE | Conectada: Login → OPCIONES (Main.qml:210-245) | plan desactualizado probable (2d4ffa8) | SEGURIDAD |
| 4 | §4.4: `QThreadPool`/`QRunnable` | DIFIERE | `threading.Thread` (comandos_ciclo.py:20-21; comandos_puerta.py) | indeterminado | COSMÉTICO |
| 5 | F5/MIG-06: ticket de arranque desde el nuevo punto de entrada, con un solo responsable | NO IMPLEMENTADO | Ningún archivo de `ui_qml` imprime el ticket; solo lo hace tkinter (main.py:306; ui/window/main_window.py:162-214) | — | FUNCIONAL |
| 6 | F6: reubicar `service_ui` a `ui_common/` y retirar tkinter | NO IMPLEMENTADO | No existe `ui_common`; `src/autoclave/ui/` y tkinter siguen (main.py:28; ui/window/main_window.py:7-8) | — | FUNCIONAL |

**Resumen:** 18 afirmaciones: COINCIDE 12 · DIFIERE 4 · NO IMPLEMENTADO 2.

---

## planeacion_ui_dual_pantalla (v1.0) (código @ 8d1884c)

**Estado:**
- Fecha: primer commit 23d9466 (2026-09-02), último e195e1f (2026-10-01, anotación de la revocación de D-18/D-19). El plan se fecha 2026-08-12 y se declara "no implementar hasta cerrar §14".
- Commits que lo citan: 23d9466.
- Otra rama: no.
- Commits posteriores en el área: 2ae014c (2026-09-24, borró `ui_qml/components` y `ui_qml/design`), 2242a63, f5ece46, 12ad6b5, 2d4ffa8, 8d1884c, entre otros.

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×12:**<ul><li>dos procesos de UI independientes (D-01);</li><li>QML sobre PySide6 sin SOUP nuevo (D-07);</li><li>revocación de D-18/D-19 anotada (§2, §13);</li><li>cerrar la UI no apaga el backend (UI-03, §4.4);</li><li>condición 1 de UI-07: bind `127.0.0.1`;</li><li>temporizadores de fase con monotonic (C-01, V-05);</li><li>estado "ocupado" durante un comando (§6.1-2);</li><li>retroceso 1/2/4/8/15 s en `domain/reconexion.py` (§6.4);</li><li>validación de frontera en `domain/telemetria.py` (§6.1-3);</li><li>controles de la puerta propia (§12.1-3);</li><li>"kPa" (§12.2-9);</li><li>`domain/alarmas.py` (F8).</li></ul> | COINCIDE | app.py:3-10, 65-66; backend/main.py:9; calentamiento.py:226; esterilizacion.py:180; comandos_*.py; ui_qml/domain/reconexion.py, telemetria.py, alarmas.py; PantallaPreciclo.qml:576-606; es.json:123 | — | — |
| 1 | D-11/§8: lienzo lógico 800 × 1280 | DIFIERE | 1200 × 1920 (Tema/Escala.qml:8-9) | plan desactualizado probable | COSMÉTICO |
| 2 | D-12/§6.2: telemetría por WebSocket a 1 Hz | DIFIERE | Polling del caché REST cada 500 ms (ui_bridge.py:135, 149); no existe `/ws/telemetry` | plan desactualizado probable (`planeacion_migracion_qml` §4.3) | FUNCIONAL |
| 3 | D-22/UI-07: función de red diferida a un documento propio | DIFIERE | Envío de correo por SMTP desde Historial y Reportes (acciones_ciclos.py:3-22) | indeterminado | SEGURIDAD |
| 4 | D-23/§9.4: serie persistida como blob comprimido por ciclo | DIFIERE | Una fila por muestra en `lecturas_grafica` (db_manager.py:74-82) | indeterminado | FUNCIONAL |
| 5 | §5.2 M-1: vínculo monitor ↔ puerta por EDID, **nunca por índice** | DIFIERE | `--screen` es un índice de `QGuiApplication.screens()` (app.py:65-66) | indeterminado | SEGURIDAD |
| 6 | §6.2/§10.1: pipeline con PURGA (7 fases) | DIFIERE | 6 fases, sin PURGA (ciclo.py:78-85) | plan desactualizado probable (410109f) | COSMÉTICO |
| 7 | §7.5: tipografía Inter | DIFIERE | Montserrat (assets/fuentes/Montserrat-*.otf) | plan desactualizado probable (`planeacion_reorganizacion` decisiones) | COSMÉTICO |
| 8 | §7.2: `Tokens.qml` generado y prohibido escribir hex en componentes | DIFIERE | No existe `Tokens.qml`; las pantallas declaran hex (PantallaPreciclo.qml:114-135) | plan desactualizado probable (2ae014c) | COSMÉTICO |
| 9 | §9.1: series con temperatura de camisa (obligatoria) y F0 | DIFIERE | Series `temp_camara`, `temp_ref`, `pres_camara` (server.py:681-689) | indeterminado | FUNCIONAL |
| 10 | V-05 (§14): "los temporizadores de fase **y de puerta** usaban `time.time()`… corregido" | DIFIERE | `timeout_puerta` de `advanced_door` sigue con `time.time()` (advanced_door.py:372, 416, 461, 514) | indeterminado | SEGURIDAD |
| 11 | §15 F3/F7/F9: hechos `ContenedorEscalado.qml`, `ui_qml/components/*` y `design/register.py` (Tokens) | DIFIERE | Esos archivos no existen en el snapshot (borrados en 2ae014c); los teclados viven en `qml/Componentes` | plan desactualizado probable (2ae014c) | COSMÉTICO |
| 12 | §6.4: sin conexión los valores se marcan no vigentes **con su antigüedad** | DIFIERE | Se ponen en gris, sin mostrar antigüedad (PantallaPreciclo.qml:17-21, 48) | indeterminado | FUNCIONAL |
| 13 | D-02/§4.2: lanzador `autoclave.launcher` que supervisa backend y UIs | NO IMPLEMENTADO | No existe el módulo | — | SEGURIDAD |
| 14 | D-03/§5.3: `deployment_mode` y `screen_serial` en `installation_profile.json` | NO IMPLEMENTADO | `git grep` sin resultados | — | SEGURIDAD |
| 15 | §5.2 M-3: no arrancar las UI si falta un monitor esperado | NO IMPLEMENTADO | — | — | SEGURIDAD |
| 16 | §5.2 M-4: identidad de puerta permanente en el header, legible a 2 m | NO IMPLEMENTADO | Ningún texto de identidad de puerta en PantallaPreciclo ni PantallaCicloEnCurso | — | SEGURIDAD |
| 17 | §5.2 M-6: confirmación táctil en la puesta en marcha | NO IMPLEMENTADO | — | — | SEGURIDAD |
| 18 | §5.2 M-7: el backend registra en auditoría el `source_door` de todo comando de puerta | NO IMPLEMENTADO | `source_door` se lee y se devuelve sin usarse ni auditarse (server.py:1017-1032, 1037-1052) | — | SEGURIDAD |
| 19 | D-06: estado de la otra puerta visible en modo lectura | NO IMPLEMENTADO | — | — | SEGURIDAD |
| 20 | D-16/§10.2: estado OMITIDA de fase | NO IMPLEMENTADO | Estados `activa`/`completada`/`pendiente` (progreso_ciclo.py:117-124) | — | FUNCIONAL |
| 21 | §10.3: indicador AISLAMIENTO | NO IMPLEMENTADO | `git grep AISLAMIENTO` sin resultados | — | FUNCIONAL |
| 22 | D-20: reinicio automático de UI con registro en auditoría | NO IMPLEMENTADO | — | — | FUNCIONAL |
| 23 | D-21: tema oscuro | NO IMPLEMENTADO | — | — | COSMÉTICO |
| 24 | §9.3: decimación por mínimo y máximo de cubeta | NO IMPLEMENTADO | `git grep decim/cubeta` en ui_qml sin resultados | — | SEGURIDAD |
| 25 | §12.1-5: tarjeta de métrica F0 | NO IMPLEMENTADO | — | — | FUNCIONAL |
| 26 | V-UI-01/02/03 (banco) y D-09 (rotación) | NO VERIFICADO | Requiere hardware | — | — |

**Resumen:** 38 afirmaciones: COINCIDE 12 · DIFIERE 12 · NO IMPLEMENTADO 13 · NO VERIFICADO 1.

---

## planeacion_reorganizacion_y_andamiaje_ui (código @ 8d1884c)

**Estado:**
- Fecha: un solo commit, 2ae014c (2026-09-24).
- Commits que lo citan: f28ca36 y 2ae014c (2026-09-24).
- Otra rama: no.
- Commits posteriores en el área: los de la UI QML del 2026-09-29 en adelante.

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **COINCIDE ×10:**<ul><li>el `.zip` de diseño ya no está en `src/` (§1);</li><li>estructura `ui_qml/assets/{iconos/mono,iconos/color,textos,fuentes,logo}` y `qml/{Tema,Componentes,Pantallas}` (§1.3);</li><li>`es.json` presente (§1.4);</li><li>material de referencia en `docs/diseno/` (PDF, tokens, paleta, CSV, referencias, png_96, LEEME) (§1.5);</li><li>`_archivo/` en `.gitignore` (§1.7);</li><li>`qmldir` de Tema con Escala, Colores y Tipografia (§2.1);</li><li>familia Montserrat;</li><li>`Arranque.qml` y `Login.qml` existen;</li><li>`ui_qml/main.py` existe;</li><li>tokens de alarma IEC en `Colores`.</li></ul> | COINCIDE | `git ls-tree` de las rutas; .gitignore:12; Tema/qmldir:1-4; docs/diseno/* | — | — |
| 1 | §1.6: 49 iconos en `mono` y 49 en `color` | DIFIERE | 50 y 50 | indeterminado (crecimiento posterior) | COSMÉTICO |
| 2 | §2.2: lienzo 1080 × 1920 | DIFIERE | 1200 × 1920 (Escala.qml:8-9); el plan preveía este cambio | plan desactualizado probable | COSMÉTICO |
| 3 | Decisión: navegación provisional con `Loader`, sin cablear `StackView` | DIFIERE | `StackView` (Main.qml:124-130) | plan desactualizado probable | FUNCIONAL |
| 4 | Decisión: logo como texto, sin `Image` | DIFIERE | SVG `logo-especifika-blanco.svg` (PantallaPreciclo.qml:205-212) | plan desactualizado probable | COSMÉTICO |
| 5 | §1.3/Parte 3: `assets/fuentes` y `assets/logo` vacías | DIFIERE | Contienen Montserrat (5 .otf y OFL) y el logo | plan desactualizado probable | COSMÉTICO |
| 6 | §1.6: PDF de 31 páginas; contenido exacto de los archivos de la Parte 2 | NO VERIFICADO | No se abrió el PDF; los archivos de la Parte 2 cambiaron después y no se compararon línea a línea | — | — |

**Resumen:** 16 afirmaciones: COINCIDE 10 · DIFIERE 5 · NO VERIFICADO 1.

---

## planeacion_anuncios_voz (código @ 8d1884c y rama `worktree-anuncios-voz`)

**Estado:**
- Fecha: un solo commit, eb62ca5 (2026-09-02). El plan se declara "pendiente de aprobación" y propone **Clase A** para el subsistema (§9.1).
- Commits que lo citan: ninguno por nombre.
- **Otra rama:** `worktree-anuncios-voz` (786c735, 2026-08-13). Tiene 17 commits `audio` propios (b84c028…786c735) y le faltan 43 commits del snapshot. En el snapshot no hay nada del subsistema (`git grep announcer|/audio|sounddevice` sin resultados).
- Commits posteriores en el área: no aplica en el snapshot.
- **Nota:** en la rama, la bienvenida se pide desde el `main.py` de tkinter (worktree-anuncios-voz:main.py:46-50). La UI vigente es QML y no hace esa llamada.

| # | Afirmación del plan (sección) | Estado | Evidencia código | Origen probable | Impacto |
|---|---|---|---|---|---|
| — | **EN OTRA RAMA ×14 (rama `worktree-anuncios-voz`):**<ul><li>WAV pregenerados (D-01);</li><li>reproduce el backend (D-03);</li><li>`sounddevice` y `soundfile` (D-04, 2c094ce);</li><li>cola de prioridad con `heapq` y `Condition` (D-08, §6.1);</li><li>cooldown de 60 s para P0-P2 y 5 s para P3-P5 (manifiesto: 23×60, 9×5);</li><li>límite de cola 10 (§6.2-4);</li><li>ganancia `(v/100)**2` (§6.3);</li><li>se deshabilita tras 3 fallos (§7.2);</li><li>alerta `AUDIO_NO_DISPONIBLE`;</li><li>`data/preferences.json` con `os.replace` (§7.1);</li><li>endpoints `GET/PATCH /audio/config`, `POST /audio/test`, `POST /audio/ui-ready` (§8.1);</li><li>vista PySide de configuración (§8.2);</li><li>bienvenida después de construir la ventana (D-13, §8.3);</li><li>observador en `ControlLoop` (D-15).</li></ul> | EN OTRA RAMA | worktree-anuncios-voz: assets/audio/es/*.wav; devices/audio/announcer.py:1, 11, 22, 49, 61, 72, 101, 109, 116; assets/audio/manifest.json; config/preferences.py:6, 41; backend/context.py:139; backend/server.py:583-623; ui_pyside/views/audio_config.py:83-118; main.py:46-50; services/domain/audio/announcer_observer.py | — | FUNCIONAL |
| 1 | §4.7: "Total: 33 archivos WAV" | DIFIERE | Las tablas del propio plan suman 32 (5+4+14+4+3+2), y la rama tiene 32 WAV y 32 eventos (90b9285) | plan con error interno probable | COSMÉTICO |
| 2 | §5.1 formato (22.05 kHz, mono, −3 dBFS, ≤4 s) y pruebas T-01 a T-16 | NO VERIFICADO | No se analizaron los WAV ni se ejecutaron las pruebas de la rama | — | — |

**Resumen:** 16 afirmaciones: EN OTRA RAMA 14 · DIFIERE 1 · NO VERIFICADO 1.

---

## 1. Resumen del lote

| Plan | Afirm. | COINCIDE | DIFIERE | NO IMPL. | EN OTRA RAMA | SIN DOC. | NO VERIF. |
|---|---|---|---|---|---|---|---|
| planeacion_nuevo_usuario | 21 | 13 | 6 | 0 | 0 | 1 | 1 |
| planeacion_teclados_qml | 19 | 14 | 3 | 0 | 0 | 1 | 1 |
| planeacion_migracion_qml | 18 | 12 | 4 | 2 | 0 | 0 | 0 |
| planeacion_ui_dual_pantalla | 38 | 12 | 12 | 13 | 0 | 0 | 1 |
| planeacion_reorganizacion_y_andamiaje_ui | 16 | 10 | 5 | 0 | 0 | 0 | 1 |
| planeacion_anuncios_voz | 16 | 0 | 1 | 0 | 14 | 0 | 1 |
| **Total** | **128** | **61** | **31** | **15** | **14** | **2** | **5** |

## 2. Discrepancias con impacto SEGURIDAD, por criticidad aparente

1. **Monitor ↔ puerta (UI-01):** se vincula por índice de pantalla, no por EDID. No hay verificación de monitores al arrancar, ni identidad de puerta visible en pantalla, ni confirmación táctil, ni auditoría del `source_door` (DUAL 5, 14-18). Es la mitigación central del riesgo de comandar la puerta equivocada.
2. **Teclado:** entrega valores sin Confirmar al cambiar de campo, incluido un número válido; Cancelar en el alfanumérico vacía el campo (TEC 3). Contradice la regla "no modifica ningún valor hasta Confirmar".
3. **`timeout_puerta` con `time.time()`:** el plan da V-05 por cerrado "para fase y puerta", pero la puerta sigue con reloj de pared (DUAL 10).
4. **Correo por SMTP:** implementado aunque UI-07/D-22 difería toda función de red (DUAL 3).
5. **Sin lanzador supervisor ni estado de la otra puerta** (DUAL 13, 19).
6. **Creación de usuarios:**
   - el plan dice solo admin; el backend y el puente permiten también al ingeniero, mientras el menú PySide solo se la muestra a admin (NU 5);
   - el camino PySide no funciona: el login sigue con SHA-256 frente a PBKDF2 y no obtiene token (NU 7).
7. **Gráfica sin decimación por mínimo y máximo:** el plan la exige para no ocultar picos de presión (DUAL 24).
8. **Planes desactualizados en puntos de seguridad:** MIG-01 (no hay pantalla en curso) y "login QML sin conectar" ya no describen el código (MIG 2, 3); NU D-03/D-04 (SHA-256, sin endpoint) quedaron reemplazados (NU 1, 2, 6).
9. **Anuncios por voz:**
   - existen solo en una rama atrasada 43 commits;
   - el plan propone Clase A para un subsistema que observa alarmas, decisión que no se puede verificar en el código;
   - la bienvenida depende del `main.py` de tkinter.

## 3. Qué no se pudo verificar y por qué

- **Hardware:** V-UI-01/02/03 (EDID de los paneles Faytech, rendimiento y rotación) necesitan banco.
- **Pantalla real:** no se ejecutaron los casos de los teclados (§10) ni el flujo F4 de Nuevo Usuario.
- **Pruebas no ejecutadas:** no se corrió pytest en el snapshot ni en la rama de voz. No se califica la verificación de cambios (8.2.3).
- **Archivos de audio:** no se analizaron los WAV (formato, normalización, duración).
- **PDF de especificación:** no se abrió (`especificacion_ui_autoclave_v1.pdf`, 31 páginas).
- **Clase A del subsistema de voz:** la justificación (§9.1) es documental, no verificable en el código.

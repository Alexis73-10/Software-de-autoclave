# Tanda 27: inventario de `tools/` y de `ui_pyside` (solo análisis, 5-nov-2026)

No se borró ni editó nada; solo este archivo. Criterios de borrado (todos): a) sin referencia desde puntos de entrada vivos; b) fuera de .spec/Setup/estación; c) nombre no aparece como cadena en código vivo/JSON/YAML; d) ningún proceso vigente la nombra; e) sin prueba con `req(id)` ni cita en trazabilidad/riesgos. Ante la duda, DUDOSO. Búsqueda de nombres con `rg -F` sobre todo el repo (sin `docs/informes/` salvo para fechar el origen).

## Parte 1: `tools/`

### Vigentes (siempre, o con quien las invoca)

| Ruta | Último commit | Quién la invoca | Veredicto |
|---|---|---|---|
| `tools/generador/` | 2026-10-24 | `packaging/GeneradorCodigos.spec`, regla de la tanda | VIGENTE |
| `tools/entrega/` (`compilar_entrega.py`, `info_compilacion.py`) | 2026-10-28 | CLAUDE.md (VER), los 3 `.spec` (`sys.path`), `exe` de entrega | VIGENTE |
| `tools/estacion/` | 2026-10-29 | Setup (`autoclave.iss`, `estacion_setup.ps1`), `exe_unico` (EST-06), CLAUDE.md | VIGENTE |
| `tools/secretos/` | 2026-10-24 | compilación (CMP/LIC-01) | VIGENTE |
| `tools/tandas/` | 2026-10-25 | CLAUDE.md (lanzador de trabajos sin supervisión) | VIGENTE |
| `tools/instalador/` | 2026-10-29 | es el Setup (`autoclave.iss`, `LEEME.md`, `tarea_arranque.ps1`); CLAUDE.md, `Autoclave.spec`, `compilar_entrega.py` | VIGENTE |
| `verificar_entrega_neutra.py` | 2026-10-31 | CLAUDE.md, `Autoclave.spec`, `compilar_entrega.py`, `instalador/LEEME.md`, `test_t9_e9_entrega_neutra`, `test_automatizacion_transporte`, riesgos | VIGENTE |
| `verificar_calibracion_neutra.py` | 2026-10-29 | CLAUDE.md, `Autoclave.spec`, `verificar_entrega_neutra.py`, 4 pruebas (`test_t19_s2`, `test_t19_r2`, `test_t20_s2`, `test_t8_k8`), riesgos | VIGENTE |
| `emparejar_modulo_es.py` | 2026-10-29 | CLAUDE.md (MES-01..03), `backend/context.py`, `installation/profile.py` (mensajes), `test_e6_emparejamiento_modulo_es`, HISTORIAL | VIGENTE |
| `claves_sin_uso_i18n.py` | 2026-10-27 | checklist de cierre de las tandas 17, 19, 20, 23 y 27 (`prompt_claude_code_tanda27.md:59`); escribe `docs/mis_plans/claves_sin_uso_i18n.md`. Sin prueba. OJO: su lista de archivos escaneados nombra `ui_pyside/views/nuevo_usuario/{puente,vista}.py` (líneas 31-32); si se retira o mueve ui_pyside hay que ajustarla (igual que `tests/test_i18n.py:38-39`) | VIGENTE |

### El resto (el objeto de esta tanda)

| Ruta | Último commit | Referencias encontradas | Criterios | Veredicto |
|---|---|---|---|---|
| `ensayo_actualizacion_b_d.py` | 2026-10-27 | solo las otras 3 `ensayo_*` (la importan como `base`) y el informe `tanda10/K10_compilacion_f.md`; la lista de la tanda 27 | sin pruebas, sin `req`, sin .spec/Setup, sin docs de banco ni de entrega | BORRABLE (junto con las otras 3) |
| `ensayo_actualizacion_f_g.py` | 2026-10-23 | importa a `b_d`; nadie la importa | igual | BORRABLE |
| `ensayo_actualizacion_g_h.py` | 2026-10-24 | importa a `b_d`; la importa `ensayo_actualizacion_i.py` | igual | BORRABLE |
| `ensayo_actualizacion_i.py` | 2026-10-24 | importa `b_d` y `g_h`; nadie la importa | igual | BORRABLE |
| `medir_contador_ciclos.py` | 2026-10-20 | solo `docs/informes/tanda4/B9a_llamadas_sincronas_tick.md` (medición puntual TMG-05) y la lista de la tanda 27 | sin pruebas ni `req` | BORRABLE |
| `demos_qml/` (4 `prueba_*.py`) | 2026-10-25 | comentarios de cabecera de `ui_qml/qml/Pruebas/*.qml` (con la ruta vieja `ui_qml/prueba_*.py`, ya obsoleta), comentario en `tests/helpers/textos_caben_qml.py:462`, HISTORIAL (ORG-10). Nadie las importa; ninguna prueba las ejecuta | a, b, c, d cumplidos; pero son el único lanzador de los QML de `Pruebas/` y de `historial_ejemplo.py` (galería de capturas) | DUDOSO (si se borran, borrar también `qml/Pruebas/{Galeria,Prueba}*.qml` que solo ellos abren y `ui_qml/historial_ejemplo.py`; decisión de Cristian) |
| `generar_assets_arranque.py` | 2026-10-12 | `IntroArranque.qml:16` (comentario: de dónde salen `halo_arranque.png`/`voluta_vapor.png`); usa numpy, que no está en `pyproject` | los PNG que genera sí los usa la intro | DUDOSO (regenerador de assets; conservar o documentar en `docs/`) |
| `declarar_entradas_suministro.py` | 2026-10-12 | `tests/test_declarar_entradas_suministro.py`, `tests/test_adenda_herramientas_perfil.py` (A-6), docs de E0/E1/firmware 1.5; escribe su nombre como `herramienta` en el registro del perfil | pruebas sin `req`; procedimiento de campo (declarar el hardware instalado) | DUDOSO |
| `declarar_sondas_temperatura.py` | 2026-10-12 | `tests/test_adenda_herramientas_perfil.py` (A-2), `informe_e0_e1.md` (procedimiento); mismo patrón y misma cadena `herramienta` | igual | DUDOSO |
| `asignar_programas_tuttnauer.py` | 2026-11-02 | `importar_ciclo_tuttnauer.py` (importa `MAPA_PROGRAMAS`), `tests/test_importar_tuttnauer_programas.py`; HISTORIAL (43dbedbd, programa Textiles) | reciente (3 días); herramienta de datos de otro equipo | DUDOSO |
| `importar_ciclo_tuttnauer.py` | 2026-11-02 | `test_importar_tuttnauer_programas.py`; lista de la tanda 27 | igual | DUDOSO |
| `registro_pruebas/` (app web de registro de banco: `app_registro`, `almacen`, `definiciones`, `exportar`, `lanzador_registro`, `respaldo_registro`, `seguridad_registro`, `datos_registro`, `static/`, `.bat`, 3 `.ps1`, `README.md`) | 2026-10-29 | `tests/test_f1_registro_pruebas.py`, `tests/js/cola.test.js` (importa `static/cola.js`); `definiciones.py:15` lee `docs/mis_plans/hoja_pruebas_banco/pruebas.py` (la hoja de banco); HISTORIAL (A1 de la tanda 17 ajustó la prueba al bloque H de la hoja) | acoplada a la hoja de pruebas de banco; sigue en uso por Cristian en el banco | DUDOSO (NO borrar sin decisión) |

Resumen: **borrables con los 4 criterios cumplidos: 5 archivos** (`ensayo_actualizacion_{b_d,f_g,g_h,i}.py`, `medir_contador_ciclos.py`). Ninguno tiene prueba ni `req`, así que **no hay pruebas que solo prueben herramientas borrables**. Pruebas de herramientas DUDOSAS (no borrar con ellas): `test_declarar_entradas_suministro.py`, `test_adenda_herramientas_perfil.py`, `test_importar_tuttnauer_programas.py`, `test_f1_registro_pruebas.py` y `tests/js/cola.test.js`. Ninguna de esas tiene marcador `req(...)`; por el criterio e) la ausencia de `req` no basta mientras haya duda sobre el uso en campo (declarar/Tuttnauer/registro de banco).

## Parte 2: `src/autoclave/ui_pyside` (empaquetado como `AutoclaveSettings.exe`)

### Hallazgo central: hoy nadie puede abrirla desde la UI

- `ui_qml/bridge/lanzador_ajustes.py` (`LanzadorAjustes.abrir()`, `comando_ajustes()`) es el único camino a la app PySide, pero **ningún QML ni Python llama a `ajustes.abrir()`**. `Main.qml` solo declara `property QtObject ajustes` (línea 36); el engrane (`onAjustesPulsado`, Main.qml:425/443) llama a `ventana.abrirConfiguracion()` (Main.qml:114), que apila `Login.qml`, `CambioClave.qml` u `Opciones.qml` (QML). `app.py` solo usa `ajustes.abierto` para el standby (295-296), `ajustes.cerrar()` (321) y lo pasa por contexto (338, 370).
- `docs/riesgos/registro_riesgos.md:306` ya la llama «interfaz antigua, no alcanzable hoy».
- Los únicos accesos reales son manuales: `Autoclave.exe --rol ajustes` (`exe_unico.py:11,113,552-556`) y `python -m autoclave.ui_pyside.app`.
- Tamaño: 4 547 líneas, 25 módulos; último commit 2026-11-04 (solo un cambio de fase 6 de Opciones, ajeno a la pantalla).

### Vistas

`main_window.py:42-75, 193-215` registra 14 vistas (`navigate_to`). Equivalente = evidencia encontrada leyendo el repo; «no verificado» = equivalente probable por nombre/función sin comparar comportamiento.

| Vista (PySide) | Qué hace | Quién la abre | Equivalente QML | Estado |
|---|---|---|---|---|
| `home.py` (75) | «MENÚ PRINCIPAL»: 3 tarjetas (Tiempo de Secado, Impresión General, Login) | `MainWindowFluent` (inicio) | `Pantallas/MenuPrincipal.qml` (tarjetas, historial, reportes, info) | equivalente (no verificado en detalle) |
| `login.py` (266) | usuario/clave con `POST /auth/login`, recuerda usuario (`QSettings`), pasa a `admin_menu` | `home` | `Pantallas/Login.qml` + `controllers/login_controller.py` + `sesion_backend.py` | equivalente |
| `admin_menu.py` (180) | menú tras login: Parámetros del ciclo, Entradas/Salidas, cierre de sesión (Nuevo usuario ya se quitó) | `login` | `Pantallas/Opciones.qml` + `controllers/opciones_controller.py` (abre vía `abrirConfiguracion`, Main.qml:114) | equivalente |
| `params_ciclo/params_ciclo.py` (602) | edita parámetros del programa por pestañas, auditoría `CycleParamsAuditDB`, migración y límites | `admin_menu` | `Pantallas/OpcionesParametrosCiclo.qml` + `controllers/parametros_ciclo_controller.py` (`PATCH /cycle/parameter`, `backend/rutas/parametros_ciclo.py`) | equivalente (no verificado en detalle) |
| `entrdas_salidas/io_menu.py` (112), `io_di.py` (54), `io_temp.py` (83), `io_pres.py` (78), `io_do.py` (352), `_io_base.py` (100) | menú y vistas de entradas digitales, temperaturas, presiones y salidas (importa `EstadoAutoclave` directo; HTTP síncrono en modo prueba) | `admin_menu` → `io_menu` | `Pantallas/OpcionesEntradasSalidas.qml` + `controllers/entradas_salidas_controller.py` (SMP, ESG-02) | equivalente (no verificado en detalle) |
| `entrdas_salidas/calibracion_sensor.py` (313) | calibración de sensor 2 puntos (`hal.measures.calibration_tools`) | `io_temp`/`io_pres` | `Pantallas/OpcionesCalibracionSensor.qml` (+ `OpcionesCalibracionAtm.qml`) | equivalente (no verificado en detalle) |
| `nuevo_usuario/{vista,puente}.py` (68 + 317) | `vista` aloja `NuevoUsuario.qml` en un `QQuickWidget`; `puente.NuevoUsuarioBridge` es el modelo de datos | la propia app PySide **y `ui_qml/app.py:30`** | `Pantallas/NuevoUsuario.qml`, `NuevoUsuarioHost.qml`, `OpcionesUsuarios.qml` + `usuarios_controller.py` | **el puente NO es PySide: es de producción y está mal ubicado** (ver imports) |
| `ciclos.py` (507) | lista de ciclos, impresión térmica (`print_raw`), PDF, correo (diálogo `_EmailDialog`, keyring) | `impresion_menu` | `MenuPrincipal.qml` (ventanaHistorial, `botonImprimirMarcados`), `bridge/acciones_ciclos.py` (`imprimir`, `imprimirResumen`, envío por correo), `ui_qml/exportacion/{correo,config_correo}.py` | equivalente |
| `impresion_menu.py` (178) | «Imprimir Ciclos» (→ `ciclos`) e «Imprimir Alarmas» (ticket térmico de las alarmas activas, `_build_alarms_ticket_lines`) | `home` | Imprimir ciclos: sí (arriba). **Imprimir alarmas activas: sin equivalente** (`rg` de imprimir/ticket de alarmas en `ui_qml` y rutas: nada; solo `ui_pyside/views/impresion_menu.py` y su prueba). Reportes tiene un comentario «las alarmas se agregan después» (MenuPrincipal.qml:228) | **FALTA** |
| `secado.py` (213) | «Tiempo de Secado»: lee `GET /cycle`, ajusta con `PATCH /cycle/parameter` | `home` | La tarjeta «Tiempo adicional de secado» **se retiró del menú QML** (comentario U5, MenuPrincipal.qml:229). Los parámetros de secado del programa se editan en `OpcionesParametrosCiclo.qml`, pero el ajuste puntual del ciclo activo no tiene pantalla propia | **FALTA / decisión de Cristian** |
| `_teclado_pantalla.py` (504) | teclado en pantalla para los widgets PySide (reutiliza `ui_qml.domain.teclado_*`) | todas las vistas PySide | `Componentes/PanelTeclado.qml`, `TecladoAlfanumerico.qml`, `TecladoNumerico.qml` + controladores | equivalente (solo sirve a PySide) |
| `services/auth_backend.py`, `backend_client.py`, `renovacion_sesion.py` | login/logout, cliente HTTP (`cliente.BackendClient` envuelto) y renovación del token | vistas PySide, `conftest.py:77` | `cliente/session_manager.py`, `cliente/backend_client.py`, `ui_qml/sesion_backend.py` | equivalente |
| `main_window.py` (239), `app.py` (20) | ventana Fluent con encabezado, pie, reloj y pila de vistas | `exe_unico --rol ajustes`, `lanzador_ajustes.comando_ajustes()` | `Main.qml` | equivalente |

**Veredicto: NO hay «equivalencia completa».** Faltan: (1) *Imprimir alarmas activas* (ticket térmico de la lista de alarmas); (2) *Tiempo de secado del ciclo activo* (tarjeta retirada en U5, hoy solo vía parámetros del programa). Además, las filas «no verificado en detalle» (parámetros, E/S, calibración) tienen equivalente por nombre y controlador, pero no se comparó función por función; hacerlo antes de borrar.

### Qué importa ui_pyside desde fuera, y a dónde moverlo

`rg 'ui_pyside'` en `src`, `tests`, `tools`, `packaging`, Setup:

| Quién | Qué toma | Destino sugerido |
|---|---|---|
| `ui_qml/app.py:30` | `ui_pyside.views.nuevo_usuario.puente.NuevoUsuarioBridge` (importación real, producción) | mover `puente.py` a `ui_qml/bridge/nuevo_usuario.py` (ya depende de `ui_qml.cambio_optimista`, `operacion_critica`, `sesion_backend`, `auth.*`, `cliente.session_manager`); `vista.py` (aloja QML con `ui_qml.app.QML_DIR/_cargar_fuentes`) se va con ui_pyside |
| `ui_qml/bridge/lanzador_ajustes.py` + `app.py:44,295-296,321,338,370` | `comando_ajustes()` (`-m autoclave.ui_pyside.app`, `AutoclaveSettings.exe`, `--rol ajustes`); `ajustes.abierto` para el standby | retirar `LanzadorAjustes` y la propiedad `ajustes` de `Main.qml`; `Standby(mantener_despierto=...)` pasa a `lambda: False` o se quita el parámetro |
| `exe_unico.py:11,113,552-556` | rol `ajustes` (importa `ui_pyside.app`) | quitar el rol de `choices` y su rama |
| `cliente/session_manager.py:5`, `auth/roles.py:1`, `auth/validacion_usuario.py:1` | solo comentarios de cabecera («antes en ui_pyside/services/…»); sin import | no hay nada que mover; actualizar los comentarios |
| `ui_qml/exportacion/correo.py:5`, `config_correo.py:8,25`, `bridge/acciones_ciclos.py:11` | solo comentarios; `config_correo.SERVICIO_KEYRING = "Especifika-Autoclave-Email"` conserva el nombre de la entrada keyring de `_EmailDialog` (es dato persistido: no cambiar) | actualizar comentarios; mantener la constante |
| `ui_qml/qml/NuevoUsuarioHost.qml:9` | comentario | actualizar |
| `tests/helpers/textos_caben_qml.py:340`, `tests/banco/cap9_capturas_banco.py:105`, y pruebas `test_nuevo_usuario_puente`, `test_f6_nuevo_usuario_async`, `test_f6_sin_enviar_sincrono`, `test_navegacion_sesion_qml`, `test_s9_login_y_causa_qml`, `test_x1_una_instancia_opciones_qml` | `NuevoUsuarioBridge` / `puente.py` | seguir la mudanza del puente a `ui_qml/bridge/` (solo cambia el import; las pruebas siguen vivas) |
| `tests/conftest.py:77` | `renovacion_sesion` (fixture autouse que cancela el diálogo de login) | borrar el fixture con ui_pyside |
| `tests/test_arquitectura_capas.py`, `tests/test_b2_spec_excludes.py:15,26,61,76` | `ui_pyside` como capa prohibida; el test de excludes importa `ui_pyside.main_window/app` | ajustar listas y comando de importación |
| `tests/test_i18n.py:38-39`, `tools/claves_sin_uso_i18n.py:31-32` | rutas de `puente.py`/`vista.py` como archivos con claves i18n | reapuntar al nuevo `ui_qml/bridge/nuevo_usuario.py` |

### Pruebas que dependen de ui_pyside (ninguna verifica un `req` de seguridad del ciclo)

Solo PySide (candidatas a retirar con la app): `test_b1_secado_pyside`, `test_c1_ajustes_pyside_sesion`, `test_c1a_teclado_pyside`, `test_p3_renovacion_pyside`, `test_home_view`, `test_impresion_menu`, `test_ciclos_print`, `test_io_do_camara_header`, `test_io_temp_pres_clickable`, `test_calibracion_sensor_view`, `test_main_window_navigate_payload`, `test_admin_menu_nuevo_usuario`, `test_lanzador_ajustes` (sin `req`), `test_e1_apertura_automatica_sin_actuador` (solo 2 pruebas de `params_ciclo`), `test_q1rev_params_ciclo_fabrica_migrada`, `test_b4_renombre_parametros_equipo` (lee `admin_menu.py`).
Con **`req`, parte PySide**: `test_t16_r_correcciones.py:184` (`test_reimpresion_pyside_lleva_no_conforme`, reimpresión del ticket NO CONFORME) y `test_t23_mes04_codigo_visible_ui.py:67` (`test_ticket_de_alarmas_activas_con_codigo_visible`, MES-04); sus requisitos se cumplen también en QML/ticket_formatter y habría que reasignar la prueba a la ruta equivalente (o retirarla con decisión) en vez de borrarla sin más. `test_nuevo_usuario_qml.py:32` usa `NuevoUsuarioView` (vista PySide).

### Dependencias solo de ui_pyside

- `PySide6-Fluent-Widgets[full]` (pyproject.toml:23; lock `PySide6-Fluent-Widgets==1.11.2`): `qfluentwidgets` solo se importa en `ui_pyside/{main_window,views/home,login,admin_menu,ciclos,secado,_teclado_pantalla,nuevo_usuario/vista}.py` y `tests/test_home_view.py`. Consta además en `docs/riesgos/lista_soup.md:27` (SOUP clase A, «menú de ajustes»).
- Arrastradas por él en el lock, sin otro uso en `src` (a confirmar con `pip show`/`pipdeptree` antes de retirar): `PySideSix-Frameless-Window==0.8.1`, `darkdetect==0.8.0`, `colorthief==0.2.1`, `scipy==1.17.1` (el comentario de `Autoclave.spec:115-118` y `test_b2_spec_excludes.py:50` existen solo para que `scipy` no se excluya por `qfluentwidgets`), y `numpy==2.3.5` (su único uso fuera es `tools/generar_assets_arranque.py`; no está declarado en pyproject).
- **No** son solo de ui_pyside: `keyring` (también `ui_qml/exportacion/config_correo.py`), `requests` (cliente), `pywin32` (impresora, `devices/printer/win32_printer.py`, también la usan las acciones QML), `PySide6`.

### Todas las referencias a ui_pyside / AutoclaveSettings

- `src/autoclave/exe_unico.py`: 11 (comentario), 113 (`choices` de `--rol`), 552-556 (rama `ajustes`, log `ajustes.log`).
- `packaging/Autoclave.spec`: 91 (`hiddenimports` `autoclave.ui_pyside.app`), 4 y 115-118 (comentarios, `scipy` no se excluye); `packaging/AutoclaveSettings.spec` (entero: entrada `ui_pyside/app.py`, nombre `AutoclaveSettings`); `AutoclaveBackend.spec:9` (comentario); `GeneradorCodigos.spec:57` (excludes).
- `tools/instalador/autoclave.iss:1951` (WMI: cierra `AutoclaveSettings.exe` al instalar/desinstalar). No lo copia ni lo crea el Setup (instala el exe único).
- `tools/entrega/compilar_entrega.py:10,47` (`SPECS` incluye `AutoclaveSettings`: compila 3 .spec). `tools/verificar_entrega_neutra.py`: sin referencias.
- Pruebas por nombre de spec/exe: `test_automatizacion_transporte.py:12,112`, `test_t9_e9_entrega_neutra.py:18`, `test_ver_version.py:194` (parametrizan los 3 `.spec`), `test_t11_n11_instalador_limpia_tactiles.py:145` (taskkill), `test_lanzador_ajustes.py:53,102`, `test_b2_spec_excludes.py`, `test_arquitectura_capas.py`.
- CLAUDE.md: no menciona ui_pyside/AutoclaveSettings salvo la regla MES (`ui_pyside` en la lista de textos renombrados, línea 52); `docs/riesgos/registro_riesgos.md:306` y `lista_soup.md:27`.

### Orden de retirada sugerido (si Cristian aprueba)

1. Decidir las 2 faltantes (imprimir alarmas activas; tiempo de secado del ciclo activo).
2. Mover `NuevoUsuarioBridge` a `ui_qml/bridge/` y reapuntar `app.py`, helpers, banco, `test_i18n`, `claves_sin_uso_i18n`.
3. Quitar `LanzadorAjustes`, el rol `ajustes`, `AutoclaveSettings.spec` (y de `SPECS`, de las pruebas parametrizadas y del `taskkill` del Setup, dejando el nombre si hay instalaciones viejas con el exe) y `hiddenimports`.
4. Retirar `ui_pyside/`, las pruebas PySide, dependencias y actualizar SOUP/`test_b2`.
5. Correr la suite completa; cada paso con la suite verde.

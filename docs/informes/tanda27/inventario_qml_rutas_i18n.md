# Inventario de QML, rutas del backend y claves i18n sin uso (tanda 27)

Fecha: 5-nov-2026. Rama `tanda27` (HEAD `af2a3fb0`). **Solo análisis**: no se borró ni editó nada fuera de este archivo y no hay commit.
Los guiones de análisis se corrieron fuera del repositorio (`%USERPROFILE%\an_t27\*.py`); sus comandos se resumen en cada tabla.

Criterios de borrado (deben cumplirse **todos**): a) sin referencia estática desde un punto de entrada vivo; b) no figura en `.spec`/`qmldir`/Setup (`tools/instalador/autoclave.iss`)/`tools/estacion`; c) su nombre no aparece como cadena en código vivo, QML, JSON o YAML; d) ningún proceso vigente lo nombra (CLAUDE.md, `docs/README.md`, hoja de pruebas de banco, entrega); e) si lo prueba una prueba con `req(id)` o lo cita la trazabilidad/riesgos, **no** se borra (DUDOSO).
Criterio general: conservador; ante la duda, DUDOSO (el 1-dic se entrega un equipo funcional).

Nota que afecta a todo: `packaging/Autoclave.spec:73` empaqueta la carpeta `src/autoclave/ui_qml/qml` entera (incluida `Pruebas/`), así que el criterio b) para QML se cumple por archivo (ningún `.spec` nombra un `.qml` concreto). El único `qmldir` es `Tema/qmldir` (7 singletons).

---

## 1. QML sin uso

### 1.1 Archivos

Método: grafo de alcance desde las 4 raíces que carga `ui_qml/app.py` (`Main.qml:352`, `InstalacionVentana.qml:151`, `ReposoInstalacionVentana.qml:211`) y `ui_pyside/views/nuevo_usuario/vista.py` (`NuevoUsuarioHost.qml`), siguiendo instanciaciones `Tipo {`, `Tipo.` (singletons), `"…/Tipo.qml"` (Loader/createComponent) sin comentarios. Guiones `qml_refs.py`, `reach.py`, `inst.py`. De los 113 `.qml` (más `Componentes/grafica_ejes.mjs`, usado), 101 se instancian desde una raíz viva (102 si se cuenta la mención en un comentario de `BarraInferior`).

| Elemento | Evidencia (comando) | a–e | Veredicto |
|---|---|---|---|
| `Componentes/ResumenPeriodo.qml` | `git grep -n ResumenPeriodo -- src tools tests` → solo `tests/test_i18n_linea_base.py:7,115` (copia congelada de su función `tx` en un comentario/cadena de referencia; no carga el archivo); `docs/informes/dashboard_reportes/R_informe.md:63,78` lo declara «sin uso pero conservado» | a✓ b✓ c✓ d✓ (solo informes históricos y `inventario_cadenas_i18n.csv`) e✓ | **BORRABLE** (lo dejó sin uso la tanda 25 al pasar Reportes a pantalla completa; la decisión de conservarlo quedó en el informe R de esa tanda, así que conviene que Cristian lo confirme) |
| `Componentes/BarraInferior.qml` | `inst.py`: ningún `.qml` lo instancia; `git grep -n "BarraInferior\b"` → solo comentario en `TarjetaContenido.qml:9`; `tests/test_barra_inferior_flotante_qml.py:139` afirma `"BarraInferior {" not in texto` (comprueba que **no** se use) | a✓ b✓ c✓ d✓ (`instruccion_claude_code_barra_inferior_flotante.md` dice «si queda sin usos, no lo borres: anótalo») e✓ | **BORRABLE** (la instrucción antigua pedía solo anotarlo; ninguna prueba lo carga) |
| `Pruebas/GaleriaMenuPrincipal.qml` | lo carga `tests/test_menu_principal_componentes_qml.py` y `tools/demos_qml/prueba_menu_principal.py` | a✓ c✗ (arnés) | DUDOSO (arnés de prueba) |
| `Pruebas/PruebaCicloEnCurso.qml` | `tests/test_pantalla_ciclo_en_curso_qml.py`, `tests/banco/llf_capturas_barra_fases.py` (CLAUDE.md lo nombra, §Llenado líquido), `tools/demos_qml/prueba_ciclo_en_curso.py` | d✗ | DUDOSO (arnés vigente) |
| `Pruebas/PruebaCicloEnCursoBackend.qml` | solo `tools/demos_qml/prueba_ciclo_en_curso.py:68` (demo manual con backend); ninguna prueba | a✓ b✓ c✗ (lo nombra una herramienta) d✓ e✓ | DUDOSO (demo manual; borrarlo obliga a tocar `tools/demos_qml/prueba_ciclo_en_curso.py`) |
| `Pruebas/PruebaFinDeCiclo.qml` | `tests/banco/t21_capturas_fin_ciclo.py`, `tests/banco/osc_capturas.py`; CLAUDE.md §Fin de ciclo | d✗ | DUDOSO (arnés vigente) |
| `Pruebas/PruebaInstalacion.qml` | solo `tools/demos_qml/prueba_instalacion.py:42` (demo manual) | a✓ b✓ c✗ d✓ e✓ | DUDOSO (demo manual, misma nota que el de backend) |
| `Pruebas/PruebaMenuPrincipal.qml` | `tests/test_menu_principal_pantalla_qml.py`, `tests/test_u8_correo_rechazo_parcial_qml.py`, `tests/helpers/textos_caben_qml.py`, `tests/banco/osc_capturas.py` | c✗ | DUDOSO (arnés) |
| `Pruebas/PruebaMovimiento.qml` | `tests/test_movimiento_ui_qml.py` | c✗ | DUDOSO (arnés) |
| `Pruebas/PruebaReportes.qml` | `tests/test_rep_pantalla_reportes_qml.py`, `tests/helpers/textos_caben_qml.py`, `tests/banco/rep_capturas_reportes.py` | c✗ | DUDOSO (arnés) |
| `Pruebas/PruebaTecladoAlfanumerico.qml` / `PruebaTecladoNumerico.qml` | `tests/test_teclado_alfanumerico_qml.py`, `tests/test_teclado_numerico_qml.py` | c✗ | DUDOSO (arnés) |

Fuera del QML pero ligado: `ui_qml/bridge/reporte_resumen.py` (`ReporteResumen`) se sigue creando en `app.py:307` y se inyecta como `property QtObject reporte` en `Main.qml:49`, pero **ningún QML lo lee** (`grep -n "reporte\b" qml` → solo la declaración). Lo prueban `tests/test_reporte_resumen_puente.py` y `tests/test_v8a_reportes_fallos_puente.py` (sin `req`). DUDOSO (el informe de la tanda 25 lo deja para «una etapa posterior»; sus rutas `/report/summary` y `/report/failures` siguen en uso por `acciones_ciclos.py` y `reporte_dashboard.py`).

### 1.2 Propiedades y señales sin lector (solo lista)

Método (`props2.py`): cada `property`/`signal` declarada cuyo identificador aparece **una sola vez** en todo el QML sin comentarios (contando `onX`, `onXChanged`, `xChanged`) y ninguna vez en el Python de `ui_qml`. Es conservador: cualquier otro identificador con el mismo nombre la da por usada. Columna «pruebas» = apariciones del nombre en `tests/`.

| Archivo | Tipo | Nombre | Pruebas | Nota |
|---|---|---|---|---|
| `Componentes/ElementoCompartido.qml` | propiedad | `animando` | 0 | |
| `Componentes/IndicadorPuerta.qml` | propiedad | `colorBordeAplicado` | 1 | la lee una prueba (findChild/propiedad) |
| `Componentes/ListaAlarmasPeriodo.qml` | propiedad | `panelAbierto` | 2 | la leen pruebas |
| `Componentes/TextoAjustable.qml` | propiedad | `desborda` | 17 | la usan las pruebas de «textos caben» (D8-5.4): **no tocar** |
| `Componentes/VentanaFlotante.qml` | propiedad | `anchoContenido` | 0 | |
| `Pantallas/Opciones.qml` | propiedad | `profundidadHistorial` | 1 | la lee una prueba |
| `Pantallas/OpcionesParametrosCiclo.qml` | propiedad | `versionAlAbrir` | 0 | |
| `Pantallas/PantallaPreciclo.qml` | propiedad | `iniciarCiclo` (en el objeto de textos, `:152`) | 0 | texto `modulos.iniciar_ciclo` sin lector |
| `Tema/Colores.qml` | propiedad | `fondoCieloClaro`, `iconoBarraInferior`, `fondoPanel`, `fondoElevado`, `estadoEjecucionCirculo`, `fasePendienteIcono` | 0–8 | `tests/test_tema_oscuro.py` exige que los claros sean iguales a `dev` y mapea algunos (p. ej. `iconoBarraMenu → iconoBarraInferior`): DUDOSOS |
| `Main.qml` | propiedad | `reporte` | — | ver §1.1 (`ReporteResumen` inyectado sin lector) |

Total: 14 por el guion + `Main.reporte`. Ninguna se propone para borrar sin revisarla a mano.

### 1.3 Línea base: qué QML cargan los arneses y cómo se invocan

Arneses detectados (`git grep -lE "QQmlApplicationEngine|QQmlEngine|QQuickView|QQmlComponent|setSource|engine.load" -- tests tools` → 91 archivos). Las pruebas QML de pytest lanzan un subproceso con `QT_QPA_PLATFORM=offscreen` (`tests/helpers/textos_caben_qml.py:297,448`, `tests/helpers/opciones_qml_doble.py:132`) y se corren con `pytest tests -n auto`; varias generan un `.qml` temporal (`barra.qml`, `mant.qml`, `accion.qml`…) que instancia la pantalla real.

| QML | Lo cargan (directo o vía `Main`/`Opciones`) |
|---|---|
| `Main.qml` | `test_main_menu_principal_qml`, `test_navegacion_sesion_qml`, `test_navegacion_ciclo_en_curso`, `test_opciones_qml`, `test_u1_seguridad_navegacion_qml`, `test_u2_navegacion_qml`, `test_n8_cerrar_sesion_qml`, `test_reconocer_falla`, `test_s9_login_y_causa_qml`, `test_panel_teclado_login`, `test_t22_teclado_accion_qml`, `test_t26_arq_ui`, `test_t26_ald_detalle_alarmas`, `test_intro_arranque_qml`, `test_x1_una_instancia_opciones_qml`, `test_modo_prueba_sin_cierre_sesion`, `test_ui_qml_app`, `helpers/textos_caben_qml`; banco `cap9_capturas_banco.py` |
| `InstalacionVentana.qml` | `test_t9_instalacion`, `test_t8_e1_asistente_texto_final`, `test_t18_arranque_instalacion`, `test_tema_oscuro`; banco `m1_asistente_banco.py [es\|en]` |
| `ReposoInstalacionVentana.qml` | `test_t18_arranque_instalacion`, `test_w10_pantalla2_instalacion`, `test_tema_oscuro` |
| `NuevoUsuarioHost.qml` | solo `test_tema_oscuro` (lectura estática) |
| `Pantallas/Login`, `CambioClave`, `NuevoUsuario` | `test_login_qml_autenticacion`, `test_l9_login_qml_recordar_olvido`, `test_barra_inferior_flotante_qml`, `test_u2_navegacion_qml`, `test_v8a_barra_inferior_geometria` |
| `Pantallas/MenuPrincipal` | `test_menu_principal_pantalla_qml` (vía `Pruebas/PruebaMenuPrincipal.qml`), `test_t7_avisos_qml`, `test_aj01_apagar_fuera_de_ciclo`, `test_rep13_selector_sin_sesion_qml` |
| `Pantallas/PantallaPreciclo` | `test_b1_barra_preciclo_ciclo_qml`, `test_b6_selector_ciclo_ui`, `test_t17_s4_alarmas_qml`, `test_t21_indicador_puerta_qml`, `test_t27_a3_inicio_oculto_modo_prueba`, `test_t26_ald_detalle_alarmas`; banco `osc_capturas.py`, `cap9`, `o11` |
| `Pantallas/PantallaCicloEnCurso` | `test_pantalla_ciclo_en_curso_qml` (vía `Pruebas/PruebaCicloEnCurso.qml`), `test_cancelacion_ciclo_en_curso_qml`, `test_t21_pantalla_fin_ciclo_qml`, `test_llf_barra_fases_qml`; banco `llf_capturas_barra_fases.py [--demo]`, `t21_capturas_fin_ciclo.py` (vía `PruebaFinDeCiclo.qml`) |
| `Pantallas/Reportes` | `test_rep_pantalla_reportes_qml` (vía `PruebaReportes.qml`), `test_rep_calendario_qml`, `test_rep_componentes_graficos_qml`, `test_dr_h06_correo_manual_punta_a_punta_qml`, `test_u8_correo_rechazo_parcial_qml`; banco `rep_capturas_reportes.py [--solo 1200x1920] [--idiomas es en]` |
| `Pantallas/Opciones` + subpantallas | `helpers/opciones_qml_doble.py` → `test_f3_parametros_ciclo_async`, `test_o1_parametros_ciclo_ui`, `test_o2a_parametros_equipo`, `test_p2_parametros_equipo`, `test_p9_opciones_puertas_nc`, `test_r11_reinicio_ui`, `test_t12_opciones_parametros`, `test_v8a_parametros_ciclo_qml`, `test_o11_entradas_mostradas`, `test_b3_mantenimiento_ui`, `test_m1_mantenimiento_ui`, `test_es_pantallas_qml`, `test_p1_salidas_momentaneas_qml`, `test_r8_reasignacion_ui`, `test_t24_codigos_reasignacion`, `test_t17_s4_opciones_qml`, `test_t22_pantallas_accion_qml`; banco `opciones_qml_banco.py`, `p9_capturas_banco.py` |
| Solo en el banco `i4_truncado_banco.py` (sin prueba automática que las cargue) | `OpcionesCalibracionAtm`, `OpcionesFechaHora`, `OpcionesInfoSistema`, `OpcionesRespaldo`, `OpcionesUsuarios` (y `OpcionesBitacora`, que además tiene `test_t17_s4_opciones_qml`) |
| Componentes con arnés propio | `PanelTeclado`/`TecladoAlfanumerico`/`TecladoNumerico` (`test_teclado_*_qml`, `test_panel_teclado_login`), `SelectorDestino` (`test_c2_selector_correo_manual_qml`, `test_rep13…`), `FilaAlarma`, `ListaAlarmasPeriodo`, `PanelFinCiclo`, `PanelNotificaciones`, `SeccionEstadoSeguro`, `VentanaDetalleAlarma` (`test_t26_ald_detalle_alarmas`, `test_t17_s4_alarmas_qml`), `DeslizadorInicio` (`test_t27_a3…`), `IndicadorPuerta` (`test_t21_indicador_puerta_qml`), `TextoAjustable` (`textos_caben_qml`) |

Banco manual (no pytest; desde la raíz, `PYTHONPATH=src`): `cap9_capturas_banco.py [parte…]`, `llf_capturas_barra_fases.py [--demo]`, `m1_asistente_banco.py [es|en]`, `osc_capturas.py [--temas claro oscuro] [--destino DIR]`, `p9_capturas_banco.py`, `rep_capturas_reportes.py`, `t21_capturas_fin_ciclo.py` (con o sin `QT_QPA_PLATFORM=offscreen`), `u10a_capturas.py <antes|despues>`, `v8b_capturas.py`, `o11_capturas_banco.py`, `i4_truncado_banco.py`, `opciones_qml_banco.py`; no QML: `t26_medicion_arranque.py`, `t26_smp_latencia_salidas.py`. Demos: `tools/demos_qml/prueba_{menu_principal,ciclo_en_curso,instalacion,teclado_numerico}.py`.

---

## 2. Rutas del backend sin cliente

Lista: `docs/informes/tanda15/base/rutas.json` (114 rutas). Comprobado que coincide con la aplicación actual (`from autoclave.backend.server import app` → 114 rutas, sin altas ni bajas). Se excluyen las 4 de FastAPI (`/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc`).
Método (`rutas_ref.py`): la ruta como cadena (parámetros `{x}` como comodín, también f-strings) en archivos versionados fuera de `src/autoclave/backend/`, clasificados en cliente, ui_qml, ui_pyside, simulador, otro código de `src`, tools (incluye `tools/instalador/*.iss`/`.ps1` y `tools/estacion`), tests y docs. Después se revisó a mano cada ruta con 3 o menos apariciones para descartar comentarios y encontrar llamadas armadas (`f"{RUTA}/{accion}"`, `f"/usuarios/{quote(u)}/…"`).

Resultado: 104 de 110 rutas tienen llamador real. Las cuatro de `/maintenance/atm-calibration/{start,cancel,confirm,discard}` no aparecen literales pero las arma `calibracion_atm_controller.py:223` (`f"{RUTA}/{accion}"`, `CLAVE_ORDEN` en `:43`); `/doors/{door}/open|close` las llama `services/domain/puertas/door_command_service.py:25,42` (instanciado en `ui_qml/app.py:288`); `/outputs/reset` la llama `exe_unico.py:156`. Ningún script del Setup ni de `tools/estacion` llama al backend.

`docs/referencia/` no contiene documentación de la API (solo `.xlsx`, `.accdb` y el manual `m31/`), así que ninguna ruta es «API pública documentada». Ninguna de las rutas de abajo figura en `docs/riesgos/matriz_trazabilidad.md` ni en `registro_riesgos.md` (ni por ruta ni por nombre del manejador).

| Ruta | Evidencia (comando) | a–e | Veredicto |
|---|---|---|---|
| `GET /cycle/history/{ciclo_id}/readings` (`get_cycle_readings`) | `rutas_ref.py`: 0 llamadores y 0 pruebas; solo `docs/mis_plans/planeacion_backend_autenticacion.md:90` y `planeacion_sensores_ciclo.md` | a✓ b✓ c✓ d✓ e✓ | **BORRABLE** |
| `GET /cycle/current/readings` (`get_current_cycle_readings`) | Solo `cliente/ui_service_backend.py:267` (`get_current_cycle_readings()`, sin llamadores: `git grep get_current_cycle_readings -- src tools` → solo la definición) y su réplica en `simulador/servidor.py:223`; 0 pruebas. La gráfica en vivo usa `/cycle/current/graph` | a✓ b✓ c✓ (el método del cliente también está muerto) d✓ e✓ | **BORRABLE** (junto con el método del cliente y la ruta del simulador) |
| `GET /cycles` (`list_cycles`) | Solo `cliente/ui_service_backend.py:428` (`list_user_cycles()`, sin llamadores) y `simulador/servidor.py:155`. Pruebas sin `req`: `tests/test_backend_cycle_select_endpoint.py::test_list_cycles_incluye_todos_con_source`, `tests/test_ui_service_backend_cycle_select.py::test_list_user_cycles_*` (2). El selector de la UI usa `/programas/seleccionables` | a✓ b✓ c✓ d✓ e✓ | **BORRABLE** (con el método del cliente, la ruta del simulador y esas 3 pruebas) |
| `GET /alarms/history` (`alarm_history`) | 0 llamadores; prueba sin `req` `tests/test_alarms_endpoints.py:42,52`; diseñada en `docs/superpowers/plans/2026-10-07-sistema-alarmas-parte-a.md` (las partes B/C del sistema de alarmas siguen pendientes) | a✓ b✓ c✓ d≈ e✓ | DUDOSO (está prevista para la pantalla de historial de alarmas de las partes B/C) |
| `GET /db/estado` (`get_db_estado`) | 0 llamadores; pruebas sin `req` `tests/test_endpoint_arranque.py:126-128`, `tests/test_b7_caducidad_tokens.py:155`; diseño en `planeacion_arranque_y_modo_sin_bd.md:133,159` | a✓ b✓ c✓ d≈ e✓ | DUDOSO (diagnóstico del modo sin BD, útil con curl en el banco) |
| `POST /io/test/force-exit` (`io_test_force_exit`) | 0 llamadores en código; **la nombra la hoja de pruebas de banco** (`docs/mis_plans/hoja_pruebas_banco_equipo_pruebas.md:966`, `hoja_pruebas_banco/pruebas.py:287`: «Con el ingeniero, `POST /io/test/force-exit`…»); pruebas sin `req`: `test_b8_salida_forzada_modo_prueba.py`, `test_q1_r1p1_ack_salida_prueba.py`, `test_revision_tanda4.py` | d✗ | DUDOSO (función de seguridad de modo prueba que se usa con curl en el banco) |

Aviso para cualquier borrado de rutas: `tests/test_t15_rutas_equivalentes.py` fija las rutas y el OpenAPI contra `docs/informes/tanda15/base/` (`rutas.json`, `openapi.json`, `roles.json`). Quitar una ruta exige regenerar esa base en el mismo cambio (la prueba no lleva `req`, pero es la red de seguridad de la tanda 15).

---

## 3. Claves i18n sin uso

`python tools/claves_sin_uso_i18n.py` → **392 de 2205** claves sin uso detectado. El alcance del guion es limitado: solo mira el QML, el Python de `ui_qml`, 2 archivos de `ui_pyside/views/nuevo_usuario`, `auth/` y `estacion/configurar_modulo.py`. **No mira** el backend, `core/`, `services/`, `state_machine/` ni el resto de `ui_pyside`, que también arman textos (bitácora, ticket, alarmas, motivos). Por eso se volvió a revisar cada clave contra todo el código vivo (`i18n_check.py`, `fam.py`): literal exacto entre comillas en `src/`, `tools/` o `packaging/` (py, qml, json, yaml, ps1, iss, spec), prefijos dinámicos (constantes que terminan en `.`/`_`, f-strings, `"x." +` en QML) y, para cada familia dinámica, si el sufijo existe como cadena en el código (es decir, si hay quien lo produzca).

### 3.1 Cómo se clasificaron las 392

| Grupo | Claves | Conclusión |
|---|---|---|
| Familias dinámicas con productor en código fuera del alcance del guion | 332 | **No se borran** (ver 3.2) |
| Literales exactos en el backend/núcleo (falso positivo del guion) | 23 | **No se borran**: p. ej. `ciclo.principal_sin_lectura` (`backend/rutas/ciclo.py`), `ciclo.presion_*_sin_lectura` (`core/runtime/presion_sin_lectura.py`), `io.ui.aviso_cierre_cortado_*` (`core/runtime/salidas_prueba_seguridad.py`), `conectividad.asunto_prueba`/`cuerpo_prueba` (`backend/rutas/reportes.py`), `puerta.error_comunicacion` (`door_command_service.py`), `bitacora.ev.param_ciclo_automatico`/`programa_deshabilitado` (`core/runtime/bitacora.py`), `estado_seguro_motivos.*` (5, `core/runtime/alarmas_i18n.py`), `ticket_ciclo.aviso_excursion[_alta]` (`esterilizacion.py`), `ticket_ciclo.observacion_referencia`/`no_conforme_referencia`/`cancelado_por` (`ticket_formatter.py`), `acciones.borrar` (`ui_pyside/views/_teclado_pantalla.py:174`) |
| Nombre corto en `ticket_formatter._t(p, "…")` | 2 | `ticket_ciclo.aviso`, `ticket_ciclo.observacion` (`ticket_formatter.py:153,158`): en uso |
| DUDOSAS | 2 | ver 3.4 |
| **BORRABLES** | 33 | ver 3.3 |

### 3.2 Familias dinámicas comprobadas

| Prefijo | Construcción en el código | Claves del guion | Veredicto |
|---|---|---|---|
| `alarmas.<código>.*` | `core/runtime/alarmas_i18n.py`, `services/domain/reportes/consultas.py` | 145 | En uso. Todos los códigos existen como cadena en el código; los que ya no se emiten (`TARJETA_SIN_ACK`, `TARJETA_ALL_OFF_SIN_CONFIRMAR`, `TARJETA_REINICIO`) se conservan por el historial (CLAUDE.md, MOD-12): DUDOSO, no borrar |
| `bitacora.ev.<evento>` | `core/runtime/bitacora.py` | 58 | En uso; las filas viejas (también las de `EVENTOS_RETIRADOS`) necesitan su texto: no borrar |
| `ticket_ciclo.*` / `ticket_ciclo.fase.*` / `ticket_ciclo.resultado.*` | `ticket_formatter.py:56,134,170` (`_SECCION + clave`) | 40 | En uso (ticket, reimpresión, PDF) |
| `io.di.*`, `io.do.*`, `io.ai…` | `core/runtime/io_names.py`, `backend/server_reasignacion.py` | 37 | En uso (nombres de canales) |
| `puerta.*` | `core/runtime/motivos.py` | 25 | En uso |
| `motivos_fase.*` / `motivos_fase.etapa.*` | `core/runtime/motivos_fase.py`, `cycle_phases/descompresion.py` | 26 | En uso (motivos de fallo guardados) |
| `io.ui.*` | `ui_qml/controllers/entradas_salidas_controller.py:180` (`causa.startswith("io.ui.")`: deja pasar la clave que manda el backend) y `:122,159` (literales) | 6 (+2 literales) | 1 con productor; **5 sin productor** → 3.3 |

Las demás familias que da el guion (p. ej. `reasignacion.motivo_<motivo>`, `reasignacion.funcion_<f>`, `estados.*`, `opciones.secciones.*`, `exportacion.carga_<tipo>`, `selector_ciclo.motivo_*`) el propio guion ya las cuenta enteras como usadas y no aparecen en la lista de 392.

### 3.3 BORRABLES (33)

Evidencia común: `python tools/claves_sin_uso_i18n.py` las lista; `i18n_check.py`: 0 apariciones de la clave completa entre comillas en todo el repo versionado (excepto `es.json`/`en.json` e informes); ningún prefijo dinámico que la cubra (no existe `"modulos." +`, `"opciones." +`, `"sensores_ciclo.estado_"`, `f"reasignacion.{…}"` genérico, etc.); 0 en pruebas, CLAUDE.md, `docs/README.md`, hoja de banco, riesgos y trazabilidad. Cumplen a–e. Hay que borrarlas en `es.json` **y** `en.json` a la vez.

| Clave | Evidencia propia | a–e | Veredicto |
|---|---|---|---|
| `opciones.equipo_motivo_rol` | ni la hoja `equipo_motivo_rol` aparece en el código | ✓✓✓✓✓ | BORRABLE |
| `opciones.equipo_unidades` | el QML usa `opciones.equipo_unidades_confirmar`, no esta | ✓✓✓✓✓ | BORRABLE |
| `opciones.equipo_unidades_ayuda` | — | ✓✓✓✓✓ | BORRABLE |
| `opciones.gestion_titulo` | — | ✓✓✓✓✓ | BORRABLE |
| `opciones.habilitar_programa`, `opciones.deshabilitar_programa`, `opciones.duplicar_programa`, `opciones.borrar_programa`, `opciones.borrar_programa_pregunta`, `opciones.nombre_programa` | Manejo de ciclos usa sus propias claves | ✓✓✓✓✓ | BORRABLE (6) |
| `opciones.nuevo_usuario` | la hoja `nuevo_usuario` aparece en `ui_pyside/main_window.py`, pero como nombre de vista, no como clave | ✓✓✓✓✓ | BORRABLE |
| `modulos.programas`, `modulos.impresion`, `modulos.mantenimiento`, `modulos.conectividad` | Opciones titula con `opciones.secciones.<clave>` (`Opciones.qml:61-62`); no hay `"modulos." +` | ✓✓✓✓✓ | BORRABLE (4) |
| `ciclo.cancelar_pregunta` | de F1 (14-oct); la cancelación usa `ModalConfirmacion` con otras claves | ✓✓✓✓✓ | BORRABLE |
| `acciones.restablecer`, `acciones.reconocer` | de F1; sin `"acciones." +` | ✓✓✓✓✓ | BORRABLE (2) |
| `exportacion.duracion` | ni literal ni nombre corto `"duracion"` en `ui_qml/exportacion/*.py` (el `"duracion"` de `reporte_dashboard.py:343` es el id de una tarjeta y usa `reportes.dash_min`) | ✓✓✓✓✓ | BORRABLE |
| `selector_ciclo.motivo_estado_seguro` | `PantallaPreciclo.qml:103-109` devuelve solo `motivo_ciclo_en_curso`, `_paro`, `_modo_prueba`, `_estado` | ✓✓✓✓✓ | BORRABLE |
| `sensores_ciclo.estado_disponible`, `sensores_ciclo.estado_sin_senal`, `sensores_ciclo.estado_no_instalado` | del 14-oct (T3); hoy solo se usan `sensores_ciclo.rol_*` | ✓✓✓✓✓ | BORRABLE (3) |
| `bitacora.desde_formato` | — | ✓✓✓✓✓ | BORRABLE |
| `reasignacion.puerto_ocupado`, `reasignacion.nombre_escrito`, `reasignacion.escribir_clave`, `reasignacion.clave_escrita` | de R8 (22-oct); `_MENSAJES` de `reasignacion_controller.py` no las usa | ✓✓✓✓✓ | BORRABLE (4) |
| `io.ui.n_canales`, `io.ui.atrapamiento_aviso`, `io.ui.cerrar_sesion_prueba`, `io.ui.cal_aplicada`, `io.ui.atras_cal` | `fam.py`: el sufijo no existe como cadena en ningún código; el backend solo manda `io.ui.aviso_*` (de 20-oct, `a563a066`) | ✓✓✓✓✓ | BORRABLE (5). Ojo con `atrapamiento_aviso`: la tanda 27 (A4) trabaja el seguro de atrapamiento; confirmar que no se piensa volver a usar |

### 3.4 DUDOSAS

| Clave | Evidencia | a–e | Veredicto |
|---|---|---|---|
| `ciclo.rol_sonda_no_activa` | sin uso en el código, pero `tests/test_t16_s4_programas.py:570-573` exige que exista en es/en, con `pytestmark = pytest.mark.req("T16-S4")` (`:28`) | e✗ | DUDOSO (prueba con `req`) |
| `ticket_ciclo.aviso_uniformidad` | ya no se produce (C-13.5; `test_t12_c13_excursion_referencia.py:193` comprueba que no se emite), pero los ciclos guardados antes de la tanda 12 pueden tenerla en sus `avisos` y `aviso_ticket` la traduce al reimprimir (`test_x9_d9_13_4_ticket_motivos_idioma.py:175,200`) | c✗ (dato persistido) | DUDOSO (historial) |

---

## 4. Pruebas que solo prueban lo borrable

| Prueba | Qué prueba | Se va con |
|---|---|---|
| `tests/test_backend_cycle_select_endpoint.py::test_list_cycles_incluye_todos_con_source` | `GET /cycles` | la ruta `/cycles` (las demás pruebas del archivo, de `/cycle/select`, se quedan) |
| `tests/test_ui_service_backend_cycle_select.py::test_list_user_cycles_filtra_solo_source_user` | `UIServiceBackend.list_user_cycles` | `/cycles` + el método del cliente |
| `tests/test_ui_service_backend_cycle_select.py::test_list_user_cycles_retorna_vacio_si_falla_backend` | ídem | ídem |
| `tests/test_t15_rutas_equivalentes.py` (no se borra) | fija las 114 rutas y el OpenAPI | hay que regenerar `docs/informes/tanda15/base/` si se quita alguna ruta |

`/cycle/history/{id}/readings`, `/cycle/current/readings`, `ResumenPeriodo.qml`, `BarraInferior.qml` y las 33 claves BORRABLES no tienen pruebas propias. La copia congelada de la función de `ResumenPeriodo.qml` en `tests/test_i18n_linea_base.py` no depende del archivo.

## 5. Resumen de conteos

- QML: 113 archivos; 101 instanciados desde una raíz viva; 2 BORRABLES (`ResumenPeriodo.qml`, `BarraInferior.qml`); 10 de `Pruebas/` DUDOSOS (arneses y demos); 15 propiedades sin lector (solo lista); `ReporteResumen`/`Main.reporte` DUDOSO.
- Rutas: 110 de la app (sin las 4 de FastAPI); 104 con llamador; 3 BORRABLES (`/cycle/history/{id}/readings`, `/cycle/current/readings`, `/cycles`); 3 DUDOSAS (`/alarms/history`, `/db/estado`, `/io/test/force-exit`).
- i18n: el guion lista 392 de 2205; 357 están en uso fuera de su alcance o por familias dinámicas; 33 BORRABLES; 2 DUDOSAS.
- Pruebas que solo prueban lo borrable: 3 (las de `/cycles`).

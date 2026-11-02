# Informe — Dashboard de Reportes

## Etapa A — Verificación del §3 contra el código (2026-11-02)

Resultado: el §3 es correcto en lo sustancial. Diferencias menores:

1. `ventanaReportes` está en `ui_qml/qml/Pantallas/MenuPrincipal.qml` desde la línea 789 hasta el final del archivo (≈1230), no «779–1000». Contiene `SelectorPeriodo` (919), `ResumenPeriodo` (940), `ListaCiclos` (1049) y `SelectorDestino` (1201). Las líneas 614–767 son del Historial (otro `SelectorPeriodo`, `ListaCiclos`, `SelectorDestino`).
2. El índice por fecha de inicio ya existe con el nombre `idx_ciclos_fecha` (`ON ciclos(fecha_inicio)`, `db_manager.py:69`), no `idx_ciclos_fecha_inicio` (§8). No hace falta migración para él.
3. `ciclos_historial.py` (Historial, `/cycle/list`) tiene su propia tupla `PERIODOS` de tres; `/cycle/list` sigue sin aceptar «anio» (hay prueba que lo exige) y no se tocó.
4. El simulador (`simulador/servidor.py:236,244`) declara su propio `Literal["dia","semana","mes"]` en `/cycle/list` y `/report/summary`; no se tocó (fuera del alcance de esta etapa). El rótulo del periodo en `ui_qml/domain/resumen_sistema.py:199-206` trata todo lo que no sea día/semana como mes: con «anio» daría un rótulo de mes. Ambos son para la etapa E.
5. Confirmados sin diferencia: rutas `/report/summary`, `/report/failures`, `/report/summary/print`; columnas de `ciclos` (incluida `numero_programa`); `alarmas_historial` con `ciclo_id`; niveles INFORMATIVO/AVISO/ALARMA/FALLO_CRITICO; correo enviado desde la UI con auditoría `POST /email/sent` (`acciones_ciclos.py`, `rutas/reportes.py`); `periodos` solo aceptaba dia/semana/mes.

## Etapa B — «anio» en periodos y /report/* (DR-H04)

- `utils/periodos.py`: `rango("anio")` = 1 ene – 1 ene siguiente; `es_actual` y `desplazar` (±N años, tope en `hoy`) lo heredan. Nueva constante `PERIODOS_REPORTES` = PERIODOS + «anio». **DECISIÓN SIN CONFIRMAR:** `PERIODOS` se dejó en tres para no cambiar el comportamiento de `ReporteResumen` (que valida contra ella y cuya prueba exige rechazar «anio») ni del Historial; la etapa E debe pasar a `PERIODOS_REPORTES` en el nuevo controlador.
- `backend/rutas/reportes.py`: los tres `Literal` (`/report/summary`, `/report/failures`, cuerpo de `/report/summary/print`) aceptan «anio». El envío del consolidado lo hace la UI y no valida periodo en el backend.
- Pruebas: `tests/test_periodos_calendario.py` (rango, es_actual, desplazar con cruce de año y bisiesto), `tests/test_backend_cycle_summary.py` (rango del periodo, resumen, fallos e impresión de un año; 422 para valores inválidos), `tests/test_v8a_reportes_fallos_backend.py` (el valor inválido pasó de «anio» a «trimestre»).
- Resultado: 100 passed (periodos, cycle_summary, v8a fallos backend, reporte_resumen_puente, simulador).
- Pendiente esperado: `tests/test_t15_rutas_equivalentes.py::test_openapi_identico` falla porque el OpenAPI cambia (enum de periodo); según §8 hay que actualizar `docs/informes/tanda15/base/` en la etapa D. Arquitectura de capas pasa.

## Etapa D — DbManager y endpoints (2026-11-02)

Archivos tocados: `services/domain/logging/db_manager.py` (solo dos métodos nuevos), `backend/rutas/reportes.py` (3 rutas y ayudantes), `backend/rutas/_comun.py` (solo el comentario de `_ciclo_json`, DR-H07), `tests/test_backend_dashboard_reportes.py` (nuevo, 32 pruebas), `tests/test_t15_rutas_equivalentes.py` (nota en el docstring), `docs/informes/tanda15/base/rutas.json` y `openapi.json`.

DbManager (solo lectura, una consulta cada una, sin migración: `idx_ciclos_fecha` y `idx_alarmas_aparecida` ya existen): `get_ciclos_periodo(desde, hasta)` devuelve dicts con `id, numero_ciclo, fecha_inicio, fecha_fin, tipo_ciclo, nombre_ciclo, numero_programa, resultado, operador, avisos_ticket` por `fecha_inicio` e `id`, en [desde, hasta); `get_alarmas_periodo(desde, hasta)` devuelve `codigo, nivel, titulo` con `aparecida` en [desde, hasta).

Formas finales (sin token; fechas ISO `YYYY-MM-DD`, `hasta` inclusivo como en `/report/summary`):
- `GET /report/dashboard?periodo=dia|semana|mes|anio&fecha=` (periodo por defecto `dia`, fecha por defecto hoy) → `{periodo, desde, hasta, anterior: {desde, hasta}, indicadores: {total, completados, fallos, cancelados, sin_cierre, exito_pct, duracion_media_s (float|null), duraciones_excluidas}, indicadores_anterior (misma forma | null si el periodo anterior no tiene ciclos), serie: [{etiqueta, inicio, total, completados, fallos}], por_programa, causas_fallo (misma forma que /report/summary, vía resumen_periodo.resumir), alarmas: [{codigo, codigo_visible, nivel, titulo, cantidad}] (lista completa; la pantalla recorta a 8), operadores: [{operador, sin_operador, cantidad}] (máx. 5), operadores_otros: null | {operadores, ciclos}}`.
- `GET /report/calendar?periodo=&fecha=&programa=` (periodo por defecto `mes`) → `{periodo, desde, hasta, programas: [{numero, programa_id, nombre}], programa (int|null), dias: [{fecha, estado, intentos, exitos}]}`. Estados: `futuro, en_curso, sin_operacion, exito, exito_fallo_previo, sin_exito, falto, no_ejecutado`. `intentos` y `exitos` no cuentan el ciclo activo.
- `GET /report/day-cycles?programa=<n>&fecha=` (programa obligatorio, ≥ 1) → `{fecha, estado, ciclos: [_ciclo_json…]}` en orden de inicio; incluye el ciclo activo si es del programa.

Resultados: `tests/test_backend_dashboard_reportes.py`, `test_t15_rutas_equivalentes.py`, `test_arquitectura_capas.py` y `test_backend_cycle_summary.py`: 98 passed. También verdes `test_v8a_reportes_fallos_backend.py` y `test_backend_ciclo_en_curso_endpoints.py`. La base de rutas se actualizó añadiendo las 3 rutas a `rutas.json` (sin reordenar las demás; se comprobó que las existentes no cambian) y regenerando `openapi.json` con `openapi_ordenado`.

Decisiones (todas DECISIÓN SIN CONFIRMAR salvo que se diga lo contrario):
1. **Título de alarma:** hay mecanismo en el backend: `i18n.t("alarmas.<código>.titulo")` en el idioma activo del backend; sin esa clave (o código con «.»), el título guardado. El idioma es el del proceso del backend, no el de la pantalla que consulta (el endpoint no recibe idioma); si la UI necesita el otro idioma, la etapa E debe traducir por `codigo`.
2. **Ciclo activo** = `_ciclo_de_pantalla()` (solo hay uno con la máquina en CICLO; ante un error, ninguno). En `/report/dashboard` el ciclo en curso cuenta como «sin cierre» y en `total` (misma agrupación que `/report/summary`); solo el calendario lo excluye de los intentos y de N(D).
3. **Selector de programas (DR-D06):** se calcula con el periodo pedido (`periodo`/`fecha`), no con todo el mes/año que dibuja el calendario; así en Día o Semana el selector refleja ese día o esa semana. El número de programa es el efectivo (DR-H02); sin número, el ciclo no aparece en el selector ni cuenta como intento de ningún programa, pero sí en N(D). Nombre y `programa_id`: los del programa actual con ese número; si ya no existe, el del ciclo más reciente del periodo. Sin ciclos en el periodo: `programas` vacío y `programa` null (los días salen `sin_operacion`/`no_ejecutado`/`futuro`).
4. **Mes del calendario con `semana`:** se usa el mes que contiene `fecha` (una semana a caballo entre dos meses no muestra el otro mes).
5. **`por_programa.programa_nombre`** en el dashboard sale del ciclo más reciente *del periodo*; `/report/summary` lo toma del más reciente de toda la base. Puede diferir si un programa se renombró.
6. **`day-cycles`:** `programa_numero` de cada ciclo se sustituye por el número efectivo (DR-H02) para que coincida con el filtro; `_ciclo_json` por sí solo lo toma del programa actual.
7. **Operadores:** claves extra respecto al §8: `sin_operador` por fila y `operadores_otros` aparte (el §8 mostraba solo `{operador, cantidad}`).
8. **Avisos no resueltos para la etapa E:** el simulador (`simulador/servidor.py`) no tiene las rutas nuevas; `ReporteResumen` sigue con `PERIODOS` de tres.

## Etapa E — Pantalla Reportes (2026-11-02)

Archivos nuevos: `qml/Pantallas/Reportes.qml`, `qml/Componentes/{ListaProgramasReporte,ListaAlarmasPeriodo,ListaOperadores}.qml`, `qml/Pruebas/PruebaReportes.qml`, `tests/helpers/reportes_ejemplo.py` (backend REAL de solo lectura sobre una base temporal sembrada: ~125 ciclos de octubre de 2026, septiembre para comparar, 10 códigos de alarma; días notables: 8 con fallo previo, 14 «faltó», 21 sin éxito), `tests/banco/rep_capturas_reportes.py`, `tests/test_rep_pantalla_reportes_qml.py` (15 casos + 6 de textos).
Archivos tocados: `qml/Main.qml` (`reportesComp`, `onReportesPulsado: pila.push(reportesComp)`; se quitó `reporte:` del menú), `qml/Pantallas/MenuPrincipal.qml` (retirada `ventanaReportes`, ≈450 líneas; la tarjeta solo emite `reportesPulsado`; `abrirVentana("reportes")` también), `qml/Pruebas/PruebaMenuPrincipal.qml`, `qml/Componentes/SelectorPeriodo.qml` (propiedad `conAnio`: 4.º filtro con rótulos `reportes.periodo_*`; sin ella queda idéntico), `bridge/reporte_dashboard.py` (causa de fallo: `abrirFallo`, `moverPaginaFallo`, `cerrarFallo`, `causaFallo`, `ciclosFallo`, `paginaFallo`, `paginasFallo`, `totalFallo`, `cargandoFallo`, `sinConexionFallo`; consulta `/report/failures`), `domain/reporte_dashboard.py` (cada fila de alarma lleva `detalle` para `VentanaDetalleAlarma`), `i18n/es.json` y `en.json` (15 claves `reportes.*` al final del bloque, p. ej. `cal_titulo`, `cal_ver_anio`, `cal_cargando`, `cal_sin_intentos`, `graf_*`, `prog_vacia`, `mant_correctivos`, `mant_repuestos`), `tests/helpers/textos_caben_qml.py` (sin `ventanaReportes`; nuevo `revisar_reportes`), `tests/test_menu_principal_pantalla_qml.py`, `tests/test_u8_correo_rechazo_parcial_qml.py` (el caso de Reportes pasó a `test_rep_pantalla_reportes_qml.py`), `tests/test_u10b_textos_caben_qml.py` (se quitó solo la aserción «hay algún TextoAjustable en el menú»: era el encabezado de la tabla de la ventana retirada; el bucle de comprobación se conserva y `test_u10a` cubre los de Preciclo), `tests/test_i18n.py` (las familias `menu.` y `reportes.` leen los rótulos de `SelectorPeriodo` y ya no las pestañas Resumen/Consolidado).

Pantalla: barra superior (`EncabezadoMenu`: logo, reloj y campana con el panel de alarmas; título REPORTES) y barra inferior (`BarraInferiorMenu` personalizada: Inicio a la izquierda, Salir a la derecha) fijas; `Flickable` con las secciones en el orden del §5 (Periodo, Indicadores en 2×2, Resultado, Ciclos por día, Por programa, Calendario + panel del día, Causas de fallo en dos columnas, Mantenimiento / Alarmas / Por operador en tres columnas, Acciones). Todo visible sin sesión; sin lectura, tarjeta con `textoError` y «Reintentar». Tocar un intento del día o un ciclo de una causa de fallo abre una capa con `DetalleCiclo` (curva por `CiclosHistorial.cargarGrafica`, imprimir, enviar). Enviar usa `SelectorDestino` con `sesionActiva` (REP-13). «Ver todas» de las alarmas abre un panel paginado (8 por página) y la fila abre `VentanaDetalleAlarma`.

Capturas (1200×1920 y 1080×1920, es y en; plataforma real de Windows, ventana sin marco en 0,0): `docs/informes/dashboard_reportes/capturas/rep_<idioma>_<tamaño>_{mes_1..4,anio_1,anio_calendario,dia_previo,dia_previo_panel,dia_falto,selector,alarmas_todas,correo_sin_sesion}.png` (hay además `rep_*_mes_5.png` de una corrida anterior, ya obsoletos). Con offscreen los `Shape` salen sin recortar al desplazar el Flickable (figuras fuera de su caja), por eso el banco usa la plataforma de Windows por defecto.

Resultados reales (offscreen; suite agrupada de 20 archivos: 611 pruebas, 11 min 42 s): 605 pasaron y 6 fallaron por efecto del retiro de `ventanaReportes` (4 de `test_u10b::test_menu_abreviado...` y 2 de `test_i18n::test_familia_dinamica...`); tras actualizarlas, `test_i18n.py` + `test_i18n_linea_base.py` dan 73 passed y `test_u10b_textos_caben_qml.py -k menu` da 20 passed. Pasan: `test_v8a_textos`, `test_v8b_textos`, `test_u10a_textos_caben_qml`, `test_t21_textos_caben_qml`, `test_main_menu_principal_qml`, `test_menu_principal_pantalla_qml`, `test_arquitectura_capas`, `test_u8_correo_rechazo_parcial_qml`, `test_c2_selector_correo_manual_qml`, `test_rep_calendario_qml`, `test_rep_componentes_graficos_qml`, `test_reporte_dashboard_dominio`, `test_reporte_dashboard_puente`, `test_reporte_resumen*`, `test_t22_regla_teclado_accion` y `test_rep_pantalla_reportes_qml` (carga sin avisos QML en es/en; periodo Día/Semana/Mes/Año y flechas; ninguna escritura al backend al cargar y navegar; panel del día y detalle del ciclo; causa de fallo → lista → detalle; alarmas con «Ver todas»; imprimir resumen; correo con y sin sesión; consolidado grande con confirmación; sin destinatarios guardados; rechazo parcial en rojo; sin conexión y reintento; Inicio y Salir; textos dentro de su cuadro en todos los estados a 1200×1920, 1024×1638 y 1080×1920). No se corrió la suite completa.

Desvíos del plan y DECISIÓN SIN CONFIRMAR:
1. **Inicio/Salir:** Inicio vuelve al Menú Principal (`ventana.atras()`) y Salir va a la pantalla principal del equipo (`volverAPrincipal()`); el plan decía «como en el Menú Principal» pero allí son Atrás/Inicio. DECISIÓN SIN CONFIRMAR.
2. **Encabezado:** título REPORTES con reloj y campana; no muestra «equipo y puerta» (el encabezado del menú no los trae). DECISIÓN SIN CONFIRMAR.
3. **Panel del día debajo del calendario**, a todo el ancho (no «a la derecha»: siete círculos de ≥ 64 px no dejan ancho a 1200). Solo en la vista de mes.
4. **Tamaño estimado del consolidado grande:** 0,1 MB por ciclo (`mbPorCiclo`), umbral 300 ciclos (`umbralConsolidado`); a medir en el banco con el PDF real. DECISIÓN SIN CONFIRMAR.
5. **Textos de envío:** los botones conservan su rótulo y, si no se puede enviar, una nota bajo ellos dice por qué (correo sin configurar o «No hay destinatarios guardados»).
6. **Título de la alarma** en el panel «Ver todas» y en el detalle: se arma en el idioma de la pantalla; un título que no cabe baja a varias líneas (no se corta).
7. **Anillo de mantenimiento:** su título va en un `Text` propio que se ajusta en varias líneas (el del `AnilloProgreso` no cabe en una línea en la columna de un tercio).
8. `ReporteResumen`, `ResumenPeriodo.qml` y las claves `reportes.pestana_*` quedan sin uso en la UI (se conservan; sus pruebas siguen verdes). `ventana.reporte` sigue inyectado en `Main.qml` pero nadie lo usa; se puede retirar en una etapa posterior.
9. Hay dos archivos modificados en el árbol que no son de esta etapa (`simulador/servidor.py`, `Componentes/CirculoFaseLiquido.qml`).
Pendiente de banco para Cristian: navegación táctil real de la pantalla, rendimiento de la vista Año con datos reales y el umbral del consolidado.

## Etapa G — Riesgos, trazabilidad y documentación (2026-11-02)

- `docs/riesgos/registro_riesgos.md`: sección «Dashboard de Reportes» con HAZ-REP-01 (MEDIA; verificación = prueba de textos y revisión de capturas), HAZ-REP-02 (BAJA; residual DR-H08, control solo en la UI) y HAZ-REP-03 (BAJA).
- `docs/riesgos/matriz_trazabilidad.md`: REQ-37 a REQ-50, uno por REP-01 a REP-14 (REQ-36 era el último). Las pruebas existentes llevan `pytestmark = [... req("REQ-xx")]` al final del archivo, sin cambiar su lógica; `test_rep_pantalla_reportes_qml.py` tenía `req("REP-01")` y pasó a REQ-37, 44–48.
- Prueba nueva `tests/test_rep_textos_prohibidos.py` (REQ-50): ninguna clave `reportes.*` (es/en) ni literal de los QML del dashboard contiene «conforme»/«apto» (ni sus equivalentes en inglés); la leyenda DR-H01 (`reportes.cal_leyenda`) es exactamente la acordada en ambos idiomas y el dominio la usa. La clave heredada del Historial queda fuera.
- `CLAUDE.md`: sección «Dashboard de Reportes (tanda 25, 2-nov)».
- DR-H07 (comentario de `_ciclo_json`) ya hecho en la etapa D; i18n es/en en el commit 96a28ed5.

### DECISIÓN SIN CONFIRMAR recogidas (A–E)
- B: `PERIODOS` se queda en tres; el dashboard usa `PERIODOS_REPORTES` (con «anio»).
- D: (1) título de alarma en el idioma del backend; (2) el ciclo en curso cuenta como «sin cierre» y en `total` del dashboard, no en el calendario; (3) el selector de programas se calcula con el periodo pedido; (4) con `semana` el calendario usa el mes que contiene `fecha`; (5) `por_programa.programa_nombre` del ciclo más reciente del periodo; (6) `day-cycles` con el número de programa efectivo; (7) claves extra `sin_operador` y `operadores_otros`.
- E: (1) Inicio vuelve al Menú Principal y Salir a la pantalla principal; (2) encabezado sin equipo ni puerta; (3) panel del día debajo del calendario; (4) consolidado grande: 0,1 MB por ciclo y umbral de 300 ciclos; (5) notas bajo los botones de envío; (6) títulos de alarma en el idioma de la pantalla; (7) anillo de mantenimiento con título propio; (8) `ReporteResumen`, `ResumenPeriodo.qml` y `reportes.pestana_*` sin uso pero conservados.
- AJ-01: sin decisión (no se subió la saturación).
- Pendiente de banco para Cristian: navegación táctil, rendimiento de la vista Año con datos reales, umbral del consolidado, envío sin sesión, aprobación visual de AJ-01.

### Archivos tocados por toda la tanda (`git diff --name-only dev..HEAD` más el trabajo sin commit de la etapa G; sin las capturas PNG de `docs/informes/dashboard_reportes/capturas/`)
- `CLAUDE.md`
- `docs/informes/dashboard_reportes/F_diagnostico_correo.md`
- `docs/informes/dashboard_reportes/R_informe.md`
- `docs/informes/dashboard_reportes/aj01_notas.md`
- `docs/informes/dashboard_reportes/claves_i18n_reportes.json`
- `docs/informes/dashboard_reportes/estado.md`
- `docs/informes/tanda15/base/openapi.json`
- `docs/informes/tanda15/base/rutas.json`
- `docs/mis_plans/planeacion_dashboard_reportes.md`
- `docs/riesgos/matriz_trazabilidad.md`
- `docs/riesgos/registro_riesgos.md`
- `src/autoclave/backend/rutas/_comun.py`
- `src/autoclave/backend/rutas/reportes.py`
- `src/autoclave/i18n/en.json`
- `src/autoclave/i18n/es.json`
- `src/autoclave/services/domain/logging/db_manager.py`
- `src/autoclave/services/domain/reportes/dashboard.py`
- `src/autoclave/ui_qml/app.py`
- `src/autoclave/ui_qml/bridge/acciones_ciclos.py`
- `src/autoclave/ui_qml/bridge/reporte_dashboard.py`
- `src/autoclave/ui_qml/domain/reporte_dashboard.py`
- `src/autoclave/ui_qml/qml/Componentes/AnilloProgreso.qml`
- `src/autoclave/ui_qml/qml/Componentes/CalendarioEjecucion.qml`
- `src/autoclave/ui_qml/qml/Componentes/DeslizadorInicio.qml`
- `src/autoclave/ui_qml/qml/Componentes/GraficaArea.qml`
- `src/autoclave/ui_qml/qml/Componentes/GraficaDona.qml`
- `src/autoclave/ui_qml/qml/Componentes/ListaAlarmasPeriodo.qml`
- `src/autoclave/ui_qml/qml/Componentes/ListaOperadores.qml`
- `src/autoclave/ui_qml/qml/Componentes/ListaProgramasReporte.qml`
- `src/autoclave/ui_qml/qml/Componentes/MesMiniatura.qml`
- `src/autoclave/ui_qml/qml/Componentes/PanelDiaCalendario.qml`
- `src/autoclave/ui_qml/qml/Componentes/SelectorDestino.qml`
- `src/autoclave/ui_qml/qml/Componentes/SelectorPeriodo.qml`
- `src/autoclave/ui_qml/qml/Componentes/TarjetaIndicador.qml`
- `src/autoclave/ui_qml/qml/Main.qml`
- `src/autoclave/ui_qml/qml/Pantallas/MenuPrincipal.qml`
- `src/autoclave/ui_qml/qml/Pantallas/PantallaPreciclo.qml`
- `src/autoclave/ui_qml/qml/Pantallas/Reportes.qml`
- `src/autoclave/ui_qml/qml/Pruebas/PruebaMenuPrincipal.qml`
- `src/autoclave/ui_qml/qml/Pruebas/PruebaReportes.qml`
- `src/autoclave/ui_qml/qml/Tema/Colores.qml`
- `src/autoclave/utils/periodos.py`
- `tests/banco/rep_capturas_reportes.py`
- `tests/helpers/reportes_ejemplo.py`
- `tests/helpers/textos_caben_qml.py`
- `tests/test_acciones_ciclos_puente.py`
- `tests/test_backend_cycle_summary.py`
- `tests/test_backend_dashboard_reportes.py`
- `tests/test_c2_acciones_correo_manual.py`
- `tests/test_c2_selector_correo_manual_qml.py`
- `tests/test_dashboard_reportes_servicio.py`
- `tests/test_dr_h06_correo_manual_punta_a_punta_qml.py`
- `tests/test_i18n.py`
- `tests/test_menu_principal_pantalla_qml.py`
- `tests/test_periodos_calendario.py`
- `tests/test_rep13_acciones_sin_sesion.py`
- `tests/test_rep13_selector_sin_sesion_qml.py`
- `tests/test_rep_calendario_qml.py`
- `tests/test_rep_componentes_graficos_qml.py`
- `tests/test_rep_pantalla_reportes_qml.py`
- `tests/test_rep_textos_prohibidos.py`
- `tests/test_reporte_dashboard_dominio.py`
- `tests/test_reporte_dashboard_puente.py`
- `tests/test_reportes_i18n_paridad.py`
- `tests/test_t15_rutas_equivalentes.py`
- `tests/test_u10b_textos_caben_qml.py`
- `tests/test_u8_correo_rechazo_parcial_qml.py`
- `tests/test_v8a_reportes_fallos_backend.py`

No se tocaron `src/autoclave/simulador/servidor.py` ni `Componentes/CirculoFaseLiquido.qml` (cambios ajenos sin commit). No se compiló la entrega: `python tools/entrega/compilar_entrega.py` desde `dev` limpio.

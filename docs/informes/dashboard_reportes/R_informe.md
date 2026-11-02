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

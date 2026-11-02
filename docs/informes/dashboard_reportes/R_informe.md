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

# B9a — Llamadas síncronas en el tick: `contador.siguiente` y `marcar_en_curso`

**Dónde:** `CycleLogger._on_inicio()` (`services/domain/logging/cycle_logger.py` ~líneas 317-370), que corre dentro del tick del `ControlLoop` UNA vez, en el primer tick en que la máquina entra en CICLO (`_on_inicio_protegido`). Ambas escriben `data/ciclo_contador.json` de forma atómica (temporal + fsync + `os.replace`). `siguiente()` además va precedida de `db.max_numero_ciclo()` (lectura SQLite; ya protegida por `try/except` y omitida sin base de datos).

**Decisión: se DOCUMENTA con medición, no se cambia el código.** Razones: (1) ocurre una sola vez por ciclo, no por tick; (2) el número de ciclo debe conocerse antes de escribir la base y el respaldo (`numero` se usa en `_on_inicio` enseguida), así que `siguiente` no puede ser asíncrona sin cambiar la semántica de numeración sin huecos; (3) `marcar_en_curso` debe quedar escrita ANTES de la base (TMG-03 de T6: permite recuperar el ciclo interrumpido tras un corte), y la base y el respaldo corren en dos colas FIFO distintas, así que moverla a un hilo no garantizaría ese orden.

**Medición** (`python tools/medir_contador_ciclos.py 100`, disco local de esta máquina, 100 repeticiones, n = 100):
| llamada | p50 | p95 | máx |
|---|---|---|---|
| `siguiente` | ~1.9 ms | ~2.4 ms | ~2.8 ms |
| `marcar_en_curso` | ~1.7 ms | ~2.3 ms | ~3.9 ms |

El tick nominal es de 0.5 s (`interval=0.5`): el costo es <1 % del tick y ocurre una vez por ciclo. Riesgo residual: en un disco lento o con antivirus el fsync podría tardar decenas de ms; sigue muy por debajo del tick. **Comprobación manual sugerida en el equipo de pruebas:** ejecutar `tools/medir_contador_ciclos.py 100 <carpeta data del equipo>` y confirmar que el máximo es < 100 ms.
Sin revisión de `timing-auditor` (no ejecutado por orden de Cristian, 20-oct).

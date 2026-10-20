# E1 — Ensayo completo en simulador

## Cómo se hizo (y límites)
- El simulador del repositorio (`autoclave.simulador`) solo REPITE ciclos grabados: no puede provocar paro, pérdida de tarjeta ni cortes. Se usó el arnés de planta simulada de T11 (modelo físico simple de la cámara: vapor saturado, aire, sonda con retardo, chaqueta) con el código REAL de producción: `CicloState` (6 fases), `SetOutput`, `ProtocoloFallo`, `ProtocoloEstadoSeguro`, `CycleLogger` (ticket y respaldo JSONL), `ContadorCiclos`, `DbManager` y la evaluación real de cámara segura. NO se probó el ejecutable ni la tarjeta; el `ControlLoop` completo no entra en este arnés (la pérdida de tarjeta se dispara con la misma llamada que hace el ControlLoop: `abortar_por_desconexion`).
- Los valores de la planta son PROVISIONALES: sirven para verificar la secuencia, los estados finales y la seguridad de las salidas; los tiempos (min simulados) y las rampas de enfriamiento NO representan al equipo.
- Código: `tests/test_e1_ensayo_simulador.py` (20 casos + generación de la tabla con `E1_ESCRIBIR_INFORME=1`). Tabla cruda: `E1_tabla.md`.

## Resultados: programa × evento
Todos los casos terminan en el estado esperado, con el ticket cerrado con el estado real y `Operador: ensayo` (O1), sin ninguna salida de proceso (vapor, vacío, bomba, aire comprimido) energizada al final, y sin vapor a la cámara tras el evento.

| Programa | Ciclo completo | Cancelación | Paro en ciclo | Pérdida de tarjeta | Corte de energía y reinicio |
|---|---|---|---|---|---|
| 1 Bowie & Dick | COMPLETADO (12,9 min) | CANCELADO, ventea a 75 kPa | EMERGENCIA, SIS-01, sin válvulas (123 °C / 220 kPa se mantienen) | FALLO_CONEXION, COM-02, ventea | ciclo interrumpido cerrado; estado seguro tras confirmar |
| 2 Instrumental 134 | COMPLETADO (10,9) | CANCELADO | EMERGENCIA, SIS-01 | FALLO_CONEXION, COM-02 | ídem |
| 3 Instrumental 121 | COMPLETADO (21,3) | CANCELADO | EMERGENCIA, SIS-01 | FALLO_CONEXION, COM-02 | ídem |
| 4 Líquidos | COMPLETADO (21,9), sin prevacío ni secado | CANCELADO, enfría a 56 °C sin usar la rápida caliente | EMERGENCIA, SIS-01 | FALLO_CONEXION, COM-02 | estado seguro sin la rápida con la carga caliente |

Detalle por evento:
- **Paro:** con el paro activo y tras SOLTARLO sin confirmar, las salidas de proceso quedan en 0 (sin avance automático, §15.2), para los 4 programas.
- **Corte y reinicio (simulado):** la marca de ciclo en curso (`ciclo_contador.json`) sobrevive al corte; al arrancar con la base nueva el ciclo se cierra como INTERRUMPIDO (1 ciclo); la cámara NO se considera segura (caliente y presurizada); la recuperación arranca con todo en 0 y sin válvulas; durante 60 s sin confirmar no se mueve nada; "Confirmar y llevar a estado seguro" lo lleva a estado seguro (26,8 min simulados en sólidos; 1,5 min en líquidos con la planta provisional). Con carga líquida nunca se usó la rápida caliente; en sólidos el protocolo del programa usa la rápida con la cámara caliente (esperado: no hay líquido que hierva).
- **Apagado en FALLA / sin tarjeta (A1) y cambio de programa en FALLA (S2):** no dependen del programa. Se verifican con sus pruebas (`tests/test_t7_apagar_equipo.py`, 52 casos: FALLA, EMERGENCIA, paro, sin tarjeta, cámara no segura, ciclo rechazado, pasos que fallan, `ALL_OFF` inmediato; `tests/test_s2_cycle_select.py` y afines: cambio de programa permitido en FALLA, rechazado en ciclo, auditado). Todas en verde (100 casos de esas pruebas y las de select).

## Anomalías / observaciones
- No se encontraron defectos de la lógica de ciclo con este arnés.
- Se corrigió una expectativa mía (no un defecto): para programas de sólidos el protocolo de estado seguro puede abrir la rápida con la cámara a >100 °C; lo que se prohíbe es hacerlo con carga LÍQUIDA caliente.
- Pendiente fuera de este arnés (comprobar en banco): ensayo con el `ControlLoop` real y la tarjeta (B-07, C-03, C-04 y F-01 a F-03 de la hoja de pruebas) y con el ejecutable. Los valores de la planta (rampas, enfriamiento por chaqueta) deben calibrarse con datos del equipo antes de usar los tiempos.

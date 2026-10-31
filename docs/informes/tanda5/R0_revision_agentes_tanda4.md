# R0 — Revisión de agentes de la tanda 4

Resultados encontrados en `docs/informes/tanda4/R_revision_agentes.md` (safety-reviewer sobre B5/B7/B8; timing-auditor sobre B5/B7/B8/B9a). Las correcciones estaban en el índice sin commit: quedaron en **b33b9cf** (`dev`). Los dos Altos (SAF-01, TMG-01) están corregidos con prueba (`tests/test_revision_tanda4.py`). Como los resultados existían y estaban completos, no se volvieron a ejecutar los agentes.

Pendientes de esa revisión:
- TMG-08 (auditoría sin usuario en el código de la otra sesión): **corregido en E0** (8d5ddce).
- TMG-07 (temporizador de inactividad que podría sacar a una sesión nueva): **corregido en P1** (número de generación del modo prueba).
- SAF-04 (el ACK del ALL_OFF de `exit_test_mode` no se audita) y TMG-06: siguen pendientes (Bajos).

## Comprobación obligatoria de B7: caducidad del token frente a acciones de seguridad
Revisado en `backend/server.py`: **ninguna acción de seguridad exige token.**

| Acción | Endpoint | Token |
|---|---|---|
| Cancelar ciclo | `POST /cycle/abort` | no |
| Reconocer falla | `POST /fault/reset` | no (decisión 16) |
| Confirmar estado seguro | `POST /safe-state/confirm` | no |
| Confirmar resultado del ciclo | `POST /cycle/acknowledge` | no |
| Reconocer alarma | `POST /alarms/{clave}/acknowledge` | no (usuario opcional en el cuerpo) |
| Apagar equipo | `POST /system/shutdown` | no |
| Apagar salidas | `POST /outputs/reset` | no |
| Puertas | `POST /doors/{n}/open` y `/close` | no |
| Paro de emergencia | entrada física | no aplica |

Salidas sin supervisión con el token vencido: el modo prueba es lo único que deja salidas manuales. Lo cierran el vigilante SAF-01 (2 s después de invalidarse la sesión dueña) y el plazo de inactividad (90 s).

# Informe: llenado líquido de la barra de fases (31-oct-2026)

Rama `llenado-fases` (worktree `codigo_autoclave_llf`). NO unida a `dev`. NO se compiló la entrega.

## Qué cambió
- Backend/dominio/puente: `fraccion` y `referencia_s` por fase en `/cycle/current/progress`; `exposicion_total_s` publicado por esterilización (sin cambio de lógica de control).
- QML: `BarraFases`, `CirculoFaseLiquido`, `ConectorFase` (ola viva, vaciado parcial al recalcular, conector que se llena y chorro hacia el siguiente círculo).
- Decisiones P-01..P-12 aceptadas por Cristian; animación aprobada visualmente el 31-oct.

## Archivos
`core/runtime/progreso_ciclo.py`, `core/runtime/status.py`, `state_machine/cycle_phases/esterilizacion.py`, `backend/rutas/ciclo.py`, `ui_qml/domain/ciclo_en_curso.py`, `ui_qml/bridge/progreso_ciclo.py`, los 3 componentes QML, `PantallaCicloEnCurso.qml`, `PruebaCicloEnCurso.qml`, pruebas `tests/test_llf_*`, `tests/banco/llf_capturas_barra_fases.py`, capturas en `capturas/`.

## Pruebas
Suite completa verde (código 0). Capturas a 1024 px y 1200×1920 en `capturas/`.

## Hallazgos
| ID | Estado |
|---|---|
| LLF-01..16 | Atendidos en la planeación; revisor (opus) aprobó con observaciones |
| Revisión 1: entero gigante → OverflowError en el bloque LLF | Corregido (`_segundos_llf`) |
| Revisión 2: tope QML reasignable | Corregido (`_topeEfectivo`) |
| Revisión 3, 4, 5 | Aceptados (ver `AJUSTES.md`) |
| `tiempo_restante` con entero gigante / referencias None | Preexistente, fuera de alcance, sin corregir |

## Pendiente
- LLF-08: medir CPU en el PC de la estación (banco, Cristian).
- Unir a `dev` cuando Cristian lo decida.
- Compilar la entrega (no hecho): desde `dev` limpio, `python tools/entrega/compilar_entrega.py`.

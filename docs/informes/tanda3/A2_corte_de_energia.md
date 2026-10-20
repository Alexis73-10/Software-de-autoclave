# A2 — Corte de energía sin UPS

Pruebas: ver A1 (3620 en total; 13 nuevas en `tests/test_a2_corte_de_energia.py`).

## Revisión
| Elemento | Antes | Ahora |
|---|---|---|
| BD | WAL, `synchronous` implícito (FULL por defecto de SQLite) | `synchronous = FULL` explícito + `PRAGMA quick_check` al abrir; si falla lanza "malformed" → el arranque la aparta, deja BD_BLOQUEADA y opera sin BD con alarma (flujo T8 existente) |
| Ciclo interrumpido | `cerrar_ciclos_interrumpidos` + marca `en_curso` en `ciclo_contador.json` | sin cambio; se pierde el tramo no escrito: las lecturas ya salieron por el respaldo JSONL con fsync por línea |
| Respaldo JSONL | fsync por línea; línea cortada descartada | además se lee con `errors="replace"`: bytes basura al final (NTFS) ya no invalidan el archivo entero |
| `ciclo_contador.json` | atómico (tmp+fsync+replace) | igual; ilegible → se recupera con el máximo de la BD |
| `last_shutdown.json`, `backend.pid` | `write_text` (no atómico) | atómicos (`utils/archivos.py`); ilegibles se leen como ausentes |
| `calibration.yaml` | `open("w")` directo: un corte dejaba un YAML truncado y el equipo no arrancaba (ARR_CALIBRACION) | atómico + copia `.bak` de la versión previa |
| perfil de instalación | atómico (TMG-03 T9) | igual; `cambio_perfil.py` ahora también atómico |

## Decisiones sin confirmar
- `quick_check` en lugar de `integrity_check` (más rápido; detecta daño de páginas). Alternativa: `integrity_check` (lento con muchas lecturas).
- Si `calibration.yaml` queda corrupto el equipo sigue sin arrancar (ARR_CALIBRACION): se deja la copia `.bak` pero NO se restaura sola (restaurar una calibración vieja en silencio es peor). Un técnico la restaura a mano.

## Revisores
Cubiertos junto con A1 (timing-auditor/safety-reviewer revisaron la secuencia de apagado; los cambios de A2 son de persistencia sin lógica de control).

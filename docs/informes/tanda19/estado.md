# Tanda 19 — estado

Fuente: `docs/mis_plans/decisiones_tanda_19.md`, `docs/mis_plans/planeacion_enlace_modbus.md` e instrucción `docs/mis_plans/instruccion_claude_code_tanda_19.md`.

| Etapa | Estado | Nota |
|---|---|---|
| A0 | Hecha | **base tanda-18** (tanda-18 no es ancestro de dev); rama `tanda-19` desde `tanda-18` (1dd3e94); worktree limpio; commit 875d6e2 (docs y manuales M31); línea base verde en `base_suite.txt` (8521 recolectadas) |
| V | Hecha | V-01..V-04 (subagentes de solo lectura); notas en `V19_notas.md` |
| F1 | Hecha | pymodbus 3.16.1 (7563a3e) |
| F2 | Hecha | EnlaceES, enlace_io.json, build_enlace, enlace_io en /status (754e9a4) |
| F3 | Hecha | alarmas nuevas, i18n, catálogo (4964934) |
| P-s1 | En curso | rama `tanda-19-s1` |
| P-s2 | En curso | rama `tanda-19-s2` |
| P-s3 | En curso | rama `tanda-19-s3` |
| I | En curso | adelantado en la sesión principal: hoja de banco bloque M y riesgos MED (f70c096), .spec (f5c057c); falta unir P, integración, i18n, compilación y suite |
| R | Pendiente | |
| K | Pendiente | base tanda-18: K une las dos tandas a dev |
| L | Pendiente | |
| Z | Pendiente | |

## Tabla de propiedad de archivos (P)

Un dueño por archivo. Lo no listado es de la sesión principal (F o I): `pyproject.toml`, `requirements.lock.txt`, `packaging/*.spec`, `devices/factory/factory.py`, `backend/context.py`, `config/enlace_io.*`, `protocols/enlace.py`, `protocols/serial_link.py` (no se toca), `tests/conftest.py`, `docs/`.

| Dueño | Archivos |
|---|---|
| s1 | `src/autoclave/protocols/modbus_link.py`, `src/autoclave/protocols/modbus_link_config.py`, `src/autoclave/config/modbus_link.json`, `tests/helpers/m31_simulado.py`, `tests/test_t19_s1*.py` |
| s2 | `src/autoclave/hal/measures/converters.py`, `src/autoclave/hal/measures/units.py`, `src/autoclave/config/schema.py`, `src/autoclave/config/calibration_modbus.yaml`, `src/autoclave/config/calibration_writer.py`, `src/autoclave/utils/paths.py`, `src/autoclave/backend/dependencias.py` (solo `CALIBRATION_PATH`), `src/autoclave/backend/rutas/io.py` (solo calibración y el comentario de DO), `src/autoclave/backend/rutas/respaldo.py` (solo calibración), `src/autoclave/core/runtime/asignacion_io.py`, `src/autoclave/backend/server_reasignacion.py` (puertos), `src/autoclave/core/runtime/status.py` (`map_do`), `src/autoclave/config/instances/ACV-2026-001.yaml`, `src/autoclave/devices/io/set_io.py`, `src/autoclave/core/runtime/aire_atmosferico_prueba.py` (comentarios), `.gitignore`, `tools/verificar_calibracion_neutra.py`; pruebas: `tests/test_r8_*.py`, `tests/test_set_io_reset_outputs.py`, `tests/test_e11_retiro_aire_chaqueta.py`, `tests/test_p1_rutas_build_congelado.py`, `tests/test_t19_s2*.py` |
| s3 | `src/autoclave/services/domain/loop/control_loop.py`, `src/autoclave/state_machine/states/ciclo.py`, `src/autoclave/backend/rutas/sistema.py`, `src/autoclave/ui_qml/bridge/info_equipo.py`, `src/autoclave/ui_qml/qml/Componentes/PanelEquipo.qml`, `src/autoclave/ui_qml/controllers/info_sistema_controller.py`, `src/autoclave/ui_qml/qml/Pantallas/OpcionesInfoSistema.qml`, `src/autoclave/i18n/es.json`, `src/autoclave/i18n/en.json`; pruebas: `tests/test_e6_emparejamiento_tarjeta.py`, `tests/test_e6_control_loop_tarjeta.py`, `tests/test_t19_s3*.py` |

Último commit: f5c057c

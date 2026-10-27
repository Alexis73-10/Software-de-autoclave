# Tanda 19 — estado

Fuente: `docs/mis_plans/decisiones_tanda_19.md`, `docs/mis_plans/planeacion_enlace_modbus.md` e instrucción `docs/mis_plans/instruccion_claude_code_tanda_19.md`.

| Etapa | Estado | Nota |
|---|---|---|
| A0 | Hecha | **base tanda-18** (tanda-18 no es ancestro de dev); rama `tanda-19` desde `tanda-18` (1dd3e94); worktree limpio; commit 875d6e2 (docs y manuales M31); línea base verde en `base_suite.txt` (8521 recolectadas) |
| V | Hecha | V-01..V-04 (subagentes de solo lectura); notas en `V19_notas.md` |
| F1 | Hecha | pymodbus 3.16.1 (7563a3e) |
| F2 | Hecha | EnlaceES, enlace_io.json, build_enlace, enlace_io en /status (754e9a4) |
| F3 | Hecha | alarmas nuevas, i18n, catálogo (4964934) |
| P-s1 | Hecha | `tanda-19-s1` (d8a9f33, 0b99bad): ModbusLink, config, simulador M31; 97 pruebas |
| P-s2 | Hecha | `tanda-19-s2` (dcdb3de, 103fbf9, b8a42be): None por canal, calibración Modbus, puertos por enlace, buzzer DO 25; 76 pruebas |
| P-s3 | Hecha | `tanda-19-s3` (e4d061b, a723e62): alarmas Modbus en el lazo, enlace_io en la UI; 51 pruebas |
| I | Hecha | merges s2 (2851c55), s1 (b3e324f), s3 (a19e1b8) sin conflictos; carrera de test_uptime corregida en la prueba (d41b30e); integración Modbus 4b58f14; i18n sin claves huérfanas nuevas (solo alarmas.*, que lee el backend); hoja M y MED (f70c096); .spec (f5c057c); suite completa VERDE: 8765 passed, 10 skipped, 3 xfailed (8778 recolectadas = 8521 base + 257 nuevas) |
| R | Hecha | 0 altos; corregidos V19-s1-01,03..07, V19-s2-01..04, V19-s3-04 (r1 50ebae2, r2 364d16b); V19-s1-02/s3-01 y s3-02 documentados como DECISIÓN SIN CONFIRMAR; suite tras R: 8822 passed + 3 caídas de trabajador Qt en paralelo (test_home_view, test_impresion_menu x2) que pasan en serie → verde (8838 recolectadas) |
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

Último commit: 1277048 (más este)

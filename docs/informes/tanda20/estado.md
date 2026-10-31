# Estado — tanda 20

Rama `tanda-20` desde `dev` (391aedf). Último commit: ver la nota de cada fila.

| Etapa | Estado | Nota |
|---|---|---|
| A0 | Hecha | Árbol limpio (sin cambios de fin de línea). Rama `tanda-20` creada. Commit docs 2c05e2f. Línea base: 8838 recolectadas; 8822 passed, 10 skipped, 3 xfailed, 3 fallidas solo en paralelo (Qt, verdes en serie) — `base_suite.txt`. |
| B | Hecha | `G:\Respaldos_autoclave\pre_tanda20_20261027_1448\`; bundle `repo_completo.bundle` SHA-256 2224aa05770c2249b44d8819decc2af113f71b9cc411d010f863118503b9a86e (verify okay, releído desde G:); `dev_391aedf.zip` SHA-256 32c6cba444563f31e5a469b8d010ca3cb2fb17a2d7b668682fe2a730681a29ae; `LEEME.txt`; etiqueta local `respaldo-serial-pre-t20` sobre 391aedf. |
| V | Hecha | V-01 (inventario serial), V-02 (pruebas), V-03 (adenda), V-04 (Setup) recibidos; resumen en R20_informe.md. |
| F | Hecha | F2 bfc6f93 (claves i18n `configurar_modulo.*`; los textos del Setup van en `[CustomMessages]` del .iss, dueño s3 — DECISIÓN SIN CONFIRMAR para no partir el archivo). F1 0da003a (`tests/helpers/enlace_doble.py`, fixture `enlace_doble`). |
| P | Hecha | s1 (75857ed, d0510ac) unida en 9fce64a; s3 (30499a8, f2cc939) unida en cab7dfd; s2 (e6b2ac7..2828d25) unida en 20577d8. |
| I | Hecha | Uniones sin conflictos; `tests/test_t20_integracion.py`; grep limpio (solo historial); sin huérfanas i18n nuevas (381 = 381); T20-06 (f95e624, fee8f32); pyserial desinstalado. Suite final (tras R): 8824 passed, 11 skipped, 3 xfailed, 2 fallidas solo en paralelo (Qt, verdes en serie). Recolectadas 8840 = 8838 + 182 nuevas − 180 borradas. |
| R | Hecha | V20-s1 (2 altos + 6) en r1; V20-s2 (7) por la principal fff1c85; V20-s3 (11) en r3; re-revisión de los altos: cerrados; V20-rr-01/05 corregidos (último commit de código del merge de r1 + fix rr); rr-02..04 al registro de riesgos. Sin altos abiertos. Informe 104e4d8. |
| K | Hecha | dev d8c3ffa (Merge tanda-20 en dev), suite verde (4 Qt solo en paralelo); anomalías 8a214e9; entrega 1.0.0-alpha.4 a6795c1 + etiqueta v1.0.0-alpha.4 (`entrega/v1.0.0-alpha.4_2026-10-27`); K4 rol contra el simulador: ok. Sin push: `git push origin dev v1.0.0-alpha.4`. |
| L | Hecha | 5 worktrees de la tanda quitados + `git worktree prune`. |
| Z | Hecha | CLAUDE.md, informe R20, índice `informe_tanda_2026-10-27_t20.md`, CERRADO.txt (commit de cierre en dev). |

## Tabla de propiedad de archivos (P)

Un dueño por archivo. Lo que no está en la tabla no se toca en P.

| Dueño | Archivos |
|---|---|
| s1 | `src/autoclave/protocols/modbus_link.py`, `src/autoclave/protocols/modbus_link_config.py`, `src/autoclave/config/modbus_link.json`, `tests/helpers/m31_simulado.py`, `src/autoclave/exe_unico.py`, `src/autoclave/estacion/configurar_modulo.py` (nuevo), `tests/test_t19_s1_enlace.py`, `tests/test_t19_r1_enlace.py`, `tests/test_t20_s1*.py` |
| s2 | Todo lo demás del inventario V-01/V-02: `protocols/serial_link.py`, `serial_link_config.py`, `crc16.py`, `device_reset.py`, `config/serial_link.json`, `config/enlace_io.py`/`.json`, `config/calibration.yaml`, `config/plantillas/calibration_neutra.yaml`, `devices/factory/factory.py`, `utils/paths.py`, `hal/measures/converters.py`, `hal/measures/units.py`, `core/runtime/asignacion_io.py`, `services/domain/loop/control_loop.py` (solo comentarios), `backend/**` (salvo lo de s1), `ui_qml/controllers/info_sistema_controller.py`, `ui_qml/bridge/info_equipo.py`, `i18n/es.json`/`en.json`, `state_machine/**` (comentarios, catálogo), `protocols/enlace.py`, `installation/profile.py` (comentario), demás comentarios de `src/` que nombran el serial, `packaging/*.spec`, `tools/verificar_calibracion_neutra.py`, `tools/verificar_entrega_neutra.py`, `tools/log_calibracion_sensores.py`, `tools/emparejar_tarjeta.py`, `tools/entrega/info_compilacion.py`, `pyproject.toml`, `requirements.lock.txt`, `Hardware/`, `tests/conftest.py`, `tests/helpers/serial_doble.py`, todas las pruebas que dependan del serial (salvo las de s1 y s3), `tests/test_t20_s2*.py`, `docs/catalogo_alarmas.md`, `docs/riesgos/lista_soup.md`, `docs/riesgos/registro_riesgos.md` (solo riesgos del serial), `docs/README.md`, `tests/README.md` |
| s3 | `tools/instalador/autoclave.iss`, `tools/instalador/estacion_setup.ps1`, `tools/estacion/08_red_modulos.ps1` y `08_revertir_red_modulos.ps1` (nuevos), `tools/estacion/_comun.ps1`, `tools/estacion/LEEME.md`, `tools/instalador/LEEME.md`, pruebas del Setup (`tests/test_t9_e9_setup_estacion.py`, `test_t11_n11_instalador_limpia_tactiles.py`, `test_t17_s1_setup.py`, `test_t18_s1_escritorio_estacion.py`), `tests/test_t20_s3*.py` |
| principal (I/Z) | `docs/mis_plans/hoja_pruebas_banco/*` (T20-06), `docs/riesgos/registro_riesgos.md` (MED-04, AN-30/31/32, tras unir s2), `CLAUDE.md`, informes |

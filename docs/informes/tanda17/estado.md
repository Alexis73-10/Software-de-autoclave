# Tanda 17 — estado

Rama `tanda-17` desde `dev` (84c146a).

| Etapa | Estado | Nota |
|---|---|---|
| A0 | Hecha | precondición OK (tanda-16 ⊂ dev, árbol limpio); rama `tanda-17`; `424e5d6` documentos; línea base en `base_suite.txt` (8234 passed, 4 failed: 1 preexistente + 3 solo en paralelo) |
| A1 | Hecha | `fca0102` test_historial (R16 §8); `af32dbd` test_f1_registro_pruebas (bloque H, falla preexistente también en serie desde el cierre Z de la tanda 16). `compilar_entrega.py` corre la suite con `-n auto` y repite en serie las rojas (`--lf`) |
| V | Hecha | 4 subagentes; resumen en `V_resumen.md` |
| F | Hecha | F1 `7324847` ruta de datos; F2 `526a570` bitácora central; F3 `f101b2e` textos + UI-VER (UI-VER pasa de s4 a la sesión principal: retirar `app.version` rompía las pantallas) |
| P | Hecha | s1 `892a29b`, s2 `10b9427`, s3 `8daaa0b`, s4 `783c968` (resumen en `P_resumen.md`) |
| I | En curso | merges `53b59a4` (s3), `687f2e8` (s1), `2764835` (s2), `73c3624` (s4) sin conflictos; integración `32efe11`; suite completa corriendo |
| R | En curso | 4 revisores de solo lectura |
| K | Pendiente | |
| L | Pendiente | |
| Z | Pendiente | |

## Tabla de propiedad de archivos (P)

Un dueño por archivo. Lo no listado es de la sesión principal (I): `i18n/*.json` (los subagentes dejan sus textos en `docs/informes/tanda17/i18n/<s>.json`), `bitacora.py`, `db_manager.py`, `backend/context.py`, `puente_instalacion.py`, `utils/resources.py`, CLAUDE.md, hoja de banco.

| Dueño | Archivos |
|---|---|
| s1 · Setup y ruta de datos | `tools/instalador/autoclave.iss`, `tools/instalador/estacion_setup.ps1`, `tools/instalador/LEEME.md`, `tools/estacion/_comun.ps1`, `tools/estacion/LEEME.md`, `src/autoclave/instalador_exe.py`, `src/autoclave/utils/paths.py` (comentarios), `docs/instalacion/LEEME_INSTALACION.md`, `tests/test_t9_e9_setup_estacion.py`, `tests/test_t11_n11_instalador_limpia_tactiles.py`, `tests/test_instalador_exe_carpeta.py`, `tests/test_p1_rutas_build_congelado.py`, `tests/test_t17_s1*.py` |
| s2 · Estación: táctiles y arranque | `tools/estacion/06_asociar_tactiles.ps1`, `tools/estacion/06_revertir_asociar_tactiles.ps1`, `tools/estacion/03_tarea_autoclave.ps1`, `tools/instalador/tarea_arranque.ps1`, `src/autoclave/exe_unico.py`, `src/autoclave/estacion/` (nuevo: herramienta de táctiles y cubierta de arranque), `src/autoclave/ui_qml/app.py` (señal de primer cuadro), `packaging/Autoclave.spec`, `tests/test_t17_s2*.py` |
| s3 · Backend: sondas, estado seguro, modo prueba | `src/autoclave/core/runtime/sensores_ciclo.py`, `src/autoclave/core/managers/gestion_programas.py`, `src/autoclave/backend/rutas/programas.py`, `src/autoclave/backend/rutas/ciclo.py`, `src/autoclave/backend/rutas/historial.py`, `src/autoclave/backend/rutas/sistema.py`, `src/autoclave/backend/rutas/io.py`, `src/autoclave/ui_qml/domain/entradas_mostradas.py`, `src/autoclave/ui_qml/domain/ciclo_en_curso.py`, `src/autoclave/ui_qml/bridge/ciclos_historial.py`, `src/autoclave/ui_qml/exportacion/pdf_ciclo.py`, `src/autoclave/services/domain/logging/cycle_logger.py`, `src/autoclave/services/domain/loop/control_loop.py`, `src/autoclave/state_machine/estado_seguro.py`, `src/autoclave/state_machine/cycle_phases/protocolo_fallo.py`, `src/autoclave/core/runtime/salidas_prueba_seguridad.py`, `src/autoclave/core/runtime/camara_segura.py`, `src/autoclave/core/runtime/status.py`, `tests/test_o11_entradas_mostradas.py`, `tests/test_o3_entradas_mostradas.py`, `tests/test_s9_*.py`, `tests/test_s4_cic10.py`, `tests/test_t3_*.py`, `tests/test_s11_sen03_sensores_en_uso.py`, `tests/test_t17_s3*.py` |
| s4 · Interfaz QML | `src/autoclave/ui_qml/qml/**` (salvo lo ya hecho en F3), `src/autoclave/ui_qml/controllers/{parametros_ciclo,manejo_ciclos,entradas_salidas,bitacora,info_sistema}_controller.py`, `src/autoclave/ui_qml/bridge/ui_bridge.py`, `src/autoclave/ui_qml/bridge/info_equipo.py`, `src/autoclave/ui_qml/bridge/comandos_sistema.py`, `tests/test_info_equipo.py`, `tests/test_o2e_bitacora.py`, `tests/test_c9_manejo_ciclos_*.py`, `tests/test_v8a_parametros_ciclo_qml.py`, `tests/test_t17_s4*.py` |

# Tanda 16 — estado

| Etapa | Estado | Nota |
|---|---|---|
| A0 | Hecha | rama tanda-16 desde dev (f403b87); commit cbb96ba; base 7922 recolectadas, 1 falla preexistente (base_suite.txt) |
| V | Hecha | V-01..V-05 respondidas (resumen abajo; detalle en R16_informe.md) |
| F1 | Hecha | f1dc41e parámetros de equipo VCH/D-CHQ/DEU-01 (submenú Chaqueta) |
| F2 | Hecha | 3df6b1a CIC-15..18, motivos de fase, i18n de parámetros nuevos |
| F3 | Hecha | 7a74963 DebounceAcumulado, AislamientoCamara, profile.modo_vapor |
| F4 | Hecha | 41ed517, 687207c contratos del estado del ciclo |
| F5 | Hecha | d26d7cf testpaths |
| P | En curso | s1 7f364f1, s2 4125106, s3 00b0bb5 hechos; s4, s5 en curso |
| I | Pendiente | |
| R | Pendiente | |
| K | Pendiente | |
| L | Pendiente | |
| Z | Pendiente | |

Último commit: 687207c

## Resumen de V
- V-01: no existía función de perfil para chaqueta; creada `installation/profile.py::modo_vapor(profile, io_enabled=None)` (chaqueta solo con perfil real, `has_full_jacket is True` y `vapor_chaqueta`/`pres_chaqueta` en io_enabled filtrado). CicloState la evalúa en reset() → `estado.modo_vapor`.
- V-02: FALLO, cancelación y paro pasan por `ProtocoloFallo.ejecutar()` → ALL_OFF (incluye vapor_camara y vapor_chaqueta). Huecos: tolerancia DI vencida solo corta camara/chaqueta; el protocolo no reafirma vapor OFF tras el ACK; desconexión antes de COM-02 sin orden de apagado (control_loop, fuera de alcance).
- V-03: parámetros de programa en cycles/*.json + catalogo_parametros + cycle_manager.migrar_parametros; de equipo en global_params.json + ConfigManager; UI genérica.
- V-04: dobles con `cap=MagicMock()` y estado MagicMock → el modo se decide por `estado.modo_vapor == "chaqueta"` estricto; P1 afecta los programas de usuario (121/9, 134/9) y muchas pruebas que los cargan.
- V-05: constantes de presión solo usadas en catalogo_parametros._evaluar_limites; lecturas vivas en `EstadoAutoclave.update` (status.py); roles en rutas/programas.py + core/runtime/sensores_ciclo.py; NO CONFORME solo en ticket.

## Tabla de propiedad de archivos (etapa P)
Un dueño por archivo. Lo que no está aquí lo trabaja la sesión principal en I.

| Subagente | Archivos propios |
|---|---|
| s1 ESTERILIZACION | `state_machine/cycle_phases/esterilizacion.py`; pruebas `tests/test_esterilizacion_fase.py`, `tests/helpers/t12_e12_apoyo.py`, `tests/test_t12_c03_*`, `tests/test_t12_c07_debounce_*`, `tests/test_t12_c08_*`, `tests/test_t12_c13_excursion_referencia.py`, `tests/test_t12_v12_correcciones_esterilizacion.py`, `tests/test_t16_s1*.py`; `docs/informes/tanda16/i18n/s1.json` |
| s2 CALENTAMIENTO + P7 | `state_machine/cycle_phases/calentamiento.py`; `core/runtime/status.py` (solo `update()`, filtro P7); pruebas `tests/test_calentamiento_fase.py`, `tests/test_t12_c01_*`, `tests/test_t12_c02_*`, `tests/test_t12_c13_7b_ventana_*`, `tests/test_t12_v12_ventana_*`, `tests/test_t16_s2*.py`; `docs/informes/tanda16/i18n/s2.json` |
| s3 CICLO | `state_machine/states/ciclo.py`; `state_machine/cycle_phases/protocolo_fallo.py`; pruebas `tests/test_ciclo_chaqueta.py`, `tests/test_t2_p3_di_vencida.py`, `tests/test_adenda_estados.py`, `tests/test_t16_s3*.py`; `docs/informes/tanda16/i18n/s3.json` |
| s4 PROGRAMAS Y LÍMITES | `core/managers/catalogo_parametros.py`; `core/managers/cycle_manager.py`; `core/managers/gestion_programas.py`; `cycles/factory/*.json`; `cycles/user/*.json`; `backend/rutas/programas.py`; `backend/rutas/parametros_ciclo.py`; `backend/context.py`; `core/runtime/sensores_ciclo.py` (PRG-01, también la puerta de inicio vía `verificar_inicio`); `ui_qml/controllers/parametros_ciclo_controller.py`, `ui_qml/qml/Pantallas/OpcionesParametrosCiclo.qml`; pruebas `tests/test_t12_c04_*`, `tests/test_t12_c05_chaqueta.py`, `tests/test_t12_c07_c13_json.py`, `tests/test_t10_endurecimiento.py`, `tests/test_t17_copia_programa.py`, `tests/test_o1_gestion_programas.py`, `tests/test_v8a_tipo_carga_modos.py`, `tests/test_x9_d9_13_3_*`, `tests/test_q1_r1p3_*`, `tests/test_cycle_set_param.py`, `tests/test_t16_s4*.py`; `docs/informes/tanda16/i18n/s4.json` |
| s5 NO CONFORME | `backend/rutas/sistema.py` (`/status`); `backend/rutas/ciclo.py` (acknowledge y progreso); `backend/rutas/historial.py`; `backend/rutas/_comun.py`; `core/runtime/progreso_ciclo.py`; `services/domain/logging/cycle_logger.py`, `db_manager.py`, `ticket_formatter.py`; `ui_qml/qml/Pantallas/PantallaCicloEnCurso.qml`, `MenuPrincipal.qml`, `ListaCiclos.qml`, `DetalleCiclo.qml`; `ui_qml/bridge/*` y `ui_qml/domain/*` del ciclo en curso e historial; `ui_qml/bridge/acciones_ciclos.py`, `ui_qml/exportacion/*`; pruebas existentes de esos módulos y `tests/test_t16_s5*.py`; `docs/informes/tanda16/i18n/s5.json` |
| Sesión principal | `i18n/*.json`, `alarms/catalogo.py`, `core/runtime/motivos_fase.py`, `config/global_params.json`, `config_manager.py`, `limites_equipo.py`, `aislamiento_camara.py`, `debounce_acumulado.py`, `installation/profile.py`, `pyproject.toml`, `tests/test_t16_integracion.py`, docs |

# Tanda 23 — inventario (A0.3)

Hecho con grep sobre `tanda-23` en 0b92a352, sin cambiar código. Ignora `__pycache__`, `.claude/worktrees`, `dist/`, `entrega/`, `build/`.
Tamaño: 478 archivos con «tarjeta|targeta» en `src/`, `tools/`, `packaging/` y `tests/` (≈7500 apariciones).

## (a) Nombres persistidos con «tarjeta» (MES-03.2: NO se renombran)

| Nombre | Dónde se escribe | Almacén |
|---|---|---|
| `TARJETA_SIN_TRAMA_VALIDA`, `TARJETA_VERSION_INCOMPATIBLE`, `TARJETA_SIN_ACK`, `TARJETA_ALL_OFF_SIN_CONFIRMAR`, `TARJETA_SALIDAS_NO_APAGADAS`, `TARJETA_EXPANSOR_FUERA_DE_LINEA`, `TARJETA_WATCHDOG`, `TARJETA_REINICIO`, `TARJETA_CONFIG_SEGURIDAD`, `TARJETA_MODULOS_ORDEN` (+ `CODIGOS_TARJETA`, la tupla que los agrupa) | `state_machine/alarms/catalogo.py` | SQLite: historial de alarmas (`HistorialAlarmas`, código), `audit_log`, ticket/respaldo de ciclo (alarmas del ciclo). MES-03.1 |
| `TARJETA_DESCONECTADA`, `TARJETA_SIN_DATOS` | `ui_qml/qml/Componentes/SeccionEstadoSeguro.qml` (`idAlarma` de filas sintéticas) | No se guardan, pero tienen la forma de código `TARJETA_*`: se tratan como códigos (MES-03.1) y se muestran con `codigo_visible()` |
| evento `tarjeta_conectada` | `backend/context.py` `_al_conectar_tarjeta` → `db.registrar_auditoria`; listado en `core/runtime/bitacora.py` (l. 77 y 127, categorías) | SQLite `audit_log.evento` |
| entidad `tarjeta_es` | `backend/context.py` (misma fila) | SQLite `audit_log.entidad` |
| clave de detalle `tarjeta_conectada` del evento `apagar_equipo` | `backend/rutas/apagado.py:187` | SQLite `audit_log.detalle` (JSON) |
| `board_id` (perfil de instalación; no dice «tarjeta» pero es el ID del módulo) | `installation/profile.py` | `installation_profile.json` en `datos\` |
| `ConnectivityTicket` subsistema `"TARJETA"` (clave interna, no persistida) | `devices/printer/connectivity_ticket.py`, `control_loop.py:998/1024` | No persistida: se puede renombrar la clave; el texto impreso cambia |

No se encontró «tarjeta» en esquemas SQLite (`sqlite_master` de `data/autoclave.db`), en claves de `config/*.json` ni en claves del registro de Windows (`Paso08`, `Adaptador08`, `RutaPrograma`, `RutaDatos`). `config/instances/ACV-2026-001.yaml` solo la tiene en comentarios. Campos en memoria (no persistidos, sí se renombran): `estado.sin_datos_tarjeta_s`, `/status.tarjeta`, `/status.estado_tarjeta`, `id_tarjeta` de `/system/info`, `EnlaceES.tarjeta` (miembro de `MIEMBROS_ENLACE`), `tarjeta_st` del diagnóstico.

## (b) «Tarjeta» como recuadro de interfaz (MES-03.3: NO se renombran)

Componentes: `Componentes/TarjetaMenu.qml`, `TarjetaContenido.qml`, `TarjetaResumen.qml`, `OpcionTarjeta.qml`; componentes en línea `TarjetaCanal` (`OpcionesEntradasSalidas.qml`), `TarjetaGrupo` (`OpcionesParametrosEquipo.qml`, `objectName: "tarjeta_" + grupo`), `TarjetaSensor`.
Propiedades y objectName de recuadros: `fondoTarjeta`, `bordeTarjeta`, `altoTarjeta`, `aroTarjeta`, `tarjetas`, `tarjetaSalida`, `tarjetaEntrada`, `tarjetaSensor`, `tarjetaValor`, `valorTarjeta`, `tituloTarjeta`, `descripcionTarjeta`, `tarjetaPrincipal`, `tarjetaContenido`, `tarjetaOpciones`, `tarjetaVentana`, `tarjetaTextoLargo`, `tarjetaSeguridadCiclo`, `tarjetaSecado*`, `tarjetaReportes`, `tarjetaPresionada`, `tarjetaPreciclo`, `tarjetaPanelFinCiclo`, `tarjetaNuevoUsuario`, `tarjetaNormal`, `tarjetaModalConfirmacion`, `tarjetaLogin`, `tarjetaIniciarSesion`, `tarjetaInformacion`, `tarjetaHistorial`, `tarjetaDetalleAlarma`, `tarjetaDesplegable`, `tarjetaDeshabilitada`, `tarjetaCicloEnCurso`, `tarjetaCambioClave`, `tarjetaCalendario`, `relleno_tarjeta`; estilos tipográficos `tarjeta_titulo`, `tarjeta_descripcion` (`Tema/Tipografia.qml`, `TecladoProvisional.qml`); la «tarjeta Último ciclo» y demás textos de comentarios que hablan de un recuadro.
Regla para los dudosos: si el nombre describe un rectángulo/recuadro visual, se queda; si describe el estado o el hardware de E/S, se renombra.

**Sí son hardware y se renombran** (aunque estén en QML): `estadoTarjeta` (`UiBridge.estadoTarjeta`, `SeccionEstadoSeguro`, `PantallaCicloEnCurso`, `PantallaPreciclo`, `PruebaFinDeCiclo`), `tarjetaDesconectada`, `tarjetaSinDatos`, `filaTarjetaDesconectada`, `filaTarjetaSinDatos`, claves `sistema.tarjeta_desconectada[_valores]`, `sistema.tarjeta_sin_datos[_valores]`, `seguridad.tarjeta` de `UiBridge`.

## (c) Lugares donde se muestra un código de alarma (MES-04)

Todos deben pasar el código por `state_machine.alarms.catalogo.codigo_visible()` justo antes de mostrarlo (el código guardado no cambia).
- Backend `backend/rutas/sistema.py:246-283` `_alarma_dto()` (`codigo`, `id` = `CODIGO|origen`): se agrega/usa el código visible en el campo que se muestra; la clave `id` sigue siendo la guardada (la usa el reconocimiento).
- `ui_qml/bridge/ui_bridge.py:136-224` (`_normalizar_alarmas`, `AlarmListModel` roles `id`/`codigo`, `detalle()`).
- QML: `FilaAlarma.qml:43` (cae en `idAlarma`), `PanelNotificaciones.qml:53-55,165,170` (cae en `m.id`), `VentanaDetalleAlarma.qml:98-99` (cae en `datos.id`) y `:214-218` (campo «Código»), `PantallaPreciclo.qml:639` (cae en `fila.model.id`), `SeccionEstadoSeguro.qml` (`TARJETA_DESCONECTADA`, `TARJETA_SIN_DATOS` como `idAlarma`), `PanelFinCiclo.qml`/`FilaAcordeon.qml` (línea `meta`).
- `ui_qml/domain/fin_de_ciclo.py:76,157-236` (`_textos_alarma`, `_causa`, `_fila_alarma`, `_fila_observacion`; plantillas `ciclo.fin_meta_*` con `{codigo}`).
- `core/runtime/alarmas_i18n.py:179-200` `motivo_fallo()` («código · título»), usado por `ui_qml/bridge/acciones_ciclos.py:538-573` (campo Motivo del PDF, adjunto del correo).
- `services/domain/logging/ticket_formatter.py:257-273` `motivo_ticket()` («código - título»; historial 510-511 y `cycle_logger.py:558,604`).
- `state_machine/states/ciclo.py:454-459`: texto libre `motivo_fallo` guardado en la BD con el código.
- `ui_pyside/views/impresion_menu.py:58-80` (ticket de alarmas activas: «código - título» o «ID: id»).
- Sin código visible: `/alarms/history` (solo API), Reportes (causas = resultado), `devices/printer`. No hay CSV.

## (d) Usos de número de puerto con tipo "AI" que suponen rangos sin solape (AIN-R1)

- `core/runtime/asignacion_io.py`: `_PUERTOS_MODBUS`/`_OFFSET_PRES` (51-63), `etiqueta()` (155, sin grupo), `puertos_validos()` sin función (164-177, junta los dos grupos), `fabrica_codigo()` (186-189), `validar()` (286-303, un solo `ocupados` por tipo → falso conflicto), `puertos_sin_calibracion()` (306-323), `texto_error()` (355-367), `aplicar_en_memoria()` (383-387), `en_memoria()` (404-411), `responde()` (547-553).
- `core/runtime/io_names.py:38,203-219` (`_OFFSET_RAW_PRESION`, id «AI 09» de Entradas/Salidas y Calibración).
- `backend/server_reasignacion.py`: 272, auditorías con `etiqueta` (442-447, 700, 760-764), evidencias por puerto numérico «AI» (472-552; `ultimo_es_del_puerto_vigente` compara `detalle.puerto` viejo 9–16), GET `/io/assignment` (570-585; `ocupados` un solo dict para «AI»), `_largos_calibracion` (364-373), `validar_respaldo`/`restaurar_respaldo` (721-765, sin migración).
- `backend/rutas/io.py:296-297,393-395` (`puerto = index+1+(8 si presión)`), 336/373/401 (evidencias).
- `backend/rutas/respaldo.py:153-155,228-241,264-273,285,313-314`.
- `backend/context.py:378,409-413` (texto SEN-09 «f (AI 09)»), 530-537.
- `ui_qml/controllers/reasignacion_controller.py`: 25-39, `etiqueta()` 59-64, `conflictos()` 67-91 y 266-271 (por tipo «AI» → falso conflicto), 193, `puertosPara()` 206-234 (`ocupados["AI"]` común), 255-259, 284-286.
- `ui_qml/qml/Pantallas/OpcionesReasignacion.qml:233-235,318,325-327` («tipo + puerto» a mano), 390/439/453/465 (`objectName` `puerto_AI_09`, duplicable).
- `OpcionesCalibracionSensor.qml:210`, `OpcionesEntradasSalidas.qml:191`, `ui_qml/domain/entradas_salidas.py:74` (ids).
- i18n `reasignacion.conflicto`, `err_conflicto`, `err_puerto_inexistente`, `err_puerto_sin_calibracion`.
- `config/instances/ACV-2026-001.yaml:95-100,143-151` (`pres_camara: 9` …).
- Pruebas que fijan los rangos: `test_t19_s2_puertos.py`, `test_r8_asignacion_io.py`, `test_r8_reasignacion_ui.py`, `test_r8_planta_simulada.py`, `test_t22_pantallas_accion_qml.py:54`, `test_t20_s2_retiro_serial.py:132`.
- El simulador `src/autoclave/simulador` no usa `ai` ni puertos AI.

## (e) Consumidores que suponen `ai` de 16 posiciones (AIN-03)

- `protocols/modbus_link.py:98-100` (`N_PRES=8`), 270 (`[None]*16`), 720-726 (6 temp + 2 None + presión).
- `protocols/enlace.py:12-13` (contrato documentado).
- `hal/measures/units.py:51-65,95,152-166,191-193,222-229` (`_raw_ai` 16, presión ×8, `range(8)`, `raw_ai[8+i]`).
- `hal/measures/converters.py:67-68,92-95,210,300,379,406-408` (filtros ×8, `range(8)`, `raw_index = 8+i`).
- `core/runtime/io_names.py:38,212`; `core/runtime/asignacion_io.py:63,551-553`.
- `backend/rutas/sistema.py:516-531` `_cuentas_adc()` (`8+i`).
- `backend/rutas/io.py:297,395`.
- Calibración: `config/schema.py:63-69` (`range(8)`), `config/calibration_modbus.yaml` (8 de presión en fábrica y usuario), `backend/server_reasignacion.py:364-373`, `backend/rutas/respaldo.py:228-241` (`calibracion_otro_enlace` compara la fábrica: un respaldo de 8 no coincidiría con 16 → debe completarse antes de comparar).
- `core/runtime/status.py:50-55,228` (`map_pres`).
- `tests/helpers/enlace_doble.py:46,150`; `tests/helpers/m31_simulado.py:12,76,117-141,201,386,519-527`.

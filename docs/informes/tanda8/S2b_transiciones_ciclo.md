# S2b — Transiciones del ciclo (D8-2.11 a D8-2.16), tanda 8 ★

Rama `tanda-8-s2b`, desde `tanda-8` (e1d8f5e/23704cb). Fuente: `docs/mis_plans/decisiones_tanda_8.md` (D8-2.11 a D8-2.16), etapa S2 de `docs/mis_plans/instruccion_claude_code_tanda_8.md`.
La sesión se cortó una vez por el límite de uso y se reanudó (D8-2.11 a D8-2.13 ya estaban en commit).

## Qué se hizo, por punto

| Punto | Commit | Resumen | Pruebas nuevas |
|---|---|---|---|
| D8-2.11 (Q1-P1) | `86961fa` | Sin ACK del ALL_OFF al salir del modo prueba, la máquina sigue pausada y el tick reintenta 3 veces (uno por tick). Confirmado: se reanuda y se anota en la bitácora. Sin confirmar: alarma COM-04 "Salidas sin confirmar" (bloquea el inicio), se reanuda y, fuera de CICLO, se repite el handshake. COM-04 se despeja solo con un ALL_OFF confirmado o el handshake completo. | `tests/test_s2b_d8_2_11_all_off_reintentos.py` |
| D8-2.12 (Q1-P2) | `4e68fc3` | `BaseFase.pausar_ventanas_estabilidad`: al cerrar el tramo sin datos (DI vencida), `CicloState` corre las ventanas de estabilidad de la fase (sostenimiento de PRECALENTAMIENTO, hold de PRE_VACIO, ESTABLE_PREESTERILIZACION de CALENTAMIENTO, fin del SECADO). Los timeouts siguen corriendo. | `tests/test_s2b_d8_2_12_ventanas_pausa_di.py` |
| D8-2.13 (Q1-P4) | `fad9cc1` | `ControlLoop.desconexion_en_tolerancia` (enlace caído y < 5 s); `/cycle/abort` lo acepta como "cancelación en espera" (misma respuesta que R1-P5). Con paro real, resultado pendiente o tolerancia vencida, 409. | `tests/test_s2b_d8_2_13_abort_desconexion_total.py` |
| D8-2.14 (Q1-P5) | `3374723` | Columna JSON `avisos_ticket` en `ciclos` (**migración v10**) con `{"sin_datos_s", "avisos"}`; se escribe al cerrar el ciclo en la base y en el respaldo JSONL (también al reimportar). `format_ticket` la lee y reimprime además el `F0 total` (`f0_final`). Vacía, ausente o dañada: se reimprime como antes, nunca lanza. | `tests/test_s2b_d8_2_14_avisos_ticket_bd.py` (+3 pruebas existentes pasan de v9 a v10) |
| D8-2.15 (Q1-P6) | `c237d14` | `abort_cycle` devuelve la respuesta; `ComandosCicloEnCurso.aviso` lleva la clave `ciclo.cancelacion_en_espera_datos` y la pantalla de ciclo abre el aviso con ese texto. `reconocer_alarma` traduce el código HTTP a una clave del catálogo (`notificaciones.despejar_sin_enlace/no_activa/rechazado/sin_respuesta`); `ComandosSistema.mensajeDespejar` (separado del mensaje de apagar, que antes lo mostraba como "apagado rechazado: 409 Client Error…") sale en el panel de notificaciones y se borra al cerrarlo. | `tests/test_s2b_d8_2_15_textos_catalogo_qml.py` |
| D8-2.16 (Q1-P7) | `acd497e` | Recuadro rojo "CARGA NO ESTÉRIL" / "LOAD NOT STERILE" sobre la gráfica de la pantalla de ciclo cuando el ciclo terminó y el resultado no es "exitoso" (desconocido también: falla segura). PROVISIONAL, sin mockup. | `tests/test_s2b_d8_2_16_carga_no_esteril_qml.py` |
| Ensayo ★ | `6e25c83` | Planta simulada de E1 en los 4 programas. Tabla: `docs/informes/tanda8/S2b_ensayo_tabla.md`. | `tests/test_s2b_ensayo_simulador.py` |
| Banco y riesgos | `1436ad7` | Hoja de banco: B-12, C-08, F-12, F-13, F-14, F-15 (regenerados `.md`/`.html`). Registro de riesgos: HAZ-S2B-01 a 06. | — |
| Revisión ★ | `eaeda33`, `ccc459e` | Correcciones de los revisores y de la re-revisión. | `tests/test_s2b_revision_correcciones.py` |

## Ensayo con la planta simulada (4 programas)

Tabla completa en `S2b_ensayo_tabla.md` (`S2B_ESCRIBIR_INFORME=1`). Resumen:
- **D8-2.12 + D8-2.14:** 3 s de DI vencida dentro de la ventana de PRE_VACIO, CALENTAMIENTO y SECADO: la ventana se corre exactamente 3,0 s, sin vapor durante la tolerancia, el ciclo termina COMPLETADO, el ticket dice "Sin datos de la tarjeta: 3 s" y el pie reimpreso desde un `DbManager` real es idéntico al impreso en vivo. Líquidos (programa 4) no abre ventana de PRE_VACIO ni de SECADO: esas dos celdas no aplican. El sostenimiento de PRECALENTAMIENTO no está en la planta (el ciclo arranca en PRE_VACIO); queda cubierto por la prueba unitaria.
- **D8-2.13:** tarjeta caída 3 s en ESTERILIZACION con la cancelación pedida al segundo 1: CANCELADO al volver los datos. Caída de 6 s sin cancelar: FALLO_CONEXION (COM-02). En los 4 programas.
- **D8-2.16:** CANCELADO y FALLO_CONEXION marcan "CARGA NO ESTÉRIL" en pantalla y ticket; COMPLETADO no.
- D8-2.11 y D8-2.15 no dependen del programa ni de la planta: sus pruebas propias.

## Revisión ★ (safety-reviewer y timing-auditor, en paralelo)

Lanzados con la herramienta Agent sobre `git diff tanda-8...tanda-8-s2b`. Safety: 0 Críticos/Altos, 2 Medios, 3 Bajos. Timing: 1 Alto (preexistente), 3 Medios, 7 Bajos.

Corregido (commit `eaeda33`):
- **TMG-01 (Alto, preexistente) — no se duplica.** Con la tarjeta totalmente desconectada (< 5 s) el `_tick()` vuelve antes de `state_machine.update()` y no se abría la pausa. Es D8-2.7, resuelto en la rama `tanda-8-s2a` (`3e566fa`): el ControlLoop marca el tramo sin datos y `CicloState` lo une con la tolerancia de DI y lo cierra en `_cerrar_pausa_sin_datos`. En esta rama ese mismo método llama a `pausar_ventanas_estabilidad` (D8-2.12) y suma los segundos a `sin_datos_tarjeta_s` (pie del ticket, que D8-2.14 guarda en la base). **A integrar tras unir S2a:** la sesión principal debe verificar que, con las dos ramas unidas, una desconexión total breve también corre las ventanas y cuenta en el pie (la celda `d8_2_13_abort_en_desconexion` del ensayo sirve para comprobarlo añadiendo la marca de S2a).
- **SAF-01 (Medio):** `/fault/reset` se rechaza (409 `salidas_sin_confirmar`) mientras quedan reintentos del ALL_OFF; COM-04 se excluye de `resolver_todas_por_reinicio` (`DESPEJE_SOLO_POR_CONFIRMACION`); `_salidas_confirmadas` la resuelve también si el gestor la tiene activa aunque la marca local esté desfasada.
- **SAF-02 = TMG-04 (Medio):** `/cycle/start` se rechaza con el modo prueba activo (409 `modo_prueba_activo`) o con reintentos pendientes (409 `salidas_sin_confirmar`); entrar al modo prueba borra `START_CICLO` (DECISIÓN SIN CONFIRMAR).
- **TMG-02 (Medio):** el timeout de CALENTAMIENTO que vence en el sostenimiento con la ventana alargada por pausas tiene su propio motivo ("…durante el sostenimiento: la ventana de estabilidad se alargó n s por tramos sin datos de la tarjeta"), no "no se alcanzó el objetivo". PRECALENTAMIENTO lo distingue en el log (no tiene motivo de fallo propio). El cambio de la regla (alargar también el timeout) va como pregunta.
- **TMG-03 (Medio), parcial:** cada reintento espera el ACK como máximo 0,3 s (`_TIMEOUT_ACK_REINTENTO_ALL_OFF_S`, antes 1 s) bajo `_sm_lock`: cada tick retiene el lock ≤ 0,3 s más el envío de las órdenes individuales, por debajo del plazo de 0,8 s del cliente por petición (los 3 reintentos van en ticks distintos). `/status` expone `salidas_sin_confirmar_pendiente`. No se rehízo el envío sin bloqueo con verificación en el tick siguiente: tocaría `serial_link.py` (compartido) — DECISIÓN SIN CONFIRMAR. Un intento sin handshake (el enlace devuelve False en el acto, sin esperar) sigue contando: así COM-04 sale y pide el handshake, que es lo que la despeja.
- **SAF-04 (Bajo):** "CARGA NO ESTÉRIL" cierra la gráfica a pantalla completa (entra en `avisoCritico`).
- **SAF-05 = TMG-10 (Bajo):** un timeout del DESPEJAR muestra `notificaciones.despejar_sin_confirmacion` ("No se recibió la confirmación a tiempo: revise si la alarma sigue en la lista"), no "sin respuesta"; el mensaje viejo se borra al reintentar; el `emit` de `comandos_ciclo_en_curso.py` va protegido como en `comandos_sistema.py`.

Documentados sin cambio (Bajos):
- **SAF-03 = TMG-05:** en el hueco tras reconectar (enlace de vuelta, primera DI aún no vigente) `/cycle/abort` puede dar 409 falso; con S2a (D8-2.7) ese hueco también es "sin datos". Revisar al unir.
- **TMG-06:** en SECADO/PRE_VACIO el timeout del pulso se revisa antes que la presión en el mismo tick (preexistente).
- **TMG-07:** los reintentos no se ponen a 0 al reconectar; `_salidas_confirmadas` corre también desde el hilo del handshake fuera del lock (la marca es un bool; el gestor tiene su propio candado); la bitácora se escribe en un hilo daemon (como el resto de eventos de seguridad).
- **TMG-08:** dos mecanismos de pausa (exposición de ESTERILIZACION y ventanas); se cierran juntos en `_cerrar_pausa_sin_datos`.
- **TMG-09:** el hold alto de PRE_VACIO no re-verifica la presión tras la pausa (la fase la vuelve a leer en el tick siguiente).
- **TMG-11:** el historial de pendiente de CALENTAMIENTO no se corre con la pausa (el término de pendiente puede ver un salto de un tick).

### Re-revisión sobre `eaeda33` (safety y timing en paralelo)
**0 Críticos/Altos** en las dos. Confirman cerrados SAF-01, SAF-02/TMG-04, SAF-04, SAF-05/TMG-10, TMG-02 y TMG-03. Bajos nuevos, corregidos en `ccc459e`:
- `_com04_en_gestor()` contaba también una COM-04 en RESUELTA_SIN_RECONOCER (registros falsos de "COM-04 despejada" en la bitácora): ahora exige ACTIVA.
- `_ventana_pausada_s` no volvía a 0 al reabrir la ventana tras salir de banda (motivo de timeout engañoso): se pone a 0 al abrir cada ventana nueva (CALENTAMIENTO y PRECALENTAMIENTO).
- Borrar un `START_CICLO` pendiente al entrar al modo prueba no dejaba rastro: ahora queda en el log y en la bitácora (`inicio_descartado_por_modo_prueba`).

Bajos documentados sin cambio:
- El plazo de 0,3 s está fijo y no sigue a `all_off_timeout_s` de `serial_link.json`; con una tarjeta lenta daría COM-04 falsa (resultado seguro: todo apagado y bloqueo de inicio). Un "OK ALL_OFF" tardío podría tomarse como respuesta del reintento siguiente (`_expected_ack` se limpia fuera de `_cmd_lock`, preexistente). Ver pregunta 8.
- `exit_test_mode` sigue esperando 1 s bajo `_sm_lock` (preexistente).
- El timeout de PRECALENTAMIENTO no deja `motivo_fallo` (preexistente; solo log).
- `ConnectTimeout` también cae en "no se recibió la confirmación a tiempo" (más pesimista de lo necesario).

**Altos/Críticos abiertos: ninguno** (TMG-01 del primer timing es D8-2.7 de S2a; ver arriba).

## DECISIONES SIN CONFIRMAR
1. D8-2.12: el fin del SECADO se pausa como ventana (no es un timeout, es la duración del secado).
2. D8-2.15: el rechazo de DESPEJAR se traduce en el cliente por código HTTP (409 sin enlace, 404 ya no activa, sin respuesta, timeout, otro), sin tocar el backend.
3. D8-2.16: el recuadro va sobre la gráfica (diseño provisional); solo en la pantalla de ciclo, no en el detalle del último ciclo del menú.
4. Revisión: `/cycle/start` se rechaza con el modo prueba activo; entrar al modo prueba borra `START_CICLO`.
5. Revisión TMG-03: plazo corto del ACK en lugar del envío sin bloqueo.

## PREGUNTAS PARA CRISTIAN
1. (TMG-02) ¿El timeout de PRECALENTAMIENTO/CALENTAMIENTO debe alargarse también lo que se pausó la ventana? Hoy no (D8-2.12 dice que los timeouts siguen); solo cambia el motivo.
2. (Safety) ¿`timeout_pulso` del SECADO debe correrse con la pausa? Hoy no (es un timeout).
3. (Safety) ¿Se permite entrar al modo prueba desde FALLA? Hoy sí (preexistente); con COM-04 activa también.
4. (Safety/Timing) ¿El handshake debe seguir siendo la segunda barrera de D8-2.11 (fuera de CICLO)? ¿Qué hace el firmware ante un ALL_OFF cuyo ACK se pierde?
5. (Timing) En la tolerancia por DI vencida solo se cortan los vapores (cámara y chaqueta); ¿se deben cortar más salidas?
6. (Timing) Los avisos de uniformidad se guardan como texto ya formateado en español: la reimpresión en inglés los muestra en español. ¿Guardar los datos crudos y formatear al imprimir?
7. (Timing TMG-04) ¿Limpiar `START_CICLO` en PREPARADO cuando `listo=False`? Es un cambio de transición: no se hizo.
8. (Re-revisión) ¿Cuánto tarda la tarjeta en responder "OK ALL_OFF" con el expansor? Medir en banco (B-12): si pasa de 0,3 s, el plazo del reintento debe subir o seguir a `all_off_timeout_s`.
9. (Re-revisión) Ratificar el borrado de `START_CICLO` al entrar al modo prueba, o preferir rechazar la entrada al modo prueba con un inicio pendiente.

## Puntos de choque al integrar
- `src/autoclave/services/domain/logging/db_manager.py`: **migración v10** (`_migracion_v10`, columna `avisos_ticket`). Si S1 o M8 usan v10, renumerar; las pruebas `test_db_audit_log.py`, `test_i4_ingles_backend.py`, `test_o1_operador_ciclo.py` y `test_s2b_d8_2_14_avisos_ticket_bd.py` comparan `ESQUEMA_VERSION == 10`.
- i18n (`es.json`/`en.json`): `alarmas.COM-04`, `ciclo.carga_no_esteril`, `ciclo.salidas_sin_confirmar_pendiente`, `notificaciones.despejar_no_activa/rechazado/sin_respuesta/sin_confirmacion` (unión de claves).
- Catálogo de alarmas: `COM_04` en `catalogo.py`; `alarm_manager.py` (`DESPEJE_SOLO_POR_CONFIRMACION`).
- QML compartidos: `Pantallas/PantallaCicloEnCurso.qml`, `Componentes/PanelNotificaciones.qml`.
- `control_loop.py`, `backend/server.py` (`/cycle/abort`, `/cycle/start`, `/fault/reset`, `/status`), `states/ciclo.py`, `base_fase.py`, `calentamiento.py`, `precalentamiento.py`, `prevacio.py`, `secado.py`, `set_io.py`, `ui_service_backend.py`, puentes `comandos_sistema.py` y `comandos_ciclo_en_curso.py`.
- Con S2a: D8-2.7 (`3e566fa`) y D8-2.12 se juntan en `CicloState._cerrar_pausa_sin_datos` (ver TMG-01).
- Hoja de banco: IDs B-12, C-08, F-12 a F-15 (renumerar si otra etapa los usó). Registro de riesgos: sección "tanda 8 — S2b".

## Pruebas
Según la instrucción del coordinador (regla 8 del brief en esta tanda), **no se corrió la suite completa**: solo las pruebas de lo tocado y de lo que lo importa, con `PYTHONPATH=<worktree>/src` y `autoclave.__file__` = `C:\Users\tecni\Documents\codigo_autoclave\.claude\worktrees\agent-a621292afc926f886\src\autoclave\__init__.py`.

- Lote de lo tocado y de lo que lo importa (148 archivos que usan `AlarmManager`, `ControlLoop`, calentamiento, `SetOutput`, `/cycle/start`, `/fault/reset`, `/status`, `reconocer_alarma`, la pantalla de ciclo y los puentes), sobre `eaeda33`: **2874 passed, 3 skipped** (10 min). `tests/test_c1_ajustes_pyside_sesion.py` se corrió aparte (**20 passed**, igual que en la base sin los cambios): dentro del lote grande el proceso de pytest se cortó en una de sus pruebas (salida 127, sin traza), interacción entre pruebas de PySide ajena a este cambio.
- i18n, todas las `test_s2b_*`, despeje manual, catálogo de alarmas y ensayo Q1: **475 passed, 2 skipped**.
- D8-2.14 (lote de 63 archivos de base, ticket y logger): **1526 passed, 1 skipped**. D8-2.15 (puentes y QML): **515 passed**; archivos que leen el catálogo: **661 passed**.
- Tras `ccc459e`: `test_s2b_revision_correcciones.py`, `test_s2b_d8_2_11_*`, `test_control_loop_test_mode.py`, `test_b8_salida_forzada_modo_prueba.py`, `test_io_test_mode_endpoints.py`: **81 passed**; pruebas de calentamiento/precalentamiento: **317 passed**; ensayo S2b: **24 passed, 1 skipped** (el escritor de la tabla).

## Pendientes
- Verificación de TMG-01 con S2a unida (ver arriba).
- Diseño visual de "CARGA NO ESTÉRIL" y del aviso de cancelación en espera (provisionales).

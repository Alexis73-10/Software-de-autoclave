# Hotfix ES: unión con la tanda 28 (6-nov-2026) — informe de los pasos 1 a 4

Prompt: `docs/mis_plans/prompt_claude_code_hotfix_es_merge.md` (decisiones D1–D6 de Cristian). Worktree `C:\Users\tecni\Documents\codigo_autoclave_hotfix_merge`, rama `hotfix-es-merge` desde `dev` (fa18324a), `git merge hotfix-estado-seguro` (d520f7ab). Los pasos 5 a 8 (revisor, merge a `dev`, compilación, CERRADO) quedan para el director. `AJUSTES.md` del repositorio principal no se tocó.

Puerta IEC 62304 (clase C): toca el fin de ciclo, el arranque, el secado tras fallo (bomba de vacío, aire atmosférico) y «NO ABRIR». Solicitud de cambio: D1–D6. Riesgos: HAZ-ES-RET-01 (residual D5), HAZ-A9-01 (sin objeto) y HAZ-SFF-01 (modificado) en `docs/riesgos/registro_riesgos.md`, sección nueva «Unión del hotfix ES con la tanda 28». Sin cambio de SOUP. Pendiente fuera del encargo: trazabilidad (REQ-64/REQ-65 siguen citando pruebas retiradas) y la hoja de banco (T28-A9-01, T28-A10-01, T28-A13-01 describen el protocolo).

## 1. Conflictos (18) y resolución

| Archivo | Resolución |
|---|---|
| `state_machine/estado_seguro.py` | Lado hotfix entero (`ConfirmacionParo`); D1. Se pierde `cortar_secado` del estado seguro (A13-M1): ya no hay secado fuera de CICLO. |
| `state_machine/state_machine.py` | Lado hotfix en los 2 bloques: sin `cortar_secado` del estado seguro y sin protocolo en el COMPLETADO no seguro (D1). |
| `services/domain/loop/control_loop.py` | Lado hotfix (`_procesar_recuperacion` sin protocolo). Se retiraron la marca persistente (A9-R1: `protocolo_fin_ciclo_en_curso`, `_programa_para_marca`, `_sincronizar_marca_estado_seguro`, paso 5a; D2) y `programa_del_ciclo` (A13-M5; D5). `recuperar_ciclo_interrumpido(programa, interrumpido=True)`: `interrumpido` solo va al log y al evento `arranque_camara_no_segura` (D2). Nuevo `_seguir_secado_tras_fallo` (eventos de bitácora del secado, D4). |
| `core/runtime/camara_segura.py` | Los dos: `_temp_alta` con valor y límite (hotfix) + `secado_pendiente` (A13-M4). Se retiró `limites()` (A10; D3). |
| `core/runtime/motivos.py` | Los dos códigos: `paro_sin_confirmar` (hotfix) y `secando_vapor_residual` (M4). |
| `backend/rutas/sistema.py` | Lado hotfix: `/status.estado_seguro` sin `en_pausa_modo_prueba` ni `motivo_pendiente` (A10; D3). |
| `ui_qml/domain/detalle_aviso.py` | Lado hotfix; además se retiraron `texto_espera`, `MOTIVO_SECANDO` y la familia `estado_seguro_espera` (D3). |
| `ui_qml/qml/Componentes/SeccionEstadoSeguro.qml` | Lado hotfix (sin fila en curso, causa ni nota de espera). |
| `i18n/es.json`, `i18n/en.json` | Lado hotfix («Confirmar paro»; sin causas); además se retiró `aviso_detalle.estado_seguro_espera.*` (D3). Se conservan `puerta.secando_vapor_residual`, `aviso_detalle.no_abrir_motivos.secando_vapor_residual` y `ticket_ciclo.secado_motivo.programa_incierto` (historial). |
| `docs/riesgos/registro_riesgos.md` | Las dos historias (A9, A13 y hotfix) + sección nueva «Unión del hotfix ES con la tanda 28» (A9 sin objeto, A13 modificado, A10 retirado) + residual D5 en HAZ-ES-RET-01. |
| `tests/test_ess07_reasignacion_reinicio.py`, `test_s9_estado_seguro_arranque.py`, `test_s9_login_y_causa_qml.py`, `test_s9_planta_simulada.py`, `test_t17_s3_esg.py`, `test_t6_arranque_seguro.py` | Lado hotfix entero (los cambios de la tanda 28 eran la causa `ciclo_interrumpido` y la marca, retiradas). |
| `tests/test_t2_p1_completado_estado_seguro.py` | Borrado (lo retiró el hotfix). |

Sin conflicto, ajustados a mano: `backend/context.py` (sin `marca_estado_seguro` ni `_programa_para_arranque_con_origen`; `_programa_para_arranque` y `_programa_del_ciclo_interrumpido` vuelven a la versión anterior a M5; `hubo_ciclo_interrumpido` conserva A9-R3 y la falla segura, solo informa), `core/runtime/marca_estado_seguro.py` (borrado), `ui_qml/bridge/ui_bridge.py` y `detalle_aviso_qml.py` (sin `es_pausa_prueba`, `es_pendiente`, `pausaPrueba`, `pendiente` ni el slot `textoEspera`), `cycle_phases/protocolo_fallo.py` (sin `programa_incierto`; `finalizar()` robusto, ver D6), `CLAUDE.md` (viñetas A9 y A13 reescritas; enlace en la sección del hotfix).

## 2. D6 (seguridad)

`StateMachine._finalizar_protocolo_ciclo` (FALLO y CANCELADO) llama a `ProtocoloFallo.finalizar()`: secado en curso → `cortado` (bomba, vacío y aire OFF), pendiente → `omitido (no_aplica)`; hecho, sin_vacio y sin_ruptura no cambian. Si el corte lanza, `finalizar()` lo atrapa, da el secado por cortado/omitido (`error`), apaga el vacío y sigue cerrando válvulas. COMPLETADO no dispara el protocolo: `secado_tras_fallo` queda None (lo pone `reset()` al iniciar el ciclo). Tras un reinicio, `EstadoAutoclave` nace con None. Nadie continúa el secado fuera de CICLO, así que M4 nunca deja «NO ABRIR» pegado. Prueba: `tests/test_hotfix_es_merge_secado.py` (8; StateMachine, CicloState y ProtocoloFallo reales): confirmar durante el secado (FALLO y CANCELADO) → cortado, salidas OFF, NO ABRIR liberado y sin bomba en 20 ticks; confirmar con pendiente → omitido; hecho se conserva; error al cortar → final; COMPLETADO → None; reinicio → None; eventos de bitácora.

`cortado` no está en la lista literal de D6 (hecho, omitido, sin_vacio, sin_ruptura), pero es un estado final (no pendiente). Ver dudas.

## 3. Pruebas

**Retiradas (archivos):** `test_t28b_a10_estado_seguro_rango.py` (todo A10, D3), `test_t28b_a9r_marca_estado_seguro.py` (marca, D2), `test_t28b_m5_programa_interrumpido.py` (M5, D5), `test_t2_p1_completado_estado_seguro.py` (ya retirado por el hotfix).

**Retiradas (funciones):**
- `test_t28b_a13_secado_tras_fallo.py`: `test_modo_prueba_lo_corta`, `test_datos_no_vigentes_lo_cortan` (los cortaba el estado seguro; en CICLO no hay modo prueba y la trama AI vencida sigue cubierta), `test_fila_de_estado_seguro_dice_secando_vapor_residual` (`texto_espera`, D3).
- `test_t28b_a13r_secado_revision.py`: `test_m1_excepcion_en_el_estado_seguro_la_atrapa_la_maquina_y_corta`, `test_b1_modo_prueba_antes_de_empezar_lo_omite`, `test_b1_datos_no_vigentes_antes_de_empezar_no_lo_omiten`, `test_b4_secado_empezado_en_ciclo_sigue_en_el_estado_seguro` (reemplazada por las de D6), `test_b4_arranque_tras_ciclo_interrumpido_arma_el_secado` (D5).
- `test_t28b_a9_arranque_sin_protocolo.py`: `test_causa_arranque_retirada_y_ciclo_interrumpido_con_texto`, `test_detalle_ald_nombra_el_ciclo_interrumpido` (causas retiradas por el hotfix) y el fixture `_marca_aislada`.
- Archivos de conflicto tomados del hotfix: pierden solo los cambios de causa de la tanda 28 (sus pruebas del protocolo ya las había retirado el hotfix; lista en `docs/informes/hotfix_estado_seguro/R_informe.md` §3).

**Ajustadas:**
- `test_t28b_a13_secado_tras_fallo.py`: el arnés `_Equipo` ya no usa `ProtocoloEstadoSeguro`; `tick()` hace lo del paso 0 de `CicloState` con el resultado pendiente (paro → `apagar_por_paro` + `cortar_secado("paro")`; si no, `protocolo.update()`) y registra eventos con `ControlLoop._seguir_secado_tras_fallo` real; nuevos `salir_de_ciclo()` y `no_abrir()`. Las aserciones del estado seguro (activo, 3 lecturas, motivo pendiente) pasan a «NO ABRIR» por `camara_segura` (M4); `test_estado_seguro_no_se_alcanza_antes_de_terminar_la_ruptura` → `test_no_abrir_hasta_terminar_la_ruptura`.
- `test_t28b_a13r_secado_revision.py`: `cortar_secado` y `lectura_ai` sobre el protocolo/estado en lugar del estado seguro.
- `test_t28b_m3_vacio_secado.py`: «no se queda colgado» = NO ABRIR liberado tras `sin_vacio`.
- `test_t28b_m4_no_abrir_secado.py`: `test_al_terminar_la_ruptura_deja_de_ser_motivo` (sin las 3 lecturas del estado seguro); sin `texto_espera`.
- `test_t28b_a9_arranque_sin_protocolo.py`: tampoco hay protocolo tras un ciclo interrumpido (`test_ciclo_interrumpido_liquido_sin_protocolo_preparacion_solo_por_la_lenta`, ventea por la lenta desde PREPARACION); por omisión se informa `interrumpido: true` sin protocolo; retención sin protocolo en los dos casos; `_recorrer` sigue hasta 3 lecturas seguras; `construir_control` pasa solo `interrumpido`; evento con `interrumpido` en lugar de `estado_seguro`.

**Nueva:** `tests/test_hotfix_es_merge_secado.py` (8, D6).

## 4. Restos (`git grep` en `src/` y `tests/`)

`git grep -n "ProtocoloEstadoSeguro\|estado_seguro\.iniciar\|_TICKS_SEGUROS\|estado_seguro_causa_\|marca_estado_seguro\|MarcaEstadoSeguro\|estado_seguro_en_curso\.json" -- src tests`:

- `src/autoclave/services/domain/loop/control_loop.py:45,558` `_TICKS_SEGUROS_OLVIDAR_CICLO`: constante de SAF-01 de T3 (olvidar el programa del último ciclo tras 3 ticks seguros), no del protocolo. Se queda.
- `src/autoclave/state_machine/estado_seguro.py:4`: comentario de cabecera que explica el retiro.
- `tests/test_hotfix_es_retiro.py:356`: prueba que exige que NO exista ninguna clave `sistema.estado_seguro_causa_*`.
- `tests/test_i18n.py:255`: comentario del retiro de la familia.
- `tests/test_t28b_a13_secado_tras_fallo.py:16`, `test_t28b_a13r_secado_revision.py:21`, `test_t28b_m3_vacio_secado.py:12`: docstrings que explican que ya no se usa.

Sin restos de `estado_seguro.iniciar`, de la marca de A9 (`marca_estado_seguro`, `MarcaEstadoSeguro`, `estado_seguro_en_curso.json`) ni de `programa_incierto` fuera de la tupla de motivos conservada para el historial (`protocolo_fallo.py:114`, comentada).

## 5. Suite

`PYTHONPATH=<worktree>\src PYTHONUTF8=1 pytest tests -n auto` (antes del commit de la unión, mismo contenido): **11209 pasan, 11 omitidas, 3 xfail, 1 roja**: `tests/test_t20_s3_setup_modbus.py::test_ejecuta_consulta_de_adaptadores_solo_lectura`, preexistente y ajena (consulta los adaptadores de red de la máquina; anotada en el informe de la tanda 28b); sola pasa (inestable en paralelo).

`test_t26_ald_detalle_alarmas.py::test_qml_tocar_no_abrir_abre_detalle_con_valor_y_limite` **pasa con `PYTHONUTF8=1`** y sigue roja sin esa variable (`stdout` None al decodificar la salida del subproceso QML: AJ28B-05, codificación de la consola). No depende de D3; queda documentada así. Sin `PYTHONUTF8=1` la suite da esa roja además de la de T20.

## 6. Dudas abiertas

1. **Confirmar durante el secado:** la confirmación del resultado sale de CICLO y corta el secado (`cortado`) o lo omite si aún no empezó. Interpreté D4 («corre dentro de CICLO, antes de salir») como dónde corre, no como que la salida espere al secado (esperar contradiría el espíritu de D6 si queda pendiente). Si Cristian quiere que el CONFIRMAR espere a un secado en curso (acotado: ≤ 300 s + 120 s), es un cambio aparte. Anotado como residual en HAZ-ES-RET-01.
2. **`cortado` como estado final:** no figura en la lista de D6, pero no es pendiente; motivo `no_aplica` en el ticket («cortado a los N s (no aplica)»). Cambiar el texto pediría una clave i18n nueva.
3. Trazabilidad (REQ-64/REQ-65) y hoja de banco (T28-A9-01, T28-A10-01, T28-A13-01) sin actualizar (fuera del encargo).
4. Un `data/estado_seguro_en_curso.json` que haya dejado una versión con la tanda 28 en un equipo queda huérfano (no se lee ni se borra).

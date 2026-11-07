# Tanda 31: informe (7-nov-2026)

Rama `tanda31` desde `dev`. Entrega NO compilada. Plan: `docs/mis_plans/planeacion_entrega_camara_fin_ciclo.md`.

## Resultado por ENT
| ENT | Resultado |
|---|---|
| ENT-01/02 | `state_machine/states/entrega_camara.py` (puro), creado por `CicloState`; entrega con `camara_segura.evaluar`, datos vigentes, sin sellado y 3 tramas AI; tras COMPLETADO, espera `tiempo_espera_apertura` y CIC-07 al pasar `timeout_temperatura`. |
| ENT-03 | `/cycle/acknowledge` sin entrega: 409 `camara_no_entregada` con el motivo, es/en. |
| ENT-04 | `forzar: true` solo ingeniero con `dependencias.reautenticar`; bitácora `ciclo_confirmado_sin_entrega`; línea en el pie. |
| ENT-05 | Con paro soltado la confirmación no espera la entrega; `estado.confirmado_tras_paro`; pie «Confirmado tras paro de emergencia, cámara sin verificar». |
| ENT-06/07 | `CycleLogger` separa resultado y cierre; filas «E» periódicas; `fecha_resultado` (migración v14); registro `resultado` del respaldo; un corte de energía conserva el resultado. |
| ENT-08 | F0 no acumula tras el resultado (verificado con prueba). |
| ENT-09 | Indicador del motivo o de la espera, CONFIRMAR con la entrega y botón forzado (`ui_qml/domain/entrega_camara.py`, `PantallaCicloEnCurso.qml`, `confirmarForzado`). |
| ENT-10 | Transcurrido y gráfica siguen hasta la entrega. |
| ENT-11 | No hay PDF ni correo automático al cierre; Historial no ofrece PDF/correo de ciclos sin `fecha_fin`. |
| ENT-12 | `progress.entrega` = `{entregada, motivos, espera_restante_s, forzable}`. |

## Pruebas
Nuevas: `tests/test_t31_entrega_camara.py`, `tests/test_t31_entrega_ticket.py`, `tests/test_t31_ent09_pantalla.py`. Ajustadas las que dependían del cierre inmediato (cycle_logger, ensayos del simulador, t15 rutas, t21, t16 no conforme, t6, t8, s3, entre otras).

Suite completa: 11519 pasan, 11 omitidas, 3 xfail, 2 fallos (12 min 30 s, `-n 8`; `suite_t31.txt`). Los dos fallos eran de entorno, no de la tanda: `test_t26_ald_detalle_alarmas::test_qml_tocar_no_abrir...` (la salida del subproceso salía en cp1252; corregido con `PYTHONIOENCODING=utf-8` y `errors="replace"`) y `test_t21_pantalla_fin_ciclo_qml::test_la_cuenta_se_detiene_con_un_modal` (intermitente bajo carga; pasa solo). Ambos archivos pasan juntos (21 passed).
Revisor: hallazgos M1, B1 y B2 corregidos en f040022a.

## Riesgos
HAZ-ENT-01..04 en `docs/riesgos/registro_riesgos.md`; HAZ-ENT-04 (ENT-05) queda con residual pendiente de Cristian. Trazabilidad REQ-76..REQ-81. Banco: bloque T31 (T31-01..06).

## DECISIÓN SIN CONFIRMAR (lista completa)
- (a) `confirmado_tras_paro` solo se marca si la cámara no estaba entregada.
- (b) Con el paro soltado la entrega no se evalúa, pero se publica.
- (c) CIC-07 en COMPLETADO solo si el motivo vigente es temperatura alta; la marca es compartida con la apertura automática.
- (d) La falta de contraseña en la confirmación forzada da 403 `reautenticacion_requerida` (no 428).
- (e) La entrega usa `camara_segura.evaluar` (falla cerrada sin configuración); la apertura automática usa valores por defecto.
- (f) «Error de ciclo» y «F0 total» van al resultado solo si no es COMPLETADO; sin motivo, la línea lleva el resultado.
- (g) La salida de CICLO sin entrega cierra el ciclo igual.
- (h) Un resultado sin entrega cuenta como interrumpido (`cerrar_ciclos_interrumpidos` y reimportación; auditoría `ciclo_completado_desde_respaldo`).
- (i) `duracion_media` cuenta transitoriamente un COMPLETADO sin entrega como excluido.
- (j) `hora_fin_pantalla` sigue siendo la hora del resultado.
- (k) Muestras de gráfica durante la espera con fase terminal y `fase_ui` None.
- (l) `ui_pyside/views/ciclos.py` no inserta «Error de ciclo».
- (m) Posición y tamaño del indicador y del botón forzado en la barra inferior: pendiente de captura y visto bueno de Cristian.
- (n) El texto del motivo sale en las unidades del backend.
- (o) El simulador publica `entrega.entregada=True`.

## No se compiló
Para compilar: `python tools/entrega/compilar_entrega.py` desde `dev` limpio.

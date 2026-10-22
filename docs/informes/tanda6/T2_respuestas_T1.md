# T2 — Respuestas de Cristian a las preguntas de T1 ★ (tanda 6)

Fuente: `instruccion_claude_code_tanda_6.md` §1.1. Matriz actualizada: `T2_matriz_actualizada.md`. Ensayo con la planta simulada de E1 en los 4 programas: `T2_ensayo_tabla.md` (`tests/test_t2_ensayo_simulador.py`: 12 casos, todos pasan).

## Qué se hizo (un commit por P, con pruebas)
| P | Cambio | Archivos | Pruebas |
|---|---|---|---|
| P-1 | Al reconocer un COMPLETADO con la cámara no segura (falla cerrada; rige el menor `temp_max_apertura`, global o del ciclo) se ejecuta el protocolo de fallo y empieza el estado seguro. Sin datos vigentes, o con paro, el protocolo no abre válvulas. | `state_machine.py` | `test_t2_p1_completado_estado_seguro.py` |
| P-2 | Principal perdido en ciclo (None **o 0**): FALLO y protocolo `solo_lenta` (sin escalar ni contrapresión, en todos los modos). CIC-10 se mantiene mientras la sonda no lea. FALLA pasa a PREPARACION sin técnico aunque el estado seguro siga activo. `/cycle/start` responde `PRINCIPAL_SIN_LECTURA` con "Sonda principal sin lectura: llame a servicio" (es/en). | `ciclo.py`, `protocolo_fallo.py`, `estado_seguro.py`, `state_machine.py`, `server.py`, i18n | `test_t2_p2_principal_perdido.py` |
| P-3 | Trama DI vencida en ciclo: tolerancia de **4 s** (WD_TIMEOUT_MS = 5000 en el `.ino` V3, menos 1 s). Durante la tolerancia: vapor de cámara y de chaqueta en OFF y la fase no corre; 3 ticks vigentes seguidos reinician la cuenta. Vencida la tolerancia: `FALLO_CONEXION` + COM-03, sin válvulas. | `ciclo.py` | `test_t2_p3_di_vencida.py` (lee el `.ino`); se ajustaron `test_t5_estado_seguro.py` y `test_u4_tarjeta_desconectada.py` |
| P-4 | PREPARADO exige `not has_blocking_alarm()`. Si la consulta falla, bloquea. | `preparado.py` | `test_t2_p4_bloquea_inicio.py` |
| P-5 | COM-02 y COM-03 no se resuelven al salir de FALLA mientras no estén reconocidas. Un reconocimiento explícito fuera de CICLO las despeja. Botón **DESPEJAR** en el panel de notificaciones (hasta ahora no había forma de reconocer una alarma desde QML). | `alarm_manager.py`, `comandos_sistema.py`, `ui_service_backend.py`, `FilaAlarma.qml`, `PanelNotificaciones.qml`, i18n | `test_t2_p5_despeje_manual_com.py` |
| P-6 | Tras un paro con el ciclo terminando, CONFIRMAR abre un diálogo con el texto de §15.2 (verificar fugas; "Confirmar y llevar a estado seguro"). Nuevo campo `/status.estado_seguro.ack_confirma_estado_seguro`. | `ciclo.py`, `server.py`, `ui_bridge.py`, `PantallaCicloEnCurso.qml`, i18n | `test_t2_p6_dialogo_estado_seguro.py` |
| P-7 | `/cycle/abort` responde 409 con `resultado_pendiente`, `paro_emergencia` o `estado_no_permitido`. Una cancelación no procesada se limpia cuando el resultado queda pendiente. | `server.py`, `ciclo.py` | `test_t2_p7_abort_409.py` |
| P-8 | Se retiran `GlobalState.EMERGENCIA` e `HIBERNACION` con sus módulos. Antes se verificó que `standby.py` y el backend no usan HIBERNACION; solo `Main.qml` tenía un manejador muerto, que se conserva. | `enum_global.py`, `state_machine.py`, `server.py`, `control_loop.py`, `standby.py`, `permisos_opciones.py`; 9 pruebas ajustadas | `test_t2_p8_estados_retirados.py` |
| P-9 | El ticket de un ciclo INTERRUMPIDO lleva "*** CARGA NO ESTÉRIL ***" / "*** LOAD NOT STERILE ***" (cp437). La reimpresión desde Historial ya funcionaba. | `ticket_formatter.py` | `test_t2_p9_reimprimir_interrumpido.py` |
| P-12 | Líquidos: el drenaje a presión atmosférica va por la lenta mientras el Principal esté por encima de `temp_max_apertura` (o sin lectura o sin configuración). La rápida solo después de 3 lecturas seguidas en o por debajo de ese valor. Una sola orden de la lenta por tick. | `preparacion.py` | `test_t2_p12_drenaje_liquidos.py`; se ajustaron `test_t1_venteo_liquidos.py` y `test_adenda_estados.py` |
| P-10, P-11 | Sin cambio. | — | — |

## Suite
Línea base: 4379/1/3. Resultados en verde después de cada grupo: P-1, 4386; P-2, 4403; P-3/4/5/9/12, 4442; P-7, 4447; P-6, 4463 (2 omitidas: los escritores de informe); P-8, ver `estado.md`. P-3, P-4, P-5, P-9 y P-12 tocan archivos distintos. Para ganar tiempo se validaron juntos en una sola corrida completa y se commitearon por separado.

## Revisores (★)
- **Primera pasada** (safety, timing y sensor-role) sobre P-1 a P-5, P-9 y P-12. **Altos corregidos:**
  - SEN-01: un 0 del Principal no contaba como sonda perdida.
  - TMG-01, TMG-02 y SAF-01: durante la tolerancia de P-3 las salidas quedaban congeladas, vapor incluido. El WD del firmware mide el enlace PC→tarjeta y no cubre este caso. Además, una DI intermitente renovaba la tolerancia.

  También se corrigieron estos Medios y Bajos:
  - TMG-06: P-12 daba ON y OFF de la lenta en un mismo tick.
  - TMG-07 y SAF-04: P-1 abría válvulas sin datos vigentes o con paro.
  - TMG-08: lock en `reconocer`.
  - SEN-02: el 0 no entraba en `bloqueado_motivo`.
- **Segunda pasada** (safety y timing) sobre todo el diff, incluidos P-6, P-7 y P-8: **sin Críticos ni Altos**.
- **Medios y Bajos abiertos** (pasan a R1):
  - SAF-02/TMG: los timers de fase siguen corriendo durante la tolerancia, incluida la exposición de ESTERILIZACION (hasta 4 s por episodio de DI vencida).
  - SAF-03: DESPEJAR no comprueba que la causa haya desaparecido. Las alarmas TARJETA_* siguen bloqueando igual.
  - SAF-05: si el protocolo ya se ejecutó por otra causa y después se pierde el Principal, no pasa a `solo_lenta`.
  - SAF-06: la marca "no estéril" solo aparece en INTERRUMPIDO.
  - SEN-03: sin `programas_seguridad`, P-12 mide el programa seleccionado.
  - `ack_confirma_estado_seguro` se lee sin lock (efecto solo cosmético).
  - Durante la tolerancia no se tocan las salidas de escape ni de vacío.
  - El texto del 409 de abort durante la tolerancia no corresponde a la situación.
  - Quedan el alias `DISTINTO_DE_CICLO_E_HIBERNACION`, el docstring de `control_loop` y el manejador muerto en `Main.qml`.

## DECISIONES SIN CONFIRMAR
- **T2-1 (P-3):** tolerancia de 4 s y no de 5 s. El WD es de 5 s exactos y se dejó 1 s de margen. Ese WD vigila líneas PC→tarjeta: con la DI vencida el PC sigue enviando y el WD no apaga nada. Por eso se corta el vapor durante la tolerancia. Alternativa: 5 s. Para revertir: `_TOLERANCIA_DI_VENCIDA_SEG`.
- **T2-2 (P-3):** durante la tolerancia la fase no corre y se cortan el vapor de cámara y el de chaqueta; 3 ticks vigentes reinician la cuenta. Alternativa: dejar correr la fase solo con las entradas analógicas.
- **T2-3 (P-5):** "despeje manual" se implementó como reconocimiento explícito por alarma, con un botón DESPEJAR nuevo (usuario "operador", sin rol). Sin ese botón, P-4 dejaba el equipo bloqueado sin salida desde QML. Alternativas: exigir sesión, o despejar al volver el enlace.
- **T2-4 (P-2):** un 0 de un sensor de temperatura en uso cuenta como sin lectura (antes solo None o no finito), igual que en `estado_sensor` y `temp_seguridad`.
- **T2-5 (P-12):** para usar la rápida se exigen 3 lecturas seguidas en o por debajo de `temp_max_apertura` (el menor entre el global y los de los programas). Si el `temp_max_apertura` global no está configurado, siempre va por la lenta.
- **T2-6 (P-8):** se conservan el nombre `DISTINTO_DE_CICLO_E_HIBERNACION` (alias de `DISTINTO_DE_CICLO`) y el manejador muerto de HIBERNACION en `Main.qml`.
- **T2-7 (P-9):** la marca va en el pie del ticket solo para INTERRUMPIDO.

## PREGUNTAS PARA CRISTIAN
- ¿Pueden contar como tiempo de exposición en ESTERILIZACION los segundos de tolerancia por DI vencida (hasta 4 s, con el vapor cortado)? ¿O hay que pausar el timer o marcar el ticket?
- ¿El DESPEJAR de COM-02/03 debe exigir que el enlace vuelva a "ok", o una sesión?
- ¿La marca "CARGA NO ESTÉRIL" también para FALLO, CANCELADO y EMERGENCIA?
- P-10: verificar en banco (C-05) qué botón ofrece la UI al arrancar con la cámara no segura.

## Comprobaciones manuales (banco)
- **P-1:** reconocer un COMPLETADO con la cámara caliente. Debe mostrar NO ABRIR y pasar a PREPARADO con el estado seguro activo.
- **P-2:** desconectar el Principal en esterilización. Debe ventear solo por la lenta, pasar de FALLA a PREPARACION con el reconocimiento y mostrar el mensaje al intentar iniciar.
- **P-3:** dejar sin DI (cable o firmware). Debe esperar 4 s y terminar en FALLO_CONEXION.
- **P-5:** probar DESPEJAR en el panel.
- **P-6:** comprobar que aparece el diálogo después de soltar el paro.
- **P-12:** líquidos con agua en la cámara caliente. Debe drenar por la lenta y hay que verificar que el agua sale.

## Otras notas
- Durante la etapa aparecieron cambios ajenos en la rama: el commit `74af54f` (W1, de otra sesión) y `docs/mis_plans/planeacion_mantenimiento.md` sin versionar. No los toqué.
- Las traducciones nuevas al inglés (`ciclo.principal_sin_lectura`, `ciclo.confirmar_estado_seguro_texto`, `notificaciones.despejar`) quedan marcadas como "sin revisar".

# T2 — Matriz de transiciones actualizada (tanda 6) ★

Copia de `docs/informes/tanda5/T1_matriz_transiciones.md` con las respuestas de Cristian a P-1…P-12 (instrucción de la tanda 6, §1.1) aplicadas en T2. Las celdas cambiadas llevan **[T2 P-n]**. Informe: `T2_respuestas_T1.md`. Ensayo con la planta simulada de E1 en los 4 programas: `T2_ensayo_tabla.md` (`tests/test_t2_ensayo_simulador.py`).

---

# (original T1, actualizada) Matriz de transiciones de ciclo

La matriz se construyó leyendo el código, no la documentación. Se comparó con `planeacion_fin_de_ciclo_y_puertas.md` (v3 y sus adendas) y con las decisiones de la memoria del proyecto. Regla aplicada (regla 4, excepción T1): solo se corrige lo que la spec dice de forma explícita y es inseguro; lo ambiguo queda como **PREGUNTA PARA CRISTIAN**.

Abreviaturas de archivos (bajo `src/autoclave/`):

| Sigla | Archivo |
|---|---|
| SM | `state_machine/state_machine.py` |
| CS | `state_machine/states/ciclo.py` |
| ES | `state_machine/estado_seguro.py` |
| CL | `services/domain/loop/control_loop.py` |
| SRV | `backend/server.py` |
| CTX | `backend/context.py` |
| PF | `cycle_phases/protocolo_fallo.py` |
| CLG | `services/domain/logging/cycle_logger.py` |
| CAT | `alarms/catalogo.py` |

## Reglas comunes
- **Confirmación de fin de ciclo.** Todo fin de ciclo (COMPLETADO, FALLO o CANCELADO) deja el resultado pendiente y la máquina sigue en CICLO hasta que el operador confirma con `/cycle/acknowledge`. La confirmación no pide sesión (CS:483-537, SRV:1916-1950). Si el resultado es un fallo, esa misma confirmación cuenta como reconocimiento de la falla (SRV:1945-1949).
- **BD y ticket.** Se cierran en cuanto la fase deja de estar en curso, sin esperar la confirmación (CLG:246-253). Queda guardado el resultado, el motivo, el código de fallo y el F0.
- **Protocolo de fallo.** Envía ALL_OFF y abre la válvula según la presión de la cámara. Con el paro activo (`abrir_valvulas=False`) solo envía ALL_OFF (PF:137-181).
- **Estado seguro (ES).** Al salir de CICLO por FALLO o CANCELADO, ES continúa el protocolo fuera de CICLO. Termina tras 3 ticks seguidos con la cámara segura y audita cada paso (SM:155/160, ES:200-209).
- **"NO ABRIR".** Se publica como `no_abrir = not camara_segura` en cualquier estado y falla cerrado (SRV:923-934, `camara_segura.py:43-67`).
- **Nuevo ciclo.** Solo se puede iniciar desde PREPARADO con todo listo. No se puede con la cámara no segura, con ES activo, con la puerta abierta, con el paro activo ni con sensores del programa fuera de servicio.

## Matriz

| Estado · Evento | Destino | Salidas | Alarma/UI | NO ABRIR | Bloquea nuevo ciclo | BD/ticket | Confirmación |
|---|---|---|---|---|---|---|---|
| PREPARACION · condiciones OK | PREPARADO | lazos de chaqueta, presión y drenaje | se resuelven PRE/SUM/SEN | según la cámara | — | — | no |
| PREPARADO · inicio | CICLO | fases | — | según la cámara | rechazo si no está listo, si el programa está dañado, si es de líquidos sin capacidad o si faltan sensores | apertura del ciclo | no |
| CICLO · fin normal | resultado pendiente COMPLETADO → (ack) PREPARADO; **con la cámara no segura, + ES [T2 P-1]** | válvula de reposo, drenaje; **tras el ack con cámara no segura: protocolo de fallo (sin válvulas si no hay datos vigentes o hay paro) → ES [T2 P-1]** | CIC-07/08 (avisos) | sí, hasta cámara segura | **sí, hasta cámara segura [T2 P-1]** | `COMPLETADO` | ack |
| CICLO · cancelación | pendiente CANCELADO → (ack) PREPARADO + ES | protocolo de fallo → ES | — | sí | sí, mientras ES actúe | `CANCELADO`, motivo vacío | ack |
| CICLO · fallo de fase (las 6 fases) | pendiente FALLO → (ack) FALLA | protocolo de fallo → ES | CIC-01…06 | sí | sí | `FALLO_<FASE>` + motivo | ack = reconocimiento |
| CICLO · paro pulsado | pendiente FALLO | ALL_OFF sin válvulas | SIS-01 | sí | sí | `EMERGENCIA` + SIS-01 | ack rechazado mientras dure el paro |
| CICLO · paro soltado | sigue pendiente, sin movimiento | todo en 0 | **diálogo con el texto de §15.2 antes del CONFIRMAR [T2 P-6]** | sí | sí | — | ack → FALLA/PREPARADO; ES arranca sin otra confirmación |
| CICLO · fallo de suministro eléctrico | pendiente FALLO | protocolo de fallo | SUM-01 | sí | sí | `FALLO_SUMINISTRO` | ack |
| CICLO · corte de energía / reinicio del PC | al arrancar, PREPARACION; **no se reanuda** | con la cámara no segura: ALL_OFF + ES con confirmación | CIC-10 si ES no puede terminar | sí, también con el Principal del ciclo interrumpido | sí | `INTERRUMPIDO` + "la carga NO está estéril" | `/safe-state/confirm` |
| CICLO · tarjeta desconectada (más de 5 s) | pendiente FALLO | ALL_OFF sin válvulas (puede quedar sin ACK) | COM-01/COM-02 | sí | sí | `FALLO_CONEXION` | ack tras reconectar |
| CICLO · trama DI vencida con el enlace activo | **tolerancia 4 s (WD firmware 5 s − 1 s); dentro: vapor de cámara y chaqueta OFF y la fase no corre; 3 ticks vigentes reinician; pasada: pendiente FALLO [T2 P-3]** | ALL_OFF sin válvulas | COM-03 (**despeje manual [T2 P-5]**) | sí | sí | **`FALLO_CONEXION` [T2 P-3]** | ack |
| CICLO · lectura None de un sensor en uso o de la presión | pendiente FALLO | protocolo de fallo | SEN-02 | sí | sí | `SENSOR_AUSENTE` | ack |
| CICLO · sensor Principal perdido (None o 0) | pendiente FALLO → (ack) FALLA → **PREPARACION sin técnico aunque ES siga [T2 P-2]** | **protocolo solo por la LENTA, sin escalar ni contrapresión, en todos los modos [T2 P-2]** | SEN-02; CIC-10 mientras no lea | sí | sí; **`/cycle/start` → PRINCIPAL_SIN_LECTURA "Sonda principal sin lectura: llame a servicio" [T2 P-2]** | `SENSOR_AUSENTE` | ack; ES se libera por los caminos de CIC-10 |
| CICLO · evento de la tarjeta (WD, reinicio, expansor) | FALLO | protocolo de fallo (respeta el paro) | COM-03 | sí | sí | `FALLO_IO` | ack |
| CICLO · puerta abierta o empaque bajo | pendiente FALLO | protocolo de fallo | PUE-02/03 | sí | sí | `FALLO_PUERTA_n_*` | ack |
| CICLO · caducidad de sesión | sin consecuencia (el control no depende del token) | — | — | — | — | — | — |
| CICLO · apagado pedido | 409 | — | — | — | — | — | — |
| CICLO · cambio de programa | rechazado y auditado | — | — | — | — | — | — |
| FALLA · reconocimiento | PREPARACION cuando ES terminó (**o de inmediato si es el ES del Principal perdido [T2 P-2]**) | ES continúa | **COM-02/COM-03 siguen activas hasta DESPEJAR [T2 P-5]** | sí | sí (**COM-02/03 bloquean el inicio, P-4**) | audit `falla_reconocida` | sin rol |
| FALLA · paro | se queda en FALLA, ES en pausa | ALL_OFF continuo | SIS-01 | sí | sí | audit | se descarta el reset hecho durante el paro |
| FALLA / PREPARADO con ES · paro soltado | se mantiene | todo en 0 | — | sí | sí | audit | `/fault/reset` o `/safe-state/confirm` |
| PREPARACION / PREPARADO · paro | se mantiene | ALL_OFF continuo | SIS-01 | — | sí | — | al soltarlo sigue sola |
| PREPARADO · alarma activa con `bloquea_inicio` | no queda listo **[T2 P-4]** | lazos normales | la alarma | según la cámara | **sí [T2 P-4]** | — | — |
| PREPARACION · agua residual con carga líquida | drena **por la LENTA mientras Principal > temp_max_apertura o sin lectura; rápida tras 3 lecturas frías [T2 P-12]** | lenta / rápida | PRE-05 | según la cámara | sí | — | — |
| CICLO · `/cycle/abort` con resultado pendiente o paro | **409 `resultado_pendiente` / `paro_emergencia`, sin dejar el indicador [T2 P-7]** | — | — | — | — | — | — |
| Historial · reimprimir INTERRUMPIDO | **ticket con "*** CARGA NO ESTÉRIL ***" [T2 P-9]** | — | — | — | — | — | — |
| Estados HIBERNACION / EMERGENCIA | **retirados (inalcanzables) [T2 P-8]** | — | — | — | — | — | — |
| Fuera de CICLO · tarjeta desconectada | la SM no corre | sin órdenes (queda el watchdog del firmware) | COM-01 | sí | sí | — | — |
| Fuera de CICLO · apagado | lazo detenido + ALL_OFF | — | — | — | — | audit | la de la UI; rechazado si ES actúa |
| PREPARACION / PREPARADO / FALLA · cambio de programa | SM reconstruida | — | — | — | rechazado con paro, ES, recuperación, modo prueba o apagado | audit | sin sesión |
| Modo prueba | SM en pausa | ALL_OFF al entrar y al salir | — | — | rechazado en CICLO | audit | lo cierran el paro, la sesión del dueño y la salida de la ventana (P1) |

Pruebas que ejecutan estas celdas con la planta simulada en los 4 programas: `tests/test_e1_ensayo_simulador.py` (completo, cancelación, paro, pérdida de tarjeta, corte y reinicio) y `tests/test_t11_programas_integracion.py`. Las celdas de fallo de fase, puerta, sensor y suministro tienen sus propias pruebas de estado (`test_e2*`, `test_e3*`, `test_e1_puertas_perfil.py`, `test_t3_sensores_ciclo.py`). **No se agregó una prueba parametrizada que recorra toda la matriz:** queda PENDIENTE por tiempo.

## Las dos reglas
1. **Ningún fallo exige técnico para reiniciar.** Se cumple: `/fault/reset`, el ack, `/safe-state/confirm` y `/cycle/select` no piden rol. Hay una excepción práctica, P-2.
2. **Tras un corte en ciclo no se reanuda.** Se cumple: el ciclo queda `INTERRUMPIDO`, el equipo arranca en seguro y, si la cámara no es segura, se exige confirmación. Si el corte ocurre después de COMPLETADO y antes del ack, el ciclo ya figura como COMPLETADO (intencional, PF-17).

## Corregido (la spec es explícita y el comportamiento era inseguro)
**T1-01: venteo con la descompresión rápida en carga líquida.** D-19: "la descompresión rápida […] en líquidos nunca". Después del ack de un ciclo COMPLETADO no hay estado seguro. Si la cámara seguía presurizada, PREPARADO (`mantener_presion_camara`) y PREPARACION (`ejecutor`) ventilaban con la **rápida** sin mirar el tipo de carga, con riesgo de ebullición súbita del líquido.

Ahora, si el programa seleccionado **o el del último ciclo** es de carga líquida, ventean con la **lenta**. Un error al leer los programas cuenta como líquido (falla segura). Archivos: `state_machine/states/control_banda.py` (`carga_liquida`, `ventear`), `preparado.py`, `preparacion.py` y `state_machine.py`, que pasa `programas_seguridad` a PREPARACION. Prueba: `tests/test_t1_venteo_liquidos.py`.

## Estado de las preguntas tras T2
| P | Respuesta de Cristian (tanda 6 §1.1) | Estado |
|---|---|---|
| P-1 | Estado seguro tras COMPLETADO con cámara no segura | **Resuelta** |
| P-2 | Principal perdido: falla, lenta, PREPARACION sin técnico, inicio bloqueado | **Resuelta** |
| P-3 | Tolerancia DI ≤ WD − 1 s, fallo de comunicación | **Resuelta** (4 s) |
| P-4 | PREPARADO consulta has_blocking_alarm() | **Resuelta** |
| P-5 | COM-02/03 despeje manual | **Resuelta** |
| P-6 | Texto de §15.2 en el diálogo | **Resuelta** |
| P-7 | /cycle/abort 409 | **Resuelta** |
| P-8 | Retirar HIBERNACION y EMERGENCIA | **Resuelta** |
| P-9 | Reimpresión de INTERRUMPIDO | **Resuelta** |
| P-10 | Prueba de banco C-05 | Sin cambio |
| P-11 | — | Sin cambio |
| P-12 | Drenaje de líquidos por la lenta | **Resuelta** |

## (original T1) PREGUNTAS PARA CRISTIAN
- **P-1:** el ack manual de un ciclo COMPLETADO no exige cámara segura, y después del ack no hay estado seguro (pasa directo a PREPARADO). Hoy protegen "NO ABRIR" y el bloqueo de inicio (PF-06). *Recomendación:* tras COMPLETADO con la cámara no segura, entrar también al protocolo de estado seguro (el modo de descompresión del programa), igual que en cancelación y fallo.
- **P-2:** si ES se bloquea porque el sensor Principal no lee durante el enfriamiento de los modos 4/5 (CIC-10), la única salida que ofrece la UI es reasignar la sonda, que exige técnico o ingeniero. Esto contradice D-06 en la práctica. *Recomendación:* ofrecer al operador "continuar con la referencia" o "ventear con la lenta", con confirmación y auditoría.
- **P-3:** una trama DI vencida con el enlace activo aborta el ciclo de inmediato por la rama del paro y queda registrado como `EMERGENCIA`. La desconexión total, en cambio, tiene 5 s de tolerancia. *Recomendación:* misma tolerancia (5 s) y registrar `FALLO_CONEXION`/COM-03, no EMERGENCIA.
- **P-4:** el campo `bloquea_inicio` del catálogo de alarmas no se consulta en ningún lugar. Por ejemplo, TARJETA_WATCHDOG fuera de ciclo no impide iniciar. *Recomendación:* que PREPARADO consulte `has_blocking_alarm()`.
- **P-5:** al salir de FALLA, `resolver_todas_por_reinicio` resuelve también COM-02 y COM-03, cuyo comentario dice "no se despeja sola". *Recomendación:* no resolver por reinicio las alarmas de despeje manual.
- **P-6:** tras un paro en CICLO, el ack hace a la vez de "Confirmar y llevar a estado seguro" (§15.2). No hay un paso explícito de verificación de fugas. *Recomendación:* mantener la fusión; mostrar en el diálogo del ack el texto de §15.2.
- **P-7:** `/cycle/abort` responde "ok" aunque el resultado ya esté pendiente o haya paro, sin efecto, y el indicador queda puesto hasta el siguiente ciclo. *Recomendación:* responder 409 en esos casos y limpiar el indicador.
- **P-8:** HIBERNACION y EMERGENCIA son estados inalcanzables (PF-07). *Recomendación:* retirarlos o marcarlos como reservados.
- **P-9:** no existe reimpresión del ticket de un ciclo INTERRUMPIDO. *Recomendación:* permitirla desde Historial con la marca "carga NO estéril".
- **P-10:** al arrancar con la cámara no segura solo sirve `/safe-state/confirm`; `/fault/reset` devuelve 409. Hay que verificar en el equipo que la UI ofrezca el botón correcto (H1).
- **P-11:** la cancelación vuelve a PREPARADO (D-05) y PREPARADO nunca vuelve a PREPARACION aunque se degrade. Coincide con la spec; se anota por si se quiere revisar.

- **P-12 (nueva, de la revisión):** en carga líquida, el drenaje de agua residual con la cámara ya a presión atmosférica sigue usando la **rápida**. D-19 no aclara si aplica sin sobrepresión, y no se sabe si la lenta drena agua con eficacia. *Recomendación:* confirmar en el equipo. Si la rápida también es peligrosa con líquido caliente a presión atmosférica, cambiarla por la lenta y verificar que el agua sale.

## Revisores (T1-01)
- **safety-reviewer:** sin Críticos ni Altos. Los Medios (la lenta se apaga y se vuelve a encender en el mismo tick; el drenaje de líquidos pasaba por la lenta; pruebas débiles) y los Bajos (lenta abierta al bajar de la banda; lista de programas vacía) están **corregidos**. El drenaje quedó como pregunta P-12.
- **timing-auditor:** **Alto T1-01-A** (órdenes OFF y ON de la lenta en el mismo tick): **corregido**. Ahora hay una sola decisión de venteo por tick (`aplicar_venteo`). `igualar_presion_camara` ya no toca la lenta, y la válvula contraria se cierra siempre. Los Medios T1-01-B (lenta abierta en la rama baja o sin dato) y los Bajos T1-01-D (cambio de veredicto) y T1-01-E (log en cada tick, ahora se registra una sola vez) están **corregidos**. **PENDIENTE** el Medio T1-01-C: `mantener_presion_camara` corre dos veces por tick en PREPARADO. Es anterior a T1, viene de `esta_preparado()`, y hace que el debounce del aire avance de a 2. Las órdenes repetidas son idempotentes.
- **sensor-role-auditor:** la fuente de "carga líquida" (`globals.tipo_carga`) es la correcta y única. SEN-01/SEN-03 (campo ausente o lista vacía contaban como sólido) están **corregidos**: ahora cuentan como líquido, igual que la recuperación de arranque. Todos los perfiles traen `tipo_carga`. SEN-02 (lógica duplicada con `_carga_liquida` del servidor) queda **PENDIENTE** (Bajo).

Pruebas: `tests/test_t1_venteo_liquidos.py` (estado final de la lenta en rango, por debajo de la banda y sin dato; una sola orden por tick; drenaje; falla segura).

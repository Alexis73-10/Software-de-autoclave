# Planeación: entrega de la cámara al terminar el ciclo (ENT)

Fecha: 7-nov-2026. Decisiones de Cristian: todas las de este documento (7-nov), salvo las marcadas `DECISIÓN SIN CONFIRMAR`.
Referencia de comportamiento: ticket Tuttnauer 3870EL, ciclo 005355 (error «Presión baja» a 01:10:09; filas «E» cada 3 min hasta 01:58:30 con 96,7 °C; pie con F0, «Falló el Ciclo» y hora final 09:02:30).

## 1. Problema (estado actual, revisado en `dev` 2bfbee10)

- `CycleLogger.update()` llama a `_on_fin()` en cuanto `fase_ciclo` sale de `_FASES_EN_CURSO`: cierra el ciclo en la base y el respaldo e imprime el pie (Temp. final, Estado, Hora) en el instante del fallo, la cancelación o el COMPLETADO (PF-17/E4). Después, `_cierre_ya_procesado` corta todo registro: durante el protocolo de fallo no hay filas en el ticket ni en la base.
- `PantallaCicloEnCurso.qml` muestra CONFIRMAR con `terminado = resultado !== ""` y `/cycle/acknowledge` lo acepta con cualquier resultado: el operador confirma con la cámara aún presurizada o caliente y el ticket ya salió cerrado.
- `ProtocoloFallo._update()` ya detecta la condición segura (presión en atm ± `rango_presion_atm` y Principal ≤ `temp_max_apertura` del programa), pero solo para el buzzer (`_buzzer_emitido`). Las condiciones de `finalizacion` de COMPLETADO solo las usa `_mantener_apertura_automatica()`.

## 2. Requisitos

**ENT-01 Entrega tras FALLO o CANCELADO.** La cámara queda «entregada» cuando `camara_segura.evaluar` (programa del ciclo, T29-04) no da motivos —presión en banda, Principal ≤ `temp_max_apertura` vigente, sin vacío, sin secado tras fallo en curso ni pendiente (A13-M4)— con datos vigentes, sin sellado (D8-2.10) y sostenida 3 lecturas de tramas AI distintas (como `_DEBOUNCE_LECTURAS`). Una vez entregada no se retira (el operador ya puede confirmar). Lo decide `CicloState` (o un componente puro nuevo, `state_machine/states/entrega_camara.py`) con el protocolo corriendo como hoy; el protocolo no cambia.

**ENT-02 Entrega tras COMPLETADO.** Mismas condiciones de la apertura automática: espera `finalizacion.tiempo_espera_apertura` desde el COMPLETADO y luego Principal ≤ `temp_max_apertura` vigente y presión en banda, 3 lecturas. Si se pasa `timeout_temperatura` se activa CIC-07 (como hoy en la apertura automática, una vez) y se sigue esperando. La apertura automática no cambia: ya exige estas condiciones antes de confirmar.

**ENT-03 Compuerta en el backend (falla cerrada).** `/cycle/acknowledge` sin cámara entregada → 409 `camara_no_entregada` con el motivo vigente (valor y límite, como NO ABRIR). Textos es/en en `sesion_backend.py`. Sin dato para decidir = no entregada.

**ENT-04 Confirmación forzada.** Para los casos en que la condición nunca se cumple (Principal o presión sin lectura, `solo_lenta`, sellado sin sonda, AI vencida): `POST /cycle/acknowledge` con `forzar: true`, solo rol ingeniero con reautenticación (mismo mecanismo de `server_reasignacion._reautenticar`: 428/403 `reautenticacion_*`). Bitácora `ciclo_confirmado_sin_entrega` (categoría seguridad, usuario, motivo vigente) y línea en el pie del ticket, PDF y correo: «Confirmado sin condiciones seguras por {usuario}: {motivo}». En la pantalla, botón visible solo con sesión de ingeniero, con modal de advertencia y reautenticación.

**ENT-05 Paro de emergencia con el resultado pendiente.** `DECISIÓN SIN CONFIRMAR`: se conserva §15.2: con el paro soltado y sin confirmar nada se mueve, así que la entrega no puede ocurrir; en ese caso la confirmación (`ack_confirma_estado_seguro`) sigue permitida sin esperar la entrega, y el pie lleva «Confirmado tras paro de emergencia, cámara sin verificar». Bitácora como hoy.

**ENT-06 Ticket.**
- En el instante del resultado: fila «E» (como hoy) y, si no es COMPLETADO, «Error de ciclo: {motivo}» (`motivo_ticket`) y «F0 total: x» si el ciclo tenía F0. Sin pie.
- Durante la espera: filas «E» cada `intervalo_impresion` (defecto 180 s) con el Principal y la presión, también a la base y al respaldo (`_registrar_lectura("E", ...)`). También en COMPLETADO.
- Al entregar (o confirmar forzado o tras paro): fila final «E» y el pie completo (Temp. final = Principal en ese momento, Estado, Motivo, F0 del momento del resultado, avisos —con el secado tras fallo ya en estado final—, operador, Hora = hora de la entrega o confirmación).
- La reimpresión, el PDF y el correo reproducen lo mismo (filas «E» incluidas y la línea «Error de ciclo»).

**ENT-07 Base de datos y corte de energía (PF-17).** En el instante del resultado se guardan resultado, motivo, código, valores y F0 (como hoy) más una columna nueva `fecha_resultado` (migración de esquema). `fecha_fin` se fija en la entrega o la confirmación; la duración del ciclo (historial, Reportes) va del inicio a `fecha_fin`. Corte de energía durante la espera: al arrancar, un ciclo con resultado y sin `fecha_fin` conserva su resultado (no pasa a INTERRUMPIDO), recibe `fecha_fin` del arranque y el aviso «Entrega de la cámara no registrada (corte de energía)» en `avisos_ticket`; cuenta como ciclo interrumpido para `hubo_ciclo_interrumpido()` y «NO ABRIR» (`DECISIÓN SIN CONFIRMAR`). Revisar el respaldo y su reimportación (A9-R3) con la misma regla.

**ENT-08 F0.** No se acumula después del resultado (ya es así: solo en CALENTAMIENTO/ESTERILIZACION; verificar). El ticket imprime el F0 del momento del resultado.

**ENT-09 Pantalla.** Mientras no haya entrega, en el lugar de CONFIRMAR va un indicador (no botón) con el motivo vigente: «Esperando cámara segura: Temperatura 105 °C, máximo 80 °C» (textos de NO ABRIR, `motivos._presentar`) o, en COMPLETADO durante la espera fija, «Esperando condiciones de apertura: m:ss». Con la entrega aparece CONFIRMAR (con su modal FC-09). `PanelFinCiclo`, «Ver gráfica» y el regreso automático no cambian. Textos sin elide (D8-5.4), es/en. QML solo dibuja; el texto lo arma `ui_qml/domain/`.

**ENT-10 Reloj.** El tiempo transcurrido sigue corriendo hasta la entrega o confirmación (`_t_fin_s` se fija ahí); la serie de la gráfica sigue muestreando.

**ENT-11 PDF y correo.** Se generan con el ticket cerrado (tras la entrega). Si hoy hay generación o envío automático al cierre, se mueve a la entrega; las acciones de Historial sobre un ciclo sin `fecha_fin` no se ofrecen hasta que se cierre.

**ENT-12 Publicación.** `GET /cycle/current/progress` publica `entrega`: `{entregada: bool, motivos: [...], espera_restante_s: int|null, forzable: bool}` (forzable = no entregada y resultado pendiente; la UI decide mostrarlo según el rol de la sesión).

## 3. Riesgos (registro de riesgos)
- HAZ-ENT-01: equipo retenido en CICLO sin poder confirmar si la condición nunca se cumple → control: ENT-04.
- HAZ-ENT-02: confirmación forzada con la cámara no segura → control: solo ingeniero, reautenticación, advertencia, bitácora y ticket.
- HAZ-ENT-03: corte de energía durante la espera → control: ENT-07.
- HAZ-ENT-04 (ENT-05): confirmación tras paro sin verificar la cámara → riesgo residual, pendiente de Cristian.

## 4. Banco (bloque T31)
Fallo en esterilización con cámara presurizada (CONFIRMAR oculto hasta presión y temperatura seguras; filas «E» cada 3 min; pie con la hora de la entrega); cancelación; COMPLETADO con `tiempo_espera_apertura`; Principal desconectado tras el fallo (confirmación forzada por ingeniero); corte de energía durante la espera; paro durante la espera.

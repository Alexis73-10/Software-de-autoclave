# T5 — E3: estado seguro común, matriz de fin de ciclo, PF-10, TMG-03/04, SECADO y líquidos

Instrucción: tanda 2026-10-14 §2 T5, §1.2 y §1.3; `planeacion_fin_de_ciclo_y_puertas.md` §4 y §15.

## 1. Qué se hizo

### 1.1 Protocolo de estado seguro común (§15) — `state_machine/estado_seguro.py` (nuevo)

Antes (PF-10), al confirmar un FALLO nadie seguía el protocolo de fallo: PREPARACION solo venteaba con la rápida, y solo si pasaban sensores y suministros, y nunca cerraba la descompresión de chaqueta de los modos 4/5.

Ahora, al salir de CICLO con FALLO o CANCELADO, la `StateMachine` entrega el `ProtocoloFallo` del ciclo a `ProtocoloEstadoSeguro`, que lo sigue ejecutando fuera de CICLO, en cada tick y antes del estado:

1. **Paro activo**: no actúa (los estados mandan ALL_OFF continuo, A-7) y marca que hará falta una confirmación.
2. **Paro liberado**: salidas en 0, sin avance automático, hasta "Confirmar y llevar a estado seguro" (`POST /safe-state/confirm`, cualquier operador, sin rol). Va fusionado con el reconocimiento: `POST /fault/reset` y, con el resultado del ciclo pendiente, `POST /cycle/acknowledge` también confirman.
3. **Confirmado**: exige datos vigentes; sigue el protocolo de fallo con el modo de descompresión del programa (§1.3 de este informe).
4. **Estado seguro**: cuando la cámara está segura (T4) en 3 ticks seguidos, `finalizar()` cierra toda válvula del protocolo y el protocolo termina. FALLA solo pasa a PREPARACION en ese momento; el reconocimiento queda guardado mientras tanto (`FallaState.run(puede_salir)`).

Tras una cancelación (destino PREPARADO, D-05), mientras el estado seguro está activo PREPARADO no ejecuta su lazo (ni venteo con la rápida ni chaqueta) ni habilita el inicio. Al entrar a un ciclo nuevo se cierra cualquier estado seguro previo antes de reiniciar el `ProtocoloFallo`, que es compartido. La instancia vive en el `ControlLoop` y sobrevive a `set_active_cycle`.

Cada paso queda en `audit_log` (`entidad = "estado_seguro"`): `estado_seguro_iniciado`, `paro_activado`, `paro_liberado`, `estado_seguro_confirmado`, `estado_seguro_alcanzado` (con `duracion_s`). La escritura va en un hilo propio, fuera del tick. `/status.estado_seguro = {activo, requiere_confirmacion}`.

Aviso sonoro: lo emite el propio protocolo al alcanzar condiciones seguras (`BEEP_FALLO`, ya existía).

### 1.2 TMG-04: paro con el resultado del ciclo pendiente

`CicloState.run()` evaluaba el paro solo con el ciclo en marcha; con el resultado pendiente seguía accionando la válvula de reposo, el aire atmosférico y el intercambiador con el paro pulsado. Ahora:
- con el paro activo, `apagar_por_paro()` y nada más;
- tras soltarlo, nada se mueve hasta `CICLO_CONFIRMADO`;
- un paro durante el ciclo ejecuta el protocolo **sin abrir válvulas** (`ejecutar(abrir_valvulas=False)`, §15.1); las abre el estado seguro tras la confirmación.

### 1.3 Protocolo de fallo (`protocolo_fallo.py`): PF-19 y líquidos

- **Modos 4/5 (PF-19)**: primero enfriamiento con contrapresión, igual que la fase DESCOMPRESION: aire comprimido hasta `presion_camara_enfriamiento`, agua de chaqueta, pulsos de la descompresión de chaqueta y, en el modo 5, la lenta. Sigue hasta que el Principal llega a `temperatura_enfriamiento`; solo entonces abre chaqueta + rápida. Si vence el timeout: en sólidos escala a chaqueta + rápida, como antes; en líquidos con la carga caliente no escala (se registra un error).
- **Carga líquida** (`globals.tipo_carga = "liquido"`): la rápida nunca se usa mientras la carga esté caliente. Los modos 1/2/3, que la validación de T10 no permitirá en líquidos, se tratan como lenta.
- **Presión desconocida al disparo**: abre la lenta y no escala (§15.3). Antes no abría nada.
- `finalizar()` cierra rápida, lenta, chaqueta, aire comprimido, agua de chaqueta y aire atmosférico (PF-10).
- **Válvula de reposo** (`valvula_reposo.py`, usada al completar el ciclo y al final de DESCOMPRESION): en líquidos, la rápida solo en los modos 4/5 y con el Principal ya enfriado; en cualquier otro caso, la lenta.

### 1.4 Modo 0 (enfriamiento natural): cómo lo tratan los módulos

`descompresion.modo = 0` se conserva como función soportada. Lo tratan así:
- **Fase DESCOMPRESION**: sin válvulas, sin timeout; espera a que la presión baje a la atmosférica.
- **`valvula_reposo.py`**: como modo 2 (lenta).
- **`protocolo_fallo.py`**: como modo 2 (lenta), con el timeout de `descompresion.modo_2.timeout`. Si vence en sólidos, escala a chaqueta + rápida.

El estado seguro no depende de un timeout inexistente: termina por condición (cámara segura), no por tiempo. El timeout del modo 2 solo decide la escalada. Si `modo_2.timeout` falta, se usan 60 min por defecto.

### 1.5 TMG-03: excepciones repetidas en el tick

Un tick que lanza no renueva el latido (TMG-01 de E0). Ahora, además, tras 3 ticks fallidos seguidos (≈1,5 s) el `ControlLoop` llama a `reset_all_outputs()`, una vez por racha. El log lleva la traza (`logger.exception`), pero solo en el primer fallo y luego uno de cada 20.

### 1.6 SECADO sin vacío real

Lo que hacía, en `secado.py:76-95` del commit `0211880`: en los modos 1 y 2 la única condición de salida era el temporizador. No leía la presión ni comprobaba la bomba, así que con la bomba averiada el ciclo terminaba **COMPLETADO sin secado**.

Ahora los modos 1/2 exigen vacío real: presión de cámara bajo `atm − rango_presion_atm` dentro de `secado.timeout_pulso` (parámetro existente, 180 s en los programas). Fallan (FALLO de SECADO) en tres casos:
- el vacío no se alcanza en ese plazo;
- se pierde de forma sostenida (3 lecturas seguidas);
- el tiempo termina sin haberlo alcanzado.

### 1.7 Matriz de fin de ciclo (§4)

| Causa | Acción | Resultado | Tras confirmar |
|---|---|---|---|
| Completado | Válvula de reposo + drenaje (en líquidos, sin la rápida si está caliente) | exitoso | PREPARADO |
| Cancelación | Protocolo de fallo → estado seguro | cancelado | PREPARADO (bloqueado hasta estado seguro) |
| Fallo de fase, puerta, sensor, comunicación > 5 s, suministro, tarjeta de E/S | Protocolo de fallo → estado seguro | fallo | FALLA → PREPARACION al alcanzar el estado seguro |
| Paro | ALL_OFF continuo, sin válvulas; confirmación tras soltar | fallo | Igual que fallo |

## 2. Pruebas

- Nuevas: `test_t5_protocolo_liquidos.py` (16), `test_t5_estado_seguro.py` (16) y 5 en `test_secado_fase.py`.
- Ajustadas: `test_secado_fase.py` (la configuración de prueba devolvía MagicMock para atm/rango), `test_ciclo_apertura_automatica.py` (el doble de `get_param` admite claves anidadas) y `test_control_loop_set_active_cycle.py` (firma de `StateMachine`).
- El protocolo y el estado seguro se escribieron antes que sus pruebas; las pruebas de SECADO y TMG-04 se escribieron contra el comportamiento nuevo. Excepción a "pruebas primero", registrada por honestidad.
- Suite completa: ver `estado.md`.

## 3. Revisores

Ver §6.

## 4. DECISIONES SIN CONFIRMAR

- D-T5-1: FALLA espera el estado seguro antes de pasar a PREPARACION (§15.4). Alternativa: pasar a PREPARACION y que el estado seguro siga en paralelo. Se eligió esperar porque PREPARACION tiene su propio venteo con la rápida, prohibido en líquidos calientes.
- D-T5-2: tras una cancelación, PREPARADO suspende su lazo (incluida la chaqueta) mientras dura el estado seguro.
- D-T5-3: modos 4/5 en sólidos también enfrían antes de despresurizar (PF-19 no distingue el tipo de carga).
- D-T5-4: el enfriamiento de los modos 4/5 manda aunque la cámara empiece en presión normal, mientras la carga esté sobre `temperatura_enfriamiento`; la contrapresión puede subir la presión hasta `presion_camara_enfriamiento`.
- D-T5-5: SECADO modos 1/2: el umbral de "vacío real" es `atm − rango_presion_atm`, con el plazo de `timeout_pulso`. No hay parámetros nuevos.
- D-T5-6: TMG-03: umbral de 3 ticks (no medido en segundos).

## 5. PENDIENTES

- La UI: botón "Confirmar y llevar a estado seguro" y textos de la pantalla de paro (T7).
- PREPARACION sigue usando la rápida para igualar presión. Fuera del estado seguro, la cámara ya está en rango. En líquidos solo podría haber presión en PREPARACION por una causa externa.

## 6. Revisores (resultado)

`timing-auditor`: 1 Alto, corregido.
- **TMG-01 (Alto)**: tras una cancelación, si el supervisor de PREPARADO fallaba, sus "salidas seguras" ventean con la rápida (también con líquido caliente) y peleaban con el protocolo. **Corrección**: el estado seguro se evalúa antes que el supervisor; mientras esté activo PREPARADO solo evalúa alarmas y apaga el vapor.
- Corregidos (Medio/Bajo): TMG-02 (el plazo del modo se arma al empezar a abrir válvulas, `reanudar()`, no durante el paro o la espera de confirmación); TMG-03 (el estado seguro recibe `datos_vigentes` del lazo); TMG-04 (un error del estado seguro no corta el estado); TMG-06 (una confirmación guardada durante el paro se descarta); TMG-07 (los pulsos de chaqueta y la contrapresión empiezan de nuevo al reanudar).
- Pendientes: TMG-05 (un hilo por evento de auditoría, sin cola FIFO acotada), TMG-08 (`None` en el debounce de pérdida de vacío), TMG-09 (lectura de `/status.estado_seguro` sin lock, solo visual).

`safety-reviewer`: 2 Críticos y 2 Altos, corregidos.
- **SAF-01 (Crítico)** = TMG-01.
- **SAF-02 (Crítico)**: `aire_comprimido_camara` podía quedar enclavado en ON al escalar, al cambiar de rama o con la presión en `None`. **Corrección**: `_fin_enfriamiento()` al escalar; sin presión se apaga el aire; el enfriamiento siempre pasa por la misma ruta.
- **SAF-03 (Alto)**: el protocolo presurizaba con aire una cámara que no estaba presurizada al disparo, y la puerta podía abrirse mientras tanto. **Corrección**: contrapresión solo si estaba presurizada al disparo; si no, la lenta (o el aire atmosférico si hay vacío) hasta enfriar; además, no se abre ninguna puerta con el estado seguro activo.
- **SAF-04 (Alto)**: con el Principal sin lectura, el protocolo quedaba en contrapresión para siempre, sin aviso. **Corrección**: Principal sin lectura en los modos 4/5 → lenta y sin escalar; alarma nueva **CIC-10 "Estado seguro detenido"** (AVISO) con el motivo, también cuando se deniega la escalada en líquidos. Sigue sin haber salida automática: la cámara no se declara segura sin temperatura (falla cerrada). PENDIENTE: definir con Cristian una salida de mantenimiento autorizada y auditada.
- Corregidos (Medio/Bajo): SAF-05 (el paro domina sobre la cancelación y los abortos forzados); SAF-06 (3 lecturas para dar por enfriada la carga); SAF-07 (el estado seguro mantiene el enfriamiento del drenaje); SAF-09 (rige también el `temp_max_apertura` del ciclo); SAF-10 (= TMG-03); SAF-12 (un error al leer `tipo_carga` se trata como líquido); SAF-13 (SECADO modo 3 registra su motivo).
- Hallado al revisar: **SECADO no cerraba la válvula de reposo** que DESCOMPRESION deja abierta. Con la exigencia nueva de vacío, eso podía hacer fallar ciclos normales. Ahora SECADO cierra rápida, lenta y chaqueta al empezar. DECISIÓN SIN CONFIRMAR, ver §7.
- Pendientes: SAF-08 (el estado seguro no persiste tras un reinicio → T6), SAF-11 (TMG-03 por racha, no por ventana deslizante); pregunta abierta sobre la validación de modo 4/5 obligatorio en líquidos → T10.

## 7. Comprobaciones manuales de Cristian

- Simulador: provocar un fallo en ESTERILIZACION con modo 4 y `tipo_carga=liquido`. Debe enfriar con contrapresión, despresurizar con chaqueta + rápida solo bajo `temperatura_enfriamiento` y cerrar todo al quedar segura. FALLA no debe pasar a PREPARACION antes.
- Pulsar el paro en pleno ciclo: sin válvulas abiertas mientras esté pulsado. Al soltar, nada se mueve hasta confirmar.
- SECADO modo 1 con la bomba desconectada: el ciclo debe terminar en FALLO a los `timeout_pulso` segundos.
- **Importante:** con la bomba en buen estado, comprobar que SECADO modos 1 y 2 alcanzan `atm − rango_presion_atm` (≈70 kPa con atm 75) en menos de `timeout_pulso`. SECADO ahora cierra las válvulas de descompresión al empezar. Si en el equipo esas válvulas fueran necesarias durante el secado, avisar.
- Respuesta pendiente: ¿hay válvula de alivio de cámara y regulador en la línea de aire comprimido? (presión máxima de la contrapresión).

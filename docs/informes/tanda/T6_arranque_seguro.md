# T6 — E4: arranque seguro

Instrucción: tanda 2026-10-14 §2 T6; `planeacion_arranque_y_modo_sin_bd.md` §7.5 (aprobado) y `planeacion_fin_de_ciclo_y_puertas.md` D-08, §8.

## 1. Verificaciones (sin cambios)

- **ALL_OFF al conectar**: ya hecho en E6. El handshake (`SerialLink._ejecutar_handshake`) manda ALL_OFF, primero de mejor esfuerzo (TMG-02 de E0) y luego confirmado en el paso 5, antes de aceptar cualquier orden de salida. El firmware V3 arranca con las salidas en 0 hasta el primer ALL_OFF válido.
- **PF-21 (paro NC)**: ya hecho en E1 (`dd4a672`). `EmergencyStop.update`: paro = entrada en 0 o sin dato (`paro_emergencia.py:32-39`).

## 2. Qué se hizo

- **Contador persistente** (`core/runtime/contador_ciclos.py`): archivo `data/ciclo_contador.json` con escritura atómica (temporal + `fsync` + `os.replace`). Al arrancar se sincroniza con `max(contador, MAX(numero))` de la base. Al iniciar cada ciclo se reserva `max(contador, MAX(numero)) + 1`. Un contador ilegible no baja la numeración (manda la base). Sin base de datos, el contador sigue siendo la fuente (sin prefijo, D-07).
- **Migración de BD v3**:
  - `ciclos.uuid` (UUID4 por ciclo, clave de idempotencia para el respaldo de T8) y `ciclos.programa_json` (instantánea del programa: id, nombre, número, origen, asignación de sensores y todos los parámetros).
  - Índice UNIQUE `idx_ciclos_numero_unico` sobre `numero_ciclo`, solo si no hay duplicados. Si los hay, se registran en el log y no se crea (migración no destructiva).
- **Ciclos interrumpidos** (D-08, PF-17): al abrir la base, todo ciclo con `fecha_fin` NULL se cierra como `INTERRUMPIDO` con el motivo "Ciclo interrumpido: el equipo se reinició o perdió energía sin cerrarlo. El ciclo no se reanuda; la carga NO está estéril.", y queda `ciclo_interrumpido` en `audit_log`.
- **Recuperación tras el reinicio** (resuelve SAF-08 de T5 y TMG-02/SAF-02 de T4):
  - Se reconstruye el programa del último ciclo interrumpido: desde la instantánea (v3) o, en filas anteriores, el programa cargado con la asignación de sensores registrada (v2).
  - Su sensor Principal cuenta para la seguridad de apertura hasta que la cámara sea segura.
  - Con el primer dato vigente, si la cámara **no** es segura, arranca el protocolo de estado seguro con ese programa (modo de descompresión, carga líquida y modos 4/5 incluidos) y **con confirmación**: nada se mueve hasta "Confirmar y llevar a estado seguro". Nunca se reanuda el ciclo.
  - PREPARACION, como PREPARADO, cede la cámara al estado seguro: sin venteo con la rápida, sin chaqueta y sin avanzar.
- **Cierre inmediato del COMPLETADO** (PF-17): el registro cierra el ciclo en la base e imprime el pie en cuanto termina, sin esperar la confirmación. Un corte antes de confirmar ya no lo deja sin cierre.

## 3. Pruebas

`tests/test_t6_arranque_seguro.py` (13): contador (persistencia, sincronización, contador atrasado o ilegible), v3 (UNIQUE y migración con duplicados), cierre de interrumpidos, instantánea, cierre inmediato del COMPLETADO, numeración desde el contador, y recuperación con la cámara caliente (estado seguro con confirmación, sin rápida) o segura (nada). Ajustada `test_db_audit_log` (esquema v3). Las pruebas se escribieron junto con el código. Suite completa: ver `estado.md`.

## 4. DECISIONES SIN CONFIRMAR

- D-T6-1: tras un reinicio con la cámara no segura, el estado seguro exige confirmación (operador presente), aunque el ciclo no haya terminado en paro. Alternativa: arrancar el protocolo sin confirmación.
- D-T6-2: el contador se escribe en el hilo del lazo al iniciar y al cerrar cada ciclo (marca de ciclo en curso).
- D-T6-4: en cada arranque se evalúa la cámara con el programa del último ciclo (o uno conservador). Si no es segura, se pide confirmación aunque no haya habido corte. El modo prueba queda bloqueado ~1,5 s hasta esa evaluación.
- D-T6-3: `INTERRUMPIDO` se agrega como resultado en la base. Las pantallas lo clasifican como "fallo" (`progreso_ciclo.resultado`: todo cierre distinto de COMPLETADO/CANCELADO), así que se ve como Fallo. Alternativa: texto propio `menu.resultado_interrumpido`.

## 5. PENDIENTES

- Respaldo JSONL por ciclo y reimportación por UUID: T8 (modo sin BD).
- Texto propio para el resultado `INTERRUMPIDO`, si se quiere distinguir de Fallo.

## 6. Revisores (resultado)

`timing-auditor`: 1 Alto, corregido.
- **TMG-01 (Alto)**: un fallo al registrar el inicio del ciclo (contador o base) se propagaba como excepción del tick, se reintentaba cada 0,5 s y las salidas oscilaban (ALL_OFF de TMG-03 y reencendido por la máquina de estados), además de quemar números. **Corrección**: `_on_inicio_protegido()`: el fallo no sube; el ciclo sigue sin registro en la base (`sin_registro`, para T8) y el número se reserva una sola vez por ciclo.
- Corregidos (Medio): TMG-03 (sin base o con la base bloqueada el ciclo interrumpido no se detectaba). Ahora `data/ciclo_contador.json` guarda además una **marca de ciclo en curso con la instantánea del programa**, escrita antes de tocar la base y limpiada al cerrar el ciclo. TMG-04: con datos no vigentes o con una recuperación pendiente no se cuentan ticks seguros, y una recuperación que llega en CICLO se descarta con registro.
- Pendientes: TMG-02 (I/O de base y `fsync` del contador dentro del tick al iniciar el ciclo; medir en el hardware destino), TMG-05 (`fsync` del directorio en POSIX), TMG-06 (eventos de auditoría en hilos daemon), TMG-07 (`fecha_fin` del INTERRUMPIDO = hora del arranque, no del corte).

`safety-reviewer`: 1 Alto, corregido.
- **SAF-01 (Alto)**: la recuperación dependía de una fila abierta en la base. No ocurría sin base, con la base bloqueada, tras un corte durante FALLA o CANCELADO, ni con la fila ya cerrada por un arranque fallido previo. **Corrección**: se decide por el **estado físico**. En cada arranque se arma la recuperación con el mejor programa disponible: el del ciclo interrumpido (fila o marca), si no el del último ciclo registrado (`programa_json`) y, si no, uno conservador (líquido, solo la lenta). Con el primer dato vigente, si la cámara no es segura, entra en estado seguro con confirmación.
- Corregidos (Medio/Bajo): SAF-02 (3 ticks seguros seguidos antes de descartar la recuperación; una excepción no la pierde); SAF-03 (el modo prueba se rechaza durante la recuperación o el estado seguro); SAF-04 (= SAF-01: el último ciclo cuenta aunque haya terminado en COMPLETADO); SAF-05 (un programa sin `tipo_carga` se recupera como líquido).
- Pendiente SAF-06: alarma visible y copia del contador ilegible (hoy solo log; la base decide el mínimo).

## 7. Comprobaciones manuales de Cristian

- Cortar la energía del PC a mitad de un ciclo y volver a encender: el ciclo debe aparecer en el historial como INTERRUMPIDO y el número del siguiente no debe repetirse. Si la cámara quedó presurizada o caliente, el equipo debe pedir confirmación antes de mover válvulas.
- Borrar `autoclave.db` (con copia) y arrancar: el siguiente ciclo debe seguir la numeración de `data/ciclo_contador.json`.

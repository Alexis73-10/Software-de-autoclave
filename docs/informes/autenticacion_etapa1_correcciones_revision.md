# Informe — Autenticación, etapa 1: correcciones de la revisión de seguridad

**Fecha:** 2026-10-07
**Rama:** dev, sin commits
**Origen:** `autenticacion_etapa1_revision_seguridad.md`. Aprobado: A, B, C, D y tres extras (encender solo desde la sesión dueña, intentos de login atómicos y cancelación por paro con dueño limpio y registro en la bitácora). No cambia ninguna decisión de la spec.

## Resultado

- La suite completa queda en verde: **2022 tests pasan**, ninguno omitido. Antes de las correcciones eran 1964.
- La validación de `rango_presion_atm` al arrancar está hecha con la opción 2 que elegiste: el backend arranca bloqueado con una alarma visible (ver la última sección).

## Archivos modificados

- `src/autoclave/services/domain/loop/control_loop.py`
- `src/autoclave/backend/server.py`
- `src/autoclave/backend/autenticacion.py`
- `src/autoclave/ui/service_ui/ui_service_backend.py`
- `src/autoclave/main.py`
- `src/autoclave/ui/main.py`
- `src/autoclave/ui/window/main_window.py`
- `src/autoclave/backend/context.py` y nuevo `src/autoclave/core/managers/validacion_config.py` (configuración inválida)
- Tests: `tests/test_io_endpoints.py` (reescrito), `tests/test_backend_autenticacion.py`, `tests/test_control_loop_test_mode.py` `tests/test_ui_service_backend_cierre.py` (nuevo) y `tests/test_config_invalida_arranque.py` (nuevo)

## Qué se corrigió

### A — R-02 lee las puertas en vivo (crítico)
- Antes, `_motivo_r02()` leía el estado lógico de la puerta. Ese estado queda congelado durante el modo prueba, porque `door.update()` está en pausa.
- Ahora lee directamente las entradas digitales de cada puerta: `door.di["cerrada"]` y, si la puerta tiene ese sensor, `door.di["abierta"]`, desde `estado.sensores_di`, que se actualiza en cada tick.
- **Puerta cerrada:** exige `cerrada=1` y `abierta=0`.
- **Sin lectura, con rechazo:** valor `None`, valor fuera de 0/1, entrada ausente, puerta sin mapa de entradas o lista de puertas vacía.
- No uso `AdvancedDoor.puerta_abierta()` porque convierte una lectura ausente en `False`, y eso dejaría pasar una puerta sin lectura.
- La presión se sigue comparando con `presion_admosferica ± rango_presion_atm`. Las dos son absolutas, como confirmaste.

### B — Cerrar o apagar desde Tk con un ciclo en curso
- **Nuevo `UIServiceBackend.reset_outputs_al_cerrar()`.** Devuelve:
  - `"apagado"`: el backend apagó las salidas.
  - `"ciclo"`: el backend respondió 409 porque hay un ciclo en curso.
  - `"error"`: cualquier otro fallo, por ejemplo el backend inaccesible.
- **`on_close` de `main.py` y de `ui/main.py`:** con `"ciclo"`, la ventana no se cierra y el backend no se termina. Se muestra el aviso "No se puede cerrar con un ciclo en curso. Espere a que termine o abórtelo antes de cerrar." Con `"error"` se mantiene el comportamiento anterior: el backend ya no responde, así que se cierra igual.
- **`apagar_equipo` de `main_window.py`:** tenía el mismo problema. Además, llamaba a `on_close` y dejaba colgada la pantalla "Apagando equipo". Ahora se cancela con un aviso equivalente.
- **Backend:** `FastAPI(lifespan=...)` ejecuta `control_loop.stop()`, que manda `ALL_OFF`, en todo apagado ordenado (Ctrl+C o SIGTERM de uvicorn). Un `TerminateProcess` de Windows no pasa por ahí; por eso lo principal es que Tk ya no termine el backend durante un ciclo.
- **Variante respecto a la propuesta de la revisión:** proponía "pedir confirmación y abortar con `/cycle/abort`". No lo hice así porque, tras abortar, el protocolo de fallo sigue en CICLO un rato (descompresión) y cerrar en ese momento volvería a matar el backend a mitad del protocolo. Se avisa y no se cierra; el operador aborta desde la pantalla normal.

### C — Entrar y salir del modo prueba bajo el lock
- **Lock reentrante:** `_sm_lock` pasa a ser `threading.RLock`. El backend lo toma en el guard y dentro llama a `enter/exit_test_mode`, que también lo toman.
- **`enter_test_mode()` y `exit_test_mode()`** corren con el lock tomado. `exit_test_mode` apaga primero y reanuda después.
- **El tick hace los pasos 2c a 5 dentro del mismo lock:**
  - 2c: cancelación por paro.
  - 3: puertas.
  - 4: servicio de puertas.
  - 5: máquina de estados.
  Así, la decisión "¿estoy en modo prueba?" no puede quedar desfasada a mitad de tick (TMG-04).
- **En el servidor:**
  - `/io/test/exit` y `/auth/logout` comprueban la sesión dueña y salen dentro del lock.
  - `/io/test/enter` vuelve a validar el token dentro del lock. Así, un logout que llegue mientras la petición espera hace que se rechace con 401 y el modo prueba no queda huérfano (TMG-03).

### D — Nada lento con el lock tomado
- **`_Rechazo`:** dentro de `guard_estado`, los rechazos se lanzan como `_Rechazo`. El guard los registra en `audit_log` y los convierte en `HTTPException` **después** de soltar el lock. Ningún 409 escribe en SQLite con el lock tomado.
- **Calibración:** bajo el lock solo se comprueba el estado. La lectura y escritura del YAML y la recarga van fuera. No hace falta atomicidad: el guard solo deja pasar en CICLO al ingeniero, que es el único rol que llega a ese endpoint.
- **Parámetros de ciclo:** la comprobación de estado y del programa en curso, y el cambio en memoria, siguen bajo el lock, porque deben ser atómicos con START_CICLO. El JSON se escribe fuera.
- **Nuevo `_lock_archivos`:** serializa las escrituras del YAML de calibración y del JSON de ciclos, que ahora se hacen fuera de `_sm_lock`.
- **Bajo el lock solo quedan** los cambios en memoria y las órdenes a la tarjeta (`set_output`; `ALL_OFF` al entrar o salir del modo prueba). Todos ocurren fuera de CICLO, así que no afectan a ningún ciclo en curso.

### Extras aprobados
1. **Encender solo desde la sesión dueña:** `/io/test/output` con `value=true` desde otra sesión responde 409. Cualquier sesión de prueba puede apagar. Sin dueño, nadie enciende.
2. **Intentos de login atómicos:** `ControlIntentos.reservar_intento()` comprueba el bloqueo y cuenta el intento en una sola operación, antes de la verificación lenta. Un login correcto lo devuelve con `registrar_exito()`. Desaparece `registrar_fallo()`.
3. **Cancelación por paro:**
   - `ControlLoop.al_cancelar_modo_prueba(callback)` avisa una sola vez, fuera del lock y desde el hilo del loop. Un error en el aviso no interrumpe el tick.
   - El backend olvida la sesión dueña y registra `modo_prueba_sale` con el usuario dueño y `{"motivo": "paro de emergencia"}`.
   - Un aviso que llegue tarde, con un modo prueba nuevo ya activo, no lo toca.

## Tests añadidos o cambiados

| Hallazgo | Tests |
|---|---|
| A | `test_puerta_abierta_durante_la_prueba_bloquea_aunque_el_estado_diga_cerrado` (el escenario del hallazgo), `test_encender_exige_cerrada_1_y_abierta_0` (6 casos: intermedia, incoherente, `None` en cada entrada, entrada ausente, valor inválido), `test_estado_logico_abierto_no_bloquea_si_las_entradas_dicen_cerrada`, `test_puerta_sin_sensor_de_abierta_usa_solo_cerrada`, `test_segunda_puerta_abierta_bloquea`, `test_puerta_sin_mapa_de_entradas_409` |
| B | `tests/test_ui_service_backend_cierre.py` (apagado, 409 → "ciclo", 500 y backend caído → "error"), `test_apagado_del_backend_detiene_el_loop_y_apaga_salidas` |
| C | `test_lock_de_la_maquina_es_reentrante`, `test_enter_y_exit_corren_con_el_lock_tomado`, `test_exit_apaga_antes_de_reanudar`, `test_tick_decide_puertas_y_maquina_con_el_lock_tomado`, `test_cancelacion_por_paro_apaga_con_el_lock_tomado`, `test_enter_revalida_el_token_dentro_del_lock`, `test_logout_sale_del_modo_prueba_con_el_lock_tomado` |
| D | `test_rechazo_por_estado_se_registra_con_el_lock_libre`, `test_rechazo_409_queda_en_audit_log_fuera_del_lock`, `test_salida_se_acciona_con_el_lock_tomado`, `test_calibracion_escribe_archivo_y_recarga_fuera_del_lock` (sustituye a `test_escritura_de_calibracion_dentro_del_lock_de_la_maquina`, que comprobaba lo contrario), `test_parametro_cambia_en_memoria_con_lock_y_guarda_json_sin_lock` |
| Sesión dueña | `test_otra_sesion_no_puede_encender_pero_si_apagar`, `test_sin_dueno_nadie_enciende` |
| Login atómico | `test_intentos_en_paralelo_no_superan_el_maximo` (20 hilos → 5 intentos), `test_logins_en_paralelo_contra_el_endpoint_no_superan_el_maximo` (10 logins a la vez → 5×401 y 5×429), `test_bloqueo_dura_cinco_minutos` (adaptado a `reservar_intento`) |
| Paro | `test_cancelacion_por_paro_avisa_una_vez_y_fuera_del_lock`, `test_error_en_un_aviso_no_rompe_el_tick`, `test_cancelacion_por_paro_olvida_al_dueno_y_queda_en_la_bitacora`, `test_aviso_de_paro_tardio_no_toca_un_modo_prueba_nuevo` |

En `tests/test_io_endpoints.py`, el fixture ahora usa puertas con mapa de entradas y una sesión dueña del modo prueba. Los tests que comprobaban el estado lógico de la puerta (`test_encender_con_puerta_no_cerrada_409[...]`) se reemplazaron por los de entradas en vivo.

## Lo que no se hizo y por qué

- **Validación de `rango_presion_atm`:** hecha; ver la sección siguiente.
- **No incluido, pendiente de tu decisión:** E, F, K y L, y las preguntas de hardware 1 y 2.
- **Preexistente, sin tocar:** I (escrituras no atómicas), J (`cycle_logger` con `time.time()`), M (`all_off` con el evento de ACK compartido) y N (`BEGIN IMMEDIATE` en las migraciones).
- **"Nivel de acceso":** no se agregó, como indicaste.

## Configuración inválida al arrancar (opción 2)

- **Validación:** `core/managers/validacion_config.py` → `errores_config_arranque(config)`. Exige `rango_presion_atm` numérico, sin NaN ni booleanos, dentro de **1–10 kPa** con los límites incluidos. Que falte también es un error. Es el lugar donde se añadirá la validación de todas las claves de `planeacion_backend_parametros.md` §4.2.
- **Al arrancar** (`BackendContext._validar_configuracion`, antes de `control_loop.start()`):
  - Si hay errores, se registra la alarma `CONFIGURACION_INVALIDA`: tipo FALLA, origen `ARRANQUE`, bloqueante y no recuperable. La descripción incluye el motivo, por ejemplo "Configuración inválida: rango_presion_atm fuera de rango: 25 kPa (permitido 1–10 kPa)".
  - Además se llama a `control_loop.bloquear_por_configuracion(motivo)`.
- **`ControlLoop` bloqueado:**
  - Cada tick sigue leyendo y publicando sensores, paro de emergencia y suministro, para que la UI los muestre.
  - No ejecuta puertas, servicio de puertas, máquina de estados, registro de ciclo ni buzzer.
  - Manda `ALL_OFF` una vez por conexión con la tarjeta, también después de una reconexión.
  - `enter_test_mode()` lo rechaza.
- **Endpoints:** `/cycle/start`, `/doors/{puerta}/open`, `/doors/{puerta}/close` y `/io/test/enter` responden 409 "Configuración inválida: …" y quedan en la bitácora. `/outputs/reset` sigue disponible.
- **UI:** la alarma llega por `/status` y la fila de alarma de QML muestra su descripción. No hubo que tocar QML.
- **Salida del bloqueo:** se corrige `global_params.json` y se reinicia. No hay forma de limpiar el bloqueo en caliente, porque la configuración del sistema aún no se edita desde la UI (spec de parámetros).
- **Posible conflicto:** la alarma usa la clase `Alarm` actual. Si la rama `alarmas-parte-a` cambia el catálogo o la API de alarmas, habrá que portar `CONFIGURACION_INVALIDA` al unirla.

**Tests (28 en `tests/test_config_invalida_arranque.py`):**
- Límites válidos 1, 5 y 10.
- Valores inválidos: 0,99, 10,01, 0, negativo, 20, ausente, texto, booleano y NaN.
- La configuración de fábrica es válida.
- El arranque bloqueado registra la alarma con su tipo y motivo; con un rango válido no hay alarma.
- El loop bloqueado no ejecuta puertas, máquina ni buzzer, sí publica sensores y apaga una vez por conexión.
- El modo prueba se rechaza en el loop y en el endpoint.
- Inicio de ciclo y puertas responden 409; apagar salidas sigue permitido.

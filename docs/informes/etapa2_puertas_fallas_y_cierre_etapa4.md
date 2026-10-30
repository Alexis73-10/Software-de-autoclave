# Etapa 2 (T-13, T-18, T-16) y resto de la etapa 4 (T-15, T-19)

**Fecha:** 2026-10-09 · **Rama:** `dev` (sobre `8492927`) · **Suite:** 2204 en verde · **Verificación visual:** aprobada por Cristian (2026-10-10).
**Spec:** `planeacion_backend_autenticacion.md` v7 (§5.3, §5.9, decisiones 15-24).
**Evaluación previa IEC 62304:** cambios Clase C sobre medidas de control (enclavamiento de puertas, reconocimiento de fallas); base: spec v7 (sin registro formal de solicitud de cambio, NRM-02); sin fichero de riesgos (NRM-01).

## Qué se hizo

### T-13 · Puertas: guard y condiciones físicas (§5.3)
- Endpoints `/doors/{puerta}/open|close` (`_orden_puerta`, `server.py`): guard de estado bajo `_sm_lock`, **409 en CICLO, HIBERNACION y EMERGENCIA** (permitido en PREPARACION, PREPARADO y FALLA). Todo rechazo es **409 con código y motivo** (`puerta_rechazada`, `estado_no_permitido`, `paro_emergencia`, `modo_prueba_activo`, `sin_conexion_tarjeta`) y queda en `audit_log` (antes era 403). Puerta inexistente: 404.
- `ServicioPuertas` (`ser_puertas.py`) **falla cerrada**: sin lectura válida (ausente, no numérica, NaN o infinita) de `pres_camara` o `temp_camara`, o sin `presion_admosferica`, `rango_presion_atm` o `temp_max_apertura`, no abre (antes se omitía la comprobación, OPC-16). La configuración se **lee en vivo** (OPC-11).
- Cierre: rechazado con estado **DESCONOCIDO** (la posición segura es abierta), sin lectura de `pres_camara` o sin configuración atmosférica; la presión del empaque solo interviene si **la puerta tiene empaque** (`ai["presion_empaque"]`, solo el tipo ADVANCED). Sin comprobación de vacío ni de temperatura (decisión 18).

### T-18 · Resultado real
- `AdvancedDoor.cmd_abrir` / `cmd_cerrar` devuelven `(ok, motivo)`: bloqueo mecánico → rechazo; cerrar solo desde ABIERTO. `SimpleDoor` (sin actuador) acepta y el endpoint responde `"sin_actuador": true`.

### T-16 · Fallas (§5.9)
- `/cycle/acknowledge` pre-arma `RESET_FALLA` para **todo resultado "fallo"** (incluido `SENSOR_AUSENTE`, OPC-22) y registra `falla_reconocida`.
- `/fault/reset` (sin identificación) registra `falla_reconocida`.
- Con el **paro de emergencia activo**, ambos responden 409 y no guardan nada; `FallaState` además **descarta** un `RESET_FALLA` que llegue con el paro activo, así que tras soltarlo hay que reconocer de nuevo (OPC-23).
- QML: botón **RECONOCER FALLA** en la pantalla de preciclo, en el lugar de INICIAR CICLO, visible solo en FALLA con datos vigentes, sin rol (`ComandoReconocerFalla`, `comandos_falla.py`). Texto `modulos.reconocer_falla` = "RECONOCER FALLA" (**propuesto**); colores naranja **provisionales** (sin mockup).

### Resto de la etapa 4
- **T-15:** `CicloController` usa `url_backend()` (respeta `AUTOCLAVE_BACKEND_URL`).
- **T-19:** `temp_chaqueta` fuera de `map_temp`, de `verificar_sensores`, de `/status`, de `get_sensores_temp`, de la vista PySide y del simulador. Los demás sensores conservan su posición en la trama y en la calibración. Nota en `calibration.yaml`: la posición 3 no se borra (la calibración es posicional); se verificó que sobrevive a una recalibración.
- Simulador: puertas con el contrato nuevo (409 con código en CICLO, `sin_actuador`).

## Revisiones (safety-reviewer, timing-auditor, sensor-role-auditor)

**Corregido:**

| Id | Sev. | Hallazgo | Corrección |
|---|---|---|---|
| TMG-01 / SAF-01 | Alta | Abrir durante el cierre dejaba energizados a la vez cerrar y abrir (o bloquear y desbloquear) y heredaba el plazo del cierre; alcanzable desde el botón QML | `cmd_abrir` solo desde CERRADO, DESCONOCIDO o ERROR (en movimiento o ATRAPADA: rechazo; ABIERTO: "ya está abierta"); arranque con plazo nuevo |
| TMG-02 / SAF-05 | Alta/Media | Las órdenes de puerta no miraban el paro de emergencia | `ServicioPuertas` rechaza con el paro activo (cubre también la apertura automática) |
| SAF-04 | Media | Con modo prueba o enlace caído la orden quedaba pendiente y se ejecutaba después sin revalidar | 409 `modo_prueba_activo` / `sin_conexion_tarjeta` (nuevo `ControlLoop.desconectado`, solo lectura) |
| TMG-03 / SAF-07 | Media | `/cycle/acknowledge` a mitad de ciclo quedaba guardado y la máquina salía al terminar sin que el operador viera el resultado | 409 `sin_resultado` si el ciclo no terminó |
| TMG-05 | Media | `AdvancedDoor` medía plazos con `time.time()` | `time.monotonic()` (regla del proyecto) |
| SAF-06 | Media | El cierre exigía presión de empaque a toda `AdvancedDoor` (LOCKING/MOTORIZED no tienen) | Solo si la puerta declara `presion_empaque` |
| TMG-07 | Baja | `/fault/reset` en modo prueba se aplicaba al salir sin reconocimiento posterior | 409 `modo_prueba_activo` |
| TMG-08 | Baja | Emisión desde el hilo tras cerrar la ventana | Protegida |
| SEN-01 / SEN-02 | Baja | Posición 3 de calibración sin aviso; T-19 sin pruebas de backend | Nota en `calibration.yaml`; pruebas de `/status` e índices |

**No corregido (requiere hardware o decisión):**
- **SAF-02 (Media) — respondida:** no existe entrada física de bloqueo mecánico; la única entrada de la puerta es el **botón de atrapamiento** (`atrapamiento_puerta_N`, DI 6/7). El rechazo por bloqueo de T-18 queda **sin efecto en campo**. Además, `factory.py:43` asigna como entrada `bloqueo_puerta_N`, que es el nombre de una **salida** (`map_do` 10/11), así que esa comprobación nunca lee nada. Pendiente (fuera de esta etapa): retirar `has_mech_lock_sensor` y la comprobación de `cmd_abrir`, o dejarlas documentadas.
- **SAF-03 (Media) — se aborda aparte:** `convert_pressures` nunca devuelve `None` (recorta a ≥ 0): un transductor desconectado da 0 kPa y el rechazo "sin lectura válida de presión" no se activa en campo. Corregirlo toca la conversión de todas las presiones del control.
- **TMG-04 (Media):** con el enlace inestable, los POST de comando pueden esperar el lock más que el timeout de 0,8 s del cliente: el backend aplica y la UI registra "rechazado".
- **TMG-06 (Baja):** un reconocimiento aceptado y luego descartado por un paro posterior queda solo en el log, no en `audit_log`.
- **SAF-08/09/10 (Baja):** la UI no muestra el motivo del rechazo de RECONOCER FALLA ni el aviso "sin actuador".
- `CicloState`, esperando confirmación con resultado COMPLETADO, no consulta el paro en su paso 0 (válvula de reposo); la apertura automática sí queda bloqueada ahora.

## Preguntas abiertas
1. **Abrir mientras cierra:** se rechaza. ¿Debe permitirse como inversión manual (con apagado de cerrar/bloquear)? La detección de atrapamiento ya invierte sola.
2. ~~SAF-02~~: respondida, solo existe el botón de atrapamiento.
3. ¿Los tipos LOCKING, MOTORIZED y MOTORIZED_LOCKING se usan en campo?
4. `temp_max_apertura` = 120 °C global: ¿intencional para la apertura manual?
5. ¿El paro de emergencia corta por hardware la energía de los actuadores de puerta y de la bomba?
6. ¿El firmware sigue enviando 8 temperaturas con la posición 3 presente (T-19)?

## Pruebas
- Nuevas: `test_servicio_puertas.py` (33), `test_puertas_fallas_endpoints.py` (30), `test_reconocer_falla.py` (7, incluye carga real de `Main.qml`), `test_sin_temp_chaqueta.py` (2), T-15 en `test_ciclo_controller.py`.
- Ajustada: `test_simulador_servidor.py` (409 en ciclo), `test_preparado_suministro.py`.

## Verificación visual (Cristian)
Botón RECONOCER FALLA: con el backend real en FALLA (p. ej. provocar una falla de sensor) debe aparecer en preciclo en el lugar de INICIAR CICLO; al tocarlo, la máquina pasa a PREPARACION. Con el paro activo, el backend lo rechaza y la máquina sigue en FALLA. El simulador no alcanza FALLA.

# Revisión de seguridad y temporización — Autenticación, etapa 1

**Fecha:** 2026-10-07
**Agentes:** `safety-reviewer` (hallazgos SAF) y `timing-auditor` (hallazgos TMG), ambos solo de lectura, sobre los cambios sin commit de la etapa 1.
**Estado:** A, B, C, D, G, H y O corregidos (ver `autenticacion_etapa1_correcciones_revision.md`). E, F, K y L esperan decisión. I, J, M y N quedan para otra spec.

Los hallazgos repetidos entre los dos agentes se agrupan. **Verificado** indica que lo comprobé yo en el código, además del agente.

## Críticos y altos

### A. R-02 no ve las puertas en modo prueba — CRÍTICO (SAF-01, verificado)
- **Causa:** `_motivo_r02()` lee `estado.get_door_state()`. Ese estado solo lo actualiza `door.update()` (`simple_door.py:29` y `advanced_door.py:289`), y `_tick()` no llama a `door.update()` mientras el modo prueba está activo (`control_loop.py:171-173`). En la práctica, el estado de la puerta queda congelado en el valor que tenía al entrar al modo prueba.
- **Escenario:**
  1. Se entra al modo prueba con la puerta cerrada.
  2. Se abre la puerta, a mano o con su actuador.
  3. Se enciende `vapor_camara`. La presión sale atmosférica porque la puerta está abierta, y la puerta "sigue CERRADO".
  4. R-02 acepta: entra vapor con la puerta abierta.
- **Corrección propuesta:** en R-02, leer en vivo la entrada digital de puerta cerrada (`sensores_di`, que sí se actualiza en cada tick). Una lectura `None` cuenta como rechazo. Añadir un test con el `ControlLoop` real en modo prueba.

### B. Cerrar Tk durante un ciclo mata el backend sin apagar salidas — ALTO, crítico si la tarjeta no tiene watchdog (SAF-02, verificado)
- **Causa:** `main.py:267-281` captura el 409 de `/outputs/reset`, pero sigue y ejecuta `backend_process.terminate()`. El backend no tiene manejador de apagado. Por eso **la desviación 7 del informe de la etapa era incorrecta**: el ciclo no deja de cortarse, se sigue cortando, y ahora queda con las salidas como estaban (p. ej. `vapor_camara` encendida) y sin registrar la falla.
- **Corrección propuesta:**
  - En Tk: si `reset_outputs()` falla, no terminar el backend. Pedir confirmación y abortar con `/cycle/abort`.
  - En el backend: añadir un manejador de apagado que ejecute `ALL_OFF`.

### C. Carreras al salir del modo prueba — ALTO (SAF-03 y TMG-01)
- **Causa:** `exit_test_mode()` (lo llaman `/io/test/exit` y `/auth/logout`) y el autocancel por paro de emergencia no toman `_sm_lock`. En cambio `/io/test/output` sí lo toma.
- **Escenario:** una petición de encendido ya validada puede llegar justo después de `ALL_OFF`. La salida queda encendida con la máquina de estados ya reanudada.
- **Agravante:** `exit_test_mode` limpia la bandera antes de apagar las salidas.
- **Corrección propuesta:** `enter_test_mode`, `exit_test_mode` y el autocancel bajo `_sm_lock`; dentro de `exit_test_mode`, apagar primero y limpiar la bandera después. Volver a comprobar `_test_mode` dentro del lock antes de `state_machine.update()` (TMG-04).

### D. Trabajo lento con `_sm_lock` tomado detiene el loop — ALTO (TMG-02 y SAF-05)
- **Causa:** con el lock tomado se hacen la auditoría de cada 409 (INSERT y commit en SQLite), la escritura del YAML de calibración, `_save_cycle_json` y el `ALL_OFF` (hasta 1 s esperando el ACK).
- **Efecto:** durante CICLO, cada rechazo 409 o cada calibración del ingeniero detiene el tick completo: PWM de vapor, escapes y detección de fallas. En el peor caso pueden ser segundos, porque sqlite espera hasta 5 s si otro proceso tiene la base bloqueada.
- **Corrección propuesta:** dentro del lock, solo comprobar el estado y hacer la mutación en memoria. La auditoría, la escritura de archivos y `ALL_OFF` se hacen fuera del lock. El 409 se lanza después de soltarlo.

### E. Calibración durante CICLO sin límites — ALTO (SAF-04; es una decisión de la spec, §5.8)
- **Causa:** el ingeniero puede recalibrar `temp_camara` o `pres_camara` en plena esterilización, sin tope de gain/offset.
- **Riesgo:** un error en la calibración desplaza el control, las fallas y el F0. El ciclo puede terminar en COMPLETADO sin haber esterilizado.
- **Decisión necesaria:** esto no se corrige en código sin cambiar la spec. Opciones:
  1. Rechazar en CICLO la calibración de los sensores que usan las fases.
  2. Diferir la calibración al siguiente ciclo.
  3. Limitar el cambio a un margen.
  4. Mantener la decisión actual y registrar el riesgo.

## Medios

- **F. Modo prueba huérfano (SAF-06 y TMG-03):** los tokens no vencen y solo el dueño puede salir. Si la UI dueña se cae sin hacer logout, el modo prueba queda activo para siempre, con la máquina de estados pausada. Solo lo recuperan el paro de emergencia o reiniciar el backend. Hay además una carrera entre `enter` y `logout` simultáneos. R-02 solo se evalúa al encender, no mientras la salida sigue encendida. **Propuesta:**
  - un tiempo máximo de inactividad que saque solo del modo prueba;
  - que un ingeniero pueda forzar la salida, con auditoría;
  - apagar las salidas si la presión o la puerta salen de R-02 mientras están encendidas.
  Esto amplía la spec y necesita tu decisión.
- **G. `/io/test/output` no exige ser la sesión dueña (SAF-07):** otra pantalla puede encender salidas durante la prueba de otra persona. **Propuesta:** exigir el token dueño para encender; apagar sigue abierto a cualquier sesión de prueba.
- **H. Bloqueo por intentos con carrera entre comprobar y registrar (TMG-05):** logins en paralelo pueden probar más de 5 claves por ventana. **Propuesta:** reservar el intento de forma atómica antes de verificar.
- **I. Escrituras no atómicas de YAML y JSON (TMG-06, ya existía):** un corte de energía a mitad de la escritura corrompe la calibración o el perfil. **Propuesta:** archivo temporal, `fsync` y `os.replace`.
- **J. `cycle_logger` usa `time.time()` para medir intervalos (TMG-10, ya existía, fuera de la etapa):** viola la regla de monotonic del CLAUDE.md.

## Bajos

- **K. Resultados ignorados (SAF-08):** `set_output` y `ALL_OFF` no reportan si llegaron a la tarjeta, así que el endpoint responde `ok` y audita aunque el enlace esté caído. **Propuesta:** 503 si no se aplicó, y no encender con el enlace desconectado.
- **L. `/outputs/reset` (SAF-09 y TMG-09):**
  - Sigue sin token.
  - La comprobación y `stop()` no son atómicos.
  - `stop()` envía `ALL_OFF` antes de detener el loop (ya existía).
- **M. `all_off` comparte el evento de ACK sin serializar (TMG-08, ya existía):** ignora `all_off_timeout_s` y `all_off_intentos` de `serial_link.json`.
- **N. Migraciones entre procesos (TMG-11):** conviene usar `BEGIN IMMEDIATE` y releer `user_version` dentro de la transacción.
- **O. Autocancel por paro de emergencia:** no limpia el dueño del modo prueba ni escribe `modo_prueba_sale` en la bitácora (TMG-07).

## Preguntas de los agentes que no puedo responder desde el código

1. ¿El firmware del ESP32 apaga todas las salidas si deja de recibir `HB` o tramas? Esto decide si B y L son críticos.
2. ¿Hay salidas cuyo **apagado** es inseguro con la cámara presurizada (p. ej. aire o vacío del empaque)? Afecta a la regla "apagar siempre permitido".
3. ¿`pres_camara` y `presion_admosferica` usan la misma referencia (absoluta o manométrica)? ¿Hay tope para `rango_presion_atm`? Un rango grande anula R-02.
4. ¿Qué estados de la máquina reescriben todas sus salidas en cada tick? Esto define cuánto dura una salida que quedó encendida por las carreras de C.

## Propuesta

**Dentro del alcance de la etapa 1, sin cambiar decisiones de la spec:**
- A (puertas en vivo en R-02)
- B (cierre de Tk y apagado del backend)
- C (lock al salir del modo prueba)
- D (sacar trabajo lento del lock)
- G (dueño para encender)
- H (intento atómico)
- O (limpiar dueño y auditar el autocancel)

**Necesitan tu decisión** porque cambian o amplían la spec:
- E (calibración en CICLO)
- F (salida forzada o timeout del modo prueba, supervisión continua)
- K (503)
- L (token en `/outputs/reset`)

**Preexistentes, se pueden dejar para otra spec:** I, J, M y N.

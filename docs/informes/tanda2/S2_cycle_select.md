# S2 — `POST /cycle/select`

Instrucción: `instruccion_claude_code_tanda_2.md` §2 S2 y decisión 2. Cambiar de programa sin sesión y en FALLA es lo deseado: ningún fallo exige técnico.

## Situación encontrada

- `ControlLoop.set_active_cycle` (`control_loop.py`) **solo rechazaba CICLO**. Se colaba con:
  - el **paro activo**;
  - el **estado seguro en curso o pendiente de confirmar**;
  - la **recuperación pendiente** tras un reinicio.

  En esos casos se reconstruía la StateMachine. Entre otras cosas, se volvía a enlazar `estado_seguro.mantener_drenaje` a un `CicloState` nuevo.
- El cambio **no se registraba** en la bitácora.
- El único cliente es la ruta tkinter (`ui/window/main_window.py`, que R1 retira). Ninguna UI QML lo llama.

Las pruebas nuevas fallaron con el código previo (7 de 9) antes de corregirlo.

## Qué se hizo

- **`ControlLoop._motivo_no_cambiar_ciclo()`** (bajo `_sm_lock`) rechaza el cambio con:
  - CICLO, que incluye la espera de confirmación;
  - EMERGENCIA o HIBERNACION;
  - paro activo (sin conexión con la tarjeta el mensaje lo dice);
  - estado seguro activo o pendiente;
  - recuperación pendiente;
  - **inicio ya pedido** (`START_CICLO`);
  - modo prueba;
  - apagado en curso;
  - configuración inválida.

  **En FALLA, sin nada de lo anterior, se permite** (decisión 2).
- **`POST /cycle/select`**:
  - **Origen declarado:** campo `origen` opcional del cuerpo, de una lista cerrada (`puerta_1`, `puerta_2`, `remoto`, `desconocido`; sin campo = `desconocido`). Un valor fuera de la lista se rechaza con 422 `origen_invalido`.
  - **Bitácora:**
    - `PROGRAMA_SELECCIONADO` lleva `valor_anterior`/`valor_nuevo` (ids), el nombre del programa, `origen`, `origen_autenticado: false`, `cliente` (IP) y `estado`.
    - **Todos los rechazos** quedan como `PROGRAMA_SELECCION_RECHAZADA`, con el código y el motivo: 404, 422 de fábrica, origen inválido, dañado, líquidos y cambio no permitido.
  - **Programa dañado (RB-04.4):** sigue rechazado con 409 `PROGRAMA_NO_EDITABLE`.
  - **Líquidos:** un programa de carga líquida en un equipo sin capacidad de líquidos se rechaza también al seleccionarlo (T11).
  - **Lectura del programa anterior, cambio en el lazo y cambio en el `CycleManager`:** juntos bajo `bloqueo_maquina()`. La bitácora se escribe al soltar el lock.
- **`POST /cycle/start`:** la validación del programa (dañado, líquidos, RS-06) y `START_CICLO` van juntas bajo `bloqueo_maquina()` (nueva `_validar_inicio`). Un `select` concurrente ya no puede cambiar el programa entre la validación y el inicio.
- **`_auditar` sin base de datos:** deja el evento en el log de texto como advertencia, sin traza (T8: sin base no hay bitácora).

## Pruebas

- Antes: 3394. Después: 3413.
- Nueva `tests/test_s2_cycle_select.py`:
  - FALLA se permite;
  - paro, estado seguro (en curso o por confirmar), recuperación, EMERGENCIA/HIBERNACION, inicio ya pedido, apagado, configuración inválida y modo prueba se rechazan;
  - bitácora con el origen y "desconocido";
  - rechazos auditados con el origen;
  - origen inválido;
  - dañado sigue rechazado;
  - lazo y `CycleManager` bajo el mismo lock.

  Las pruebas de la revisión se escribieron después de la corrección.
- Ajustadas:
  - fixtures que no consideraban que el paro arranca activo (falla cerrada hasta el primer dato, PF-21): `test_control_loop_set_active_cycle`, `test_alarm_manager_unico`, `test_t3_sensores_ciclo`, `test_t5_estado_seguro`, `test_e1_supply_inputs_loop_status`;
  - HIBERNACION ya no está entre los estados permitidos.

## Revisores

**timing-auditor:**
- TMG-01 (**Alto**): `set_active_cycle` y `set_default_cycle` no eran atómicos; la pantalla podía mostrar un programa y ejecutar otro. **Corregido.**
- TMG-02 (Medio): `/cycle/start` validaba fuera del lock y un `select` podía colarse. **Corregido** con el lock y el rechazo con `START_CICLO` pendiente.
- TMG-03 (Medio): `valor_anterior` se leía fuera del lock. **Corregido.**
- TMG-04 (Bajo): mensaje engañoso con el enlace caído. **Corregido.**
- TMG-05 (Bajo): ruido en el log sin base de datos. **Corregido.**
- TMG-06 (Bajo): rechazos sin el mismo evento. **Corregido.**

**safety-reviewer:** sin Críticos ni Altos.
- S2-01 (Medio, programa distinto del validado): **corregido**, igual que TMG-02, más la comprobación de líquidos al seleccionar.
- S2-02 (Medio): igual que TMG-01. **Corregido.**
- S2-03 (Medio, la auditoría no atribuye el cambio): **corregido parcialmente** con la lista cerrada de origen, `origen_autenticado: false` y el nombre del programa. La atribución a una persona no es posible sin sesión. Riesgo aceptado por la decisión 2; ver D-S2-1.
- S2-04, S2-05, S2-06 y S2-07 (Bajos): **corregidos**.
- Pregunta abierta del revisor: si `ProtocoloFallo.ejecutar()` lanzara una excepción antes de marcarse ejecutado, el estado seguro no se activaría y el cambio de programa estaría permitido. Es anterior a S2; queda como PENDIENTE de análisis.

## DECISIONES SIN CONFIRMAR

- **D-S2-1:** el origen es **declarado** por el cliente, no autenticado. La bitácora lo marca así (`origen_autenticado: false`). Para el expediente 62304 se documenta como riesgo aceptado de trazabilidad (decisión 2: sin sesión). Alternativa: si llega un token válido, registrar también usuario y rol.
- **D-S2-2:** en modo prueba no se permite cambiar de programa, aunque la máquina esté en un estado que lo admitiría.

## Comprobaciones manuales

1. En FALLA, sin sesión, cambiar de programa: se acepta y aparece `PROGRAMA_SELECCIONADO` en `audit_log`.
2. Con el paro pulsado, o con "Confirmar y llevar a estado seguro" pendiente, intentar cambiar: se rechaza y queda `PROGRAMA_SELECCION_RECHAZADA`.
